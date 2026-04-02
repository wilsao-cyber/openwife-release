# Dual-API Fallback + Feature Testing Design

**Date:** 2026-04-03
**Status:** Approved

---

## 1. Dual-API Fallback Architecture

### Problem
DashScope (Alibaba Cloud) blocks explicit content at the API level (`400 data_inspection_failed`). OpenRouter does not. We need both: DashScope for daily tasks (fast, cheap, tool support) and OpenRouter as automatic fallback when content is blocked.

### Design: LLMClient Internal Fallback

The `LLMClient` holds two sets of credentials (primary + fallback). On every request, it tries primary first. If it receives a 400 content moderation error, it automatically retries with the fallback provider. This is transparent to all callers (agent chat, agent assist, TTS translation, memory extraction).

#### LLMClient Changes
- New attributes: `fallback_provider`, `fallback_base_url`, `fallback_api_key`, `fallback_model`
- `_openai_complete()`: catch 400 + `data_inspection_failed` → rebuild request with fallback config and retry
- `_openai_stream()`: detect 400 or empty response → rebuild request with fallback config and retry
- `_ollama_complete()` / `_ollama_stream()`: no change (local Ollama has no moderation)
- New method: `update_fallback(provider, base_url, api_key, model)` for runtime config
- New property: `has_fallback` → bool

#### Flow
```
User message → LLMClient.chat()
  → try primary (DashScope)
    → 200 OK → return response
    → 400 data_inspection_failed → log warning, retry with fallback (OpenRouter)
      → 200 OK → return response
      → any error → raise/yield error
  → non-400 error → normal retry/raise logic (unchanged)
```

#### Config Changes
`LLMConfig` adds:
- `fallback_provider: str = ""`
- `fallback_base_url: str = ""`
- `fallback_api_key: str = ""`
- `fallback_model: str = ""`

`server_config.yaml` adds under `llm:`:
```yaml
fallback_provider: "openrouter"
fallback_base_url: "https://openrouter.ai/api"
fallback_api_key: ""
fallback_model: "qwen/qwen3.6-plus:free"
```

#### API Endpoint Changes
- `GET /api/config/provider` → also returns fallback info (`fallback_provider`, `fallback_model`, `has_fallback_key`)
- `POST /api/config/provider` → accepts optional `fallback_provider`, `fallback_base_url`, `fallback_api_key`, `fallback_model`

#### Frontend Changes
- Setup page: after primary provider fields, add collapsible "Fallback API (optional)" section with same fields (provider/base_url/model/api_key)
- Settings modal "LLM 供應商" tab: add fallback section below primary
- Both auto-fill presets when selecting provider
- Fallback is optional — if not configured, 400 errors surface normally

### What Does NOT Change
- `AgentOrchestrator` — no changes, uses `self.llm` as before
- `TTSEngine._translate_to_ja()` — uses `self._llm_client` as before
- `MemoryStore.extract_from_conversation()` — uses llm_client as before
- `SkillRegistry` — no changes
- All tool execution logic — no changes

---

## 2. Feature Testing Plan

End-to-end testing of all 7 skill modules through the Assist mode pipeline: natural language → LLM tool_calls → user confirm → execute → result summary.

### Test Matrix

| # | Skill | Tool | Test Command | Success Criteria |
|---|-------|------|-------------|-----------------|
| 1 | email | email_list | 「幫我看看最近的信件」 | Returns inbox list |
| 2 | email | email_send | 「寄一封測試信給 [address]」 | Gmail sends successfully |
| 3 | email | email_search | 「搜尋主旨含有 test 的信件」 | Returns search results |
| 4 | email | email_read | 「讀一下第一封信的內容」 | Returns full email body, displayed in panel |
| 5 | calendar | calendar_view | 「看看我今天的行程」 | Returns calendar events |
| 6 | calendar | calendar_create | 「幫我建一個明天下午三點的會議」 | Event created in Google Calendar |
| 7 | search | web_search | 「幫我搜尋今天台北天氣」 | SearXNG returns results |
| 8 | file | file_write | 「幫我寫一個 test.txt 內容 hello」 | File created |
| 9 | file | file_read | 「讀一下 test.txt」 | Returns file content |
| 10 | browser | browser_open | 「打開 example.com 擷取內容」 | Returns page text |
| 11 | desktop | desktop_screenshot | 「截一張螢幕畫面」 | Returns screenshot |
| 12 | opencode | opencode_run | 「執行 python -c "print(1+1)"」 | Returns "2" |

### Test Approach
1. **Backend unit test**: call `skill.execute()` directly, verify return format
2. **Frontend E2E test**: type command in chat → confirm plan → verify result displayed
3. **Fix on fail**: any failure is fixed immediately before moving to next test

### Dependencies
- Gmail OAuth token must be valid
- Google Calendar OAuth token must be valid
- SearXNG must be running on localhost:8080
- OpenCode server must be accessible (or mock for simple test)

---

## 3. Media Display Panel

### Problem
When the AI executes desktop screenshots, reads images, browses websites, or handles media, the result is only described in text. Users need to actually see the images/screenshots/videos.

### Design: Inline Thumbnail + Lightbox Panel

Two-layer display:
1. **Chat bubble thumbnail** — images/screenshots appear inline in the assistant's message bubble as clickable thumbnails (max 300px wide)
2. **Lightbox panel** — clicking a thumbnail opens a full-screen overlay with zoom, pan, and multi-image navigation

#### Supported Content Types
- **Images**: screenshots from `desktop_screenshot`, images from `file_read`, web screenshots from `browser`
- **Rich text**: email body from `email_read`, file content from `file_read` (text files), web page content from `browser`
- Any image URL or long text content returned by tools

#### Backend Changes
- Tool results that contain image data return `{"type": "image", "url": "/path/to/image", "alt": "description"}`
- `desktop_screenshot` → saves PNG to `output/screenshots/`, returns URL
- `browser` screenshot → same pattern
- New endpoint: `GET /api/media/{filename}` — serve images/screenshots from output directory
- `file_read` on image files → return base64 thumbnail + file URL

#### Frontend Changes
- **Thumbnail renderer**: when a tool result or chat message contains image data, render `<img>` thumbnail (max-width 300px, rounded corners, click handler)
- **Lightbox/Panel component**: full-screen dark overlay, two modes:
  - **Image mode**: centered image, zoom in/out (scroll wheel or buttons), pan (drag when zoomed), left/right arrows for multi-image, image counter ("2 / 5")
  - **Rich text mode**: formatted HTML content panel (max-width 800px, scrollable), used for email body, file content, web page text. Supports basic HTML rendering (headers, paragraphs, links, lists, tables)
  - Close button (X) or click outside / Esc key
- **CSS**: `.media-thumb`, `.content-preview`, `.lightbox-overlay`, `.lightbox-img`, `.lightbox-richtext`, zoom/pan transitions

#### Chat Message Format
Tool results containing images will include a `media` array:
```json
{
  "type": "tool_result",
  "tool": "desktop_screenshot",
  "result": {
    "success": true,
    "description": "螢幕截圖",
    "media": [
      {"type": "image", "url": "/api/media/screenshot_001.png", "alt": "Desktop screenshot"}
    ]
  }
}
```

For rich text content (email body, file content):
```json
{
  "type": "tool_result",
  "tool": "email_read",
  "result": {
    "success": true,
    "subject": "Meeting notes",
    "from": "boss@example.com",
    "media": [
      {"type": "richtext", "title": "Meeting notes", "html": "<h3>From: boss@example.com</h3><p>Email body here...</p>"}
    ]
  }
}
```

The frontend renders:
- **Images** → clickable thumbnail in chat bubble, opens lightbox image mode
- **Rich text** → clickable preview card in chat bubble (shows title + snippet), opens lightbox rich text mode with formatted HTML
