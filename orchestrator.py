import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List

from rich.console import Console

from agents.chief_agent import combine_results, plan_task
from app.assistant_fastlane import handle_fastlane
from app.classifier import classify
from app.event_streaming import event_stream
from app.model_selector import select_model
from app.queue_manager import (
    COMPLETED,
    FAILED,
    IN_PROGRESS,
    get_pending_tasks,
    load_json,
    move_file,
    save_json,
)
from app.router import execute_single_task
from app.state import add_log, record_task_metrics, update_state
from app.tool_selector import ToolSelector
from tools.notes_tools import save_task_result_note, summarize_task_memory


console = Console()
VALID_TASK_TYPES = {"code", "writer", "research"}


def _normalize_task_type(task_type: str) -> str:
    return task_type if task_type in VALID_TASK_TYPES else "research"


def _emit(event_type: str, payload: Dict, level: str = "info") -> None:
    try:
        event_stream.emit(event_type, payload, level=level)
    except Exception:
        pass


def _set_active_subtasks(subtasks: List[Dict]) -> None:
    update_state("active_subtasks", subtasks)


def _extract_response_text(result: Dict) -> str:
    if not isinstance(result, dict):
        return str(result or "")
    if isinstance(result.get("response"), str):
        return result.get("response", "")
    if isinstance(result.get("result"), dict) and isinstance(result["result"].get("response"), str):
        return result["result"].get("response", "")
    return str(result)


def _execute_subtask(task: Dict, subtask: Dict) -> Dict:
    subtask_type = _normalize_task_type(subtask.get("task_type", "research"))

    enhanced_input = f"""
MAIN TASK:
{task["input"]}

CURRENT SUBTASK:
{subtask["input"]}

NOTE:
This subtask is running in parallel with other subtasks.
Avoid depending on the output of other subtasks.
Return only the best output for this subtask.
""".strip()

    model = select_model(subtask_type, complexity="complex", task_input=enhanced_input)
    enhanced_task = {
        "task_type": subtask_type,
        "input": enhanced_input,
        "model": model,
        "complexity": "complex",
    }

    add_log(f"[SUBTASK {subtask.get('id')}] type={subtask_type} | model={model}")
    _emit(
        "subtask_started",
        {
            "task_id": task.get("task_id"),
            "subtask_id": subtask.get("id"),
            "task_type": subtask_type,
            "model": model,
        },
    )

    routing_output = execute_single_task(enhanced_task)
    return {
        "id": subtask.get("id", 0),
        "task_type": subtask_type,
        "result": routing_output.get("result", {"response": ""}),
        "fallback_used": routing_output.get("fallback_used", False),
        "model": routing_output.get("model"),
        "llm": routing_output.get("llm", {}),
    }


def run_subtasks(task: Dict, subtasks: List[Dict], on_subtask_done=None) -> Dict:
    """
    on_subtask_done(result, done_count, total_count) — optional callback fired
    each time a subtask completes. Used by jarvis.py for live voice narration.
    """
    subtask_results: List[Dict] = []
    fallback_count = 0

    if not subtasks:
        return {"subtask_results": [], "fallback_count": 0}

    _set_active_subtasks(
        [
            {
                "id": subtask.get("id"),
                "task_type": _normalize_task_type(subtask.get("task_type", "research")),
                "status": "pending",
                "model": None,
                "fallback_used": False,
            }
            for subtask in subtasks
        ]
    )

    with ThreadPoolExecutor(max_workers=min(4, len(subtasks))) as executor:
        future_to_subtask = {
            executor.submit(_execute_subtask, task, subtask): subtask
            for subtask in subtasks
        }

        for future in as_completed(future_to_subtask):
            subtask = future_to_subtask[future]
            try:
                result = future.result()
                if result.get("fallback_used"):
                    fallback_count += 1
                subtask_results.append(result)

                if on_subtask_done:
                    try:
                        on_subtask_done(result, len(subtask_results), len(subtasks))
                    except Exception:
                        pass

                _set_active_subtasks(
                    [
                        {
                            "id": item.get("id"),
                            "task_type": item.get("task_type"),
                            "status": "completed",
                            "model": item.get("model"),
                            "fallback_used": item.get("fallback_used", False),
                        }
                        for item in subtask_results
                    ]
                )

                _emit(
                    "subtask_completed",
                    {
                        "task_id": task.get("task_id"),
                        "subtask_id": result.get("id"),
                        "task_type": result.get("task_type"),
                        "fallback_used": result.get("fallback_used", False),
                        "model": result.get("model"),
                    },
                )
            except Exception as exc:
                add_log(f"[SUBTASK ERROR] id={subtask.get('id')} | {exc}")
                console.print(f"[red]Subtask {subtask.get('id')} failed:[/red] {exc}")
                _emit(
                    "subtask_failed",
                    {
                        "task_id": task.get("task_id"),
                        "subtask_id": subtask.get("id"),
                        "task_type": _normalize_task_type(subtask.get("task_type", "research")),
                        "error": str(exc),
                    },
                    level="error",
                )
                subtask_results.append(
                    {
                        "id": subtask.get("id", 0),
                        "task_type": _normalize_task_type(subtask.get("task_type", "research")),
                        "result": {"response": f"[ERROR] {exc}"},
                        "fallback_used": False,
                        "model": None,
                        "llm": {},
                    }
                )

    subtask_results = sorted(subtask_results, key=lambda item: item.get("id", 0))
    return {"subtask_results": subtask_results, "fallback_count": fallback_count}


def process_task(task_file: Path) -> None:
    if not task_file.exists():
        return

    task_id = task_file.stem
    update_state("status", "running")
    update_state("current_task", task_id)
    add_log(f"Picked up task: {task_id}")
    console.print(f"[cyan]Processing[/cyan] {task_id}")

    _emit("task_started", {"task_id": task_id, "input": str(task_file.name)})

    in_progress_file = move_file(task_file, IN_PROGRESS)
    task = {}
    task_start = time.time()
    task_type = "research"
    complexity = "simple"

    try:
        task = load_json(in_progress_file)
        task["status"] = "in_progress"
        task["task_id"] = task_id
        save_json(in_progress_file, task)

        fastlane_result = handle_fastlane(task.get("input", ""))
        if fastlane_result and fastlane_result.get("handled"):
            task_type = _normalize_task_type(fastlane_result.get("task_type", "research"))
            complexity = "simple"
            classification = {
                "type": task_type,
                "confidence": 1.0,
                "complexity": complexity,
                "source": f"assistant_fastlane:{fastlane_result.get('kind', 'local')}",
            }
            chief_plan = {
                "mode": "simple",
                "task_type": task_type,
                "source": "assistant_fastlane",
            }
            model_used = fastlane_result.get("model_used", "local:assistant_fastlane")
            task["task_type"] = task_type
            task["classification"] = classification
            task["chief_plan"] = chief_plan
            task["tools"] = {
                "primary_tools": ["get_weather"] if model_used == "tool:get_weather" else [],
                "secondary_tools": [],
            }
            task["agent"] = fastlane_result.get("agent", "assistant_fastlane")
            task["model"] = model_used
            task["result"] = {
                "response": fastlane_result.get("response", ""),
                "fastlane": True,
                "kind": fastlane_result.get("kind"),
                "payload": fastlane_result.get("payload"),
                "llm": {
                    "model_used": model_used,
                    "fallback_used": False,
                },
            }
            task["fallback_count"] = 0
            task["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

            update_state("current_classification", classification)
            update_state("current_plan", chief_plan)
            update_state("current_model", model_used)
            update_state("current_agent", task["agent"])
            update_state("current_tools", task["tools"]["primary_tools"])
            add_log(
                f"[FASTLANE] kind={fastlane_result.get('kind')} | "
                f"agent={task['agent']} | model={model_used}"
            )
            _emit(
                "task_fastlane_completed",
                {
                    "task_id": task_id,
                    "kind": fastlane_result.get("kind"),
                    "agent": task["agent"],
                    "model": model_used,
                },
            )

            task["status"] = "completed"
            task["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            task["second_brain"] = {
                "status": "skipped",
                "reason": "fastlane_request",
            }
            task["memory_workflow"] = {
                "used_memory": False,
                "notes_used": [],
                "memory_summary": "",
                "captured_notes": [],
                "status": "skipped",
            }
            _emit(
                "second_brain_updated",
                {
                    "task_id": task_id,
                    "memory_workflow": task["memory_workflow"],
                },
            )
            duration = time.time() - task_start
            record_task_metrics(
                task_type,
                complexity,
                duration,
                success=True,
                model=model_used,
                fallback_used=False,
            )
            save_json(in_progress_file, task)
            completed_file = move_file(in_progress_file, COMPLETED)
            add_log(f"Task completed: {completed_file.name}")
            console.print(f"[green]Completed[/green] {completed_file.name}")
            _emit(
                "task_completed",
                {
                    "task_id": task_id,
                    "status": "completed",
                    "duration": duration,
                    "agent": task.get("agent"),
                    "model": task.get("model"),
                },
            )
            return

        classification = classify(task.get("input", ""))
        task_type = _normalize_task_type(classification.get("type", "research"))
        complexity = classification.get("complexity", "simple")

        task["task_type"] = task_type
        task["classification"] = classification
        task["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

        update_state("current_classification", classification)
        add_log(
            f"[CLASSIFIER] type={task_type} | "
            f"conf={classification.get('confidence', 0):.2f} | "
            f"complexity={complexity} | "
            f"source={classification.get('source', 'unknown')}"
        )
        _emit(
            "task_classified",
            {
                "task_id": task_id,
                "task_type": task_type,
                "complexity": complexity,
                "classification": classification,
            },
        )

        chief_plan = plan_task(task.get("input", ""))
        task["chief_plan"] = chief_plan
        task["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        update_state("current_plan", chief_plan)
        add_log(f"[CHIEF] mode={chief_plan.get('mode')}")

        model = select_model(task_type, complexity=complexity, task_input=task.get("input", ""))
        task["model"] = model
        task["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        update_state("current_model", model)
        add_log(f"[MODEL] {task_type} + {complexity} -> {model}")
        _emit(
            "model_selected",
            {
                "task_id": task_id,
                "task_type": task_type,
                "complexity": complexity,
                "model": model,
            },
        )

        tool_selection = ToolSelector.select_tools(
            task_type,
            complexity=complexity,
            task_context=task,
        )
        task["tools"] = tool_selection
        task["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        update_state("current_tools", tool_selection.get("primary_tools", []))
        add_log(
            f"[TOOLS] primary={tool_selection.get('primary_tools', [])} | "
            f"secondary={tool_selection.get('secondary_tools', [])}"
        )
        _emit("tools_selected", {"task_id": task_id, "tools": tool_selection})

        mode = chief_plan.get("mode", "simple")
        save_json(in_progress_file, task)

        if mode == "multi":
            subtasks = chief_plan.get("subtasks", [])
            if not subtasks:
                add_log("[CHIEF] multi mode but no subtasks - falling back to simple")
                mode = "simple"
            else:
                add_log(f"[CHIEF] executing {len(subtasks)} subtasks")
                _emit(
                    "execution_started",
                    {"task_id": task_id, "mode": "multi", "subtasks": len(subtasks)},
                )
                subtask_data = run_subtasks(task, subtasks)
                final_result = combine_results(task.get("input", ""), subtask_data["subtask_results"])

                task["agent"] = "chief"
                task["result"] = final_result
                task["fallback_count"] = subtask_data.get("fallback_count", 0)
                task["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

                update_state("current_agent", "chief")
                add_log("Assigned agent: chief")
                _emit("agent_assigned", {"task_id": task_id, "agent": "chief", "mode": "multi"})
                _emit(
                    "result_generated",
                    {
                        "task_id": task_id,
                        "agent": "chief",
                        "model": task.get("model"),
                        "fallback_used": bool(task.get("fallback_count", 0)),
                        "has_response": bool(final_result.get("response")),
                    },
                )
                _emit(
                    "execution_completed",
                    {
                        "task_id": task_id,
                        "mode": "multi",
                        "subtasks_completed": len(subtask_data["subtask_results"]),
                        "fallback_count": subtask_data.get("fallback_count", 0),
                    },
                )

        if mode == "simple":
            planned_type = _normalize_task_type(chief_plan.get("task_type", task_type))
            task["task_type"] = planned_type

            _emit(
                "execution_started",
                {"task_id": task_id, "mode": "simple", "agent": planned_type},
            )
            routing_output = execute_single_task(task)

            result = routing_output.get("result", {"response": "[NO RESULT]"})
            agent_name = routing_output.get("agent", "research")
            fallback_used = routing_output.get("fallback_used", False)
            actual_model = routing_output.get("model", task.get("model"))

            task["agent"] = agent_name
            task["result"] = result
            task["model"] = actual_model
            task["fallback_count"] = 1 if fallback_used else 0
            task["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

            update_state("current_agent", agent_name)
            update_state("current_model", actual_model)
            add_log(f"Assigned agent: {agent_name}")
            _emit("agent_assigned", {"task_id": task_id, "agent": agent_name, "mode": "simple"})
            _emit(
                "result_generated",
                {
                    "task_id": task_id,
                    "agent": agent_name,
                    "model": actual_model,
                    "fallback_used": fallback_used,
                    "has_response": bool(result.get("response")),
                },
            )
            _emit(
                "execution_completed",
                {
                    "task_id": task_id,
                    "mode": "simple",
                    "agent": agent_name,
                    "fallback_used": fallback_used,
                    "model": actual_model,
                },
            )

        task["status"] = "completed"
        task["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        note_capture = save_task_result_note(task, _extract_response_text(task.get("result", {})))
        task["second_brain"] = {
            "status": "saved" if note_capture.get("success") else "error",
            "note": note_capture.get("result"),
            "error": note_capture.get("error"),
        }
        task["memory_workflow"] = summarize_task_memory(task)
        _emit(
            "second_brain_updated",
            {
                "task_id": task_id,
                "memory_workflow": task["memory_workflow"],
            },
        )
        duration = time.time() - task_start
        record_task_metrics(
            task_type,
            complexity,
            duration,
            success=True,
            model=task.get("model", ""),
            fallback_used=bool(task.get("fallback_count", 0)),
        )
        save_json(in_progress_file, task)
        completed_file = move_file(in_progress_file, COMPLETED)

        add_log(f"Task completed: {completed_file.name}")
        console.print(f"[green]Completed[/green] {completed_file.name}")
        _emit(
            "task_completed",
            {
                "task_id": task_id,
                "status": "completed",
                "duration": duration,
                "agent": task.get("agent"),
                "model": task.get("model"),
            },
        )

    except Exception as exc:
        try:
            task["status"] = "failed"
            task["error"] = str(exc)
            task["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            duration = time.time() - task_start
            record_task_metrics(
                task_type,
                complexity,
                duration,
                success=False,
                model=task.get("model", ""),
                fallback_used=bool(task.get("fallback_count", 0)),
            )
            save_json(in_progress_file, task)
            failed_file = move_file(in_progress_file, FAILED)
            add_log(f"Task failed: {failed_file.name} | Error: {exc}")
            console.print(f"[red]Failed[/red] {failed_file.name} -> {exc}")
            _emit(
                "execution_failed",
                {
                    "task_id": task_id,
                    "agent": task.get("agent"),
                    "model": task.get("model"),
                    "error": str(exc),
                },
                level="error",
            )
            _emit(
                "error_occurred",
                {"task_id": task_id, "error": str(exc), "stage": "execution"},
                level="error",
            )
        except Exception as inner_exc:
            console.print(f"[red]Critical failure[/red] {task_file.name} -> {exc} | inner: {inner_exc}")

    finally:
        update_state("status", "idle")
        update_state("current_task", None)
        update_state("current_agent", None)
        update_state("current_model", None)
        update_state("current_classification", None)
        update_state("current_tools", [])
        update_state("current_plan", None)
        update_state("active_subtasks", [])


def main() -> None:
    console.print("[bold green]OfficeOS Orchestrator is running...[/bold green]")

    while True:
        try:
            pending_tasks = get_pending_tasks()
            if pending_tasks:
                task_file = pending_tasks[0]
                if task_file.exists():
                    process_task(task_file)
        except Exception as exc:
            console.print(f"[red]Orchestrator loop error:[/red] {exc}")
            add_log(f"[ORCHESTRATOR ERROR] {exc}")

        time.sleep(1)


if __name__ == "__main__":
    main()
