"""
core/voice_loop.py — Main async voice pipeline.

Orchestrates the full flow:
  1. Wake word detected → play confirmation cue ("Yes?")
  2. Record until silence
  3. Transcribe (STT)
  4. Skip if empty / noise
  5. Send to Brain (Phase 2+) or echo back (Phase 1)
  6. Speak the response (TTS)
  7. Return to listening

Runs as a background asyncio task inside the FastAPI process.
State changes are broadcast over WebSocket in Phase 8.
"""

from __future__ import annotations

import asyncio
from typing import Callable, Awaitable

from core.audio import record_until_silence, pcm_to_wav
from core.stt import transcribe
from core.tts import speak_async

# State labels — also used by WebSocket broadcaster (Phase 8)
STATE_IDLE      = "IDLE"
STATE_LISTENING = "LISTENING"
STATE_THINKING  = "THINKING"
STATE_SPEAKING  = "SPEAKING"


class VoiceLoop:
    """Async voice pipeline. Instantiate once; schedule run() as an asyncio task."""

    def __init__(
        self,
        on_state_change: Callable[[str], Awaitable[None]] | None = None,
        on_transcript: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        """
        Args:
            on_state_change: async callback(state) — fired on every state transition.
            on_transcript:   async callback(role, text) — 'user' or 'jarvis'.
        """
        async def _noop_state(s: str) -> None: pass
        async def _noop_transcript(r: str, t: str) -> None: pass

        self._on_state_change = on_state_change or _noop_state
        self._on_transcript   = on_transcript   or _noop_transcript
        self._state   = STATE_IDLE
        self._running = False
        self.brain    = None   # injected in Phase 2; None → echo mode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start the voice loop — runs until stop() is called."""
        self._running = True
        await self._set_state(STATE_IDLE)

        from core.wake_word import WakeWordDetector
        loop = asyncio.get_running_loop()

        detector = WakeWordDetector(
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
            print("[VoiceLoop] Stopped.")

    def stop(self) -> None:
        """Gracefully stop the voice loop."""
        self._running = False

    async def process_text(self, text: str) -> str:
        """
        Process a text command directly — used by the REST API and mobile app.

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
            # Give feedback so user knows Jarvis is busy
            print(f"[VoiceLoop] Busy ({self._state}) — ignoring hotkey.")
            if self._state == STATE_SPEAKING:
                await speak_async("One moment.")
            return

        try:
            # 1. Confirmation cue
            await self._set_state(STATE_LISTENING)
            await self._notify_transcript("jarvis", "Yes?")
            await speak_async("Yes?")

            # 2. Record
            loop = asyncio.get_running_loop()
            pcm = await loop.run_in_executor(None, record_until_silence)
            wav = pcm_to_wav(pcm)

            # 3. Transcribe
            await self._set_state(STATE_THINKING)
            text = await loop.run_in_executor(None, transcribe, wav)

            # 4. Skip if empty or pure noise
            if not text or len(text.strip()) < 2:
                await speak_async("I didn't catch that.")
                return

            await self._notify_transcript("user", text)

            # 5. Think (echo in Phase 1, LLM in Phase 2+)
            response = await self._think(text)
            await self._notify_transcript("jarvis", response)

            # 6. Speak
            await self._speak(response)

        except Exception as exc:
            print(f"[VoiceLoop] Error during pipeline: {exc}")
            try:
                await speak_async("Sorry, something went wrong.")
            except Exception:
                pass

        finally:
            # Always return to IDLE — no matter what happened above
            await self._set_state(STATE_IDLE)

    async def _think(self, text: str) -> str:
        """Route to Brain (Phase 2+) or simple echo (Phase 1)."""
        if self.brain is not None:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self.brain.think, text)
        return f"You said: {text}"

    async def _speak(self, text: str) -> None:
        """Set speaking state, then play TTS."""
        await self._set_state(STATE_SPEAKING)
        await speak_async(text)           # speak_async runs pygame in executor — safe

    async def _set_state(self, state: str) -> None:
        self._state = state
        await self._on_state_change(state)

    async def _notify_transcript(self, role: str, text: str) -> None:
        await self._on_transcript(role, text)
