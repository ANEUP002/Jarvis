from app.llm_classifier import llm_classify
from app.intents import is_weather_query


THRESHOLD = 0.70


# =========================
# COMPLEXITY HEURISTIC
# =========================

# Only truly multi-agent requests are complex.
# A question — even a hard one — is still simple.
COMPLEX_SIGNALS = [
    "and then write", "and then create", "research and write",
    "build and deploy", "first research", "step by step plan",
    "multiple reports", "generate a full", "create a complete",
    "write a report and", "analyse and build",
]

# If the query starts with one of these it is almost always a single question → simple.
QUESTION_STARTERS = (
    "what", "who", "where", "when", "why", "how", "which", "is ", "are ",
    "can ", "could ", "does ", "do ", "did ", "will ", "would ", "should ",
    "tell me", "give me", "show me", "explain",
)


def _detect_complexity(text: str) -> str:
    lower = text.lower().strip()

    # Questions are almost always simple regardless of word count.
    if any(lower.startswith(s) for s in QUESTION_STARTERS):
        return "simple"

    word_count = len(lower.split())
    # Only long compound instructions qualify as complex.
    if word_count > 60:
        for signal in COMPLEX_SIGNALS:
            if signal in lower:
                return "complex"

    for signal in COMPLEX_SIGNALS:
        if signal in lower:
            return "complex"

    return "simple"


# =========================
# RULE-BASED CLASSIFIER
# =========================
def rule_based_classify(text: str) -> dict:
    lower = text.lower()
    score = {"code": 0, "writer": 0, "research": 0}

    code_keywords = [
        "fastapi", "api", "endpoint", "function", "python", "javascript",
        "typescript", "script", "debug", "code", "implement", "class",
        "algorithm", "database", "sql", "parse", "compile", "syntax",
        "error in my code", "fix this code", "write a program",
        "write a script", "build an app", "create a function",
        "refactor", "unit test", "pytest", "django", "flask", "react",
        "node", "npm", "git commit", "pull request", "dockerfile",
    ]

    writer_keywords = [
        "email", "essay", "blog", "article", "story", "write", "draft",
        "letter", "summarize", "report", "cover letter", "resume",
        "compose", "paragraph", "poem", "speech", "press release",
        "announcement", "caption", "bio", "biography", "proposal",
        "proofread", "edit my", "rewrite this",
    ]

    research_keywords = [
        # Questions
        "explain", "why", "how does", "what is", "what are", "what's",
        "who is", "who are", "who was", "where is", "when did", "when was",
        "which is", "difference between", "compare", "overview", "describe",
        "tell me", "give me", "show me", "define", "meaning of",
        # Knowledge & facts
        "history of", "how many", "how much", "population", "founded",
        "invented", "created", "discovered", "capital of",
        "fact", "true or false", "is it true",
        # Advice / opinion
        "should i", "best way", "recommend", "advice", "pros and cons",
        "benefits of", "risks of", "help me understand",
        "what do you think", "your opinion",
        # Current events / news
        "news", "happening", "going on", "latest", "recent", "update",
        "world", "situation", "crisis", "event", "today",
        "current", "right now", "this week", "this year",
        # Market / career / general
        "market", "salary", "job", "career", "industry", "trend",
        "price of", "cost of", "worth", "value",
        # Science / tech knowledge (not coding)
        "artificial intelligence", "machine learning", "how ai",
        "quantum", "climate", "space", "health", "medical",
    ]

    for word in code_keywords:
        if word in lower:
            score["code"] += 1

    for word in writer_keywords:
        if word in lower:
            score["writer"] += 1

    for word in research_keywords:
        if word in lower:
            score["research"] += 1

    total = sum(score.values())

    if total == 0:
        return {
            "type": "unknown",
            "confidence": 0.0,
            "complexity": _detect_complexity(text),
            "source": "rule",
        }

    max_type = max(score, key=score.get)
    max_score = score[max_type]
    confidence = max_score / total

    return {
        "type": max_type,
        "confidence": confidence,
        "complexity": _detect_complexity(text),
        "source": "rule",
    }


# =========================
# MAIN CLASSIFIER
# =========================
def classify(input_text: str) -> dict:
    text = input_text.lower()

    if is_weather_query(text):
        result = {
            "type": "research",
            "confidence": 1.0,
            "complexity": "simple",
            "source": "rule_weather_fast_path",
        }
        print(f"[CLASSIFIER RULE] {result}")
        return result

    rule_result = rule_based_classify(text)
    print(f"[CLASSIFIER RULE] {rule_result}")

    # CASE 1: Unknown → must use LLM
    if rule_result["type"] == "unknown":
        llm_result = llm_classify(input_text)
        print(f"[CLASSIFIER LLM] {llm_result}")
        # Never let LLM escalate a one-sentence question to complex
        if _detect_complexity(input_text) == "simple":
            llm_result["complexity"] = "simple"
        return llm_result

    # CASE 2: High confidence → trust rule
    if rule_result["confidence"] >= THRESHOLD:
        return rule_result

    # CASE 3: Low confidence → use LLM, but cap complexity
    llm_result = llm_classify(input_text)
    print(f"[CLASSIFIER LLM] {llm_result}")

    if _detect_complexity(input_text) == "simple":
        llm_result["complexity"] = "simple"

    if llm_result["confidence"] > rule_result["confidence"]:
        return llm_result

    if llm_result.get("complexity") == "complex" and _detect_complexity(input_text) == "complex":
        rule_result["complexity"] = "complex"

    return rule_result
