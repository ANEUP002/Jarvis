# =========================
# PERSONAL ROUTINE TOOLS
# =========================

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from app.event_streaming import event_stream
from tools.base_tool import BaseTool

PROFILE_DIR = Path(__file__).parent.parent / "memory" / "profile"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
ROUTINE_FILE = PROFILE_DIR / "daily_routine.json"


def _default_routine() -> Dict[str, Any]:
    return {
        "timezone": "America/New_York",
        "updated_at": None,
        "blocks": [],
    }


def _load_routine() -> Dict[str, Any]:
    if not ROUTINE_FILE.exists():
        return _default_routine()
    try:
        with open(ROUTINE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return _default_routine()


def _save_routine(data: Dict[str, Any]) -> None:
    with open(ROUTINE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_routine_snapshot(now: datetime = None) -> Dict[str, Any]:
    routine = _load_routine()
    now = now or datetime.now()
    current_time = now.strftime("%H:%M")

    current_block = None
    upcoming: List[Dict[str, Any]] = []
    for block in routine.get("blocks", []):
        start = block.get("start", "")
        end = block.get("end", "")
        if start and end and start <= current_time <= end:
            current_block = block
        elif start and start > current_time:
            upcoming.append(block)

    return {
        "date": now.date().isoformat(),
        "current_time": current_time,
        "current_block": current_block,
        "next_block": upcoming[0] if upcoming else None,
        "blocks": routine.get("blocks", []),
        "timezone": routine.get("timezone", "America/New_York"),
        "updated_at": routine.get("updated_at"),
    }


class SaveDailyRoutineTool(BaseTool):
    name = "save_daily_routine"
    description = "Save your daily routine for dashboard and assistant context"

    def execute(self, blocks: List[Dict[str, Any]], timezone: str = "America/New_York", **kwargs) -> Dict[str, Any]:
        try:
            if not isinstance(blocks, list):
                return {"success": False, "result": None, "error": "blocks must be a list"}

            normalized_blocks = []
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                normalized_blocks.append({
                    "start": block.get("start", ""),
                    "end": block.get("end", ""),
                    "title": block.get("title", ""),
                    "notes": block.get("notes", ""),
                    "category": block.get("category", "general"),
                })

            payload = {
                "timezone": timezone,
                "updated_at": datetime.now().isoformat(),
                "blocks": normalized_blocks,
            }
            _save_routine(payload)
            event_stream.emit(
                "routine_updated",
                {
                    "timezone": timezone,
                    "blocks_count": len(normalized_blocks),
                },
                level="info",
            )
            return {
                "success": True,
                "result": {
                    "status": "saved",
                    "blocks_count": len(normalized_blocks),
                    "path": str(ROUTINE_FILE),
                },
                "error": None,
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class GetDailyRoutineTool(BaseTool):
    name = "get_daily_routine"
    description = "Get the saved daily routine and current block"

    def execute(self, **kwargs) -> Dict[str, Any]:
        try:
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "routine_snapshot_loaded"},
                level="info",
            )
            return {
                "success": True,
                "result": get_routine_snapshot(),
                "error": None,
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}
