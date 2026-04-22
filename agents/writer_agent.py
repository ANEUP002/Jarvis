import os
import re
from pathlib import Path
from providers.llm_provider import generate
from tools import ToolsManager
from agents.note_workflows import attach_memory_metadata, load_memory_bundle
from tools.notes_tools import save_email_note, save_file_output_note


WRITER_OUTPUT_DIR = Path(__file__).parent.parent / "memory" / "writings"
WRITER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _is_email_task(text: str) -> bool:
    lower = text.lower()
    return "send email" in lower or "write email" in lower or "email to" in lower or "compose email" in lower


def _extract_email_details(text: str) -> dict:
    lower = text.lower()
    email_matches = re.findall(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, flags=re.IGNORECASE)
    subject_match = re.search(r"subject:?\s*([^\n]+)", text, flags=re.IGNORECASE)

    recipients = []
    if email_matches:
        seen = set()
        for addr in email_matches:
            normalized = addr.strip()
            lower_addr = normalized.lower()
            if lower_addr not in seen:
                seen.add(lower_addr)
                recipients.append(normalized)

    subject = subject_match.group(1).strip() if subject_match else None
    if not subject and "meeting" in lower:
        subject = "Request for design review meeting"

    return {
        "to": recipients,
        "subject": subject,
    }


def _infer_email_subject(body: str) -> str | None:
    if not body:
        return None
    subject_match = re.search(r"^subject:\s*(.+)$", body, flags=re.IGNORECASE | re.MULTILINE)
    if subject_match:
        return subject_match.group(1).strip()
    return None


def _slugify_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s_-]", "", value or "").strip().lower()
    cleaned = re.sub(r"[\s_-]+", "-", cleaned)
    return cleaned or "writer-output"


def _default_output_file(task: dict | str, response: str) -> str:
    if isinstance(task, dict):
        task_id = task.get("task_id")
        input_text = task.get("input", "")
    else:
        task_id = None
        input_text = str(task)

    title_seed = input_text[:80] if input_text else response[:80]
    slug = _slugify_filename(title_seed)
    suffix = task_id or "manual"
    return str(WRITER_OUTPUT_DIR / f"{slug}-{suffix}.md")


def run(task: dict, model: str = "openrouter/gpt-4o-mini") -> dict:
    """
    Professional writing agent with file I/O capabilities.
    
    Args:
        task: Task dict with "input" key (optionally "output_file")
        model: LLM model to use (default: OpenRouter GPT-4o-mini)
        
    Returns:
        Response dict with written content and file operation status
    """
    manager = ToolsManager()
    input_text = task.get("input", "") if isinstance(task, dict) else task
    output_file = task.get("output_file", None) if isinstance(task, dict) else None
    persist_output = task.get("persist_output", True) if isinstance(task, dict) else True
    if complexity == "simple":
        note_context, notes_result = "", {"notes": []}
    else:
        note_context, notes_result = load_memory_bundle(task, agent_name="writer")

    complexity = task.get("complexity", "simple") if isinstance(task, dict) else "simple"
    if complexity == "simple":
        length_hint = "Answer in 1-3 sentences. Be direct and conversational."
    else:
        length_hint = "Be complete and well-structured. Use paragraphs or bullet points where appropriate."

    from app.learning import get_user_context
    _user_ctx = get_user_context()

    prompt = f"""
You are JARVIS, a personal AI assistant. Respond naturally and helpfully.
{_user_ctx}

Guidelines:
- {length_hint}
- No markdown formatting — no headers (##), no bold (**), no bullet points unless the task explicitly calls for a formatted document
- Do not repeat the question or start with "Certainly!"
- Maintain a professional but friendly tone
{note_context}

Task: {input_text}
""".strip()

    llm_result = generate(prompt, model=model, return_metadata=True)
    response = llm_result["content"]

    # Save to file by default unless explicitly disabled
    file_result = None
    resolved_output_file = output_file or (_default_output_file(task, response) if persist_output else None)
    if resolved_output_file:
        try:
            write_result = manager.execute(
                "write_file",
                filepath=resolved_output_file,
                content=response,
                task_type="writer",
                agent_name="writer",
                task_id=task.get("task_id") if isinstance(task, dict) else None,
            )
            file_result = {
                "status": "success" if write_result["success"] else "error",
                "filepath": write_result.get("filepath"),
                "bytes_written": write_result.get("bytes_written"),
                "error": write_result.get("error")
            }
        except Exception as e:
            file_result = {
                "status": "error",
                "error": str(e)
            }

    email_result = None
    if _is_email_task(input_text):
        email_details = _extract_email_details(input_text)
        email_details["body"] = response
        email_details["cc"] = task.get("cc") if isinstance(task, dict) else None
        email_details["bcc"] = task.get("bcc") if isinstance(task, dict) else None
        email_details["send_via_smtp"] = True
        if not email_details.get("subject"):
            email_details["subject"] = _infer_email_subject(response) or "Message from OfficeOS"

        if not email_details.get("to"):
            default_to = os.getenv("EMAIL_DEFAULT_TO")
            if default_to:
                email_details["to"] = default_to

        try:
            send_result = manager.execute(
                "send_email",
                task_type="writer",
                agent_name="writer",
                task_id=task.get("task_id") if isinstance(task, dict) else None,
                **email_details,
            )
            email_result = {
                "status": "success" if send_result["success"] else "error",
                "result": send_result.get("result"),
                "error": send_result.get("error")
            }
        except Exception as e:
            email_result = {
                "status": "error",
                "error": str(e)
            }

    second_brain = {
        "file_note": save_file_output_note(task if isinstance(task, dict) else {"input": input_text}, file_result, response)
        if file_result else None,
        "email_note": save_email_note(task if isinstance(task, dict) else {"input": input_text}, email_result, response)
        if email_result else None,
    }

    return attach_memory_metadata({
        "response": response,
        "file_output": file_result,
        "email_output": email_result,
        "llm": llm_result,
    }, notes_result, second_brain)
