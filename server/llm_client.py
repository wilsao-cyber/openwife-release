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
        self.client = httpx.AsyncClient(timeout=120.0)

    async def chat(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> str | AsyncGenerator[str, None]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": stream,
        }

        if stream:
            return self._stream_response(payload)
        else:
            return await self._complete_response(payload)

    async def _complete_response(self, payload: dict) -> str:
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self.client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500:
                    raise
                last_error = e
                logger.warning(f"LLM request failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                logger.warning(f"LLM request failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(self.RETRY_DELAYS[attempt])
        logger.error(f"LLM request failed after {self.MAX_RETRIES} attempts: {last_error}")
        raise last_error

    async def _stream_response(self, payload: dict) -> AsyncGenerator[str, None]:
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        chunk = json.loads(data)
                        content = chunk["choices"][0]["delta"].get("content", "")
                        if content:
                            yield content
        except Exception as e:
            logger.error(f"LLM stream request failed: {e}")
            raise

    async def generate_3d_model_prompt(self, image_description: str) -> str:
        prompt = f"""
        Based on this character description, generate a detailed 3D model specification:
        {image_description}
        
        Please provide:
        1. Body proportions and measurements
        2. Hair style, color, and details
        3. Eye shape, color, and expression
        4. Clothing/outfit details
        5. Accessories and props
        6. Pose and expression
        7. Color palette
        """
        return await self.chat([{"role": "user", "content": prompt}])

    async def translate(self, text: str, target_lang: str) -> str:
        lang_map = {
            "zh-TW": "Traditional Chinese",
            "ja": "Japanese",
            "en": "English",
        }
        target = lang_map.get(target_lang, target_lang)
        prompt = f"Translate the following text to {target}:\n{text}"
        return await self.chat([{"role": "user", "content": prompt}])

    async def close(self):
        await self.client.aclose()
