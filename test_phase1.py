"""
test_phase1.py — Component tests for Phase 1.

Run individual tests to verify each part works before the full voice loop.
Does NOT test wake word or mic (those need manual testing).

Usage:
    python test_phase1.py tts        # test text-to-speech
    python test_phase1.py stt        # test speech-to-text (records 5 s from mic)
    python test_phase1.py server     # test server health endpoint
    python test_phase1.py all        # run all automated tests
"""

import sys
import asyncio


def test_tts() -> None:
    """Verify edge-tts synthesises and plays audio."""
    print("\n=== TTS Test ===")
    from core.tts import speak
    speak("Jarvis voice test successful. Text to speech is working.")
    print("[PASS] TTS works.")


def test_stt() -> None:
    """Record 5 seconds from mic and transcribe."""
    print("\n=== STT Test ===")
    from core.audio import pcm_to_wav, SAMPLE_RATE, CHANNELS, FORMAT, CHUNK
    from core.stt import transcribe, get_model
    import pyaudio

    # Pre-warm the model BEFORE recording so the window isn't wasted on download
    print("Pre-loading Whisper model (may download ~150 MB on first run)...")
    get_model()
    print("Model ready.")

    print("\nSpeak now — recording for 5 seconds...")
    pa     = pyaudio.PyAudio()
    stream = pa.open(rate=SAMPLE_RATE, channels=CHANNELS,
                     format=FORMAT, input=True, frames_per_buffer=CHUNK)
    frames = []
    total  = int(SAMPLE_RATE / CHUNK * 5)
    for i in range(total):
        frames.append(stream.read(CHUNK, exception_on_overflow=False))
        # Simple countdown every second
        remaining = 5 - int(i / (total / 5))
        if i % int(total / 5) == 0:
            print(f"  {remaining}s remaining...", end="\r")
    stream.stop_stream(); stream.close(); pa.terminate()
    print("\nRecording done.")

    wav  = pcm_to_wav(b"".join(frames))
    text = transcribe(wav)
    print(f"[STT] Transcribed: {text!r}")
    if text:
        print("[PASS] STT works.")
    else:
        print("[WARN] Nothing transcribed — try speaking louder or closer to the mic.")


def test_server() -> None:
    """Hit the /health endpoint on the running server."""
    print("\n=== Server Health Test ===")
    import httpx
    try:
        r = httpx.get("http://localhost:8765/health", timeout=3)
        print(f"[Server] Response: {r.json()}")
        print("[PASS] Server is running.")
    except Exception as e:
        print(f"[FAIL] Server not reachable: {e}")
        print("       Start it first with: python server.py")


def test_imports() -> None:
    """Verify all core modules import without errors."""
    print("\n=== Import Test ===")
    modules = [
        "core.audio", "core.tts", "core.stt",
        "core.brain", "core.memory", "core.voice_loop", "core.wake_word",
        "tools.system", "tools.web",
    ]
    for m in modules:
        try:
            __import__(m)
            print(f"  [OK] {m}")
        except Exception as e:
            print(f"  [FAIL] {m}: {e}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if cmd == "tts":
        test_tts()
    elif cmd == "stt":
        test_stt()
    elif cmd == "server":
        test_server()
    elif cmd == "imports":
        test_imports()
    elif cmd == "all":
        test_imports()
        test_tts()
        print("\nSkipping STT (needs mic) — run: python test_phase1.py stt")
        print("Skipping server (needs server running) — run: python test_phase1.py server")
    else:
        print(__doc__)
