"""
Automatic SFX detection from dialogue text.
Analyzes Chinese/Japanese text for environmental and event cues,
returns layered SFX recommendations.
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SfxLayer:
    tag: str
    volume: float
    layer_type: str  # "ambient", "event", "mood"


# Ambient: keywords → SFX tag + volume. Persists entire audio.
AMBIENT_KEYWORDS = {
    # Rain
    "rain": [
        (["下雨", "雨", "雨声", "大雨", "暴雨", "雷雨", "雨滴", "雨聲", "ザーザー", "しとしと", "雨音"], "rain", 0.3),
        (["小雨", "微雨", "細雨", "毛毛雨"], "rain_light", 0.25),
        (["暴風雨", "豪雨", "狂風暴雨"], "rain_heavy", 0.35),
    ],
    # Bath/shower
    "bath": [
        (["洗澡", "浴室", "浴缸", "泡澡", "シャワー", "お風呂", "湯船"], "shower", 0.25),
    ],
}

# Event: keywords → SFX tag + volume. One-shot, placed where keyword appears.
EVENT_KEYWORDS = [
    (["脱衣", "脱", "脫", "服を脱", "解开", "解開", "扣子"], "clothes_rustle", 0.5),
    (["床", "ベッド", "躺", "横になる", "布団", "被窩", "被子", "被窝"], "bedsheet", 0.4),
    (["拉鍊", "ファスナー", "zipper"], "zipper", 0.5),
    (["門", "ドア", "开门", "開門", "关门", "關門"], "door", 0.5),
]

# Mood: emotion → SFX tag + volume. Ambient layer based on emotion.
MOOD_MAP = {
    "horny": ("handjob_slow", 0.35),
    "relaxed": (None, 0),  # ambient handles relaxed scenes
    "happy": (None, 0),
    "sad": (None, 0),
    "angry": (None, 0),
    "surprised": (None, 0),
    "neutral": (None, 0),
}


def detect_sfx(text: str, emotion: str = "neutral") -> list[SfxLayer]:
    """Analyze text and emotion, return list of SFX layers to apply.

    Returns layers sorted by priority: ambient first, then mood, then events.
    """
    layers = []
    text_lower = text.lower()

    # 1. Detect ambient sounds from text content
    for category, patterns in AMBIENT_KEYWORDS.items():
        for keywords, tag, volume in patterns:
            if any(kw in text for kw in keywords):
                layers.append(SfxLayer(tag=tag, volume=volume, layer_type="ambient"))
                break  # one per category

    # 2. Detect mood-based ambient
    mood_tag, mood_vol = MOOD_MAP.get(emotion, (None, 0))
    if mood_tag:
        # Don't add mood SFX if ambient already covers the scene
        if not any(l.layer_type == "ambient" for l in layers):
            layers.append(SfxLayer(tag=mood_tag, volume=mood_vol, layer_type="mood"))

    # 3. Detect event sounds (not used in batch auto-mix, but available for scene_mixer)
    for keywords, tag, volume in EVENT_KEYWORDS:
        if any(kw in text for kw in keywords):
            layers.append(SfxLayer(tag=tag, volume=volume, layer_type="event"))

    if layers:
        logger.info(f"SFX auto-detect: {', '.join(f'{l.tag}({l.layer_type}@{l.volume})' for l in layers)}")

    return layers
