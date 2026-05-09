# JARVIS // Mission Control

A voice-activated AI assistant that runs on your laptop. Say **"Jarvis"** — it wakes up, listens, thinks, and acts.

Built with Python · FastAPI · Claude API · Whisper · Picovoice

---

## Features (build roadmap)

| Phase | Capability | Status |
|-------|-----------|--------|
| 1 | Voice loop — wake word → STT → TTS echo | 🔧 Building |
| 2 | LLM brain — Claude API + tool use | ⏳ Planned |
| 3 | System control — open apps, volume, notes | ⏳ Planned |
| 4 | Web tools — search, browse, fetch | ⏳ Planned |
| 5 | Productivity — Gmail + Calendar | ⏳ Planned |
| 6 | Conversational memory (vector DB) | ⏳ Planned |
| 7 | Desktop UI — animated orb + live transcript | ⏳ Planned |
| 8 | REST + WebSocket API | ⏳ Planned |
| 9 | Mobile companion app (React Native) | ⏳ Planned |
| 10 | Polish — latency, auth, docs | ⏳ Planned |

---

## Setup

### Prerequisites

- Python 3.11+
- FFmpeg — `winget install ffmpeg` (Windows) / `brew install ffmpeg` (macOS)
- On Windows, pyaudio may require: `pip install pipwin && pipwin install pyaudio`

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/jarvis.git
cd jarvis
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 2. API keys

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

| Key | Where to get it |
|-----|----------------|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) — free, no credit card |
| `PICOVOICE_ACCESS_KEY` | [console.picovoice.ai](https://console.picovoice.ai) — free tier |

### 3. Run

```bash
python server.py
```

Open `http://localhost:8765` in your browser. Say **"Jarvis"** to activate.

---

## Project Structure

```
jarvis/
├── core/               # Wake word, audio I/O, STT, TTS, LLM brain, memory
├── tools/              # Tool implementations (system, web, productivity)
├── ui/                 # Single-file HTML/CSS/JS desktop interface
├── mobile/             # React Native companion app (Phase 9)
├── data/               # Local vector DB, OAuth tokens (git-ignored)
├── server.py           # FastAPI entry point
├── requirements.txt
├── .env.example
└── README.md
```

---

## Architecture

```
Microphone
    │
    ▼
Porcupine (wake word)
    │  "Jarvis" detected
    ▼
faster-whisper (STT)
    │  transcription text
    ▼
Claude API (LLM brain + tool use)
    │  tool calls / text response
    ▼
Tool handlers (system / web / productivity)
    │  results
    ▼
edge-tts (TTS) → audio playback
    │
    ▼
WebSocket → Desktop UI / Mobile app
```

---

## Design

"Apple meets NASA mission control." Restrained, professional, futuristic.
Dark interface · single cyan accent · monospace readouts · no emoji.

---

## License

MIT
