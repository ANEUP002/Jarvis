from typing import Any, Dict, List, Tuple

from agents.note_context import load_note_context


def load_memory_bundle(task: dict | str, agent_name: str, limit: int = 3) -> Tuple[str, Dict[str, Any]]:
    note_context, notes_result = load_note_context(task, agent_name=agent_name, limit=limit)
    results = []
    if isinstance(notes_result, dict):
        results = notes_result.get("results", []) or []

    note_titles = [item.get("title") for item in results if item.get("title")]
    note_ids = [item.get("note_id") for item in results if item.get("note_id")]

    bundle = {
        "status": (notes_result or {}).get("status", "empty") if isinstance(notes_result, dict) else "empty",
        "count": len(results),
        "results": results,
        "note_titles": note_titles,
        "note_ids": note_ids,
        "summary": build_memory_summary(note_titles),
    }
    return note_context, bundle


def build_memory_summary(note_titles: List[str]) -> str:
    if not note_titles:
        return "No second-brain notes were used."
    if len(note_titles) == 1:
        return f"Used second-brain note: {note_titles[0]}"
    return f"Used {len(note_titles)} second-brain notes: {', '.join(note_titles[:4])}"


def attach_memory_metadata(
    payload: Dict[str, Any],
    notes_used: Dict[str, Any] | None,
    second_brain: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    memory = {
        "used": bool(notes_used and notes_used.get("count")),
        "notes_used_count": (notes_used or {}).get("count", 0),
        "note_titles": (notes_used or {}).get("note_titles", []),
        "summary": (notes_used or {}).get("summary", "No second-brain notes were used."),
    }
    payload["notes_used"] = notes_used
    payload["memory"] = memory
    if second_brain is not None:
        payload["second_brain"] = second_brain
        payload["memory"]["captures"] = summarize_second_brain(second_brain)
    return payload


def summarize_second_brain(second_brain: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    captures: List[Dict[str, Any]] = []
    if not isinstance(second_brain, dict):
        return captures

    for key, value in second_brain.items():
        if not isinstance(value, dict):
            continue
        note = value.get("result") or value.get("note") or value
        if isinstance(note, dict) and note.get("note_id"):
            captures.append(
                {
                    "channel": key,
                    "note_id": note.get("note_id"),
                    "title": note.get("title"),
                    "category": note.get("category"),
                }
            )
    return captures
