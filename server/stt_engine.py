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
        self._last_emotion = None  # SenseVoice emotion detection

    @property
    def last_emotion(self) -> Optional[str]:
        """Return emotion detected from last transcription (SenseVoice only)."""
        return self._last_emotion

    async def initialize(self):
        logger.info(f"Initializing STT engine with provider: {self.provider}")
        if self.provider == "sensevoice":
            await self._init_sensevoice()
        elif self.provider == "whisper":
            await self._init_whisper()
        else:
            raise ValueError(f"Unsupported STT provider: {self.provider}")

    async def _init_sensevoice(self):
        try:
            from funasr import AutoModel

            self._model = AutoModel(
                model="iic/SenseVoiceSmall",
                trust_remote_code=True,
                device="cuda",
            )
            logger.info("SenseVoice STT loaded (iic/SenseVoiceSmall, CUDA)")
        except Exception as e:
            logger.warning(f"SenseVoice init failed ({e}), trying CPU...")
            try:
                from funasr import AutoModel

                self._model = AutoModel(
                    model="iic/SenseVoiceSmall",
                    trust_remote_code=True,
                    device="cpu",
                )
                logger.info("SenseVoice STT loaded (CPU fallback)")
            except Exception as e2:
                logger.error(f"SenseVoice init failed completely: {e2}")
                self._model = None

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
        self._last_emotion = None

        if not self._model:
            return await self._mock_transcribe(audio_data)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            if self.provider == "sensevoice":
                return await self._transcribe_sensevoice(tmp_path, language)
            else:
                return await self._transcribe_whisper(tmp_path, language)
        except Exception as e:
            logger.error(f"STT transcription failed: {e}")
            return ""
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _transcribe_sensevoice(self, audio_path: str, language: Optional[str] = None) -> str:
        import re

        lang = language or "zh"
        # SenseVoice language codes: zh, en, ja, ko, yue
        lang_map = {"zh-TW": "zh", "zh": "zh", "ja": "ja", "en": "en"}
        sv_lang = lang_map.get(lang, "zh")

        result = self._model.generate(
            input=audio_path,
            cache={},
            language=sv_lang,
            use_itn=True,
        )

        if not result or not result[0]:
            return ""

        raw_text = result[0].get("text", "") if isinstance(result[0], dict) else str(result[0])

        # SenseVoice returns text with emotion/event tags like <|HAPPY|>, <|SAD|>, etc.
        emotion_match = re.search(r'<\|(HAPPY|SAD|ANGRY|NEUTRAL|FEARFUL|DISGUSTED|SURPRISED)\|>', raw_text, re.IGNORECASE)
        if emotion_match:
            emotion_map = {
                "HAPPY": "happy", "SAD": "sad", "ANGRY": "angry",
                "NEUTRAL": "neutral", "FEARFUL": "sad",
                "DISGUSTED": "angry", "SURPRISED": "surprised",
            }
            self._last_emotion = emotion_map.get(emotion_match.group(1).upper(), "neutral")

        # Clean tags from text
        clean = re.sub(r'<\|[^|]+\|>', '', raw_text).strip()
        logger.info(f"SenseVoice transcribed: {clean[:50]}... (emotion: {self._last_emotion})")
        return clean

    async def _transcribe_whisper(self, audio_path: str, language: Optional[str] = None) -> str:
        lang = language if language != "auto" else None
        result = self._model.transcribe(
            audio_path,
            language=lang,
            fp16=False,
        )
        logger.info(f"Whisper transcribed: {result['text'][:50]}...")
        return result["text"]

    async def _mock_transcribe(self, audio_data: bytes) -> str:
        logger.warning("Using mock STT output - STT engine not available")
        return "[Speech recognition service not available]"

    async def transcribe_file(
        self, file_path: str, language: Optional[str] = None
    ) -> str:
        with open(file_path, "rb") as f:
            audio_data = f.read()
        return await self.transcribe(audio_data, language)
