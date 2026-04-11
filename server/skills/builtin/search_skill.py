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
                    "description": "在網路上搜尋最新資訊 (Search the web for latest information). 搜尋關鍵字不要加日期，搜尋引擎會自動排序最新結果。如果搜尋失敗會回傳 error 欄位，你必須誠實告知用戶搜尋失敗，不要假裝有結果。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜尋關鍵字（不要加日期），例如：TSMC stock price、台積電股價",
                            },
                            "num_results": {
                                "type": "integer",
                                "description": "回傳的搜尋結果數量，預設 5，最少 5",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "image_search",
                    "description": "搜尋圖片 (Search for images). 回傳圖片的 URL 列表，圖片會直接顯示在聊天中給用戶看。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜尋圖片的關鍵字",
                            },
                            "num_results": {
                                "type": "integer",
                                "description": "回傳圖片數量，預設 5",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "video_search",
                    "description": "搜尋影片 (Search for videos). 回傳影片的 URL 和嵌入碼。影片結果會顯示在聊天中。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜尋影片的關鍵字",
                            },
                            "num_results": {
                                "type": "integer",
                                "description": "回傳影片數量，預設 5",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "web_fetch",
                    "description": "擷取指定網頁的文字內容 (Fetch and extract text content from a URL). 用於讀取搜尋結果的詳細內容。回傳的內容會顯示在面板中供用戶閱讀。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "要擷取的網頁 URL",
                            },
                        },
                        "required": ["url"],
                    },
                },
            },
        ]

    async def execute(self, tool_name: str, **kwargs) -> dict:
        if tool_name == "web_search":
            result = await self._tool.search(
                query=kwargs["query"],
                num_results=max(5, kwargs.get("num_results", 5)),
            )
            return result
        if tool_name == "image_search":
            return await self._tool.search_images(
                query=kwargs["query"],
                num_results=kwargs.get("num_results", 5),
            )
        if tool_name == "video_search":
            return await self._tool.search_videos(
                query=kwargs["query"],
                num_results=kwargs.get("num_results", 5),
            )
        if tool_name == "web_fetch":
            result = await self._tool.fetch_page_content(kwargs["url"])
            # Add rich text media for panel display
            if result.get("content"):
                content = result["content"]
                html = f"<h3>{kwargs['url']}</h3><pre style='white-space:pre-wrap;'>{content[:10000]}</pre>"
                result["media"] = [{"type": "richtext", "title": kwargs["url"], "html": html}]
            return result
        return {"error": f"Unknown search tool: {tool_name}"}
