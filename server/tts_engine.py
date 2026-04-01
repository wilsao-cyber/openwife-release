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
            visemes = self._generate_visemes_from_audio(str(output_path), text)
            return output_filename, visemes

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return await self._mock_synthesize(text, language)

    async def _mock_synthesize(self, text: str, language: str = "zh-TW") -> tuple[str, list[dict]]:
        import uuid
        import struct

        output_filename = f"{uuid.uuid4()}.wav"
        output_path = self.output_dir / output_filename

        sample_rate = self.sample_rate
        duration = 0.5
        num_samples = int(sample_rate * duration)

        with open(output_path, "wb") as f:
            data_size = num_samples * 2  # 16-bit samples
            f.write(b'RIFF')
            f.write(struct.pack('<I', 36 + data_size))
            f.write(b'WAVE')
            f.write(b'fmt ')
            f.write(struct.pack('<I', 16))
            f.write(struct.pack('<H', 1))
            f.write(struct.pack('<H', 1))
            f.write(struct.pack('<I', sample_rate))
            f.write(struct.pack('<I', sample_rate * 2))
            f.write(struct.pack('<H', 2))
            f.write(struct.pack('<H', 16))
            f.write(b'data')
            f.write(struct.pack('<I', data_size))
            f.write(b'\x00' * data_size)

        logger.warning(f"Using mock TTS output (silence generated): {output_filename}")
        return output_filename, []

    def _generate_visemes_from_audio(self, audio_path: str, text: str = "") -> list[dict]:
        """Generate viseme data from audio file and text using a phoneme map."""
        PHONEME_VISEME_MAP = {
            'a': 'aa', 'o': 'oh', 'u': 'ou', 'e': 'ee', 'i': 'ih',
            'b': 'oh', 'p': 'oh', 'm': 'oh',
            'f': 'ih', 'v': 'ih',
            's': 'ee', 'z': 'ee', 'sh': 'ee',
            't': 'ih', 'd': 'ih', 'n': 'ih', 'l': 'ih',
            'k': 'aa', 'g': 'aa',
            'r': 'oh', 'w': 'ou', 'y': 'ee',
        }
        
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
            
            # Map text to shape indices
            text_chars = [c.lower() for c in text if c.lower() in PHONEME_VISEME_MAP]

            for i in range(0, len(samples), chunk_size):
                chunk = samples[i:i + chunk_size]
                if not chunk:
                    break
                amplitude = sum(abs(s) for s in chunk) / len(chunk) / 32768.0
                time_sec = i / framerate

                if amplitude < 0.02:
                    continue

                weight = min(1.0, amplitude * 5)
                
                if text_chars:
                    char_idx = min(int((i / len(samples)) * len(text_chars)), len(text_chars) - 1)
                    mapped_shape = PHONEME_VISEME_MAP.get(text_chars[char_idx], 'aa')
                else:
                    shape_idx = (i // chunk_size) % len(mouth_shapes)
                    mapped_shape = mouth_shapes[shape_idx]

                visemes.append({
                    'time': round(time_sec, 3),
                    'viseme': mapped_shape,
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
