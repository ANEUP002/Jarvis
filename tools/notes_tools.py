# =========================
# SECOND BRAIN NOTE TOOLS
# =========================

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from app.event_streaming import event_stream
from tools.base_tool import BaseTool
from tools.vector_db_advanced import AdvancedVectorStore


NOTES_DIR = Path(__file__).parent.parent / "memory" / "notes"
NOTES_DIR.mkdir(parents=True, exist_ok=True)

NOTE_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s_-]", "", value).strip().lower()
    cleaned = re.sub(r"[\s_-]+", "-", cleaned)
    return cleaned or "untitled-note"


def _note_path(note_id: str, category: str | None = None) -> Path:
    slug = _slugify(note_id)
    base_dir = NOTES_DIR
    if category:
        safe_category = Path(*[_slugify(part) for part in str(category).replace("\\", "/").split("/") if part.strip()])
        base_dir = NOTES_DIR / safe_category
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"{slug}.md"


def _extract_links(content: str) -> List[str]:
    seen = []
    for match in NOTE_LINK_RE.findall(content or ""):
        target = match.strip()
        if target and target not in seen:
            seen.append(target)
    return seen


def _build_note_document(metadata: Dict[str, Any], body: str) -> str:
    header = json.dumps(metadata, ensure_ascii=True, indent=2)
    return f"---\n{header}\n---\n\n{body.rstrip()}\n"


def _parse_note_document(raw_text: str) -> Dict[str, Any]:
    default = {"metadata": {}, "body": raw_text or ""}
    if not raw_text.startswith("---\n"):
        return default

    try:
        _, rest = raw_text.split("---\n", 1)
        header, body = rest.split("\n---\n", 1)
        metadata = json.loads(header)
        return {"metadata": metadata if isinstance(metadata, dict) else {}, "body": body.lstrip("\n")}
    except Exception:
        return default


def _load_note(path: Path) -> Dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    parsed = _parse_note_document(raw)
    metadata = parsed["metadata"]
    body = parsed["body"]
    note_id = metadata.get("note_id", path.stem)
    return {
        "note_id": note_id,
        "title": metadata.get("title", note_id),
        "category": metadata.get("category", ""),
        "tags": metadata.get("tags", []),
        "aliases": metadata.get("aliases", []),
        "created_at": metadata.get("created_at"),
        "updated_at": metadata.get("updated_at"),
        "links": metadata.get("links", _extract_links(body)),
        "body": body,
        "path": str(path),
        "source_task_id": metadata.get("source_task_id"),
        "source_type": metadata.get("source_type"),
    }


def _list_note_records() -> List[Dict[str, Any]]:
    notes = []
    for path in sorted(NOTES_DIR.rglob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            notes.append(_load_note(path))
        except Exception:
            continue
    return notes


def _find_note_path(note_id: str) -> Path | None:
    direct = _note_path(note_id)
    if direct.exists():
        return direct
    slug = _slugify(note_id)
    for path in NOTES_DIR.rglob(f"{slug}.md"):
        return path
    return None


def _find_backlinks(note_title: str) -> List[str]:
    backlinks = []
    for note in _list_note_records():
        if note.get("title") == note_title:
            continue
        if note_title in note.get("links", []):
            backlinks.append(note.get("title"))
    return backlinks


def _build_backlinks_index(notes: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """O(N) single-pass backlinks index: {title → [titles that link to it]}."""
    index: Dict[str, List[str]] = {}
    for note in notes:
        for link_title in note.get("links", []):
            index.setdefault(link_title, [])
            if note["title"] not in index[link_title]:
                index[link_title].append(note["title"])
    return index


class SaveNoteTool(BaseTool):
    name = "save_note"
    description = "Create or update a markdown note with metadata, backlinks, and semantic indexing"

    def execute(
        self,
        title: str,
        content: str,
        tags: List[str] | None = None,
        note_id: str | None = None,
        category: str = "general",
        embedding_provider: str = "huggingface",
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            if not title.strip():
                return {"success": False, "result": None, "error": "title is required"}

            event_stream.emit(
                "memory_accessed",
                {"tool_name": self.name, "action": "save_note", "title": title},
            )

            resolved_id = note_id or title
            path = _note_path(resolved_id, category=category)
            now = datetime.now().isoformat()
            existing = _load_note(path) if path.exists() else None
            links = _extract_links(content)
            metadata = {
                "note_id": _slugify(resolved_id),
                "title": title.strip(),
                "category": category,
                "tags": tags or [],
                "aliases": kwargs.get("aliases", existing.get("aliases", []) if existing else []),
                "created_at": existing.get("created_at") if existing else now,
                "updated_at": now,
                "links": links,
                "source_task_id": kwargs.get("source_task_id"),
                "source_type": kwargs.get("source_type"),
            }
            path.write_text(_build_note_document(metadata, content), encoding="utf-8")

            vector_store = AdvancedVectorStore("vector_db_advanced", embedding_provider)
            vector_store.store(
                key=f"note:{metadata['note_id']}",
                text=f"{metadata['title']}\n\n{content}",
                metadata={"type": "note", "title": metadata["title"], "tags": metadata["tags"]},
            )

            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "note_saved",
                    "note_id": metadata["note_id"],
                    "links_count": len(links),
                    "tags_count": len(metadata["tags"]),
                },
            )

            return {
                "success": True,
                "result": {
                    "note_id": metadata["note_id"],
                    "title": metadata["title"],
                    "path": str(path),
                    "category": category,
                    "links": links,
                    "tags": metadata["tags"],
                },
                "error": None,
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class GetNoteTool(BaseTool):
    name = "get_note"
    description = "Read a note with backlinks and metadata"

    def execute(self, note_id: str, **kwargs) -> Dict[str, Any]:
        try:
            path = _find_note_path(note_id)
            if not path or not path.exists():
                return {"success": False, "result": None, "error": f"note not found: {note_id}"}

            note = _load_note(path)
            note["backlinks"] = _find_backlinks(note["title"])
            event_stream.emit(
                "memory_accessed",
                {"tool_name": self.name, "action": "get_note", "note_id": note["note_id"]},
            )
            return {"success": True, "result": note, "error": None}
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class ListNotesTool(BaseTool):
    name = "list_notes"
    description = "List notes in the second brain with optional tag and category filters"

    def execute(
        self,
        limit: int = 25,
        tag: str | None = None,
        category: str | None = None,
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            all_notes = _list_note_records()
            # Build backlinks index in one O(N) pass instead of per-note O(N) scans
            backlinks_index = _build_backlinks_index(all_notes)

            notes = all_notes
            if tag:
                notes = [n for n in notes if tag in n.get("tags", [])]
            if category:
                notes = [n for n in notes if n.get("category", "").startswith(category)]

            results = []
            for note in notes[:limit]:
                results.append({
                    "note_id": note["note_id"],
                    "title": note["title"],
                    "category": note["category"],
                    "tags": note["tags"],
                    "aliases": note.get("aliases", []),
                    "updated_at": note["updated_at"],
                    "links_count": len(note["links"]),
                    "backlinks_count": len(backlinks_index.get(note["title"], [])),
                })

            event_stream.emit(
                "memory_accessed",
                {"tool_name": self.name, "action": "list_notes", "count": len(results)},
            )
            return {"success": True, "result": {"notes": results, "count": len(results)}, "error": None}
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class SearchNotesTool(BaseTool):
    name = "search_notes"
    description = "Search notes by full-text, tags, category, and semantic similarity"

    def execute(
        self,
        query: str,
        top_k: int = 5,
        embedding_provider: str = "huggingface",
        tags: List[str] | None = None,
        category: str | None = None,
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            if not query.strip():
                return {"success": False, "result": None, "error": "query is required"}

            notes = _list_note_records()

            # Apply tag / category filters before scoring
            if tags:
                notes = [n for n in notes if any(t in n.get("tags", []) for t in tags)]
            if category:
                notes = [n for n in notes if n.get("category", "").startswith(category)]

            query_lower = query.lower()
            lexical_hits = []
            for note in notes:
                # Full-body search including all aliases
                alias_text = " ".join(note.get("aliases", []))
                haystack = " ".join([
                    note["title"],
                    alias_text,
                    " ".join(note.get("tags", [])),
                    note["body"],          # full body, not [:500]
                ]).lower()
                if query_lower in haystack:
                    # Boost score if match is in title or alias
                    score = 1.5 if query_lower in note["title"].lower() else 1.0
                    lexical_hits.append({
                        "note_id": note["note_id"],
                        "title": note["title"],
                        "score": score,
                        "source": "lexical",
                    })

            vector_store = AdvancedVectorStore("vector_db_advanced", embedding_provider)
            note_ids_in_filter = {n["note_id"] for n in notes}
            semantic_hits = []
            for key, score, _text in vector_store.search(query, top_k=max(top_k * 3, 10)):
                if not str(key).startswith("note:"):
                    continue
                note_key = str(key).split("note:", 1)[1]
                # Respect tag/category filter
                if note_ids_in_filter and note_key not in note_ids_in_filter:
                    continue
                path = _note_path(note_key)
                if not path.exists():
                    path = _find_note_path(note_key)
                    if not path:
                        continue
                note = _load_note(path)
                semantic_hits.append({
                    "note_id": note["note_id"],
                    "title": note["title"],
                    "score": round(score, 4),
                    "source": "semantic",
                })

            merged: Dict[str, Any] = {}
            for hit in lexical_hits + semantic_hits:
                current = merged.get(hit["note_id"])
                if not current or hit["score"] > current["score"]:
                    merged[hit["note_id"]] = hit

            ranked = sorted(merged.values(), key=lambda item: item["score"], reverse=True)[:top_k]
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "note_search_completed", "query": query, "count": len(ranked)},
            )
            return {"success": True, "result": {"query": query, "results": ranked, "count": len(ranked)}, "error": None}
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class GetNoteGraphTool(BaseTool):
    name = "get_note_graph"
    description = "Return note nodes and edges for graph visualization"

    def execute(self, limit: int = 50, **kwargs) -> Dict[str, Any]:
        try:
            all_notes = _list_note_records()
            # Build backlinks index once — O(N) instead of O(N²)
            backlinks_index = _build_backlinks_index(all_notes)
            notes = all_notes[:limit]

            title_to_id = {note["title"]: note["note_id"] for note in notes}
            nodes = []
            edges = []

            for note in notes:
                nodes.append({
                    "id": note["note_id"],
                    "label": note["title"],
                    "category": note.get("category", ""),
                    "tags": note["tags"],
                    "aliases": note.get("aliases", []),
                    "links_count": len(note["links"]),
                    "backlinks_count": len(backlinks_index.get(note["title"], [])),
                    "source_task_id": note.get("source_task_id"),
                })
                for link in note["links"]:
                    target_id = title_to_id.get(link)
                    if target_id:
                        edges.append({"source": note["note_id"], "target": target_id})

            return {
                "success": True,
                "result": {"nodes": nodes, "edges": edges, "total_notes": len(all_notes)},
                "error": None,
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class DeleteNoteTool(BaseTool):
    name = "delete_note"
    description = "Delete a note from the second brain and remove it from the vector index"

    def execute(self, note_id: str, **kwargs) -> Dict[str, Any]:
        try:
            path = _find_note_path(note_id)
            if not path or not path.exists():
                return {"success": False, "result": None, "error": f"note not found: {note_id}"}

            note = _load_note(path)
            slug = note["note_id"]
            path.unlink()

            # Remove from vector store
            vector_store = AdvancedVectorStore("vector_db_advanced", "huggingface")
            vector_store.delete(f"note:{slug}")

            event_stream.emit(
                "memory_accessed",
                {"tool_name": self.name, "action": "delete_note", "note_id": slug},
            )
            return {
                "success": True,
                "result": {"note_id": slug, "title": note["title"], "deleted": True},
                "error": None,
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


# ── Daily Notes ───────────────────────────────────────────────────────────────

def create_daily_note(date: str | None = None, extra_content: str = "") -> Dict[str, Any]:
    """
    Create or retrieve the daily note for a given date (defaults to today).
    Format: YYYY-MM-DD, stored at memory/notes/daily/YYYY-MM-DD.md
    Idempotent — safe to call multiple times on the same day.
    """
    date_str = date or datetime.now().strftime("%Y-%m-%d")
    title = f"Daily Note {date_str}"
    note_id = date_str

    tool = SaveNoteTool()
    # Load existing content if it already exists
    path = _note_path(note_id, category="daily")
    existing_body = ""
    if path.exists():
        existing = _load_note(path)
        existing_body = existing["body"]

    template = f"# {date_str}\n\n## Tasks\n\n## Notes\n\n## Links\n"
    body = existing_body or template
    if extra_content:
        body = body.rstrip() + f"\n\n{extra_content}"

    return tool.execute(
        title=title,
        content=body,
        note_id=note_id,
        category="daily",
        tags=["daily", "journal", date_str],
    )


def get_today_note() -> Dict[str, Any]:
    """Return today's daily note, creating it if it doesn't exist."""
    return create_daily_note()


def save_task_result_note(task: Dict[str, Any], response_text: str) -> Dict[str, Any]:
    manager = SaveNoteTool()
    task_type = task.get("task_type", "general")
    task_id = task.get("task_id", "task")
    title = f"{task_type.title()} Task {task_id}"
    input_text = task.get("input", "").strip()
    links = []
    notes_used = task.get("result", {}).get("notes_used") if isinstance(task.get("result"), dict) else None
    if isinstance(notes_used, dict):
        for item in notes_used.get("results", [])[:5]:
            if item.get("title"):
                links.append(f"[[{item['title']}]]")

    body_parts = [
        f"Task ID: {task_id}",
        f"Task Type: {task_type}",
        f"Agent: {task.get('agent', 'unknown')}",
        f"Model: {task.get('model', 'unknown')}",
        "",
        "Original Request:",
        input_text,
        "",
        "Response:",
        response_text.strip(),
    ]
    if links:
        body_parts.extend(["", "Related Notes:", *links])
    memory = task.get("result", {}).get("memory") if isinstance(task.get("result"), dict) else None
    if isinstance(memory, dict) and memory.get("summary"):
        body_parts.extend(["", "Memory Workflow:", memory["summary"]])

    return manager.execute(
        title=title,
        content="\n".join(body_parts).strip(),
        note_id=task_id,
        category=f"tasks/{task_type}",
        tags=[task_type, "task-result", task.get("agent", "unknown")],
        source_task_id=task_id,
        source_type="task_result",
    )


def summarize_task_memory(task: Dict[str, Any]) -> Dict[str, Any]:
    result = task.get("result", {}) if isinstance(task.get("result"), dict) else {}
    memory = result.get("memory", {}) if isinstance(result, dict) else {}
    second_brain = task.get("second_brain", {}) if isinstance(task.get("second_brain"), dict) else {}

    captures = []
    for key, value in second_brain.items():
        if isinstance(value, dict):
            note = value.get("result") or value.get("note")
            if isinstance(note, dict) and note.get("note_id"):
                captures.append({
                    "channel": key,
                    "note_id": note.get("note_id"),
                    "title": note.get("title"),
                    "category": note.get("category"),
                })

    return {
        "used": bool(memory.get("used")),
        "notes_used_count": memory.get("notes_used_count", 0),
        "note_titles": memory.get("note_titles", []),
        "summary": memory.get("summary", "No second-brain notes were used."),
        "captures": captures,
    }


def save_research_note(task: Dict[str, Any], findings_text: str) -> Dict[str, Any]:
    task_id = task.get("task_id", "research")
    title = f"Research {task_id}"
    body = "\n".join(
        [
            f"Task ID: {task_id}",
            "Type: research",
            "",
            "Query:",
            task.get("input", "").strip(),
            "",
            "Findings:",
            findings_text.strip(),
        ]
    ).strip()
    return SaveNoteTool().execute(
        title=title,
        content=body,
        note_id=f"research-{task_id}",
        category="research",
        tags=["research", "auto-captured"],
        source_task_id=task_id,
        source_type="research_output",
    )


def save_email_note(task: Dict[str, Any], email_result: Dict[str, Any], body_text: str) -> Dict[str, Any]:
    if not email_result or email_result.get("status") != "success":
        return {"success": False, "result": None, "error": "email not successfully generated"}

    result_payload = email_result.get("result") or {}
    task_id = task.get("task_id", "email")
    subject = result_payload.get("subject", "Email Output")
    recipients = ", ".join(result_payload.get("to", [])) if isinstance(result_payload.get("to"), list) else ""
    body = "\n".join(
        [
            f"Task ID: {task_id}",
            f"Subject: {subject}",
            f"Recipients: {recipients or 'unknown'}",
            f"Sent Via: {result_payload.get('sent_via', 'unknown')}",
            "",
            "Email Body:",
            body_text.strip(),
        ]
    ).strip()
    return SaveNoteTool().execute(
        title=f"Email {subject}",
        content=body,
        note_id=f"email-{task_id}",
        category="communications/email",
        tags=["email", "auto-captured"],
        source_task_id=task_id,
        source_type="email_output",
    )


def save_file_output_note(task: Dict[str, Any], file_result: Dict[str, Any], body_text: str) -> Dict[str, Any]:
    if not file_result or file_result.get("status") != "success":
        return {"success": False, "result": None, "error": "file output not successfully generated"}

    filepath = file_result.get("filepath", "")
    task_id = task.get("task_id", "file")
    body = "\n".join(
        [
            f"Task ID: {task_id}",
            f"File: {filepath}",
            "",
            "Generated Output:",
            body_text.strip(),
        ]
    ).strip()
    return SaveNoteTool().execute(
        title=f"File Output {task_id}",
        content=body,
        note_id=f"file-output-{task_id}",
        category="files/generated",
        tags=["file-output", "auto-captured"],
        source_task_id=task_id,
        source_type="file_output",
    )
