"""
server.py — Jarvis FastAPI entry point.

Starts the voice loop as a background task and exposes:
  GET  /          → desktop UI (Phase 7)
  POST /command   → text command, returns response (Phase 8)
  WS   /ws        → real-time state + transcript (Phase 8)
  POST /transcribe → audio file → transcribed text (Phase 8)
"""

import asyncio
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

load_dotenv()

app = FastAPI(title="Jarvis", version="0.1.0")

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """Serve the desktop UI (added in Phase 7)."""
    ui_path = os.path.join(os.path.dirname(__file__), "ui", "index.html")
    if os.path.exists(ui_path):
        with open(ui_path, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Jarvis — UI coming in Phase 7</h1>")


@app.get("/health")
async def health() -> dict:
    """Simple liveness check."""
    return {"status": "ok", "version": "0.1.0"}


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup_event() -> None:
    """Start background tasks when the server comes up."""
    # Voice loop will be registered here in Phase 1
    print("[Jarvis] Server started. Voice loop will be wired up in Phase 1.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8765"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
