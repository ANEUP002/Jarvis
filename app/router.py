from typing import Dict, Any

from agents.research_agent import run as research_run
from agents.code_agent import run as code_run
from agents.writer_agent import run as writer_run


AGENT_MAP = {
    "code": (code_run, "code"),
    "writer": (writer_run, "writer"),
    "research": (research_run, "research"),
}

from app.model_selector import select_model

from typing import Dict, Any

from agents.research_agent import run as research_run
from agents.code_agent import run as code_run
from agents.writer_agent import run as writer_run


AGENT_MAP = {
    "code": (code_run, "code"),
    "writer": (writer_run, "writer"),
    "research": (research_run, "research"),
}


def execute_single_task(task: Dict[str, Any]) -> Dict[str, Any]:
    task_type = task.get("task_type")
    model = task.get("model")

    print(f"[ROUTER DEBUG] task_type = {task_type} | model = {model}")

    handler, agent = AGENT_MAP.get(
        task_type,
        (research_run, "research")
    )

    result = handler(task, model=model)

    return {
        "result": result,
        "agent": agent,
        "model": model
    }

def route_task(task: Dict[str, Any]) -> Dict[str, Any]:
    return execute_single_task(task)