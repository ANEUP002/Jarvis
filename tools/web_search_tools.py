# =========================
# ENHANCED WEB SEARCH TOOLS
# =========================
# Integrates with SerpAPI, Google Custom Search, and DuckDuckGo

import os
import json
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from app.event_streaming import event_stream
from tools.base_tool import BaseTool

load_dotenv()

try:
    import requests
except ImportError:
    requests = None


def _build_session():
    session = requests.Session()
    disable_env_proxies = os.getenv("WEB_TOOLS_DISABLE_ENV_PROXIES", "true").lower() in ("1", "true", "yes")
    if disable_env_proxies:
        session.trust_env = False
    return session


class SerpAPISearchTool(BaseTool):
    """Search using SerpAPI (100 free searches/month)"""
    
    name = "serpapi_search"
    description = "Search the web using SerpAPI"
    
    def execute(self, query: str, num_results: int = 5, **kwargs) -> Dict[str, Any]:
        """
        Search using SerpAPI
        
        Requires: SERPAPI_API_KEY environment variable
        Free tier: 100 searches/month
        """
        if not requests:
            return {"success": False, "result": None, "error": "requests library not installed"}
        
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            return {
                "success": False,
                "result": None,
                "error": "SERPAPI_API_KEY not set. Get free key at https://serpapi.com"
            }
        
        try:
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "request_started",
                    "service": "serpapi",
                    "query": query,
                },
                level="info",
            )
            url = "https://serpapi.com/search"
            params = {
                "q": query,
                "num": num_results,
                "api_key": api_key
            }
            
            session = _build_session()
            response = session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract organic results
            results = []
            if "organic_results" in data:
                for result in data["organic_results"][:num_results]:
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("link", ""),
                        "snippet": result.get("snippet", ""),
                        "source": result.get("source", "")
                    })
            
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "request_completed",
                    "service": "serpapi",
                    "query": query,
                    "results_count": len(results),
                },
                level="info",
            )
            return {
                "success": True,
                "result": {
                    "query": query,
                    "results": results,
                    "total_results": data.get("search_information", {}).get("total_results", 0)
                },
                "error": None
            }
        
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "error": str(e),
                "hint": "Set SERPAPI_API_KEY in .env file"
            }


class GoogleCustomSearchTool(BaseTool):
    """Search using Google Custom Search API"""
    
    name = "google_search"
    description = "Search the web using Google Custom Search"
    
    def execute(self, query: str, num_results: int = 5, **kwargs) -> Dict[str, Any]:
        """
        Search using Google Custom Search
        
        Requires: GOOGLE_SEARCH_KEY and GOOGLE_SEARCH_ENGINE_ID
        Free tier: 100 searches/day
        """
        if not requests:
            return {"success": False, "result": None, "error": "requests library not installed"}
        
        api_key = os.getenv("GOOGLE_SEARCH_KEY")
        engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        
        if not api_key or not engine_id:
            return {
                "success": False,
                "result": None,
                "error": "GOOGLE_SEARCH_KEY or GOOGLE_SEARCH_ENGINE_ID not set"
            }
        
        try:
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "request_started",
                    "service": "google_custom_search",
                    "query": query,
                },
                level="info",
            )
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "q": query,
                "key": api_key,
                "cx": engine_id,
                "num": min(num_results, 10)
            }
            
            session = _build_session()
            response = session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract results
            results = []
            if "items" in data:
                for item in data["items"][:num_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                        "source": item.get("displayLink", "")
                    })
            
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "request_completed",
                    "service": "google_custom_search",
                    "query": query,
                    "results_count": len(results),
                },
                level="info",
            )
            return {
                "success": True,
                "result": {
                    "query": query,
                    "results": results,
                    "total_results": data.get("queries", {}).get("request", [{}])[0].get("totalResults", 0)
                },
                "error": None
            }
        
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "error": str(e)
            }


class DuckDuckGoSearchTool(BaseTool):
    """Search using DuckDuckGo (no API key required)"""
    
    name = "duckduckgo_search"
    description = "Search the web using DuckDuckGo (no API key needed)"
    
    def execute(self, query: str, num_results: int = 5, **kwargs) -> Dict[str, Any]:
        """
        Search using DuckDuckGo with duckduckgo_search library
        
        No API key required!
        Requires: duckduckgo-search package (pip install duckduckgo-search)
        """
        try:
            from ddgs import DDGS
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "request_started",
                    "service": "duckduckgo",
                    "query": query,
                },
                level="info",
            )
            
            results = []
            with DDGS(timeout=10) as ddgs:
                search_results = ddgs.text(query, max_results=num_results)
                for result in search_results:
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("href", ""),
                        "snippet": result.get("body", ""),
                        "source": result.get("source", "")
                    })
            
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "request_completed",
                    "service": "duckduckgo",
                    "query": query,
                    "results_count": len(results),
                },
                level="info",
            )
            return {
                "success": True,
                "result": {
                    "query": query,
                    "results": results,
                    "count": len(results)
                },
                "error": None
            }
        
        except ImportError:
            return {
                "success": False,
                "result": None,
                "error": "ddgs not installed. Install with: pip install ddgs",
                "hint": "This tool requires the ddgs package"
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "error": str(e)
            }


class SemanticSearchTool(BaseTool):
    """Search knowledge base using semantic similarity (for local memory)"""
    
    name = "semantic_search"
    description = "Search memory/knowledge base using semantic similarity"
    
    def execute(self, query: str, memory_dir: str = "memory", num_results: int = 5, **kwargs) -> Dict[str, Any]:
        """
        Search saved memory items using simple keyword matching
        (Full semantic search requires vector database)
        """
        try:
            from pathlib import Path
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "local_search_started",
                    "query": query,
                    "memory_dir": memory_dir,
                },
                level="info",
            )
            
            memory_path = Path(memory_dir)
            if not memory_path.exists():
                return {"success": True, "result": {"query": query, "results": []}, "error": None}
            
            query_lower = query.lower().split()
            results = []
            
            # Simple keyword matching (TODO: upgrade to vector DB for true semantic search)
            for json_file in memory_path.glob("*.json"):
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    content = str(data).lower()
                    
                    # Count keyword matches
                    matches = sum(1 for word in query_lower if word in content)
                    
                    if matches > 0:
                        results.append({
                            "key": json_file.stem,
                            "relevance": matches / len(query_lower),
                            "data": data.get("data", data)
                        })
            
            # Sort by relevance
            results.sort(key=lambda x: x["relevance"], reverse=True)
            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "local_search_completed",
                    "query": query,
                    "results_count": len(results[:num_results]),
                },
                level="info",
            )
            
            return {
                "success": True,
                "result": {
                    "query": query,
                    "results": results[:num_results],
                    "count": len(results)
                },
                "error": None
            }
        
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "error": str(e)
            }
