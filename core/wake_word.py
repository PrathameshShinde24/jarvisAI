"""
core/wake_word.py — Wake word detection using openwakeword (free, no signup).

Listens continuously for "Jarvis" using a pre-trained openwakeword model.
Runs in its own thread; calls an async callback when the wake word fires.

openwakeword: https://github.com/dscripka/openWakeWord
  - Fully open source, no API key, no account needed
  - Models are downloaded automatically on first run (~5 MB)
  - Detection threshold tunable via WAKE_WORD_THRESHOLD in .env
"""

from __future__ import annotations

import asyncio
import threading
from typing import Callable, Coroutine, Any

import numpy as np
import pyaudio
from openwakeword.model import Model

# Audio config expected by openwakeword
SAMPLE_RATE = 16_000
FRAME_SIZE = 1280          # ~80 ms chunks at 16 kHz — required by openwakeword

# Confidence threshold (0.0–1.0). Lower = more sensitive, more false triggers.
DEFAULT_THRESHOLD = 0.5


class WakeWordDetector:
    """Detects the 'Jarvis' wake word using openwakeword (offline, free)."""

    def __init__(
        self,
        on_detected: Callable[[], Coroutine[Any, Any, None]],
        loop: asyncio.AbstractEventLoop,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        """
        Args:
            on_detected: Async coroutine called each time the wake word fires.
            loop:        The running asyncio event loop.
            threshold:   Detection confidence threshold (default 0.5).
        """
        self._on_detected = on_detected
        self._loop = loop
        self._threshold = threshold
        self._running = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the detector in a background daemon thread."""
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
        """Blocking detection loop — runs in a dedicated thread."""

        print("[WakeWord] Loading model (first run downloads ~5 MB)...")

        # openwakeword includes a 'hey_jarvis' community model.
        # If it fails, falls back to the built-in 'alexa' model as a placeholder.
        try:
            oww = Model(
                wakeword_models=["hey_jarvis"],
                inference_framework="onnx",
            )
            target_label = "hey_jarvis"
            print("[WakeWord] Loaded 'hey_jarvis' model.")
        except Exception:
            oww = Model(inference_framework="onnx")
            target_label = list(oww.models.keys())[0]
            print(f"[WakeWord] 'hey_jarvis' model not found — using '{target_label}' as fallback.")
            print("[WakeWord] Say the fallback keyword to trigger Jarvis.")

        pa = pyaudio.PyAudio()
        stream = pa.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=FRAME_SIZE,
        )

        print(f"[WakeWord] Listening... (threshold={self._threshold})")
        try:
            while self._running:
                raw = stream.read(FRAME_SIZE, exception_on_overflow=False)
                # Convert bytes → int16 numpy array (required by openwakeword)
                audio = np.frombuffer(raw, dtype=np.int16)
                predictions = oww.predict(audio)

                score = predictions.get(target_label, 0.0)
                if score >= self._threshold:
                    print(f"[WakeWord] Detected! (score={score:.2f})")
                    asyncio.run_coroutine_threadsafe(self._on_detected(), self._loop)
                    # Brief cooldown — prevent re-triggering on the same utterance
                    oww.reset()
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
