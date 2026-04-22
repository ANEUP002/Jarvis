# =========================
# MODEL SELECTOR
# =========================
# Picks task-aware OpenRouter models and fallbacks.
# Simple tasks stay on smaller/faster models.
# Complex tasks use stronger models based on task type.
# =========================

DEFAULT_MODEL = "openrouter/gpt-4o-mini"
FINAL_FALLBACK_MODEL = "openrouter/gpt-4o-mini"

RESEARCH_COMPLEX_MODEL = "openrouter/google/gemma-4-31b-it:free"
RESEARCH_REASONING_FALLBACK = "openrouter/nvidia/nemotron-3-super-120b-a12b:free"
WRITER_COMPLEX_MODEL = "openrouter/minimax/minimax-m2.5:free"
WRITER_CREATIVE_MODEL = "openrouter/arcee-ai/trinity-large-preview:free"
CODE_SIMPLE_MODEL = "openrouter/gpt-4o-mini"
CODE_COMPLEX_MODEL = "openrouter/google/gemma-4-31b-it:free"

CREATIVE_SIGNALS = (
    "creative",
    "story",
    "fiction",
    "poem",
    "poetry",
    "novel",
    "screenplay",
    "dialogue",
    "lyrics",
    "worldbuilding",
    "character arc",
)


def _is_creative_writing(task_input: str) -> bool:
    text = (task_input or "").lower()
    return any(signal in text for signal in CREATIVE_SIGNALS)


def _dedupe(models: list[str]) -> list[str]:
    ordered = []
    for model in models:
        if model and model not in ordered:
            ordered.append(model)
    return ordered


def select_model(task_type: str, complexity: str = "simple", task_input: str = "") -> str:
    if complexity not in {"simple", "complex"}:
        complexity = "simple"

    if task_type == "code":
        return CODE_COMPLEX_MODEL if complexity == "complex" else CODE_SIMPLE_MODEL

    if task_type == "writer":
        if complexity == "simple":
            return DEFAULT_MODEL
        if _is_creative_writing(task_input):
            return WRITER_CREATIVE_MODEL
        return WRITER_COMPLEX_MODEL

    if task_type == "research":
        return RESEARCH_COMPLEX_MODEL if complexity == "complex" else DEFAULT_MODEL

    return DEFAULT_MODEL


def get_model_fallbacks(task_type: str, complexity: str = "simple", task_input: str = "") -> list[str]:
    primary = select_model(task_type, complexity, task_input=task_input)

    if task_type == "code":
        fallback = [
            RESEARCH_REASONING_FALLBACK,
            RESEARCH_COMPLEX_MODEL,
            FINAL_FALLBACK_MODEL,
        ]
    elif task_type == "writer":
        if complexity == "complex" and _is_creative_writing(task_input):
            fallback = [
                WRITER_COMPLEX_MODEL,
                RESEARCH_COMPLEX_MODEL,
                RESEARCH_REASONING_FALLBACK,
                FINAL_FALLBACK_MODEL,
            ]
        elif complexity == "complex":
            fallback = [
                RESEARCH_COMPLEX_MODEL,
                RESEARCH_REASONING_FALLBACK,
                FINAL_FALLBACK_MODEL,
            ]
        else:
            fallback = [FINAL_FALLBACK_MODEL]
    elif task_type == "research":
        fallback = [
            RESEARCH_REASONING_FALLBACK,
            WRITER_COMPLEX_MODEL,
            FINAL_FALLBACK_MODEL,
        ]
    else:
        fallback = [FINAL_FALLBACK_MODEL]

    return _dedupe([primary] + fallback)
