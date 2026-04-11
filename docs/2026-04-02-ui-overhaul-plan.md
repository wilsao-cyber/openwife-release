# AI Wife App UI Overhaul — Implementation Plan

**Goal:** Add model switcher, startup screen, debug panel, think-mode control, and 3D virtual display panels.

**Division of Labor:**
- **Claude (Backend):** API endpoints, config changes, LLM client modifications
- **Qwen OpenCode (Frontend):** index.html UI, 3D panels, startup screen, loading states

---

## Feature 1: Model Switcher + Think Disable

### 1A. Backend — Model Switch API (Claude)

**Files to modify:**
- `server/main.py` — new endpoint
- `server/llm_client.py` — add `think` option passthrough to Ollama
- `server/config.py` — expose MODEL_PRESETS

**API Endpoint:**

```
POST /api/config/model
Body: { "model": "smart7" }
Response: { "success": true, "model": "qwen2.5:7b", "preset": "smart7" }

GET /api/config/models
Response: { "models": [
  { "preset": "smart7", "actual": "qwen2.5:7b", "label": "Qwen 2.5 7B" },
  { "preset": "smart9", "actual": "qwen3.5:9b", "label": "Qwen 3.5 9B" },
  { "preset": "ultra", "actual": "qwen3.5:27b", "label": "Qwen 3.5 27B" }
], "current": "smart7" }
```

**LLM Client — think: false:**

Currently `llm_client.py:chat()` accepts `think` param but doesn't pass it to Ollama.
Ollama's OpenAI-compatible endpoint supports `options: { "think": false }` in payload.

Change in `llm_client.py`:
```python
# In chat() method, add to payload:
if not think:
    payload["options"] = {"think": False}
```

**Model switch logic in main.py:**
```python
@app.post("/api/config/model")
async def switch_model(data: dict):
    preset = data.get("model", "")
    actual = resolve_model(preset)
    llm_client.model = actual
    config.llm.model = actual
    return {"success": True, "model": actual, "preset": preset}

@app.get("/api/config/models")
async def list_models():
    labels = {
        "smart7": "Qwen 2.5 7B",
        "smart9": "Qwen 3.5 9B",
        "ultra": "Qwen 3.5 27B Q4",
    }
    models = [
        {"preset": k, "actual": v, "label": labels.get(k, k)}
        for k, v in MODEL_PRESETS.items()
        if k in ("smart7", "smart9", "ultra")
    ]
    return {"models": models, "current": config.llm.model}
```

### 1B. Frontend — Model Selector UI (Qwen)

**File:** `server/static/index.html`

**Requirements:**
- Add `<select id="model-selector">` in `#top-bar` next to mode/lang selectors
- On page load: `GET /api/config/models` to populate options and set current
- On change: `POST /api/config/model` with selected preset
- Show loading overlay during switch (spinner + "Switching model...")
- After switch completes, show brief toast notification "已切換至 Qwen 3.5 27B"

---

## Feature 2: Startup / Setup Screen

### 2A. Backend — Health Check API (Claude)

**File:** `server/main.py`

**Endpoint:**
```
GET /api/health
Response: {
  "status": "ready",  // or "starting"
  "components": {
    "llm": { "status": "ok", "model": "qwen2.5:7b", "latency_ms": 230 },
    "tts": { "status": "ok", "provider": "cosyvoice" },
    "stt": { "status": "ok", "provider": "whisper" },
    "email": { "status": "ok" },
    "calendar": { "status": "ok" },
    "memory": { "status": "ok", "count": 42 },
    "skills": { "status": "ok", "tool_count": 12 }
  }
}
```

**Run connectivity test:**
```
POST /api/health/test
Response: {
  "llm_test": { "ok": true, "reply": "OK", "latency_ms": 340 },
  "tts_test": { "ok": true },
  "stt_test": { "ok": true }
}
```

### 2B. Frontend — Setup Screen (Qwen)

**File:** `server/static/index.html`

**Requirements:**
- Full-screen overlay `#setup-screen` shown on first load (above everything)
- Structure:
  1. App title / logo area
  2. Model selector (same as Feature 1B, but larger)
  3. Language selector
  4. "Test Connection" button → calls `POST /api/health/test`
  5. Each component shows checkmark/cross as test completes
  6. "Enter" button (enabled only after all tests pass) → hides setup screen, shows main UI
- Save preferences to `localStorage` so next visit skips setup (but can return via settings)
- Settings modal gets new "System" tab with "Return to Setup" button
- Loading animation sequence:
  1. Fade in logo
  2. Progress bar as tests run
  3. VRM model loads in background during tests
  4. Smooth transition to main view

---

## Feature 3: Debug Panel

### 3A. Backend — Debug Info SSE (Claude)

**File:** `server/main.py`, `server/agent.py`

Add debug info to existing SSE events:
```python
# In agent.py chat_stream, yield additional debug events:
yield json.dumps({
    "type": "debug",
    "data": {
        "mode": mode,
        "model": self.llm.model,
        "intent_keywords": matched_keywords,
        "memory_hits": len(memories),
        "tool_calls": [...],
        "think_stripped": think_chars_removed,
        "tokens_est": len(full_response) // 2,
    }
}, ensure_ascii=False)
```

### 3B. Frontend — 3D Debug Overlay (Qwen)

**File:** `server/static/index.html`

**Requirements:**
- Semi-transparent panel overlaid on VRM container (CSS overlay, not 3D)
- Position: bottom-left of VRM container, `position: absolute`
- Toggle: small bug icon button in `#top-bar`
- Display real-time info from `debug` SSE events:
  - Current model name
  - Mode (chat/assist)
  - Intent classification result
  - Memory hits count
  - Tool calls being executed
  - Response time (TTFB + total)
  - Think blocks stripped (yes/no + char count)
- Auto-scroll log of recent events
- Semi-transparent dark background (`rgba(0,0,0,0.6)`) with monospace font
- Max height 40% of VRM container, scrollable

---

## Feature 4: 3D Virtual Display Panels (Rich Content)

> This is the most complex feature. It creates floating "screen" panels in the 3D scene.

### 4A. Backend — Content Rendering Hints (Claude)

**File:** `server/agent.py`

When tool results contain displayable content (email body, calendar events, images, search results), wrap them with display hints:

```python
# In confirm_plan, when yielding tool_result:
display_hint = None
if tool_name == "email_read":
    display_hint = {"type": "email", "title": result.get("subject", "")}
elif tool_name == "email_list":
    display_hint = {"type": "table", "title": "Inbox"}
elif tool_name == "calendar_view":
    display_hint = {"type": "calendar", "title": "Events"}

yield json.dumps({
    "type": "tool_result",
    "tool": tool_name,
    "result": result,
    "display_hint": display_hint,
}, ensure_ascii=False)
```

### 4B. Frontend — Virtual Display Panels (Qwen)

**File:** `server/static/index.html`

**Architecture:** Use HTML/CSS overlay panels positioned relative to VRM container (not Three.js planes — too complex for rich content).

**Requirements:**
- Class `VirtualPanel` manages floating panel instances
- Each panel is a `<div>` absolutely positioned over VRM container
- Panel features:
  - Title bar with drag handle + close button
  - Scrollable content area
  - Resize handles (corners)
  - Semi-transparent background matching app theme
  - Smooth open/close animations (scale + fade)
- Panel types:
  - **Email panel:** Renders email subject, from, date, body with basic formatting
  - **Table panel:** Renders email list / search results as scrollable list
  - **Calendar panel:** Renders events in timeline format
  - **Image panel:** Renders images with zoom
  - **Markdown panel:** Renders formatted text (code blocks, lists, etc.)
- Panels can be created by:
  1. Tool results with `display_hint` → auto-open panel
  2. LLM text containing `[panel:type]content[/panel]` markers
  3. User clicking on tool result cards in chat
- Max 3 panels open simultaneously (oldest auto-closes)
- Close via: X button, user says "關掉" / "close", or LLM responds with `[close_panel:id]`
- Panels should not block VRM character (position to sides)

**Implementation sketch:**
```javascript
class VirtualPanel {
  constructor(id, type, title, content) { ... }
  render() {
    // Create DOM element, position over VRM container
    // Add drag, resize, close handlers
  }
  updateContent(content) { ... }
  close() { /* animate out, remove DOM */ }
}

const panelManager = {
  panels: new Map(),
  maxPanels: 3,
  create(type, title, content) {
    if (this.panels.size >= this.maxPanels) {
      // Close oldest
    }
    const panel = new VirtualPanel(id, type, title, content);
    panel.render();
    this.panels.set(id, panel);
  },
  closeAll() { ... }
};
```

---

## Feature 5: Better Markdown / Rich Text in Chat

### Frontend Only (Qwen)

**File:** `server/static/index.html`

**Requirements:**
- Parse LLM responses for basic markdown:
  - `**bold**`, `*italic*`, `` `code` ``, ``` ```code blocks``` ```
  - Lists (- item, 1. item)
  - Links
- Use a lightweight markdown parser (can inline a minimal one, ~50 lines)
- Images in responses: render as `<img>` tags, clickable to open in Virtual Panel
- Apply to both chat messages and Virtual Panel content

---

## Work Assignment Summary

| Task | Assignee | Priority | Depends On |
|------|----------|----------|------------|
| 1A. Model switch API + think:false | **Claude** | P0 | — |
| 1B. Model selector UI | **Qwen** | P0 | 1A |
| 2A. Health check API | **Claude** | P0 | — |
| 2B. Startup screen | **Qwen** | P0 | 2A |
| 3A. Debug SSE events | **Claude** | P1 | — |
| 3B. Debug panel overlay | **Qwen** | P1 | 3A |
| 4A. Display hints in tool results | **Claude** | P1 | — |
| 4B. Virtual display panels | **Qwen** | P2 | 4A |
| 5. Markdown rendering in chat | **Qwen** | P1 | — |

**Execution Order:**
1. Claude does 1A + 2A + 3A + 4A in parallel (all backend, no dependencies)
2. Qwen does 1B + 2B + 5 after Claude's APIs are ready
3. Qwen does 3B + 4B last (more complex UI)

---

## Qwen OpenCode Task Spec

Copy this section to Qwen as its task brief:

```
你需要修改 server/static/index.html 完成以下前端功能：

### 任務 1: Model Selector（模型切換器）
- 在 #top-bar 加入 <select id="model-selector">
- 頁面載入時 GET /api/config/models 取得可用模型列表
- 切換時 POST /api/config/model { "model": "preset_name" }
- 切換中顯示 loading overlay（spinner + "切換模型中..."）
- 切換完成顯示 toast "已切換至 XXX"

### 任務 2: Startup Screen（起始畫面）
- 全屏 overlay #setup-screen，首次載入顯示
- 包含：模型選擇、語言選擇、"測試連線" 按鈕
- 測試連線呼叫 POST /api/health/test
- 每個元件顯示 ✓ 或 ✗
- 全部通過才能按 "進入" 進入主畫面
- localStorage 記住設定，下次跳過
- Settings 加入 "系統" tab 可回到起始畫面

### 任務 3: Debug Panel（除錯面板）
- VRM 容器左下角半透明面板
- #top-bar 加入 🐛 toggle 按鈕
- 顯示 SSE debug 事件：model、mode、intent、memory hits、tool calls、response time
- 深色半透明背景 + monospace 字型
- 自動捲動 log

### 任務 4: Virtual Display Panels（虛擬顯示面板）
- CSS overlay 浮動面板（不是 Three.js）
- 可拖曳、可調整大小、可關閉
- tool_result 含 display_hint 時自動開啟
- 面板類型：email、table、calendar、image、markdown
- 最多同時 3 個面板
- 用戶說 "關掉" 或 LLM 回 [close_panel:id] 可關閉

### 任務 5: Markdown 渲染
- 聊天訊息支援基本 markdown（粗體、斜體、code、code block、列表）
- 圖片渲染為 <img>，點擊開啟 Virtual Panel
- 套用到聊天和 Virtual Panel 內容

### Ollama think:false 注意
- 後端已處理 think:false 傳給 Ollama API
- 前端 _ThinkStripper 仍保留作為 fallback
```
