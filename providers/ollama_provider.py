import requests
import time


OLLAMA_URL = "http://localhost:11434/api/generate"


import requests
import time


OLLAMA_URL = "http://localhost:11434/api/generate"


def generate(prompt: str, model: str = "gemma:2b", max_retries: int = 2):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    last_error = None

    for attempt in range(max_retries + 1):
        try:
            print(f"[LLM CALL] model={model} | attempt={attempt+1}")

            response = requests.post(OLLAMA_URL, json=payload, timeout=30)

            if response.status_code != 200:
                raise Exception(f"Ollama error: {response.text}")

            data = response.json()
            output = data.get("response", "").strip()

            if not output:
                raise ValueError("Empty response")

            return output

        except Exception as e:
            print(f"[LLM ERROR] {e}")
            last_error = e
            time.sleep(1)

    # FINAL FAIL SAFE
    raise Exception(f"LLM failed after retries: {last_error}")
'''import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
MINIMAX_URL = "https://api.minimax.io/v1/chat/completions"


def generate(prompt: str, model: str = "MiniMax-M2.7", system_prompt: str = None, max_retries: int = 2):
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful AI assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    last_error = None

    for attempt in range(max_retries + 1):
        try:
            print(f"[LLM CALL] model={model} | attempt={attempt+1}")

            response = requests.post(
                MINIMAX_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code != 200:
                raise Exception(f"MiniMax error: {response.text}")

            data = response.json()

            output = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )

            if not output:
                raise ValueError("Empty response")

            return output

        except Exception as e:
            print(f"[LLM ERROR] {e}")
            last_error = e
            time.sleep(1)

    #   FINAL FAIL SAFE
    raise Exception(f"LLM failed after retries: {last_error}")'''