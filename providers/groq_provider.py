import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.ai/v1/chat/completions")
GROQ_RETRY_DELAY = float(os.getenv("GROQ_RETRY_DELAY", "1"))


def _normalize_model(model: str) -> str:
    if model.startswith("groq/"):
        return model.split("/", 1)[1]
    return model


def generate(prompt: str, model: str = "llama-3", system_prompt: str = None, temperature: float = 0.0, max_retries: int = 2) -> str:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is missing")

    model_name = _normalize_model(model)
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt} if system_prompt else {},
            {"role": "user", "content": prompt},
        ] if system_prompt else [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            print(f"[GROQ] model={model_name} | attempt={attempt+1}")
            response = requests.post(GROQ_BASE_URL, headers=headers, json=payload, timeout=30)

            if response.status_code != 200:
                raise Exception(f"GROQ error: {response.status_code}: {response.text}")

            data = response.json()
            output = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )

            if not output:
                raise ValueError("Empty response from GROQ")

            return output
        except Exception as exc:
            print(f"[GROQ ERROR] model={model_name} attempt={attempt+1} -> {exc}")
            last_error = exc
            time.sleep(GROQ_RETRY_DELAY)

    raise Exception(f"GROQ failed after retries: {last_error}")