import httpx
import asyncio
import json
import logging
from typing import Optional, AsyncGenerator
from config import LLMConfig

logger = logging.getLogger(__name__)


class LLMClient:
    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 2, 4]

    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.base_url
        self.model = config.model
        self.provider = config.provider
        self.api_key = config.api_key
        self.client = httpx.AsyncClient(timeout=300.0)
        # Fallback provider
        self.fallback_provider = config.fallback_provider
        self.fallback_base_url = config.fallback_base_url
        self.fallback_api_key = config.fallback_api_key
        self.fallback_model = config.fallback_model

    @property
    def _is_ollama(self) -> bool:
        return self.provider == "ollama"

    @property
    def has_fallback(self) -> bool:
        return bool(self.fallback_provider and self.fallback_api_key and self.fallback_base_url)

    def _auth_headers(self) -> dict:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    def _fallback_auth_headers(self) -> dict:
        if self.fallback_api_key:
            return {"Authorization": f"Bearer {self.fallback_api_key}"}
        return {}

    def _is_content_blocked(self, error: httpx.HTTPStatusError) -> bool:
        if error.response.status_code not in (400, 403):
            return False
        try:
            body = error.response.json()
            err = body.get("error", {})
            code = err.get("code", "")
            msg = err.get("message", "").lower()
            etype = err.get("type", "").lower()
            blocked_codes = ("data_inspection_failed", "content_filter", "content_policy_violation")
            blocked_msgs = ("inappropriate content", "content filter", "safety", "moderation")
            return code in blocked_codes or etype in ("data_inspection_failed",) or any(k in msg for k in blocked_msgs)
        except Exception:
            return False

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        think: bool = True,
        use_fallback: bool = False,
    ) -> str | dict | AsyncGenerator[str, None]:
        if use_fallback and self.has_fallback:
            payload = {
                "model": self.fallback_model,
                "messages": messages,
                "temperature": temperature or self.config.temperature,
                "max_tokens": max_tokens or self.config.max_tokens,
                "stream": stream,
            }
            if tools:
                payload["tools"] = tools
            if stream:
                return self._fallback_stream(payload)
            return await self._fallback_complete(payload)
        if self._is_ollama:
            return await self._ollama_chat(
                messages, tools, temperature, max_tokens, stream, think
            )
        return await self._openai_chat(messages, tools, temperature, max_tokens, stream)

    # ── Ollama ─────────────────────────────────────────────────────────

    async def _ollama_chat(
        self, messages, tools, temperature, max_tokens, stream, think
    ):
        predict = max_tokens or 1024
        if not think:
            predict += 1024
        options = {
            "think": think,
            "num_ctx": 4096,
            "num_predict": predict,
        }
        if temperature:
            options["temperature"] = temperature
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": options,
        }
        if tools:
            payload["tools"] = tools
        if stream:
            return self._ollama_stream(payload)
        return await self._ollama_complete(payload)

    async def _ollama_complete(self, payload: dict) -> str | dict:
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self.client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                message = data.get("message", {})
                content = message.get("content", "")
                if message.get("tool_calls"):
                    return {"content": content, "tool_calls": message["tool_calls"]}
                return content
            except (
                httpx.HTTPStatusError,
                httpx.TimeoutException,
                httpx.ConnectError,
            ) as e:
                last_error = e
                logger.warning(f"Ollama request failed (attempt {attempt + 1}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAYS[attempt])
        raise last_error or Exception("LLM request failed after all retries")

    async def _ollama_stream(self, payload: dict) -> AsyncGenerator[str, None]:
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                yielded = 0
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    msg = chunk.get("message", {})
                    content = msg.get("content", "")
                    # Ollama Qwen3.5: thinking phase has content="" + thinking="..."
                    # Content phase has content="..." + thinking=""
                    if content:
                        yielded += len(content)
                        yield content
                if yielded == 0:
                    logger.warning(f"Ollama stream produced 0 content chars (model may be thinking-only)")
        except Exception as e:
            logger.error(f"Ollama stream failed: {e}")
            raise

    # ── OpenAI-compatible ──────────────────────────────────────────────

    async def _openai_chat(self, messages, tools, temperature, max_tokens, stream):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
        if self.provider == "dashscope" and not stream:
            payload["enable_thinking"] = False
        if stream:
            return self._openai_stream(payload)
        return await self._openai_complete(payload)

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

    async def _openai_stream(self, payload: dict) -> AsyncGenerator[str, None]:
        headers = self._auth_headers()
        url = f"{self.base_url}/v1/chat/completions"
        logger.info(f"OpenAI stream: {url}, model={payload.get('model')}, auth={'Bearer ***' + self.api_key[-4:] if self.api_key else 'none'}")
        try:
            async with self.client.stream(
                "POST", url, json=payload, headers=headers,
            ) as response:
                # Content blocked → fallback
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
                            # Check both formats: top-level code and nested error
                            block_code = (
                                chunk.get("code", "")
                                or chunk.get("error", {}).get("code", "")
                                or chunk.get("error", {}).get("type", "")
                            )
                            block_msg = chunk.get("message", "") or chunk.get("error", {}).get("message", "")
                            is_blocked = block_code in ("data_inspection_failed", "content_filter", "content_policy_violation") or "inappropriate content" in block_msg.lower()
                            if is_blocked and self.has_fallback:
                                logger.warning(f"Output blocked mid-stream by {self.provider}, falling back to {self.fallback_provider}")
                                async for fb_chunk in self._fallback_stream(payload):
                                    yield fb_chunk
                                return
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

    # ── Model/Provider Management ──────────────────────────────────────

    async def switch_model(self, new_model: str):
        old_model = self.model
        if old_model and self._is_ollama:
            try:
                await self.client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": old_model, "keep_alive": 0},
                )
                logger.info(f"Unloaded model: {old_model}")
            except Exception as e:
                logger.warning(f"Failed to unload {old_model}: {e}")
        self.model = new_model
        if self._is_ollama:
            try:
                await self.client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": new_model, "prompt": "OK", "stream": False},
                )
                logger.info(f"Loaded model: {new_model}")
            except Exception as e:
                logger.error(f"Failed to load {new_model}: {e}")
                raise

    def update_provider(self, provider: str, base_url: str, api_key: str, model: str):
        from config import resolve_model
        self.provider = provider
        self.base_url = base_url
        self.api_key = api_key
        self.model = resolve_model(model) if provider == "ollama" else model
        logger.info(f"Provider switched: {provider} @ {base_url}, model={self.model}")

    def update_fallback(self, provider: str, base_url: str, api_key: str, model: str):
        self.fallback_provider = provider
        self.fallback_base_url = base_url
        self.fallback_api_key = api_key
        self.fallback_model = model
        logger.info(f"Fallback updated: {provider} @ {base_url}, model={model}")

    async def close(self):
        await self.client.aclose()
