from skills.base_skill import BaseSkill
from tools.mcp_desktop_tool import MCPDesktopTool


class DesktopSkill(BaseSkill):
    def __init__(self):
        self._tool = MCPDesktopTool()

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "desktop_screenshot",
                    "description": "擷取桌面截圖 (Take a screenshot of the desktop). 可以選擇是否偵測畫面中的元素。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "detect_elements": {
                                "type": "boolean",
                                "description": "是否偵測畫面中的 UI 元素，預設 true",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_click",
                    "description": "在桌面上點擊指定位置或元素 (Click on the desktop at a position or element).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "element_id": {
                                "type": "integer",
                                "description": "要點擊的 UI 元素 ID",
                            },
                            "x": {
                                "type": "number",
                                "description": "點擊位置的 X 百分比 (0-1)",
                            },
                            "y": {
                                "type": "number",
                                "description": "點擊位置的 Y 百分比 (0-1)",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_type",
                    "description": "在桌面上輸入文字 (Type text on the desktop).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "要輸入的文字"},
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_hotkey",
                    "description": "按下組合鍵 (Press a keyboard hotkey combination). 例如 ['ctrl', 'c']。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keys": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "按鍵列表，例如 ['ctrl', 'c'] 或 ['alt', 'tab']",
                            },
                        },
                        "required": ["keys"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_open_browser",
                    "description": "在桌面上打開瀏覽器並導航到指定網址 (Open a browser on the desktop and navigate to a URL).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "要打開的網址"},
                        },
                        "required": ["url"],
                    },
                },
            },
        ]

    async def initialize(self):
        await self._tool.initialize()

    async def execute(self, tool_name: str, **kwargs) -> dict:
        dispatch = {
            "desktop_screenshot": lambda: self._tool.screenshot(
                detect_elements=kwargs.get("detect_elements", True),
            ),
            "desktop_click": lambda: self._tool.click(
                element_id=kwargs.get("element_id"),
                x=kwargs.get("x"),
                y=kwargs.get("y"),
            ),
            "desktop_type": lambda: self._tool.type(
                text=kwargs["text"],
            ),
            "desktop_hotkey": lambda: self._tool.hotkey(
                keys=kwargs["keys"],
            ),
            "desktop_open_browser": lambda: self._tool.open_browser(
                url=kwargs["url"],
            ),
        }
        method = dispatch.get(tool_name)
        if not method:
            return {"error": f"Unknown desktop tool: {tool_name}"}
        return await method()
