import pytest
from unittest.mock import patch, MagicMock
import httpx
from vision_analyzer import VisionAnalyzer


@pytest.fixture
def analyzer():
    return VisionAnalyzer(vision_model="llava", change_threshold=0.3)


class TestChangeDetection:
    def test_first_frame_always_significant(self, analyzer):
        assert analyzer.has_significant_change(b"frame1", None) is True

    def test_same_frame_no_change(self, analyzer):
        frame = b"identical_frame_data"
        assert analyzer.has_significant_change(frame, frame) is False

    def test_different_frames_detected(self, analyzer):
        assert analyzer.has_significant_change(b"frame1", b"frame2") is True


class TestAnalyzeSingle:
    def test_returns_text_and_emotion(self, analyzer):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": "I see a cat"}

        with patch("httpx.Client") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = analyzer.analyze_single(b"image_bytes", "en")
            assert result["text"] == "I see a cat"
            assert result["emotion"] == "neutral"

    def test_uses_correct_language_prompt(self, analyzer):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": "test"}

        with patch("httpx.Client") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client_instance

            analyzer.analyze_single(b"img", "zh-TW")
            call_args = mock_client_instance.post.call_args
            payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
            assert "繁體中文" in payload["prompt"]

    def test_error_returns_error_message(self, analyzer):
        with patch("httpx.Client") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = httpx.ConnectError("refused")
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = analyzer.analyze_single(b"img", "en")
            assert "Error" in result["text"] or "error" in result["text"].lower()
            assert result["emotion"] == "sad"


class TestAnalyzeStream:
    def test_returns_none_when_no_change(self, analyzer):
        frame = b"same_frame"
        result = analyzer.analyze_stream(frame, frame, "en")
        assert result is None

    def test_analyzes_when_change_detected(self, analyzer):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": "something changed"}

        with patch("httpx.Client") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = analyzer.analyze_stream(b"frame1", b"frame2", "en")
            assert result is not None
            assert result["text"] == "something changed"
