"""
core/tts.py — Text-to-speech via edge-tts (Microsoft Edge TTS, free, no API key).

Synthesises text to an MP3 in-memory buffer and plays it immediately.
Voice: en-US-GuyNeural (calm, professional male voice — suits Jarvis).

Two entry points:
  speak(text)        — sync, safe to call from non-async code / tests
  speak_async(text)  — async, runs playback in executor so the event loop
                       is not blocked
"""

from __future__ import annotations

import asyncio
import io

import edge_tts

from core.audio import play_audio_bytes

VOICE = "en-US-GuyNeural"


# ---------------------------------------------------------------------------
# Internal synthesis
# ---------------------------------------------------------------------------

async def _synthesise(text: str) -> bytes:
    """Async: synthesise text → MP3 bytes via edge-tts."""
    communicate = edge_tts.Communicate(text, VOICE)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def speak(text: str) -> None:
    """
    Synthesise and play text — blocking, safe to call from sync code.

    Creates its own temporary event loop for synthesis, then plays via
    pygame. Do NOT call this from inside an already-running event loop
    (use speak_async instead).

    Args:
        text: Plain text — no markdown, no bullet points.
    """
    print(f"[TTS] Speaking: {text!r}")
    mp3_bytes = asyncio.run(_synthesise(text))
    play_audio_bytes(mp3_bytes, ".mp3")


async def speak_async(text: str) -> None:
    """
    Synthesise and play text — async-safe.

    Synthesis runs natively async; pygame playback runs in a thread
    executor so the event loop is never blocked.

    Args:
        text: Plain text — no markdown, no bullet points.
    """
    print(f"[TTS] Speaking: {text!r}")
    mp3_bytes = await _synthesise(text)
    # Playback is blocking (pygame) — offload to thread executor
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, play_audio_bytes, mp3_bytes, ".mp3")
