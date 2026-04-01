from skills.base_skill import BaseSkill
from tools.calendar_tool import CalendarTool
from config import config


class CalendarSkill(BaseSkill):
    def __init__(self):
        self._tool = CalendarTool(config.calendar)

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "calendar_view",
                    "description": "查看未來的行程/日曆事件 (View upcoming calendar events).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days_ahead": {
                                "type": "integer",
                                "description": "查看未來幾天的行程，預設 7",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendar_create",
                    "description": "建立新的日曆事件 (Create a new calendar event). 需要提供標題和開始時間。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "事件標題"},
                            "start_time": {
                                "type": "string",
                                "description": "開始時間，ISO 8601 格式，例如 2026-04-01T14:00:00",
                            },
                            "end_time": {
                                "type": "string",
                                "description": "結束時間，ISO 8601 格式。如不提供，預設為開始時間後一小時",
                            },
                            "description": {
                                "type": "string",
                                "description": "事件描述",
                            },
                            "location": {"type": "string", "description": "事件地點"},
                        },
                        "required": ["title", "start_time"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendar_update",
                    "description": "更新現有的日曆事件 (Update an existing calendar event). 只需要提供要修改的欄位。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_id": {
                                "type": "string",
                                "description": "要更新的事件 ID",
                            },
                            "title": {"type": "string", "description": "新的事件標題"},
                            "start_time": {
                                "type": "string",
                                "description": "新的開始時間，ISO 8601 格式",
                            },
                            "end_time": {
                                "type": "string",
                                "description": "新的結束時間，ISO 8601 格式",
                            },
                            "description": {
                                "type": "string",
                                "description": "新的事件描述",
                            },
                        },
                        "required": ["event_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendar_delete",
                    "description": "刪除指定的日曆事件 (Delete a calendar event).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_id": {
                                "type": "string",
                                "description": "要刪除的事件 ID",
                            },
                        },
                        "required": ["event_id"],
                    },
                },
            },
        ]

    async def initialize(self):
        await self._tool.initialize()

    async def execute(self, tool_name: str, **kwargs) -> dict:
        dispatch = {
            "calendar_view": lambda: self._tool.view_events(
                days_ahead=kwargs.get("days_ahead", 7),
            ),
            "calendar_create": lambda: self._tool.create(
                title=kwargs["title"],
                start_time=kwargs["start_time"],
                end_time=kwargs.get("end_time"),
                description=kwargs.get("description", ""),
                location=kwargs.get("location", ""),
            ),
            "calendar_update": lambda: self._tool.update(
                event_id=kwargs["event_id"],
                title=kwargs.get("title"),
                start_time=kwargs.get("start_time"),
                end_time=kwargs.get("end_time"),
                description=kwargs.get("description"),
            ),
            "calendar_delete": lambda: self._tool.delete(
                event_id=kwargs["event_id"],
            ),
        }
        method = dispatch.get(tool_name)
        if not method:
            return {"error": f"Unknown calendar tool: {tool_name}"}
        return await method()
