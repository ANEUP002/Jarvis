# =========================
# TOOLS MANAGER
# =========================
# Central registry and dispatcher for all tools

from typing import Any, Dict, Optional

from app.event_streaming import event_stream
from app.state import record_tool_metrics, update_state

# Import all tools
from tools.file_tools import (
    ReadFileTool,
    WriteFileTool,
    AppendFileTool,
    ListDirTool,
    DeleteFileTool,
    FileSearchTool,
)
from tools.code_tools import (
    ExecuteCodeTool,
    ExecuteShellTool,
)
from tools.web_tools import (
    WebSearchTool,
    FetchWebpageTool,
    ParseJsonTool,
)
from tools.weather_tools import (
    GetWeatherTool,
)
from tools.web_search_tools import (
    SerpAPISearchTool,
    GoogleCustomSearchTool,
    DuckDuckGoSearchTool,
    SemanticSearchTool,
)
from tools.memory_tools import (
    SaveMemoryTool,
    LoadMemoryTool,
    ListMemoryTool,
)
from tools.data_tools import (
    JsonProcessTool,
    CsvProcessTool,
    TextProcessTool,
)
from tools.vector_tools import (
    StoreVectorTool,
    SemanticSearchVectorTool,
    DeleteVectorTool,
    ListVectorsTool,
)
from tools.vector_db_advanced import (
    StoreVectorAdvancedTool,
    SemanticSearchAdvancedTool,
    ListVectorsAdvancedTool,
)
from tools.email_tools import (
    SendEmailTool,
    ListEmailsTool,
    GetEmailTool,
    SearchEmailsTool,
)
from tools.todo_tools import (
    CreateTodoTool,
    ListTodosTool,
    CompleteTodoTool,
    UpdateTodoTool,
    DeleteTodoTool,
    GetTodoStatsTool,
)
from tools.personal_tools import (
    SaveDailyRoutineTool,
    GetDailyRoutineTool,
)
from tools.notes_tools import (
    SaveNoteTool,
    GetNoteTool,
    ListNotesTool,
    SearchNotesTool,
    GetNoteGraphTool,
    DeleteNoteTool,
)
from tools.desktop_tools import ALL_DESKTOP_TOOLS
from tools.mcp_client import MCPCallTool, MCPListToolsTool, MCPServersTool


SERVICE_MAP = {
    "read_file": "filesystem",
    "write_file": "filesystem",
    "append_file": "filesystem",
    "list_dir": "filesystem",
    "delete_file": "filesystem",
    "file_search": "filesystem",
    "execute_code": "python_runtime",
    "execute_shell": "shell",
    "web_search": "web",
    "fetch_webpage": "web",
    "serpapi_search": "serpapi",
    "google_search": "google_custom_search",
    "duckduckgo_search": "duckduckgo",
    "get_weather": "weather",
    "save_memory": "memory",
    "load_memory": "memory",
    "list_memory": "memory",
    "process_json": "data_processing",
    "process_csv": "data_processing",
    "process_text": "data_processing",
    "store_vector": "vector_db",
    "vector_search": "vector_db",
    "delete_vector": "vector_db",
    "list_vectors": "vector_db",
    "store_vector_advanced": "vector_db",
    "vector_search_advanced": "vector_db",
    "list_vectors_advanced": "vector_db",
    "send_email": "smtp",
    "create_todo": "todo",
    "list_todos": "todo",
    "complete_todo": "todo",
    "update_todo": "todo",
    "delete_todo": "todo",
    "get_todo_stats": "todo",
    "get_daily_routine": "routine",
    "save_daily_routine": "routine",
    "save_note": "second_brain",
    "get_note": "second_brain",
    "list_notes": "second_brain",
    "search_notes": "second_brain",
    "get_note_graph": "second_brain",
    "delete_note": "second_brain",
    # Desktop control
    "open_app": "desktop",
    "close_app": "desktop",
    "list_windows": "desktop",
    "focus_window": "desktop",
    "get_active_window": "desktop",
    "run_command": "desktop",
    "take_screenshot": "desktop",
    "search_apps": "desktop",
    "set_volume": "desktop",
    # MCP external tools
    "mcp_call": "mcp",
    "mcp_list_tools": "mcp",
    "mcp_servers": "mcp",
}


class ToolsManager:
    """
    Central tools manager for all agents.
    
    Usage:
        manager = ToolsManager()
        result = manager.execute("read_file", filepath="path/to/file.txt")
    """
    
    def __init__(self):
        # Register all available tools
        self.tools = {
            # File tools
            "read_file": ReadFileTool(),
            "write_file": WriteFileTool(),
            "append_file": AppendFileTool(),
            "list_dir": ListDirTool(),
            "delete_file": DeleteFileTool(),
            "file_search": FileSearchTool(),
            
            # Code tools
            "execute_code": ExecuteCodeTool(),
            "execute_shell": ExecuteShellTool(),
            
            # Web tools
            "web_search": WebSearchTool(),
            "fetch_webpage": FetchWebpageTool(),
            "parse_json": ParseJsonTool(),
            "get_weather": GetWeatherTool(),
            
            # Web Search Tools (API-based)
            "serpapi_search": SerpAPISearchTool(),
            "google_search": GoogleCustomSearchTool(),
            "duckduckgo_search": DuckDuckGoSearchTool(),
            "semantic_search": SemanticSearchTool(),
            
            # Memory tools
            "save_memory": SaveMemoryTool(),
            "load_memory": LoadMemoryTool(),
            "list_memory": ListMemoryTool(),
            
            # Data tools
            "process_json": JsonProcessTool(),
            "process_csv": CsvProcessTool(),
            "process_text": TextProcessTool(),
            
            # Vector Database tools
            "store_vector": StoreVectorTool(),
            "vector_search": SemanticSearchVectorTool(),
            "delete_vector": DeleteVectorTool(),
            "list_vectors": ListVectorsTool(),
            
            # Advanced Vector Database tools (with real embeddings)
            "store_vector_advanced": StoreVectorAdvancedTool(),
            "vector_search_advanced": SemanticSearchAdvancedTool(),
            "list_vectors_advanced": ListVectorsAdvancedTool(),
            # Email tools
            "send_email": SendEmailTool(),
            "list_emails": ListEmailsTool(),
            "get_email": GetEmailTool(),
            "search_emails": SearchEmailsTool(),
            # Todo tools
            "create_todo": CreateTodoTool(),
            "list_todos": ListTodosTool(),
            "complete_todo": CompleteTodoTool(),
            "update_todo": UpdateTodoTool(),
            "delete_todo": DeleteTodoTool(),
            "get_todo_stats": GetTodoStatsTool(),
            # Personal tools
            "save_daily_routine": SaveDailyRoutineTool(),
            "get_daily_routine": GetDailyRoutineTool(),
            # Second brain tools
            "save_note": SaveNoteTool(),
            "get_note": GetNoteTool(),
            "list_notes": ListNotesTool(),
            "search_notes": SearchNotesTool(),
            "get_note_graph": GetNoteGraphTool(),
            "delete_note": DeleteNoteTool(),
            # Desktop control tools (Windows, zero extra dependencies)
            **{t.name: t for t in ALL_DESKTOP_TOOLS},
            # MCP external tools
            "mcp_call": MCPCallTool(),
            "mcp_list_tools": MCPListToolsTool(),
            "mcp_servers": MCPServersTool(),
        }

    
    def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a tool by name.
        
        Args:
            tool_name: Name of the tool to execute
            **kwargs: Arguments to pass to the tool
            
        Returns:
            Result dict with success, result, and error keys
        """
        if tool_name not in self.tools:
            return {
                "success": False,
                "result": None,
                "error": f"Tool not found: {tool_name}. Available tools: {self.list_tools()}"
            }

        metadata = {
            "task_type": kwargs.pop("task_type", None),
            "agent_name": kwargs.pop("agent_name", None),
            "task_id": kwargs.pop("task_id", None),
        }
        safe_args = self._summarize_args(kwargs)
        service = SERVICE_MAP.get(tool_name)

        update_state("current_tool", tool_name)
        update_state("current_tool_arguments", safe_args)
        if service:
            update_state("current_external_service", service)

        self._emit_tool_started(tool_name, safe_args, metadata, service)
        tool = self.tools[tool_name]
        try:
            result = tool.execute(**kwargs)
        except Exception as exc:
            result = {
                "success": False,
                "result": None,
                "error": str(exc),
            }
        finally:
            self._emit_tool_event(tool_name, safe_args, result, metadata, service)
            record_tool_metrics(tool_name, result.get("success", False), service=service)
            update_state("current_tool", None)
            update_state("current_tool_arguments", None)
            update_state("current_external_service", None)

        return result

    def _emit_tool_started(self, tool_name: str, args: Dict[str, Any], metadata: Dict[str, Any], service: Optional[str]) -> None:
        try:
            event_stream.emit(
                "tool_started",
                {
                    "tool_name": tool_name,
                    "arguments": args,
                    "task_type": metadata.get("task_type"),
                    "agent_name": metadata.get("agent_name"),
                    "task_id": metadata.get("task_id"),
                },
                level="info",
            )
            if service:
                event_stream.emit(
                    "external_service_accessed",
                    {
                        "tool_name": tool_name,
                        "service": service,
                        "task_type": metadata.get("task_type"),
                        "agent_name": metadata.get("agent_name"),
                        "task_id": metadata.get("task_id"),
                    },
                    level="info",
                )
        except Exception:
            pass

    def _emit_tool_event(self, tool_name: str, args: Dict[str, Any], result: Dict[str, Any], metadata: Dict[str, Any], service: Optional[str]) -> None:
        try:
            event_stream.emit(
                "tool_executed",
                {
                    "tool_name": tool_name,
                    "arguments": args,
                    "success": result.get("success", False),
                    "result_summary": {
                        "result_type": type(result.get("result")).__name__,
                        "has_error": bool(result.get("error")),
                        "service": service,
                    },
                    "task_type": metadata.get("task_type"),
                    "agent_name": metadata.get("agent_name"),
                    "task_id": metadata.get("task_id"),
                },
                level="info" if result.get("success") else "error",
            )
        except Exception:
            pass

    def _summarize_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        summary = {}
        for key, value in args.items():
            if key.lower() in {"password", "api_key", "token", "authorization"}:
                summary[key] = "***"
            elif isinstance(value, str) and len(value) > 200:
                summary[key] = value[:200] + "..."
            else:
                summary[key] = value
        return summary
    
    def list_tools(self) -> list:
        """List all available tools"""
        return list(self.tools.keys())
    
    def get_tool_info(self, tool_name: str = None) -> Dict[str, Any]:
        """Get info about a tool or all tools"""
        if tool_name:
            if tool_name not in self.tools:
                return {"error": f"Tool not found: {tool_name}"}
            
            tool = self.tools[tool_name]
            return {
                "name": tool.name,
                "description": tool.description
            }
        
        # Return all tools info
        return {
            name: {
                "name": tool.name,
                "description": tool.description
            }
            for name, tool in self.tools.items()
        }
    
    def __getitem__(self, tool_name: str):
        """Allow dict-like access: manager["read_file"](filepath="...")"""
        if tool_name not in self.tools:
            raise KeyError(f"Tool not found: {tool_name}")
        return self.tools[tool_name]
