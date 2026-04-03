import asyncio
import logging
import os
from pathlib import Path
from typing import Optional
from config import TTSConfig

logger = logging.getLogger(__name__)


class TTSEngine:
    def __init__(self, config: TTSConfig, llm_client=None):
        self.config = config
        self.provider = config.provider
        self.model_path = config.model_path
        self.voice_sample_path = config.voice_sample_path
        self.sample_rate = config.sample_rate
        self.output_dir = Path("./output/audio")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._model = None
        self._llm_client = llm_client

    async def initialize(self):
        logger.info(f"Initializing TTS engine with provider: {self.provider}")
        if self.provider == "cosyvoice":
            await self._init_cosyvoice()
        elif self.provider == "gpt_sovits":
            await self._init_gpt_sovits()
        elif self.provider == "voicebox":
            await self._init_voicebox()
        else:
            raise ValueError(f"Unsupported TTS provider: {self.provider}")

    async def _init_voicebox(self):
        """Test Voicebox API connection."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.config.voicebox_api_url}/profiles")
                if resp.status_code == 200:
                    profiles = resp.json()
                    logger.info(
                        f"Voicebox connected: {len(profiles)} profiles available"
                    )
                    if self.config.voicebox_profile_id:
                        logger.info(
                            f"Using voice profile: {self.config.voicebox_profile_id}"
                        )
                    else:
                        logger.warning(
                            "No voicebox_profile_id set, using default voice"
                        )
                else:
                    logger.warning(f"Voicebox returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"Voicebox not available: {e}")
            self._model = None

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

    EMOTION_INSTRUCT_MAP = {
        "happy": "甘えた可愛い女の子の声で、愛情と温もりを込めて、少し艶っぽく、ゆっくり話してください。嬉しそうに、明るく弾んだ声で",
        "sad": "甘えた可愛い女の子の声で、愛情と温もりを込めて、ゆっくり話してください。少し寂しそうに、甘えるような声で",
        "angry": "甘えた可愛い女の子の声で、愛情と温もりを込めて、ゆっくり話してください。少し拗ねた、可愛く怒った声で",
        "surprised": "甘えた可愛い女の子の声で、愛情と温もりを込めて、少し艶っぽく、ゆっくり話してください。驚いた、でも嬉しそうな声で",
        "relaxed": "甘えた可愛い女の子の声で、愛情と温もりを込めて、少し艶っぽく、ゆっくり話してください。穏やかで、囁くような甘い声で",
        "neutral": "甘えた可愛い女の子の声で、愛情と温もりを込めて、少し艶っぽく、ゆっくり話してください",
        "horny": "喘ぎ声で、エッチな感じで、吐息を漏らしながら、感じている声で、恥ずかしそうに甘く囁いてください",
    }

    async def synthesize(
        self, text: str, language: str = "zh-TW", emotion: str = "neutral"
    ) -> tuple[str, list[dict], str]:
        """Returns (audio_filename, visemes, ja_text)."""
        if self.provider == "voicebox":
            return await self._synthesize_voicebox(text, language, emotion)
        if not self._model:
            result = await self._mock_synthesize(text, language)
            return result[0], result[1], ""

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
            return output_filename, visemes, ""

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            result = await self._mock_synthesize(text, language)
            return result[0], result[1], ""

    _TRANSLATE_BASE = (
        "あなたは中国語→日本語の翻訳者です。\n"
        "【絶対ルール】出力は100%日本語のみ。中国語を一文字でも残してはいけません。\n"
        "【キャラ設定】アニメ風の可愛い妻キャラ「アイ」のセリフです。\n"
        "【翻訳ルール】\n"
        "- 「小愛」「我」「人家」→「あたし」（自称は必ず「あたし」）\n"
        "- 「老公」「親愛的」→「あなた」「ダーリン」\n"
        "- 括弧内の動作描写（*臉紅*、（低下頭）等）→ 全て削除\n"
        "- 絵文字 → 全て削除\n"
        "- 「小愛」という名前が出る場合→「アイ」に置換\n"
        "- 可愛く甘えた口調を保つ（よ、ね、の、かな、なの）\n"
        "翻訳のみ出力。説明不要。"
    )

    _TRANSLATE_HORNY = (
        "あなたは中国語→日本語の翻訳者です。\n"
        "【絶対ルール】出力は100%日本語のみ。中国語を一文字でも残してはいけません。\n"
        "【キャラ設定】アニメ風の可愛い妻キャラ「アイ」の、親密シーンのセリフです。\n"
        "【翻訳ルール】\n"
        "- 「小愛」「我」「人家」→「あたし」（自称は必ず「あたし」）\n"
        "- 「老公」「親愛的」→「あなた」「ダーリン」\n"
        "- 括弧内の動作描写 → 全て削除\n"
        "- 絵文字 → 全て削除\n"
        "- 「小愛」→「アイ」\n"
        "【重要：擬声語・喘ぎ声を追加すること】\n"
        "- セリフの間に自然な擬声語を挿入する：\n"
        "  んっ…、はぁ…、あっ…、ちゅぷ…、じゅる…、んむ…、くちゅ…、れろ…\n"
        "- 吐息混じりの甘い声を表現する\n"
        "- 恥ずかしそうだけど感じている雰囲気を出す\n"
        "- 長い吸い付き音（ちゅぱ…じゅるる…）を適度に入れる\n"
        "翻訳のみ出力。説明不要。"
    )

    async def _translate_to_ja(self, text: str, language: str, emotion: str = "neutral") -> str:
        """Translate text to Japanese for voice synthesis using the active LLM client."""
        if language == "ja":
            return text
        try:
            if not self._llm_client:
                logger.warning("No LLM client for translation, using original text")
                return text

            prompt = self._TRANSLATE_HORNY if emotion == "horny" else self._TRANSLATE_BASE

            result = await self._llm_client.chat(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                max_tokens=500,
                temperature=0.3,
                think=False,
            )
            ja_text = result.strip() if isinstance(result, str) else str(result).strip()
            return ja_text
        except Exception as e:
            logger.warning(f"Translation to Japanese failed: {e}, using original text")
            return text

    @staticmethod
    def _strip_emoji(text: str) -> str:
        """Remove emoji and special symbols from text."""
        import re
        return re.sub(
            r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
            r'\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0000FE00-\U0000FE0F'
            r'\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
            r'\U00002600-\U000026FF\U0000200D\U00002640\U00002642]+', '', text
        ).strip()

    def _concat_wav(self, parts: list[Path], output_path: Path):
        """Concatenate multiple WAV files, trimming trailing silence."""
        import wave
        import struct

        def trim_silence(frames_bytes: bytes, sample_width: int, threshold: int = 300) -> bytes:
            """Trim trailing silence from raw PCM frames."""
            if sample_width != 2:
                return frames_bytes
            samples = struct.unpack(f"<{len(frames_bytes)//2}h", frames_bytes)
            end = len(samples)
            # Walk backwards to find last audible sample
            while end > 0 and abs(samples[end - 1]) < threshold:
                end -= 1
            # Keep a tiny tail (~50ms at 22050Hz ≈ 1100 samples)
            end = min(len(samples), end + 1100)
            return struct.pack(f"<{end}h", *samples[:end])

        with wave.open(str(output_path), "wb") as out:
            params_set = False
            for p in parts:
                with wave.open(str(p), "rb") as inp:
                    if not params_set:
                        out.setparams(inp.getparams())
                        params_set = True
                    raw = inp.readframes(inp.getnframes())
                    trimmed = trim_silence(raw, inp.getsampwidth())
                    out.writeframes(trimmed)

    async def _prepare_tts(
        self, text: str, language: str, emotion: str
    ) -> tuple[str, list[str], str, str]:
        """Shared preprocessing: translate, split sentences, build instruct.
        Returns (ja_text, sentences, instruct, profile_id)."""
        import re as _re

        # Strip emoji before translation
        clean_text = self._strip_emoji(text)
        if not clean_text:
            return "", [], "", ""

        # Translate to Japanese for voice synthesis
        ja_text = await self._translate_to_ja(clean_text, language, emotion)
        # Clean special characters that cause TTS glitch
        ja_text = ja_text.replace("～", "ー")
        ja_text = ja_text.replace("…", "、").replace("...", "、")
        ja_text = ja_text.replace("♡", "").replace("♪", "").replace("☆", "").replace("★", "")
        ja_text = ja_text.replace("→", "").replace("←", "").replace("↑", "").replace("↓", "")
        ja_text = ja_text.replace("《", "").replace("》", "").replace("【", "").replace("】", "")
        ja_text = ja_text.replace("「", "").replace("」", "").replace("『", "").replace("』", "")
        ja_text = ja_text.replace("（", "").replace("）", "").replace("(", "").replace(")", "")
        ja_text = _re.sub(r'[*#_`~|<>{}\\\/\[\]]', '', ja_text)  # markdown/code symbols
        ja_text = _re.sub(r'\s+', ' ', ja_text).strip()
        logger.info(f"TTS text (ja): {ja_text[:80]}...")

        # Split on sentence-ending punctuation and clause boundaries
        # Primary split: 。！？ (sentence end)
        # Secondary split: 、 ー after 8+ chars (clause boundary for emotional pacing)
        raw = _re.split(r'(?<=[。！？])\s*', ja_text)
        # Further split long segments on clause boundaries
        fine = []
        for seg in raw:
            seg = seg.strip()
            if not seg or len(seg) <= 1:
                continue
            if len(seg) > 25:
                # Split on 、 but keep the delimiter with the left part
                parts = _re.split(r'(?<=、)', seg)
                merged_part = ""
                for p in parts:
                    if merged_part and len(merged_part) >= 8:
                        fine.append(merged_part)
                        merged_part = p
                    else:
                        merged_part += p
                if merged_part:
                    fine.append(merged_part)
            else:
                fine.append(seg)
        # Merge very short fragments (< 6 chars) into previous
        sentences = []
        for s in fine:
            s = s.strip()
            if not s:
                continue
            if len(s) < 6 and sentences:
                sentences[-1] += s
            else:
                sentences.append(s)
        if not sentences:
            sentences = [ja_text]

        instruct = self.EMOTION_INSTRUCT_MAP.get(emotion, self.EMOTION_INSTRUCT_MAP["neutral"])

        # Select profile based on emotion
        if emotion == "horny" and self.config.voicebox_horny_profile_id:
            profile_id = self.config.voicebox_horny_profile_id
        else:
            profile_id = self.config.voicebox_profile_id or ""

        return ja_text, sentences, instruct, profile_id

    async def _voicebox_generate_one(
        self, client, sentence: str, profile_id: str, instruct: str,
        emotion: str = "neutral"
    ) -> Optional[Path]:
        """Generate a single sentence via Voicebox HTTP. Returns audio Path or None."""
        import uuid

        payload = {
            "text": sentence,
            "profile_id": profile_id,
            "language": "ja",
        }
        if instruct:
            payload["instruct"] = instruct
        model_size = getattr(self.config, "voicebox_model_size", None)
        if model_size:
            payload["model_size"] = model_size

        logger.info(f"Voicebox generating: {sentence[:40]}...")
        try:
            resp = await client.post(
                f"{self.config.voicebox_api_url}/generate",
                json=payload,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Voicebox segment failed: {e}")
            return None

        data = resp.json()
        if "audio_path" not in data:
            return None

        source = Path(data["audio_path"])
        if not source.is_absolute():
            source = Path("/home/wilsao6666/voicebox") / source
        if not source.exists():
            return None

        # Copy to output dir with unique name
        import shutil
        out_name = f"{uuid.uuid4()}.wav"
        out_path = self.output_dir / out_name
        shutil.copy2(str(source), str(out_path))

        # Apply audio post-processing based on emotion
        if getattr(self.config, "audio_fx_enabled", True):
            try:
                from audio_fx import process_wav
                process_wav(out_path, emotion)
            except Exception as e:
                logger.warning(f"Audio FX failed: {e}")

        return out_path

    async def synthesize_stream(
        self, text: str, language: str = "zh-TW", emotion: str = "neutral"
    ):
        """Async generator yielding SSE event dicts for streaming TTS.
        Uses parallel generation with ordered yield for minimal latency."""
        import httpx

        ja_text, sentences, instruct, profile_id = await self._prepare_tts(
            text, language, emotion
        )
        if not sentences:
            return

        yield {"type": "ja_text", "data": ja_text}

        concurrency = getattr(self.config, "voicebox_concurrency", 2)
        semaphore = asyncio.Semaphore(concurrency)
        results = [None] * len(sentences)
        events = [asyncio.Event() for _ in sentences]

        async def gen_one(idx, sent):
            try:
                async with semaphore:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        results[idx] = await self._voicebox_generate_one(
                            client, sent, profile_id, instruct, emotion=emotion
                        )
            except Exception as e:
                logger.error(f"Sentence {idx} generation failed: {e}")
                results[idx] = None
            finally:
                events[idx].set()

        # Launch all sentence generations concurrently (semaphore limits parallelism)
        tasks = [asyncio.create_task(gen_one(i, s)) for i, s in enumerate(sentences)]

        # Yield results in order — waits for each sentence's event before yielding
        for i in range(len(sentences)):
            await events[i].wait()
            if results[i]:
                yield {
                    "type": "audio",
                    "index": i,
                    "url": f"/audio/{results[i].name}",
                    "total": len(sentences),
                }

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _synthesize_voicebox(
        self, text: str, language: str = "zh-TW", emotion: str = "neutral"
    ) -> tuple[str, list[dict], str]:
        """Synthesize speech using Voicebox API (non-streaming path).
        Returns (audio_filename, visemes, ja_text)."""
        import uuid
        import httpx

        ja_text, sentences, instruct, profile_id = await self._prepare_tts(
            text, language, emotion
        )
        if not sentences:
            result = await self._mock_synthesize(text, language)
            return result[0], result[1], ""

        output_filename = f"{uuid.uuid4()}.wav"
        output_path = self.output_dir / output_filename

        try:
            concurrency = getattr(self.config, "voicebox_concurrency", 2)
            semaphore = asyncio.Semaphore(concurrency)
            results = [None] * len(sentences)
            events = [asyncio.Event() for _ in sentences]

            async def gen_one(idx, sent):
                try:
                    async with semaphore:
                        async with httpx.AsyncClient(timeout=120.0) as client:
                            results[idx] = await self._voicebox_generate_one(
                                client, sent, profile_id, instruct, emotion=emotion
                            )
                except Exception as e:
                    logger.error(f"Sentence {idx} generation failed: {e}")
                finally:
                    events[idx].set()

            tasks = [asyncio.create_task(gen_one(i, s)) for i, s in enumerate(sentences)]
            await asyncio.gather(*tasks, return_exceptions=True)

            audio_parts = [r for r in results if r is not None]

            if not audio_parts:
                raise RuntimeError("No audio generated")

            if len(audio_parts) == 1:
                import shutil
                shutil.copy2(str(audio_parts[0]), str(output_path))
            else:
                self._concat_wav(audio_parts, output_path)

            logger.info(f"Voicebox TTS synthesized: {output_filename} ({len(sentences)} parts)")
            visemes = self._generate_visemes_from_audio(str(output_path), ja_text)
            return output_filename, visemes, ja_text

        except Exception as e:
            logger.error(f"Voicebox synthesis failed: {e}")
            result = await self._mock_synthesize(text, language)
            return result[0], result[1], ja_text

    async def _mock_synthesize(
        self, text: str, language: str = "zh-TW"
    ) -> tuple[str, list[dict]]:
        import uuid
        import struct

        output_filename = f"{uuid.uuid4()}.wav"
        output_path = self.output_dir / output_filename

        sample_rate = self.sample_rate
        duration = 0.5
        num_samples = int(sample_rate * duration)

        with open(output_path, "wb") as f:
            data_size = num_samples * 2  # 16-bit samples
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36 + data_size))
            f.write(b"WAVE")
            f.write(b"fmt ")
            f.write(struct.pack("<I", 16))
            f.write(struct.pack("<H", 1))
            f.write(struct.pack("<H", 1))
            f.write(struct.pack("<I", sample_rate))
            f.write(struct.pack("<I", sample_rate * 2))
            f.write(struct.pack("<H", 2))
            f.write(struct.pack("<H", 16))
            f.write(b"data")
            f.write(struct.pack("<I", data_size))
            f.write(b"\x00" * data_size)

        logger.warning(f"Using mock TTS output (silence generated): {output_filename}")
        return output_filename, []

    def _generate_visemes_from_audio(
        self, audio_path: str, text: str = ""
    ) -> list[dict]:
        """Generate viseme data from audio file and text using a phoneme map."""
        PHONEME_VISEME_MAP = {
            "a": "aa",
            "o": "oh",
            "u": "ou",
            "e": "ee",
            "i": "ih",
            "b": "oh",
            "p": "oh",
            "m": "oh",
            "f": "ih",
            "v": "ih",
            "s": "ee",
            "z": "ee",
            "sh": "ee",
            "t": "ih",
            "d": "ih",
            "n": "ih",
            "l": "ih",
            "k": "aa",
            "g": "aa",
            "r": "oh",
            "w": "ou",
            "y": "ee",
        }

        try:
            import wave
            import struct

            with wave.open(audio_path, "r") as wf:
                n_frames = wf.getnframes()
                framerate = wf.getframerate()
                raw = wf.readframes(n_frames)
                samples = struct.unpack(f"<{n_frames}h", raw)

            chunk_size = max(1, framerate // 20)  # ~50ms windows
            visemes = []
            mouth_shapes = ["aa", "oh", "ee", "ih", "ou"]

            # Map text to shape indices
            text_chars = [c.lower() for c in text if c.lower() in PHONEME_VISEME_MAP]

            for i in range(0, len(samples), chunk_size):
                chunk = samples[i : i + chunk_size]
                if not chunk:
                    break
                amplitude = sum(abs(s) for s in chunk) / len(chunk) / 32768.0
                time_sec = i / framerate

                if amplitude < 0.02:
                    continue

                weight = min(1.0, amplitude * 5)

                if text_chars:
                    char_idx = min(
                        int((i / len(samples)) * len(text_chars)), len(text_chars) - 1
                    )
                    mapped_shape = PHONEME_VISEME_MAP.get(text_chars[char_idx], "aa")
                else:
                    shape_idx = (i // chunk_size) % len(mouth_shapes)
                    mapped_shape = mouth_shapes[shape_idx]

                visemes.append(
                    {
                        "time": round(time_sec, 3),
                        "viseme": mapped_shape,
                        "weight": round(weight, 2),
                    }
                )

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
