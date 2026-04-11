import logging
from skills.base_skill import BaseSkill

logger = logging.getLogger(__name__)

# Injected at startup via initialize()
_tts_engine = None


class SceneSkill(BaseSkill):
    """Skill for creating immersive audio scenes with TTS + SFX mixed together."""

    async def initialize(self):
        """Get tts_engine reference after startup completes."""
        global _tts_engine
        try:
            import main as m
            _tts_engine = m.tts_engine
            logger.info("SceneSkill: tts_engine injected")
        except Exception as e:
            logger.warning(f"SceneSkill init failed: {e}")

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "scene_play",
                    "description": (
                        "創建沉浸式音頻場景，將語音和效果音混合成一個音檔播放。\n"
                        "script 陣列步驟：\n"
                        '- {"type":"speech","text":"台詞"}\n'
                        '- {"type":"sfx","tag":"semantic_tag","volume":0.3} — 用 tag 指定效果音\n'
                        '- {"type":"pause","duration":5} — 暫停 N 秒（效果音持續）\n'
                        '- {"type":"sfx_stop"}\n'
                        "可用 tags:\n"
                        "handjob_slow, handjob_fast, handjob_irregular, handjob_buildup, "
                        "lotion_apply, lotion_bottle, piston_slow, piston_fast, piston_wet, "
                        "ejaculation, ejaculation_heavy, squirt, bedsheet, clothes_rustle, "
                        "rain, rain_light, shower, ear_cleaning"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "script": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string", "enum": ["speech", "sfx", "pause", "sfx_stop"]},
                                        "text": {"type": "string"},
                                        "tag": {"type": "string"},
                                        "query": {"type": "string"},
                                        "volume": {"type": "number"},
                                        "duration": {"type": "number"},
                                        "fade_in": {"type": "number"},
                                    },
                                },
                                "description": "場景腳本步驟列表",
                            },
                        },
                        "required": ["script"],
                    },
                },
            },
        ]

    async def execute(self, tool_name: str, **kwargs) -> dict:
        if tool_name != "scene_play":
            return {"error": f"Unknown tool: {tool_name}"}

        script = kwargs.get("script", [])
        if not script:
            return {"error": "Empty script"}

        global _tts_engine
        if not _tts_engine:
            return {"error": "TTS engine not initialized"}

        try:
            from scene_mixer import mix_scene
            from sfx_catalog import sfx_catalog

            path = await mix_scene(
                script=script,
                tts_engine=_tts_engine,
                sfx_catalog=sfx_catalog,
                language="zh-TW",
                emotion=kwargs.get("emotion", "neutral"),
            )
            if not path:
                return {"error": "Scene mixing failed"}

            return {
                "content": "🎬 場景音頻已生成",
                "media": [{"type": "audio", "url": f"/audio/{path.name}"}],
                "scene_audio": f"/audio/{path.name}",
            }
        except Exception as e:
            logger.error(f"Scene mixing failed: {e}", exc_info=True)
            return {"error": str(e)}
