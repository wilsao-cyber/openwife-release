import pytest
import base64

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)
TINY_PNG_2 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture
def analyzer():
    from vision_analyzer import VisionAnalyzer

    return VisionAnalyzer(vision_model=None)


@pytest.mark.asyncio
async def test_analyze_returns_result_or_error(analyzer):
    result = await analyzer.analyze_single(TINY_PNG, language="zh-TW")
    assert "text" in result
    assert "emotion" in result
    assert result["emotion"] in ("neutral", "sad")


def test_has_significant_change_same_image(analyzer):
    assert not analyzer.has_significant_change(TINY_PNG, TINY_PNG)


def test_has_significant_change_different_images(analyzer):
    assert analyzer.has_significant_change(TINY_PNG, TINY_PNG_2)


@pytest.mark.asyncio
async def test_analyze_stream_skips_when_no_change(analyzer):
    result = await analyzer.analyze_stream(TINY_PNG, TINY_PNG, language="zh-TW")
    assert result is None


@pytest.mark.asyncio
async def test_analyze_stream_responds_on_first_frame(analyzer):
    result = await analyzer.analyze_stream(TINY_PNG, None, language="zh-TW")
    assert result is not None
    assert "text" in result
