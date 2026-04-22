"""
MCP (Model Context Protocol) Client for JARVIS
Connects to any external MCP server via stdio transport (JSON-RPC 2.0).

Config file: mcp_servers.json in the project root.

Usage:
    from tools.mcp_client import mcp_registry
    mcp_registry.load()          # connect to all configured servers
    mcp_registry.call("tool_name", {"arg": "value"})
"""

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.base_tool import BaseTool

MCP_CONFIG_FILE = Path(__file__).parent.parent / "mcp_servers.json"


# ── MCP Stdio Client ──────────────────────────────────────────────────────────

class MCPStdioClient:
    """
    Connects to one MCP server process via stdin/stdout (JSON-RPC 2.0).
    Thread-safe: uses a lock around every request/response pair.
    """

    def __init__(self, name: str, command: List[str], env: Dict[str, str] = None):
        self.name = name
        self.command = command
        self.env = env or {}
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._id = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> bool:
        try:
            merged_env = {**os.environ, **self.env}
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                env=merged_env,
            )
            # MCP initialize handshake
            self._rpc("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "jarvis", "version": "2.0"},
            })
            self._notify("notifications/initialized", {})
            return True
        except Exception as exc:
            print(f"[MCP:{self.name}] Failed to start: {exc}")
            return False

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    # ── Public API ────────────────────────────────────────────────────────────

    def list_tools(self) -> List[Dict]:
        try:
            result = self._rpc("tools/list", {})
            return result.get("tools", [])
        except Exception as exc:
            print(f"[MCP:{self.name}] list_tools error: {exc}")
            return []

    def call_tool(self, tool_name: str, arguments: Dict) -> Dict[str, Any]:
        result = self._rpc("tools/call", {"name": tool_name, "arguments": arguments})
        # MCP returns a content array of typed blocks
        content = result.get("content", [])
        text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return {
            "output": "\n".join(text_parts),
            "is_error": result.get("isError", False),
            "raw": result,
        }

    # ── Transport ─────────────────────────────────────────────────────────────

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _send(self, data: Dict) -> None:
        if not self.process or self.process.stdin.closed:
            raise RuntimeError(f"MCP server '{self.name}' is not running")
        self.process.stdin.write(json.dumps(data, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def _recv(self) -> Dict:
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(f"MCP server '{self.name}' closed its stdout")
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            # Notifications have no "id" — skip them
            if "id" in data:
                return data

    def _rpc(self, method: str, params: Dict) -> Dict:
        with self._lock:
            mid = self._next_id()
            self._send({"jsonrpc": "2.0", "id": mid, "method": method, "params": params})
            response = self._recv()
            if "error" in response:
                raise RuntimeError(f"MCP error from '{self.name}': {response['error']}")
            return response.get("result", {})

    def _notify(self, method: str, params: Dict) -> None:
        with self._lock:
            self._send({"jsonrpc": "2.0", "method": method, "params": params})


# ── MCP Registry ──────────────────────────────────────────────────────────────

class MCPRegistry:
    """
    Reads mcp_servers.json, starts each configured server, and indexes their tools.
    Lazy-loaded on first use — call .load() explicitly or it auto-loads on first call.
    """

    def __init__(self, config_path: Path = MCP_CONFIG_FILE):
        self.config_path = config_path
        self.clients: Dict[str, MCPStdioClient] = {}
        # tool_name → (server_name, tool_schema_dict)
        self.tool_index: Dict[str, Tuple[str, Dict]] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        if not self.config_path.exists():
            return

        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[MCP] Cannot read config: {exc}")
            return

        for name, server_cfg in config.get("servers", {}).items():
            if server_cfg.get("disabled", False):
                continue
            client = MCPStdioClient(
                name=name,
                command=server_cfg["command"],
                env=server_cfg.get("env", {}),
            )
            if client.start():
                tools = client.list_tools()
                self.clients[name] = client
                for tool in tools:
                    self.tool_index[tool["name"]] = (name, tool)
                print(f"[MCP] {name} connected — {len(tools)} tools: {[t['name'] for t in tools]}")

    def call(self, tool_name: str, arguments: Dict) -> Dict[str, Any]:
        self.load()
        if tool_name not in self.tool_index:
            available = list(self.tool_index.keys())
            raise ValueError(f"MCP tool '{tool_name}' not found. Available: {available}")
        server_name, _ = self.tool_index[tool_name]
        client = self.clients[server_name]
        if not client.alive():
            raise RuntimeError(f"MCP server '{server_name}' is no longer running")
        return client.call_tool(tool_name, arguments)

    def all_tools(self) -> List[Dict]:
        self.load()
        return [schema for _, schema in self.tool_index.values()]

    def servers_info(self) -> List[Dict]:
        self.load()
        return [
            {
                "name": name,
                "alive": client.alive(),
                "tools": [t for t_name, (s, t) in self.tool_index.items() if s == name],
            }
            for name, client in self.clients.items()
        ]

    def shutdown(self) -> None:
        for client in self.clients.values():
            client.stop()
        self.clients.clear()
        self.tool_index.clear()
        self._loaded = False


# Module-level singleton — shared across all agents and tools
mcp_registry = MCPRegistry()


# ── JARVIS Tool Wrappers ──────────────────────────────────────────────────────

class MCPCallTool(BaseTool):
    name = "mcp_call"
    description = "Call a tool from any connected MCP server by name with arguments as a JSON dict"

    def execute(self, tool_name: str, arguments: Dict = None, **kwargs) -> Dict[str, Any]:
        try:
            result = mcp_registry.call(tool_name, arguments or {})
            return {"success": not result.get("is_error"), "result": result, "error": None}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class MCPListToolsTool(BaseTool):
    name = "mcp_list_tools"
    description = "List all tools available from every connected MCP server"

    def execute(self, **kwargs) -> Dict[str, Any]:
        try:
            mcp_registry.load()
            return {
                "success": True,
                "result": {
                    "servers": mcp_registry.servers_info(),
                    "tools": mcp_registry.all_tools(),
                    "count": len(mcp_registry.tool_index),
                },
                "error": None,
            }
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class MCPServersTool(BaseTool):
    name = "mcp_servers"
    description = "List all configured MCP servers and their connection status"

    def execute(self, **kwargs) -> Dict[str, Any]:
        try:
            mcp_registry.load()
            return {
                "success": True,
                "result": {"servers": mcp_registry.servers_info()},
                "error": None,
            }
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}
