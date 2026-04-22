import json
import re
from typing import Any, Dict, List

from providers.minimax_provider import MiniMaxProvider 
from agents.note_workflows import load_memory_bundle
from app.intents import is_weather_query

# =========================
# STRICT PROMPT
# =========================
CHIEF_PROMPT = """
You are a STRICT JSON planner.

CRITICAL RULES:
- Output ONLY valid JSON
- NO explanation
- NO markdown
- NO code blocks
- NO comments
- JSON must be syntactically correct

TASK TYPES:
code, writer, research

INSTRUCTIONS:
- Decide if the task is simple or multi-step
- If simple → return simple format
- If complex → break into meaningful subtasks

SUBTASK RULES:
- Each subtask must be specific
- Each subtask must be executable independently
- Avoid vague instructions like "research the topic"
- Include enough detail for execution

FORMAT:

Simple:
{"mode": "simple", "task_type": "writer"}

Multi:
{
  "mode": "multi",
  "subtasks": [
    {"id": 1, "task_type": "research", "input": "Detailed research task"},
    {"id": 2, "task_type": "writer", "input": "Write based on research"}
  ]
}

Task:
__TASK__
"""

VALID_TYPES = {"code", "writer", "research"}

minimax = MiniMaxProvider()


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="ignore").decode())
# =========================
# JSON EXTRACTION
# =========================
def _extract_json(text: str) -> str:
    text = text.strip()

    # Strip <think>...</think> reasoning blocks (MiniMax / DeepSeek-style models)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"```json", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)
    text = text.strip()

    # Find the LAST complete JSON object (the model's actual answer, not its examples)
    last_end = text.rfind("}")
    if last_end == -1:
        return ""
    # Walk backwards from last } to find matching {
    depth = 0
    for i in range(last_end, -1, -1):
        if text[i] == "}":
            depth += 1
        elif text[i] == "{":
            depth -= 1
            if depth == 0:
                return text[i:last_end + 1]
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
    if is_weather_query(task_input):
        return {
            "mode": "simple",
            "task_type": "research",
        }
    # ✅ FIX: NO .format() → use replace
    # Use raw input for second brain search (strip any conversation history prefix)
    search_input = task_input.split("[CURRENT REQUEST]")[-1].strip() if "[CURRENT REQUEST]" in task_input else task_input
    note_context, _notes_result = load_memory_bundle({"input": search_input}, agent_name="research", limit=2)
    enriched_task = task_input
    if note_context:
        enriched_task = f"{task_input}\n\nPlanner context:\n{note_context}"
    prompt = CHIEF_PROMPT.replace("__TASK__", enriched_task)

    try:
        # 🔥 FORCE STRONG MODEL FOR PLANNING
        response = minimax.chat(
            system_prompt="You are a STRICT JSON planner.",
            user_prompt=prompt
        )
        _safe_print("\n========== CHIEF DEBUG ==========")
        _safe_print(response)
        _safe_print("================================\n")

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

def _clean_final_response(text: str) -> str:
    if not text:
        return ""

    clean_text = text.strip()
    clean_text = re.sub(r"<think>.*?</think>\s*", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r"\[think\].*?\[/think\]\s*", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r"^\s*(Let me .*?\n\n)", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r"^(Final response:|Answer:)\s*", "", clean_text, flags=re.IGNORECASE)
    return clean_text.strip()


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
You are a response synthesizer.

Do not include analysis, reasoning, or internal thoughts.
Write one final clean response for the user based on the original task and agent outputs.
Return plain text only, with no extra commentary.

Original task:
{original_task}

Agent outputs:
{combined_text}
"""

    try:
        # Use strong model for final merge
        final_response = minimax.chat(
            system_prompt="""
You are a high-quality response synthesizer.

Your job:
- Combine multiple agent outputs into ONE clean final answer
- Remove redundancy
- Improve clarity and flow
- Keep it concise but complete
- Maintain a professional tone

Return ONLY the final answer.
""",
            user_prompt=merge_prompt,
        ).strip()
        final_response = _clean_final_response(final_response)
        if not final_response:
            raise ValueError("Empty final response from combiner")
    except Exception:
        final_response = _clean_final_response(combined_text)

    return {
        "response": final_response,
        "subtask_results": subtask_results
    }
