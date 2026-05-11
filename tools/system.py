"""
tools/system.py — System control tools (Phase 2+).

Tools implemented here:
  - get_current_time()            ← Phase 2 verification tool
  - open_application(name)
  - close_application(name)       ← requires verbal confirmation
  - set_volume(level)
  - list_files(directory)
  - save_note(title, content)
"""

from __future__ import annotations

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

# Notes saved here
NOTES_DIR = Path.home() / "Documents" / "JarvisNotes"

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_current_time",
        "description": "Get the current date and time on the user's computer.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "open_application",
        "description": "Open an application by name on the user's computer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Application name, e.g. 'Chrome', 'Notepad', 'Spotify'."}
            },
            "required": ["name"],
        },
    },
    {
        "name": "close_application",
        "description": "Close a running application by name. Always confirm with the user before calling this.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Process/application name to kill."}
            },
            "required": ["name"],
        },
    },
    {
        "name": "set_volume",
        "description": "Set the system master volume (0–100).",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {"type": "integer", "description": "Volume level from 0 (mute) to 100 (max)."}
            },
            "required": ["level"],
        },
    },
    {
        "name": "list_files",
        "description": "List files in a directory on the user's computer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Absolute or ~ path to list. Defaults to home directory."}
            },
            "required": [],
        },
    },
    {
        "name": "save_note",
        "description": "Save a text note to ~/Documents/JarvisNotes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short note title (used as filename)."},
                "content": {"type": "string", "description": "Body of the note."},
            },
            "required": ["title", "content"],
        },
    },
]

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def get_current_time(inputs: dict[str, Any]) -> str:
    """Return the current date and time as a readable string."""
    now = datetime.now()
    return now.strftime("It's %I:%M %p on %A, %B %d, %Y")


def open_application(inputs: dict[str, Any]) -> str:
    name = inputs["name"]
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(name)
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", name])
        else:
            subprocess.Popen([name])
        return f"Opened {name}."
    except Exception as exc:
        return f"Couldn't open {name}: {exc}"


def close_application(inputs: dict[str, Any]) -> str:
    name = inputs["name"]
    system = platform.system()
    try:
        if system == "Windows":
            # Try graceful close first, force kill only if that fails
            result = subprocess.run(
                ["taskkill", "/IM", f"{name}.exe"],
                capture_output=True, timeout=5
            )
            if result.returncode != 0:
                subprocess.run(
                    ["taskkill", "/IM", f"{name}.exe", "/F"],
                    check=True, capture_output=True, timeout=5
                )
        else:
            subprocess.run(["pkill", "-f", name], check=True, timeout=5)
        return f"Closed {name}."
    except subprocess.TimeoutExpired:
        return f"Timed out trying to close {name}."
    except subprocess.CalledProcessError:
        return f"Couldn't find a running process named {name}."
    except Exception as exc:
        return f"Couldn't close {name}: {exc}"


def set_volume(inputs: dict[str, Any]) -> str:
    level = max(0, min(100, int(inputs["level"])))
    system = platform.system()
    try:
        if system == "Windows":
            # Use pycaw (proper Windows Core Audio API)
            try:
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices   = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume    = cast(interface, POINTER(IAudioEndpointVolume))
                volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            except ImportError:
                # pycaw not installed — fall back to PowerShell WScript approach
                subprocess.run(
                    ["powershell", "-Command",
                     f"$wsh=New-Object -ComObject WScript.Shell; "
                     f"$wsh.SendKeys([char]174)"],   # just a placeholder beep; pycaw is preferred
                    capture_output=True
                )
                return f"Volume command sent (install pycaw for precise control)."
        elif system == "Darwin":
            subprocess.run(["osascript", "-e", f"set volume output volume {level}"], check=True)
        else:
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", f"{level}%"], check=True)
        return f"Volume set to {level} percent."
    except Exception as exc:
        return f"Couldn't set volume: {exc}"


def list_files(inputs: dict[str, Any]) -> str:
    directory = inputs.get("directory", "~")
    path = Path(directory).expanduser()
    if not path.exists():
        return f"Directory '{directory}' does not exist."
    # Materialise once — avoids double-iterdir race condition
    entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    names   = [f"{'[dir] ' if e.is_dir() else ''}{e.name}" for e in entries[:20]]
    suffix  = "..." if len(entries) > 20 else ""
    return f"Contents of {path}: " + ", ".join(names) + suffix


def save_note(inputs: dict[str, Any]) -> str:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    title = inputs["title"].replace(" ", "_").replace("/", "-")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = NOTES_DIR / f"{timestamp}_{title}.txt"
    filename.write_text(inputs["content"], encoding="utf-8")
    return f"Note saved to {filename}."


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

TOOL_HANDLERS: dict[str, Any] = {
    "get_current_time": get_current_time,
    "open_application": open_application,
    "close_application": close_application,
    "set_volume": set_volume,
    "list_files": list_files,
    "save_note": save_note,
}
