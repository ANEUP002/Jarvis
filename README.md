# JARVIS — Personal AI Assistant

An Iron Man-style voice assistant that runs on your local machine. Double-clap to activate, speak your request, and JARVIS responds via voice and text.

## Features

- **Voice activation** — double-clap detection with adaptive noise filtering
- **Live web search** — real-time DuckDuckGo results for news and current events
- **Multi-agent pipeline** — Research, Code, and Writer agents routed intelligently
- **Self-learning** — extracts facts from conversation, builds a personal profile over time
- **YouTube playback** — says the video title aloud and opens the correct video
- **HUD panel** — live architecture view showing which component is active
- **Weather, email, to-dos** — built-in tool integrations

## Requirements

- Python 3.10+
- Windows (uses `winsound` for audio; voice capture uses `sounddevice`)
- At least one LLM provider API key (OpenRouter recommended)

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/ANEUP002/Jarvis.git
cd Jarvis
```

**2. Create a virtual environment**
```bash
python -m venv venv
venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure environment variables**
```bash
copy .env.example .env
# Edit .env and add your API keys
```

The only required key is `OPENROUTER_API_KEY`. Everything else is optional.

Get a free OpenRouter key at [openrouter.ai](https://openrouter.ai).

**5. Run JARVIS**
```bash
# Terminal mode (recommended to start)
python jarvis.py

# Desktop panel with voice + HUD
python scripts/run_jarvis_desktop.py
```

## Voice Usage

| Action | What to do |
|--------|------------|
| Activate | Double-clap |
| Ask anything | Speak after activation |
| Play YouTube | "Play [song/video name]" |
| Remember something | "Remember that I work at X" |
| Check memory | "What do you know about me?" |
| Forget something | "Forget that I work at X" |

## Architecture

```
User Input
    │
    ▼
Classifier ──────────────────────────────────────┐
    │                                             │
    ▼                                             ▼
Chief Agent                              Assistant Fastlane
(complex tasks)                          (simple/local tasks)
    │
    ├──▶ Research Agent  (web search, Q&A)
    ├──▶ Code Agent      (code generation, debugging)
    └──▶ Writer Agent    (emails, documents, summaries)
```

## Project Structure

```
jarvis.py              # Terminal REPL entry point
launch.py              # Desktop panel launcher
agents/                # Research, code, writer, chief agents
app/                   # Classifier, router, state, HUD panel, learning engine
providers/             # OpenRouter, MiniMax, Groq, DeepSeek, Together, Google
tools/                 # Weather, email, todos, web search, memory, notes
scripts/               # Run modes and utilities
```

## Notes

- `memory/` and `logs/` are created at runtime and not committed to git
- Voice features require a microphone; clap detection uses `pyaudio`
- `faster-whisper` handles speech-to-text locally (no API key needed)
- Piper TTS models go in `assets/voices/piper/` (optional, falls back to Windows TTS)
