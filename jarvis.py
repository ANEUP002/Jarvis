#!/usr/bin/env python
"""
JARVIS — Just A Rather Very Intelligent System
Iron Man terminal interface. No browser. No GUI. Pure terminal.

Usage:
    python jarvis.py              # text mode
    python jarvis.py --voice      # text input + voice output
    python jarvis.py --listen     # voice input + voice output (full hands-free)
    python jarvis.py --debug      # show full tracebacks
"""
import sys
import uuid
import time
import threading
import subprocess
from pathlib import Path
from typing import List, Dict, Callable, Optional

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich import box

console = Console()

# ── BANNER ───────────────────────────────────────────────────────────────────

BANNER = r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝"""

# ── CONVERSATION MEMORY ───────────────────────────────────────────────────────

class Memory:
    """Conversation turns — persisted to disk so JARVIS remembers across restarts."""

    def __init__(self, max_turns: int = 8):
        from app.learning import load_session
        self.turns: List[Dict[str, str]] = load_session(max_turns)
        self.max_turns = max_turns

    def add(self, user: str, jarvis: str) -> None:
        self.turns.append({"user": user, "jarvis": jarvis})
        if len(self.turns) > self.max_turns:
            self.turns.pop(0)
        from app.learning import save_session
        save_session(self.turns)

    def clear(self) -> None:
        self.turns.clear()
        from app.learning import save_session
        save_session([])

    def enrich(self, current: str) -> str:
        """Prepend recent conversation to the current request."""
        if not self.turns:
            return current
        lines = ["[CONVERSATION HISTORY — for context only]"]
        for t in self.turns[-3:]:
            lines.append(f"User: {t['user'][:250]}")
            lines.append(f"JARVIS: {t['jarvis'][:400]}")
            lines.append("")
        lines.append("[CURRENT REQUEST]")
        lines.append(current)
        return "\n".join(lines)

# ── VOICE OUTPUT (Windows built-in TTS, zero dependencies) ───────────────────

def _tts_clean(text: str) -> str:
    """Strip markdown and symbols that sound bad when read aloud."""
    import re
    t = text.replace("\n", " ").replace("\r", " ")
    t = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", t)   # **bold** / *italic*
    t = re.sub(r"`{1,3}[^`]*`{1,3}", "", t)          # `code`
    t = re.sub(r"#{1,6}\s*", "", t)                   # ## headings
    t = re.sub(r"^\s*[-•]\s+", "", t, flags=re.M)     # bullet points
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)    # [link](url)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip().replace('"', "").replace("'", "")


def speak(text: str) -> None:
    """Blocking TTS with female voice. Returns only after speech finishes so the
    mic cannot pick up JARVIS's own output."""
    clean = _tts_clean(text)[:600]
    # Pause the clap detector so audio output doesn't trigger a false clap
    det = _clap_detector_ref
    if det:
        det.pause()
    try:
        subprocess.run(
            [
                "powershell", "-WindowStyle", "Hidden", "-Command",
                'Add-Type -AssemblyName System.Speech; '
                '$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                'try { $s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female) } catch {}; '
                '$s.Rate = 1; '
                f'$s.Speak("{clean}")',
            ],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
    except Exception:
        pass
    finally:
        if det:
            time.sleep(0.7)   # let speaker echo die before re-arming mic
            det.resume()

# ── ORB STATE BRIDGE & CLAP WAKE ─────────────────────────────────────────────
# launch.py injects these; they stay None/unset in standalone mode.
_orb_instance = None
_wake_event: Optional[threading.Event] = None      # set by launch.py clap detector
_clap_detector_ref = None                          # ClapDetector — paused during voice

def _orb_notify(state: str, text: str = "") -> None:
    """Update the JARVIS orb if one is attached (set by launch.py)."""
    orb = _orb_instance
    if orb is None:
        return
    try:
        orb.set_state(state, text)
    except Exception:
        pass


# ── PIPELINE ─────────────────────────────────────────────────────────────────

VALID_TYPES = {"code", "writer", "research"}

def _norm(t: str) -> str:
    return t if t in VALID_TYPES else "research"


def run_task(raw_input: str, memory: Memory, _on_plan=None, _on_progress=None) -> dict:
    """
    Run a request through the full JARVIS pipeline without the file queue.
    Returns a dict: {response, agent, model, mode, type, complexity, stages}

    _on_plan(mode, subtask_count)  — called just before execution starts.
    _on_progress(message)          — called at key moments during complex execution.
    """
    from app.assistant_fastlane import handle_fastlane
    from app.classifier import classify
    from agents.chief_agent import plan_task, combine_results
    from app.model_selector import select_model
    from app.router import execute_single_task
    from orchestrator import run_subtasks

    task_id = str(uuid.uuid4())[:8]
    stages: List[tuple] = []

    # ── Fastlane (greetings, time, weather — no LLM needed) ──────────────────
    fastlane = handle_fastlane(raw_input)
    if fastlane and fastlane.get("handled"):
        return {
            "response": fastlane.get("response", ""),
            "agent": "fastlane",
            "model": "local",
            "mode": "fastlane",
            "type": fastlane.get("task_type", "research"),
            "complexity": "simple",
            "stages": [("✅", "FASTLANE", fastlane.get("kind", "local"))],
        }

    # ── Classify ──────────────────────────────────────────────────────────────
    classification = classify(raw_input)
    task_type = _norm(classification.get("type", "research"))
    complexity = classification.get("complexity", "simple")
    stages.append((
        "🔍", "CLASSIFY",
        f"{task_type} · {complexity} · conf={classification.get('confidence', 0):.0%}"
    ))

    # ── Plan (enrich with conversation context) ───────────────────────────────
    enriched_input = memory.enrich(raw_input)

    # Skip the heavy MiniMax plan_task call for simple requests — they never
    # need multi-agent decomposition.
    if complexity == "simple":
        chief_plan = {"mode": "simple", "task_type": task_type}
    else:
        chief_plan = plan_task(enriched_input)

    mode = chief_plan.get("mode", "simple")
    plan_detail = mode
    if mode == "multi":
        plan_detail += f" → {len(chief_plan.get('subtasks', []))} subtasks"
    stages.append(("📋", "PLAN", plan_detail))

    # ── Model selection ───────────────────────────────────────────────────────
    model = select_model(task_type, complexity=complexity, task_input=raw_input)
    stages.append(("🤖", "MODEL", model.split("/")[-1]))

    task = {
        "task_id": task_id,
        "input": enriched_input,
        "search_query": raw_input,   # clean query for second brain — no history noise
        "task_type": task_type,
        "model": model,
        "complexity": complexity,
        "classification": classification,
        "chief_plan": chief_plan,
    }

    # ── Multi-agent parallel execution ────────────────────────────────────────
    if mode == "multi":
        subtasks = chief_plan.get("subtasks", [])
        if subtasks:
            if _on_plan:
                _on_plan("multi", len(subtasks))

            _TYPE_WORD = {"research": "Research", "code": "Code", "writer": "Writing"}

            def _subtask_done(result, done, total):
                if _on_progress:
                    ttype = _TYPE_WORD.get(result.get("task_type", ""), "Task")
                    _on_progress(f"{ttype} done. {done} of {total} complete.")

            stages.append(("⚡", "EXECUTE", f"multi-agent · {len(subtasks)} parallel"))
            subtask_data = run_subtasks(task, subtasks, on_subtask_done=_subtask_done)

            if _on_progress:
                _on_progress("Combining all results now.")
            final = combine_results(enriched_input, subtask_data["subtask_results"])
            response = final.get("response", "")
            stages.append(("✅", "SYNTHESIZE", f"{len(subtasks)} results merged"))
            return {
                "response": response,
                "agent": "chief",
                "model": model,
                "mode": "multi",
                "type": task_type,
                "complexity": complexity,
                "stages": stages,
            }

    # ── Simple single-agent execution ─────────────────────────────────────────
    stages.append(("⚡", "EXECUTE", f"{task_type}Agent · {model.split('/')[-1]}"))
    routing = execute_single_task(task)
    result = routing.get("result", {})
    response = result.get("response", "") if isinstance(result, dict) else str(result)
    actual_model = routing.get("model", model)
    stages.append(("✅", "DONE", f"via {actual_model.split('/')[-1]}"))

    return {
        "response": response,
        "agent": routing.get("agent", task_type),
        "model": actual_model,
        "mode": "simple",
        "type": task_type,
        "complexity": complexity,
        "stages": stages,
    }

# ── HELP ─────────────────────────────────────────────────────────────────────

def _print_tool_result(r: dict, label: str) -> None:
    if r["success"]:
        console.print(f"  [bold green]✓[/bold green] {r.get('result', label)}")
    else:
        console.print(f"  [bold red]✗[/bold red] {r.get('error', 'failed')}")


def show_help() -> None:
    t = Table(title="JARVIS Commands", box=box.ROUNDED, border_style="blue dim", show_header=True)
    t.add_column("Command", style="cyan bold", width=20)
    t.add_column("What it does")
    t.add_row("exit / quit", "Shut down JARVIS")
    t.add_row("history", "Show conversation history this session")
    t.add_row("clear", "Wipe conversation memory")
    t.add_row("today / daily", "Open today's daily note (Obsidian-style)")
    t.add_row("notes / brain", "Show second brain index (top 20 notes)")
    t.add_row("", "")
    t.add_row("[bold]Desktop[/bold]", "")
    t.add_row("open <app>", "Open Chrome, VSCode, Spotify, Excel, etc.")
    t.add_row("close <app>", "Close a running app by name")
    t.add_row("apps / windows", "List all open windows")
    t.add_row("focus <title>", "Bring a window to the foreground")
    t.add_row("screenshot", "Take a screenshot → ~/Pictures/")
    t.add_row("run <command>", "Run any PowerShell / shell command")
    t.add_row("search apps <q>", "Find installed apps by keyword")
    t.add_row("", "")
    t.add_row("[bold]MCP[/bold]", "")
    t.add_row("mcp", "Show connected MCP servers and their tools")
    t.add_row("", "")
    t.add_row("help", "Show this menu")
    t.add_row("", "")
    t.add_row("[bold]Startup flags[/bold]", "")
    t.add_row("--voice  / -v", "Voice output — JARVIS speaks responses")
    t.add_row("--listen / -l", "Voice input + output — fully hands-free")
    t.add_row("--debug", "Show full error traces")
    t.add_row("", "")
    t.add_row("[dim]Tip[/dim]", "[dim]Press Enter with no text to speak one command[/dim]")
    console.print(t)

# ── MAIN LOOP ─────────────────────────────────────────────────────────────────

def _get_voice_input() -> str | None:
    """Show listening indicator, record, transcribe, return text."""
    from app.voice_input import listen
    _orb_notify("listening", "Listening...")
    console.print("\n  [bold cyan]🎤  Listening...[/bold cyan]", end="", highlight=False)
    text = listen(timeout=8, phrase_limit=20)
    if text:
        console.print(f"\r  [bold cyan]🎤[/bold cyan]  [bold]{text}[/bold]                    ")
        _orb_notify("thinking", text[:60])
    else:
        console.print("\r  [dim]🎤  (nothing heard)[/dim]                    ")
        _orb_notify("idle")
    return text


def main() -> None:
    tts    = "--voice"  in sys.argv or "-v" in sys.argv
    stt    = "--listen" in sys.argv or "-l" in sys.argv
    clap   = "--clap"   in sys.argv          # clap-gated voice mode (set by launch.py)
    debug  = "--debug"  in sys.argv

    # --clap and --listen both imply voice output
    if stt or clap:
        tts = True

    # ── Boot sequence ─────────────────────────────────────────────────────────
    console.clear()
    console.print(BANNER, style="bold blue", justify="center")
    console.print()
    console.print("Just A Rather Very Intelligent System", style="bold cyan", justify="center")
    console.print("v2.0  ·  Iron Man Mode  ·  Terminal Interface", style="dim", justify="center")
    console.print()
    console.print(Rule(style="blue dim"))
    console.print()

    _mode_parts = []
    if clap: _mode_parts.append("clap-wake")
    if stt:  _mode_parts.append("always-listening")
    if tts:  _mode_parts.append("voice output")
    _mode_str = " · ".join(_mode_parts) if _mode_parts else "text mode"
    console.print(f"  [bold cyan]●[/bold cyan]  [dim]{_mode_str}[/dim]  ·  type [dim cyan]help[/dim cyan] for commands\n")

    # Calibrate mic only when NOT in clap mode (clap detector already owns the
    # mic stream — opening a second stream causes a silent pyaudio crash).
    if stt and not clap:
        from app.voice_input import calibrate
        with console.status("[dim]Calibrating microphone...[/dim]", spinner="dots"):
            calibrate(duration=0.5)

    # Pre-warm embeddings in background so the first query isn't slow
    def _prewarm():
        try:
            from tools.embeddings import get_embedder
            get_embedder()
        except Exception:
            pass
    threading.Thread(target=_prewarm, daemon=True).start()

    # Record session start for stats tracking
    from app.learning import (
        record_session_start, record_query, extract_from_message,
        track_interest, record_correction,
        detect_memory_command, apply_memory_command,
    )
    record_session_start()

    memory = Memory()
    _greeted = False   # say the time-of-day greeting only on the first clap

    if clap:
        console.print("  [bold cyan]◈[/bold cyan]  [dim]Clap twice to wake JARVIS. Type anytime to skip clap.[/dim]\n")

    # ── REPL ──────────────────────────────────────────────────────────────────
    while True:
        try:
            if clap:
                # Clap-wake mode: block until double-clap fires _wake_event.
                # The event is injected by launch.py; falls back to text input if missing.
                ev = _wake_event
                if ev is not None:
                    _orb_notify("idle", "Clap twice to wake")
                    ev.wait()          # blocks here; clap detector sets this
                    ev.clear()

                    if not _greeted:
                        from app.learning import load_profile as _lp
                        _uname = _lp().get("name") or "sir"
                        _hour = time.localtime().tm_hour
                        if _hour < 12:
                            _greeting = f"Good morning, {_uname}. How can I help you?"
                        elif _hour < 17:
                            _greeting = f"Good afternoon, {_uname}. How can I help you?"
                        else:
                            _greeting = f"Good evening, {_uname}. How can I help you?"
                        _greeted = True
                        _orb_notify("speaking", _greeting)
                        console.print(f"\n  [bold cyan]◈[/bold cyan]  {_greeting}")
                        if tts:
                            speak(_greeting)
                    else:
                        console.print(f"\n  [bold cyan]◈[/bold cyan]  [dim]Listening, sir.[/dim]")
                        _orb_notify("listening", "Listening")

                    # Pause clap detector so voice capture can own the mic
                    det = _clap_detector_ref
                    if det:
                        det.pause()
                    time.sleep(0.12)   # let clap stream drain one chunk
                    try:
                        user_input = _get_voice_input() or ""
                    finally:
                        if det:
                            det.resume()
                    if not user_input:
                        console.print("  [dim]Nothing heard — clap again, sir.[/dim]")
                        continue
                else:
                    # No wake event injected: fall back to text input
                    user_input = console.input("\n[bold blue]▸ Sir[/bold blue] ").strip()
            elif stt:
                # Always-on voice mode
                console.print("\n[bold blue]▸[/bold blue] ", end="")
                user_input = _get_voice_input() or ""
            else:
                user_input = console.input("\n[bold blue]▸ Sir[/bold blue] ").strip()

            # Empty text input → one-shot voice capture
            if not user_input and not stt and not clap:
                console.print("  [dim](press Enter to speak, or type your request)[/dim]")
                user_input = _get_voice_input() or ""

            if not user_input:
                continue

            # ── Built-in commands ─────────────────────────────────────────────
            cmd = user_input.lower()

            # ── Self-learning: passive extraction from every message ──────────
            extract_from_message(user_input)

            # ── Self-learning: explicit memory commands ───────────────────────
            _mem_cmd = detect_memory_command(user_input)
            if _mem_cmd:
                _mem_response = apply_memory_command(_mem_cmd)
                console.print()
                console.print(Panel(
                    _mem_response,
                    title="[bold cyan]◈  JARVIS[/bold cyan]",
                    border_style="cyan",
                    box=box.ROUNDED,
                    padding=(1, 2),
                ))
                memory.add(user_input, _mem_response)
                if tts:
                    speak(_mem_response)
                threading.Timer(3.0, lambda: _orb_notify("idle")).start()
                continue

            if cmd in {"exit", "quit", "shutdown", "offline"}:
                console.print("\n[bold cyan]  JARVIS offline. Goodbye, sir.[/bold cyan]\n")
                if tts:
                    speak("Goodbye, sir.")
                break

            if cmd == "help":
                show_help()
                continue

            if cmd == "history":
                if not memory.turns:
                    console.print("[dim]  No conversation history yet.[/dim]")
                else:
                    for i, turn in enumerate(memory.turns, 1):
                        console.print(f"\n[dim]── Turn {i} ──[/dim]")
                        console.print(f"[blue]You:[/blue]    {turn['user'][:300]}")
                        console.print(f"[cyan]JARVIS:[/cyan] {turn['jarvis'][:400]}")
                continue

            if cmd == "clear":
                memory.clear()
                console.print("[dim]  Conversation memory cleared.[/dim]")
                continue

            if cmd in {"today", "daily", "daily note"}:
                from tools.notes_tools import get_today_note
                result_note = get_today_note()
                if result_note.get("success"):
                    n = result_note["result"]
                    console.print(Panel(
                        f"[bold]{n['title']}[/bold]\nPath: {n['path']}\nTags: {', '.join(n.get('tags', []))}",
                        title="[bold cyan]◈  Daily Note[/bold cyan]",
                        border_style="cyan",
                        box=box.ROUNDED,
                    ))
                else:
                    console.print(f"[red]  Could not create daily note: {result_note.get('error')}[/red]")
                continue

            if cmd.startswith("notes") or cmd == "brain":
                from tools.notes_tools import _list_note_records, _build_backlinks_index
                all_notes = _list_note_records()
                idx = _build_backlinks_index(all_notes)
                t = Table(title=f"Second Brain ({len(all_notes)} notes)", box=box.ROUNDED, border_style="blue dim")
                t.add_column("Title", style="cyan")
                t.add_column("Category", style="dim")
                t.add_column("Tags", style="dim")
                t.add_column("↑", justify="right", style="dim")
                t.add_column("↓", justify="right", style="dim")
                for note in all_notes[:20]:
                    t.add_row(
                        note["title"][:40],
                        note.get("category", "")[:20],
                        ", ".join(note.get("tags", []))[:30],
                        str(len(note["links"])),
                        str(len(idx.get(note["title"], []))),
                    )
                console.print(t)
                continue

            # ── Media playback shortcuts ──────────────────────────────────────
            import re as _re
            _PLAY_PREFIXES = _re.match(
                r"^(play|turn on|put on|start playing|open|search)\s+",
                cmd,
            )
            _is_media = _PLAY_PREFIXES and _re.search(
                r"\b(youtube|spotify|music|song|track)\b", cmd
            )
            if _is_media:
                import webbrowser as _wb
                _prefix_len = len(_PLAY_PREFIXES.group(0))
                _play_raw = user_input[_prefix_len:].strip()
                _platform_match = _re.search(r"\s+on\s+(youtube|spotify|music)\s*$", _play_raw, _re.IGNORECASE)
                _platform = _platform_match.group(1).lower() if _platform_match else "youtube"
                _song = _re.sub(r"\s+on\s+(youtube|spotify|music)\s*$", "", _play_raw, flags=_re.IGNORECASE).strip()
                _song = _re.sub(r"\b(youtube|spotify|music|song|track)\b", "", _song, flags=_re.IGNORECASE).strip()

                if _platform == "spotify":
                    _url = f"https://open.spotify.com/search/{_song.replace(' ', '+')}"
                    _wb.open(_url)
                else:
                    # Use yt-dlp to find the first YouTube result directly
                    _url = None
                    _video_title = _song
                    try:
                        import yt_dlp as _ytdlp
                        _ydl_opts = {
                            "quiet": True,
                            "no_warnings": True,
                            "extract_flat": True,
                        }
                        with _ytdlp.YoutubeDL(_ydl_opts) as _ydl:
                            _info = _ydl.extract_info(f"ytsearch1:{_song}", download=False)
                            _entry = (_info.get("entries") or [None])[0]
                            if _entry:
                                _vid_id = _entry.get("id") or _entry.get("url", "")
                                if _vid_id and not _vid_id.startswith("http"):
                                    _url = f"https://www.youtube.com/watch?v={_vid_id}"
                                elif _vid_id.startswith("http"):
                                    _url = _vid_id
                                _video_title = _entry.get("title", _song)
                    except Exception:
                        pass

                    _announce = f"Playing {_video_title}"
                    console.print(f"  [bold green]✓[/bold green]  {_announce}")
                    if tts:
                        speak(_announce)
                    _wb.open(_url or f"https://www.youtube.com/results?search_query={_song.replace(' ', '+')}")
                    continue

                console.print(f"  [bold green]✓[/bold green]  Opening [bold]{_song}[/bold] on Spotify")
                if tts:
                    speak(f"Opening {_song} on Spotify")
                continue

            # ── Desktop control shortcuts ─────────────────────────────────────
            if cmd.startswith("open "):
                app = user_input[5:].strip()
                from tools.desktop_tools import OpenAppTool
                r = OpenAppTool().execute(app=app)
                _print_tool_result(r, f"open {app}")
                continue

            if cmd.startswith("close "):
                app = user_input[6:].strip()
                from tools.desktop_tools import CloseAppTool
                r = CloseAppTool().execute(app=app)
                _print_tool_result(r, f"close {app}")
                continue

            if cmd in {"apps", "windows"}:
                from tools.desktop_tools import ListWindowsTool
                r = ListWindowsTool().execute()
                if r["success"]:
                    wins = r["result"]["windows"]
                    t = Table(title=f"Open Windows ({len(wins)})", box=box.ROUNDED, border_style="blue dim")
                    t.add_column("App", style="cyan", width=20)
                    t.add_column("Title")
                    t.add_column("PID", justify="right", style="dim", width=8)
                    t.add_column("MB", justify="right", style="dim", width=7)
                    for w in wins:
                        t.add_row(
                            str(w.get("name", ""))[:20],
                            str(w.get("title", ""))[:60],
                            str(w.get("pid", "")),
                            str(w.get("memory_mb", "")),
                        )
                    console.print(t)
                else:
                    console.print(f"[red]{r['error']}[/red]")
                continue

            if cmd.startswith("focus "):
                title = user_input[6:].strip()
                from tools.desktop_tools import FocusWindowTool
                r = FocusWindowTool().execute(title=title)
                _print_tool_result(r, f"focus {title}")
                continue

            if cmd == "screenshot":
                from tools.desktop_tools import TakeScreenshotTool
                r = TakeScreenshotTool().execute()
                _print_tool_result(r, "screenshot")
                continue

            if cmd.startswith("run "):
                command = user_input[4:].strip()
                from tools.desktop_tools import RunCommandTool
                with console.status("[bold blue]⚡ Running...[/bold blue]", spinner="dots"):
                    r = RunCommandTool().execute(command=command)
                if r["success"]:
                    out = r["result"].get("output", "")
                    console.print(Panel(out or "(no output)", title="[bold cyan]◈ Shell[/bold cyan]",
                                        border_style="cyan", box=box.ROUNDED))
                else:
                    console.print(f"[red]  Error: {r['error']}[/red]")
                continue

            if cmd.startswith("search apps") or cmd.startswith("find app"):
                query = user_input.split(" ", 2)[-1].strip()
                from tools.desktop_tools import SearchAppsTool
                with console.status("[bold blue]Searching apps...[/bold blue]"):
                    r = SearchAppsTool().execute(query=query)
                if r["success"]:
                    apps = r["result"]["apps"][:30]
                    t = Table(title=f"Installed Apps matching '{query}'", box=box.ROUNDED, border_style="blue dim")
                    t.add_column("Name", style="cyan")
                    t.add_column("AppID", style="dim")
                    for a in apps:
                        t.add_row(str(a.get("name", ""))[:50], str(a.get("id", ""))[:60])
                    console.print(t)
                else:
                    console.print(f"[red]{r['error']}[/red]")
                continue

            # ── MCP shortcuts ─────────────────────────────────────────────────
            if cmd in {"mcp", "mcp tools"}:
                from tools.mcp_client import mcp_registry
                with console.status("[bold blue]Loading MCP servers...[/bold blue]"):
                    mcp_registry.load()
                servers = mcp_registry.servers_info()
                if not servers:
                    console.print("[dim]  No MCP servers connected. Edit [cyan]mcp_servers.json[/cyan] to add one.[/dim]")
                else:
                    for s in servers:
                        status = "[green]●[/green]" if s["alive"] else "[red]●[/red]"
                        console.print(f"  {status} [bold cyan]{s['name']}[/bold cyan] — {len(s['tools'])} tools")
                        for tool in s["tools"]:
                            console.print(f"      [dim]{tool['name']}[/dim] — {tool.get('description','')[:80]}")
                continue

            # ── Process request ───────────────────────────────────────────────
            start = time.time()
            _orb_notify("thinking", user_input[:60])

            def _narrate(msg: str) -> None:
                """Print + speak a short status update during task execution."""
                console.print(f"  [dim cyan]◈  {msg}[/dim cyan]")
                _orb_notify("thinking", msg)
                if tts:
                    speak(msg)

            def _on_multi_plan(mode: str, count: int) -> None:
                _narrate(f"On it. Breaking this into {count} parallel tasks.")

            def _on_progress(msg: str) -> None:
                _narrate(msg)

            with console.status(
                "[bold blue]⚡  Processing...[/bold blue]",
                spinner="dots",
                spinner_style="blue",
            ):
                result = run_task(user_input, memory,
                                  _on_plan=_on_multi_plan,
                                  _on_progress=_on_progress)

            elapsed = time.time() - start
            response = result.get("response") or "[No response generated]"

            _orb_notify("speaking", response[:80])

            # ── HUD stage readout ─────────────────────────────────────────────
            stages = result.get("stages", [])
            if stages:
                hud = Table.grid(padding=(0, 1))
                hud.add_column(width=3)
                hud.add_column(width=14, style="bold blue dim")
                hud.add_column(style="dim")
                for icon, label, detail in stages:
                    hud.add_row(icon, label, detail)
                console.print()
                console.print(hud)

            # ── Response panel ────────────────────────────────────────────────
            meta = (
                f"[dim]{result.get('agent', '?')} · "
                f"{result.get('model', '?').split('/')[-1]} · "
                f"{result.get('type', '?')}/{result.get('complexity', '?')} · "
                f"{elapsed:.1f}s[/dim]"
            )
            console.print()
            console.print(Panel(
                response,
                title="[bold cyan]◈  JARVIS[/bold cyan]",
                subtitle=meta,
                border_style="cyan",
                box=box.ROUNDED,
                padding=(1, 2),
            ))

            memory.add(user_input, response)

            # Track interest, count query, detect corrections — all async
            track_interest(user_input)
            record_query()
            _correction_signals = (
                "don't do that", "wrong answer", "that's wrong", "incorrect",
                "i don't want", "stop doing", "don't say", "bad answer",
                "that was wrong", "not what i asked",
            )
            if any(s in cmd for s in _correction_signals):
                record_correction(user_input)

            if tts:
                _complexity = result.get("complexity", "simple")
                _cleaned = _tts_clean(response)
                # Simple tasks: speak up to 2 sentences; complex: up to 3
                _limit = 2 if _complexity == "simple" else 3
                _sentences = [s.strip() for s in _cleaned.split(". ") if s.strip()]
                _speak_text = ". ".join(_sentences[:_limit])
                if _sentences[_limit:]:
                    _speak_text += "."
                speak(_speak_text[:500])

            # Return orb to idle after a short delay
            threading.Timer(4.0, lambda: _orb_notify("idle")).start()

        except KeyboardInterrupt:
            console.print("\n\n[bold cyan]  JARVIS offline. Goodbye, sir.[/bold cyan]\n")
            break

        except SystemExit:
            # Don't let stray sys.exit() calls kill the REPL
            pass

        except Exception as exc:
            console.print(f"\n[red]  Error:[/red] {exc}")
            if debug:
                import traceback
                console.print(f"[dim red]{traceback.format_exc()}[/dim red]")


if __name__ == "__main__":
    main()
