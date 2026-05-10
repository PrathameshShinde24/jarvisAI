"""
server.py — Jarvis FastAPI entry point.

Phase 1: Starts the voice loop as a background task (echo mode).
Phase 2: Brain injected into voice loop (LLM responses).
Phase 8: POST /command and WS /ws added.

Run:
    python server.py
Then open http://localhost:8765 and say "Jarvis".
"""

import asyncio
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

load_dotenv()

from core.voice_loop import VoiceLoop

app        = FastAPI(title="Jarvis", version="0.1.0")
voice_loop = VoiceLoop()   # Phase 1: echo mode (no brain)

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
    """Liveness check — also returns current assistant state."""
    return {"status": "ok", "version": "0.1.0", "state": voice_loop._state}


# ---------------------------------------------------------------------------
# Lifecycle — start voice loop on server boot
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event() -> None:
    """Launch the voice loop as a background asyncio task."""
    asyncio.create_task(voice_loop.run())
    print("[Jarvis] Voice loop started. Say 'Jarvis' to activate.")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    voice_loop.stop()
    print("[Jarvis] Shutting down.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8765"))
    # reload=False so the voice loop isn't killed on file changes
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
