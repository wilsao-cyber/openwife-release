# OpenWife - AI Companion App

## Project Overview
AI companion (AI Wife) application with 3D VRM character, voice synthesis, memory system, and multi-skill agent.

## Tech Stack
- **Backend**: FastAPI + Uvicorn (Python 3.11), dir: `server/`
- **Frontend**: HTML5 + Three.js + VRM, dir: `server/static/`
- **TTS**: Qwen3-TTS CustomVoice (in-process, `qwen-tts` pip package)
- **STT**: SenseVoice (FunASR, CPU mode to avoid GPU contention)
- **LLM**: DashScope / OpenRouter / Ollama (configurable)
- **DB**: SQLite (memories.db - embeddings + KG)
- **Search**: SearXNG (Docker, port 8080)

## How to Run
```bash
cd openwife/server
.venv/Scripts/python.exe launch.py   # or: python main.py (from server/ dir)
```
Preview server config: `.claude/launch.json` (use `ai-wife-server`)

## Key Architecture Decisions
- TTS provider is configurable: `qwen3tts` (default, in-process) or `nano_qwen3tts` (WSL2 server, faster but needs exclusive GPU)
- STT runs on CPU to avoid VRAM contention with TTS
- Memory uses L0/L1 wake-up context injected into every conversation
- Knowledge Graph tracks temporal facts with contradiction detection
- Background screen uses hybrid approach: Three.js plane for images (behind character), HTML overlay for iframe/video
- All emotion instruct prompts use multi-attribute format (pitch/speed/volume/texture/emotion/fluency)
- SenseVoice loads from local cache path to avoid network issues

## Current Version: v0.2.4
See ROADMAP.md for planned work.

## Known Limitations
- TTS RTF ~3.5 (1 second of audio takes 3.5 seconds to generate)
- VRAM: Qwen3-TTS 1.7B uses ~8GB, nano variant uses ~22GB (too much for 24GB GPU)
- Translation failure (no LLM API key in config) causes Chinese text sent to Japanese speaker
- WSL2 memory: limited to 12GB via .wslconfig
- SearXNG needs Docker Desktop running

## Config
- Runtime config: `config/server_config.yaml` (gitignored)
- Example config: `config/server_config.example.yaml`
- TTS provider: change `tts.provider` to `qwen3tts` or `nano_qwen3tts`
- Speaker: change `tts.qwen3tts_speaker` (Ono_Anna, Vivian, Serena, etc.)

## Important Notes for Development
- Always run server from `server/` directory (relative paths)
- `launch.py` handles cwd setup for preview server
- After editing Python files, restart server to apply changes
- After editing JS/HTML, hard refresh browser (Ctrl+Shift+R)
- SenseVoice model cached at `~/.cache/modelscope/hub/models/iic/SenseVoiceSmall`
- Qwen3-TTS model cached at `~/.cache/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice`
- ffmpeg.exe is in `.venv/Scripts/` (needed for STT audio decoding)
