from providers.llm_provider import generate
from tools import ToolsManager
from agents.note_workflows import attach_memory_metadata, load_memory_bundle
from tools.notes_tools import save_file_output_note


def run(task: dict, model: str = "openrouter/qwen/qwen-2.5-coder-32b-instruct:free") -> dict:
    """
    Code generation agent with execution and file I/O capabilities.
    
    Args:
        task: Task dict with "input" key
        model: LLM model to use (default: OpenRouter Qwen Coder 32B)
        
    Returns:
        Response dict with code, explanation, and execution results
    """
    manager = ToolsManager()
    input_text = task.get("input", "") if isinstance(task, dict) else task
    complexity = task.get("complexity", "simple") if isinstance(task, dict) else "simple"
    if complexity == "simple":
        note_context, notes_result = "", {"notes": []}
    else:
        note_context, notes_result = load_memory_bundle(task, agent_name="code")

    prompt = f"""
You are JARVIS, a personal AI assistant specialized in code.

Guidelines:
- If writing code: use a single code block, then one short plain-text explanation (no headers, no extra markdown outside the code block)
- If explaining code or answering a coding question: plain text only, no markdown headers or bold
- Do not hallucinate libraries or functions
- Be concise — skip filler phrases like "Certainly!" or "Here's the code:"
{note_context}

Task:
{input_text}
""".strip()

    llm_result = generate(prompt, model=model, return_metadata=True)
    response = llm_result["content"]

    # Try to execute the code if it looks like Python
    execution_result = None
    try:
        if "```python" in response or "import " in response:
            # Extract code block if present
            code = response
            if "```python" in response:
                code = response.split("```python")[1].split("```")[0].strip()
            
            exec_result = manager.execute(
                "execute_code",
                code=code,
                timeout=10,
                task_type="code",
                agent_name="code",
                task_id=task.get("task_id") if isinstance(task, dict) else None,
            )
            
            if exec_result["success"]:
                execution_result = {
                    "status": "success",
                    "output": exec_result["result"]
                }
            else:
                execution_result = {
                    "status": "error",
                    "error": exec_result["error"]
                }
    except Exception as e:
        execution_result = {
            "status": "error",
            "error": str(e)
        }

    second_brain = {
        "code_note": save_file_output_note(
            task if isinstance(task, dict) else {"input": input_text},
            {
                "status": "success",
                "filepath": "inline://generated-code",
            },
            response,
        ),
    }

    return attach_memory_metadata({
        "response": response,
        "execution": execution_result,
        "llm": llm_result,
    }, notes_result, second_brain)
