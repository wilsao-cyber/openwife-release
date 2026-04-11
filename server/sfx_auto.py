"""
Automatic SFX detection from dialogue text.
Analyzes Chinese/Japanese text for environmental and event cues,
returns layered SFX recommendations.
"""

import logging
from dataclasses import dataclass

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

    # 1. Detect ambient sounds from text content
    for category, patterns in AMBIENT_KEYWORDS.items():
        for keywords, tag, volume in patterns:
            if any(kw in text for kw in keywords):
                layers.append(SfxLayer(tag=tag, volume=volume, layer_type="ambient"))
                break  # one per category

    # 2. Detect mood-based ambient (always add, independent of ambient layer)
    mood_tag, mood_vol = MOOD_MAP.get(emotion, (None, 0))
    if mood_tag:
        layers.append(SfxLayer(tag=mood_tag, volume=mood_vol, layer_type="mood"))

    # Event sounds only used by scene_mixer, not auto-mix in batch TTS

    if layers:
        logger.info(f"SFX auto-detect: {', '.join(f'{l.tag}({l.layer_type}@{l.volume})' for l in layers)}")

    return layers
