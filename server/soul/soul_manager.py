import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SoulManager:
    def __init__(self, soul_dir: str = "server/soul"):
        self.soul_dir = Path(soul_dir)

    def load_soul(self) -> str:
        path = self.soul_dir / "SOUL.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        logger.warning(f"SOUL.md not found at {path}")
        return ""

    def load_profile(self) -> str:
        path = self.soul_dir / "PROFILE.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def get_chat_prompt(self, language: str) -> str:
        soul = self.load_soul()
        profile = self.load_profile()
        lang_instruction = {
            "zh-TW": "用繁體中文回覆。",
            "ja": "日本語で返答してください。",
            "en": "Reply in English.",
        }.get(language, "")

        parts = [soul]
        if profile:
            parts.append(f"\n## User Profile\n{profile}")
        parts.append(f"\n{lang_instruction}")
        parts.append("\n回覆最後一行加 [emotion:TAG]，TAG: happy/sad/angry/surprised/relaxed/neutral")

        return "\n".join(parts)

    def get_assist_prompt(self, language: str) -> str:
        base = self.get_chat_prompt(language)
        return f"""{base}

## Assist Mode Rules
你正在協助模式。使用提供的工具來幫助用戶。
- 分析用戶的需求，選擇合適的工具
- 生成完整的工具參數（例如 file_write 要生成完整檔案內容）
- 如果需要多個步驟，列出所有需要的工具調用
- 不要假裝執行了工具，系統會真正執行
- 回覆時先簡要說明你打算做什麼"""

    def update_soul(self, content: str):
        path = self.soul_dir / "SOUL.md"
        path.write_text(content, encoding="utf-8")

    def update_profile(self, content: str):
        path = self.soul_dir / "PROFILE.md"
        path.write_text(content, encoding="utf-8")
