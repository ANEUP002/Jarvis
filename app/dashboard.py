import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.event_streaming import event_stream
from app.queue_manager import COMPLETED, FAILED, IN_PROGRESS, PENDING, load_json
from app.state import STATE_FILE, get_state
from tools.notes_tools import GetNoteGraphTool, GetNoteTool, _find_backlinks, _list_note_records, summarize_task_memory
from tools.personal_tools import get_routine_snapshot


QUEUE_FOLDERS = [PENDING, IN_PROGRESS, COMPLETED, FAILED]


def get_live_events(limit: int = 100, event_type: str = None, level: str = None) -> List[Dict[str, Any]]:
    """Return the most recent live events for dashboard polling."""
    return event_stream.get_events(limit=limit, event_type=event_type, level=level)


def get_event_stats() -> Dict[str, Any]:
    """Return live event statistics for dashboard summaries."""
    return event_stream.get_stats()


def get_task_timeline(task_id: str) -> List[Dict[str, Any]]:
    """Return a timeline of events for a specific task."""
    return event_stream.get_timeline(task_id=task_id)


def clear_dashboard_events() -> None:
    """Clear the in-memory dashboard event buffer."""
    event_stream.clear_events()


def get_dashboard_snapshot() -> Dict[str, Any]:
    """Return a single HUD-friendly snapshot."""
    state = get_state()
    events = get_live_events(limit=80)
    return {
        "state": state,
        "events": events,
        "event_stats": get_event_stats(),
        "routine": get_routine_snapshot(),
        "queue": get_queue_snapshot(),
        "agent_graph": get_agent_graph_snapshot(),
        "recent_tasks": get_recent_tasks(),
        "focus": get_focus_summary(state, events),
        "diagnostics": get_system_diagnostics(state, events),
        "notes": get_notes_snapshot(),
        "second_brain_graph": get_second_brain_graph_snapshot(),
    }


def get_queue_snapshot() -> Dict[str, Any]:
    return {
        "pending": len(list(PENDING.glob("*.json"))),
        "in_progress": len(list(IN_PROGRESS.glob("*.json"))),
        "completed": len(list(COMPLETED.glob("*.json"))),
        "failed": len(list(FAILED.glob("*.json"))),
    }


def get_recent_tasks(limit: int = 10) -> List[Dict[str, Any]]:
    task_files = sorted(
        list(COMPLETED.glob("*.json")) + list(FAILED.glob("*.json")) + list(IN_PROGRESS.glob("*.json")),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    tasks = []
    for path in task_files[:limit]:
        try:
            data = load_json(path)
            tasks.append({
                "task_id": _normalize_task_id(data.get("task_id", path.name)),
                "status": data.get("status"),
                "task_type": data.get("task_type"),
                "agent": data.get("agent"),
                "model": data.get("model"),
                "updated_at": path.stat().st_mtime,
            })
        except Exception:
            continue
    return tasks


def find_task_file(task_id: str) -> Optional[Path]:
    for folder in QUEUE_FOLDERS:
        candidate = folder / task_id
        if candidate.exists():
            return candidate
        if not candidate.suffix:
            with_suffix = candidate.with_suffix(".json")
            if with_suffix.exists():
                return with_suffix
    return None


def get_task_record(task_id: str) -> Optional[Dict[str, Any]]:
    path = find_task_file(task_id)
    if not path:
        return None

    data = load_json(path)
    normalized_task_id = _normalize_task_id(data.get("task_id", task_id))
    timeline = get_task_timeline(normalized_task_id)
    return {
        "task": {**data, "task_id": normalized_task_id},
        "timeline": timeline,
        "memory_workflow": summarize_task_memory(data),
        "file_path": str(path.resolve()),
        "folder": path.parent.name,
        "updated_at": path.stat().st_mtime,
    }


def get_note_record(note_id: str) -> Optional[Dict[str, Any]]:
    result = GetNoteTool().execute(note_id=note_id)
    if not result.get("success"):
        return None
    return result.get("result")


def get_focus_summary(state: Dict[str, Any], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    active_subtasks = state.get("active_subtasks", [])
    plan = state.get("current_plan") or {}
    event_types = {}
    for event in events[-20:]:
        event_type = event.get("type", "unknown")
        event_types[event_type] = event_types.get(event_type, 0) + 1

    hottest_events = sorted(event_types.items(), key=lambda item: item[1], reverse=True)[:3]
    return {
        "active_subtasks": len(active_subtasks),
        "plan_mode": plan.get("mode") if isinstance(plan, dict) else None,
        "selected_tools": len(state.get("current_tools") or []),
        "hottest_events": [{"type": event_type, "count": count} for event_type, count in hottest_events],
    }


def _normalize_task_id(task_id: str) -> str:
    if isinstance(task_id, str) and task_id.endswith(".json"):
        return task_id[:-5]
    return task_id


def get_system_diagnostics(state: Dict[str, Any], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    now = time.time()
    worker_last_seen = STATE_FILE.stat().st_mtime if STATE_FILE.exists() else None
    worker_connected = bool(worker_last_seen and (now - worker_last_seen) < 15)
    current_task = _normalize_task_id(state.get("current_task"))
    in_progress_files = list(IN_PROGRESS.glob("*.json"))
    stale_in_progress = []

    for path in in_progress_files:
        age_seconds = now - path.stat().st_mtime
        if age_seconds > 120:
            stale_in_progress.append({
                "task_id": path.stem,
                "age_seconds": int(age_seconds),
            })

    latest_event_at = events[-1]["timestamp"] if events else None
    return {
        "worker_connected": worker_connected,
        "worker_last_seen": worker_last_seen,
        "current_task": current_task,
        "queue_active": bool(in_progress_files or list(PENDING.glob("*.json"))),
        "in_progress_count": len(in_progress_files),
        "stale_in_progress": stale_in_progress[:5],
        "latest_event_at": latest_event_at,
        "ready": worker_connected and not stale_in_progress,
    }


def get_notes_snapshot(limit: int = 8) -> Dict[str, Any]:
    notes = _list_note_records()
    recent_notes = []
    for note in notes[:limit]:
        recent_notes.append({
            "note_id": note["note_id"],
            "title": note["title"],
            "category": note.get("category", ""),
            "tags": note["tags"],
            "updated_at": note["updated_at"],
            "links_count": len(note["links"]),
            "backlinks_count": len(_find_backlinks(note["title"])),
        })

    return {
        "count": len(notes),
        "recent": recent_notes,
    }


def get_second_brain_graph_snapshot(limit: int = 40) -> Dict[str, Any]:
    graph_result = GetNoteGraphTool().execute(limit=limit)
    graph = graph_result.get("result", {"nodes": [], "edges": []}) if graph_result.get("success") else {"nodes": [], "edges": []}
    task_nodes = []
    task_edges = []

    for task in get_recent_tasks(limit=12):
        task_node_id = f"task:{task['task_id']}"
        task_nodes.append({
            "id": task_node_id,
            "label": task["task_id"],
            "type": "task_record",
            "status": task.get("status"),
        })

    for node in graph.get("nodes", []):
        source_task_id = node.get("source_task_id")
        if source_task_id:
            task_edges.append({
                "source": f"task:{source_task_id}",
                "target": node["id"],
                "label": "captured_as",
            })
        node["type"] = "note"

    return {
        "nodes": task_nodes + graph.get("nodes", []),
        "edges": task_edges + graph.get("edges", []),
    }


def get_agent_graph_snapshot() -> Dict[str, Any]:
    state = get_state()
    nodes = []
    edges = []

    if state.get("current_task"):
        nodes.append({
            "id": state["current_task"],
            "type": "task",
            "label": state["current_task"],
            "status": state.get("status"),
        })

    if state.get("current_agent"):
        agent_id = f"agent:{state['current_agent']}"
        nodes.append({
            "id": agent_id,
            "type": "agent",
            "label": state["current_agent"],
            "status": "active",
            "model": state.get("current_model"),
        })
        if state.get("current_task"):
            edges.append({
                "source": state["current_task"],
                "target": agent_id,
                "label": "assigned_to",
            })

    for subtask in state.get("active_subtasks", []):
        subtask_id = f"subtask:{subtask.get('id')}"
        nodes.append({
            "id": subtask_id,
            "type": "subtask",
            "label": f"{subtask.get('task_type')}:{subtask.get('id')}",
            "status": subtask.get("status"),
            "model": subtask.get("model"),
            "fallback_used": subtask.get("fallback_used", False),
        })
        if state.get("current_task"):
            edges.append({
                "source": state["current_task"],
                "target": subtask_id,
                "label": "contains",
            })

    if state.get("current_tool"):
        tool_id = f"tool:{state['current_tool']}"
        nodes.append({
            "id": tool_id,
            "type": "tool",
            "label": state["current_tool"],
            "status": "active",
            "service": state.get("current_external_service"),
        })
        if state.get("current_agent"):
            edges.append({
                "source": f"agent:{state['current_agent']}",
                "target": tool_id,
                "label": "uses",
            })

    return {"nodes": nodes, "edges": edges}
