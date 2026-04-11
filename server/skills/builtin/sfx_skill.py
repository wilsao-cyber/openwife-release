import logging
from skills.base_skill import BaseSkill
from sfx_catalog import sfx_catalog

logger = logging.getLogger(__name__)


class SfxSkill(BaseSkill):
    """Skill for playing sound effects alongside voice. LLM selects SFX based on scene context."""

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "sfx_play",
                    "description": (
                        "効果音を再生する (Play sound effects). "
                        "Use semantic tags for accuracy. Available tags:\n"
                        "Intimate: handjob_slow, handjob_fast, handjob_irregular, handjob_buildup, "
                        "lotion_apply, lotion_bottle, piston_slow, piston_fast, piston_wet, piston_dry, "
                        "ejaculation, ejaculation_heavy, squirt, onahole, condom, tissue\n"
                        "Fabric: bedsheet, clothes_rustle, zipper\n"
                        "Environment: rain, rain_heavy, rain_light\n"
                        "Daily: typing, gaming, bath_water, shower, ear_cleaning\n"
                        "Action: door, footstep"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tag": {
                                "type": "string",
                                "description": "Semantic tag (e.g., 'handjob_slow', 'rain', 'bedsheet', 'piston_fast')",
                            },
                            "description": {
                                "type": "string",
                                "description": "Fallback: free-text description if no tag matches",
                            },
                            "loop": {
                                "type": "boolean",
                                "description": "Whether to loop (for ambient/continuous sounds). Default false.",
                            },
                            "volume": {
                                "type": "number",
                                "description": "Volume 0.0-1.0. Default 0.3 for background, 0.6 for prominent.",
                            },
                        },
                        "required": ["description"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sfx_stop",
                    "description": "効果音を停止する (Stop all currently playing sound effects).",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    async def execute(self, tool_name: str, **kwargs) -> dict:
        if tool_name == "sfx_play":
            tag = kwargs.get("tag", "")
            query = kwargs.get("description", "")
            loop = kwargs.get("loop", False)
            volume = kwargs.get("volume", 0.3)

            results = sfx_catalog.search(tag=tag, query=query, limit=3)
            if not results:
                return {"content": "No matching sound effects found."}

            urls = [sfx_catalog.get_url(r) for r in results]
            desc = results[0].description
            return {
                "content": f"🔊 Playing: {desc}",
                "sfx": {
                    "urls": urls,
                    "loop": loop,
                    "volume": volume,
                },
            }

        elif tool_name == "sfx_stop":
            return {
                "content": "🔇 Sound effects stopped.",
                "sfx": {"stop": True},
            }

        return {"error": f"Unknown sfx tool: {tool_name}"}
