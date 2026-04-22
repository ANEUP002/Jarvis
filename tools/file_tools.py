# =========================
# FILE TOOLS
# =========================

import os
from pathlib import Path
from typing import Any, Dict, List

from app.event_streaming import event_stream
from tools.base_tool import BaseTool


class ReadFileTool(BaseTool):
    """Read file contents"""
    
    name = "read_file"
    description = "Read the contents of a file"
    
    def execute(self, filepath: str, **kwargs) -> Dict[str, Any]:
        try:
            path = Path(filepath)
            event_stream.emit("tool_progress", {"tool_name": self.name, "stage": "read_started", "filepath": str(path)})
            if not path.exists():
                return {"success": False, "result": None, "error": f"File not found: {filepath}"}
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "read_completed", "filepath": str(path), "size": len(content)}
            )
            
            return {
                "success": True,
                "result": content,
                "error": None,
                "filepath": str(path),
                "size": len(content)
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class WriteFileTool(BaseTool):
    """Write content to file"""
    
    name = "write_file"
    description = "Write content to a file (creates or overwrites)"
    
    def execute(self, filepath: str, content: str, **kwargs) -> Dict[str, Any]:
        try:
            path = Path(filepath)
            event_stream.emit("tool_progress", {"tool_name": self.name, "stage": "write_started", "filepath": str(path)})
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "write_completed", "filepath": str(path), "bytes_written": len(content)}
            )
            
            return {
                "success": True,
                "result": str(path),
                "error": None,
                "filepath": str(path),
                "bytes_written": len(content)
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class AppendFileTool(BaseTool):
    """Append content to file"""
    
    name = "append_file"
    description = "Append content to the end of a file"
    
    def execute(self, filepath: str, content: str, **kwargs) -> Dict[str, Any]:
        try:
            path = Path(filepath)
            event_stream.emit("tool_progress", {"tool_name": self.name, "stage": "append_started", "filepath": str(path)})
            
            with open(path, 'a', encoding='utf-8') as f:
                f.write(content)
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "append_completed", "filepath": str(path), "bytes_appended": len(content)}
            )
            
            return {
                "success": True,
                "result": str(path),
                "error": None,
                "filepath": str(path),
                "bytes_appended": len(content)
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class ListDirTool(BaseTool):
    """List directory contents"""
    
    name = "list_dir"
    description = "List files and directories in a folder"
    
    def execute(self, dirpath: str, **kwargs) -> Dict[str, Any]:
        try:
            path = Path(dirpath)
            event_stream.emit("tool_progress", {"tool_name": self.name, "stage": "list_started", "dirpath": str(path)})
            if not path.exists():
                return {"success": False, "result": None, "error": f"Directory not found: {dirpath}"}
            
            items = []
            for item in sorted(path.iterdir()):
                items.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else None
                })
            
            return {
                "success": True,
                "result": items,
                "error": None,
                "dirpath": str(path),
                "count": len(items)
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class DeleteFileTool(BaseTool):
    """Delete a file"""
    
    name = "delete_file"
    description = "Delete a file"
    
    def execute(self, filepath: str, **kwargs) -> Dict[str, Any]:
        try:
            path = Path(filepath)
            event_stream.emit("tool_progress", {"tool_name": self.name, "stage": "delete_started", "filepath": str(path)})
            if not path.exists():
                return {"success": False, "result": None, "error": f"File not found: {filepath}"}
            
            path.unlink()
            event_stream.emit("tool_progress", {"tool_name": self.name, "stage": "delete_completed", "filepath": str(path)})
            
            return {
                "success": True,
                "result": str(path),
                "error": None,
                "filepath": str(path)
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class FileSearchTool(BaseTool):
    """Search for files matching a pattern"""
    
    name = "file_search"
    description = "Search for files matching a pattern (using glob)"
    
    def execute(self, pattern: str, start_dir: str = ".", **kwargs) -> Dict[str, Any]:
        try:
            start_path = Path(start_dir)
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "search_started", "pattern": pattern, "start_dir": str(start_path)}
            )
            matches = list(start_path.glob(pattern))
            
            files = [str(f) for f in matches if f.is_file()]
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "search_completed", "pattern": pattern, "count": len(files)}
            )
            
            return {
                "success": True,
                "result": files,
                "error": None,
                "pattern": pattern,
                "count": len(files)
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}
