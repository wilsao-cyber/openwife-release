import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from skills.base_skill import BaseSkill
from tools.calendar_tool import CalendarTool
from config import config

_tz = ZoneInfo(config.calendar.timezone)


def _parse_time(value: str) -> str:
    """Convert natural language time to ISO 8601.

    Handles:
    - Already ISO: "2026-04-08T10:30:00" → unchanged
    - Date + time: "2026-04-08 10:30" → "2026-04-08T10:30:00"
    - Relative: "明天下午三點" / "tomorrow 3pm" → computed datetime
    - Day of week: "下週一早上九點" → next Monday 9am
    """
    if not value or not isinstance(value, str):
        return value

    # Already ISO format
    if "T" in value and len(value) >= 19:
        return value

    now = datetime.now(tz=_tz)
    tz_offset = now.strftime("%z")
    tz_offset = tz_offset[:3] + ":" + tz_offset[3:]  # "+0800" -> "+08:00"

    # Try common formats first
    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M"]:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S") + tz_offset
        except ValueError:
            pass

    # Try date only
    for fmt in ["%Y-%m-%d", "%Y/%m/%d"]:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%Y-%m-%dT09:00:00") + tz_offset
        except ValueError:
            pass

    v = value.lower().strip()

    # Chinese relative time parsing
    day_offset = 0
    hour = 9  # default 9am
    minute = 0

    # Day references
    if "明天" in v or "tomorrow" in v:
        day_offset = 1
    elif "後天" in v or "day after" in v:
        day_offset = 2
    elif "今天" in v or "today" in v:
        day_offset = 0
    elif "下週" in v or "next week" in v:
        day_offset = 7

    # Day of week (Chinese)
    weekdays = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    for char, wd in weekdays.items():
        if f"週{char}" in v or f"星期{char}" in v:
            days_ahead = (wd - now.weekday()) % 7
            if days_ahead == 0 and day_offset == 0:
                days_ahead = 7  # next week
            day_offset = days_ahead
            break

    # Time references (Chinese)
    if "早上" in v or "上午" in v:
        hour = 9
    elif "中午" in v:
        hour = 12
    elif "下午" in v or "晚上" in v:
        hour = 14
        # Check for specific hour
        for h in range(1, 13):
            if f"{h}點" in v or f"{h}点" in v:
                hour = h + 12 if h < 12 else 12
                break
    elif "晚上" in v:
        hour = 19
    elif "凌晨" in v:
        hour = 0

    # Extract specific hour/minute
    import re

    time_match = re.search(r"(\d{1,2})[點点](\d{1,2})?[分]?", v)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
    else:
        # English time: "3pm", "10:30"
        time_match = re.search(r"(\d{1,2}):(\d{2})", v)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
        else:
            time_match = re.search(r"(\d{1,2})\s*(am|pm)", v)
            if time_match:
                hour = int(time_match.group(1))
                if time_match.group(2) == "pm" and hour < 12:
                    hour += 12
                elif time_match.group(2) == "am" and hour == 12:
                    hour = 0

    target = now + timedelta(days=day_offset)
    target = target.replace(hour=hour, minute=minute, second=0)
    return target.strftime("%Y-%m-%dT%H:%M:%S") + tz_offset


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
                    "description": "建立新的日曆事件 (Create a new calendar event). 需要提供標題和開始時間。時間可以用自然語言（如「明天下午三點」）或 ISO 8601 格式。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "事件標題"},
                            "start_time": {
                                "type": "string",
                                "description": "開始時間，ISO 8601 格式或自然語言（如「明天下午三點」）",
                            },
                            "end_time": {
                                "type": "string",
                                "description": "結束時間，ISO 8601 格式或自然語言。如不提供，預設為開始時間後一小時",
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
                                "description": "新的開始時間，ISO 8601 格式或自然語言",
                            },
                            "end_time": {
                                "type": "string",
                                "description": "新的結束時間，ISO 8601 格式或自然語言",
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
        # Server-side time parsing for calendar operations
        if "start_time" in kwargs and kwargs.get("start_time"):
            kwargs["start_time"] = _parse_time(kwargs["start_time"])
        if "end_time" in kwargs and kwargs.get("end_time"):
            kwargs["end_time"] = _parse_time(kwargs["end_time"])

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
