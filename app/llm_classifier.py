import json
import re
from providers.ollama_provider import generate


VALID_TYPES = {"code", "writer", "research"}

CLASSIFICATION_PROMPT = """
You are a strict classification engine.

Your job is ONLY to classify the task.

DO NOT generate code.
DO NOT explain anything.

Return ONLY valid JSON in this exact format:
{"type": "code", "confidence": 0.9}

Allowed values for type:
- code
- writer
- research

Task:
{input}
"""


import re

def clean_response(text: str) -> str:
    text = text.strip()

    # Remove markdown code blocks completely
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    # Extract JSON only
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        return match.group(0)

    return ""


def llm_classify(input_text: str) -> dict:
    prompt = CLASSIFICATION_PROMPT + f"\nTask: {input_text}"

    try:
        response = generate(prompt)

        cleaned = clean_response(response)

        parsed = json.loads(cleaned)

        task_type = parsed.get("type", "").lower()
        confidence = float(parsed.get("confidence", 0.0))

        if task_type in VALID_TYPES:
            return {
                "type": task_type,
                "confidence": confidence,
                "source": "llm"
            }

    except Exception as e:
        print(f"[LLM CLASSIFIER ERROR] {e}")
        print(f"[RAW RESPONSE] {response}")

    # 🔥 Safe fallback
    return {
        "type": "research",
        "confidence": 0.3,
        "source": "llm_fallback"
    }