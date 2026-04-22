"""
JARVIS Voice Input — Speech-to-Text
Uses Google STT via SpeechRecognition (free, online, very accurate).
Falls back to offline Sphinx if no internet.

Usage:
    from app.voice_input import listen
    text = listen()          # blocks until speech detected
    text = listen(timeout=5) # stop waiting after 5s of silence
"""

import threading
from typing import Optional

# Lazy-load so the module imports fast even if mic isn't needed
_sr = None
_recognizer = None
_mic = None
_lock = threading.Lock()


def _load():
    global _sr, _recognizer, _mic
    if _sr is not None:
        return True
    try:
        import speech_recognition as sr
        _sr = sr
        _recognizer = sr.Recognizer()
        # Faster response — don't wait too long for silence
        _recognizer.pause_threshold = 1.8       # seconds of silence to end phrase
        _recognizer.phrase_threshold = 0.3      # min seconds of speech to record
        _recognizer.non_speaking_duration = 0.9
        _recognizer.energy_threshold = 300      # will be auto-adjusted on calibration
        _recognizer.dynamic_energy_threshold = True
        _mic = sr.Microphone()
        return True
    except Exception as exc:
        print(f"[VOICE] Failed to initialise: {exc}")
        return False


def calibrate(duration: float = 0.5) -> None:
    """Adjust for ambient noise. Call once on startup."""
    if not _load():
        return
    try:
        with _mic as source:
            _recognizer.adjust_for_ambient_noise(source, duration=duration)
    except Exception:
        pass


def listen(
    timeout: int = 8,
    phrase_limit: int = 15,
    language: str = "en-US",
) -> Optional[str]:
    """
    Listen for one spoken phrase and return the transcription.

    Args:
        timeout:      Seconds to wait for speech to start (None = wait forever)
        phrase_limit: Max seconds to record a single phrase
        language:     BCP-47 language code (e.g. "en-US", "en-IN")

    Returns:
        Transcribed string, or None on failure/silence.
    """
    if not _load():
        return None

    with _lock:
        try:
            with _mic as source:
                audio = _recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_limit,
                )

            # Try Google first (best quality, free)
            try:
                text = _recognizer.recognize_google(audio, language=language)
                return text.strip()
            except _sr.UnknownValueError:
                return None          # heard nothing recognisable
            except _sr.RequestError:
                pass                 # no internet — try offline

            # Offline fallback (CMU Sphinx — lower accuracy)
            try:
                text = _recognizer.recognize_sphinx(audio)
                return text.strip()
            except Exception:
                return None

        except _sr.WaitTimeoutError:
            return None              # no speech within timeout
        except Exception as exc:
            print(f"[VOICE] listen error: {exc}")
            return None
