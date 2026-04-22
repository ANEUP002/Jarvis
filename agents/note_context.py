from typing import Any, Dict, List, Tuple

from tools import ToolsManager


def load_note_context(task: dict | str, agent_name: str, limit: int = 3) -> Tuple[str, Dict[str, Any] | None]:
    manager = ToolsManager()
    input_text = task.get("search_query") or task.get("input", "") if isinstance(task, dict) else str(task)
    # Strip conversation history prefix added by jarvis.py session memory
    if "[CURRENT REQUEST]" in input_text:
        input_text = input_text.split("[CURRENT REQUEST]")[-1].strip()
    task_id = task.get("task_id") if isinstance(task, dict) else None

    try:
        search_result = manager.execute(
            "search_notes",
            query=input_text,
            top_k=limit,
            task_type=agent_name,
            agent_name=agent_name,
            task_id=task_id,
        )
        if not search_result.get("success"):
            return "", None

        note_hits = search_result.get("result", {}).get("results", [])
        if not note_hits:
            return "", {"status": "empty", "count": 0}

        rendered_notes: List[str] = []
        for hit in note_hits:
            note_result = manager.execute(
                "get_note",
                note_id=hit.get("note_id"),
                task_type=agent_name,
                agent_name=agent_name,
                task_id=task_id,
            )
            if not note_result.get("success"):
                continue
            note = note_result.get("result", {})
            rendered_notes.append(
                "\n".join(
                    [
                        f"Title: {note.get('title')}",
                        f"Tags: {', '.join(note.get('tags', [])) or 'none'}",
                        f"Links: {', '.join(note.get('links', [])) or 'none'}",
                        f"Backlinks: {', '.join(note.get('backlinks', [])) or 'none'}",
                        f"Body: {note.get('body', '').strip()}",
                    ]
                )
            )

        if not rendered_notes:
            return "", {"status": "empty", "count": 0}

        return (
            "\n\nRelevant notes from the second brain:\n" + "\n\n---\n\n".join(rendered_notes),
            {
                "status": "loaded",
                "count": len(rendered_notes),
                "results": note_hits,
            },
        )
    except Exception as exc:
        return "", {"status": "error", "error": str(exc)}
