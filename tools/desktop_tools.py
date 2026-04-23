"""
Desktop Control Tools for JARVIS (Windows)
Full desktop automation: apps, websites, mouse, keyboard, screenshots.
"""

import datetime
import json
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, List

from tools.base_tool import BaseTool


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ps(script: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _ps_json(script: str, timeout: int = 15) -> Any:
    result = _ps(script, timeout=timeout)
    raw = result.stdout.strip()
    if not raw:
        return None
    data = json.loads(raw)
    return data if isinstance(data, list) else [data]


def _launch(cmd: str) -> None:
    """Launch an app or protocol URL reliably on Windows."""
    subprocess.Popen(f'start "" {cmd}', shell=True)


def _pyautogui():
    """Lazy import pyautogui — fails gracefully if not installed."""
    try:
        import pyautogui as pg
        pg.FAILSAFE = True
        pg.PAUSE = 0.05
        return pg
    except ImportError:
        return None


# ── App shorthand map ─────────────────────────────────────────────────────────

APP_SHORTCUTS: Dict[str, str] = {
    # Browsers
    "chrome":          "chrome",
    "browser":         "chrome",
    "google chrome":   "chrome",
    "firefox":         "firefox",
    "edge":            "msedge",
    "microsoft edge":  "msedge",
    "brave":           "brave",
    # Microsoft Office
    "excel":           "excel",
    "word":            "winword",
    "powerpoint":      "powerpnt",
    "outlook":         "outlook",
    "onenote":         "onenote",
    "access":          "msaccess",
    # Dev tools
    "vscode":          "code",
    "vs code":         "code",
    "code":            "code",
    "terminal":        "wt",
    "cmd":             "cmd",
    "powershell":      "powershell",
    "postman":         "postman",
    # Editors
    "notepad":         "notepad",
    "notepad++":       "notepad++",
    "sublime":         "sublime_text",
    # Communication
    "teams":           "ms-teams:",
    "slack":           "slack",
    "discord":         "discord",
    "zoom":            "zoom",
    "skype":           "skype",
    "whatsapp":        "whatsapp:",
    # Media
    "spotify":         "spotify",
    "vlc":             "vlc",
    "photos":          "ms-photos:",
    "camera":          "microsoft.windows.camera:",
    # System
    "calculator":      "calc",
    "calc":            "calc",
    "paint":           "mspaint",
    "paint3d":         "ms-paint:",
    "explorer":        "explorer",
    "file explorer":   "explorer",
    "task manager":    "taskmgr",
    "control panel":   "control",
    "settings":        "ms-settings:",
    "device manager":  "devmgmt.msc",
    "registry":        "regedit",
    "snipping tool":   "snippingtool",
    "snip":            "snippingtool",
    "clock":           "ms-clock:",
    "alarms":          "ms-clock:",
    "store":           "ms-windows-store:",
    "microsoft store": "ms-windows-store:",
    "mail":            "outlookmail:",
    "calendar":        "outlookcal:",
    "sticky notes":    "microsoft.microsoftstickyNotes:",
    "to do":           "ms-todo:",
    "todo":            "ms-todo:",
    "steam":           "steam",
    "obs":             "obs64",
    "7zip":            "7zfm",
    "winrar":          "winrar",
}

# Common websites — keyword → URL
WEBSITE_MAP: Dict[str, str] = {
    "facebook":      "https://www.facebook.com",
    "youtube":       "https://www.youtube.com",
    "google":        "https://www.google.com",
    "twitter":       "https://www.twitter.com",
    "x":             "https://www.x.com",
    "instagram":     "https://www.instagram.com",
    "reddit":        "https://www.reddit.com",
    "netflix":       "https://www.netflix.com",
    "amazon":        "https://www.amazon.com",
    "github":        "https://www.github.com",
    "gmail":         "https://mail.google.com",
    "google drive":  "https://drive.google.com",
    "drive":         "https://drive.google.com",
    "google maps":   "https://maps.google.com",
    "maps":          "https://maps.google.com",
    "linkedin":      "https://www.linkedin.com",
    "wikipedia":     "https://www.wikipedia.org",
    "stackoverflow": "https://www.stackoverflow.com",
    "stack overflow":"https://www.stackoverflow.com",
    "chatgpt":       "https://chat.openai.com",
    "openai":        "https://chat.openai.com",
    "claude":        "https://claude.ai",
    "whatsapp web":  "https://web.whatsapp.com",
    "twitch":        "https://www.twitch.tv",
    "tiktok":        "https://www.tiktok.com",
    "pinterest":     "https://www.pinterest.com",
    "ebay":          "https://www.ebay.com",
    "paypal":        "https://www.paypal.com",
    "outlook":       "https://outlook.live.com",
    "hotmail":       "https://outlook.live.com",
    "yahoo":         "https://www.yahoo.com",
    "bing":          "https://www.bing.com",
    "duckduckgo":    "https://www.duckduckgo.com",
    "dropbox":       "https://www.dropbox.com",
    "notion":        "https://www.notion.so",
    "trello":        "https://www.trello.com",
    "figma":         "https://www.figma.com",
    "canva":         "https://www.canva.com",
}


def resolve_website(name: str) -> str | None:
    """Return URL for a website name, or None if unknown."""
    key = name.lower().strip()
    if key in WEBSITE_MAP:
        return WEBSITE_MAP[key]
    # If it looks like a URL already
    if key.startswith("http") or "." in key.split("/")[0]:
        return key if key.startswith("http") else f"https://{key}"
    return None


# ── Tools ─────────────────────────────────────────────────────────────────────

class OpenAppTool(BaseTool):
    name = "open_app"
    description = "Open any desktop application by name (chrome, vscode, spotify, calculator, excel…)"

    def execute(self, app: str, **kwargs) -> Dict[str, Any]:
        try:
            key = app.lower().strip()
            cmd = APP_SHORTCUTS.get(key, app)
            _launch(cmd)
            time.sleep(0.4)
            return {"success": True, "result": f"Opened '{app}'", "error": None}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class OpenWebsiteTool(BaseTool):
    name = "open_website"
    description = "Open any website in the default browser (facebook, youtube, github, or a URL)"

    def execute(self, site: str, **kwargs) -> Dict[str, Any]:
        try:
            url = resolve_website(site)
            if not url:
                return {"success": False, "result": None, "error": f"Unknown site: '{site}'"}
            webbrowser.open(url)
            return {"success": True, "result": f"Opened {url}", "error": None}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class CloseAppTool(BaseTool):
    name = "close_app"
    description = "Close a running application by process name or window title"

    def execute(self, app: str, force: bool = True, **kwargs) -> Dict[str, Any]:
        try:
            flag = "-Force" if force else ""
            script = (
                f"$procs = Get-Process | Where-Object {{"
                f"$_.Name -like '*{app}*' -or $_.MainWindowTitle -like '*{app}*'}}; "
                f"$procs | Stop-Process {flag} -PassThru | Select-Object -ExpandProperty Name"
            )
            result = _ps(script)
            killed = [ln.strip() for ln in result.stdout.strip().splitlines() if ln.strip()]
            if killed:
                return {"success": True, "result": f"Closed: {', '.join(set(killed))}", "error": None}
            return {"success": False, "result": None, "error": f"No process found matching '{app}'"}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class ListWindowsTool(BaseTool):
    name = "list_windows"
    description = "List all currently open windows with their titles and process names"

    def execute(self, **kwargs) -> Dict[str, Any]:
        try:
            windows = _ps_json(
                "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} "
                "| Select-Object "
                "@{N='name';E={$_.Name}}, "
                "@{N='title';E={$_.MainWindowTitle}}, "
                "@{N='pid';E={$_.Id}}, "
                "@{N='memory_mb';E={[math]::Round($_.WorkingSet64/1MB,1)}} "
                "| ConvertTo-Json"
            ) or []
            return {"success": True, "result": {"windows": windows, "count": len(windows)}, "error": None}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class FocusWindowTool(BaseTool):
    name = "focus_window"
    description = "Bring any window to the foreground by its title or app name"

    _WIN32_CS = """
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class WinFocus {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
}
'@ -ErrorAction SilentlyContinue
"""

    def execute(self, title: str, **kwargs) -> Dict[str, Any]:
        try:
            script = (
                self._WIN32_CS +
                f"$p = Get-Process | Where-Object {{$_.MainWindowTitle -like '*{title}*'}} | Select-Object -First 1; "
                "if ($p) { "
                "[WinFocus]::ShowWindow($p.MainWindowHandle, 9); "
                "[WinFocus]::SetForegroundWindow($p.MainWindowHandle); "
                "Write-Output 'ok' "
                "} else { Write-Output 'notfound' }"
            )
            result = _ps(script, timeout=20)
            found = "ok" in result.stdout
            return {
                "success": found,
                "result": f"Focused: {title}" if found else None,
                "error": None if found else f"No window matching '{title}'",
            }
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class GetActiveWindowTool(BaseTool):
    name = "get_active_window"
    description = "Get the title and process name of the currently focused window"

    _WIN32_CS = """
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class FGW {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
}
'@ -ErrorAction SilentlyContinue
"""

    def execute(self, **kwargs) -> Dict[str, Any]:
        try:
            script = (
                self._WIN32_CS +
                "$hwnd = [FGW]::GetForegroundWindow(); "
                "Get-Process | Where-Object {$_.MainWindowHandle -eq $hwnd} "
                "| Select-Object @{N='name';E={$_.Name}}, @{N='title';E={$_.MainWindowTitle}}, @{N='pid';E={$_.Id}} "
                "| ConvertTo-Json"
            )
            result = _ps(script, timeout=20)
            raw = result.stdout.strip()
            data = json.loads(raw) if raw else {}
            if isinstance(data, list):
                data = data[0] if data else {}
            return {"success": True, "result": data, "error": None}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class TakeScreenshotTool(BaseTool):
    name = "take_screenshot"
    description = "Take a full screenshot and save it as a PNG file"

    def execute(self, filepath: str = None, **kwargs) -> Dict[str, Any]:
        try:
            if not filepath:
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filepath = str(Path.home() / "Pictures" / f"jarvis_{ts}.png")
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            script = f"""
Add-Type -Assembly System.Windows.Forms,System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bmp.Save('{filepath.replace(chr(92), "/")}')
$g.Dispose(); $bmp.Dispose()
Write-Output 'ok'
"""
            result = _ps(script, timeout=20)
            if "ok" in result.stdout:
                return {"success": True, "result": {"filepath": filepath}, "error": None}
            return {"success": False, "result": None, "error": result.stderr or "Screenshot failed"}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class RunCommandTool(BaseTool):
    name = "run_command"
    description = "Run any PowerShell or shell command and return its output"

    def execute(self, command: str, shell: str = "powershell", timeout: int = 30, **kwargs) -> Dict[str, Any]:
        try:
            if shell == "powershell":
                proc = _ps(command, timeout=timeout)
            else:
                proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            output = (proc.stdout or "").strip()
            error_out = (proc.stderr or "").strip()
            success = proc.returncode == 0
            return {
                "success": success,
                "result": {"output": output, "returncode": proc.returncode},
                "error": error_out if not success else None,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "result": None, "error": f"Timed out after {timeout}s"}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class SearchAppsTool(BaseTool):
    name = "search_apps"
    description = "Search all installed Windows apps and Start menu shortcuts by keyword"

    def execute(self, query: str = "", **kwargs) -> Dict[str, Any]:
        try:
            filter_clause = f"| Where-Object {{$_.Name -like '*{query}*'}}" if query else ""
            apps = _ps_json(
                f"Get-StartApps {filter_clause} "
                "| Select-Object @{{N='name';E={{$_.Name}}}}, @{{N='id';E={{$_.AppID}}}} "
                "| ConvertTo-Json"
            ) or []
            return {"success": True, "result": {"apps": apps, "count": len(apps)}, "error": None}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class SetVolumeTool(BaseTool):
    name = "set_volume"
    description = "Set the system volume (0–100)"

    def execute(self, level: int = None, mute: bool = None, **kwargs) -> Dict[str, Any]:
        try:
            if mute is not None:
                script = "$obj = New-Object -ComObject WScript.Shell; for($i=0;$i-lt50;$i++){$obj.SendKeys([char]173)}"
            elif level is not None:
                script = f"""
$vol = [math]::Round({level} / 100 * 65535)
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {{ void a();void b();void c();void d();
  int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
}}
[Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
class MMDeviceEnumerator {{}}
'@ -ErrorAction SilentlyContinue
Write-Output "volume set to {level}"
"""
            else:
                return {"success": False, "result": None, "error": "Provide 'level' (0-100) or 'mute' (true/false)"}
            result = _ps(script)
            return {"success": True, "result": result.stdout.strip() or f"Volume → {level}%", "error": None}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


# ── Mouse & Keyboard (pyautogui) ──────────────────────────────────────────────

class TypeTextTool(BaseTool):
    name = "type_text"
    description = "Type text into the currently focused window (like a keyboard)"

    def execute(self, text: str, interval: float = 0.03, **kwargs) -> Dict[str, Any]:
        pg = _pyautogui()
        if pg is None:
            return {"success": False, "result": None, "error": "pyautogui not installed. Run: pip install pyautogui"}
        try:
            time.sleep(0.3)
            pg.write(text, interval=interval)
            return {"success": True, "result": f"Typed: {text[:60]}{'...' if len(text) > 60 else ''}", "error": None}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class MouseClickTool(BaseTool):
    name = "mouse_click"
    description = "Click the mouse at screen coordinates (x, y) or double-click"

    def execute(self, x: int, y: int, double: bool = False, button: str = "left", **kwargs) -> Dict[str, Any]:
        pg = _pyautogui()
        if pg is None:
            return {"success": False, "result": None, "error": "pyautogui not installed. Run: pip install pyautogui"}
        try:
            if double:
                pg.doubleClick(x, y, button=button)
            else:
                pg.click(x, y, button=button)
            return {"success": True, "result": f"{'Double-c' if double else 'C'}licked at ({x}, {y})", "error": None}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class MouseMoveTool(BaseTool):
    name = "mouse_move"
    description = "Move the mouse cursor to screen coordinates (x, y)"

    def execute(self, x: int, y: int, **kwargs) -> Dict[str, Any]:
        pg = _pyautogui()
        if pg is None:
            return {"success": False, "result": None, "error": "pyautogui not installed. Run: pip install pyautogui"}
        try:
            pg.moveTo(x, y, duration=0.2)
            return {"success": True, "result": f"Mouse moved to ({x}, {y})", "error": None}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class ScrollTool(BaseTool):
    name = "scroll"
    description = "Scroll the mouse wheel up or down (amount = number of clicks)"

    def execute(self, direction: str = "down", amount: int = 3, **kwargs) -> Dict[str, Any]:
        pg = _pyautogui()
        if pg is None:
            return {"success": False, "result": None, "error": "pyautogui not installed. Run: pip install pyautogui"}
        try:
            clicks = amount if direction.lower() == "up" else -amount
            pg.scroll(clicks)
            return {"success": True, "result": f"Scrolled {direction} {amount} clicks", "error": None}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class PressKeyTool(BaseTool):
    name = "press_key"
    description = "Press a keyboard key (enter, escape, tab, space, f5, ctrl+c, win+d, etc.)"

    def execute(self, key: str, **kwargs) -> Dict[str, Any]:
        pg = _pyautogui()
        if pg is None:
            return {"success": False, "result": None, "error": "pyautogui not installed. Run: pip install pyautogui"}
        try:
            if "+" in key:
                keys = [k.strip() for k in key.split("+")]
                pg.hotkey(*keys)
            else:
                pg.press(key.strip())
            return {"success": True, "result": f"Pressed: {key}", "error": None}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


class GetMousePositionTool(BaseTool):
    name = "get_mouse_position"
    description = "Get the current mouse cursor position on screen"

    def execute(self, **kwargs) -> Dict[str, Any]:
        pg = _pyautogui()
        if pg is None:
            return {"success": False, "result": None, "error": "pyautogui not installed. Run: pip install pyautogui"}
        try:
            pos = pg.position()
            return {"success": True, "result": {"x": pos.x, "y": pos.y}, "error": None}
        except Exception as exc:
            return {"success": False, "result": None, "error": str(exc)}


# ── Registration ──────────────────────────────────────────────────────────────

ALL_DESKTOP_TOOLS = [
    OpenAppTool(),
    OpenWebsiteTool(),
    CloseAppTool(),
    ListWindowsTool(),
    FocusWindowTool(),
    GetActiveWindowTool(),
    RunCommandTool(),
    TakeScreenshotTool(),
    SearchAppsTool(),
    SetVolumeTool(),
    TypeTextTool(),
    MouseClickTool(),
    MouseMoveTool(),
    ScrollTool(),
    PressKeyTool(),
    GetMousePositionTool(),
]
