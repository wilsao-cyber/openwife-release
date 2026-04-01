import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional
from config import STTConfig

logger = logging.getLogger(__name__)


class STTEngine:
    def __init__(self, config: STTConfig):
        self.config = config
        self.provider = config.provider
        self.model_name = config.model
        self.default_language = config.language
        self._model = None

    async def initialize(self):
        logger.info(f"Initializing STT engine with provider: {self.provider}")
        if self.provider == "whisper":
            await self._init_whisper()
        else:
            raise ValueError(f"Unsupported STT provider: {self.provider}")

    async def _init_whisper(self):
        try:
            import whisper

            self._model = whisper.load_model(self.model_name)
            logger.info(f"Whisper STT loaded model: {self.model_name}")
        except ImportError:
            logger.warning("Whisper not installed, using mock STT")
            self._model = None

    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
    ) -> str:
        if not self._model:
            return await self._mock_transcribe(audio_data)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            lang = language if language != "auto" else None
            result = self._model.transcribe(
                tmp_path,
                language=lang,
                fp16=False,
            )
            logger.info(f"STT transcribed: {result['text'][:50]}...")
            return result["text"]
        except Exception as e:
            logger.error(f"STT transcription failed: {e}")
            return ""
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _mock_transcribe(self, audio_data: bytes) -> str:
        logger.warning("Using mock STT output - Speech recognition service not available")
        return "[Speech recognition service not available - Whisper not installed]"

    async def transcribe_file(
        self, file_path: str, language: Optional[str] = None
    ) -> str:
        with open(file_path, "rb") as f:
            audio_data = f.read()
        return await self.transcribe(audio_data, language)
