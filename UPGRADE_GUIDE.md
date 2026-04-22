# UPGRADE GUIDE: Real Embeddings & Web Search API Integration

## Overview

This upgrade adds production-ready features to OfficeOS:

1. **Advanced Vector Database** - Real embeddings from OpenAI, Google, or Hugging Face
2. **Web Search API Integration** - SerpAPI, Google Custom Search, DuckDuckGo
3. **Automatic Fallbacks** - Graceful degradation when APIs unavailable

---

## Part 1: Vector Database Upgrade

### Current Status
- ✅ TF-IDF fallback (always available)
- ⚠️ Real embeddings (optional, requires dependencies)

### Architecture

```
vector_db_advanced/
├── metadata.json        # Document metadata + embeddings provider
└── embeddings.json      # Actual embedding vectors [1536, 768, or 384 dims]
```

### Supported Providers

#### 1. Hugging Face (FREE - Recommended for local development)
- **Model**: sentence-transformers/all-MiniLM-L6-v2
- **Dimension**: 384
- **Speed**: Fast (local, no API calls)
- **Cost**: FREE

**Installation**:
```bash
pip install sentence-transformers
```

**Usage**:
```python
manager.execute("store_vector_advanced", 
               key="doc1",
               text="Your text here",
               embedding_provider="huggingface")
```

#### 2. OpenAI (PAID - Best quality)
- **Model**: text-embedding-3-small
- **Dimension**: 1536
- **Speed**: ~1ms per request
- **Cost**: ~$0.02 per 1M tokens

**Installation**:
```bash
pip install openai
```

**Configuration in .env**:
```
OPENAI_API_KEY="sk-..."
```

**Usage**:
```python
manager.execute("store_vector_advanced", 
               key="doc1",
               text="Your text here",
               embedding_provider="openai")
```

#### 3. Google PaLM (FREE tier - Balanced)
- **Model**: models/embedding-001
- **Dimension**: 768
- **Speed**: ~500ms per request
- **Cost**: FREE (with quota limits)

**Installation**:
```bash
pip install google-generativeai
```

**Configuration in .env**:
```
GOOGLE_AI_API_KEY="AIza..."  # Already set from existing config
```

**Usage**:
```python
manager.execute("store_vector_advanced", 
               key="doc1",
               text="Your text here",
               embedding_provider="google")
```

### API Reference

#### Store Vector (with real embeddings)
```python
from tools import ToolsManager

manager = ToolsManager()

# Store with Hugging Face (local)
result = manager.execute(
    "store_vector_advanced",
    key="document_id",
    text="Your document text here",
    metadata={"source": "web", "date": "2026-04-10"},
    embedding_provider="huggingface"  # or "openai", "google"
)

# Result format
{
    "success": True,
    "result": {
        "key": "document_id",
        "stored": True,
        "provider": "huggingface"
    }
}
```

#### Search Vectors (with real embeddings)
```python
result = manager.execute(
    "vector_search_advanced",
    query="your search query",
    top_k=5,
    db_dir="vector_db_advanced",
    embedding_provider="huggingface",
    min_similarity=0.3  # Optional: filter by relevance
)

# Result format
{
    "success": True,
    "result": {
        "query": "your search query",
        "embedding_provider": "huggingface",
        "results": [
            {
                "key": "doc1",
                "similarity": 0.95,
                "text_preview": "..."
            }
        ],
        "count": 1
    }
}
```

#### List Vectors
```python
result = manager.execute(
    "list_vectors_advanced",
    embedding_provider="huggingface"
)

# Shows all stored vectors with metadata
```

### Fallback Behavior
If embedding provider fails or is unavailable:
1. System falls back to TF-IDF embeddings
2. Same interface, transparent to user
3. Still works, just lower quality

---

## Part 2: Web Search API Integration

### Current Status
- ✅ DuckDuckGo (FREE, no API key)
- ⚠️ SerpAPI (free tier available)
- ⚠️ Google Custom Search (free tier available)
- ✅ Semantic local search (on saved KB)

### Available Search Tools

#### 1. DuckDuckGo (Always Available)
- **No API key required**
- **Free**: Unlimited (rate limited)
- **Speed**: Fast
- **Coverage**: Decent

**Usage**:
```python
result = manager.execute(
    "duckduckgo_search",
    query="Python programming",
    num_results=5
)
```

**Installation** (optional, for better results):
```bash
pip install duckduckgo-search
```

#### 2. SerpAPI (100 free searches/month)
- **Free searches**: 100/month
- **Paid**: $0.01 per additional search
- **Quality**: Excellent
- **Speed**: Fast

**Sign Up**:
1. Go to https://serpapi.com
2. Create account (free)
3. Get API key

**Configuration in .env**:
```
SERPAPI_API_KEY="your_api_key_here"
```

**Usage**:
```python
result = manager.execute(
    "serpapi_search",
    query="Python programming",
    num_results=5
)
```

#### 3. Google Custom Search (100 free searches/day)
- **Free searches**: 100/day
- **Setup required**: Create custom search engine
- **Quality**: Best
- **Limitations**: Need to configure search engine

**Sign Up**:
1. Go to https://programmablesearchengine.google.com
2. Create a search engine (restrict to specific sites or web-wide)
3. Get Search Engine ID (cx parameter)
4. Get API key from Google Cloud Console

**Configuration in .env**:
```
GOOGLE_SEARCH_ENGINE_ID="your_cx_here"
GOOGLE_SEARCH_KEY="your_api_key_here"
```

**Usage**:
```python
result = manager.execute(
    "google_search",
    query="Python programming",
    num_results=5
)
```

#### 4. Semantic Search (Local Knowledge Base)
- **Free**: Unlimited
- **No API key**: Required
- **Speed**: Very fast
- **Index**: Your saved memory

**Usage**:
```python
result = manager.execute(
    "semantic_search",
    query="previously researched topic",
    num_results=5,
    memory_dir="memory"
)
```

### Configuration Checklist

- [ ] DuckDuckGo (works out of box)
- [ ] SerpAPI (optional):
  - [ ] Sign up at serpapi.com
  - [ ] Get API key
  - [ ] Add to .env: `SERPAPI_API_KEY="..."`
- [ ] Google Custom Search (optional):
  - [ ] Create search engine at programmablesearchengine.google.com
  - [ ] Get Search Engine ID (cx)
  - [ ] Get API key from Google Cloud
  - [ ] Add to .env: `GOOGLE_SEARCH_ENGINE_ID="..."` and `GOOGLE_SEARCH_KEY="..."`

### API Response Format

```python
{
    "success": True,
    "result": {
        "query": "Python programming",
        "results": [
            {
                "title": "Python Official Website",
                "url": "https://www.python.org",
                "snippet": "Official Python website with...",
                "source": "python.org"
            }
        ],
        "total_results": 1000000
    }
}
```

---

## Integration with Agents

### Code Agent with Embeddings
```python
from tools import ToolsManager

def run(task: dict, model: str = "groq/llama3-8b") -> dict:
    manager = ToolsManager()
    
    # Generate code
    code = generate(task["input"], model=model)
    
    # Store embeddings for future search
    manager.execute(
        "store_vector_advanced",
        key=f"code_{task['id']}",
        text=code,
        embedding_provider="huggingface"
    )
    
    return {"response": code}
```

### Research Agent with Web Search
```python
def run(task: dict, model: str = "groq/mixtral") -> dict:
    manager = ToolsManager()
    
    # Search the web
    search_results = manager.execute(
        "duckduckgo_search",
        query=task["input"],
        num_results=5
    )
    
    # Store findings
    manager.execute(
        "save_memory",
        key=f"research_{task['id']}",
        data=search_results["result"]
    )
    
    return {"response": "Research completed"}
```

---

## Performance Optimization

### Caching
- Embeddings cached to disk after generation
- No re-computation on repeated searches
- Metadata cached alongside embeddings

### Parallelization
- Multiple documents can be embedded in parallel
- Batch operations supported by all providers

### Cost Optimization
```
Monthly Cost Estimates:

Free:
- Hugging Face embeddings: $0
- DuckDuckGo search: $0
- Semantic search: $0
- Total: $0/month

Budget-Friendly ($1-5/month):
- HuggingFace + SerpAPI 100/month: ~$1
- HuggingFace + Google Search 100/day: $0 (limited)
- Total: ~$0-1/month

Premium ($10-50/month):
- OpenAI embeddings + SerpAPI: ~$5
- OpenAI embeddings + Google Search: $0-5
- Total: ~$5-10/month

Enterprise (flexible):
- OpenAI embeddings + SerpAPI + Google: customizable
```

---

## Troubleshooting

### Embeddings not working
```
⚠️ Hugging Face embeddings unavailable: sentence-transformers required
Solution: pip install sentence-transformers
```

```
⚠️ OpenAI embeddings unavailable: OPENAI_API_KEY not found in .env
Solution: Add OPENAI_API_KEY to .env and restart
```

### Web search failing
Check configuration with:
```bash
python tools/web_search_setup.py
```

Shows which APIs are configured and ready.

### Slow embeddings
- Use Hugging Face (local) instead of OpenAI (API)
- Or batch documents together
- Embeddings are cached, second search is instant

### Storage space
- Embeddings database: ~500KB per 1000 documents (Hugging Face 384-dim)
- ~1.5MB per 1000 documents (OpenAI 1536-dim)

---

## File Changes Summary

**New Files**:
- `tools/embeddings.py` - Embedding providers
- `tools/vector_db_advanced.py` - Advanced vector database
- `tools/web_search_setup.py` - Web search configuration helper
- `test_upgraded_embeddings.py` - Comprehensive test

**Modified Files**:
- `.env` - Added web search and embedding API key placeholders
- `tools/manager.py` - Registered new advanced vector tools
- `tools/web_search_tools.py` - Added dotenv loading

---

## Next Steps

1. **Choose an embedding provider**:
   - Local: `pip install sentence-transformers` (Hugging Face)
   - Cloud: Set `OPENAI_API_KEY` (OpenAI)

2. **Configure web search (optional)**:
   - Add `SERPAPI_API_KEY` or Google Custom Search keys to `.env`

3. **Test the upgrades**:
   ```bash
   python test_upgraded_embeddings.py
   ```

4. **Integrate into agents**:
   - Use `manager.execute("store_vector_advanced", ...)` in code/research agents
   - Use `manager.execute("duckduckgo_search", ...)` for web search

---

## Support & Documentation

- Test file: `test_upgraded_embeddings.py`
- Configuration checker: `python tools/web_search_setup.py`
- Tool docs: `tools/TOOLS.md`
