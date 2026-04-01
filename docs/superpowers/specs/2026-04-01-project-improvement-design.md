# AI Wife App - Full Project Improvement Design

**Date**: 2026-04-01
**Status**: Approved
**Approach**: Parallel Agent-Driven (3 streams)

## Overview

Comprehensive improvement of the AI Wife App covering stability, feature completion, mobile fixes, and test coverage. Work is split into 4 streams executed by 3 agents in parallel.

## Stream Assignment

| Stream | Scope | Agent | Priority |
|--------|-------|-------|----------|
| S1 | Server Stability | Claude Opus 4.6 | P0 |
| S2 | Server Feature Completion | Gemini 3.1 Pro | P0 |
| S3 | Mobile Fixes | Qwen 3.6 | P0 |
| S4 | Test Coverage | Claude Opus 4.6 | P1 (after S1-S3) |

## Execution Order

```
Phase 1 (parallel): S1 + S2 + S3
  - Exception: calendar_tool.py → S1 first (async), then S2 (timezone)
Phase 2: S4 (tests after all streams complete)
```

## File Ownership (No Conflicts)

| File | Owner |
|------|-------|
| `server/llm_client.py` | S1 |
| `server/websocket_manager.py` | S1 |
| `server/main.py` | S1 |
| `server/agent.py` | S1 |
| `server/tools/email_tool.py` | S1 |
| `server/tools/calendar_tool.py` | S1 then S2 |
| `server/vision_analyzer.py` | S2 |
| `server/stt_engine.py` | S2 |
| `server/tts_engine.py` | S2 |
| `server/config.py` | S2 |
| `mobile_app/lib/**` | S3 |

---

## S1: Server Stability (Claude Opus)

### 1. Async Fix — email_tool.py, calendar_tool.py
Wrap all synchronous Google API `.execute()` calls with `asyncio.to_thread()`.
Approximately 15-20 call sites across both files.

### 2. LLM Retry — llm_client.py
Add `_retry_with_backoff()`: max 3 retries, delays 1s/2s/4s.
Only retry on timeout and 5xx errors. 4xx raises immediately.

### 3. WebSocket Heartbeat — websocket_manager.py
- Per-client ping task every 30s on `connect()`
- Pong timeout 10s → auto disconnect + cleanup
- Cancel ping task on `disconnect()`

### 4. Tool Detection Hardening — agent.py
- try/except around JSON parse in `_detect_tools()`
- Validate tool name against known tool list
- On failure → return empty list (pure conversation)

### 5. CORS Restriction — main.py
Change `allow_origins=["*"]` to `["http://localhost:8000", "http://localhost:3000", "http://10.0.2.2:8000"]`

### 6. Conversation History Limit — agent.py
Enforce max 20 messages per client. FIFO eviction when exceeded.

---

## S2: Server Feature Completion (Gemini 3.1 Pro)

### 1. Vision Analyzer — vision_analyzer.py
Replace stub with real Ollama LLaVA integration:
- base64 encode image
- POST to Ollama `/api/generate` with model "llava" and image
- Keep `has_significant_change()` with image hash diff

### 2. STT Mock Fix — stt_engine.py
Mock returns `"[Speech recognition service not started]"` instead of fake Chinese text.

### 3. TTS Mock Fix — tts_engine.py
Mock generates valid 0.5s silence WAV (proper header + zero samples) instead of empty file.

### 4. Viseme Improvement — tts_engine.py
Add basic phoneme-to-viseme mapping table alongside amplitude analysis.

### 5. Timezone Config — config.py + calendar_tool.py
- Add `timezone: str = "Asia/Taipei"` to `CalendarConfig` in config.py
- Add `timezone` field to server_config.yaml
- Replace hardcoded timezone in calendar_tool.py with `self.config.timezone`
- **IMPORTANT**: Wait for S1 to finish async fixes on calendar_tool.py first

---

## S3: Mobile Fixes (Qwen 3.6)

### 1. Language Dynamic — voice_input_button.dart
- Accept `language` parameter from parent widget
- Map: `zh-TW` → `zh_TW`, `ja` → `ja_JP`, `en` → `en_US`
- Use mapped locale in `speech.listen(localeId: ...)`

### 2. State Management — chat_screen.dart
- Remove `findAncestorStateOfType<HomeScreenState>()`
- Create `ChatProvider extends ChangeNotifier` with messages list + current expression
- Register in main.dart MultiProvider
- ChatScreen and HomeScreen share state via Provider

### 3. WebSocket Connection — api_service.dart, home_screen.dart
- Call `connectWebSocket()` on app startup in HomeScreen.initState()
- Add auto-reconnect: 3s delay, max 5 attempts
- Handle incoming WebSocket messages (update chat, expressions)

### 4. Message Persistence — api_service.dart
- Save messages as JSON array in SharedPreferences (key: `chat_history`)
- Load on startup, write on each new message
- FIFO: keep latest 50 messages

### 5. Error Messages i18n — all screens
- Create error message map per language
- Use current language setting for error display

### 6. Chat History Limit — chat_screen.dart
- Enforce `Constants.maxChatHistory` (50) by trimming list

---

## S4: Test Coverage (After S1-S3)

| Target | Test Type | Key Scenarios |
|--------|-----------|---------------|
| `llm_client.py` | Unit | Retry on 5xx, no retry on 4xx, backoff timing |
| `websocket_manager.py` | Unit | Heartbeat sends ping, dead client cleanup |
| `agent.py` | Unit | Valid tool detection, malformed JSON fallback |
| `email_tool.py` | Integration | Async execution doesn't block |
| `calendar_tool.py` | Integration | Async + timezone from config |
| `vision_analyzer.py` | Unit | LLaVA call format, change detection |
| Flutter `ApiService` | Widget | WebSocket connect/reconnect, message persistence |

---

## Completion Criteria

- **S1**: Server starts with no warnings, Google API calls are non-blocking, WebSocket auto-cleans dead connections
- **S2**: `/api/vision/capture` returns real LLaVA analysis, STT/TTS never return mock data silently
- **S3**: Language switch affects voice input, chat history survives restart, WebSocket connected on launch
- **S4**: `pytest` passes all tests, critical paths covered
