"""
server.py — Jarvis FastAPI entry point.

Phase 1: Voice loop in echo mode (hotkey → record → STT → TTS echo).
Phase 2: Brain injected for LLM responses.
Phase 8: POST /command and WS /ws added.

Run:
    python server.py
Then press CTRL+SPACE and speak.
"""

import asyncio
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

load_dotenv()

from core.voice_loop import VoiceLoop

voice_loop = VoiceLoop()


# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated on_event)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm models and start voice loop on boot; clean up on shutdown."""
    # ── Startup ──
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _prewarm_models)
    task = asyncio.create_task(voice_loop.run())
    print("[Jarvis] Ready. Press CTRL+SPACE to activate.")

    yield  # server is running

    # ── Shutdown ──
    voice_loop.stop()
    task.cancel()
    print("[Jarvis] Shutdown complete.")


def _prewarm_models() -> None:
    """Load Whisper at startup so it's never downloading during a live recording."""
    from core.stt import get_model
    print("[Jarvis] Pre-warming Whisper model...")
    get_model()
    print("[Jarvis] Whisper ready.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Jarvis", version="0.1.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """Serve the desktop UI (Phase 7)."""
    ui_path = os.path.join(os.path.dirname(__file__), "ui", "index.html")
    if os.path.exists(ui_path):
        with open(ui_path, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Jarvis — UI coming in Phase 7</h1>")


@app.get("/health")
async def health() -> dict:
    """Liveness check — returns current assistant state."""
    return {"status": "ok", "version": "0.1.0", "state": voice_loop._state}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8765"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
