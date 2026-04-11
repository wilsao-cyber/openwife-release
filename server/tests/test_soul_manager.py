import pytest
from pathlib import Path


@pytest.fixture
def soul_dir(tmp_path):
    soul_md = tmp_path / "SOUL.md"
    soul_md.write_text(
        "# Test Soul\n\n## Identity\nTest identity.\n\n## Personality\n- Kind\n",
        encoding="utf-8",
    )
    profile_md = tmp_path / "PROFILE.md"
    profile_md.write_text(
        "# User Profile\n\n## Preferences\n- likes cats\n", encoding="utf-8"
    )
    return str(tmp_path)


def test_load_soul(soul_dir):
    from soul.soul_manager import SoulManager

    sm = SoulManager(soul_dir=soul_dir)
    soul = sm.load_soul()
    assert "Test Soul" in soul
    assert "Test identity" in soul


def test_load_profile(soul_dir):
    from soul.soul_manager import SoulManager

    sm = SoulManager(soul_dir=soul_dir)
    profile = sm.load_profile()
    assert "likes cats" in profile


def test_load_profile_missing(tmp_path):
    soul_md = tmp_path / "SOUL.md"
    soul_md.write_text("# Soul\n", encoding="utf-8")
    from soul.soul_manager import SoulManager

    sm = SoulManager(soul_dir=str(tmp_path))
    profile = sm.load_profile()
    assert profile == ""


def test_get_chat_prompt_zh(soul_dir):
    from soul.soul_manager import SoulManager

    sm = SoulManager(soul_dir=soul_dir)
    prompt = sm.get_chat_prompt("zh-TW")
    assert "Test identity" in prompt
    assert "likes cats" in prompt
    assert "繁體中文" in prompt
    assert "[emotion:TAG]" in prompt


def test_get_chat_prompt_en(soul_dir):
    from soul.soul_manager import SoulManager

    sm = SoulManager(soul_dir=soul_dir)
    prompt = sm.get_chat_prompt("en")
    assert "English" in prompt


def test_get_assist_prompt(soul_dir):
    from soul.soul_manager import SoulManager

    sm = SoulManager(soul_dir=soul_dir)
    prompt = sm.get_assist_prompt("zh-TW")
    assert "Assist Mode" in prompt
    assert "tool" in prompt.lower()


def test_update_soul(soul_dir):
    from soul.soul_manager import SoulManager

    sm = SoulManager(soul_dir=soul_dir)
    sm.update_soul("# New Soul\n\nNew content.")
    soul = sm.load_soul()
    assert "New Soul" in soul
    assert "New content" in soul


def test_update_profile(soul_dir):
    from soul.soul_manager import SoulManager

    sm = SoulManager(soul_dir=soul_dir)
    sm.update_profile("# New Profile\n\nNew prefs.")
    profile = sm.load_profile()
    assert "New prefs" in profile
