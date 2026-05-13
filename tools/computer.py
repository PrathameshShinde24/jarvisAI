"""
tools/computer.py — Full computer control tools.

Capabilities:
  - take_screenshot()         capture screen
  - read_screen()             describe what is on screen using vision
  - find_and_click(target)    find UI element by description and click it
  - click_at(x, y)            click at exact coordinates
  - type_text(text)           type text via keyboard
  - press_key(key)            press key or shortcut (e.g. "ctrl+c", "enter")
  - scroll(direction, amount) scroll up/down
  - get_cursor_position()     returns current mouse x, y
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import tempfile
import time
from typing import Any

import pyautogui
import mss
import mss.tools
from PIL import Image

pyautogui.FAILSAFE = True
pyautogui.PAUSE    = 0.05

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "take_screenshot",
        "description": "Take a screenshot of the current screen and save it.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "read_screen",
        "description": "Look at the current screen and describe what is on it. Use this before interacting with UI to understand the current state.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "find_and_click",
        "description": "Find a UI element on screen by description and click it. Example: 'the Send button', 'search bar', 'Chrome icon on taskbar'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":       {"type": "string",  "description": "Description of the element to find and click."},
                "double_click": {"type": "boolean", "description": "Set true to double-click instead of single click."}
            },
            "required": ["target"],
        },
    },
    {
        "name": "click_at",
        "description": "Click at specific screen coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x":            {"type": "integer", "description": "X coordinate in pixels from left."},
                "y":            {"type": "integer", "description": "Y coordinate in pixels from top."},
                "double_click": {"type": "boolean", "description": "Set true to double-click."},
                "right_click":  {"type": "boolean", "description": "Set true to right-click."}
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "type_text",
        "description": "Type text using the keyboard at the current cursor position.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text":     {"type": "string", "description": "Text to type."},
                "interval": {"type": "number", "description": "Seconds between keystrokes (default 0.03)."}
            },
            "required": ["text"],
        },
    },
    {
        "name": "press_key",
        "description": "Press a keyboard key or shortcut. Examples: 'enter', 'escape', 'ctrl+c', 'ctrl+v', 'alt+tab', 'win', 'f5'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key or shortcut to press."}
            },
            "required": ["key"],
        },
    },
    {
        "name": "scroll",
        "description": "Scroll the screen up or down.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down"], "description": "Scroll direction."},
                "amount":    {"type": "integer", "description": "Number of scroll clicks (default 3)."}
            },
            "required": ["direction"],
        },
    },
    {
        "name": "get_cursor_position",
        "description": "Get the current mouse cursor position on screen.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

# ---------------------------------------------------------------------------
# Vision helper
# ---------------------------------------------------------------------------

def _screenshot_base64() -> tuple[str, int, int]:
    """Capture full screen, return (base64_png, width, height)."""
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        max_w = 1280
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return b64, img.width, img.height


def _vision_query(prompt: str) -> str:
    """Send screenshot + prompt to Groq vision model."""
    from groq import Groq
    b64, w, h = _screenshot_base64()
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    resp = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        max_tokens=512,
    )
    return resp.choices[0].message.content.strip()

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def take_screenshot(inputs: dict[str, Any]) -> str:
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        raw = sct.grab(monitor)
        path = os.path.join(tempfile.gettempdir(), "jarvis_screen.png")
        mss.tools.to_png(raw.rgb, raw.size, output=path)
    return f"Screenshot saved to {path}."


def read_screen(inputs: dict[str, Any]) -> str:
    try:
        return _vision_query(
            "Describe what is currently on this screen in detail. "
            "Mention open applications, visible text, buttons, and overall layout."
        )
    except Exception as exc:
        return f"Could not read screen: {exc}"


def find_and_click(inputs: dict[str, Any]) -> str:
    target = inputs["target"]
    double = inputs.get("double_click", False)
    try:
        b64, img_w, img_h = _screenshot_base64()
        screen_w, screen_h = pyautogui.size()
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        prompt = (
            f"In this screenshot (image size {img_w}x{img_h} pixels), find: '{target}'.\n"
            f"Return ONLY a JSON object with pixel coordinates of its center, like: "
            f'{{\"x\": 450, \"y\": 320}}\n'
            f"If not found, return: {{\"x\": -1, \"y\": -1}}"
        )
        resp = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens=64,
        )
        text = resp.choices[0].message.content.strip()
        match = re.search(r'\{[^}]+\}', text)
        if not match:
            return f"Could not locate '{target}' on screen."
        coords = json.loads(match.group())
        x_img, y_img = int(coords["x"]), int(coords["y"])
        if x_img == -1:
            return f"'{target}' not found on screen."
        x_screen = int(x_img * screen_w / img_w)
        y_screen = int(y_img * screen_h / img_h)
        if double:
            pyautogui.doubleClick(x_screen, y_screen)
        else:
            pyautogui.click(x_screen, y_screen)
        return f"Clicked '{target}' at ({x_screen}, {y_screen})."
    except Exception as exc:
        return f"find_and_click failed: {exc}"


def click_at(inputs: dict[str, Any]) -> str:
    x, y = int(inputs["x"]), int(inputs["y"])
    try:
        if inputs.get("right_click"):
            pyautogui.rightClick(x, y)
        elif inputs.get("double_click"):
            pyautogui.doubleClick(x, y)
        else:
            pyautogui.click(x, y)
        return f"Clicked at ({x}, {y})."
    except Exception as exc:
        return f"Click failed: {exc}"


def type_text(inputs: dict[str, Any]) -> str:
    text     = inputs["text"]
    interval = float(inputs.get("interval", 0.03))
    try:
        pyautogui.write(text, interval=interval)
        return f"Typed: {text!r}"
    except Exception as exc:
        return f"Type failed: {exc}"


def press_key(inputs: dict[str, Any]) -> str:
    key = inputs["key"].lower().strip()
    try:
        if "+" in key:
            parts = [p.strip() for p in key.split("+")]
            pyautogui.hotkey(*parts)
        else:
            pyautogui.press(key)
        return f"Pressed: {key}"
    except Exception as exc:
        return f"Key press failed: {exc}"


def scroll(inputs: dict[str, Any]) -> str:
    direction = inputs.get("direction", "down")
    amount    = int(inputs.get("amount", 3))
    clicks    = amount if direction == "up" else -amount
    try:
        pyautogui.scroll(clicks)
        return f"Scrolled {direction} by {amount}."
    except Exception as exc:
        return f"Scroll failed: {exc}"


def get_cursor_position(inputs: dict[str, Any]) -> str:
    x, y = pyautogui.position()
    return f"Cursor is at ({x}, {y})."


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

TOOL_HANDLERS: dict[str, Any] = {
    "take_screenshot":    take_screenshot,
    "read_screen":        read_screen,
    "find_and_click":     find_and_click,
    "click_at":           click_at,
    "type_text":          type_text,
    "press_key":          press_key,
    "scroll":             scroll,
    "get_cursor_position": get_cursor_position,
}
