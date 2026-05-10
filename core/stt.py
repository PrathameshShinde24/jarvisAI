"""
core/stt.py — Speech-to-text via faster-whisper (local, private).

Uses the "base" Whisper model by default (~150 MB, good speed/quality balance).
The model is downloaded automatically on first use and cached by faster-whisper.
"""

from __future__ import annotations

import io

from faster_whisper import WhisperModel

# Singleton — load once, reuse across calls
_model: WhisperModel | None = None


def get_model(model_size: str = "base") -> WhisperModel:
    """Public alias for pre-warming the model before recording."""
    return _get_model(model_size)


def _get_model(model_size: str = "base") -> WhisperModel:
    global _model
    if _model is None:
        print(f"[STT] Loading Whisper '{model_size}' model (first run may download ~150 MB)...")
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
        print("[STT] Model ready.")
    return _model


def transcribe(audio: bytes, is_wav: bool = True) -> str:
    """
    Transcribe audio bytes to text.

    Args:
        audio:   Audio data — WAV bytes (default) or raw PCM.
        is_wav:  If True, treat `audio` as WAV-wrapped bytes.

    Returns:
        Transcribed string, stripped of leading/trailing whitespace.
        Returns an empty string if nothing was detected.
    """
    model = _get_model()
    audio_file = io.BytesIO(audio)

    segments, _info = model.transcribe(
        audio_file,
        beam_size=5,
        language="en",
        vad_filter=True,          # skip silent segments
        vad_parameters={"min_silence_duration_ms": 500},
    )

    text = " ".join(seg.text for seg in segments).strip()
    print(f"[STT] Transcribed: {text!r}")
    return text
