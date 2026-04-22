#!/usr/bin/env python

import argparse
import atexit
import os
import signal
import subprocess
import sys
from pathlib import Path

import uvicorn


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def start_orchestrator() -> subprocess.Popen | None:
    orchestrator_path = ROOT_DIR / "orchestrator.py"
    if not orchestrator_path.exists():
        print("[dashboard] orchestrator.py not found, skipping worker startup")
        return None

    process = subprocess.Popen(
        [sys.executable, str(orchestrator_path)],
        cwd=str(ROOT_DIR),
    )
    print(f"[dashboard] started orchestrator worker pid={process.pid}")
    return process


def stop_process(process: subprocess.Popen | None) -> None:
    if not process or process.poll() is not None:
        return

    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the OfficeOS HUD dashboard.")
    parser.add_argument(
        "--no-orchestrator",
        action="store_true",
        help="Run only the dashboard server without starting the orchestrator worker.",
    )
    args = parser.parse_args()

    os.chdir(ROOT_DIR)
    orchestrator_process = None if args.no_orchestrator else start_orchestrator()
    atexit.register(stop_process, orchestrator_process)

    try:
        uvicorn.run("app.dashboard_server:app", host="127.0.0.1", port=8000, reload=False)
    finally:
        stop_process(orchestrator_process)


if __name__ == "__main__":
    main()
