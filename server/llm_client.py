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

    @property
    def _is_ollama(self) -> bool:
        return self.provider == "ollama"

    def _auth_headers(self) -> dict:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        think: bool = True,
    ) -> str | dict | AsyncGenerator[str, None]:
        if self._is_ollama:
            return await self._ollama_chat(
                messages, tools, temperature, max_tokens, stream, think
            )
        return await self._openai_chat(messages, tools, temperature, max_tokens, stream)

    async def _ollama_chat(
        self, messages, tools, temperature, max_tokens, stream, think
    ):
        # num_predict includes thinking tokens, so add buffer
        # Qwen3.5 still thinks even with think=False (~500-1000 tokens)
        predict = max_tokens or 1024
        if not think:
            predict += 1024  # thinking overhead buffer
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
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
        except Exception as e:
            logger.error(f"Ollama stream failed: {e}")
            raise

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
        # DashScope Qwen3+ requires enable_thinking for non-streaming
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
                if e.response.status_code < 500:
                    raise
                last_error = e
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(self.RETRY_DELAYS[attempt])
        raise last_error or Exception("LLM request failed after all retries")

    async def _openai_stream(self, payload: dict) -> AsyncGenerator[str, None]:
        headers = self._auth_headers()
        url = f"{self.base_url}/v1/chat/completions"
        logger.info(f"OpenAI stream: {url}, model={payload.get('model')}, auth={'Bearer ***' + self.api_key[-4:] if self.api_key else 'none'}")
        try:
            async with self.client.stream(
                "POST", url, json=payload, headers=headers,
            ) as response:
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
                            # DashScope content moderation or empty response
                            logger.warning(f"Stream chunk missing 'choices': {data[:200]}")
                            continue
                        delta = choices[0].get("delta", {})
                        content = delta.get("content") or ""
                        if content:
                            yield content
        except Exception as e:
            logger.error(f"OpenAI stream failed: {e}")
            yield f"[Error: {str(e)[:100]}]"

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
        self.provider = provider
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        logger.info(
            f"Provider switched: {provider} @ {base_url}, model={model}"
        )

    async def close(self):
        await self.client.aclose()
