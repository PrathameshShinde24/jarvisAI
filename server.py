"""
server.py — Jarvis FastAPI entry point.

Phase 1: Voice loop echo mode.
Phase 2: Brain (Groq LLM + tools) injected into voice loop.
Phase 3: POST /command REST endpoint for text-based testing + memory tools.

Run:
    python server.py
Then press CTRL+SPACE and speak, or POST to /command for text input.
"""

import asyncio
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

load_dotenv()

from core.voice_loop import VoiceLoop
from core.brain import Brain
from tools import ALL_SCHEMAS, ALL_HANDLERS

# ── WebSocket connection manager ──────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.append(ws)

    def disconnect(self, ws: WebSocket):
        self._clients.discard if hasattr(self._clients, 'discard') else None
        if ws in self._clients:
            self._clients.remove(ws)

    async def broadcast(self, data: dict):
        import json
        dead = []
        for ws in self._clients:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()

async def _on_state_change(state: str):
    await manager.broadcast({"type": "state", "state": state})

async def _on_transcript(role: str, text: str):
    await manager.broadcast({"type": "transcript", "role": role, "text": text})

voice_loop = VoiceLoop(on_state_change=_on_state_change, on_transcript=_on_transcript)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm models, wire Brain, start voice loop."""
    loop = asyncio.get_running_loop()

    # Pre-warm Whisper so it's never loading during a live recording
    await loop.run_in_executor(None, _prewarm_models)

    # Phase 2 — inject Brain into voice loop (replaces echo mode)
    voice_loop.brain = Brain(tools=ALL_SCHEMAS, tool_handlers=ALL_HANDLERS)
    print("[Jarvis] Brain online — Groq Llama 3.3 with tools ready.")

    task = asyncio.create_task(voice_loop.run())
    print("[Jarvis] Ready. Press CTRL+SPACE to activate.")

    yield  # server is running

    voice_loop.stop()
    task.cancel()
    print("[Jarvis] Shutdown complete.")


def _prewarm_models() -> None:
    """Load Whisper at startup so it's never downloading mid-conversation."""
    from core.stt import get_model
    print("[Jarvis] Pre-warming Whisper model...")
    get_model()
    print("[Jarvis] Whisper ready.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Jarvis", version="0.4.0", lifespan=lifespan)


class CommandRequest(BaseModel):
    text: str


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
    return {"status": "ok", "version": "0.4.0", "state": voice_loop._state}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket — streams state changes and transcript to the UI."""
    await manager.connect(ws)
    # Send current state immediately on connect
    import json
    await ws.send_text(json.dumps({"type": "state", "state": voice_loop._state}))
    try:
        while True:
            await ws.receive_text()   # keep connection alive; UI sends nothing
    except WebSocketDisconnect:
        manager.disconnect(ws)


@app.post("/command")
async def command(req: CommandRequest) -> dict:
    """
    Text-based command endpoint — bypasses voice entirely.
    Useful for testing tools without a microphone.

    POST /command
    { "text": "What's the weather in Mumbai?" }
    """
    if not req.text.strip():
        return {"error": "Empty command."}
    loop = asyncio.get_running_loop()
    # Brain.think() is synchronous (blocking Groq calls) — run off the event loop
    response = await loop.run_in_executor(None, voice_loop.brain.think, req.text.strip())
    return {"input": req.text.strip(), "response": response}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8765"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
