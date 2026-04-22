from typing import Dict, Any

from agents.research_agent import run as research_run
from agents.code_agent import run as code_run
from agents.writer_agent import run as writer_run
from app.model_selector import get_model_fallbacks


AGENT_MAP = {
    "code": (code_run, "code"),
    "writer": (writer_run, "writer"),
    "research": (research_run, "research"),
}

LEGACY_MODEL_MAP = {
    "google-gemma-4-26b-a4b": "google/gemma-4-26b-a4b-it:free",
    "google-gemma-4-31b": "google/gemma-4-31b-it:free",
    "google-gemma-4-26b-a4b-it": "google/gemma-4-26b-a4b-it:free",
    "google-gemma-4-31b-it": "google/gemma-4-31b-it:free",
}


def normalize_model_id(model_id: str) -> str:
    return LEGACY_MODEL_MAP.get(model_id, model_id)


def canonical_model_id(model_id: str) -> str:
    normalized = normalize_model_id(model_id)
    if isinstance(normalized, str) and normalized.startswith("openrouter/"):
        return normalized.split("/", 1)[1]
    return normalized


def execute_single_task(task: Dict[str, Any]) -> Dict[str, Any]:
    task_type = task.get("task_type", "research")
    requested_model = normalize_model_id(task.get("model"))
    complexity = task.get("complexity", "simple")
    task_input = task.get("input", "")

    print(f"[ROUTER DEBUG] task_type={task_type} | requested_model={requested_model} | complexity={complexity}")

    handler, agent = AGENT_MAP.get(
        task_type,
        (research_run, "research")
    )

    models_to_try = get_model_fallbacks(task_type, complexity, task_input=task_input)
    if requested_model and requested_model not in models_to_try:
        models_to_try.insert(0, requested_model)

    last_error = None
    for model in models_to_try:
        try:
            print(f"[ROUTER] trying model={model}")
            result = handler(task, model=model)
            llm_info = result.get("llm", {}) if isinstance(result, dict) else {}
            model_used = llm_info.get("model_used", model)
            fallback_used = bool(llm_info.get("fallback_used")) or bool(
                requested_model and canonical_model_id(model_used) != canonical_model_id(requested_model)
            )
            return {
                "result": result,
                "agent": agent,
                "model": model_used,
                "requested_execution_model": model,
                "fallback_used": fallback_used,
                "requested_model": requested_model,
                "models_tried": models_to_try,
                "llm": llm_info,
            }
        except Exception as exc:
            print(f"[ROUTER FALLBACK] model={model} failed: {exc}")
            last_error = exc

    raise last_error or Exception("No model succeeded during task execution")


