import logging
from skills.base_skill import BaseSkill
from config import config

logger = logging.getLogger(__name__)


class VoiceSkill(BaseSkill):
    """Skill for managing voice profiles via Voicebox API."""

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "voice_list_profiles",
                    "description": "列出所有可用的語音角色 (List all voice profiles). 顯示名稱、ID、語言。",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "voice_switch_profile",
                    "description": "切換目前使用的語音角色 (Switch active voice profile). 可以切換正常語音或親密語音。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "profile_id": {
                                "type": "string",
                                "description": "語音角色 ID",
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["normal", "horny"],
                                "description": "切換哪個語音：normal=正常, horny=親密",
                            },
                        },
                        "required": ["profile_id", "mode"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "voice_test_generate",
                    "description": "用指定角色生成測試語音 (Test voice generation with a profile).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "profile_id": {
                                "type": "string",
                                "description": "語音角色 ID",
                            },
                            "text": {
                                "type": "string",
                                "description": "要生成的日文文字",
                            },
                        },
                        "required": ["profile_id"],
                    },
                },
            },
        ]

    async def execute(self, tool_name: str, **kwargs) -> dict:
        import httpx

        voicebox_url = config.tts.voicebox_api_url

        if tool_name == "voice_list_profiles":
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{voicebox_url}/profiles")
                resp.raise_for_status()
                profiles = resp.json()
            current_normal = config.tts.voicebox_profile_id
            current_horny = config.tts.voicebox_horny_profile_id
            lines = ["📋 可用語音角色:\n"]
            for p in profiles:
                active = ""
                if p["id"] == current_normal:
                    active = " ← 目前正常語音"
                elif p["id"] == current_horny:
                    active = " ← 目前親密語音"
                lines.append(f"• **{p['name']}** (`{p['id'][:8]}...`) {p.get('language', '')}{active}")
            return {"content": "\n".join(lines)}

        elif tool_name == "voice_switch_profile":
            profile_id = kwargs["profile_id"]
            mode = kwargs.get("mode", "normal")
            if mode == "normal":
                config.tts.voicebox_profile_id = profile_id
                return {"content": f"✅ 正常語音已切換為 `{profile_id[:8]}...`"}
            else:
                config.tts.voicebox_horny_profile_id = profile_id
                return {"content": f"✅ 親密語音已切換為 `{profile_id[:8]}...`"}

        elif tool_name == "voice_test_generate":
            profile_id = kwargs["profile_id"]
            text = kwargs.get("text", "こんにちは、今日もいい天気だね。")
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{voicebox_url}/generate",
                    json={
                        "profile_id": profile_id,
                        "text": text,
                        "language": "ja",
                        "instruct": "甘えた可愛い女の子の声で、愛情と温もりを込めて、ゆっくり話してください",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            audio_path = data.get("audio_path", "")
            duration = data.get("duration", 0)
            return {
                "content": f"🔊 測試語音生成完成 ({duration:.1f}s)",
                "media": [{"type": "audio", "url": f"{voicebox_url}/{audio_path}"}],
            }

        return {"error": f"Unknown voice tool: {tool_name}"}
