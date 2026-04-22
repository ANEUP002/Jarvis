import json
import math
import os
import random
import re
import subprocess
import sys
import threading
import time
import tempfile
import wave
from pathlib import Path
from typing import Any, Dict, Optional

import winsound

import numpy as np
import tkinter as tk
from tkinter import ttk
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parent.parent
SNAPSHOT_URL = "http://127.0.0.1:8000/api/snapshot"
TASK_SUBMIT_URL = "http://127.0.0.1:8000/api/tasks"
TASK_DETAIL_URL = "http://127.0.0.1:8000/api/task/{task_id}"
VOICE_NAME = "Microsoft Zira Desktop"
PIPER_DIR = ROOT_DIR / "assets" / "voices" / "piper"
PIPER_MODEL_NAME = os.getenv("JARVIS_PIPER_VOICE", "en_US-lessac-medium")
PIPER_MODEL_PATH = PIPER_DIR / f"{PIPER_MODEL_NAME}.onnx"
PIPER_CONFIG_PATH = PIPER_DIR / f"{PIPER_MODEL_NAME}.onnx.json"
WHISPER_DIR = ROOT_DIR / "assets" / "voices" / "whisper"
WHISPER_MODEL_NAME = os.getenv("JARVIS_WHISPER_MODEL", "tiny.en")
OPENAI_TTS_MODEL = os.getenv("JARVIS_OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
OPENAI_TTS_VOICE = os.getenv("JARVIS_OPENAI_TTS_VOICE", "coral")
OPENAI_TTS_STYLE = os.getenv("JARVIS_OPENAI_TTS_STYLE", "Speak like a warm, polished, intelligent female assistant.")
SPEAKABLE_TYPES = {"research", "writer"}
NON_SPEAKING_KEYWORDS = {
    "code",
    "python",
    "script",
    "debug",
    "fix",
    "implement",
    "refactor",
    "terminal",
    "repository",
    "repo",
    "compile",
}
VOICE_CLOSE_PHRASES = {
    "jarvis close",
    "close panel",
    "go away",
    "dismiss",
    "close yourself",
}

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.model_selector import DEFAULT_MODEL  # noqa: E402
from app.classifier import rule_based_classify  # noqa: E402
from app.assistant_fastlane import handle_fastlane  # noqa: E402
from providers.llm_provider import generate  # noqa: E402

try:  # noqa: E402
    from openai import OpenAI
except Exception:  # noqa: E402
    OpenAI = None

try:  # noqa: E402
    from faster_whisper import WhisperModel
except Exception:  # noqa: E402
    WhisperModel = None

try:  # noqa: E402
    from piper import PiperVoice
    from piper.config import SynthesisConfig
except Exception:  # noqa: E402
    PiperVoice = None
    SynthesisConfig = None


_PIPER_VOICE = None
_PIPER_LOCK = threading.Lock()
_WHISPER_MODEL = None
_WHISPER_LOCK = threading.Lock()
_PIPER_SYNTHESIS = (
    SynthesisConfig(length_scale=1.08, noise_scale=0.52, noise_w_scale=0.68, volume=1.08)
    if SynthesisConfig is not None
    else None
)
WELCOME_LINE = "Good evening, sir. Systems are online. How may I help you?"
LISTENING_LINE = "Go ahead. I'm listening."
FOLLOWUP_LINE = "Anything else, sir?"
ACK_LINE = "Understood. I'll handle that in OfficeOS."
RUNNING_LINE = "That task is still running. I'll keep it moving in OfficeOS."
LISTEN_TIMEOUT_SECONDS = 18
DEFAULT_UI_THEME = os.getenv("JARVIS_UI_THEME", "apple_minimal").strip().lower()


def powershell_script(script: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _estimate_speech_seconds(text: str) -> float:
    words = max(1, len((text or "").split()))
    return min(12.0, max(1.6, words / 2.7))


def _get_piper_voice():
    global _PIPER_VOICE
    if _PIPER_VOICE is not None:
        return _PIPER_VOICE
    if PiperVoice is None or not PIPER_MODEL_PATH.exists() or not PIPER_CONFIG_PATH.exists():
        return None
    with _PIPER_LOCK:
        if _PIPER_VOICE is None:
            _PIPER_VOICE = PiperVoice.load(PIPER_MODEL_PATH, config_path=PIPER_CONFIG_PATH)
    return _PIPER_VOICE


def _get_whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL
    if WhisperModel is None:
        return None
    WHISPER_DIR.mkdir(parents=True, exist_ok=True)
    with _WHISPER_LOCK:
        if _WHISPER_MODEL is None:
            _WHISPER_MODEL = WhisperModel(
                WHISPER_MODEL_NAME,
                device="cpu",
                compute_type="int8",
                download_root=str(WHISPER_DIR),
            )
    return _WHISPER_MODEL


def _speak_piper(text: str) -> bool:
    voice = _get_piper_voice()
    if voice is None:
        return False
    try:
        chunks = list(voice.synthesize(text, syn_config=_PIPER_SYNTHESIS))
        if not chunks:
            return False
        sample_rate = chunks[0].sample_rate
        audio_bytes = b"".join(chunk.audio_int16_bytes for chunk in chunks)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as handle:
            temp_path = Path(handle.name)
        with wave.open(str(temp_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_bytes)
        winsound.PlaySound(str(temp_path), winsound.SND_FILENAME)
        temp_path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _speak_windows(text: str) -> None:
    escaped = text.replace("'", "''")
    script = f"""
Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$zira = $voice.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Name -eq '{VOICE_NAME}' }} | Select-Object -First 1
if ($zira) {{ $voice.SelectVoice($zira.VoiceInfo.Name) }}
$voice.Rate = 0
$voice.Volume = 100
$voice.Speak('{escaped}')
"""
    threading.Thread(target=powershell_script, args=(script,), daemon=True).start()


def _speak_openai(text: str) -> bool:
    if not os.getenv("OPENAI_API_KEY") or OpenAI is None:
        return False
    try:
        client = OpenAI()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as handle:
            temp_path = Path(handle.name)
        with client.audio.speech.with_streaming_response.create(
            model=OPENAI_TTS_MODEL,
            voice=OPENAI_TTS_VOICE,
            input=text,
            instructions=OPENAI_TTS_STYLE,
            response_format="wav",
        ) as response:
            response.stream_to_file(temp_path)
        winsound.PlaySound(str(temp_path), winsound.SND_FILENAME)
        temp_path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def speak(text: str) -> float:
    if not text or not text.strip():
        return 0.0
    duration = _estimate_speech_seconds(text)

    def _runner() -> None:
        if _speak_piper(text):
            return
        if _speak_openai(text):
            return
        _speak_windows(text)

    threading.Thread(target=_runner, daemon=True).start()
    return duration


def _capture_speech_to_wav(max_seconds: int = 18) -> Optional[Path]:
    try:
        import sounddevice as sd
    except Exception:
        return None

    sample_rate = 16000
    chunks: list[np.ndarray] = []
    pre_roll: list[np.ndarray] = []
    speech_started = False
    silence_seconds = 0.0
    deadline = time.time() + max_seconds
    quiet_threshold = 0.012
    speech_threshold = 0.028
    blocksize = 1024

    def callback(indata, frames, time_info, status):  # noqa: ARG001
        nonlocal speech_started, silence_seconds
        samples = np.copy(indata[:, 0])
        level = float(np.max(np.abs(samples))) if samples.size else 0.0

        pre_roll.append(samples)
        if len(pre_roll) > 6:
            pre_roll.pop(0)

        if not speech_started and level >= speech_threshold:
            speech_started = True
            chunks.extend(pre_roll[-4:])

        if speech_started:
            chunks.append(samples)
            if level < quiet_threshold:
                silence_seconds += len(samples) / sample_rate
            else:
                silence_seconds = 0.0

    try:
        with sd.InputStream(
            device=sd.default.device[0],
            channels=1,
            samplerate=sample_rate,
            blocksize=blocksize,
            dtype="float32",
            callback=callback,
        ):
            while time.time() < deadline:
                if speech_started and silence_seconds >= 1.5:
                    break
                time.sleep(0.05)
    except Exception:
        return None

    if not chunks:
        return None

    audio = np.concatenate(chunks)
    if audio.size < int(sample_rate * 0.35):
        return None

    audio = np.clip(audio, -1.0, 1.0)
    audio_int16 = (audio * 32767.0).astype(np.int16)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as handle:
        wav_path = Path(handle.name)

    with wave.open(str(wav_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())

    return wav_path


def recognize_once(timeout_seconds: int = 9) -> str:
    wav_path = _capture_speech_to_wav(max_seconds=timeout_seconds)
    if wav_path is None:
        return ""

    try:
        model = _get_whisper_model()
        if model is None:
            return ""
        segments, info = model.transcribe(
            str(wav_path),
            language="en",
            vad_filter=True,
            beam_size=5,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return text
    except Exception:
        return ""
    finally:
        wav_path.unlink(missing_ok=True)


def submit_task(text: str) -> Dict[str, Any]:
    payload = json.dumps({"input": text}).encode("utf-8")
    request = Request(
        TASK_SUBMIT_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def get_snapshot() -> Dict[str, Any]:
    with urlopen(SNAPSHOT_URL, timeout=3) as response:
        return json.loads(response.read().decode("utf-8"))


def get_task_record(task_id: str) -> Dict[str, Any]:
    with urlopen(TASK_DETAIL_URL.format(task_id=task_id), timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _clean_text(value: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", value or "")
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_#>-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_response_text(task_record: Dict[str, Any]) -> str:
    task = task_record.get("task", {})
    result = task.get("result") or {}
    if isinstance(result, dict):
        if isinstance(result.get("response"), str):
            return result.get("response", "")
        if isinstance(result.get("body"), str):
            return result.get("body", "")
    if isinstance(result, str):
        return result
    return ""


def _speech_summary(text: str, max_chars: int = 280) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return "I finished the task, but the result was empty."
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    compact = " ".join(sentences[:2]).strip() or cleaned
    if len(compact) > max_chars:
        compact = compact[: max_chars - 3].rstrip() + "..."
    return compact


def _build_conversational_reply(user_prompt: str, result_text: str) -> str:
    cleaned = _clean_text(result_text)
    if not cleaned:
        return "I finished the task, but there wasn't much to say back."

    prompt = f"""
You are Jarvis, a futuristic female AI assistant inspired by an elegant mission-control system.
Turn the task result into a spoken reply for the user.

Rules:
- Sound calm, refined, intelligent, and slightly cinematic.
- Keep it to 1 to 3 short sentences.
- No markdown, no bullet points, no code formatting.
- You may say "sir" once, but do not overdo it.
- Focus on directly answering the user.
- Avoid sounding robotic, salesy, or overly excited.
- Do not mention files, JSON, formatting, or internal tooling unless necessary.

User request:
{user_prompt}

Task result:
{cleaned}
""".strip()

    try:
        response = generate(prompt, model=DEFAULT_MODEL, temperature=0.5)
        spoken = _clean_text(str(response))
        if spoken:
            return spoken[:320].rstrip()
    except Exception:
        pass
    return _speech_summary(cleaned)


def should_speak_result(task_text: str) -> bool:
    lowered = (task_text or "").lower()
    if any(keyword in lowered for keyword in NON_SPEAKING_KEYWORDS):
        return False
    classification = rule_based_classify(lowered)
    if classification.get("complexity") == "complex":
        return False
    return classification.get("type") in SPEAKABLE_TYPES or classification.get("type") == "unknown"


class SpeechLevelMonitor:
    def __init__(self) -> None:
        self.stream: Optional["sd.InputStream"] = None
        self.level = 0.0

    def start(self) -> None:
        if self.stream is not None:
            return

        def callback(indata, frames, time_info, status):  # noqa: ARG001
            try:
                samples = np.abs(indata[:, 0])
                peak = float(samples.max()) if samples.size else 0.0
                avg = float(samples.mean()) if samples.size else 0.0
                target = min(1.0, (peak * 1.7) + (avg * 4.5))
                self.level = (self.level * 0.65) + (target * 0.35)
            except Exception:
                pass

        try:
            import sounddevice as sd  # local import to keep panel load resilient

            self.stream = sd.InputStream(
                device=sd.default.device[0],
                channels=1,
                samplerate=16000,
                blocksize=1024,
                dtype="float32",
                callback=callback,
            )
            self.stream.start()
        except Exception:
            self.stream = None

    def stop(self) -> None:
        self.level = 0.0
        if self.stream is None:
            return
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass
        self.stream = None


class ClapDetector:
    def __init__(self, on_clap) -> None:
        self.on_clap = on_clap
        self.stream: Optional["sd.InputStream"] = None
        self.cooldown_until = 0.0
        self.noise_floor = 0.015

    def start(self) -> None:
        if self.stream is not None:
            return

        def callback(indata, frames, time_info, status):  # noqa: ARG001
            samples = np.abs(indata[:, 0])
            peak = float(samples.max()) if samples.size else 0.0
            avg = float(samples.mean()) if samples.size else 0.0
            rms = float(np.sqrt(np.mean(np.square(indata[:, 0])))) if samples.size else 0.0
            now = time.time()
            self.noise_floor = (self.noise_floor * 0.97) + (avg * 0.03)
            transient_ratio = peak / max(self.noise_floor, 0.01)
            strong_transient = peak > 0.22 and transient_ratio > 6.0 and rms > max(0.035, self.noise_floor * 2.4)
            very_strong_hit = peak > 0.38 and rms > 0.045
            if (strong_transient or very_strong_hit) and now > self.cooldown_until:
                self.cooldown_until = now + 1.6
                self.on_clap()

        try:
            import sounddevice as sd

            self.stream = sd.InputStream(
                device=sd.default.device[0],
                channels=1,
                samplerate=16000,
                blocksize=1024,
                dtype="float32",
                callback=callback,
            )
            self.stream.start()
        except Exception:
            self.stream = None

    def stop(self) -> None:
        if self.stream is None:
            return
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass
        self.stream = None


class JarvisPanel:
    def __init__(self, root: tk.Tk, auto_listen: bool = False):
        self.root = root
        self.root.title("Jarvis")
        self.ui_theme = DEFAULT_UI_THEME if DEFAULT_UI_THEME in {"apple_minimal", "cinematic"} else "apple_minimal"
        if self.ui_theme == "apple_minimal":
            self.root.geometry("700x840")
            self.root.minsize(660, 800)
            self.root.configure(bg="#0b1118")
        else:
            self.root.geometry("760x860")
            self.root.minsize(700, 820)
            self.root.configure(bg="#03070f")
        self.root.protocol("WM_DELETE_WINDOW", self.dismiss)

        self.running = True
        self.listening = False
        self.processing = False
        self.auto_listen = auto_listen
        self.anim_phase = 0.0
        self.audio_level = 0.0
        self.voice_level = 0.0
        self.speaking_until = 0.0
        self.ready_after = 0.0
        self.scan_angle = 0.0
        self.particles: list[dict[str, float]] = []
        self.node_angles = np.linspace(0, 2 * np.pi, 24, endpoint=False)
        self.snapshot_data: Dict[str, Any] = {}
        self.followup_after_id: str | None = None
        self.level_monitor = SpeechLevelMonitor()
        self.clap_detector = ClapDetector(lambda: self.root.after(0, self._handle_ready_clap))

        self.arch_state: Dict[str, Any] = {}

        self.status_var = tk.StringVar(value="Ready")
        self.queue_var = tk.StringVar(value="Pending 0 | Progress 0 | Done 0")
        self.task_var = tk.StringVar(value="No active mission")
        self.transcript_var = tk.StringVar(value=WELCOME_LINE)
        self.motion_state_var = tk.StringVar(value="STANDBY")

        self._build_ui()
        self._init_visual_system()
        threading.Thread(target=self._poll_snapshot_loop, daemon=True).start()
        self._animate()

        self.root.after(250, self._bring_to_front)
        self.root.after(450, self._welcome)
        self.root.after(600, self._arm_clap_detector)
        if self.auto_listen:
            self.root.after(250, lambda: self._set_status("Ready"))

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        if self.ui_theme == "apple_minimal":
            self.surface_bg = "#0b1118"
            self.panel_bg = "#101a25"
            self.card_bg = "#121f2b"
            self.border_color = "#2a3e53"
            self.primary_text = "#e9f2fb"
            self.secondary_text = "#9eb6cb"
            self.accent_text = "#9bd6ff"
            canvas_width = 660
            canvas_height = 340
            title_suffix = "APPLE MINIMAL"
            title_font = ("Segoe UI Semibold", 33, "bold")
            subtitle_font = ("Segoe UI", 11)
            style.configure("Jarvis.TButton", foreground="#e9f2fb", background="#1b2d3d", borderwidth=0, focusthickness=0)
            style.map("Jarvis.TButton", background=[("active", "#294258")])
        else:
            self.surface_bg = "#03070f"
            self.panel_bg = "#06111b"
            self.card_bg = "#06111b"
            self.border_color = "#1e4661"
            self.primary_text = "#f2f9ff"
            self.secondary_text = "#6b9cb9"
            self.accent_text = "#79cfff"
            canvas_width = 700
            canvas_height = 390
            title_suffix = "NEURAL VOICE CORE"
            title_font = ("Segoe UI Semibold", 34, "bold")
            subtitle_font = ("Consolas", 12, "bold")
            style.configure("Jarvis.TButton", foreground="#dff6ff", background="#10364b", borderwidth=0, focusthickness=0)
            style.map("Jarvis.TButton", background=[("active", "#1a5170")])

        outer = tk.Frame(self.root, bg=self.surface_bg)
        outer.pack(fill="both", expand=True, padx=20, pady=18)

        title_row = tk.Frame(outer, bg=self.surface_bg)
        title_row.pack(fill="x")
        tk.Label(
            title_row,
            text="JARVIS",
            fg=self.primary_text,
            bg=self.surface_bg,
            font=title_font,
        ).pack(side="left")
        tk.Label(
            title_row,
            text=title_suffix,
            fg=self.accent_text,
            bg=self.surface_bg,
            font=subtitle_font,
        ).pack(side="left", padx=(12, 0), pady=(16, 0))

        status_strip = tk.Frame(outer, bg=self.surface_bg)
        status_strip.pack(fill="x", pady=(8, 6))
        tk.Label(
            status_strip,
            text="MOTION",
            fg=self.secondary_text,
            bg=self.surface_bg,
            font=("Consolas", 10),
        ).pack(side="left")
        tk.Label(
            status_strip,
            textvariable=self.motion_state_var,
            fg=self.accent_text,
            bg=self.surface_bg,
            font=("Consolas", 10, "bold"),
        ).pack(side="left", padx=(8, 0))
        tk.Label(
            status_strip,
            text="CLAP TO ACTIVATE VOICE CAPTURE",
            fg=self.secondary_text,
            bg=self.surface_bg,
            font=("Consolas", 10),
        ).pack(side="right")

        self.canvas = tk.Canvas(
            outer,
            width=canvas_width,
            height=canvas_height,
            bg=self.panel_bg,
            highlightthickness=1,
            highlightbackground=self.border_color,
        )
        self.canvas.pack(fill="x", pady=(8, 16))

        cards = tk.Frame(outer, bg=self.surface_bg)
        cards.pack(fill="x")
        self._info_card(cards, "STATUS", self.status_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._info_card(cards, "ACTIVE TASK", self.task_var).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self._info_card(cards, "SYSTEM QUEUE", self.queue_var).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        cards.grid_columnconfigure(0, weight=1)
        cards.grid_columnconfigure(1, weight=1)

        arch_shell = tk.Frame(outer, bg=self.panel_bg, highlightthickness=1, highlightbackground=self.border_color)
        arch_shell.pack(fill="x", pady=(10, 0))
        tk.Label(
            arch_shell,
            text="ARCHITECTURE",
            fg=self.secondary_text,
            bg=self.panel_bg,
            font=("Consolas", 10, "bold"),
        ).pack(anchor="w", padx=14, pady=(8, 2))
        self.arch_canvas = tk.Canvas(
            arch_shell,
            height=140,
            bg=self.panel_bg,
            highlightthickness=0,
        )
        self.arch_canvas.pack(fill="x", padx=10, pady=(0, 8))

        transcript_shell = tk.Frame(outer, bg=self.panel_bg, highlightthickness=1, highlightbackground=self.border_color)
        transcript_shell.pack(fill="both", expand=True, pady=(10, 12))
        tk.Label(
            transcript_shell,
            text="MISSION DIALOGUE",
            fg=self.secondary_text,
            bg=self.panel_bg,
            font=("Consolas", 11, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 4))
        self.transcript_label = tk.Label(
            transcript_shell,
            textvariable=self.transcript_var,
            fg=self.primary_text,
            bg=self.panel_bg,
            justify="left",
            anchor="nw",
            wraplength=640 if self.ui_theme == "apple_minimal" else 680,
            font=("Segoe UI", 15),
        )
        self.transcript_label.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        controls = tk.Frame(outer, bg=self.surface_bg)
        controls.pack(fill="x")
        ttk.Button(controls, text="Dismiss", style="Jarvis.TButton", command=self.dismiss).pack(side="right")

    def _init_visual_system(self) -> None:
        width = int(self.canvas.winfo_reqwidth() or 700)
        height = int(self.canvas.winfo_reqheight() or 390)
        self.particles = []
        particle_count = 58 if self.ui_theme == "apple_minimal" else 120
        for _ in range(particle_count):
            self.particles.append(
                {
                    "x": random.uniform(0, width),
                    "y": random.uniform(0, height),
                    "vx": random.uniform(-0.04, 0.04) if self.ui_theme == "apple_minimal" else random.uniform(-0.08, 0.08),
                    "vy": random.uniform(0.01, 0.08) if self.ui_theme == "apple_minimal" else random.uniform(0.02, 0.2),
                    "size": random.uniform(0.8, 2.0) if self.ui_theme == "apple_minimal" else random.uniform(0.8, 2.8),
                    "alpha": random.uniform(0.2, 0.95),
                }
            )

    def _info_card(self, parent: tk.Widget, title: str, variable: tk.StringVar) -> tk.Frame:
        frame = tk.Frame(parent, bg=self.card_bg, highlightthickness=1, highlightbackground=self.border_color)
        tk.Label(
            frame,
            text=title,
            fg=self.secondary_text,
            bg=self.card_bg,
            font=("Consolas", 10, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 2))
        tk.Label(
            frame,
            textvariable=variable,
            fg=self.primary_text,
            bg=self.card_bg,
            wraplength=300,
            justify="left",
            font=("Segoe UI Semibold", 13),
        ).pack(anchor="w", padx=10, pady=(0, 10))
        return frame

    def _bring_to_front(self) -> None:
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(1200, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except Exception:
            pass

    def _welcome(self) -> None:
        self.transcript_var.set(f"Jarvis:\n{WELCOME_LINE}")
        self._say(WELCOME_LINE)
        self.ready_after = self.speaking_until + 1.5

    def _arm_clap_detector(self) -> None:
        if not self.running or self.listening or self.processing:
            return
        block_until = max(self.speaking_until, self.ready_after)
        if time.time() < block_until:
            wait_ms = int((block_until - time.time()) * 1000) + 150
            self.root.after(max(wait_ms, 150), self._arm_clap_detector)
            return
        self.clap_detector.start()

    def _handle_ready_clap(self) -> None:
        if self.listening or self.processing or time.time() < max(self.speaking_until, self.ready_after):
            return
        self.start_listening()

    def _set_status(self, value: str) -> None:
        self.status_var.set(value)

    def _say(self, text: str) -> float:
        duration = speak(text)
        self.speaking_until = max(self.speaking_until, time.time() + duration + 0.5)
        return duration

    def start_listening(self) -> None:
        if self.listening or self.processing:
            return
        if time.time() < self.speaking_until:
            wait_ms = int((self.speaking_until - time.time()) * 1000) + 150
            self.root.after(max(wait_ms, 150), self.start_listening)
            return
        self._cancel_followup()
        self.clap_detector.stop()
        self.listening = True
        self.level_monitor.start()
        self._set_status("Listening")
        self.transcript_var.set("Jarvis:\nListening...")
        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
        threading.Thread(target=self._listen_once, daemon=True).start()

    def stop_listening(self) -> None:
        self.listening = False
        self.level_monitor.stop()
        if not self.processing:
            self._set_status("Ready")
            self.root.after(250, self._arm_clap_detector)

    def dismiss(self) -> None:
        self.running = False
        self._cancel_followup()
        self.level_monitor.stop()
        self.clap_detector.stop()
        self.root.destroy()

    def _cancel_followup(self) -> None:
        if self.followup_after_id:
            try:
                self.root.after_cancel(self.followup_after_id)
            except Exception:
                pass
            self.followup_after_id = None

    def _queue_followup(self, prompt: str = FOLLOWUP_LINE) -> None:
        if not self.running:
            return
        self._cancel_followup()
        self.transcript_var.set(f"Jarvis:\n{prompt}")
        self._set_status("Ready")

    def _listen_once(self) -> None:
        try:
            heard = recognize_once(timeout_seconds=LISTEN_TIMEOUT_SECONDS)
            if not self.listening:
                return
            if not heard:
                self.root.after(0, lambda: self.transcript_var.set("Jarvis:\nI didn't catch that. Clap and try again."))
                return

            lowered = heard.lower().strip()
            if lowered in VOICE_CLOSE_PHRASES:
                self.root.after(0, lambda: self.transcript_var.set("Closing Jarvis panel."))
                self.root.after(0, lambda: self._say("Closing the panel. Standing by."))
                self.root.after(400, self.dismiss)
                return

            fastlane_result = handle_fastlane(heard)
            if fastlane_result and fastlane_result.get("handled"):
                response = fastlane_result.get("response", "")
                self.root.after(
                    0,
                    lambda: self.transcript_var.set(
                        f"You said:\n{heard}\n\nJarvis:\n{response}\n\nClap for another request."
                    ),
                )
                self.root.after(0, lambda text=response: self._say(text))
                return

            self.root.after(0, lambda: self.transcript_var.set(f"You said:\n{heard}\n\nJarvis is thinking..."))
            task_response = submit_task(heard)
            task_id = task_response.get("task_id")

            if not task_id:
                self.root.after(0, lambda: self.transcript_var.set("The task was submitted, but tracking was unavailable."))
                return

            if should_speak_result(heard):
                self.processing = True
                self.root.after(0, lambda: self._set_status("Processing"))
                self.root.after(0, lambda: self._say("One moment."))
                threading.Thread(target=self._wait_and_speak_result, args=(task_id, heard), daemon=True).start()
            else:
                self.root.after(
                    0,
                    lambda: self.transcript_var.set(
                        f"You said:\n{heard}\n\nTask {task_id} is running in OfficeOS."
                    ),
                )
                self.root.after(0, lambda: self._say(ACK_LINE))
        except Exception as exc:
            self.root.after(0, lambda: self.transcript_var.set(f"Voice error:\n{exc}"))
        finally:
            self.root.after(0, self.stop_listening)

    def _wait_and_speak_result(self, task_id: str, original_prompt: str) -> None:
        start = time.time()
        last_status = ""
        try:
            while self.running and (time.time() - start) < 120:
                try:
                    record = get_task_record(task_id)
                except Exception:
                    time.sleep(1.5)
                    continue

                task = record.get("task", {})
                status = task.get("status", "")
                if status != last_status:
                    last_status = status
                    self.root.after(0, lambda s=status: self._set_status(s.title() if s else "Processing"))

                if status == "completed":
                    response_text = _extract_response_text(record)
                    spoken = _build_conversational_reply(original_prompt, response_text)
                    self.root.after(
                        0,
                        lambda: self.transcript_var.set(
                            f"You said:\n{original_prompt}\n\nJarvis:\n{spoken}"
                        ),
                    )
                    self.root.after(0, lambda text=spoken: self._say(text))
                    self.root.after(0, lambda: self.transcript_var.set(
                        f"You said:\n{original_prompt}\n\nJarvis:\n{spoken}\n\nClap for another request."
                    ))
                    return

                if status == "failed":
                    error_text = task.get("error") or "The task failed."
                    spoken = _speech_summary(error_text, max_chars=160)
                    self.root.after(
                        0,
                        lambda: self.transcript_var.set(
                            f"You said:\n{original_prompt}\n\nJarvis:\n{spoken}"
                        ),
                    )
                    self.root.after(0, lambda: self._say("I wasn't able to complete that task."))
                    return

                time.sleep(1.5)

            self.root.after(
                0,
                lambda: self.transcript_var.set(
                    f"You said:\n{original_prompt}\n\nThe task is still running in OfficeOS.\n\nClap for another request."
                ),
            )
            self.root.after(0, lambda: self._say(RUNNING_LINE))
        finally:
            self.processing = False
            if self.running:
                self.root.after(0, lambda: self._set_status("Ready"))

    def _poll_snapshot_loop(self) -> None:
        while self.running:
            try:
                self.snapshot_data = get_snapshot()
                self.root.after(0, self._apply_snapshot)
            except URLError:
                pass
            except Exception:
                pass
            time.sleep(2)

    def _apply_snapshot(self) -> None:
        state = self.snapshot_data.get("state", {})
        queue_data = self.snapshot_data.get("queue", {})
        current_task = state.get("current_task") or "No active mission"
        self.task_var.set(str(current_task))
        self.queue_var.set(
            f"Pending {queue_data.get('pending', 0)} | "
            f"Progress {queue_data.get('in_progress', 0)} | "
            f"Done {queue_data.get('completed', 0)}"
        )
        self.arch_state = {
            "agent": state.get("current_agent"),
            "status": state.get("status", "idle"),
            "model": state.get("current_model"),
            "subtasks": state.get("active_subtasks") or [],
            "classification": state.get("current_classification") or {},
        }

    def _draw_architecture(self) -> None:
        c = self.arch_canvas
        c.delete("all")
        width = int(c.winfo_width() or 620)
        height = 140

        agent = (self.arch_state.get("agent") or "").lower()
        status = self.arch_state.get("status", "idle")
        model = self.arch_state.get("model") or ""
        subtasks = self.arch_state.get("subtasks") or []
        classification = self.arch_state.get("classification") or {}
        task_type = classification.get("type", "")
        complexity = classification.get("complexity", "")

        running = status == "running"
        pulse = 0.5 + 0.5 * abs(math.sin(self.anim_phase * 2.5))

        # node layout: (id, display_label, x_fraction, y_fraction)
        nodes = [
            ("input",      "INPUT",     0.05, 0.50),
            ("classifier", "CLASSIFY",  0.22, 0.50),
            ("chief",      "CHIEF",     0.42, 0.50),
            ("research",   "RESEARCH",  0.70, 0.18),
            ("code",       "CODE",      0.70, 0.52),
            ("writer",     "WRITER",    0.70, 0.85),
        ]
        edges = [
            ("input", "classifier"),
            ("classifier", "chief"),
            ("chief", "research"),
            ("chief", "code"),
            ("chief", "writer"),
        ]

        # determine which nodes are active
        active_nodes: set[str] = set()
        if running:
            active_nodes.update({"input", "classifier", "chief"})
            if agent in {"research", "code", "writer"}:
                active_nodes.add(agent)
            elif subtasks:
                for st in subtasks:
                    t = (st.get("task_type") or "").lower()
                    if t in {"research", "code", "writer"}:
                        active_nodes.add(t)

        node_w, node_h = 72, 26
        positions: dict[str, tuple[int, int]] = {}
        for nid, _label, xf, yf in nodes:
            positions[nid] = (int(width * xf), int(height * yf))

        # draw edges
        for src, dst in edges:
            sx, sy = positions[src]
            dx, dy = positions[dst]
            both_active = src in active_nodes and dst in active_nodes
            color = "#3ab0f0" if both_active else "#1e3d55"
            lw = 2 if both_active else 1
            c.create_line(
                sx + node_w // 2, sy,
                dx - node_w // 2, dy,
                fill=color, width=lw, arrow=tk.LAST, arrowshape=(6, 8, 3),
            )

        # draw nodes
        for nid, label, _xf, _yf in nodes:
            nx, ny = positions[nid]
            x1, y1 = nx - node_w // 2, ny - node_h // 2
            x2, y2 = nx + node_w // 2, ny + node_h // 2
            is_active = nid in active_nodes
            if is_active:
                glow = int(58 + pulse * 80)
                outline_col = f"#{glow:02x}{int(176 + pulse * 60):02x}f0"
                fill_col = "#0f3048"
                text_col = "#c8eeff"
                lw = 2
            else:
                outline_col = "#1e3d55"
                fill_col = "#0e1d2b"
                text_col = "#4a6b82"
                lw = 1
            c.create_rectangle(x1, y1, x2, y2, fill=fill_col, outline=outline_col, width=lw)
            c.create_text(nx, ny, text=label, fill=text_col, font=("Consolas", 8, "bold"))

        # model name below active agent node
        if running and agent in {"research", "code", "writer"} and model:
            nx, ny = positions[agent]
            short = model.split("/")[-1][:20]
            c.create_text(nx, ny + node_h // 2 + 9, text=short, fill="#5a9ab8", font=("Consolas", 7))

        # task type + complexity below classifier
        if task_type:
            nx, ny = positions["classifier"]
            label = task_type.upper() + (f" · {complexity}" if complexity else "")
            c.create_text(nx, ny + node_h // 2 + 9, text=label, fill="#5a9ab8", font=("Consolas", 7))

        # subtask count above chief
        if subtasks:
            nx, ny = positions["chief"]
            c.create_text(nx, ny - node_h // 2 - 8, text=f"{len(subtasks)} subtask{'s' if len(subtasks) != 1 else ''}", fill="#4a9fb8", font=("Consolas", 7))

        # status label top-right
        status_label = "RUNNING" if running else "IDLE"
        status_color = "#3ab0f0" if running else "#2a4d62"
        c.create_text(width - 8, 10, text=status_label, fill=status_color, font=("Consolas", 8, "bold"), anchor="e")

    def _animate(self) -> None:
        if self.ui_theme == "apple_minimal":
            self.anim_phase += 0.022
            self.scan_angle = (self.scan_angle + 0.55) % 360
        else:
            self.anim_phase += 0.036
            self.scan_angle = (self.scan_angle + 1.2) % 360
        voice_level = self.level_monitor.level if self.listening else 0.0
        target = 0.08
        if self.listening:
            target = max(0.18, voice_level)
        elif self.processing:
            target = 0.3
        self.audio_level = (self.audio_level * 0.82) + (target * 0.18)

        if self.listening:
            self.motion_state_var.set("VOICE-LIVE")
        elif self.processing:
            self.motion_state_var.set("ANALYZING")
        else:
            self.motion_state_var.set("IDLE-TRACK")

        if self.ui_theme == "apple_minimal":
            self.canvas.delete("all")
            width = int(self.canvas.winfo_width() or 660)
            height = int(self.canvas.winfo_height() or 340)
            cx, cy = width / 2, height / 2 - 8

            self.canvas.create_rectangle(0, 0, width, height, fill="#101a25", outline="")
            self.canvas.create_oval(cx - 245, cy - 150, cx + 245, cy + 150, fill="#142130", outline="")
            self.canvas.create_oval(cx - 170, cy - 100, cx + 170, cy + 100, fill="#182738", outline="")

            # Minimal particle shimmer
            for particle in self.particles:
                particle["x"] += particle["vx"]
                particle["y"] += particle["vy"]
                if particle["x"] < -8:
                    particle["x"] = width + 8
                elif particle["x"] > width + 8:
                    particle["x"] = -8
                if particle["y"] > height + 8:
                    particle["y"] = -8
                    particle["x"] = random.uniform(0, width)
                size = particle["size"]
                tint = "#5f7b92" if particle["alpha"] < 0.55 else "#9ec4df"
                self.canvas.create_oval(
                    particle["x"] - size,
                    particle["y"] - size,
                    particle["x"] + size,
                    particle["y"] + size,
                    fill=tint,
                    outline="",
                )

            # Glass rings
            ring_outer = 88 + (self.audio_level * 10)
            ring_mid = 62 + (self.audio_level * 7)
            ring_inner = 38 + (self.audio_level * 4)
            self.canvas.create_oval(cx - ring_outer, cy - ring_outer, cx + ring_outer, cy + ring_outer, outline="#3d5e77", width=1)
            self.canvas.create_oval(cx - ring_mid, cy - ring_mid, cx + ring_mid, cy + ring_mid, outline="#86badf", width=2)
            self.canvas.create_oval(cx - ring_inner, cy - ring_inner, cx + ring_inner, cy + ring_inner, fill="#203648", outline="#d8e8f5", width=1)

            # Soft sweep
            sweep_radius = ring_outer + 8
            self.canvas.create_arc(
                cx - sweep_radius,
                cy - sweep_radius,
                cx + sweep_radius,
                cy + sweep_radius,
                start=self.scan_angle,
                extent=24,
                style="arc",
                outline="#b8dbf4",
                width=2,
            )
            self.canvas.create_text(cx, cy, text="J", fill="#f3f8fc", font=("Segoe UI Semibold", 28))

            status_text = "LISTENING" if self.listening else ("PROCESSING" if self.processing else "READY")
            self.canvas.create_text(cx, 26, text=status_text, fill="#9fb8ca", font=("Segoe UI", 10))

            waveform_y = height - 46
            if self.listening:
                for step in range(54):
                    phase = self.anim_phase * 4.4 + step * 0.24
                    magnitude = 2 + abs(np.sin(phase)) * (4 + voice_level * 58)
                    x = 52 + step * ((width - 104) / 53)
                    self.canvas.create_line(x, waveform_y + magnitude, x, waveform_y - magnitude, fill="#c7dff1", width=2)
            elif self.processing:
                for step in range(28):
                    phase = self.anim_phase * 3.2 + step * 0.4
                    magnitude = 2 + abs(np.sin(phase)) * 5
                    x = 94 + step * ((width - 188) / 27)
                    self.canvas.create_line(x, waveform_y + magnitude, x, waveform_y - magnitude, fill="#95b8d0", width=2)
            else:
                self.canvas.create_line(88, waveform_y, width - 88, waveform_y, fill="#405f76", width=2)
                for step in range(10):
                    x = 140 + step * ((width - 280) / 9)
                    dot = 1.8 + abs(np.sin(self.anim_phase * 1.1 + step * 0.25)) * 1.2
                    self.canvas.create_oval(x - dot, waveform_y - dot, x + dot, waveform_y + dot, fill="#6f90a8", outline="")

            self._draw_architecture()
            if self.running:
                self.root.after(40, self._animate)
            return

        self.canvas.delete("all")
        width = int(self.canvas.winfo_width() or 700)
        height = int(self.canvas.winfo_height() or 390)
        cx, cy = width / 2, height / 2 - 14

        self.canvas.create_rectangle(0, 0, width, height, fill="#06111b", outline="")
        self.canvas.create_oval(cx - 290, cy - 180, cx + 290, cy + 180, fill="#0a1a28", outline="")
        self.canvas.create_oval(cx - 210, cy - 130, cx + 210, cy + 130, fill="#0f2434", outline="")

        for i in range(8):
            offset = i * 38
            y = height - 16 - offset + (np.sin(self.anim_phase + i * 0.45) * 1.5)
            self.canvas.create_line(22 + i * 4, y, width - 22 - i * 4, y, fill="#103247", width=1)
        for i in range(12):
            x = 40 + i * ((width - 80) / 11)
            self.canvas.create_line(x, height - 12, cx, cy + 24, fill="#0f2d40", width=1)

        for particle in self.particles:
            particle["x"] += particle["vx"]
            particle["y"] += particle["vy"]
            if particle["x"] < -10:
                particle["x"] = width + 10
            elif particle["x"] > width + 10:
                particle["x"] = -10
            if particle["y"] > height + 10:
                particle["y"] = -10
                particle["x"] = random.uniform(0, width)

            shimmer = 0.55 + (np.sin(self.anim_phase * 2.3 + particle["x"] * 0.015) * 0.45)
            tint = "#7ccfff" if shimmer > 0.5 else "#3d7ea6"
            size = particle["size"]
            x = particle["x"]
            y = particle["y"]
            self.canvas.create_oval(x - size, y - size, x + size, y + size, fill=tint, outline="")

        ring_color = "#aef2ff" if self.listening else "#74d0f2"
        accent_color = "#ffd7a8"
        core_glow = 84 + (self.audio_level * 40)
        outer = 128 + (self.audio_level * 18)
        middle = 94 + (self.audio_level * 14)
        inner = 44 + (self.audio_level * 10)

        self.canvas.create_oval(cx - core_glow, cy - core_glow, cx + core_glow, cy + core_glow, fill="#123247", outline="")
        self.canvas.create_oval(cx - outer, cy - outer, cx + outer, cy + outer, outline="#1b4d69", width=1)
        self.canvas.create_oval(cx - middle, cy - middle, cx + middle, cy + middle, outline=ring_color, width=2)
        self.canvas.create_oval(cx - inner, cy - inner, cx + inner, cy + inner, fill="#1a4258", outline=accent_color, width=2)

        for index, extent in enumerate((34, 18, 12)):
            start = self.scan_angle + (index * 22)
            radius = outer - (index * 20)
            self.canvas.create_arc(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                start=start,
                extent=extent,
                style="arc",
                outline="#8edcff" if index == 0 else "#2f7ca1",
                width=2 if index == 0 else 1,
            )

        for idx, angle in enumerate(self.node_angles):
            theta = angle + (self.anim_phase * 0.65)
            r = middle + (6 * np.sin(self.anim_phase + idx * 0.28))
            nx = cx + np.cos(theta) * r
            ny = cy + np.sin(theta) * r
            dot = 2.0 + (1.4 * abs(np.sin(self.anim_phase * 1.2 + idx)))
            self.canvas.create_oval(nx - dot, ny - dot, nx + dot, ny + dot, fill="#b7efff", outline="")

        self.canvas.create_text(cx, cy, text="J", fill="#f4fbff", font=("Segoe UI Semibold", 30))

        status_text = "LISTENING" if self.listening else ("PROCESSING" if self.processing else "READY")
        self.canvas.create_text(cx, 30, text=status_text, fill="#9bc7df", font=("Consolas", 11, "bold"))

        waveform_y = height - 52
        if self.listening:
            for step in range(70):
                phase = self.anim_phase * 5.0 + step * 0.31
                magnitude = 3 + abs(np.sin(phase)) * (5 + voice_level * 90)
                x = 26 + step * ((width - 52) / 69)
                color = "#ffd8ae" if step % 2 == 0 else "#8ddfff"
                self.canvas.create_line(x, waveform_y + magnitude, x, waveform_y - magnitude, fill=color, width=2)
        elif self.processing:
            for step in range(40):
                phase = self.anim_phase * 2.6 + step * 0.45
                magnitude = 2 + abs(np.sin(phase)) * 8
                x = 70 + step * ((width - 140) / 39)
                self.canvas.create_line(x, waveform_y + magnitude, x, waveform_y - magnitude, fill="#7dc9ee", width=2)
        else:
            self.canvas.create_line(70, waveform_y, width - 70, waveform_y, fill="#1e4d68", width=2)
            for step in range(16):
                x = 100 + step * ((width - 200) / 15)
                pulse = 2 + abs(np.sin(self.anim_phase * 1.4 + step * 0.3)) * 2
                self.canvas.create_oval(x - pulse, waveform_y - pulse, x + pulse, waveform_y + pulse, fill="#296584", outline="")

        self._draw_architecture()
        if self.running:
            self.root.after(40, self._animate)


def run(auto_listen: bool = False) -> None:
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        style.theme_use("clam")
    except Exception:
        pass
    JarvisPanel(root, auto_listen=auto_listen)
    root.mainloop()


if __name__ == "__main__":
    auto = "--auto-listen" in sys.argv
    run(auto_listen=auto)
