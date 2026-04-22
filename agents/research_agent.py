from providers.llm_provider import generate
from tools import ToolsManager
import hashlib
from agents.note_workflows import attach_memory_metadata, load_memory_bundle
from tools.notes_tools import save_research_note
from app.intents import is_weather_query

_LIVE_SIGNALS = {
    "latest", "today", "now", "current", "currently", "news", "price", "prices",
    "score", "scores", "stock", "stocks", "happening", "recently", "recent",
    "trending", "live", "2025", "2026", "update", "updates", "breaking",
    "announced", "release", "released", "development", "developments",
}

_NEWS_SIGNALS = {
    "world", "news", "happening", "going on", "latest", "breaking",
    "today", "current events", "headlines",
}


def _needs_live_data(query: str) -> bool:
    lower = query.lower()
    words = set(lower.split())
    return bool(words & _LIVE_SIGNALS)


def _is_news_query(query: str) -> bool:
    lower = query.lower()
    return any(sig in lower for sig in _NEWS_SIGNALS)


def _web_search(query: str, max_results: int = 5) -> str:
    try:
        from ddgs import DDGS
        print(f"[LIVE SEARCH] query={query!r}")
        if _is_news_query(query):
            results = list(DDGS().news(query, max_results=max_results))
            if results:
                lines = [f"- [{r.get('date','')[:10]}] {r['title']}: {r['body']}" for r in results]
                print(f"[LIVE SEARCH] got {len(results)} news results")
                return "Live news results (today):\n" + "\n".join(lines)
        # General web search fallback
        results = list(DDGS().text(query, max_results=max_results))
        if not results:
            return ""
        lines = [f"- {r['title']}: {r['body']}" for r in results]
        print(f"[LIVE SEARCH] got {len(results)} web results")
        return "Live web search results:\n" + "\n".join(lines)
    except Exception as exc:
        print(f"[LIVE SEARCH ERROR] {exc}")
        return ""


def run(task: dict, model: str = "openrouter/gpt-4o-mini") -> dict:
    """
    Research agent with memory and knowledge base capabilities.
    
    Args:
        task: Task dict with "input" key (optionally "memory_key" and "search_memory")
        model: LLM model to use (default: OpenRouter GPT-4o-mini)
        
    Returns:
        Response dict with research findings and memory status
    """
    manager = ToolsManager()
    input_text = task.get("input", "") if isinstance(task, dict) else task
    memory_key = task.get("memory_key", None) if isinstance(task, dict) else None
    search_memory = task.get("search_memory", False) if isinstance(task, dict) else False

    # Use the raw query (not the conversation-enriched input) for intent detection.
    # input_text may contain previous turns that mention weather — that must not
    # accidentally trigger the weather tool on unrelated requests.
    _raw_query = task.get("search_query") or input_text
    if "[CURRENT REQUEST]" in _raw_query:
        _raw_query = _raw_query.split("[CURRENT REQUEST]")[-1].strip()

    if is_weather_query(_raw_query):
        weather_result = manager.execute(
            "get_weather",
            query=_raw_query,
            task_type="research",
            agent_name="research",
            task_id=task.get("task_id") if isinstance(task, dict) else None,
        )

        if weather_result.get("success"):
            weather_data = weather_result.get("result", {})
            output = weather_data.get("summary") or str(weather_data)
            return {
                "response": output,
                "memory_load": None,
                "memory_save": None,
                "llm": {
                    "model_used": "tool:get_weather",
                    "fallback_used": False,
                },
                "tool_result": weather_data,
            }

        return {
            "response": f"I could not fetch weather right now: {weather_result.get('error', 'unknown error')}",
            "memory_load": None,
            "memory_save": None,
            "llm": {
                "model_used": "tool:get_weather",
                "fallback_used": False,
            },
            "tool_error": weather_result.get("error"),
        }
    
    # Try to load from memory if requested
    memory_context = ""
    memory_result = None
    if search_memory and memory_key:
        try:
            load_result = manager.execute(
                "load_memory",
                key=memory_key,
                task_type="research",
                agent_name="research",
                task_id=task.get("task_id") if isinstance(task, dict) else None,
            )
            if load_result["success"]:
                memory_context = f"\n\nPrevious findings on this topic:\n{str(load_result['result'])}"
                memory_result = {
                    "status": "loaded",
                    "key": memory_key
                }
        except Exception:
            pass

    complexity = task.get("complexity", "simple") if isinstance(task, dict) else "simple"

    # Skip expensive embedding search for simple queries
    if complexity == "simple":
        note_context, notes_result = "", {"notes": []}
    else:
        note_context, notes_result = load_memory_bundle(task, agent_name="research")

    web_context = ""
    _live = _needs_live_data(_raw_query)
    print(f"[LIVE SEARCH] needs_live={_live} | query={_raw_query!r}")
    if _live:
        web_context = _web_search(_raw_query)

    from app.learning import load_profile
    _pref = load_profile().get("preferences", {}).get("answer_length", "auto")
    if _pref == "short" or complexity == "simple":
        length_hint = "Answer in 1-3 sentences. Be direct and conversational — no bullet points, no headers."
    elif _pref == "detailed":
        length_hint = "Be thorough and detailed. Cover the topic well."
    else:
        length_hint = "Be concise but thorough. Use bullet points when listing multiple items."

    _live_block = (
        f"{web_context}\n\nIMPORTANT: Use ONLY the live results above to answer. "
        "Cite specific headlines or dates from them. Do not use training data for current events."
        if web_context else ""
    )

    from app.learning import get_user_context
    _user_ctx = get_user_context()

    prompt = f"""
You are JARVIS, a personal AI assistant. Respond naturally and helpfully.
{_user_ctx}
{_live_block}

Guidelines:
- {length_hint}
- No markdown — no headers (##), no bold (**), no bullet points (-), no code blocks
- Do not repeat the question back
- Do not say "Based on..." or "Certainly!" — just answer
- {"Do not hallucinate unknown facts." if not web_context else "Answer strictly from the live results provided."}
{memory_context}
{note_context}

Question: {input_text}
""".strip()

    llm_result = generate(prompt, model=model, return_metadata=True)
    output = llm_result["content"]

    # Save findings to memory if key provided
    save_result = None
    if memory_key:
        try:
            findings = {
                "query": input_text,
                "findings": output,
                "model": llm_result.get("model_used", model)
            }
            save_result = manager.execute(
                "save_memory",
                key=memory_key,
                data=findings,
                task_type="research",
                agent_name="research",
                task_id=task.get("task_id") if isinstance(task, dict) else None,
            )
            save_result = {
                "status": "success" if save_result["success"] else "error",
                "key": memory_key,
                "error": save_result.get("error")
            }
        except Exception as e:
            save_result = {
                "status": "error",
                "key": memory_key,
                "error": str(e)
            }

    import threading as _threading
    _threading.Thread(
        target=save_research_note,
        args=(task if isinstance(task, dict) else {"input": input_text}, output),
        daemon=True,
    ).start()
    second_brain = {"research_note": None}

    return attach_memory_metadata({
        "response": output,
        "memory_load": memory_result,
        "memory_save": save_result,
        "llm": llm_result,
    }, notes_result, second_brain)
