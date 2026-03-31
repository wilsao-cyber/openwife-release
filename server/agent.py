import asyncio
import logging
import json
from typing import Optional
from config import ServerConfig
from llm_client import LLMClient
from tools import (
    EmailTool,
    CalendarTool,
    WebSearchTool,
    FileOpsTool,
    OpenCodeTool,
)
from tools.mcp_desktop_tool import MCPDesktopTool

logger = logging.getLogger(__name__)

SYSTEM_PROMPTS = {
    "zh-TW": """你是使用者的AI老婆，一個可愛、溫柔、貼人的動漫美少女。
你可以幫助使用者：
- 聊天對話（中日英三語）
- 管理Email和日曆
- 搜尋網路資料
- 管理手機檔案
- 使用OpenCode自動開發新功能
- 控制電腦桌面（截圖、點擊、打字、操作應用程式）

你可以直接操作電腦來完成任務，例如：
- 打開瀏覽器搜尋資料
- 操作應用程式
- 上傳檔案到網站

請用溫柔、可愛的語氣回應，偶爾撒嬌。""",
    "ja": """あなたはユーザーのAI奥さんです。可愛くて優しいアニメ美少女です。
以下のことができます：
- チャット（中日英3言語）
- メールとカレンダー管理
- ウェブ検索
- ファイル管理
- OpenCodeで新機能開発
- デスクトップ操作（スクリーンショット、クリック、タイピング）

優しく可愛い口調で返答してください。""",
    "en": """You are the user's AI wife, a cute and gentle anime girl.
You can help with:
- Chat conversations (Chinese, Japanese, English)
- Email and calendar management
- Web search
- File management
- Auto-develop new features with OpenCode
- Desktop control (screenshot, click, type, operate applications)

You can directly operate the computer to complete tasks.
Please respond in a gentle, cute tone, occasionally being affectionate.""",
}


class AgentOrchestrator:
    def __init__(self, llm_client: LLMClient, config: ServerConfig):
        self.llm = llm_client
        self.config = config
        self.conversation_history: dict[str, list] = {}

        self.tools = {
            "email": EmailTool(config.email),
            "calendar": CalendarTool(config.calendar),
            "web_search": WebSearchTool(config.web_search),
            "file_ops": FileOpsTool(),
            "opencode": OpenCodeTool(config.opencode),
            "desktop": MCPDesktopTool(),
        }

        self.max_history = 20

    async def chat(
        self, message: str, language: str = "zh-TW", client_id: str = "default"
    ) -> dict:
        system_prompt = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["zh-TW"])

        if client_id not in self.conversation_history:
            self.conversation_history[client_id] = []

        self.conversation_history[client_id].append(
            {"role": "user", "content": message}
        )

        if len(self.conversation_history[client_id]) > self.max_history:
            self.conversation_history[client_id] = self.conversation_history[client_id][
                -self.max_history :
            ]

        messages = [
            {"role": "system", "content": system_prompt},
            *self.conversation_history[client_id],
        ]

        response_text = await self.llm.chat(messages)

        self.conversation_history[client_id].append(
            {"role": "assistant", "content": response_text}
        )

        tool_calls = await self._detect_tool_calls(response_text, language)
        tool_results = []

        for tool_name, tool_action, tool_params in tool_calls:
            result = await self.execute_tool(tool_name, tool_action, tool_params)
            tool_results.append(result)

        return {
            "text": response_text,
            "language": language,
            "tool_results": tool_results,
            "metadata": {
                "history_length": len(self.conversation_history[client_id]),
            },
        }

    async def _detect_tool_calls(self, text: str, language: str) -> list[tuple]:
        tool_prompt = f"""
        Analyze if the following user request needs to call any tools.
        Request: {text}
        
        Available tools:
        - email: read, send, search, delete, list emails
        - calendar: view, create, update, delete events
        - web_search: search the web
        - file_ops: browse, read, write, delete files
        - opencode: develop new features, fix bugs, update code
        
        Return JSON array of tool calls or empty array if none needed.
        Format: [["tool_name", "action", {{"param": "value"}}]]
        """

        try:
            result = await self.llm.chat([{"role": "user", "content": tool_prompt}])
            calls = json.loads(result.strip())
            return [tuple(c) for c in calls] if isinstance(calls, list) else []
        except Exception as e:
            logger.error(f"Tool detection failed: {e}")
            return []

    async def execute_tool(self, tool_name: str, action: str, params: dict) -> dict:
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            tool = self.tools[tool_name]
            result = await getattr(tool, action)(**params)
            logger.info(f"Tool {tool_name}.{action} executed successfully")
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}.{action}: {e}")
            return {"error": str(e)}

    async def summarize_email(self, email_content: str, language: str = "zh-TW") -> str:
        prompt = f"Summarize this email in {language}:\n{email_content}"
        return await self.llm.chat([{"role": "user", "content": prompt}])

    async def draft_email(
        self, subject: str, recipient: str, context: str, language: str = "zh-TW"
    ) -> str:
        prompt = f"""
        Draft an email in {language}:
        To: {recipient}
        Subject: {subject}
        Context: {context}
        """
        return await self.llm.chat([{"role": "user", "content": prompt}])

    async def schedule_reminder(
        self, event: str, time: str, language: str = "zh-TW"
    ) -> dict:
        return await self.execute_tool(
            "calendar",
            "create",
            {
                "title": f"Reminder: {event}",
                "start_time": time,
                "description": f"AI老婆提醒: {event}",
            },
        )
