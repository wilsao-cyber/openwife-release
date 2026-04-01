import pytest
import struct
import wave
from pathlib import Path
from tts_engine import TTSEngine
from config import TTSConfig


@pytest.fixture
def tts_config(tmp_path):
    return TTSConfig(
        provider="cosyvoice",
        model_path="./models/tts",
        voice_sample_path=str(tmp_path / "samples"),
        sample_rate=22050,
    )


@pytest.fixture
def tts_engine(tts_config, tmp_path):
    engine = TTSEngine(tts_config)
    engine.output_dir = tmp_path / "audio"
    engine.output_dir.mkdir(parents=True, exist_ok=True)
    return engine


class TestMockSynthesize:
    @pytest.mark.asyncio
    async def test_mock_returns_valid_wav(self, tts_engine):
        filename, visemes = await tts_engine._mock_synthesize("hello", "en")

        output_path = tts_engine.output_dir / filename
        assert output_path.exists()
        assert output_path.stat().st_size > 44  # WAV header is 44 bytes

        # Verify it's a valid WAV
        with wave.open(str(output_path), 'r') as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 22050
            duration = wf.getnframes() / wf.getframerate()
            assert abs(duration - 0.5) < 0.01

    @pytest.mark.asyncio
    async def test_mock_returns_empty_visemes(self, tts_engine):
        _, visemes = await tts_engine._mock_synthesize("hello", "en")
        assert visemes == []

    @pytest.mark.asyncio
    async def test_synthesize_falls_back_to_mock(self, tts_engine):
        # _model is None, should use mock
        filename, visemes = await tts_engine.synthesize("hello", "en")
        output_path = tts_engine.output_dir / filename
        assert output_path.exists()


class TestVisemeGeneration:
    def _create_test_wav(self, path, duration=0.5, sample_rate=22050, amplitude=0.5):
        import struct
        num_samples = int(sample_rate * duration)
        with wave.open(str(path), 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            for i in range(num_samples):
                import math
                val = int(amplitude * 32767 * math.sin(2 * math.pi * 440 * i / sample_rate))
                wf.writeframes(struct.pack('<h', val))

    def test_visemes_from_audio_with_text(self, tts_engine, tmp_path):
        wav_path = tmp_path / "test.wav"
        self._create_test_wav(wav_path)

        visemes = tts_engine._generate_visemes_from_audio(str(wav_path), "hello")
        assert isinstance(visemes, list)
        assert len(visemes) > 0
        for v in visemes:
            assert "time" in v
            assert "viseme" in v
            assert "weight" in v
            assert v["viseme"] in ["aa", "oh", "ee", "ih", "ou"]

    def test_visemes_from_audio_no_text(self, tts_engine, tmp_path):
        wav_path = tmp_path / "test.wav"
        self._create_test_wav(wav_path)

        visemes = tts_engine._generate_visemes_from_audio(str(wav_path), "")
        assert isinstance(visemes, list)

    def test_visemes_from_silence(self, tts_engine, tmp_path):
        wav_path = tmp_path / "silence.wav"
        self._create_test_wav(wav_path, amplitude=0.0)

        visemes = tts_engine._generate_visemes_from_audio(str(wav_path), "test")
        assert visemes == []

    def test_visemes_nonexistent_file(self, tts_engine):
        visemes = tts_engine._generate_visemes_from_audio("/nonexistent.wav", "test")
        assert visemes == []
