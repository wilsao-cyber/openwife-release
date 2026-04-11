import logging
import hashlib
import base64
import httpx
from typing import Optional
from config import config

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    def __init__(
        self,
        vision_model=None,
        llm_client=None,
        change_threshold: Optional[float] = None,
    ):
        self._llm_client = llm_client
        self.model = vision_model or config.vision.model
        self.change_threshold = (
            change_threshold
            if change_threshold is not None
            else config.vision.change_threshold
        )
        self.base_url = config.llm.base_url
        self._last_hash: Optional[str] = None

    def _image_hash(self, image_data: bytes) -> str:
        return hashlib.md5(image_data).hexdigest()

    def has_significant_change(self, current: bytes, previous: Optional[bytes]) -> bool:
        if previous is None:
            return True
        return self._image_hash(current) != self._image_hash(previous)

    async def analyze_single(
        self, image_data: bytes, language: str = "zh-TW", context: str = ""
    ) -> dict:
        prompts = {
            "zh-TW": "請用繁體中文描述你在這張圖片中看到了什麼",
            "ja": "この画像に何が映っているか日本語で説明してください",
            "en": "Describe what you see in this image",
        }
        prompt = prompts.get(language, prompts["en"])
        if context:
            prompt += f" Context: {context}"

        b64_image = base64.b64encode(image_data).decode("utf-8")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "images": [b64_image],
                        "stream": False,
                    },
                )
            response.raise_for_status()
            data = response.json()
            return {
                "text": data.get("response", ""),
                "emotion": "neutral",
            }
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return {
                "text": f"Error analyzing image: {str(e)}",
                "emotion": "sad",
            }

    async def analyze_stream(
        self,
        current_frame: bytes,
        previous_frame: Optional[bytes],
        language: str = "zh-TW",
        context: str = "",
    ) -> Optional[dict]:
        if not self.has_significant_change(current_frame, previous_frame):
            return None
        return await self.analyze_single(current_frame, language, context)
