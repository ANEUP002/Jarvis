"""
JARVIS Adaptive Learning Engine

Every conversation makes JARVIS smarter about YOU specifically:

1. Auto-extraction  — silently pulls facts from what you say
2. Preference learning — detects how you like answers (short/long, formal/casual)
3. People & projects — remembers names, colleagues, ongoing work
4. Style adaptation  — adjusts tone based on feedback patterns
5. Persistent memory — survives restarts, grows over time
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

_MEMORY_DIR = Path(__file__).parent.parent / "memory"
PROFILE_PATH  = _MEMORY_DIR / "profile" / "user_profile.json"
SESSION_PATH  = _MEMORY_DIR / "session.json"

_lock = threading.Lock()

_DEFAULT_PROFILE = {
    "name": None,
    "facts": [],
    "people": {},          # {"John": "colleague at work"}
    "projects": [],        # ["building a JARVIS assistant"]
    "preferences": {
        "answer_length": "auto",   # auto | short | detailed
        "response_style": "auto",  # auto | conversational | structured
    },
    "interests": {},       # {"AI": 12, "career": 5}
    "corrections": [],
    "stats": {
        "total_queries": 0,
        "session_count": 0,
        "first_seen": None,
        "last_seen": None,
    },
}


# ── Profile I/O ───────────────────────────────────────────────────────────────

def load_profile() -> dict:
    try:
        if PROFILE_PATH.exists():
            data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
            # Merge with defaults so new keys always exist
            merged = dict(_DEFAULT_PROFILE)
            merged.update(data)
            for k, v in _DEFAULT_PROFILE.items():
                if isinstance(v, dict) and k not in data:
                    merged[k] = dict(v)
            return merged
    except Exception:
        pass
    return _deepcopy_default()


def _deepcopy_default() -> dict:
    import copy
    return copy.deepcopy(_DEFAULT_PROFILE)


def _save_profile(profile: dict) -> None:
    try:
        PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROFILE_PATH.write_text(
            json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


def _save_async(profile: dict) -> None:
    threading.Thread(target=_save_profile, args=(profile,), daemon=True).start()


# ── Session persistence ───────────────────────────────────────────────────────

def load_session(max_turns: int = 10) -> list:
    try:
        if SESSION_PATH.exists():
            return json.loads(SESSION_PATH.read_text(encoding="utf-8"))[-max_turns:]
    except Exception:
        pass
    return []


def save_session(turns: list) -> None:
    def _write():
        try:
            SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
            SESSION_PATH.write_text(
                json.dumps(turns[-30:], indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass
    threading.Thread(target=_write, daemon=True).start()


# ── Session stats ─────────────────────────────────────────────────────────────

def record_session_start() -> None:
    def _update():
        with _lock:
            p = load_profile()
            stats = p.setdefault("stats", {})
            stats["session_count"] = stats.get("session_count", 0) + 1
            stats["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            if not stats.get("first_seen"):
                stats["first_seen"] = datetime.now().strftime("%Y-%m-%d")
            _save_profile(p)
    threading.Thread(target=_update, daemon=True).start()


def record_query() -> None:
    def _update():
        with _lock:
            p = load_profile()
            p.setdefault("stats", {})
            p["stats"]["total_queries"] = p["stats"].get("total_queries", 0) + 1
            _save_profile(p)
    threading.Thread(target=_update, daemon=True).start()


# ── Passive fact extraction from conversation ─────────────────────────────────

# Patterns that reveal personal facts without the user explicitly saying "remember"
_AUTO_PATTERNS = [
    # Identity
    (r"\bmy name(?:'?s| is) (\w+)", "name"),
    (r"\bcall me (\w+)", "name"),
    (r"\bi(?:'?m| am) (\w+(?:\s+\w+)?),?\s+(?:a |an )?(?:software|data|machine|AI|ML|web|mobile|backend|frontend|full.?stack|senior|junior|lead)?(?:\s+)?(?:engineer|developer|scientist|analyst|designer|manager|student|researcher|consultant)", "job"),
    (r"\bi(?:'?m| am) (?:a |an )?(?:software|data|machine|AI|ML|web|mobile|backend|frontend|full.?stack|senior|junior|lead)?\s*(?:engineer|developer|scientist|analyst|designer|manager|student|researcher|consultant)", "job"),
    # Location
    (r"\bi(?:'?m| am) (?:in|from|based in) ([\w\s,]+?)(?:\.|,|$)", "location"),
    (r"\bi live in ([\w\s,]+?)(?:\.|,|$)", "location"),
    # Work
    (r"\bi work(?:ing)? (?:at|for|with) ([\w\s]+?)(?:\.|,|$)", "employer"),
    (r"\bmy (?:company|employer|workplace|office) is ([\w\s]+?)(?:\.|,|$)", "employer"),
    # Projects
    (r"\bi(?:'?m| am) (?:building|working on|developing|creating|making) ([\w\s]+?)(?:\.|,|$)", "project"),
    (r"\bmy (?:project|app|side project|startup) is (?:called )?([^\.\,]+)", "project"),
    # People
    (r"\bmy (?:boss|manager|supervisor|lead) (?:is |'?s )?(\w+)", "boss"),
    (r"\bmy (?:colleague|coworker|teammate) (\w+)", "colleague"),
    (r"\bmy (?:friend|buddy) (\w+)", "friend"),
    (r"\bmy (?:wife|husband|partner|girlfriend|boyfriend) (?:is |'?s )?(\w+)", "partner"),
]

# Preference signals in follow-up messages
_PREFER_SHORTER = [
    "shorter", "brief", "concise", "too long", "simpler", "less detail",
    "just tell me", "in one sentence", "quick answer", "tldr", "tl;dr",
    "cut it short", "summarize", "one line",
]
_PREFER_LONGER = [
    "more detail", "elaborate", "expand", "explain more", "tell me more",
    "go deeper", "comprehensive", "full explanation", "in depth", "more info",
    "can you explain", "what do you mean",
]
_PREFER_CASUAL = [
    "too formal", "relax", "casual", "chill", "like a friend",
    "don't be so stiff", "friendly",
]
_PREFER_STRUCTURED = [
    "use bullet points", "structured", "with headers", "list format",
    "step by step", "numbered",
]

_STOP_WORDS = {
    "what", "who", "where", "when", "why", "how", "is", "are", "was", "were",
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "do",
    "does", "did", "can", "could", "would", "should", "me", "my", "i", "you",
    "it", "this", "that", "with", "from", "about", "tell", "give", "show",
    "please", "now", "today", "right", "going", "get", "make", "latest",
    "just", "very", "really", "some", "any", "all", "also", "then", "than",
}


def extract_from_message(user_msg: str) -> None:
    """Passively extract facts from what the user says, without them asking."""
    def _run():
        lower = user_msg.lower().strip()
        with _lock:
            p = load_profile()
            changed = False

            # Auto-patterns
            for pattern, fact_type in _AUTO_PATTERNS:
                m = re.search(pattern, lower, re.IGNORECASE)
                if not m:
                    continue
                value = m.group(1).strip().rstrip(".,")
                if len(value) < 2 or len(value) > 60:
                    continue

                if fact_type == "name" and not p.get("name"):
                    p["name"] = value.capitalize()
                    _add_fact(p, f"Name is {value.capitalize()}")
                    changed = True

                elif fact_type in ("job", "location", "employer"):
                    fact = f"{fact_type.capitalize()}: {value}"
                    if _add_fact(p, fact):
                        changed = True

                elif fact_type == "project":
                    clean = value.strip().rstrip(".")
                    if clean and clean not in p.get("projects", []):
                        p.setdefault("projects", []).append(clean)
                        p["projects"] = p["projects"][-10:]
                        _add_fact(p, f"Working on: {clean}")
                        changed = True

                elif fact_type in ("boss", "colleague", "friend", "partner"):
                    name = value.strip().capitalize()
                    if name and name not in p.get("people", {}):
                        p.setdefault("people", {})[name] = fact_type
                        _add_fact(p, f"{name} is their {fact_type}")
                        changed = True

            # Preference signals
            if any(s in lower for s in _PREFER_SHORTER):
                if p["preferences"].get("answer_length") != "short":
                    p["preferences"]["answer_length"] = "short"
                    changed = True
            elif any(s in lower for s in _PREFER_LONGER):
                if p["preferences"].get("answer_length") != "detailed":
                    p["preferences"]["answer_length"] = "detailed"
                    changed = True

            if any(s in lower for s in _PREFER_CASUAL):
                p["preferences"]["response_style"] = "conversational"
                changed = True
            elif any(s in lower for s in _PREFER_STRUCTURED):
                p["preferences"]["response_style"] = "structured"
                changed = True

            if changed:
                _save_profile(p)

    threading.Thread(target=_run, daemon=True).start()


def _add_fact(profile: dict, fact: str) -> bool:
    existing = {f["fact"].lower() for f in profile.get("facts", [])}
    if fact.lower() not in existing:
        profile.setdefault("facts", []).append({
            "fact": fact,
            "added": datetime.now().strftime("%Y-%m-%d"),
        })
        profile["facts"] = profile["facts"][-60:]
        return True
    return False


# ── Interest tracking ─────────────────────────────────────────────────────────

def track_interest(query: str) -> None:
    words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", query)]
    keywords = [w for w in words if w not in _STOP_WORDS]
    if not keywords:
        return

    def _update():
        with _lock:
            p = load_profile()
            interests = p.setdefault("interests", {})
            for kw in keywords[:4]:
                interests[kw] = interests.get(kw, 0) + 1
            if len(interests) > 150:
                p["interests"] = dict(
                    sorted(interests.items(), key=lambda x: x[1], reverse=True)[:100]
                )
            _save_profile(p)

    threading.Thread(target=_update, daemon=True).start()


# ── Explicit memory commands ──────────────────────────────────────────────────

_REMEMBER_PATTERNS = [
    r"^remember that (.+)",
    r"^remember[,:]?\s+(.+)",
    r"^note that (.+)",
    r"^keep in mind that (.+)",
    r"^always (.+)",
    r"^never (.+)",
    r"^i prefer (.+)",
    r"^i like (.+)",
    r"^i don'?t like (.+)",
    r"^my name is (\w+)",
    r"^call me (\w+)",
]
_FORGET_PATTERNS = [
    r"^forget (?:that )?(.+)",
    r"^delete (?:the )?memory (?:about )?(.+)",
]
_RECALL_PATTERNS = [
    "what do you know about me",
    "what do you remember",
    "tell me what you know",
    "what have you learned about me",
    "show my profile",
    "my profile",
    "what do you know",
]


def detect_memory_command(text: str) -> Optional[dict]:
    lower = text.lower().strip()

    if any(p in lower for p in _RECALL_PATTERNS):
        return {"action": "recall"}

    for pattern in _FORGET_PATTERNS:
        m = re.match(pattern, lower, re.IGNORECASE)
        if m:
            return {"action": "forget", "target": m.group(1).strip()}

    for pattern in _REMEMBER_PATTERNS:
        m = re.match(pattern, lower, re.IGNORECASE)
        if m:
            fact = m.group(1).strip().rstrip(".")
            if re.match(r"^(my name is|call me)\s+", lower, re.IGNORECASE):
                name = m.group(1).strip().split()[0].capitalize()
                return {"action": "set_name", "name": name}
            return {"action": "remember", "fact": fact}

    return None


def apply_memory_command(cmd: dict) -> str:
    with _lock:
        p = load_profile()
        action = cmd["action"]

        if action == "recall":
            return _format_recall(p)

        if action == "set_name":
            p["name"] = cmd["name"]
            _add_fact(p, f"Name is {cmd['name']}")
            _save_profile(p)
            return f"Got it, {cmd['name']}. I'll remember that."

        if action == "remember":
            _add_fact(p, cmd["fact"])
            _save_profile(p)
            return "Noted. I'll keep that in mind."

        if action == "forget":
            target = cmd["target"].lower()
            before = len(p.get("facts", []))
            p["facts"] = [f for f in p.get("facts", []) if target not in f["fact"].lower()]
            if p.get("name") and target in p["name"].lower():
                p["name"] = None
            removed = before - len(p.get("facts", []))
            _save_profile(p)
            return f"Done. Cleared {removed} item{'s' if removed != 1 else ''}." if removed else "Nothing matched that."

    return "Done."


def record_correction(text: str) -> None:
    def _run():
        with _lock:
            p = load_profile()
            c = p.setdefault("corrections", [])
            if text not in c:
                c.append(text)
                p["corrections"] = c[-20:]
            _save_profile(p)
    threading.Thread(target=_run, daemon=True).start()


def _format_recall(p: dict) -> str:
    parts = []
    if p.get("name"):
        parts.append(f"Your name is {p['name']}.")
    stats = p.get("stats", {})
    if stats.get("total_queries"):
        parts.append(f"We've had {stats['total_queries']} conversations across {stats.get('session_count', 1)} sessions.")
    facts = [f["fact"] for f in p.get("facts", [])[-12:]]
    if facts:
        parts.append("Things I know: " + "; ".join(facts) + ".")
    people = p.get("people", {})
    if people:
        parts.append("People: " + ", ".join(f"{n} ({r})" for n, r in list(people.items())[:6]) + ".")
    projects = p.get("projects", [])
    if projects:
        parts.append("Projects you've mentioned: " + ", ".join(projects[-4:]) + ".")
    interests = p.get("interests", {})
    if interests:
        top = sorted(interests.items(), key=lambda x: x[1], reverse=True)[:5]
        parts.append("Top topics: " + ", ".join(t for t, _ in top) + ".")
    prefs = {k: v for k, v in p.get("preferences", {}).items() if v != "auto"}
    if prefs:
        parts.append("Preferences: " + "; ".join(f"{k}={v}" for k, v in prefs.items()) + ".")
    if not parts:
        return "I don't have much on you yet. Just talk to me — I'll learn as we go."
    return " ".join(parts)


# ── Context injection ─────────────────────────────────────────────────────────

def get_user_context() -> str:
    """
    Build a rich, concise context block injected into every agent prompt.
    Grows more detailed as JARVIS learns more about the user.
    """
    try:
        p = load_profile()
        lines = []

        name = p.get("name")
        if name:
            lines.append(f"You are talking to {name}.")

        facts = [f["fact"] for f in p.get("facts", [])[-8:]]
        if facts:
            lines.append("Known facts: " + "; ".join(facts) + ".")

        people = p.get("people", {})
        if people:
            lines.append("Their contacts: " + ", ".join(f"{n} ({r})" for n, r in list(people.items())[:5]) + ".")

        projects = p.get("projects", [])
        if projects:
            lines.append("Current projects: " + ", ".join(projects[-3:]) + ".")

        interests = p.get("interests", {})
        if interests:
            top = sorted(interests.items(), key=lambda x: x[1], reverse=True)[:5]
            lines.append("Frequent topics: " + ", ".join(t for t, _ in top) + ".")

        prefs = p.get("preferences", {})
        length_pref = prefs.get("answer_length", "auto")
        style_pref  = prefs.get("response_style", "auto")
        if length_pref == "short":
            lines.append("Preference: keep answers brief and direct.")
        elif length_pref == "detailed":
            lines.append("Preference: give detailed, thorough answers.")
        if style_pref == "conversational":
            lines.append("Preference: casual, friendly tone.")
        elif style_pref == "structured":
            lines.append("Preference: structured responses with clear sections.")

        corrections = p.get("corrections", [])
        if corrections:
            lines.append("Avoid: " + "; ".join(corrections[-3:]) + ".")

        if not lines:
            return ""
        return "\n[Personal context — use this to tailor your response]\n" + "\n".join(lines)
    except Exception:
        return ""
