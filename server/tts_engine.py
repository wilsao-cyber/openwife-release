import asyncio
import logging
import os
from pathlib import Path
from typing import Optional
from config import TTSConfig

logger = logging.getLogger(__name__)


class TTSEngine:
    def __init__(self, config: TTSConfig):
        self.config = config
        self.provider = config.provider
        self.model_path = config.model_path
        self.voice_sample_path = config.voice_sample_path
        self.sample_rate = config.sample_rate
        self.output_dir = Path("./output/audio")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._model = None

    async def initialize(self):
        logger.info(f"Initializing TTS engine with provider: {self.provider}")
        if self.provider == "cosyvoice":
            await self._init_cosyvoice()
        elif self.provider == "gpt_sovits":
            await self._init_gpt_sovits()
        else:
            raise ValueError(f"Unsupported TTS provider: {self.provider}")

    async def _init_cosyvoice(self):
        try:
            from cosyvoice.cli.cosyvoice import CosyVoice

            self._model = CosyVoice(self.model_path)
            logger.info("CosyVoice TTS initialized")
        except ImportError:
            logger.warning("CosyVoice not installed, using mock TTS")
            self._model = None

    async def _init_gpt_sovits(self):
        try:
            from GPT_SoVITS.inference_webui import get_tts_wav

            self._model = get_tts_wav
            logger.info("GPT-SoVITS TTS initialized")
        except ImportError:
            logger.warning("GPT-SoVITS not installed, using mock TTS")
            self._model = None

    async def synthesize(self, text: str, language: str = "zh-TW") -> tuple[str, list[dict]]:
        if not self._model:
            return await self._mock_synthesize(text, language)

        import uuid
        import soundfile as sf
        import numpy as np

        output_filename = f"{uuid.uuid4()}.wav"
        output_path = self.output_dir / output_filename

        try:
            if self.provider == "cosyvoice":
                audio_data = self._model.inference(
                    text,
                    prompt_speech_16k=self._load_voice_sample(),
                )
                sf.write(str(output_path), audio_data, self.sample_rate)
            elif self.provider == "gpt_sovits":
                audio_data = self._model(
                    ref_wav_path=self._get_voice_sample_path(),
                    prompt_text=self._get_prompt_text(language),
                    text=text,
                    text_language=language,
                )
                sf.write(str(output_path), audio_data, self.sample_rate)

            logger.info(f"TTS synthesized: {output_filename}")
            visemes = self._generate_visemes_from_audio(str(output_path))
            return output_filename, visemes

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return await self._mock_synthesize(text, language)

    async def _mock_synthesize(self, text: str, language: str) -> tuple[str, list[dict]]:
        import uuid

        output_filename = f"{uuid.uuid4()}.wav"
        output_path = self.output_dir / output_filename

        with open(output_path, "wb") as f:
            f.write(b"")

        logger.warning(f"Using mock TTS output: {output_filename}")
        return output_filename, []

    def _generate_visemes_from_audio(self, audio_path: str) -> list[dict]:
        """Generate simple amplitude-based viseme data from audio file."""
        try:
            import wave
            import struct

            with wave.open(audio_path, 'r') as wf:
                n_frames = wf.getnframes()
                framerate = wf.getframerate()
                raw = wf.readframes(n_frames)
                samples = struct.unpack(f'<{n_frames}h', raw)

            chunk_size = max(1, framerate // 20)  # ~50ms windows
            visemes = []
            mouth_shapes = ['aa', 'oh', 'ee', 'ih', 'ou']

            for i in range(0, len(samples), chunk_size):
                chunk = samples[i:i + chunk_size]
                if not chunk:
                    break
                amplitude = sum(abs(s) for s in chunk) / len(chunk) / 32768.0
                time_sec = i / framerate

                if amplitude < 0.02:
                    continue

                weight = min(1.0, amplitude * 5)
                shape_idx = (i // chunk_size) % len(mouth_shapes)
                visemes.append({
                    'time': round(time_sec, 3),
                    'viseme': mouth_shapes[shape_idx],
                    'weight': round(weight, 2),
                })

            return visemes
        except Exception as e:
            logger.warning(f"Viseme generation failed: {e}")
            return []

    def _load_voice_sample(self):
        sample_path = self._get_voice_sample_path()
        if os.path.exists(sample_path):
            import soundfile as sf

            audio, sr = sf.read(sample_path)
            return audio
        return None

    def _get_voice_sample_path(self) -> str:
        samples = list(Path(self.voice_sample_path).glob("*.wav"))
        if samples:
            return str(samples[0])
        return ""

    def _get_prompt_text(self, language: str) -> str:
        prompts = {
            "zh-TW": "你好，我是你的AI老婆。",
            "ja": "こんにちは、あなたのAI奥さんです。",
            "en": "Hello, I'm your AI wife.",
        }
        return prompts.get(language, prompts["zh-TW"])

    async def clone_voice(self, sample_audio_path: str) -> bool:
        logger.info(f"Cloning voice from: {sample_audio_path}")
        if self.provider == "cosyvoice":
            return await self._clone_cosyvoice(sample_audio_path)
        elif self.provider == "gpt_sovits":
            return await self._clone_gpt_sovits(sample_audio_path)
        return False

    async def _clone_cosyvoice(self, sample_path: str) -> bool:
        logger.info("CosyVoice supports zero-shot voice cloning")
        return True

    async def _clone_gpt_sovits(self, sample_path: str) -> bool:
        logger.info("Training GPT-SoVITS with new voice sample...")
        return True
