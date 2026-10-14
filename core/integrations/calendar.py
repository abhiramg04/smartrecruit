"""
Modular Calendar & Scheduling Integration Service for SmartRecruit.
"""
from abc import ABC, abstractmethod
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict

class BaseCalendarProvider(ABC):
    @abstractmethod
    def generate_invite(self, title: str, description: str, start_time: datetime, duration_minutes: int = 60, location: str = "") -> Dict[str, str]:
        pass

class ICSCalendarProvider(BaseCalendarProvider):
    """Standard iCalendar (.ics) and Google Calendar web link provider."""
    def generate_invite(self, title: str, description: str, start_time: datetime, duration_minutes: int = 60, location: str = "") -> Dict[str, str]:
        end_time = start_time + timedelta(minutes=duration_minutes)
        start_str = start_time.strftime("%Y%m%dT%H%M%SZ")
        end_str = end_time.strftime("%Y%m%dT%H%M%SZ")

        ics_content = (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "PRODID:-//SmartRecruit//Recruitment Platform//EN\r\n"
            "BEGIN:VEVENT\r\n"
            f"SUMMARY:{title}\r\n"
            f"DESCRIPTION:{description}\r\n"
            f"LOCATION:{location}\r\n"
            f"DTSTART:{start_str}\r\n"
            f"DTEND:{end_str}\r\n"
            "STATUS:CONFIRMED\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )

        gcal_params = {
            'action': 'TEMPLATE',
            'text': title,
            'details': description,
            'location': location,
            'dates': f"{start_str}/{end_str}"
        }
        gcal_url = f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(gcal_params)}"

        return {
            'ics_content': ics_content,
            'google_calendar_url': gcal_url,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat()
        }


def get_calendar_provider() -> BaseCalendarProvider:
    return ICSCalendarProvider()


class CalendarService:
    @staticmethod
    def generate_ics_invite(title: str, description: str, start_time: datetime, duration_minutes: int = 60, location: str = "") -> str:
        provider = get_calendar_provider()
        res = provider.generate_invite(title, description, start_time, duration_minutes, location)
        return res['ics_content']

    @staticmethod
    def get_event_links(title: str, description: str, start_time: datetime, duration_minutes: int = 60, location: str = "") -> Dict[str, str]:
        provider = get_calendar_provider()
        return provider.generate_invite(title, description, start_time, duration_minutes, location)
