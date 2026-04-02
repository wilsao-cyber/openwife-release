# Dual-API Fallback + Feature Testing + Media Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic DashScope→OpenRouter fallback, test all 12 tool endpoints E2E, and build inline media/rich-text display panel.

**Architecture:** LLMClient gains fallback credentials; on 400 content-moderation it retries with fallback. Frontend gets lightbox for images + rich text. All tools tested backend-first then frontend E2E.

**Tech Stack:** Python/FastAPI, httpx, vanilla JS (index.html)

---

### Task 1: LLMConfig + YAML — Add Fallback Fields

**Files:**
- Modify: `server/config.py:24-35`
- Modify: `config/server_config.yaml:6-13`

- [ ] **Step 1: Add fallback fields to LLMConfig**

In `server/config.py`, add 4 fields after `api_key`:

```python
class LLMConfig(BaseSettings):
    provider: str = "ollama"
    base_url: str = "http://localhost:9090"
    model: str = "smart7"
    temperature: float = 0.7
    max_tokens: int = 2048
    api_key: str = ""
    fallback_provider: str = ""
    fallback_base_url: str = ""
    fallback_api_key: str = ""
    fallback_model: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        self.model = resolve_model(self.model)
```

- [ ] **Step 2: Add fallback to server_config.yaml**

In `config/server_config.yaml`, under `llm:`:

```yaml
llm:
  provider: "ollama"
  base_url: "http://localhost:9090"
  model: "smart7"
  temperature: 0.7
  max_tokens: 2048
  api_key: ""
  fallback_provider: ""
  fallback_base_url: ""
  fallback_api_key: ""
  fallback_model: ""
```

- [ ] **Step 3: Verify config loads**

Run: `cd server && source venv/bin/activate && python3 -c "from config import config; print(f'fallback={config.llm.fallback_provider!r}')"`
Expected: `fallback=''`

- [ ] **Step 4: Commit**

```bash
git add server/config.py config/server_config.yaml
git commit -m "feat: add fallback provider fields to LLMConfig"
```

---

### Task 2: LLMClient — Fallback Logic for Non-Streaming

**Files:**
- Modify: `server/llm_client.py`

- [ ] **Step 1: Add fallback attributes and helpers**

After `self.client = httpx.AsyncClient(timeout=300.0)` in `__init__`, add:

```python
        self.fallback_provider = config.fallback_provider
        self.fallback_base_url = config.fallback_base_url
        self.fallback_api_key = config.fallback_api_key
        self.fallback_model = config.fallback_model
```

Add property and methods after `_auth_headers`:

```python
    @property
    def has_fallback(self) -> bool:
        return bool(self.fallback_provider and self.fallback_api_key and self.fallback_base_url)

    def _fallback_auth_headers(self) -> dict:
        if self.fallback_api_key:
            return {"Authorization": f"Bearer {self.fallback_api_key}"}
        return {}

    def _is_content_blocked(self, error: httpx.HTTPStatusError) -> bool:
        """Check if the error is a content moderation block."""
        if error.response.status_code != 400:
            return False
        try:
            body = error.response.json()
            code = body.get("error", {}).get("code", "")
            return code in ("data_inspection_failed", "content_filter", "content_policy_violation")
        except Exception:
            return False

    def update_fallback(self, provider: str, base_url: str, api_key: str, model: str):
        self.fallback_provider = provider
        self.fallback_base_url = base_url
        self.fallback_api_key = api_key
        self.fallback_model = model
        logger.info(f"Fallback updated: {provider} @ {base_url}, model={model}")
```

- [ ] **Step 2: Add fallback to `_openai_complete`**

Replace the current `_openai_complete` method. Key change: catch 400 content block, retry with fallback:

```python
    async def _openai_complete(self, payload: dict) -> str | dict:
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self.client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers=self._auth_headers(),
                )
                response.raise_for_status()
                data = response.json()
                message = data["choices"][0]["message"]
                if message.get("tool_calls"):
                    return {
                        "content": message.get("content", ""),
                        "tool_calls": message["tool_calls"],
                    }
                return message.get("content", "")
            except httpx.HTTPStatusError as e:
                if self._is_content_blocked(e) and self.has_fallback:
                    logger.warning(f"Content blocked by {self.provider}, falling back to {self.fallback_provider}")
                    return await self._fallback_complete(payload)
                if e.response.status_code < 500:
                    raise
                last_error = e
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(self.RETRY_DELAYS[attempt])
        raise last_error or Exception("LLM request failed after all retries")

    async def _fallback_complete(self, original_payload: dict) -> str | dict:
        """Retry a blocked request using the fallback provider."""
        payload = {**original_payload, "model": self.fallback_model}
        payload.pop("enable_thinking", None)
        headers = self._fallback_auth_headers()
        response = await self.client.post(
            f"{self.fallback_base_url}/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        message = data["choices"][0]["message"]
        if message.get("tool_calls"):
            return {"content": message.get("content", ""), "tool_calls": message["tool_calls"]}
        return message.get("content", "")
```

- [ ] **Step 3: Verify import**

Run: `python3 -c "from llm_client import LLMClient; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add server/llm_client.py
git commit -m "feat: add fallback provider for non-streaming LLM calls"
```

---

### Task 3: LLMClient — Fallback Logic for Streaming

**Files:**
- Modify: `server/llm_client.py`

- [ ] **Step 1: Add fallback to `_openai_stream`**

Replace the current `_openai_stream`. Key change: on 400 content block, yield from fallback stream:

```python
    async def _openai_stream(self, payload: dict) -> AsyncGenerator[str, None]:
        headers = self._auth_headers()
        url = f"{self.base_url}/v1/chat/completions"
        logger.info(f"OpenAI stream: {url}, model={payload.get('model')}, auth={'Bearer ***' + self.api_key[-4:] if self.api_key else 'none'}")
        try:
            async with self.client.stream(
                "POST", url, json=payload, headers=headers,
            ) as response:
                if response.status_code == 400 and self.has_fallback:
                    body = await response.aread()
                    try:
                        err = json.loads(body)
                        code = err.get("error", {}).get("code", "")
                    except Exception:
                        code = ""
                    if code in ("data_inspection_failed", "content_filter", "content_policy_violation"):
                        logger.warning(f"Stream content blocked by {self.provider}, falling back to {self.fallback_provider}")
                        async for chunk in self._fallback_stream(payload):
                            yield chunk
                        return
                    logger.error(f"OpenAI stream HTTP 400: {body.decode()[:300]}")
                    yield "[Error: API returned 400]"
                    return
                if response.status_code != 200:
                    body = await response.aread()
                    logger.error(f"OpenAI stream HTTP {response.status_code}: {body.decode()[:300]}")
                    yield f"[Error: API returned {response.status_code}]"
                    return
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices")
                        if not choices:
                            logger.warning(f"Stream chunk missing 'choices': {data[:200]}")
                            continue
                        delta = choices[0].get("delta", {})
                        content = delta.get("content") or ""
                        if content:
                            yield content
        except Exception as e:
            logger.error(f"OpenAI stream failed: {e}")
            yield f"[Error: {str(e)[:100]}]"

    async def _fallback_stream(self, original_payload: dict) -> AsyncGenerator[str, None]:
        """Stream from fallback provider."""
        payload = {**original_payload, "model": self.fallback_model, "stream": True}
        payload.pop("enable_thinking", None)
        headers = self._fallback_auth_headers()
        url = f"{self.fallback_base_url}/v1/chat/completions"
        logger.info(f"Fallback stream: {url}, model={self.fallback_model}")
        try:
            async with self.client.stream(
                "POST", url, json=payload, headers=headers,
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    logger.error(f"Fallback stream HTTP {response.status_code}: {body.decode()[:300]}")
                    yield f"[Error: fallback returned {response.status_code}]"
                    return
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices")
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        content = delta.get("content") or ""
                        if content:
                            yield content
        except Exception as e:
            logger.error(f"Fallback stream failed: {e}")
            yield f"[Error: {str(e)[:100]}]"
```

- [ ] **Step 2: Verify import**

Run: `python3 -c "from llm_client import LLMClient; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add server/llm_client.py
git commit -m "feat: add fallback provider for streaming LLM calls"
```

---

### Task 4: Backend API — Fallback Provider Endpoints + Media Serving

**Files:**
- Modify: `server/main.py`

- [ ] **Step 1: Update GET /api/config/provider**

```python
@app.get("/api/config/provider")
async def get_provider():
    return {
        "provider": config.llm.provider,
        "base_url": config.llm.base_url,
        "model": config.llm.model,
        "has_api_key": bool(config.llm.api_key),
        "fallback_provider": config.llm.fallback_provider,
        "fallback_base_url": config.llm.fallback_base_url,
        "fallback_model": config.llm.fallback_model,
        "has_fallback_key": bool(config.llm.fallback_api_key),
    }
```

- [ ] **Step 2: Update POST /api/config/provider — add fallback handling**

After existing primary provider logic, add:

```python
    fb_provider = data.get("fallback_provider", "").strip()
    fb_base_url = data.get("fallback_base_url", "").strip()
    fb_api_key = data.get("fallback_api_key", "").strip()
    fb_model = data.get("fallback_model", "").strip()

    if fb_provider and fb_api_key:
        llm_client.update_fallback(fb_provider, fb_base_url, fb_api_key, fb_model)
        config.llm.fallback_provider = fb_provider
        config.llm.fallback_base_url = fb_base_url
        config.llm.fallback_api_key = fb_api_key
        config.llm.fallback_model = fb_model
```

Add `"has_fallback": llm_client.has_fallback` to the return dict.

- [ ] **Step 3: Add media endpoint**

```python
@app.get("/api/media/{filename}")
async def get_media(filename: str):
    import os
    for directory in ["./output/screenshots", "./output/audio", "./output/media"]:
        path = os.path.join(directory, filename)
        if os.path.exists(path):
            return FileResponse(path)
    raise HTTPException(status_code=404, detail="File not found")
```

- [ ] **Step 4: Create output directories in startup**

```python
os.makedirs("./output/screenshots", exist_ok=True)
os.makedirs("./output/media", exist_ok=True)
```

- [ ] **Step 5: Commit**

```bash
git add server/main.py
git commit -m "feat: fallback provider endpoints + media serving"
```

---

### Task 5: Frontend — Fallback Provider UI

**Files:**
- Modify: `server/static/index.html`

- [ ] **Step 1: Add fallback fields to Setup page**

After `#setup-cloud-fields`, add a collapsible fallback section with provider select, model input, and API key input. Show it when cloud provider is selected.

- [ ] **Step 2: Update setupProvider change handler**

Show/hide fallback fields alongside cloud fields.

- [ ] **Step 3: Include fallback in enter button POST**

Send `fallback_provider`, `fallback_base_url`, `fallback_api_key`, `fallback_model` in the `/api/config/provider` POST body.

- [ ] **Step 4: Persist fallback in localStorage**

Save/restore `ai-wife-fb-provider`, `ai-wife-fb-key`, `ai-wife-fb-model`.

- [ ] **Step 5: Commit**

```bash
git add server/static/index.html
git commit -m "feat: fallback provider UI in setup page"
```

---

### Task 6: Frontend — Lightbox + Media Panel

**Files:**
- Modify: `server/static/index.html`

- [ ] **Step 1: Add lightbox CSS**

Styles for `.media-thumb`, `.content-preview`, `#lightbox`, `#lightbox-img`, `#lightbox-richtext`, navigation arrows, zoom.

- [ ] **Step 2: Add lightbox HTML**

Before `</body>`, add the lightbox overlay with close button, prev/next arrows, img element, richtext div, and nav counter.

- [ ] **Step 3: Add lightbox JS**

`openLightbox(items, index)`, `showLightboxItem()`, keyboard/click close, scroll zoom for images, `renderMediaInChat(container, media)` function.

Note: For rich text content (email bodies), use a sanitized approach — the content comes from our own backend (email API, file reads) not user input. Render via safe DOM construction or use `textContent` where possible. For email HTML bodies that need rendering, set content inside an iframe with sandbox attribute for isolation:

```javascript
if (item.type === 'richtext') {
  lbRichtext.textContent = ''; // clear
  if (item.html.includes('<')) {
    // HTML content - use sandboxed iframe
    const iframe = document.createElement('iframe');
    iframe.sandbox = 'allow-same-origin';
    iframe.style.cssText = 'width:100%;height:80vh;border:none;background:white;border-radius:8px;';
    lbRichtext.appendChild(iframe);
    iframe.srcdoc = item.html;
  } else {
    // Plain text
    const pre = document.createElement('pre');
    pre.style.cssText = 'white-space:pre-wrap;';
    pre.textContent = item.html;
    lbRichtext.appendChild(pre);
  }
  lbRichtext.style.display = 'block';
}
```

- [ ] **Step 4: Hook into tool_result SSE handler**

In the `case 'tool_result':` handler, after error badge logic:

```javascript
if (r && r.media) {
  renderMediaInChat(aiDiv, r.media);
}
```

- [ ] **Step 5: Commit**

```bash
git add server/static/index.html
git commit -m "feat: lightbox panel for images and rich text display"
```

---

### Task 7: Backend — Test & Fix Each Skill

**Files:**
- Possibly modify: `server/skills/builtin/*.py`, `server/tools/*.py`

Test each skill directly via Python. Fix any broken ones immediately.

- [ ] **Step 1: Test email_list**
- [ ] **Step 2: Test email_read**
- [ ] **Step 3: Test email_send**
- [ ] **Step 4: Test email_search**
- [ ] **Step 5: Test calendar_view**
- [ ] **Step 6: Test calendar_create**
- [ ] **Step 7: Test web_search**
- [ ] **Step 8: Test file_write + file_read**
- [ ] **Step 9: Test desktop_screenshot**
- [ ] **Step 10: Test browser_go_to**
- [ ] **Step 11: Test opencode_run**
- [ ] **Step 12: Fix any failures and commit**

Each test: run `python3 -c "..."` calling `skill.execute()` directly, verify return format, fix if error.

---

### Task 8: Backend — Add Media to Tool Results

**Files:**
- Modify: `server/skills/builtin/desktop_skill.py`
- Modify: `server/skills/builtin/email_skill.py`
- Modify: `server/skills/builtin/file_skill.py`
- Modify: `server/skills/builtin/browser_skill.py`

- [ ] **Step 1: desktop_screenshot — save to output/screenshots, add media array**
- [ ] **Step 2: email_read — wrap body as richtext media**
- [ ] **Step 3: file_read — wrap large content as richtext media**
- [ ] **Step 4: browser results — add screenshot/content media if available**
- [ ] **Step 5: Commit**

---

### Task 9: Frontend E2E Testing

- [ ] **Step 1: Start server, set DashScope primary + OpenRouter fallback**
- [ ] **Step 2: Test fallback — send explicit content, verify OpenRouter takes over**
- [ ] **Step 3: Test each tool via Assist mode chat commands (all 12)**
- [ ] **Step 4: Verify media panel — screenshot thumbnail + click lightbox, email read + click rich text panel**
- [ ] **Step 5: Fix any failures and commit**

---

### Task 10: Final Integration Commit

- [ ] **Step 1: Run full import check**

```bash
cd server && source venv/bin/activate
python3 -c "from config import config; print('config OK')"
python3 -c "from llm_client import LLMClient; print('llm OK')"
python3 -c "from agent import AgentOrchestrator; print('agent OK')"
python3 -c "from tts_engine import TTSEngine; print('tts OK')"
```

- [ ] **Step 2: Final commit**

```bash
git add -A
git commit -m "feat: dual-API fallback, media panel, all skills tested"
```
