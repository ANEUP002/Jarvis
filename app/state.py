import time
from typing import Any, Dict, List


STATE: Dict[str, Any] = {
    "status": "idle",
    "current_task": None,
    "current_agent": None,
    "current_model": None,
    "current_classification": None,   # 🔥 NEW
    "logs": []
}


def add_log(message: str) -> None:
    """
    Add a timestamped log entry.
    """
    STATE["logs"].append({
        "message": message,
        "timestamp": time.time()
    })

    # 🔥 Optional: keep logs small (last 100)
    if len(STATE["logs"]) > 100:
        STATE["logs"] = STATE["logs"][-100:]


def update_state(key: str, value: Any) -> None:
    """
    Update a specific key in the state.
    """
    STATE[key] = value


def get_state() -> Dict[str, Any]:
    """
    Return current system state.
    """
    return STATE

###What this file is doing??

# This fiel stores the live runtime of our system. Because I am building a dashboard later that will need the current task, current agenty, current model and recent logs.
