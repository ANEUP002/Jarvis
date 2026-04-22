from pathlib import Path
import asyncio
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.dashboard import (
    clear_dashboard_events,
    get_dashboard_snapshot,
    get_event_stats,
    get_live_events,
    get_note_record,
    get_task_record,
    get_task_timeline,
)
from scripts.submit import create_task
from tools import ToolsManager


BASE_DIR = Path(__file__).resolve().parent
UI_DIR = BASE_DIR / "dashboard_ui"

app = FastAPI(title="OfficeOS HUD", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")


class TaskCreateRequest(BaseModel):
    input: str


class NoteUpsertRequest(BaseModel):
    title: str
    content: str
    category: str = "general"
    tags: list[str] | None = None
    note_id: str | None = None


notes_manager = ToolsManager()


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {"ok": True}


@app.get("/api/snapshot")
def snapshot() -> Dict[str, Any]:
    return get_dashboard_snapshot()


@app.get("/api/events")
def events(limit: int = 100, event_type: str | None = None, level: str | None = None) -> Dict[str, Any]:
    return {"events": get_live_events(limit=limit, event_type=event_type, level=level)}


@app.get("/api/stats")
def stats() -> Dict[str, Any]:
    return get_event_stats()


@app.get("/api/timeline/{task_id}")
def timeline(task_id: str) -> Dict[str, Any]:
    return {"task_id": task_id, "events": get_task_timeline(task_id)}


@app.get("/api/task/{task_id}")
def task_detail(task_id: str) -> Dict[str, Any]:
    record = get_task_record(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="task not found")
    return record


@app.get("/api/note/{note_id}")
def note_detail(note_id: str) -> Dict[str, Any]:
    record = get_note_record(note_id)
    if not record:
        raise HTTPException(status_code=404, detail="note not found")
    return record


@app.get("/api/notes")
def notes_list(query: str | None = None, tag: str | None = None, limit: int = 12) -> Dict[str, Any]:
    if query and query.strip():
        result = notes_manager.execute("search_notes", query=query.strip(), top_k=limit)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error") or "note search failed")
        return result.get("result", {"results": [], "count": 0})

    result = notes_manager.execute("list_notes", limit=limit, tag=tag)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "note listing failed")
    return result.get("result", {"notes": [], "count": 0})


@app.post("/api/notes")
def notes_upsert(request: NoteUpsertRequest) -> Dict[str, Any]:
    if not request.title.strip():
        raise HTTPException(status_code=400, detail="title is required")
    result = notes_manager.execute(
        "save_note",
        title=request.title.strip(),
        content=request.content,
        category=request.category or "general",
        tags=request.tags or [],
        note_id=request.note_id,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "note save failed")
    return result.get("result", {})


@app.post("/api/events/clear")
def clear_events() -> Dict[str, Any]:
    clear_dashboard_events()
    return {"success": True}


@app.post("/api/tasks")
def submit_task(request: TaskCreateRequest) -> Dict[str, Any]:
    if not request.input.strip():
        raise HTTPException(status_code=400, detail="input is required")
    task = create_task(request.input.strip())
    return {"success": True, "task_id": task["task_id"], "task": task}


@app.websocket("/ws")
async def websocket_feed(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(get_dashboard_snapshot())
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return


@app.get("/")
def index() -> FileResponse:
    return FileResponse(UI_DIR / "index.html", headers={"Cache-Control": "no-store, max-age=0"})
