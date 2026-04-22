import os
import time

import requests
from dotenv import load_dotenv
from app.event_streaming import event_stream

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL",
    "https://openrouter.ai/api/v1/chat/completions"
)
OPENROUTER_DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL_DEFAULT", "gpt-4o-mini")
OPENROUTER_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv("OPENROUTER_FALLBACK_MODELS", "").split(",")
    if model.strip()
]
OPENROUTER_NVIDIA_FALLBACK = os.getenv(
    "OPENROUTER_NVIDIA_FALLBACK",
    "nvidia/nemotron-3-super-120b-a12b:free"
)
OPENROUTER_RETRY_DELAY = float(os.getenv("OPENROUTER_RETRY_DELAY", "1"))
OPENROUTER_DISABLE_ENV_PROXIES = os.getenv("OPENROUTER_DISABLE_ENV_PROXIES", "true").lower() in ("1", "true", "yes")

OPENROUTER_MODEL_ALIASES = {
    "openrouter/deepseek-r1": "DeepSeek R1",
    "openrouter/llama-3": "llama-3",
    "openrouter/mistral": "mistral",
    "openrouter/google-gemini-2.5-flash": "google/gemini-2.5-flash",
    "openrouter/gpt-4o-mini": "gpt-4o-mini",
    "openrouter/gpt-4o": "gpt-4o",
    "openrouter/google/gemma-4-31b-it:free": "google/gemma-4-31b-it:free",
    "openrouter/nvidia/nemotron-3-super-120b-a12b:free": "nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/minimax/minimax-m2.5:free": "minimax/minimax-m2.5:free",
    "openrouter/arcee-ai/trinity-large-preview:free": "arcee-ai/trinity-large-preview:free",
    "openrouter/qwen/qwen-2.5-coder-32b-instruct:free": "qwen/qwen-2.5-coder-32b-instruct:free",
}

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY is missing")


def _normalize_model_list(models):
    normalized = []
    for model in models:
        if model:
            normalized.append(_normalize_model(model))
    return list(dict.fromkeys(normalized))


def _normalize_model(model: str) -> str:
    if not model:
        return model
    if model in OPENROUTER_MODEL_ALIASES:
        return OPENROUTER_MODEL_ALIASES[model]
    if model.startswith("openrouter/"):
        return model.split("/", 1)[1]
    return model


def _build_session() -> requests.Session:
    session = requests.Session()
    if OPENROUTER_DISABLE_ENV_PROXIES:
        session.trust_env = False
    return session


def generate(
    prompt: str,
    model: str = None,
    system_prompt: str = None,
    temperature: float = 0.0,
    max_retries: int = 2,
    return_metadata: bool = False,
) -> str | dict:
    primary_model = _normalize_model(model or OPENROUTER_DEFAULT_MODEL)
    candidate_models = _normalize_model_list([
        primary_model,
        *OPENROUTER_FALLBACK_MODELS,
        OPENROUTER_NVIDIA_FALLBACK,
        OPENROUTER_DEFAULT_MODEL,
    ])

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    last_error = None
    session = _build_session()
    attempt_log = []

    for current_model in candidate_models:
        for attempt in range(max_retries + 1):
            try:
                print(f"[OpenRouter] model={current_model} | attempt={attempt + 1}")
                try:
                    event_stream.emit(
                        "external_service_accessed",
                        {
                            "service": "openrouter",
                            "model": current_model,
                            "attempt": attempt + 1,
                        },
                    )
                    event_stream.emit(
                        "tool_progress",
                        {
                            "tool_name": "llm_generate",
                            "service": "openrouter",
                            "stage": "request_started",
                            "model": current_model,
                            "attempt": attempt + 1,
                        },
                    )
                except Exception:
                    pass

                payload = {
                    "model": current_model,
                    "messages": messages,
                    "temperature": temperature,
                    "top_p": 1.0,
                    "stream": False,
                }

                response = session.post(
                    OPENROUTER_BASE_URL,
                    headers=headers,
                    json=payload,
                    timeout=30,
                )

                if response.status_code != 200:
                    response_text = response.text
                    status_code = response.status_code

                    if status_code == 400 and "invalid model id" in response_text.lower():
                        print(f"[OpenRouter INVALID MODEL] {current_model} is invalid, skipping to fallback")
                        last_error = Exception(f"Invalid model: {current_model}")
                        break

                    if status_code in {404, 429, 502, 503, 504}:
                        print(f"[OpenRouter RATE LIMIT/BUSY] {current_model} returned {status_code}, skipping to fallback")
                        last_error = Exception(f"Service busy/rate limited: {current_model}")
                        break

                    raise Exception(f"OpenRouter error: {status_code}: {response_text}")

                data = response.json()
                output = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )

                if not output:
                    raise ValueError("Empty response from OpenRouter")

                fallback_used = current_model != primary_model
                attempt_log.append({
                    "model": current_model,
                    "attempt": attempt + 1,
                    "success": True,
                    "error": None,
                })

                if current_model != primary_model:
                    print(f"[OpenRouter FALLBACK] used {current_model} after failure of {primary_model}")

                try:
                    event_stream.emit(
                        "tool_progress",
                        {
                            "tool_name": "llm_generate",
                            "service": "openrouter",
                            "stage": "request_completed",
                            "model": current_model,
                            "attempt": attempt + 1,
                            "fallback_used": fallback_used,
                        },
                    )
                except Exception:
                    pass

                if return_metadata:
                    return {
                        "content": output,
                        "provider": "openrouter",
                        "requested_model": primary_model,
                        "model_used": current_model,
                        "fallback_used": fallback_used,
                        "attempts": attempt_log,
                    }

                return output

            except Exception as exc:
                print(f"[OpenRouter ERROR] model={current_model} attempt={attempt + 1} -> {exc}")
                last_error = exc
                try:
                    event_stream.emit(
                        "tool_progress",
                        {
                            "tool_name": "llm_generate",
                            "service": "openrouter",
                            "stage": "request_failed",
                            "model": current_model,
                            "attempt": attempt + 1,
                            "error": str(exc),
                        },
                        level="warning",
                    )
                except Exception:
                    pass
                attempt_log.append({
                    "model": current_model,
                    "attempt": attempt + 1,
                    "success": False,
                    "error": str(exc),
                })
                if "invalid model" in str(exc).lower() or "rate limited" in str(exc).lower():
                    break
                time.sleep(OPENROUTER_RETRY_DELAY)

    raise Exception(f"OpenRouter failed after retries and fallback models: {last_error}")
