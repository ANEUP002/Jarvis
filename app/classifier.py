from app.llm_classifier import llm_classify


THRESHOLD = 0.75  # when to trust rule vs LLM


def rule_based_classify(text: str) -> dict:
    score = {
        "code": 0,
        "writer": 0,
        "research": 0
    }

    code_keywords = [
        "fastapi", "api", "endpoint", "function",
        "python", "script", "debug", "code", "implement"
    ]

    writer_keywords = [
        "email", "essay", "blog", "article", "story", "write"
    ]

    research_keywords = [
        "explain", "why", "how", "analysis", "concept", "compare"
    ]

    for word in code_keywords:
        if word in text:
            score["code"] += 1

    for word in writer_keywords:
        if word in text:
            score["writer"] += 1

    for word in research_keywords:
        if word in text:
            score["research"] += 1

    total = sum(score.values())

    # CRITICAL FIX
    if total == 0:
        return {
            "type": "unknown",
            "confidence": 0.0,
            "source": "rule"
        }

    max_type = max(score, key=score.get)
    max_score = score[max_type]

    confidence = max_score / total

    return {
        "type": max_type,
        "confidence": confidence,
        "source": "rule"
    }

def classify(input_text: str) -> dict:
    text = input_text.lower()

    rule_result = rule_based_classify(text)

    print(f"[CLASSIFIER RULE] {rule_result}")

    # ✅ CASE 1: Unknown → MUST use LLM
    if rule_result["type"] == "unknown":
        llm_result = llm_classify(input_text)
        print(f"[CLASSIFIER LLM] {llm_result}")
        return llm_result

    # ✅ CASE 2: High confidence → trust rule
    if rule_result["confidence"] >= 0.7:
        return rule_result

    # ✅ CASE 3: Medium confidence → compare with LLM
    llm_result = llm_classify(input_text)
    print(f"[CLASSIFIER LLM] {llm_result}")

    # 🔥 SMART DECISION
    if llm_result["confidence"] > rule_result["confidence"]:
        return llm_result

    return rule_result