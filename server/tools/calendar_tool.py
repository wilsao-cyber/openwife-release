import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from config import CalendarConfig
from auth.google_calendar_oauth import GoogleCalendarAuth

logger = logging.getLogger(__name__)


class CalendarTool:
    def __init__(self, config: CalendarConfig):
        self.config = config
        self.credentials_path = config.credentials_path
        self.token_path = config.token_path
        self._calendar_service = None

    async def initialize(self):
        self._calendar_service = GoogleCalendarAuth(
            self.credentials_path, self.token_path
        )
        await self._calendar_service.authenticate()
        logger.info("Calendar tool initialized")

    async def view_events(
        self,
        days_ahead: int = 7,
        calendar_id: str = "primary",
    ) -> dict:
        try:
            now = datetime.utcnow().isoformat() + "Z"
            end = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"

            events_result = await asyncio.to_thread(
                self._calendar_service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=now,
                    timeMax=end,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute
            )

            events = events_result.get("items", [])
            formatted_events = []
            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date"))
                formatted_events.append(
                    {
                        "id": event["id"],
                        "summary": event.get("summary", "No title"),
                        "start": start,
                        "end": event["end"].get("dateTime", event["end"].get("date")),
                        "location": event.get("location", ""),
                        "description": event.get("description", ""),
                    }
                )

            return {"events": formatted_events, "total": len(formatted_events)}
        except Exception as e:
            logger.error(f"View events failed: {e}")
            return {"error": str(e)}

    async def create(
        self,
        title: str,
        start_time: str,
        end_time: Optional[str] = None,
        description: str = "",
        location: str = "",
        calendar_id: str = "primary",
        reminders: bool = True,
    ) -> dict:
        try:
            if end_time is None:
                end_dt = datetime.fromisoformat(start_time) + timedelta(hours=1)
                end_time = end_dt.isoformat()

            event = {
                "summary": title,
                "location": location,
                "description": description,
                "start": {"dateTime": start_time, "timeZone": self.config.timezone},
                "end": {"dateTime": end_time, "timeZone": self.config.timezone},
            }

            if reminders:
                event["reminders"] = {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 30},
                        {"method": "popup", "minutes": 10},
                    ],
                }

            created_event = await asyncio.to_thread(
                self._calendar_service.events()
                .insert(calendarId=calendar_id, body=event)
                .execute
            )

            return {
                "success": True,
                "event_id": created_event["id"],
                "link": created_event.get("htmlLink", ""),
            }
        except Exception as e:
            logger.error(f"Create event failed: {e}")
            return {"error": str(e)}

    async def update(
        self,
        event_id: str,
        title: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        description: Optional[str] = None,
        calendar_id: str = "primary",
    ) -> dict:
        try:
            event = await asyncio.to_thread(
                self._calendar_service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute
            )

            if title:
                event["summary"] = title
            if start_time:
                event["start"] = {"dateTime": start_time, "timeZone": self.config.timezone}
            if end_time:
                event["end"] = {"dateTime": end_time, "timeZone": self.config.timezone}
            if description:
                event["description"] = description

            updated_event = await asyncio.to_thread(
                self._calendar_service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=event)
                .execute
            )

            return {"success": True, "event_id": updated_event["id"]}
        except Exception as e:
            logger.error(f"Update event failed: {e}")
            return {"error": str(e)}

    async def delete(self, event_id: str, calendar_id: str = "primary") -> dict:
        try:
            await asyncio.to_thread(
                self._calendar_service.events()
                .delete(calendarId=calendar_id, eventId=event_id)
                .execute
            )
            return {"success": True, "event_id": event_id}
        except Exception as e:
            logger.error(f"Delete event failed: {e}")
            return {"error": str(e)}

    async def find_free_time(
        self,
        duration_minutes: int = 60,
        days_ahead: int = 3,
        calendar_id: str = "primary",
    ) -> dict:
        try:
            now = datetime.utcnow()
            end = now + timedelta(days=days_ahead)

            events_result = await asyncio.to_thread(
                self._calendar_service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=now.isoformat() + "Z",
                    timeMax=end.isoformat() + "Z",
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute
            )

            events = events_result.get("items", [])
            duration = timedelta(minutes=duration_minutes)

            current = now.replace(minute=0, second=0, microsecond=0) + timedelta(
                hours=1
            )
            while current < end:
                slot_end = current + duration
                conflict = False

                for event in events:
                    event_start = datetime.fromisoformat(
                        event["start"]
                        .get("dateTime", event["start"].get("date"))
                        .replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    event_end = datetime.fromisoformat(
                        event["end"]
                        .get("dateTime", event["end"].get("date"))
                        .replace("Z", "+00:00")
                    ).replace(tzinfo=None)

                    if current < event_end and slot_end > event_start:
                        conflict = True
                        current = event_end
                        break

                if not conflict:
                    return {
                        "success": True,
                        "available_slot": {
                            "start": current.isoformat(),
                            "end": slot_end.isoformat(),
                        },
                    }

                current += timedelta(minutes=30)

            return {"success": False, "message": "No free time slots found"}
        except Exception as e:
            logger.error(f"Find free time failed: {e}")
            return {"error": str(e)}
