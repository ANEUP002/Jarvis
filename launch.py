#!/usr/bin/env python
"""
JARVIS Master Launcher
======================
Starts everything in the right order:

  1. FastAPI HUD server  (background thread — serves the dashboard on :8000)
  2. JARVIS Orb GUI      (background thread — animated Siri-style orb)
  3. Clap detector       (background daemon — double-clap wakes JARVIS)
  4. JARVIS terminal     (foreground REPL — main interaction loop)

Usage:
    python launch.py              # text mode
    python launch.py --voice      # TTS output
    python launch.py --listen     # voice input + TTS output
    python launch.py --no-orb     # skip the orb GUI
    python launch.py --no-hud     # skip the dashboard server
    python launch.py --debug      # verbose errors
"""

from __future__ import annotations

import sys
import time
import threading
import webbrowser
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── flags ─────────────────────────────────────────────────────────────────────
_args = set(sys.argv[1:])
FLAG_VOICE  = "--voice"  in _args or "-v" in _args
FLAG_LISTEN = "--listen" in _args or "-l" in _args
FLAG_ORB    = "--no-orb" not in _args
FLAG_HUD    = "--no-hud" not in _args
FLAG_DEBUG  = "--debug"  in _args

# launch.py always boots in clap-wake mode unless --listen is explicit.
# --clap tells jarvis.main() to wait for the threading.Event before each listen.
if FLAG_LISTEN:
    if "--listen" not in sys.argv: sys.argv.append("--listen")
else:
    # Default launch mode: clap-gated voice + TTS
    if "--clap"  not in sys.argv: sys.argv.append("--clap")
    if "--voice" not in sys.argv: sys.argv.append("--voice")

if FLAG_DEBUG:
    if "--debug" not in sys.argv: sys.argv.append("--debug")

# Shared wake event — clap detector sets it, jarvis REPL waits on it
_wake_event = threading.Event()


# ── rich console ──────────────────────────────────────────────────────────────
from rich.console import Console
from rich.rule import Rule

console = Console()


# ── 1. FastAPI HUD server ─────────────────────────────────────────────────────

_hud_started = threading.Event()

def _start_hud_server() -> None:
    try:
        import uvicorn
        from app.dashboard_server import app as fastapi_app
        _hud_started.set()
        uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_level="error")
    except Exception as exc:
        console.print(f"[yellow]  HUD server failed to start: {exc}[/yellow]")
        _hud_started.set()


def start_hud() -> None:
    t = threading.Thread(target=_start_hud_server, daemon=True, name="hud-server")
    t.start()
    _hud_started.wait(timeout=6)
    time.sleep(0.8)   # let uvicorn bind the port


# ── 2. Orb GUI ────────────────────────────────────────────────────────────────

_orb = None

def start_orb() -> None:
    global _orb
    try:
        from app.jarvis_orb import JarvisOrb
        _orb = JarvisOrb()
        _orb.start()
        time.sleep(0.3)
    except Exception as exc:
        console.print(f"[yellow]  Orb GUI failed: {exc}[/yellow]")


def orb_set(state: str, text: str = "") -> None:
    if _orb:
        try:
            _orb.set_state(state, text)
        except Exception:
            pass


def orb_response(text: str) -> None:
    if _orb:
        try:
            _orb.set_response(text)
        except Exception:
            pass


# ── 3. Clap detector ──────────────────────────────────────────────────────────

_detector: "ClapDetector | None" = None


def _on_double_clap() -> None:
    console.print("\n[bold cyan]  ◈  Clap — listening, sir.[/bold cyan]")
    orb_set("listening", "Clap wake")
    _wake_event.set()   # unblocks jarvis REPL _wake_event.wait()


def start_clap_detector() -> None:
    global _detector
    try:
        from app.clap_detect import ClapDetector
        _detector = ClapDetector(_on_double_clap)
        _detector.start()
    except Exception as exc:
        console.print(f"[yellow]  Clap detector failed: {exc}[/yellow]")


# ── 4. Open HUD in browser ───────────────────────────────────────────────────

def open_hud_browser() -> None:
    try:
        webbrowser.open("http://127.0.0.1:8000/")
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    console.print()
    console.print(Rule("[bold blue]J.A.R.V.I.S  LAUNCH SEQUENCE[/bold blue]", style="blue dim"))
    console.print()

    # 1. HUD server
    if FLAG_HUD:
        console.print("  [dim]Starting HUD server...[/dim]", end=" ")
        start_hud()
        console.print("[bold green]✓[/bold green] http://127.0.0.1:8000/")
    else:
        console.print("  [dim]HUD server skipped (--no-hud).[/dim]")

    # 2. Orb
    if FLAG_ORB:
        console.print("  [dim]Starting orb GUI...[/dim]", end=" ")
        start_orb()
        console.print("[bold green]✓[/bold green] Orb ready.")
    else:
        console.print("  [dim]Orb skipped (--no-orb).[/dim]")

    # 3. Clap detector
    console.print("  [dim]Arming clap detector...[/dim]", end=" ")
    start_clap_detector()
    console.print("[bold green]✓[/bold green] Double-clap to wake.")

    # 4. Open HUD in browser
    if FLAG_HUD:
        console.print("  [dim]Opening HUD in browser...[/dim]")
        threading.Timer(1.5, open_hud_browser).start()

    console.print()
    console.print(Rule(style="blue dim"))
    console.print()

    # 5. Inject orb + wake event + clap detector ref into jarvis module
    import jarvis as jarvis_mod
    if _orb:
        jarvis_mod._orb_instance = _orb
    jarvis_mod._wake_event = _wake_event          # clap detector fires this
    jarvis_mod._clap_detector_ref = _detector     # paused during voice capture

    orb_set("idle", "Clap twice to wake")

    # 6. Hand off to jarvis main REPL
    jarvis_mod.main()

    orb_set("idle")
    if _orb:
        _orb.stop()


if __name__ == "__main__":
    main()
