"""
core/audio.py — Microphone recording and audio playback helpers.

Recording:
  - Captures audio after wake word fires.
  - Stops on ~1.5 s of silence or a max duration cap (~10 s).

Playback:
  - Plays back .mp3 / .wav TTS output via pygame.mixer.
"""

from __future__ import annotations

import io
import time
import wave
from pathlib import Path

import numpy as np
import pyaudio
import pygame


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16_000       # Hz — matches Whisper's expected input
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK = 1024               # frames per buffer
SILENCE_THRESHOLD = 300    # RMS below this → silence (lowered for sensitivity)
SILENCE_DURATION = 1.5     # seconds of silence before stopping
GRACE_PERIOD = 1.0         # seconds before silence detection kicks in (user prep time)
MAX_DURATION = 10.0        # hard cap on recording length


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

def record_until_silence() -> bytes:
    """
    Record from the default microphone until silence is detected.

    Returns:
        Raw 16-bit PCM audio bytes at SAMPLE_RATE.
    """
    pa = pyaudio.PyAudio()
    stream = pa.open(
        rate=SAMPLE_RATE,
        channels=CHANNELS,
        format=FORMAT,
        input=True,
        frames_per_buffer=CHUNK,
    )

    frames: list[bytes] = []
    silence_start: float | None = None
    start_time = time.monotonic()

    print("[Audio] Recording... (speak now)")
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

        elapsed = time.monotonic() - start_time
        rms     = _rms(data)

        # Grace period — don't check silence for the first second
        # so the user has time to start speaking after hearing "Yes?"
        if elapsed < GRACE_PERIOD:
            continue

        if rms < SILENCE_THRESHOLD:
            if silence_start is None:
                silence_start = time.monotonic()
            elif time.monotonic() - silence_start >= SILENCE_DURATION:
                print("[Audio] Silence detected — stopping.")
                break
        else:
            silence_start = None

        if elapsed >= MAX_DURATION:
            print("[Audio] Max duration reached — stopping.")
            break

    stream.stop_stream()
    stream.close()
    pa.terminate()

    return b"".join(frames)


def pcm_to_wav(pcm_bytes: bytes) -> bytes:
    """Wrap raw PCM bytes in a WAV container (in-memory)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)          # 16-bit = 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Playback
# ---------------------------------------------------------------------------

_mixer_initialized = False


def _ensure_mixer() -> None:
    global _mixer_initialized
    if not _mixer_initialized:
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.init()
        _mixer_initialized = True


def play_audio_file(path: str | Path) -> None:
    """
    Block until an audio file (mp3/wav) finishes playing.

    Args:
        path: Filesystem path to the audio file.
    """
    _ensure_mixer()
    pygame.mixer.music.load(str(path))
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.05)


def play_audio_bytes(data: bytes, suffix: str = ".mp3") -> None:
    """
    Play audio from an in-memory bytes object (blocking).

    Safe to call from a thread or executor — uses pygame which is
    thread-safe once the mixer is initialised.

    Args:
        data:   Raw audio bytes.
        suffix: File extension hint for pygame ('.mp3' or '.wav').
    """
    _ensure_mixer()
    buf = io.BytesIO(data)
    pygame.mixer.music.load(buf, suffix)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.05)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rms(data: bytes) -> float:
    """
    Compute root-mean-square energy of a 16-bit PCM chunk.

    Uses numpy — works on all Python versions (replaces audioop which
    was removed in Python 3.13).
    """
    if not data:
        return 0.0
    audio = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(audio ** 2)))
