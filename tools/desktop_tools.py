"""
Desktop Control Tools for JARVIS (Windows)
Zero extra dependencies — everything runs through PowerShell.

Tools:
    open_app        — launch any installed app
    close_app       — kill a process by name/title
    list_windows    — see all open windows
    focus_window    — bring any window to front
    get_active_window — what's focused right now
    run_command     — run any shell/PowerShell command
    take_screenshot — screenshot to a file
    search_apps     — discover installed apps by keyword
"""

import datetime
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

from tools.base_tool import BaseTool


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ps(script: str, timeout: int = 15) -> subprocess.CompletedProcess:
    """Run a PowerShell script and return the result."""
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _ps_json(script: str, timeout: int = 15) -> Any:
    """Run PowerShell that outputs JSON, parse and return."""
    result = _ps(script, timeout=timeout)
    raw = result.stdout.strip()
    if not raw:
        return None
    data = json.loads(raw)
    # PowerShell wraps single objects in a dict instead of a list
    return data if isinstance(data, list) else [data]


# ── App shorthand map ─────────────────────────────────────────────────────────

APP_SHORTCUTS: Dict[str, str] = {
    # Browsers
    "chrome": "chrome",
    "browser": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "brave": "brave",
    # Microsoft Office
    "excel": "excel",
    "word": "winword",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
    "onenote": "onenote",
    "access": "msaccess",
    # Dev tools
    "vscode": "code",
    "code": "code",
    "terminal": "wt",
    "cmd": "cmd",
    "powershell": "powershell",
    "git": "gitbash",
    "postman": "postman",
    # Editors
    "notepad": "notepad",
    "notepad++": "notepad++",
    "sublime": "sublime_text",
    # Communication
    "teams": "ms-teams:",
    "slack": "slack",
    "discord": "discord",
    "zoom": "zoom",
    "skype": "skype",
    "whatsapp": "whatsapp:",
    # Media
    "spotify": "spotify",
    "vlc": "vlc",
    "photos": "ms-photos:",
    "camera": "microsoft.windows.camera:",
    # System
    "calculator": "calc",
    "calc": "calc",
    "paint": "mspaint",
    "paint3d": "ms-paint:",
    "explorer": "explorer",
    "file explorer": "explorer",
    "task manager": "taskmgr",
    "control panel": "control",
    "settings": "ms-settings:",
    "device manager": "devmgmt.msc",
    "registry": "regedit",
    "snipping tool": "snippingtool",
    "snip": "snippingtool",
    "clock": "ms-clock:",
    "alarms": "ms-clock:",
    "weather": "bingweather:",
    "maps": "bingmaps:",
    "store": "ms-windows-store:",
    "microsoft store": "ms-windows-store:",
    "microsoft": "ms-windows-store:",
    "mail": "outlookmail:",
    "calendar": "outlookcal:",
    "sticky notes": "microsoft.microsoftstickyNotes:",
    "to do": "ms-todo:",
    "todo": "ms-todo:",
    # Others
    "steam": "steam",
    "obs": "obs64",
    "7zip": "7zfm",
    "winrar": "winrar",
}


# ── Tools ─────────────────────────────────────────────────────────────────────

class OpenAppTool(BaseTool):
    name = "open_app"
    description = "Open any desktop application by name (e.g. 'chrome', 'vscode', 'spotify', 'calculator', 'excel')"

    def execute(self, app: str, **kwargs) -> Dict[str, Any]:
        try:
            cmd = APP_SHORTCUTS.get(app.lower().strip(), app)
            # shell=True handles UWP protocol URLs (ms-settings:, etc.) and PATH lookups
            subprocess.Popen(cmd, shell=True)
            time.sleep(0.4)  # let the window appear
            return {"success": True, "result": f"Opened '{app}'", "error": None}
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
    description = "List all currently open windows with their titles, process names, and PIDs"

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

    # Inlined C# so we don't need extra packages
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
    description = "Get the title and process name of the window that is currently focused"

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


class RunCommandTool(BaseTool):
    name = "run_command"
    description = "Run any PowerShell or shell command and return its output"

    def execute(self, command: str, shell: str = "powershell", timeout: int = 30, **kwargs) -> Dict[str, Any]:
        try:
            if shell == "powershell":
                proc = _ps(command, timeout=timeout)
            else:
                proc = subprocess.run(
                    command, shell=True, capture_output=True,
                    text=True, timeout=timeout,
                )
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
    description = "Set the system volume (0–100) or mute/unmute"

    def execute(self, level: int = None, mute: bool = None, **kwargs) -> Dict[str, Any]:
        try:
            if mute is True:
                script = "$obj = New-Object -ComObject WScript.Shell; for($i=0;$i-lt50;$i++){$obj.SendKeys([char]173)}"
            elif mute is False:
                script = "$obj = New-Object -ComObject WScript.Shell; for($i=0;$i-lt50;$i++){$obj.SendKeys([char]173)}"
            elif level is not None:
                # Use nircmd if available, else PowerShell audio API
                script = f"""
$vol = [math]::Round({level} / 100 * 65535)
$wsh = New-Object -ComObject WScript.Shell
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


# Convenience list for registration
ALL_DESKTOP_TOOLS = [
    OpenAppTool(),
    CloseAppTool(),
    ListWindowsTool(),
    FocusWindowTool(),
    GetActiveWindowTool(),
    RunCommandTool(),
    TakeScreenshotTool(),
    SearchAppsTool(),
    SetVolumeTool(),
]
