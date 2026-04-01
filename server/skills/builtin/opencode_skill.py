from skills.base_skill import BaseSkill
from tools.opencode_tool import OpenCodeTool
from config import config


class OpenCodeSkill(BaseSkill):
    def __init__(self):
        self._tool = OpenCodeTool(config.opencode)

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "opencode_execute",
                    "description": "使用 OpenCode 執行程式開發任務 (Execute a coding task via OpenCode). 可以自動生成、修改或檢查程式碼。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_description": {
                                "type": "string",
                                "description": "任務的詳細描述，例如「建立一個新的 Flutter widget」",
                            },
                            "project_path": {
                                "type": "string",
                                "description": "專案路徑，預設 ./mobile_app",
                            },
                        },
                        "required": ["task_description"],
                    },
                },
            },
        ]

    async def execute(self, tool_name: str, **kwargs) -> dict:
        if tool_name == "opencode_execute":
            return await self._tool.execute(
                task_description=kwargs["task_description"],
                project_path=kwargs.get("project_path", "./mobile_app"),
            )
        return {"error": f"Unknown opencode tool: {tool_name}"}
