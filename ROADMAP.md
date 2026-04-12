# OpenWife Roadmap

> Last updated: 2026-04-13 (v0.2.4)

## Current State (v0.2.4)

| Area | Status | Notes |
|------|--------|-------|
| TTS (Qwen3-TTS) | Done | CustomVoice + VoiceClone, 9 speakers, emotion instruct |
| Memory (L0/L1/KG) | Done | Wake-up context, Wing/Room, contradiction detection |
| Background Screen | Done | 3D plane + HTML overlay, search auto-display |
| Live2D | Removed | Pulled from v0.2.4, code exists in git history, needs redesign |
| nano-qwen3tts | Done | WSL2 accelerated backend, optional, default off |
| Security Hardening | Done | SSRF, path traversal, iframe sandbox |

---

## NOW (Next 2 weeks)

| ID | Initiative | Priority | Effort | Description |
|----|-----------|----------|--------|-------------|
| N1 | TTS Speed Optimization | P0 | Medium | RTF ~3.5 is slow. Options: 0.6B model toggle, sentence-level streaming (play first sentence while generating rest), translation cache |
| N2 | LLM Provider Stability | P0 | Small | Translation failure (401) sends Chinese to Japanese speaker = bad quality. Need: fallback translation, auto-switch speaker language on translation fail |
| N3 | STT Experience | P1 | Small | CPU mode has high latency. Consider: Whisper alternative, GPU/CPU dynamic switch based on TTS provider |
| N4 | Heartbeat Activation | P1 | Small | daily_reflection, morning_greeting etc are defined but disabled. Enable + test L1 auto-update via daily_reflection |
| N5 | Compactor Wiring | P1 | Small | MemoryCompactor exists but never called. Wire into heartbeat or post-extraction hook |

## NEXT (1-3 months)

| ID | Initiative | Priority | Effort | Description |
|----|-----------|----------|--------|-------------|
| X1 | Live2D Redesign | P1 | Large | Separate rendering pipeline, proper parameter-driven animation, motion file support, multi-model management. Reference: pixi-live2d-display v0.4 + Cubism SDK |
| X2 | Multimodal Input | P1 | Large | Image recognition (vision), document analysis, screenshot understanding |
| X3 | Background Screen v2 | P2 | Medium | Document reader, web browsing (iframe), shared whiteboard, code display |
| X4 | Skill Auto-Learning | P2 | Medium | Hermes-style closed learning loop: agent auto-creates + improves skills from successful interactions |
| X5 | Proactive Care System | P2 | Medium | Memory-driven proactive triggers: remember important dates, detect emotional dips, reach out when inactive |
| X6 | Multi-Platform Gateway | P3 | Large | Telegram / Discord / LINE integration, cross-platform conversation continuity |

## LATER (3-6 months)

| ID | Initiative | Priority | Effort | Description |
|----|-----------|----------|--------|-------------|
| L1 | Honcho User Modeling | P2 | Large | Deep user understanding: thinking patterns, values, communication preferences |
| L2 | Emotion State Engine | P2 | Medium | AI's own emotional state system (causal, not random), affects response style and proactive behavior |
| L3 | Voice Conversation Mode | P2 | Large | Full-duplex voice conversation (STT->LLM->TTS pipeline streaming, interrupt support) |
| L4 | VoiceEditing Integration | P3 | Small | When Qwen3-TTS-25Hz-1.7B-VoiceEditing releases, enable clone + instruct together |
| L5 | Local LLM Optimization | P3 | Medium | Ollama integration improvements, local model function calling and personality performance |

---

## Risks & Dependencies

| Risk | Impact | Mitigation |
|------|--------|------------|
| RTX 3090 VRAM limit (24GB) | nano-qwen3tts cannot coexist with STT on GPU | Keep qwen3tts as default; wait for larger VRAM GPU or cloud |
| Qwen3-TTS VoiceEditing unreleased | Clone + instruct cannot work simultaneously | Multi-emotion reference audio workaround |
| LLM translation depends on external API | Translation failure = TTS quality degradation | Local translation model or auto-fallback to Chinese speaker |
| Live2D Cubism SDK licensing | Commercial use requires Live2D license | Confirm license terms, or use open-source alternative (Spine) |

## Key Metrics

| Metric | Current (v0.2.4) | Target |
|--------|-------------------|--------|
| TTS RTF | ~3.5 | < 1.5 |
| TTS first-sentence latency | ~6s | < 3s |
| Memory recall accuracy | Unmeasured | > 85% |
| Server startup time | ~25s | < 15s |
| VRAM usage (qwen3tts) | ~8GB | < 8GB |

---

## Architecture Notes

### TTS Provider Chain
```
Config provider setting
  -> qwen3tts:       In-process Qwen3-TTS (Windows, ~8GB VRAM, RTF ~3.5)
  -> nano_qwen3tts:  WSL2 nano-qwen3tts server (HTTP, ~16GB VRAM, RTF ~1.0, needs GPU exclusive)
  -> voicebox:       Legacy Voicebox HTTP wrapper (deprecated)
```

### Memory Layer Stack
```
L0 Identity (~50 tokens)     - Always injected, auto-built from high-importance facts
L1 Key Facts (~120 tokens)   - Always injected, updated by daily_reflection heartbeat
L2 Semantic Search (top 3)   - Per-query, vector search with optional Wing filter
Knowledge Graph              - Temporal triples, contradiction detection, auto-extracted
```

### Key File Locations
```
server/tts_engine.py          - TTS providers, emotion instruct system
server/agent.py               - Chat/Assist orchestrator, memory integration
server/memory/memory_store.py - SQLite + embeddings, Wing/Room, extraction
server/memory/wake_up.py      - L0/L1 wake-up context
server/memory/knowledge_graph.py - Temporal KG + contradiction detection
server/soul/SOUL.md           - Character personality definition
server/soul/PROFILE.md        - User profile (auto-populated)
server/heartbeat/HEARTBEAT.md - Scheduled task definitions
server/static/index.html      - Main UI (Three.js + VRM + background screen)
server/static/js/chat.js      - Chat module, screen media display
server/static/js/audio.js     - BGM, SFX, lip sync, audio fallback
server/static/js/settings.js  - Settings UI, emotion prompt editor
config/server_config.yaml     - Runtime config (gitignored)
```
