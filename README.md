# JARVIS — Personal AI Assistant

I built this because I wanted something closer to the Iron Man JARVIS experience — a voice assistant that actually knows who you are, remembers your conversations, runs real research, writes code, and controls your computer. Not just a smart speaker that forgets everything the moment you close the app.

Double-clap to activate. Speak your request. JARVIS responds out loud and in the terminal.

## What it actually does

**Talks to you like a real assistant**
You clap twice, it listens. It answers out loud using either Piper TTS (local, fast), OpenAI TTS (higher quality), or Windows built-in voice as a fallback. No wake word, no button to press.

**Learns who you are over time**
Every conversation, JARVIS is quietly pulling out facts about you — your name, where you work, what projects you're running, who you mention. It builds a profile that persists across sessions and injects that context into every response. Ask it something a week later and it still remembers you mentioned you work at X or that you're building Y.

**Has a second brain**
Every research answer, code output, and task result gets saved as a structured note with tags, links, and backlinks between related topics, like Obsidian but automated. When you ask something in the future, it searches those notes with vector similarity and uses relevant past findings to give better answers. It builds up knowledge over time instead of starting from scratch every time.

**Does real research with live data**
For anything involving current events, news, prices, or recent information, it hits DuckDuckGo before answering. News queries get actual headlines with dates. General queries get web snippets. The LLM is told to use only the live results, not its training data.

**Controls your desktop**
Open apps, open websites, type text, click at coordinates, press keyboard shortcuts, scroll, take screenshots. Full desktop automation built in.

**Runs multiple agents in parallel for complex tasks**
Simple question → one agent answers directly. Complex task → Chief Agent breaks it into subtasks, runs Research + Code + Writer agents in parallel, then combines the results. You can watch the whole pipeline live in the HUD.

## Two ways to run it

There are two modes and it's worth understanding the difference.

`python jarvis.py` runs everything in one process. You type or speak, it classifies, routes, runs the agent, and responds — all inline. Simple, fast, no moving parts.

`python scripts/run_jarvis_desktop.py` (or `run_dashboard.py`) launches three things together: the FastAPI server, the orchestrator worker, and the desktop panel. In this mode tasks flow through a file-based queue. When you submit something via the panel or the web dashboard, it writes a JSON file to `queue/pending/`. The orchestrator is a background process that watches that folder in a loop — it picks up the file, runs the full pipeline, writes the result back to the file, and moves it to `queue/completed/`. The panel then polls for that completed result and reads it back.

This queue-based design means the system never blocks. You can submit ten tasks, the orchestrator processes them one at a time, and the HUD dashboard updates in real time as each one moves through the pipeline. The orchestrator is also what powers the event stream — every step it takes (classifier ran, model selected, agent started, result saved) gets emitted as an event that the HUD picks up.

## How it's built

```
You (clap / type)
      │
      ▼
  Classifier
  (rule-based first, LLM fallback)
      │
      ├──── Simple / local ──▶  Assistant Fastlane
      │                         (time, date, greetings,
      │                          weather, progress checks)
      │
      └──── Needs an agent ──▶  Chief Agent
                                (plans and routes the task)
                                      │
                          ┌───────────┼───────────┐
                          ▼           ▼            ▼
                    Research        Code         Writer
                     Agent          Agent         Agent
                  (web search,   (generates,   (emails,
                   Q&A, news)     debugs code)  documents,
                                               summaries)
                          │           │            │
                          └───────────┴────────────┘
                                      │
                                 Second Brain
                              (every result saved
                               as a searchable note)
```

The Classifier first tries keyword rules — fast, no LLM call. If it's confident, it skips the LLM entirely. If not, it falls back to an LLM classifier. Simple questions that start with "what", "who", "how" are always kept simple with no unnecessary multi-agent overhead.

The Chief Agent sits between the classifier and the workers. For simple tasks it just picks the right agent. For complex tasks it writes a JSON plan with subtasks, runs them in parallel threads, and combines the results.

## The Second Brain

This is probably the most underrated part of the project. Every time an agent produces a response, it saves a note automatically in the background:

Research answers get saved under `memory/notes/research/`, code outputs under `memory/notes/code/`, task results under `memory/notes/tasks/`, and emails under `memory/notes/emails/`.

Each note has a title, tags, category, creation date, and `[[wiki-style links]]` to related notes. The system maintains a backlinks index so you can see which notes reference which other notes.

When you ask a new question, before going to the LLM it does a vector similarity search over all past notes. If it finds something relevant, that context gets injected into the prompt. Over time, JARVIS gets smarter about topics you've asked about before without you having to do anything.

The vector store runs locally with sentence-transformers so no API key is needed for embeddings.

## Self-Learning

The learning engine (`app/learning.py`) runs silently on every message. It extracts facts from what you say using regex patterns — your name, employer, location, ongoing projects, people you mention. It counts topic keywords over time to build a picture of what you care about. If you ask for shorter answers or more detail, it adjusts and remembers. Conversation history is saved to disk and loaded on the next startup so JARVIS always has context from last time. You can also be explicit about it — say "remember that I'm applying for jobs", "forget that", or "what do you know about me" and it handles those directly.

The profile lives in `memory/profile/user_profile.json` and grows over time.

## Setup

You need Python 3.10+ and Windows (voice and audio use Windows-specific APIs).

```bash
git clone https://github.com/ANEUP002/Jarvis.git
cd Jarvis

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env
# Open .env and add your API keys
```

The only key you actually need is `OPENROUTER_API_KEY`. Get one free at [openrouter.ai](https://openrouter.ai) — it gives you access to GPT-4o, Gemini, Claude, and a bunch of free models all in one place.

Everything else (MiniMax, Google AI) is optional. The system falls back through providers automatically if one fails or rate limits.

```bash
# Start in terminal mode
python jarvis.py

# Start with desktop panel (clap to open panel + HUD)
python scripts/run_jarvis_desktop.py
```

## Voice commands

| Say this | What happens |
|----------|-------------|
| double clap | Activates listening |
| "Play Blinding Lights on YouTube" | Finds and opens the actual video, announces the title |
| "Open Facebook" | Opens facebook.com in your browser |
| "Open Chrome" or "Open VS Code" | Launches the app |
| "What's the weather in New York" | Live weather data |
| "Remember that I'm a CS student" | Saves to your profile |
| "What do you know about me?" | Recaps your profile |
| "Forget that I'm a CS student" | Removes it |
| "What time is it" | Instant local answer, no LLM call |
| "What are you working on?" | Shows current task progress |

## Desktop control

JARVIS has full desktop automation. These work directly in the terminal:

```
open chrome             → launches Chrome
open facebook           → opens facebook.com
open VS Code            → launches VSCode
close spotify           → kills the Spotify process
type hello world        → types text into the focused window
press ctrl+c            → sends keyboard shortcut
press win+d             → show desktop
scroll down 5           → scrolls mouse wheel
click 960 540           → clicks at screen coordinates
mouse pos               → shows current cursor position
screenshot              → saves a PNG to ~/Pictures
run <powershell cmd>    → runs any shell command
windows                 → lists all open windows
focus Chrome            → brings Chrome to front
```

## HUD Dashboard

The desktop panel shows a live architecture diagram that updates as tasks run. You can see exactly which component is active at any moment. INPUT, CLASSIFY, and CHIEF are always lit when a task is running. Whichever agent handles your request (RESEARCH, CODE, or WRITER) glows. In multi-agent mode all three can light up simultaneously for parallel tasks. The model name appears under the active agent and the task type shows under the classifier node.

The backend also runs a FastAPI server at `localhost:8000` with a web dashboard showing the task queue, recent results, event log, and note graph.

## Project structure

```
jarvis.py                   ← terminal REPL, handles everything inline in one process
orchestrator.py             ← background worker that processes the file-based task queue
launch.py                   ← desktop launcher (starts orb + server + orchestrator together)

agents/
  chief_agent.py            ← task planner, multi-agent coordinator
  research_agent.py         ← web search, Q&A, live data
  code_agent.py             ← code generation and debugging
  writer_agent.py           ← emails, documents, summaries
  note_context.py           ← loads relevant notes before each agent runs
  note_workflows.py         ← saves results to second brain after each run

app/
  classifier.py             ← rule-based task classifier
  llm_classifier.py         ← LLM fallback classifier
  assistant_fastlane.py     ← handles simple local queries without LLM
  router.py                 ← routes tasks to the right agent with model fallbacks
  learning.py               ← self-learning engine, user profile
  clap_detect.py            ← adaptive double-clap detection
  voice_input.py            ← speech recognition via Whisper
  jarvis_panel.py           ← Tkinter HUD panel with live architecture view
  jarvis_orb.py             ← animated orb UI (alternative desktop mode)
  dashboard.py              ← dashboard data API
  dashboard_server.py       ← FastAPI server for web dashboard
  event_streaming.py        ← real-time event bus for HUD updates
  model_selector.py         ← picks the right model for each task type
  state.py                  ← live system state (current agent, task, model)

providers/
  llm_provider.py           ← unified generate() used by all agents
  openrouter_provider.py    ← primary: GPT-4o, Gemini, Claude, free models
  minimax_provider.py       ← used by chief agent for planning

tools/
  notes_tools.py            ← second brain: save, search, link notes
  vector_db_advanced.py     ← local vector store with sentence-transformers
  memory_tools.py           ← key-value memory for agent state
  desktop_tools.py          ← app launcher, websites, mouse, keyboard
  weather_tools.py          ← live weather via Open-Meteo (no API key needed)
  web_search_tools.py       ← DuckDuckGo search
  email_tools.py            ← Gmail SMTP send/read
  todo_tools.py             ← local to-do list
  file_tools.py             ← read, write, search files
  code_tools.py             ← execute Python, run shell commands

scripts/
  run_jarvis_desktop.py     ← clap-to-launch desktop mode
  run_jarvis_mode.py        ← always-on terminal mode
  run_dashboard.py          ← web dashboard + orchestrator
  submit.py                 ← submit tasks via API
  rebuild_vector_index.py   ← rebuild the note embeddings index

memory/                     ← created at runtime, not in git
  profile/user_profile.json ← your personal profile
  session.json              ← last conversation session
  notes/                    ← second brain notes (auto-generated)
  events/                   ← event log for dashboard
```

## Models

JARVIS uses OpenRouter as the primary gateway, which means one API key covers GPT-4o, Gemini, Claude, Gemma, and a bunch of free models. Model selection is automatic based on task type and complexity:

| Task | Simple | Complex |
|------|--------|---------|
| Research | GPT-4o mini | GPT-4o |
| Code | GPT-4o mini | Gemma 4 31B |
| Writer | GPT-4o mini | GPT-4o |
| Chief (planner) | MiniMax M2.7 | MiniMax M2.7 |

If a model fails with a 429, 404, or timeout, it falls back to the next one automatically.

## What's not in the repo

`memory/` (your profile and notes), `logs/`, `queue/`, `vector_db/` (generated embeddings), `assets/voices/` (large model files), and `.env` (your API keys) are all gitignored. They get created automatically on first run.

## Optional voice setup

By default JARVIS uses Windows built-in TTS (Zira voice). For better quality:

**Faster Whisper** — better speech recognition, runs fully locally:
```bash
pip install faster-whisper
# downloads automatically on first use (~40MB for tiny.en)
```

**Piper TTS** — local neural voice, much better than Windows TTS:
```bash
pip install piper-tts
# download a voice from https://rhasspy.github.io/piper-samples/
# put the .onnx and .onnx.json files in assets/voices/piper/
```

**OpenAI TTS** — highest quality, needs an API key:
```bash
# add to .env:
OPENAI_API_KEY=sk-...
JARVIS_OPENAI_TTS_VOICE=coral
```
