# AI Wife App

An AI companion with personality, voice, and real-world skills — running on your own hardware.

She manages your emails, schedules your calendar, searches the web, and chats with you in a custom-cloned voice through a 3D anime avatar.

## Architecture

```
Flutter Mobile App ─┐
                    ├──► FastAPI Server ──► Ollama (LLM)
Web UI (3D Avatar) ─┘        │               Voicebox (TTS)
                             │               Whisper (STT)
                             ├──► Gmail API
                             ├──► Google Calendar API
                             ├──► SearXNG (Web Search)
                             └──► MCP Desktop Control
```

**Dual-mode agent** inspired by CoPaw:
- **Chat mode** — fast, no tools, `think=false`
- **Assist mode** — ReAct loop with tools, human-in-the-loop confirmation before execution

## Features

| Category | Details |
|----------|---------|
| **LLM** | Qwen3.5 27B/9B/7B via Ollama, model hot-swap at runtime |
| **TTS** | Qwen3-TTS via Voicebox, custom voice cloning (28s sample) |
| **STT** | Whisper (medium) |
| **Email** | Gmail OAuth2 — read, send, search, delete |
| **Calendar** | Google Calendar — view, create, update, delete |
| **Web Search** | SearXNG self-hosted search |
| **Browser** | Headless browser automation (navigate, click, extract) |
| **Desktop** | Screenshot, click, type, hotkeys via MCP |
| **Files** | Read, write, list, delete local files |
| **Memory** | SQLite + semantic search, auto-learns from conversations |
| **Heartbeat** | Cron-based scheduled tasks (morning greeting, event reminders) |
| **Soul** | Markdown-defined personality, editable at runtime |
| **3D Avatar** | VRM model viewer with FBX animations (idle, think, wave) |

## Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) with a Qwen model
- [Voicebox](https://github.com/voicebox-tts/voicebox) (optional, for TTS)
- Flutter 3.x (optional, for mobile app)

### 1. Setup

```bash
cd server
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Google OAuth (for email & calendar)
python setup_google_auth.py
```

### 2. Configure

Edit `config/server_config.yaml`:

```yaml
llm:
  provider: "ollama"
  base_url: "http://localhost:11434"  # or custom port
  model: "ultra"                      # smart7 | smart9 | ultra

tts:
  provider: "voicebox"
  voicebox_api_url: "http://localhost:17493"
  voicebox_profile_id: "your-profile-id"  # from voice cloning
```

### 3. Run

```bash
# Start Ollama
ollama serve &

# Start Voicebox (optional)
cd ~/voicebox && source backend/venv/bin/activate
python -m backend.main --port 17493 &

# Start server
cd server && source venv/bin/activate
python main.py --model ultra
```

Open `http://localhost:8000` for the Web UI.

### Model Presets

| Preset | Model | VRAM | Use Case |
|--------|-------|------|----------|
| `smart7` | Qwen 2.5 7B | ~6 GB | Fast, lightweight |
| `smart9` | Qwen 3.5 9B | ~8 GB | Balanced |
| `ultra` | Qwen 3.5 27B | ~20 GB | Best quality |

Switch at runtime: `POST /api/config/model {"model": "smart9"}`

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat/stream` | POST | SSE streaming chat |
| `/api/chat` | POST | Non-streaming chat |
| `/api/chat/confirm/{id}` | POST | Confirm tool execution plan |
| `/api/chat/deny/{id}` | POST | Cancel tool execution plan |
| `/api/tts` | POST | Text-to-speech |
| `/api/stt` | POST | Speech-to-text |
| `/api/soul` | GET/PUT | Read/update personality |
| `/api/memory/list` | GET | List stored memories |
| `/api/config/model` | POST | Switch LLM model |
| `/api/config/models` | GET | List available models |
| `/api/health` | GET | Component status |
| `/ws/{client_id}` | WS | WebSocket (mobile app) |

## Project Structure

```
ai_wife_app/
├── server/
│   ├── main.py              # FastAPI server + all endpoints
│   ├── agent.py             # Dual-mode ReAct agent orchestrator
│   ├── llm_client.py        # Ollama / OpenAI-compatible LLM client
│   ├── tts_engine.py        # Voicebox / CosyVoice TTS
│   ├── config.py            # Pydantic config with CLI model override
│   ├── soul/                # Personality definition (SOUL.md)
│   ├── memory/              # SQLite memory store with semantic search
│   ├── heartbeat/           # Cron scheduler for proactive tasks
│   ├── skills/builtin/      # Tool implementations
│   │   ├── email_skill.py
│   │   ├── calendar_skill.py
│   │   ├── search_skill.py
│   │   ├── browser_skill.py
│   │   ├── desktop_skill.py
│   │   ├── file_skill.py
│   │   └── opencode_skill.py
│   └── static/              # Web UI (3D avatar + chat)
├── mobile_app/              # Flutter app
│   └── lib/
│       ├── screens/         # Chat, settings, home
│       ├── services/        # API client
│       └── models/          # Data models
└── config/
    └── server_config.yaml   # All configuration
```

## Qwen3.5 Free API

No GPU? Use Alibaba's free Qwen API tier to get started without local hardware:

1. Get a free API key at [DashScope](https://dashscope.console.aliyun.com/)
2. Configure in `config/server_config.yaml`:

```yaml
llm:
  provider: "openai"  # DashScope is OpenAI-compatible
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  model: "qwen3.5-32b-free"
  api_key: "sk-your-dashscope-key"
```

This frees all GPU VRAM for TTS, or lets you run entirely without a GPU.

## Known Limitations

- **VRAM**: 27B LLM (~20GB) + TTS 1.7B (~4GB) needs >24GB VRAM to run simultaneously
- **Workaround**: Use a smaller model preset, disable TTS, or use external API
- **Planned**: Full provider system (Alibaba DashScope, OpenAI, etc.) with API key management in UI

## License

MIT
