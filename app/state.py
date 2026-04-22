import json
import time
from pathlib import Path
from typing import Any, Dict


# =========================
# LIVE SYSTEM STATE
# =========================
# This is the single source of truth for the orchestrator's runtime.
# The HUD dashboard will read from this to show live status.
# =========================

METRICS_FILE = Path("logs/metrics.json")
STATE_FILE = Path("logs/live_state.json")

STATE: Dict[str, Any] = {
    "status": "idle",               # idle | running
    "current_task": None,           # current task filename
    "current_agent": None,          # which agent is active
    "current_model": None,          # which model is being used
    "current_classification": None, # full classification dict {type, confidence, complexity, source}
    "current_tools": [],            # selected tools for current task
    "current_plan": None,           # chief plan for current task
    "active_subtasks": [],          # active subtasks for HUD graph
    "current_tool": None,           # currently active tool
    "current_tool_arguments": None, # safe tool argument summary
    "current_external_service": None, # e.g. openrouter, serpapi, spotify
    "logs": [],                     # recent log entries (last 100)
    "metrics": {
        "tasks_total": 0,
        "tasks_completed": 0,
        "tasks_failed": 0,
        "tasks_by_type": {"code": 0, "writer": 0, "research": 0},
        "tasks_by_complexity": {"simple": 0, "complex": 0},
        "total_duration_s": 0.0,
        "average_duration_s": 0.0,
        "last_duration_s": 0.0,
        "fallback_events": 0,
        "tool_calls_total": 0,
        "tool_failures": 0,
        "service_calls": {},
        "last_model": None,
        "last_task_type": None,
        "last_complexity": None,
        "updated_at": None,
    },
}


def add_log(message: str) -> None:
    """
    Append a timestamped log entry to STATE["logs"].
    Keeps only the last 100 entries to avoid memory bloat.
    """
    STATE["logs"].append({
        "message": message,
        "timestamp": time.time()
    })

    if len(STATE["logs"]) > 100:
        STATE["logs"] = STATE["logs"][-100:]
    _persist_state()


def update_state(key: str, value: Any) -> None:
    """
    Update a specific key in the live state.
    Called by orchestrator at each step.
    """
    STATE[key] = value
    _persist_state()


def _persist_state() -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with STATE_FILE.open("w", encoding="utf-8") as f:
            json.dump(STATE, f, indent=2)
    except Exception:
        pass


def _persist_metrics() -> None:
    try:
        METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with METRICS_FILE.open("w", encoding="utf-8") as f:
            json.dump(STATE["metrics"], f, indent=2)
    except Exception:
        pass


def record_task_metrics(
    task_type: str,
    complexity: str,
    duration_seconds: float,
    success: bool,
    model: str,
    fallback_used: bool = False,
) -> None:
    metrics = STATE["metrics"]
    metrics["tasks_total"] += 1

    if success:
        metrics["tasks_completed"] += 1
    else:
        metrics["tasks_failed"] += 1

    metrics["tasks_by_type"][task_type] = metrics["tasks_by_type"].get(task_type, 0) + 1
    metrics["tasks_by_complexity"][complexity] = metrics["tasks_by_complexity"].get(complexity, 0) + 1

    metrics["total_duration_s"] += duration_seconds
    metrics["last_duration_s"] = duration_seconds
    metrics["average_duration_s"] = (
        metrics["total_duration_s"] / metrics["tasks_total"]
        if metrics["tasks_total"] > 0
        else 0.0
    )

    if fallback_used:
        metrics["fallback_events"] += 1

    metrics["last_model"] = model
    metrics["last_task_type"] = task_type
    metrics["last_complexity"] = complexity
    metrics["updated_at"] = time.time()

    _persist_metrics()
    _persist_state()


def record_tool_metrics(tool_name: str, success: bool, service: str = None) -> None:
    metrics = STATE["metrics"]
    metrics["tool_calls_total"] += 1

    if not success:
        metrics["tool_failures"] += 1

    if service:
        service_calls = metrics.setdefault("service_calls", {})
        service_calls[service] = service_calls.get(service, 0) + 1

    metrics["updated_at"] = time.time()
    _persist_metrics()
    _persist_state()


def get_state() -> Dict[str, Any]:
    """
    Return the full current state.
    HUD dashboard polls this to render live status.
    """
    try:
        if STATE_FILE.exists():
            with STATE_FILE.open("r", encoding="utf-8") as f:
                persisted = json.load(f)
                if isinstance(persisted, dict):
                    STATE.update(persisted)
    except Exception:
        pass
    return STATE


def reset_state() -> None:
    """
    Reset all fields to idle/None.
    Called in orchestrator finally block.
    """
    STATE["status"] = "idle"
    STATE["current_task"] = None
    STATE["current_agent"] = None
    STATE["current_model"] = None
    STATE["current_classification"] = None
    STATE["current_tools"] = []
    STATE["current_plan"] = None
    STATE["active_subtasks"] = []
    STATE["current_tool"] = None
    STATE["current_tool_arguments"] = None
    STATE["current_external_service"] = None
    _persist_state()
