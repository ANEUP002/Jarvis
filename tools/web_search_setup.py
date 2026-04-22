#!/usr/bin/env python
# =========================
# WEB SEARCH SETUP & CONFIGURATION
# =========================
# Check and configure web search API keys

import os
from dotenv import load_dotenv

load_dotenv()


def check_web_search_apis():
    """Check which web search APIs are available"""
    print("\n" + "="*70)
    print("WEB SEARCH API CONFIGURATION")
    print("="*70)
    
    apis = {
        "DuckDuckGo": {
            "key": None,
            "status": "✅ Ready (No API key needed)",
            "requires_key": False,
            "tool": "duckduckgo_search",
            "limit": "Unlimited (rate limited)"
        },
        "SerpAPI": {
            "key": os.getenv("SERPAPI_API_KEY"),
            "status": None,
            "requires_key": True,
            "tool": "serpapi_search",
            "limit": "100 searches/month (free)"
        },
        "Google Custom Search": {
            "key_id": os.getenv("GOOGLE_SEARCH_ENGINE_ID"),
            "key_api": os.getenv("GOOGLE_SEARCH_KEY"),
            "status": None,
            "requires_key": True,
            "tool": "google_search",
            "limit": "100 searches/day (free)"
        },
        "Semantic Search": {
            "key": None,
            "status": "✅ Ready (Local memory search)",
            "requires_key": False,
            "tool": "semantic_search",
            "limit": "Unlimited"
        }
    }
    
    print("\n📋 Available Search APIs:\n")
    
    for api_name, config in apis.items():
        if api_name == "Google Custom Search":
            has_key = config["key_id"] and config["key_api"]
        else:
            has_key = config.get("key") is not None
        
        if not config.get("requires_key"):
            status = config.get("status", "✅ Ready")
        elif has_key:
            status = "✅ Configured"
        else:
            status = "⚠️  Not configured"
        
        print(f"{api_name:25} {status:20} Limit: {config['limit']}")
    
    print("\n" + "="*70)
    print("SETUP INSTRUCTIONS")
    print("="*70)
    
    print("""
For FREE web search:
  ✅ DuckDuckGo: Already working! No setup needed
  ✅ Semantic Search: Already working! (searches local KB)

For API-based search (optional upgrades):
  
  📌 SerpAPI (100 free searches/month):
     1. Sign up at https://serpapi.com
     2. Get your API key
     3. Add to .env: SERPAPI_API_KEY="your_key_here"
     
  📌 Google Custom Search (100 free searches/day):
     1. Create a search engine at https://programmablesearchengine.google.com
     2. Get your Search Engine ID (cx) and API key
     3. Add to .env:
        GOOGLE_SEARCH_ENGINE_ID="your_cx_here"
        GOOGLE_SEARCH_KEY="your_key_here"

Current Configuration:
""")
    
    # Show current configuration
    serpapi = os.getenv("SERPAPI_API_KEY")
    google_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
    google_key = os.getenv("GOOGLE_SEARCH_KEY")
    
    print(f"  SerpAPI Key:            {'✅ Set' if serpapi else '❌ Not set'}")
    print(f"  Google Search Engine ID: {'✅ Set' if google_id else '❌ Not set'}")
    print(f"  Google Search API Key:   {'✅ Set' if google_key else '❌ Not set'}")
    
    print("\n" + "="*70 + "\n")
    
    return {
        "duckduckgo": True,
        "serpapi": bool(serpapi),
        "google": bool(google_id and google_key),
        "semantic": True
    }


if __name__ == "__main__":
    check_web_search_apis()
