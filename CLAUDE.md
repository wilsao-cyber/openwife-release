# OpenWife — AI Companion App

## What This Is
AI companion with 3D VRM anime character, Japanese TTS voice, Chinese STT, self-evolving personality, and web UI. Version 0.2.1.

## Tech Stack
- **Backend**: FastAPI (Python 3.12) — `server/main.py` (59 endpoints + WebSocket)
- **Frontend**: Single-page web app — `server/static/index.html` (Three.js + @pixiv/three-vrm)
- **LLM**: Cloud default (DashScope/OpenRouter), local Ollama optional
- **TTS**: Voicebox (Qwen3-TTS 1.7B) on GPU — `server/tts_engine.py`
- **STT**: SenseVoice (FunASR) with emotion detection — `server/stt_engine.py`
- **Memory**: SQLite + multilingual embeddings — `server/memory/memory_store.py`
- **Personality**: SOUL.md self-evolution — `server/soul/`

## Directory Structure
```
server/
  main.py            # FastAPI app, all endpoints
  agent.py           # ReAct agent, chat/assist modes
  llm_client.py      # Multi-provider LLM client
  tts_engine.py      # Voicebox TTS + emotion audio FX
  stt_engine.py      # SenseVoice STT
  config.py          # YAML config loader
  skills/builtin/    # 12 skill modules (self_evolution, code, browser, calendar, email...)
  soul/              # SOUL.md + PROFILE.md personality files
  memory/            # SQLite memory store
  heartbeat/         # Scheduled tasks (morning greeting, reflection...)
  static/
    index.html       # Web UI (4000+ lines, being modularized)
    js/              # vrm_controller.js, lip_sync.js, Three.js libs
    models/          # VRM character models
    animations/      # FBX animation files + registry.json
config/
  server_config.yaml # All service configuration
scripts/
  start_server.sh    # Server launcher
```

## How to Run
```bash
# Start server (from project root)
cd server && source venv/bin/activate && python main.py

# Start Voicebox TTS (separate terminal, needs GPU)
# Voicebox runs on port 17493

# Start Ollama (only if using local LLM)
# ollama serve --port 9090

# Mobile access via Tailscale
tailscale serve --bg --https 443 http://localhost:8000
```

## Platform Strategy
- **Web only** — no native mobile apps
- Mobile = phone browser + Tailscale HTTPS
- Flutter (mobile_app/) and React Native (openwife-app/) are abandoned and deleted
- Unity (open-wife/) is abandoned and deleted

## Development Rules
- **Never downgrade models** — keep full-power defaults (27B LLM, 1.7B TTS), add cloud provider flexibility instead
- **VRAM constraint**: RTX 3090 24GB can't run LLM + TTS simultaneously. Cloud LLM is the default to free GPU for TTS
- **Shader/KK work**: If ever revisited, use plugin content (KKShadersPlus, ShaderSwapper, MaterialEditor), never game originals
- **Frontend**: Being modularized into ES modules (js/chat.js, js/settings.js, etc.). Keep zero-build (no webpack/vite)

## Testing
```bash
cd server && python -m pytest tests/ -v
```
13 test modules, ~89 unit tests covering core systems.

## Key Config: config/server_config.yaml
- LLM: provider, model, temperature, max_tokens, fallback provider
- TTS: Voicebox URL, profile IDs (normal + horny variants), model size
- STT: SenseVoice model, language
- Integrations: Gmail OAuth, Google Calendar, SearXNG search
