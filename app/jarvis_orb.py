"""
JARVIS Orb — Premium animated GUI overlay.
Always-on-top, borderless, draggable dark window with a large animated orb.

States: idle | listening | thinking | speaking | error

Usage:
    from app.jarvis_orb import JarvisOrb
    orb = JarvisOrb()
    orb.start()
    orb.set_state("listening", "Say something...")
    orb.set_state("thinking", "Processing...")
    orb.set_state("speaking", "Here is your answer.")
    orb.set_state("idle")
    orb.stop()
"""

from __future__ import annotations

import math
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from typing import Optional


# ── window dimensions ──────────────────────────────────────────────────────────
WIN_W   = 480
WIN_H   = 560
ORB_CX  = WIN_W // 2
ORB_CY  = 220
ORB_R   = 120     # max ring radius
CANVAS_H = 420

# ── palette ────────────────────────────────────────────────────────────────────
BG      = "#060b15"
HEADER  = "#0a1525"

STATE_PALETTE = {
    #           core-bright    core-mid      ring-inner    ring-outer   label
    "idle":     ("#00cfff",   "#0088cc",    "#004488",    "#001833",   "#5599bb"),
    "listening":("#00ff99",   "#00cc66",    "#004422",    "#001811",   "#44aa66"),
    "thinking": ("#ffaa00",   "#dd7700",    "#442200",    "#1a0d00",   "#bb8833"),
    "speaking": ("#cc55ff",   "#9922cc",    "#330044",    "#11001a",   "#8844aa"),
    "error":    ("#ff2244",   "#cc0022",    "#330011",    "#110007",   "#aa2233"),
}

STATE_LABELS = {
    "idle":      "STANDBY",
    "listening": "LISTENING",
    "thinking":  "PROCESSING",
    "speaking":  "RESPONDING",
    "error":     "ERROR",
}

SPEED = {
    "idle":      0.022,
    "listening": 0.070,
    "thinking":  0.115,
    "speaking":  0.082,
    "error":     0.150,
}

FPS = 60


class JarvisOrb:
    def __init__(self, x: int = 30, y: int = 60) -> None:
        self._state  = "idle"
        self._text   = ""
        self._lock   = threading.Lock()
        self._phase  = 0.0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._root:   Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None
        self._lbl_state:  Optional[tk.Label] = None
        self._lbl_text:   Optional[tk.Label] = None
        self._start_x = x
        self._start_y = y
        self._drag_ox = self._drag_oy = 0

    # ── public API ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._gui_loop, daemon=True, name="jarvis-orb"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass

    def set_state(self, state: str, text: str = "") -> None:
        with self._lock:
            self._state = state if state in STATE_PALETTE else "idle"
            if text:
                self._text = text
        self._push_update()

    def set_response(self, text: str) -> None:
        with self._lock:
            self._text = text[:200] + "…" if len(text) > 200 else text
        self._push_update()

    # ── internals ──────────────────────────────────────────────────────────────

    def _push_update(self) -> None:
        if self._root:
            try:
                self._root.event_generate("<<JUpdate>>", when="tail")
            except Exception:
                pass

    def _gui_loop(self) -> None:
        root = tk.Tk()
        self._root = root

        root.title("J.A.R.V.I.S")
        root.geometry(f"{WIN_W}x{WIN_H}+{self._start_x}+{self._start_y}")
        root.configure(bg=BG)
        root.attributes("-topmost", True)
        root.attributes("-alpha",   0.94)
        root.resizable(False, False)
        root.overrideredirect(True)

        # ── canvas (orb area) ──────────────────────────────────────────────────
        canvas = tk.Canvas(root, width=WIN_W, height=CANVAS_H,
                           bg=BG, highlightthickness=0)
        canvas.pack(fill="x")
        self._canvas = canvas

        # ── bottom info panel ──────────────────────────────────────────────────
        info_frame = tk.Frame(root, bg=HEADER, height=WIN_H - CANVAS_H)
        info_frame.pack(fill="both", expand=True)
        info_frame.pack_propagate(False)

        # Title row
        title_row = tk.Frame(info_frame, bg=HEADER)
        title_row.pack(fill="x", padx=18, pady=(10, 0))

        tk.Label(
            title_row, text="J.A.R.V.I.S", bg=HEADER,
            font=("Consolas", 14, "bold"), fg="#00cfff"
        ).pack(side="left")

        # Close button
        close_btn = tk.Label(
            title_row, text="✕", bg=HEADER,
            font=("Consolas", 11), fg="#224455", cursor="hand2"
        )
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda _: self.stop())

        # State label
        self._lbl_state = tk.Label(
            info_frame, text="S T A N D B Y", bg=HEADER,
            font=("Consolas", 9, "bold"), fg="#5599bb",
        )
        self._lbl_state.pack(anchor="w", padx=18, pady=(2, 0))

        # Separator
        tk.Frame(info_frame, bg="#0d2a4a", height=1).pack(fill="x", padx=18, pady=6)

        # Text label
        self._lbl_text = tk.Label(
            info_frame, text="", bg=HEADER,
            font=("Consolas", 9), fg="#88aabb",
            wraplength=WIN_W - 40, justify="left", anchor="nw"
        )
        self._lbl_text.pack(fill="x", padx=18)

        # ── drag support ───────────────────────────────────────────────────────
        for widget in (root, canvas, info_frame):
            widget.bind("<ButtonPress-1>",  self._drag_start)
            widget.bind("<B1-Motion>",      self._drag_move)

        root.bind("<<JUpdate>>", self._on_update)
        self._animate()
        root.mainloop()

    def _animate(self) -> None:
        if not self._running or not self._root:
            return

        with self._lock:
            state = self._state

        palette = STATE_PALETTE[state]
        bright, mid, ring_in, ring_out, _ = palette
        speed = SPEED.get(state, 0.022)
        self._phase += speed
        t = self._phase

        c = self._canvas
        c.delete("all")

        # ── background glow (subtle) ───────────────────────────────────────────
        _oval(c, ORB_CX, ORB_CY, ORB_R * 1.8, _alpha_color(ring_out, 0.5))
        _oval(c, ORB_CX, ORB_CY, ORB_R * 1.4, _alpha_color(ring_in, 0.5))

        # ── animated rings ─────────────────────────────────────────────────────
        num_rings = 5
        for i in range(num_rings, 0, -1):
            frac  = i / num_rings
            pulse = 0.5 + 0.5 * math.sin(t - i * 0.9)
            extra = (16 * pulse) if state != "idle" else (5 * pulse)
            r     = ORB_R * (0.45 + 0.55 * frac) + extra
            alpha = 0.12 + 0.10 * pulse * frac
            color = _alpha_color(ring_in, alpha)
            _oval(c, ORB_CX, ORB_CY, r, color)

        # ── core orb ──────────────────────────────────────────────────────────
        cp    = 0.90 + 0.10 * math.sin(t * 2.1)
        cr    = ORB_R * 0.55 * cp

        # Outer softening ring
        _oval(c, ORB_CX, ORB_CY, cr * 1.25, _alpha_color(mid, 0.35))

        # Main gradient (approximate with two ovals)
        _oval(c, ORB_CX, ORB_CY, cr, mid)
        _oval(c, ORB_CX, ORB_CY, cr * 0.68, bright)

        # Inner highlight
        hx = ORB_CX - cr * 0.38
        hy = ORB_CY - cr * 0.42
        hr = cr * 0.22
        _oval(c, hx, hy, hr, "#ffffff")

        # Tiny core sparkle
        _oval(c, hx + hr * 0.3, hy + hr * 0.3, hr * 0.35, "#e0f8ff")

        # ── LISTENING: audio bars below the orb ───────────────────────────────
        if state == "listening":
            bar_count = 9
            bar_w = 6
            bar_gap = 5
            bar_base_y = ORB_CY + cr + 14
            total_bar_w = bar_count * (bar_w + bar_gap) - bar_gap
            bar_start_x = ORB_CX - total_bar_w // 2
            for i in range(bar_count):
                bh = 8 + 30 * abs(math.sin(t * 4 + i * 0.9))
                bx = bar_start_x + i * (bar_w + bar_gap)
                c.create_rectangle(
                    bx, bar_base_y,
                    bx + bar_w, bar_base_y + bh,
                    fill=bright, outline="", width=0
                )

        # ── THINKING: rotating arcs ────────────────────────────────────────────
        if state == "thinking":
            arc_r = cr + 28
            for i in range(3):
                ang = math.degrees(t * 2 + i * (2 * math.pi / 3))
                c.create_arc(
                    ORB_CX - arc_r, ORB_CY - arc_r,
                    ORB_CX + arc_r, ORB_CY + arc_r,
                    start=ang, extent=60,
                    style="arc", outline=bright, width=2
                )

        # ── state label inside orb ─────────────────────────────────────────────
        label_text = STATE_LABELS[state]
        c.create_text(
            ORB_CX, ORB_CY + cr + (55 if state == "listening" else 22),
            text=label_text, fill=palette[4],
            font=("Consolas", 10, "bold")
        )

        # ── schedule next frame ───────────────────────────────────────────────
        if self._root:
            self._root.after(int(1000 / FPS), self._animate)

    def _on_update(self, _event=None) -> None:
        with self._lock:
            state = self._state
            text  = self._text

        palette = STATE_PALETTE[state]
        if self._lbl_state:
            spaced = "  ".join(STATE_LABELS[state])
            self._lbl_state.config(text=spaced, fg=palette[4])
        if self._lbl_text:
            self._lbl_text.config(text=text)

    # ── drag ──────────────────────────────────────────────────────────────────
    def _drag_start(self, ev: tk.Event) -> None:
        self._drag_ox = ev.x_root - self._root.winfo_x()
        self._drag_oy = ev.y_root - self._root.winfo_y()

    def _drag_move(self, ev: tk.Event) -> None:
        if self._root:
            nx = ev.x_root - self._drag_ox
            ny = ev.y_root - self._drag_oy
            self._root.geometry(f"+{nx}+{ny}")


# ── canvas helpers ─────────────────────────────────────────────────────────────

def _oval(canvas: tk.Canvas, cx: float, cy: float, r: float, fill: str) -> None:
    canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                       fill=fill, outline="", width=0)


def _alpha_color(hex_color: str, alpha: float) -> str:
    """Blend hex_color toward BG (#060b15) by (1-alpha) to fake transparency."""
    bg_r, bg_g, bg_b = 6, 11, 21
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    rr = int(r * alpha + bg_r * (1 - alpha))
    gg = int(g * alpha + bg_g * (1 - alpha))
    bb = int(b * alpha + bg_b * (1 - alpha))
    return f"#{rr:02x}{gg:02x}{bb:02x}"
