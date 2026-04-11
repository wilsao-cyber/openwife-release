"""
Self-Evolution Skill — gives the AI tools to create/manage her own skills,
update her personality, record user info, and reflect on conversations.
"""

import logging
from datetime import date, datetime
from pathlib import Path
from skills.base_skill import BaseSkill

logger = logging.getLogger(__name__)


class SelfEvolutionSkill(BaseSkill):
    def __init__(self):
        from skills.skill_loader import skill_loader
        self._loader = skill_loader
        self._soul_dir = Path(__file__).parent.parent.parent / "soul"
        self._daily_dir = Path(__file__).parent.parent / "memory" / "daily"
        self._daily_dir.mkdir(parents=True, exist_ok=True)

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "skill_create",
                    "description": "建立一個新的技能（行為指令）。技能會影響你未來的行為模式。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "技能名稱（英文，如 morning_greeting）"},
                            "description": {"type": "string", "description": "技能用途的簡短描述"},
                            "body": {"type": "string", "description": "技能的完整行為規則（Markdown 格式）"},
                            "trigger": {"type": "string", "enum": ["always", "keyword", "scheduled"], "description": "觸發方式"},
                        },
                        "required": ["name", "description", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "skill_update",
                    "description": "更新一個已有的技能內容。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "要更新的技能名稱"},
                            "body": {"type": "string", "description": "新的技能內容（Markdown）"},
                        },
                        "required": ["name", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "skill_list",
                    "description": "列出所有已學會的技能。",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "skill_disable",
                    "description": "停用一個技能（不刪除）。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "要停用的技能名稱"},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "soul_read",
                    "description": "讀取自己的人格定義（SOUL.md）。",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "soul_update",
                    "description": "更新自己的人格定義。請謹慎使用，這會影響你的核心性格。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "新的 SOUL.md 完整內容"},
                        },
                        "required": ["content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "profile_read",
                    "description": "讀取你對使用者（老公）的了解（PROFILE.md）。",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "profile_update",
                    "description": "更新你對使用者的了解。學到新東西時主動記錄。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "新的 PROFILE.md 完整內容"},
                        },
                        "required": ["content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_reflect",
                    "description": "回顧最近的對話，提取值得記住的要點。用於每日反思。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string", "description": "今天的對話摘要和學習要點"},
                        },
                        "required": ["summary"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "daily_log_write",
                    "description": "寫入今日的對話日誌摘要。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "今日摘要（Markdown）"},
                        },
                        "required": ["content"],
                    },
                },
            },
        ]

    async def execute(self, tool_name: str, **kwargs) -> dict:
        try:
            if tool_name == "skill_create":
                path = self._loader.save_skill(
                    name=kwargs["name"],
                    description=kwargs["description"],
                    body=kwargs["body"],
                    trigger=kwargs.get("trigger", "always"),
                )
                return {"content": f"技能已建立：{kwargs['name']} ({path})"}

            elif tool_name == "skill_update":
                path = self._loader.update_skill(kwargs["name"], kwargs["body"])
                return {"content": f"技能已更新：{kwargs['name']}"}

            elif tool_name == "skill_list":
                skills = self._loader.list_skills()
                if not skills:
                    return {"content": "目前沒有學會的技能。"}
                lines = []
                for s in skills:
                    status = "啟用" if s["enabled"] else "停用"
                    lines.append(f"- **{s['name']}** [{status}]: {s['description']}")
                return {"content": "\n".join(lines)}

            elif tool_name == "skill_disable":
                ok = self._loader.disable_skill(kwargs["name"])
                return {"content": f"技能已停用：{kwargs['name']}" if ok else f"找不到技能：{kwargs['name']}"}

            elif tool_name == "soul_read":
                path = self._soul_dir / "SOUL.md"
                if path.exists():
                    return {"content": path.read_text(encoding="utf-8")}
                return {"content": "SOUL.md 不存在"}

            elif tool_name == "soul_update":
                path = self._soul_dir / "SOUL.md"
                path.write_text(kwargs["content"], encoding="utf-8")
                return {"content": "人格定義已更新。"}

            elif tool_name == "profile_read":
                path = self._soul_dir / "PROFILE.md"
                if path.exists():
                    return {"content": path.read_text(encoding="utf-8")}
                return {"content": "PROFILE.md 不存在"}

            elif tool_name == "profile_update":
                path = self._soul_dir / "PROFILE.md"
                path.write_text(kwargs["content"], encoding="utf-8")
                return {"content": "使用者資料已更新。"}

            elif tool_name == "memory_reflect":
                today = str(date.today())
                path = self._daily_dir / f"{today}.md"
                # Append to today's log
                existing = path.read_text(encoding="utf-8") if path.exists() else ""
                timestamp = datetime.now().strftime("%H:%M")
                new_content = existing + f"\n## 反思 ({timestamp})\n\n{kwargs['summary']}\n"
                path.write_text(new_content, encoding="utf-8")
                return {"content": f"反思已記錄到 {today}.md"}

            elif tool_name == "daily_log_write":
                today = str(date.today())
                path = self._daily_dir / f"{today}.md"
                existing = path.read_text(encoding="utf-8") if path.exists() else f"# {today} 日誌\n"
                timestamp = datetime.now().strftime("%H:%M")
                new_content = existing + f"\n## {timestamp}\n\n{kwargs['content']}\n"
                path.write_text(new_content, encoding="utf-8")
                return {"content": f"日誌已寫入 {today}.md"}

            return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.error(f"SelfEvolution tool {tool_name} failed: {e}")
            return {"error": str(e)}
