# =========================
# WEB & SEARCH TOOLS
# =========================

import os
from typing import Any, Dict

from app.event_streaming import event_stream
from tools.base_tool import BaseTool


class WebSearchTool(BaseTool):
    """Search the web (simulated for now)"""
    
    name = "web_search"
    description = "Search the web for information"
    
    def execute(self, query: str, max_results: int = 5, **kwargs) -> Dict[str, Any]:
        try:
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "search_started",
                    "query": query,
                    "max_results": max_results,
                },
                level="info",
            )
            # This is a placeholder - in production, integrate with a real search API
            # Options: SerpAPI, Google Custom Search, Bing, DuckDuckGo
            
            return {
                "success": True,
                "result": {
                    "query": query,
                    "results": [],
                    "note": "Web search requires API integration (SerpAPI, Google Custom Search, etc.)"
                },
                "error": None,
                "max_results": max_results
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class FetchWebpageTool(BaseTool):
    """Fetch and parse webpage content"""
    
    name = "fetch_webpage"
    description = "Fetch content from a URL"
    
    def execute(self, url: str, timeout: int = 10, **kwargs) -> Dict[str, Any]:
        try:
            import requests
            import urllib3

            disable_env_proxies = os.getenv("WEB_TOOLS_DISABLE_ENV_PROXIES", "true").lower() in ("1", "true", "yes")
            session = requests.Session()
            if disable_env_proxies:
                session.trust_env = False
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "fetch_started",
                    "url": url,
                    "timeout": timeout,
                },
                level="info",
            )
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            verify_ssl = os.getenv("WEB_TOOLS_VERIFY_SSL", "true").lower() in ("1", "true", "yes")
            try:
                response = session.get(url, headers=headers, timeout=timeout, verify=verify_ssl)
            except requests.exceptions.SSLError:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                event_stream.emit(
                    "tool_progress",
                    {
                        "tool_name": self.name,
                        "stage": "ssl_retry_without_verification",
                        "url": url,
                    },
                    level="warning",
                )
                response = session.get(url, headers=headers, timeout=timeout, verify=False)
            response.raise_for_status()
            content = response.text
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "fetch_completed",
                    "url": url,
                    "content_length": len(content),
                },
                level="info",
            )
            
            return {
                "success": True,
                "result": content[:5000],  # Limit to first 5000 chars
                "error": None,
                "url": url,
                "content_length": len(content)
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}


class ParseJsonTool(BaseTool):
    """Parse JSON data"""
    
    name = "parse_json"
    description = "Parse and validate JSON data"
    
    def execute(self, data: str, **kwargs) -> Dict[str, Any]:
        try:
            import json
            parsed = json.loads(data)
            
            return {
                "success": True,
                "result": parsed,
                "error": None
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}
