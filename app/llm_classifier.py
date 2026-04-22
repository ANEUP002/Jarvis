import json
import re
from providers.llm_provider import generate
from app.model_selector import DEFAULT_MODEL


VALID_TYPES = {"code", "writer", "research"}

CLASSIFICATION_PROMPT = """You are a strict task classifier for a voice AI assistant.

Classify the user's request into exactly one type and one complexity.

TYPE rules:
- "research"  → any question, fact lookup, news, explanation, advice, current events, general knowledge, definitions, comparisons, recommendations, career/market questions. When in doubt, use research.
- "writer"    → explicitly asked to write/draft/compose something: email, essay, blog post, cover letter, poem, report, announcement.
- "code"      → explicitly asked to write, debug, fix, or explain programming code or a script.

COMPLEXITY rules:
- "simple"    → ANY single question or single task, no matter how hard the topic. One agent can answer it.
- "complex"   → ONLY when the request explicitly needs multiple DIFFERENT agent types working together (e.g. "research X AND write a blog post AND generate code for it"). Requires the word "and" connecting fundamentally different output types.

Examples:
- "what's happening in the world today" → research, simple
- "who is Elon Musk" → research, simple
- "market for new graduates" → research, simple
- "latest news on AI" → research, simple
- "write an email to my boss" → writer, simple
- "fix this Python bug" → code, simple
- "research quantum computing and write a blog post about it" → research, complex
- "build a REST API with tests and documentation" → code, complex

Return ONLY valid JSON in this exact format, nothing else:
{"type": "research", "confidence": 0.95, "complexity": "simple"}

Task: {input}
"""


def clean_response(text: str) -> str:
    text = text.strip()
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return ""


def llm_classify(input_text: str) -> dict:
    prompt = CLASSIFICATION_PROMPT.replace("{input}", input_text)

    response = ""
    try:
        response = generate(prompt, model=DEFAULT_MODEL)
        cleaned = clean_response(response)
        parsed = json.loads(cleaned)

        task_type = parsed.get("type", "").lower()
        confidence = float(parsed.get("confidence", 0.0))
        complexity = parsed.get("complexity", "simple").lower()

        if task_type not in VALID_TYPES:
            task_type = "research"

        if complexity not in {"simple", "complex"}:
            complexity = "simple"

        return {
            "type": task_type,
            "confidence": confidence,
            "complexity": complexity,
            "source": "llm",
        }

    except Exception as e:
        print(f"[LLM CLASSIFIER ERROR] {e}")
        print(f"[RAW RESPONSE] {response}")

    return {
        "type": "research",
        "confidence": 0.5,
        "complexity": "simple",
        "source": "llm_fallback",
    }
