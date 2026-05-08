"""
core/wake_word.py — Picovoice Porcupine wake-word detector.

Listens continuously for "Jarvis" using the built-in keyword.
Runs in its own thread; calls an async callback when the wake word fires.
"""

from __future__ import annotations

import asyncio
import struct
import threading
from typing import Callable, Coroutine, Any

import pvporcupine
import pyaudio


class WakeWordDetector:
    """Wraps Porcupine to detect the 'jarvis' wake word offline."""

    def __init__(
        self,
        access_key: str,
        on_detected: Callable[[], Coroutine[Any, Any, None]],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """
        Args:
            access_key:  Picovoice access key from console.picovoice.ai.
            on_detected: Async coroutine called each time the wake word fires.
            loop:        The running asyncio event loop (so we can schedule the callback).
        """
        self._access_key = access_key
        self._on_detected = on_detected
        self._loop = loop
        self._running = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the detector in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the detector to stop."""
        self._running = False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Blocking loop — runs in a dedicated thread."""
        porcupine = pvporcupine.create(
            access_key=self._access_key,
            keywords=["jarvis"],
        )
        pa = pyaudio.PyAudio()
        stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length,
        )

        print("[WakeWord] Listening for 'Jarvis'...")
        try:
            while self._running:
                raw = stream.read(porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from(f"{porcupine.frame_length}h", raw)
                result = porcupine.process(pcm)
                if result >= 0:
                    print("[WakeWord] Detected!")
                    asyncio.run_coroutine_threadsafe(self._on_detected(), self._loop)
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
            porcupine.delete()
