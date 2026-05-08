"""
core/voice_loop.py — Main async voice pipeline.

Orchestrates the full flow:
  1. Wake word detected → play confirmation cue
  2. Record until silence
  3. Transcribe (STT)
  4. Skip if empty/noise
  5. Send to Brain (Phase 2+) or echo back (Phase 1)
  6. Speak the response (TTS)
  7. Return to listening

Designed to run as a background asyncio task inside the FastAPI process.
State changes are broadcast over WebSocket in Phase 8.
"""

from __future__ import annotations

import asyncio
import os
from typing import Callable, Awaitable

from core.audio import record_until_silence, pcm_to_wav
from core.stt import transcribe
from core.tts import speak_async

# State labels — broadcast to UI via WebSocket (Phase 8)
STATE_IDLE = "IDLE"
STATE_LISTENING = "LISTENING"
STATE_THINKING = "THINKING"
STATE_SPEAKING = "SPEAKING"


class VoiceLoop:
    """
    Async voice loop.  Instantiate once; call run() as an asyncio task.
    """

    def __init__(
        self,
        on_state_change: Callable[[str], Awaitable[None]] | None = None,
        on_transcript: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        """
        Args:
            on_state_change: Async callback(state: str) fired on every state transition.
            on_transcript:   Async callback(role, text) fired when user or Jarvis speaks.
                             role is 'user' or 'jarvis'.
        """
        self._on_state_change = on_state_change or (lambda s: asyncio.sleep(0))
        self._on_transcript = on_transcript or (lambda r, t: asyncio.sleep(0))
        self._state = STATE_IDLE
        self._running = False

        # Brain is injected in Phase 2; None → echo mode (Phase 1)
        self.brain = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start the voice loop. Runs until stop() is called."""
        self._running = True
        await self._set_state(STATE_IDLE)

        from core.wake_word import WakeWordDetector
        loop = asyncio.get_running_loop()

        detector = WakeWordDetector(
            access_key=os.environ["PICOVOICE_ACCESS_KEY"],
            on_detected=self._handle_wake,
            loop=loop,
        )
        detector.start()
        print("[VoiceLoop] Running. Say 'Jarvis' to activate.")

        try:
            while self._running:
                await asyncio.sleep(0.1)
        finally:
            detector.stop()

    def stop(self) -> None:
        """Stop the voice loop gracefully."""
        self._running = False

    async def process_text(self, text: str) -> str:
        """
        Process a text command directly (used by REST API + mobile).

        Args:
            text: Command string.

        Returns:
            Jarvis's response as plain text.
        """
        response = await self._think(text)
        await self._speak(response)
        return response

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    async def _handle_wake(self) -> None:
        """Called by the wake word detector when 'Jarvis' is heard."""
        if self._state != STATE_IDLE:
            return  # Already active — ignore double-trigger

        # Confirmation cue
        await speak_async("Yes?")

        # Record
        await self._set_state(STATE_LISTENING)
        await self._notify_transcript("jarvis", "Yes?")

        loop = asyncio.get_running_loop()
        pcm = await loop.run_in_executor(None, record_until_silence)
        wav = pcm_to_wav(pcm)

        # Transcribe
        await self._set_state(STATE_THINKING)
        text = await loop.run_in_executor(None, transcribe, wav)

        if not text or len(text.split()) < 2:
            await speak_async("I didn't catch that.")
            await self._set_state(STATE_IDLE)
            return

        await self._notify_transcript("user", text)

        # Think
        response = await self._think(text)
        await self._notify_transcript("jarvis", response)

        # Speak
        await self._speak(response)
        await self._set_state(STATE_IDLE)

    async def _think(self, text: str) -> str:
        """Route text to Brain (Phase 2+) or echo it back (Phase 1)."""
        if self.brain is not None:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self.brain.think, text)
        # Phase 1 — simple echo
        return f"You said: {text}"

    async def _speak(self, text: str) -> None:
        await self._set_state(STATE_SPEAKING)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: asyncio.run(speak_async(text)))

    async def _set_state(self, state: str) -> None:
        self._state = state
        await self._on_state_change(state)

    async def _notify_transcript(self, role: str, text: str) -> None:
        await self._on_transcript(role, text)
