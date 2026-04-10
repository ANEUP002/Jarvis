import time
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console

from app.queue_manager import (
    get_pending_tasks,
    load_json,
    save_json,
    move_file,
    IN_PROGRESS,
    COMPLETED,
    FAILED,
)
from app.classifier import classify
from app.model_selector import select_model
from app.state import add_log, update_state
from app.router import execute_single_task
from agents.chief_agent import plan_task, combine_results


console = Console()

VALID_TASK_TYPES = {"code", "writer", "research"}


def run_subtasks(task: Dict[str, Any], subtasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    subtask_results = []

    for subtask in subtasks:
        # 🔥 Build context from previous results
        context_text = "\n\n".join([
            f"Subtask {r['id']} ({r['task_type']}):\n{r['result'].get('response', '')}"
            for r in subtask_results
        ]) if subtask_results else "None"

        enhanced_input = f"""
MAIN TASK:
{task["input"]}

CURRENT SUBTASK:
{subtask["input"]}

PREVIOUS RESULTS:
{context_text}

INSTRUCTION:
Use previous results if useful.
Return only the best output.
""".strip()

        model = select_model(subtask["task_type"], enhanced_input)

        enhanced_task = {
            "task_type": subtask["task_type"],
            "input": enhanced_input,
            "model": model  # 🔥 CRITICAL FIX
        }
                

        routing_output = execute_single_task({
        "task_type": task["task_type"],
        "input": task["input"],
        "model": task["model"]  # 🔥 CRITICAL FIX
    })
        subtask_results.append({
            "id": subtask["id"],
            "task_type": subtask["task_type"],
            "result": routing_output["result"]
        })

    return subtask_results

def process_task(task_file: Path) -> None:
    if not task_file.exists():
        return

    update_state("status", "running")
    update_state("current_task", task_file.name)

    add_log(f"Picked up task: {task_file.name}")
    console.print(f"[cyan]Processing[/cyan] {task_file.name}")

    in_progress_file = move_file(task_file, IN_PROGRESS)

    try:
        task = load_json(in_progress_file)
        task["status"] = "in_progress"

        # 1. classify task
        classification = classify(task.get("input", ""))
        task_type = classification.get("type", "research")

        if task_type not in VALID_TASK_TYPES:
            task_type = "research"

        confidence = classification.get("confidence", 0.0)
        source = classification.get("source", "unknown")

        task["task_type"] = task_type
        task["classification"] = classification

        update_state("current_classification", {
            "type": task_type,
            "confidence": confidence,
            "source": source
        })

        add_log(
            f"[CLASSIFIER] type={task_type} | conf={confidence:.2f} | source={source}"
        )

        # 2. chief agent plans execution
        chief_plan = plan_task(task.get("input", ""))
        task["chief_plan"] = chief_plan
        add_log(f"[CHIEF] mode={chief_plan.get('mode')}")

        # 3. choose model for top-level task
        model = select_model(task_type)
        task["model"] = model
        update_state("current_model", model)
        add_log(f"Selected model: {model}")

        # 4. execute
        mode = chief_plan.get("mode", "simple")
        if mode == "multi":
            subtasks = chief_plan.get("subtasks", [])
            add_log(f"[CHIEF] executing {len(subtasks)} subtasks")

            subtask_results = run_subtasks(task, subtasks)
            final_result = combine_results(task.get("input", ""), subtask_results)

            task["agent"] = "chief"
            update_state("current_agent", "chief")
            add_log("Assigned agent (from chief): chief")

            task["result"] = final_result
        else:
            planned_type = chief_plan.get("task_type", task_type)
            if planned_type not in VALID_TASK_TYPES:
                planned_type = task_type

            task["task_type"] = planned_type

            routing_output = execute_single_task(task)

            result = routing_output.get("result")
            agent_name = routing_output.get("agent", "research")

            task["agent"] = agent_name
            update_state("current_agent", agent_name)
            add_log(f"Assigned agent (from router): {agent_name}")

            task["result"] = result

        task["status"] = "completed"

        save_json(in_progress_file, task)
        completed_file = move_file(in_progress_file, COMPLETED)

        add_log(f"Task completed: {completed_file.name}")
        console.print(f"[green]Completed[/green] {completed_file.name}")

    except Exception as e:
        try:
            task["status"] = "failed"
            task["error"] = str(e)
            save_json(in_progress_file, task)
            failed_file = move_file(in_progress_file, FAILED)
            add_log(f"Task failed: {failed_file.name} | Error: {e}")
            console.print(f"[red]Failed[/red] {failed_file.name} -> {e}")
        except Exception:
            console.print(f"[red]Failed[/red] {task_file.name} -> {e}")

    finally:
        update_state("status", "idle")
        update_state("current_task", None)
        update_state("current_agent", None)
        update_state("current_model", None)
        update_state("current_classification", None)


def main() -> None:
    console.print("[bold green]OfficeOS Orchestrator is running...[/bold green]")

    while True:
        pending_tasks = get_pending_tasks()

        if pending_tasks:
            task_file = pending_tasks[0]

            if task_file.exists():
                process_task(task_file)

        time.sleep(1)


if __name__ == "__main__":
    main()