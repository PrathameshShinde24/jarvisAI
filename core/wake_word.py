"""
core/wake_word.py — Wake word detection using openwakeword (free, no signup).

Listens continuously for "Jarvis" using a pre-trained openwakeword model.
Runs in its own thread; calls an async callback when the wake word fires.

openwakeword: https://github.com/dscripka/openWakeWord
  - Fully open source, no API key, no account needed
  - Models download automatically on first run (~5 MB)
  - Sensitivity tunable via WAKE_WORD_THRESHOLD in .env (default 0.5)
"""

from __future__ import annotations

import asyncio
import time
import threading
from typing import Callable, Coroutine, Any

import numpy as np
import pyaudio
from openwakeword.model import Model

SAMPLE_RATE = 16_000
FRAME_SIZE  = 1280          # ~80 ms at 16 kHz — required by openwakeword
COOLDOWN    = 2.0           # seconds to wait before re-triggering


class WakeWordDetector:
    """Detects 'Jarvis' using openwakeword (offline, no API key)."""

    def __init__(
        self,
        on_detected: Callable[[], Coroutine[Any, Any, None]],
        loop: asyncio.AbstractEventLoop,
        threshold: float = 0.5,
    ) -> None:
        """
        Args:
            on_detected: Async coroutine called when wake word fires.
            loop:        Running asyncio event loop.
            threshold:   Confidence threshold 0.0–1.0 (default 0.5).
                         Lower = more sensitive, higher = fewer false triggers.
        """
        self._on_detected = on_detected
        self._loop        = loop
        self._threshold   = threshold
        self._running     = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start detector in a background daemon thread."""
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the detector to stop."""
        self._running = False

    def _run(self) -> None:
        """Blocking detection loop — runs in dedicated thread."""

        print("[WakeWord] Loading model (first run downloads ~5 MB)...")
        try:
            oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            target = "hey_jarvis"
            print("[WakeWord] 'hey_jarvis' model loaded.")
        except Exception as e:
            print(f"[WakeWord] hey_jarvis model unavailable ({e}), using default model.")
            oww = Model(inference_framework="onnx")
            target = list(oww.models.keys())[0]
            print(f"[WakeWord] Using '{target}' — say this word to activate Jarvis.")

        pa     = pyaudio.PyAudio()
        stream = pa.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=FRAME_SIZE,
        )

        last_trigger = 0.0
        print(f"[WakeWord] Listening... (threshold={self._threshold})")

        try:
            while self._running:
                raw   = stream.read(FRAME_SIZE, exception_on_overflow=False)
                audio = np.frombuffer(raw, dtype=np.int16)

                predictions = oww.predict(audio)
                score = predictions.get(target, 0.0)

                now = time.monotonic()
                if score >= self._threshold and (now - last_trigger) > COOLDOWN:
                    print(f"[WakeWord] Detected! (score={score:.2f})")
                    last_trigger = now
                    asyncio.run_coroutine_threadsafe(self._on_detected(), self._loop)
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
