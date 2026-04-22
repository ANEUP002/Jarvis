#!/usr/bin/env python

import atexit
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import sounddevice as sd
import uvicorn


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

HEALTH_URL = "http://127.0.0.1:8000/api/health"
DASHBOARD_URL = "http://127.0.0.1:8000"


def start_orchestrator() -> subprocess.Popen | None:
    orchestrator_path = ROOT_DIR / "orchestrator.py"
    if not orchestrator_path.exists():
        print("[jarvis] orchestrator.py not found, skipping worker startup")
        return None
    process = subprocess.Popen([sys.executable, str(orchestrator_path)], cwd=str(ROOT_DIR))
    print(f"[jarvis] orchestrator worker pid={process.pid}")
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


def start_dashboard_server() -> threading.Thread:
    def _run() -> None:
        uvicorn.run("app.dashboard_server:app", host="127.0.0.1", port=8000, reload=False, log_level="info")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


def wait_for_dashboard(timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(HEALTH_URL, timeout=2) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


class ClapLauncher:
    def __init__(self) -> None:
        self.stream: sd.InputStream | None = None
        self.cooldown_until = 0.0
        self.panel_process: subprocess.Popen | None = None
        self.noise_floor = 0.015
        self.last_level_log = 0.0
        self.dashboard_opened = False

    def start(self) -> None:
        def callback(indata, frames, time_info, status):  # noqa: ARG001
            if status:
                print(f"[jarvis] audio status: {status}")
            samples = np.abs(indata[:, 0])
            peak = float(samples.max()) if samples.size else 0.0
            avg = float(samples.mean()) if samples.size else 0.0
            rms = float(np.sqrt(np.mean(np.square(indata[:, 0])))) if samples.size else 0.0
            now = time.time()
            self.noise_floor = (self.noise_floor * 0.97) + (avg * 0.03)
            transient_ratio = peak / max(self.noise_floor, 0.01)
            strong_transient = peak > 0.22 and transient_ratio > 6.0 and rms > max(0.035, self.noise_floor * 2.4)
            very_strong_hit = peak > 0.38 and rms > 0.045

            if now - self.last_level_log > 8:
                self.last_level_log = now
                print(
                    "[jarvis] mic armed "
                    f"(peak={peak:.3f} avg={avg:.3f} rms={rms:.3f} floor={self.noise_floor:.3f})"
                )

            if (strong_transient or very_strong_hit) and now > self.cooldown_until:
                self.cooldown_until = now + 1.6
                self._launch_panel()

        input_device = sd.default.device[0]
        try:
            device_info = sd.query_devices(input_device, "input")
            print(f"[jarvis] listening on microphone: {device_info['name']}")
        except Exception:
            print(f"[jarvis] listening on microphone device: {input_device}")

        try:
            self.stream = sd.InputStream(
                device=input_device,
                channels=1,
                samplerate=16000,
                blocksize=1024,
                dtype="float32",
                callback=callback,
            )
            self.stream.start()
        except Exception as exc:
            print(f"[jarvis] microphone startup failed: {exc}")
            raise

    def stop(self) -> None:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        stop_process(self.panel_process)

    def _launch_panel(self) -> None:
        if self.panel_process and self.panel_process.poll() is None:
            print("[jarvis] panel already open")
            if not self.dashboard_opened:
                self._open_dashboard()
            return
        panel_path = ROOT_DIR / "app" / "jarvis_panel.py"
        self.panel_process = subprocess.Popen(
            [sys.executable, str(panel_path)],
            cwd=str(ROOT_DIR),
        )
        self._open_dashboard()
        print("[jarvis] clap detected -> opening Jarvis panel")

    def _open_dashboard(self) -> None:
        try:
            webbrowser.open(DASHBOARD_URL, new=1)
            self.dashboard_opened = True
            print("[jarvis] opening dashboard")
        except Exception as exc:
            print(f"[jarvis] dashboard open failed: {exc}")


def main() -> None:
    orchestrator_process = start_orchestrator()
    atexit.register(stop_process, orchestrator_process)
    server_thread = start_dashboard_server()
    _ = server_thread

    if wait_for_dashboard():
        print("[jarvis] backend online")
    else:
        print("[jarvis] backend did not report ready yet, continuing anyway")

    launcher = ClapLauncher()
    atexit.register(launcher.stop)
    launcher.start()

    print("[jarvis] clap once to open the Jarvis panel")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[jarvis] shutting down")
    finally:
        launcher.stop()
        stop_process(orchestrator_process)


if __name__ == "__main__":
    main()
