from __future__ import annotations

from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict

from app.dashboard import get_dashboard_snapshot, get_task_record
from app.intents import extract_weather_location, is_weather_query
from tools import ToolsManager


GREETING_PATTERNS = (
    "hello",
    "hi",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
)

HOW_ARE_YOU_PATTERNS = (
    "how are you",
    "how are you today",
    "how you doing",
    "how's it going",
    "hows it going",
)

TIME_PATTERNS = (
    "what time is it",
    "tell me the time",
    "current time",
    "time now",
)

DATE_PATTERNS = (
    "what day is it",
    "what's the date",
    "whats the date",
    "today's date",
    "todays date",
)

PROGRESS_PATTERNS = (
    "what are you doing",
    "what is the progress",
    "what's the progress",
    "progress of",
    "status of",
    "are you still working",
    "what are you working on",
    "current task",
)


VOICE_NORMALIZATIONS = {
    "yp": "you",
    "ya": "you",
    "u": "you",
    "ur": "your",
    "taday": "today",
    "todai": "today",
    "todsy": "today",
    "wether": "weather",
    "waether": "weather",
    "progess": "progress",
    "statys": "status",
}


def _normalize_voice_text(text: str) -> str:
    lowered = " ".join((text or "").strip().lower().split())
    if not lowered:
        return ""
    words = [VOICE_NORMALIZATIONS.get(word, word) for word in lowered.split()]
    cleaned = " ".join(words)
    return "".join(char if char.isalnum() or char.isspace() else " " for char in cleaned).strip()


def _fuzzy_match(text: str, pattern: str, threshold: float = 0.82) -> bool:
    normalized_text = _normalize_voice_text(text)
    normalized_pattern = _normalize_voice_text(pattern)
    if not normalized_text or not normalized_pattern:
        return False
    if normalized_pattern in normalized_text:
        return True
    ratio = SequenceMatcher(None, normalized_text, normalized_pattern).ratio()
    if ratio >= threshold:
        return True
    text_words = normalized_text.split()
    pattern_words = normalized_pattern.split()
    if len(text_words) < len(pattern_words):
        return False
    window = len(pattern_words)
    for index in range(0, len(text_words) - window + 1):
        candidate = " ".join(text_words[index:index + window])
        if SequenceMatcher(None, candidate, normalized_pattern).ratio() >= threshold:
            return True
    return False


def _contains_any(text: str, patterns: tuple[str, ...], threshold: float = 0.82) -> bool:
    return any(_fuzzy_match(text, pattern, threshold=threshold) for pattern in patterns)


def _build_result(kind: str, response: str, **extra: Any) -> Dict[str, Any]:
    result = {
        "handled": True,
        "response": response,
        "kind": kind,
        "task_type": "research",
        "agent": "assistant_fastlane",
        "model_used": "local:assistant_fastlane",
    }
    result.update(extra)
    return result


def _friendly_progress(snapshot: Dict[str, Any]) -> str:
    state = snapshot.get("state", {})
    queue = snapshot.get("queue", {})
    current_task = state.get("current_task")
    current_agent = state.get("current_agent")
    current_tool = state.get("current_tool")

    if current_task:
        parts = ["I've started that request."]
        try:
            record = get_task_record(current_task)
            task_input = ((record or {}).get("task") or {}).get("input", "")
        except Exception:
            task_input = ""
        if task_input:
            clean_input = " ".join(str(task_input).split())
            if len(clean_input) > 88:
                clean_input = clean_input[:85].rstrip() + "..."
            parts.append(f"I'm working on {clean_input}.")
        if current_agent:
            parts.append(f"I'm handling it through the {current_agent.replace('_', ' ')} workflow.")
        if current_tool:
            parts.append(f"Right now I'm checking {current_tool.replace('_', ' ')}.")
        return " ".join(parts)

    in_progress = queue.get("in_progress", 0)
    pending = queue.get("pending", 0)
    if in_progress:
        return f"I have {in_progress} request{'s' if in_progress != 1 else ''} in progress right now."
    if pending:
        return f"I have {pending} request{'s' if pending != 1 else ''} waiting in the queue, but nothing active this second."
    return "Nothing heavy is running right now. I'm ready when you are."


def handle_fastlane(query: str) -> Dict[str, Any] | None:
    lowered = (query or "").strip().lower()
    normalized = _normalize_voice_text(lowered)
    if not lowered:
        return None

    if _contains_any(normalized, HOW_ARE_YOU_PATTERNS):
        return _build_result(
            "small_talk",
            "I'm doing well, sir. Systems are steady and I'm ready to help.",
        )

    if _contains_any(normalized, GREETING_PATTERNS, threshold=0.8) and len(normalized.split()) <= 5:
        return _build_result("greeting", "Hello, sir. I'm here and ready.")

    if any(p in normalized for p in TIME_PATTERNS):
        now = datetime.now()
        return _build_result("time", f"It's {now.strftime('%I:%M %p').lstrip('0')}.")

    # Weather checked BEFORE date so "what is the weather today" never fuzzy-matches
    # "what day is it" and returns a date instead of actual weather.
    _WEATHER_WORDS = {"weather", "forecast", "temperature", "rain", "snow",
                      "humid", "wind", "storm", "sunny", "cloudy"}
    if _WEATHER_WORDS & set(lowered.split()):
        manager = ToolsManager()
        location = extract_weather_location(query)
        result = manager.execute(
            "get_weather",
            query=query,
            location=location,
            task_type="research",
            agent_name="jarvis_fastlane",
        )
        if result.get("success"):
            return _build_result(
                "weather",
                result.get("result", {}).get("summary", "I have the weather ready."),
                payload=result.get("result"),
                model_used="tool:get_weather",
            )
        return _build_result(
            "weather_error",
            f"I couldn't get the weather right now: {result.get('error', 'unknown error')}.",
            model_used="tool:get_weather",
        )

    if any(p in normalized for p in DATE_PATTERNS):
        now = datetime.now()
        return _build_result("date", f"Today is {now.strftime('%A, %B %d, %Y')}.")

    if _contains_any(normalized, PROGRESS_PATTERNS):
        snapshot = get_dashboard_snapshot()
        return _build_result(
            "progress",
            _friendly_progress(snapshot),
            payload=snapshot,
        )

    return None
