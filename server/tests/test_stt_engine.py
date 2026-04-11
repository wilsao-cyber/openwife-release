import pytest
from stt_engine import STTEngine
from config import STTConfig


@pytest.fixture
def stt_config():
    return STTConfig(provider="whisper", model="medium", language="auto")


@pytest.fixture
def stt_engine(stt_config):
    engine = STTEngine(stt_config)
    # Don't initialize — model stays None, exercises mock path
    return engine


class TestSTTMock:
    @pytest.mark.asyncio
    async def test_mock_returns_warning_message(self, stt_engine):
        result = await stt_engine.transcribe(b"fake_audio_data")
        assert "not available" in result.lower() or "not installed" in result.lower()

    @pytest.mark.asyncio
    async def test_mock_does_not_return_fake_transcription(self, stt_engine):
        result = await stt_engine.transcribe(b"fake_audio_data")
        # Should NOT return convincing fake text
        assert "[" in result  # bracketed warning message


class TestSTTFileTranscribe:
    @pytest.mark.asyncio
    async def test_transcribe_file_reads_and_calls_transcribe(self, stt_engine, tmp_path):
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio content")

        result = await stt_engine.transcribe_file(str(audio_file))
        assert "not available" in result.lower() or "not installed" in result.lower()
