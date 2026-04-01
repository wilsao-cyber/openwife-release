from skills.base_skill import BaseSkill
from tools.web_search_tool import WebSearchTool
from config import config


class SearchSkill(BaseSkill):
    def __init__(self):
        self._tool = WebSearchTool(config.web_search)

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "在網路上搜尋資訊 (Search the web for information). 使用 SearXNG 或 Tavily 搜尋引擎。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜尋關鍵字或問題句",
                            },
                            "num_results": {
                                "type": "integer",
                                "description": "回傳的搜尋結果數量，預設 10",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
        ]

    async def execute(self, tool_name: str, **kwargs) -> dict:
        if tool_name == "web_search":
            return await self._tool.search(
                query=kwargs["query"],
                num_results=kwargs.get("num_results", 10),
            )
        return {"error": f"Unknown search tool: {tool_name}"}
