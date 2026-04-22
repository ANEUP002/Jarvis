import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY")
GOOGLE_AI_BASE_URL = os.getenv("GOOGLE_AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta2/models")
GOOGLE_AI_RETRY_DELAY = float(os.getenv("GOOGLE_AI_RETRY_DELAY", "1"))


def _normalize_model(model: str) -> str:
    if model.startswith("google/"):
        return model.split("/", 1)[1]
    return model


def generate(prompt: str, model: str = "gemini-2.5-flash", system_prompt: str = None, temperature: float = 0.0, max_retries: int = 2) -> str:
    if not GOOGLE_AI_API_KEY:
        raise ValueError("GOOGLE_AI_API_KEY is missing")

    model_name = _normalize_model(model)
    url = f"{GOOGLE_AI_BASE_URL}/{model_name}:generate?key={GOOGLE_AI_API_KEY}"
    headers = {
        "Content-Type": "application/json",
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "prompt": {"messages": messages},
        "temperature": temperature,
    }

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            print(f"[GOOGLE AI] model={model_name} | attempt={attempt+1}")
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code != 200:
                raise Exception(f"Google AI error: {response.status_code}: {response.text}")

            data = response.json()
            output = (
                data.get("candidates", [{}])[0]
                .get("content", "")
                .strip()
            )

            if not output:
                raise ValueError("Empty response from Google AI")

            return output
        except Exception as exc:
            print(f"[GOOGLE AI ERROR] model={model_name} attempt={attempt+1} -> {exc}")
            last_error = exc
            time.sleep(GOOGLE_AI_RETRY_DELAY)

    raise Exception(f"Google AI failed after retries: {last_error}")