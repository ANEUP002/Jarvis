#!/usr/bin/env python
"""
Launcher for JARVIS terminal mode.

Usage:
    python scripts/run_jarvis_mode.py           # text only
    python scripts/run_jarvis_mode.py --voice   # text + voice output
    python scripts/run_jarvis_mode.py --debug   # show full tracebacks
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

# Forward all flags (--voice, --debug) to jarvis.py
from jarvis import main

if __name__ == "__main__":
    main()
