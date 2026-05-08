"""
core/tts.py — Text-to-speech via edge-tts (Microsoft Edge TTS, free, no API key).

Synthesises text to an MP3 in-memory buffer and plays it immediately.
Voice: en-US-GuyNeural (calm, professional male voice — suits Jarvis).
"""

from __future__ import annotations

import asyncio
import io

import edge_tts

from core.audio import play_audio_bytes

# Microsoft Edge Neural voice — change here to swap voice globally
VOICE = "en-US-GuyNeural"


async def _synthesise(text: str) -> bytes:
    """Return MP3 bytes for the given text."""
    communicate = edge_tts.Communicate(text, VOICE)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


def speak(text: str) -> None:
    """
    Synthesise `text` via edge-tts and play it immediately.

    Blocks until playback finishes. Safe to call from sync code.

    Args:
        text: Plain text to speak — no markdown, no bullet points.
    """
    print(f"[TTS] Speaking: {text!r}")
    mp3_bytes = asyncio.run(_synthesise(text))
    play_audio_bytes(mp3_bytes, suffix=".mp3")


async def speak_async(text: str) -> None:
    """
    Async version of speak() — use inside async contexts.

    Args:
        text: Plain text to speak.
    """
    print(f"[TTS] Speaking: {text!r}")
    mp3_bytes = await _synthesise(text)
    play_audio_bytes(mp3_bytes, suffix=".mp3")
