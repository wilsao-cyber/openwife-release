import asyncio
import logging
from skills.base_skill import BaseSkill

logger = logging.getLogger(__name__)


class BrowserSkill(BaseSkill):
    """Browser automation skill using browser-use library."""

    def __init__(self):
        self._browser = None
        self._initialized = False

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "browser_go_to",
                    "description": "打開指定網址 (Navigate to a URL). 瀏覽器會前往該網頁。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "要前往的網址"},
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_click",
                    "description": "點擊網頁上的元素 (Click an element on the page). 需要指定元素的描述或索引。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "index": {
                                "type": "integer",
                                "description": "要點擊的元素索引",
                            },
                        },
                        "required": ["index"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_type",
                    "description": "在網頁上輸入文字 (Type text into an input field).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "index": {
                                "type": "integer",
                                "description": "要輸入的元素索引",
                            },
                            "text": {"type": "string", "description": "要輸入的文字"},
                        },
                        "required": ["index", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_scroll",
                    "description": "捲動網頁 (Scroll the page). amount 為正數向下捲，負數向上捲。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "amount": {
                                "type": "integer",
                                "description": "捲動量，預設 500",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_extract",
                    "description": "從當前網頁擷取資訊 (Extract information from the current page). 用自然語言描述你要什麼。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "goal": {
                                "type": "string",
                                "description": "要擷取的資訊描述",
                            },
                        },
                        "required": ["goal"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_task",
                    "description": "用自然語言描述一個瀏覽器任務 (Describe a browser task in natural language). AI 會自動操作瀏覽器完成。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "任務描述，例如「去 PTT 看今天的熱門文章」",
                            },
                            "url": {
                                "type": "string",
                                "description": "起始網址（可選）",
                            },
                        },
                        "required": ["task"],
                    },
                },
            },
        ]

    async def initialize(self):
        """Initialize the browser."""
        if self._initialized:
            return
        try:
            from browser_use import Browser

            self._browser = Browser(
                disable_security=True,
                headless=True,
            )
            self._initialized = True
            logger.info("Browser initialized")
        except Exception as e:
            logger.warning(f"Browser initialization failed: {e}")
            self._browser = None

    async def execute(self, tool_name: str, **kwargs) -> dict:
        if not self._initialized:
            await self.initialize()
        if not self._browser:
            return {"error": "Browser not available"}

        dispatch = {
            "browser_go_to": lambda: self._go_to(kwargs["url"]),
            "browser_click": lambda: self._click(kwargs["index"]),
            "browser_type": lambda: self._type(kwargs["index"], kwargs["text"]),
            "browser_scroll": lambda: self._scroll(kwargs.get("amount", 500)),
            "browser_extract": lambda: self._extract(kwargs["goal"]),
            "browser_task": lambda: self._run_task(kwargs["task"], kwargs.get("url")),
        }
        method = dispatch.get(tool_name)
        if not method:
            return {"error": f"Unknown browser tool: {tool_name}"}
        return await method()

    async def _go_to(self, url: str) -> dict:
        try:
            from browser_use import Agent, ChatBrowserUse

            agent = Agent(
                task=f"Go to {url} and tell me what you see on the page",
                llm=ChatBrowserUse(),
                browser=self._browser,
            )
            result = await agent.run()
            return {"success": True, "url": url, "result": str(result)}
        except Exception as e:
            return {"error": str(e)}

    async def _click(self, index: int) -> dict:
        try:
            from browser_use import Agent, ChatBrowserUse

            agent = Agent(
                task=f"Click element {index} on the current page",
                llm=ChatBrowserUse(),
                browser=self._browser,
            )
            result = await agent.run()
            return {"success": True, "clicked": index, "result": str(result)}
        except Exception as e:
            return {"error": str(e)}

    async def _type(self, index: int, text: str) -> dict:
        try:
            from browser_use import Agent, ChatBrowserUse

            agent = Agent(
                task=f"Type '{text}' into element {index}",
                llm=ChatBrowserUse(),
                browser=self._browser,
            )
            result = await agent.run()
            return {"success": True, "typed": text, "result": str(result)}
        except Exception as e:
            return {"error": str(e)}

    async def _scroll(self, amount: int = 500) -> dict:
        try:
            from browser_use import Agent, ChatBrowserUse

            direction = "down" if amount > 0 else "up"
            agent = Agent(
                task=f"Scroll {direction} by {abs(amount)} pixels",
                llm=ChatBrowserUse(),
                browser=self._browser,
            )
            result = await agent.run()
            return {"success": True, "result": str(result)}
        except Exception as e:
            return {"error": str(e)}

    async def _extract(self, goal: str) -> dict:
        try:
            from browser_use import Agent, ChatBrowserUse

            agent = Agent(
                task=f"Extract the following information from the current page: {goal}",
                llm=ChatBrowserUse(),
                browser=self._browser,
            )
            result = await agent.run()
            return {"success": True, "goal": goal, "result": str(result)}
        except Exception as e:
            return {"error": str(e)}

    async def _run_task(self, task: str, url: str = None) -> dict:
        try:
            from browser_use import Agent, ChatBrowserUse

            full_task = f"Go to {url}\n\nThen: {task}" if url else task
            agent = Agent(
                task=full_task,
                llm=ChatBrowserUse(),
                browser=self._browser,
            )
            result = await agent.run()
            return {"success": True, "task": task, "result": str(result)}
        except Exception as e:
            return {"error": str(e)}

    async def close(self):
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
            self._initialized = False
