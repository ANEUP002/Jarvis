# =========================
# MEMORY & KNOWLEDGE TOOLS
# =========================

import json
from pathlib import Path
from typing import Any, Dict

from app.event_streaming import event_stream
from tools.base_tool import BaseTool


class SaveMemoryTool(BaseTool):
    """Save information to memory/knowledge base"""
    
    name = "save_memory"
    description = "Save key information to memory for later retrieval"
    
    def execute(self, key: str, data: Any, memory_dir: str = "memory", **kwargs) -> Dict[str, Any]:
        try:
            memory_path = Path(memory_dir)
            memory_path.mkdir(exist_ok=True)
            
            file_path = memory_path / f"{key}.json"
            event_stream.emit(
                "memory_accessed",
                {"tool_name": self.name, "action": "save", "key": key, "memory_dir": str(memory_path)},
            )
            
            with open(file_path, 'w') as f:
                json.dump({
                    "key": key,
                    "data": data,
                    "metadata": kwargs
                }, f, indent=2)
            
            return {
                "success": True,
                "result": str(file_path),
                "error": None,
                "key": key
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class LoadMemoryTool(BaseTool):
    """Load information from memory"""
    
    name = "load_memory"
    description = "Load previously saved information from memory"
    
    def execute(self, key: str, memory_dir: str = "memory", **kwargs) -> Dict[str, Any]:
        try:
            file_path = Path(memory_dir) / f"{key}.json"
            event_stream.emit(
                "memory_accessed",
                {"tool_name": self.name, "action": "load", "key": key, "memory_dir": memory_dir},
            )
            
            if not file_path.exists():
                return {"success": False, "result": None, "error": f"Memory not found for key: {key}"}
            
            with open(file_path, 'r') as f:
                content = json.load(f)
            
            return {
                "success": True,
                "result": content.get("data"),
                "error": None,
                "key": key
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class ListMemoryTool(BaseTool):
    """List all saved memory items"""
    
    name = "list_memory"
    description = "List all keys in memory"
    
    def execute(self, memory_dir: str = "memory", **kwargs) -> Dict[str, Any]:
        try:
            memory_path = Path(memory_dir)
            event_stream.emit(
                "memory_accessed",
                {"tool_name": self.name, "action": "list", "memory_dir": str(memory_path)},
            )
            
            if not memory_path.exists():
                return {"success": True, "result": [], "error": None, "count": 0}
            
            keys = [f.stem for f in memory_path.glob("*.json")]
            
            return {
                "success": True,
                "result": keys,
                "error": None,
                "count": len(keys)
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}
