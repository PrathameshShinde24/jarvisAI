"""
core/wake_word.py — Wake trigger via keyboard hotkey (Ctrl+Space).

openwakeword's 'hey_jarvis' model is not in their standard model set,
so we use a keyboard hotkey as the activation trigger instead.
This is reliable, zero-dependency, and works great for demos.

Hotkey: Ctrl+Space  →  activates Jarvis (same as saying "Hey Jarvis")

To change the hotkey, set WAKE_HOTKEY in your .env file.
e.g. WAKE_HOTKEY=ctrl+j  or  WAKE_HOTKEY=f9
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from typing import Callable, Coroutine, Any

import keyboard

COOLDOWN = 0.3  # seconds before re-triggering is allowed (state check prevents double-trigger)


class WakeWordDetector:
    """Keyboard-based wake trigger. Fires callback when hotkey is pressed."""

    def __init__(
        self,
        on_detected: Callable[[], Coroutine[Any, Any, None]],
        loop: asyncio.AbstractEventLoop,
        threshold: float = 0.5,   # kept for API compatibility, unused here
    ) -> None:
        """
        Args:
            on_detected: Async coroutine called when hotkey is pressed.
            loop:        Running asyncio event loop.
            threshold:   Unused — kept for drop-in compatibility with future detectors.
        """
        self._on_detected  = on_detected
        self._loop         = loop
        self._running      = False
        self._last_trigger = 0.0
        self._hotkey       = os.getenv("WAKE_HOTKEY", "ctrl+space")
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Register hotkey and start background listener thread."""
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Unregister hotkey and stop listener."""
        self._running = False
        try:
            keyboard.remove_hotkey(self._hotkey)
        except Exception:
            pass

    def _run(self) -> None:
        """Register the hotkey and keep thread alive until stopped."""
        print(f"[WakeWord] Press  {self._hotkey.upper()}  to activate Jarvis.")
        keyboard.add_hotkey(self._hotkey, self._on_hotkey_pressed)
        while self._running:
            time.sleep(0.1)

    def _on_hotkey_pressed(self) -> None:
        """Called synchronously by the keyboard library on hotkey press."""
        now = time.monotonic()
        if now - self._last_trigger < COOLDOWN:
            return
        self._last_trigger = now
        print("[WakeWord] Hotkey detected — activating Jarvis.")
        asyncio.run_coroutine_threadsafe(self._on_detected(), self._loop)
