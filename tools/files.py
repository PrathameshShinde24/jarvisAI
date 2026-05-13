"""
tools/files.py — File system tools.

  - read_file(path)                  read any text/code/pdf/docx file
  - write_file(path, content)        write or overwrite a file
  - append_file(path, content)       append to a file
  - list_directory(path)             list files in a directory
  - search_files(directory, query)   search for files by name or content
  - move_file(src, dst)              move or rename a file
  - copy_file(src, dst)              copy a file
  - delete_file(path)                delete a file (requires confirmation)
  - create_folder(path)              create a new folder
  - get_file_info(path)              size, modified date, type
  - run_code(code, language)         execute Python code and return output
  - read_clipboard()                 read current clipboard content
  - write_clipboard(text)            write text to clipboard
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read the contents of any file — text, code, PDF, Word doc. Returns the content as text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Full file path or ~ path. Example: ~/Documents/notes.txt"},
                "max_chars": {"type": "integer", "description": "Max characters to return (default 4000)."}
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":    {"type": "string", "description": "Full file path."},
                "content": {"type": "string", "description": "Content to write."}
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "append_file",
        "description": "Append content to the end of a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":    {"type": "string", "description": "Full file path."},
                "content": {"type": "string", "description": "Content to append."}
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and folders in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (default: Desktop)."}
            },
            "required": [],
        },
    },
    {
        "name": "search_files",
        "description": "Search for files by name or content within a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory to search in (default: home)."},
                "query":     {"type": "string", "description": "File name or content to search for."},
                "by_content":{"type": "boolean", "description": "If true, search inside file contents too."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "move_file",
        "description": "Move or rename a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "Source file path."},
                "dst": {"type": "string", "description": "Destination path."}
            },
            "required": ["src", "dst"],
        },
    },
    {
        "name": "copy_file",
        "description": "Copy a file to a new location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "Source file path."},
                "dst": {"type": "string", "description": "Destination path."}
            },
            "required": ["src", "dst"],
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file. ALWAYS confirm with the user before calling this.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to delete."}
            },
            "required": ["path"],
        },
    },
    {
        "name": "create_folder",
        "description": "Create a new folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Folder path to create."}
            },
            "required": ["path"],
        },
    },
    {
        "name": "get_file_info",
        "description": "Get metadata about a file — size, type, last modified date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path."}
            },
            "required": ["path"],
        },
    },
    {
        "name": "run_code",
        "description": "Execute Python code and return the output. Use for calculations, data processing, or running scripts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code":    {"type": "string", "description": "Python code to execute."},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 10)."}
            },
            "required": ["code"],
        },
    },
    {
        "name": "read_clipboard",
        "description": "Read the current content of the clipboard.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "write_clipboard",
        "description": "Write text to the clipboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to copy to clipboard."}
            },
            "required": ["text"],
        },
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _read_pdf(path: Path) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        return "[pypdf not installed — run: pip install pypdf]"
    except Exception as exc:
        return f"[PDF read error: {exc}]"


def _read_docx(path: Path) -> str:
    try:
        import docx
        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    except ImportError:
        return "[python-docx not installed — run: pip install python-docx]"
    except Exception as exc:
        return f"[DOCX read error: {exc}]"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def read_file(inputs: dict[str, Any]) -> str:
    path = _resolve(inputs["path"])
    max_chars = int(inputs.get("max_chars", 4000))
    if not path.exists():
        return f"File not found: {path}"
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            text = _read_pdf(path)
        elif suffix in (".docx", ".doc"):
            text = _read_docx(path)
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n... [truncated — {len(text)} total chars]"
        return text or "[Empty file]"
    except Exception as exc:
        return f"Could not read {path}: {exc}"


def write_file(inputs: dict[str, Any]) -> str:
    path = _resolve(inputs["path"])
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(inputs["content"], encoding="utf-8")
        return f"Written to {path} ({len(inputs['content'])} chars)."
    except Exception as exc:
        return f"Could not write {path}: {exc}"


def append_file(inputs: dict[str, Any]) -> str:
    path = _resolve(inputs["path"])
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(inputs["content"])
        return f"Appended to {path}."
    except Exception as exc:
        return f"Could not append to {path}: {exc}"


def list_directory(inputs: dict[str, Any]) -> str:
    raw = inputs.get("path", "~/Desktop")
    path = _resolve(raw)
    if not path.exists():
        return f"Directory not found: {path}"
    entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    lines = []
    for e in entries[:40]:
        size = f"  {e.stat().st_size // 1024}KB" if e.is_file() else ""
        lines.append(f"{'[DIR] ' if e.is_dir() else ''}{e.name}{size}")
    suffix = f"\n... and {len(entries)-40} more" if len(entries) > 40 else ""
    return f"{path}:\n" + "\n".join(lines) + suffix


def search_files(inputs: dict[str, Any]) -> str:
    query      = inputs["query"].lower()
    raw_dir    = inputs.get("directory", "~")
    by_content = inputs.get("by_content", False)
    base       = _resolve(raw_dir)
    matches    = []
    try:
        for p in base.rglob("*"):
            if len(matches) >= 20:
                break
            if not p.is_file():
                continue
            if query in p.name.lower():
                matches.append(str(p))
            elif by_content and p.suffix in (".txt", ".py", ".md", ".json", ".csv", ".js", ".html"):
                try:
                    if query in p.read_text(encoding="utf-8", errors="replace").lower():
                        matches.append(str(p) + "  [content match]")
                except Exception:
                    pass
    except Exception as exc:
        return f"Search failed: {exc}"
    if not matches:
        return f"No files matching '{query}' found in {base}."
    return f"Found {len(matches)} file(s):\n" + "\n".join(matches)


def move_file(inputs: dict[str, Any]) -> str:
    src = _resolve(inputs["src"])
    dst = _resolve(inputs["dst"])
    try:
        shutil.move(str(src), str(dst))
        return f"Moved {src.name} to {dst}."
    except Exception as exc:
        return f"Move failed: {exc}"


def copy_file(inputs: dict[str, Any]) -> str:
    src = _resolve(inputs["src"])
    dst = _resolve(inputs["dst"])
    try:
        shutil.copy2(str(src), str(dst))
        return f"Copied {src.name} to {dst}."
    except Exception as exc:
        return f"Copy failed: {exc}"


def delete_file(inputs: dict[str, Any]) -> str:
    path = _resolve(inputs["path"])
    try:
        if path.is_dir():
            shutil.rmtree(str(path))
        else:
            path.unlink()
        return f"Deleted {path}."
    except Exception as exc:
        return f"Delete failed: {exc}"


def create_folder(inputs: dict[str, Any]) -> str:
    path = _resolve(inputs["path"])
    try:
        path.mkdir(parents=True, exist_ok=True)
        return f"Folder created: {path}."
    except Exception as exc:
        return f"Could not create folder: {exc}"


def get_file_info(inputs: dict[str, Any]) -> str:
    path = _resolve(inputs["path"])
    if not path.exists():
        return f"Not found: {path}"
    stat = path.stat()
    size = stat.st_size
    size_str = f"{size} bytes" if size < 1024 else f"{size//1024} KB" if size < 1024**2 else f"{size//1024**2} MB"
    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
    return f"{path.name} — {size_str}, modified {modified}, type: {path.suffix or 'folder'}."


def run_code(inputs: dict[str, Any]) -> str:
    code    = inputs["code"]
    timeout = int(inputs.get("timeout", 10))
    try:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp = f.name
        result = subprocess.run(
            [sys.executable, tmp],
            capture_output=True, text=True, timeout=timeout
        )
        os.unlink(tmp)
        output = result.stdout.strip()
        errors = result.stderr.strip()
        if errors and not output:
            return f"Error:\n{errors}"
        if errors:
            return f"Output:\n{output}\n\nWarnings:\n{errors}"
        return output or "[No output]"
    except subprocess.TimeoutExpired:
        return f"Code timed out after {timeout} seconds."
    except Exception as exc:
        return f"Run failed: {exc}"


def read_clipboard(inputs: dict[str, Any]) -> str:
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        return text or "[Clipboard is empty]"
    except Exception as exc:
        return f"Could not read clipboard: {exc}"


def write_clipboard(inputs: dict[str, Any]) -> str:
    text = inputs["text"]
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return f"Copied to clipboard: {text[:80]}{'...' if len(text)>80 else ''}"
    except Exception as exc:
        return f"Could not write clipboard: {exc}"


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

TOOL_HANDLERS: dict[str, Any] = {
    "read_file":       read_file,
    "write_file":      write_file,
    "append_file":     append_file,
    "list_directory":  list_directory,
    "search_files":    search_files,
    "move_file":       move_file,
    "copy_file":       copy_file,
    "delete_file":     delete_file,
    "create_folder":   create_folder,
    "get_file_info":   get_file_info,
    "run_code":        run_code,
    "read_clipboard":  read_clipboard,
    "write_clipboard": write_clipboard,
}
