"""
JARVIS Clap Detector — detects a double-clap and fires a callback.

Uses adaptive thresholding so music/TV noise doesn't trigger false claps:
- Tracks a rolling background RMS average
- A clap must be SPIKE_RATIO × above that rolling average
- A clap must be a sharp transient: energy drops back down within a few frames
  (music beats are sustained; claps are not)
"""

from __future__ import annotations

import collections
import struct
import threading
import time
from typing import Callable, Optional


# ── tunable constants ──────────────────────────────────────────────────────────
CHUNK        = 1024    # frames per read
RATE         = 44100   # sample rate Hz
CHANNELS     = 1
FORMAT_WIDTH = 2       # bytes per sample (paInt16)

MIN_THRESHOLD = 1800   # absolute floor — ignore tiny ambient noise
SPIKE_RATIO   = 3.5    # clap RMS must be this many × above background average
BG_WINDOW     = 120    # frames of background history (~2.8 s at 44100/1024)

MIN_GAP = 0.08         # min seconds between two claps
MAX_GAP = 0.6          # max seconds between two claps to count as double


def _rms(chunk_bytes: bytes) -> float:
    n = len(chunk_bytes) // 2
    if n == 0:
        return 0.0
    samples = struct.unpack(f"{n}h", chunk_bytes)
    return (sum(s * s for s in samples) / n) ** 0.5


class ClapDetector:
    def __init__(
        self,
        callback: Callable[[], None],
        min_gap: float = MIN_GAP,
        max_gap: float = MAX_GAP,
    ) -> None:
        self._callback  = callback
        self._min_gap   = min_gap
        self._max_gap   = max_gap
        self._thread: Optional[threading.Thread] = None
        self._running   = False
        self._paused    = False

    # ── public API ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="clap-detector"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def pause(self) -> None:
        """Yield the mic to voice capture — keeps stream open but skips processing."""
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    # ── internals ──────────────────────────────────────────────────────────────

    def _listen_loop(self) -> None:
        try:
            import pyaudio
        except ImportError:
            print("[CLAP] pyaudio not installed — clap detection disabled.")
            return

        pa = pyaudio.PyAudio()
        stream = None
        try:
            stream = pa.open(
                format=pa.get_format_from_width(FORMAT_WIDTH),
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
            )

            # Rolling background noise tracker
            bg_window: collections.deque = collections.deque(maxlen=BG_WINDOW)
            for _ in range(10):               # seed with a neutral estimate
                bg_window.append(float(MIN_THRESHOLD) / SPIKE_RATIO)

            last_clap_time: float = 0.0
            in_clap  = False
            # After a threshold crossing, read a few more frames to confirm
            # the energy drops (transient = clap) rather than stays up (music)
            post_spike_frames: list[float] = []
            waiting_for_drop  = False

            while self._running:
                if self._paused:
                    try:
                        stream.read(CHUNK, exception_on_overflow=False)
                    except Exception:
                        pass
                    time.sleep(0.02)
                    continue

                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                except Exception:
                    time.sleep(0.05)
                    continue

                rms = _rms(data)
                now = time.time()

                # Update background average (only when NOT in a spike)
                if not waiting_for_drop and rms < MIN_THRESHOLD * 2:
                    bg_window.append(rms)

                bg_avg = sum(bg_window) / len(bg_window)
                adaptive_threshold = max(MIN_THRESHOLD, bg_avg * SPIKE_RATIO)

                # ── Transient confirmation ──────────────────────────────────
                if waiting_for_drop:
                    post_spike_frames.append(rms)
                    if len(post_spike_frames) >= 3:
                        # A real clap: at least 2 of 3 follow-up frames
                        # must drop below the adaptive threshold
                        drops = sum(1 for r in post_spike_frames if r < adaptive_threshold)
                        waiting_for_drop = False
                        post_spike_frames = []
                        if drops >= 2:
                            # Confirmed transient — count as clap
                            gap = now - last_clap_time
                            if self._min_gap < gap < self._max_gap:
                                try:
                                    self._callback()
                                except Exception as exc:
                                    print(f"[CLAP] callback error: {exc}")
                                last_clap_time = 0.0
                            else:
                                last_clap_time = now - (len(post_spike_frames) * CHUNK / RATE)
                        # else: sustained energy → music beat, ignored
                    continue

                # ── Spike detection ─────────────────────────────────────────
                if rms > adaptive_threshold:
                    if not in_clap:
                        in_clap = True
                        waiting_for_drop   = True
                        post_spike_frames  = []
                else:
                    in_clap = False

        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            pa.terminate()
