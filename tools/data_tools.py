# =========================
# DATA PROCESSING TOOLS
# =========================

import json
import csv
from pathlib import Path
from typing import Any, Dict, List

from app.event_streaming import event_stream
from tools.base_tool import BaseTool


class JsonProcessTool(BaseTool):
    """Process and transform JSON data"""
    
    name = "process_json"
    description = "Process, filter, and transform JSON data"
    
    def execute(self, data: Dict, operation: str = "pretty", **kwargs) -> Dict[str, Any]:
        try:
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "json_process_started", "operation": operation},
            )
            if operation == "pretty":
                result = json.dumps(data, indent=2)
            elif operation == "minify":
                result = json.dumps(data, separators=(',', ':'))
            else:
                result = data
            
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "json_process_completed", "operation": operation},
            )
            return {
                "success": True,
                "result": result,
                "error": None,
                "operation": operation
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class CsvProcessTool(BaseTool):
    """Process CSV files"""
    
    name = "process_csv"
    description = "Read, write, and process CSV files"
    
    def execute(self, filepath: str, operation: str = "read", data: List = None, **kwargs) -> Dict[str, Any]:
        try:
            path = Path(filepath)
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "csv_process_started", "operation": operation, "filepath": str(path)},
            )
            
            if operation == "read":
                rows = []
                with open(path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                
                event_stream.emit(
                    "tool_progress",
                    {"tool_name": self.name, "stage": "csv_process_completed", "operation": operation, "row_count": len(rows)},
                )
                return {
                    "success": True,
                    "result": rows,
                    "error": None,
                    "filepath": str(path),
                    "row_count": len(rows)
                }
            
            elif operation == "write":
                if not data or len(data) == 0:
                    return {"success": False, "result": None, "error": "No data to write"}
                
                fieldnames = list(data[0].keys())
                path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data)
                
                event_stream.emit(
                    "tool_progress",
                    {"tool_name": self.name, "stage": "csv_process_completed", "operation": operation, "row_count": len(data)},
                )
                return {
                    "success": True,
                    "result": str(path),
                    "error": None,
                    "filepath": str(path),
                    "row_count": len(data)
                }
            
            else:
                return {"success": False, "result": None, "error": f"Unknown operation: {operation}"}
        
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class TextProcessTool(BaseTool):
    """Process and transform text data"""
    
    name = "process_text"
    description = "Process text (split, join, format, etc.)"
    
    def execute(self, text: str, operation: str = "count", **kwargs) -> Dict[str, Any]:
        try:
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "text_process_started", "operation": operation, "text_length": len(text)},
            )
            if operation == "count":
                result = {
                    "chars": len(text),
                    "words": len(text.split()),
                    "lines": len(text.split('\n'))
                }
            elif operation == "lines":
                result = text.split('\n')
            elif operation == "sentences":
                result = [s.strip() for s in text.split('.') if s.strip()]
            else:
                result = text
            
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "text_process_completed", "operation": operation},
            )
            return {
                "success": True,
                "result": result,
                "error": None,
                "operation": operation
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}
