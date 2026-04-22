import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.ai/v1/chat/completions")
DEEPSEEK_RETRY_DELAY = float(os.getenv("DEEPSEEK_RETRY_DELAY", "1"))


def _normalize_model(model: str) -> str:
    if model.startswith("deepseek/"):
        return model.split("/", 1)[1]
    return model


def generate(prompt: str, model: str = "r1", system_prompt: str = None, temperature: float = 0.0, max_retries: int = 2) -> str:
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY is missing")

    model_name = _normalize_model(model)
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            print(f"[DEEPSEEK] model={model_name} | attempt={attempt+1}")
            response = requests.post(DEEPSEEK_BASE_URL, headers=headers, json=payload, timeout=30)

            if response.status_code != 200:
                raise Exception(f"DeepSeek error: {response.status_code}: {response.text}")

            data = response.json()
            output = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )

            if not output:
                raise ValueError("Empty response from DeepSeek")

            return output
        except Exception as exc:
            print(f"[DEEPSEEK ERROR] model={model_name} attempt={attempt+1} -> {exc}")
            last_error = exc
            time.sleep(DEEPSEEK_RETRY_DELAY)

    raise Exception(f"DeepSeek failed after retries: {last_error}")