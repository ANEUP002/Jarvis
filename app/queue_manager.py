import json                     ##This file manages your file-based queue. The whole system uses JSON files as task. So we need a module that loads a task, saves update, m,oves task between folders, lists pending task.
import shutil                      ##wHY this is useful because it is simple , easy to debug, restart  safe.
from pathlib import Path
from typing import Any, Dict, List

BASE = Path("queue")
PENDING = BASE / "pending"
IN_PROGRESS = BASE / "in_progress"
COMPLETED = BASE / "completed"
FAILED = BASE / "failed"


def load_json(file_path: Path) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(file_path: Path, data: Dict[str, Any]) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def move_file(file_path: Path, destination_folder: Path) -> Path:
    destination = destination_folder / file_path.name
    shutil.move(str(file_path), str(destination))
    return destination


def get_pending_tasks() -> List[Path]:
    return sorted(PENDING.glob("*.json"))