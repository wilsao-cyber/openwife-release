# AI Wife App 🌸

An AI companion with personality, voice, and real-world skills — featuring a 3D anime avatar with toon-shaded rendering and Japanese voice synthesis.

She manages your emails, schedules your calendar, searches the web, finds images/videos, and chats with you in a custom-cloned anime voice.

## Architecture

```
Flutter Mobile App ─┐
                    ├──► FastAPI Server ──► Cloud LLM (DashScope / OpenRouter / OpenAI)
Web UI (3D Avatar) ─┘        │               Voicebox TTS (Qwen3-TTS)
                             │               Whisper STT
                             ├──► Gmail API
                             ├──► Google Calendar API
                             ├──► SearXNG + Brave Search
                             └──► File System
```

**Dual-mode agent** inspired by CoPaw:
- **Chat mode** — fast streaming, no tools
- **Assist mode** — ReAct loop with tools, human-in-the-loop confirmation

**Dual-API fallback** — DashScope (primary) auto-falls back to OpenRouter when content is blocked.

## Features

| Category | Details |
|----------|---------|
| **LLM** | Multi-provider: DashScope, OpenRouter, OpenAI, Ollama. Auto-fallback on content block |
| **TTS** | Qwen3-TTS via Voicebox — Japanese voice synthesis with emotion control (7 emotions including intimate), dual voice profiles, sentence splitting |
| **STT** | Whisper (medium) with language auto-detection |
| **Email** | Gmail OAuth2 — list, read (rich text panel), send, search, delete. Auto-corrects invalid email IDs |
| **Calendar** | Google Calendar — view, create, update, delete. Natural language time parsing (Chinese/English) |
| **Web Search** | SearXNG (primary) + Brave Search API (fallback). Strict citation rules |
| **Image Search** | SearXNG image search with inline thumbnails and lightbox viewer |
| **Video Search** | SearXNG video search with embedded playback (YouTube iframe) |
| **Web Fetch** | Extract webpage content into rich text panel |
| **Files** | Read (text/image/video), write, list, delete. Images/videos display in media panel |
| **Memory** | SQLite + semantic search, auto-learns from conversations |
| **Heartbeat** | Cron-based scheduled tasks (morning greeting, event reminders) |
| **Soul** | Markdown-defined personality with intimate roleplay support, editable at runtime |
| **3D Avatar** | VRM model with MToon toon shading, FBX animations, 4 scene environments |

## UI

**Rose Dusk theme** — elegant dark UI with warm rose accents, designed to be easy on the eyes.

- **Fullscreen 3D** — VRM character fills the background, chat overlays from the right
- **Glass morphism** — floating capsule controls with backdrop blur
- **Scene system** — 4 switchable environments (Home/Sakura/Fantasy/Night) with matching lighting
- **Render settings** — 16+ adjustable sliders for lighting, post-processing, MToon materials. Save custom presets
- **Media panel** — inline thumbnails + lightbox for images, videos, rich text (email content, web pages)
- **TTS controls** — on/off toggle, Japanese translation drawer, audio caching

## Quick Start

### Prerequisites

- Python 3.10+
- Docker (for SearXNG)
- [Voicebox](https://github.com/voicebox-tts/voicebox) (optional, for TTS)
- Flutter 3.x (optional, for mobile app)

### 1. Setup

```bash
cd server
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Google OAuth (for email & calendar)
python setup_google_auth.py

# Start SearXNG (web search)
docker run -d --name searxng -p 8080:8080 searxng/searxng:latest
# Enable JSON API:
docker exec searxng sed -i '/^  formats:/,/^[^ ]/{s/    - html/    - html\n    - json/}' /etc/searxng/settings.yml
docker restart searxng
```

### 2. Configure

Edit `config/server_config.yaml`:

```yaml
llm:
  provider: "ollama"           # ollama | dashscope | openrouter | openai
  base_url: "http://localhost:9090"
  model: "smart9"
  api_key: ""                  # required for cloud providers
  fallback_provider: ""        # auto-fallback on content block
  fallback_base_url: ""
  fallback_api_key: ""
  fallback_model: ""

tts:
  provider: "voicebox"
  voicebox_api_url: "http://localhost:17493"
  voicebox_profile_id: "your-profile-id"
  voicebox_horny_profile_id: ""  # separate voice for intimate scenes
```

### 3. Run

```bash
# Start Voicebox (optional)
cd ~/voicebox && source backend/venv/bin/activate
python -m backend.main --port 17493 &

# Start server
cd server && source venv/bin/activate
python main.py
```

Open `http://localhost:8000` — select your provider and API key in the setup screen.

### Cloud Providers (No GPU Required)

| Provider | Setup | Content Filter |
|----------|-------|---------------|
| **DashScope** | [bailian.console.aliyun.com](https://bailian.console.aliyun.com/) | Yes (auto-fallback) |
| **OpenRouter** | [openrouter.ai](https://openrouter.ai/) | No |
| **OpenAI** | [platform.openai.com](https://platform.openai.com/) | Yes |
| **Ollama** | Local install | No |

**Recommended**: DashScope as primary (fast, cheap) + OpenRouter as fallback (uncensored).

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat/stream` | POST | SSE streaming chat |
| `/api/chat/confirm/{id}` | POST | Confirm tool execution |
| `/api/chat/deny/{id}` | POST | Cancel tool execution |
| `/api/tts` | POST | Text-to-speech (returns audio URL + Japanese text) |
| `/api/stt` | POST | Speech-to-text |
| `/api/config/provider` | GET/POST | Provider settings (primary + fallback) |
| `/api/config/provider-models` | GET | List available models per provider |
| `/api/soul` | GET/PUT | Read/update personality |
| `/api/memory/list` | GET | List stored memories |
| `/api/media/{filename}` | GET | Serve images/screenshots/media |
| `/api/health` | GET | Component status |
| `/ws/{client_id}` | WS | WebSocket (mobile app) |

## Project Structure

```
ai_wife_app/
├── server/
│   ├── main.py              # FastAPI server + all endpoints
│   ├── agent.py             # Dual-mode ReAct agent
│   ├── llm_client.py        # Multi-provider LLM client with fallback
│   ├── tts_engine.py        # Japanese TTS pipeline (translate → split → synthesize)
│   ├── config.py            # Pydantic config
│   ├── soul/                # Personality (SOUL.md + PROFILE.md)
│   ├── memory/              # SQLite memory with semantic search
│   ├── heartbeat/           # Cron scheduler
│   ├── skills/builtin/      # Tool implementations
│   │   ├── email_skill.py   # Gmail (with auto-ID correction)
│   │   ├── calendar_skill.py # Google Calendar (with time parsing)
│   │   ├── search_skill.py  # Web/image/video search + web fetch
│   │   ├── file_skill.py    # File ops (text/image/video)
│   │   └── browser_skill.py # Browser automation
│   ├── tools/               # Low-level tool wrappers
│   └── static/              # Web UI (single-page, 3D avatar)
├── mobile_app/              # Flutter app
└── config/
    └── server_config.yaml
```

## License

MIT
