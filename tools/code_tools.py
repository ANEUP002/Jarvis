# =========================
# CODE EXECUTION TOOLS
# =========================

import subprocess
from typing import Any, Dict

from app.event_streaming import event_stream
from tools.base_tool import BaseTool


class ExecuteCodeTool(BaseTool):
    """Execute Python code"""
    
    name = "execute_code"
    description = "Execute Python code and return output"
    
    def execute(self, code: str, timeout: int = 30, **kwargs) -> Dict[str, Any]:
        try:
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "execution_started", "timeout": timeout, "code_length": len(code)},
            )
            result = subprocess.run(
                ["python", "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            payload = {
                "success": result.returncode == 0,
                "result": result.stdout.strip(),
                "error": result.stderr.strip() if result.returncode != 0 else None,
                "return_code": result.returncode
            }
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "execution_completed" if payload["success"] else "execution_failed",
                    "return_code": result.returncode,
                },
                level="info" if payload["success"] else "warning",
            )
            return payload
        except subprocess.TimeoutExpired:
            return {"success": False, "result": None, "error": f"Code execution timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class ExecuteShellTool(BaseTool):
    """Execute shell commands"""
    
    name = "execute_shell"
    description = "Execute shell commands and return output"
    
    def execute(self, command: str, timeout: int = 30, **kwargs) -> Dict[str, Any]:
        try:
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "shell_started", "timeout": timeout, "command": command[:160]},
            )
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            payload = {
                "success": result.returncode == 0,
                "result": result.stdout.strip(),
                "error": result.stderr.strip() if result.returncode != 0 else None,
                "return_code": result.returncode,
                "command": command
            }
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "shell_completed" if payload["success"] else "shell_failed",
                    "return_code": result.returncode,
                    "command": command[:160],
                },
                level="info" if payload["success"] else "warning",
            )
            return payload
        except subprocess.TimeoutExpired:
            return {"success": False, "result": None, "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}
