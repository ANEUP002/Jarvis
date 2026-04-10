import json
import re
from typing import Any, Dict, List

from providers.ollama_provider import generate


# =========================
# STRICT PROMPT
# =========================
CHIEF_PROMPT = """
You are a STRICT JSON planner.

Rules:
- Return ONLY valid JSON
- NO explanation
- NO markdown
- NO extra text
- JSON must be syntactically correct

Allowed task_type:
code, writer, research

FORMAT:

Simple:
{"mode": "simple", "task_type": "writer"}

Multi:
{
  "mode": "multi",
  "subtasks": [
    {"id": 1, "task_type": "research", "input": "Research the topic"},
    {"id": 2, "task_type": "writer", "input": "Write a summary"}
  ]
}

Task:
__TASK__
"""

VALID_TYPES = {"code", "writer", "research"}


# =========================
# JSON EXTRACTION
# =========================
def _extract_json(text: str) -> str:
    text = text.strip()

    text = re.sub(r"```json", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]

    return ""


# =========================
# SAFE JSON LOAD
# =========================
def _safe_json_loads(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[CHIEF JSON ERROR] {e}")
        print(f"[CHIEF CLEANED JSON] {text}")
        raise


# =========================
# PLAN TASK
# =========================
def plan_task(task_input: str) -> Dict[str, Any]:
    # ✅ FIX: NO .format() → use replace
    prompt = CHIEF_PROMPT.replace("__TASK__", task_input)

    try:
        # 🔥 FORCE STRONG MODEL FOR PLANNING
        response = generate(prompt, model="gemma:2b")

        print("\n========== CHIEF DEBUG ==========")
        print(response)
        print("================================\n")

        cleaned = _extract_json(response)

        if not cleaned:
            raise ValueError("No JSON found in response")

        parsed = _safe_json_loads(cleaned)

        mode = parsed.get("mode")

        # =========================
        # SIMPLE MODE
        # =========================
        if mode == "simple":
            task_type = parsed.get("task_type", "research")

            if task_type not in VALID_TYPES:
                task_type = "research"

            return {
                "mode": "simple",
                "task_type": task_type
            }

        # =========================
        # MULTI MODE
        # =========================
        if mode == "multi":
            subtasks = parsed.get("subtasks", [])

            cleaned_subtasks = []

            for i, subtask in enumerate(subtasks, start=1):
                task_type = subtask.get("task_type", "research")

                if task_type not in VALID_TYPES:
                    task_type = "research"

                cleaned_subtasks.append({
                    "id": subtask.get("id", i),
                    "task_type": task_type,
                    "input": subtask.get("input", "").strip()
                })

            if cleaned_subtasks:
                return {
                    "mode": "multi",
                    "subtasks": cleaned_subtasks
                }

        raise ValueError("Invalid structure from chief agent")

    except Exception as e:
        print(f"[CHIEF AGENT ERROR] {e}")

    # =========================
    # SAFE FALLBACK
    # =========================
    return {
        "mode": "simple",
        "task_type": "research"
    }


# =========================
# RESULT COMBINER
# =========================
def combine_results(original_task: str, subtask_results: List[Dict[str, Any]]) -> Dict[str, Any]:

    if len(subtask_results) == 1:
        return {
            "response": subtask_results[0]["result"].get("response", ""),
            "subtask_results": subtask_results
        }

    combined_text = f"Original task: {original_task}\n\n"

    for item in subtask_results:
        combined_text += (
            f"Subtask {item['id']} ({item['task_type']}):\n"
            f"{item['result'].get('response', '')}\n\n"
        )

    merge_prompt = f"""
You are combining outputs from multiple AI agents into one final response.

Original task:
{original_task}

Agent outputs:
{combined_text}

Write one final clean response for the user.
Return plain text only.
"""

    try:
        # 🔥 Use strong model for final merge
        final_response = generate(merge_prompt, model="gemma:2b").strip()
    except Exception:
        final_response = combined_text

    return {
        "response": final_response,
        "subtask_results": subtask_results
    }