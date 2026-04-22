from providers import openrouter_provider
from app.event_streaming import event_stream


def _emit(event_type: str, payload: dict, level: str = "info") -> None:
    try:
        event_stream.emit(event_type, payload, level=level)
    except Exception:
        pass


def generate(
    prompt: str,
    model: str = None,
    system_prompt: str = None,
    temperature: float = 0.0,
    max_retries: int = 2,
    return_metadata: bool = False,
) -> str | dict:
    model = model or openrouter_provider.OPENROUTER_DEFAULT_MODEL
    provider_name = "openrouter"

    _emit("llm_started", {
        "provider": provider_name,
        "model": model,
        "prompt_preview": prompt[:180] + "..." if len(prompt) > 180 else prompt,
        "temperature": temperature,
        "max_retries": max_retries,
    })

    try:
        response = openrouter_provider.generate(
            prompt,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_retries=max_retries,
            return_metadata=return_metadata,
        )
        result_model = response.get("model_used", model) if isinstance(response, dict) else model
        _emit("llm_completed", {
            "provider": provider_name,
            "requested_model": model,
            "model": result_model,
            "fallback_used": bool(response.get("fallback_used")) if isinstance(response, dict) else False,
        })
        return response
    except Exception as exc:
        _emit("llm_failed", {
            "provider": provider_name,
            "model": model,
            "error": str(exc),
        }, level="error")
        raise
