"""
Modular Video Meeting Integration Service for SmartRecruit.
"""
from abc import ABC, abstractmethod
import uuid
from typing import Dict, Any

class BaseVideoMeetingProvider(ABC):
    @abstractmethod
    def create_meeting(self, title: str, start_time_str: str) -> Dict[str, Any]:
        pass

class JitsiMeetProvider(BaseVideoMeetingProvider):
    """Free open-source video meeting link generator via Jitsi Meet."""
    def create_meeting(self, title: str, start_time_str: str) -> Dict[str, Any]:
        room_name = f"SmartRecruit-{uuid.uuid4().hex[:10]}"
        join_url = f"https://meet.jit.si/{room_name}"
        return {
            'provider': 'Jitsi Meet',
            'room_name': room_name,
            'join_url': join_url,
            'meeting_id': room_name
        }

class GoogleMeetLinkProvider(BaseVideoMeetingProvider):
    """Mock/Configurable Google Meet Link provider."""
    def create_meeting(self, title: str, start_time_str: str) -> Dict[str, Any]:
        meeting_code = f"smt-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}"
        return {
            'provider': 'Google Meet',
            'room_name': meeting_code,
            'join_url': f"https://meet.google.com/{meeting_code}",
            'meeting_id': meeting_code
        }

def get_meeting_provider() -> BaseVideoMeetingProvider:
    return JitsiMeetProvider()

class MeetingService:
    @staticmethod
    def create_interview_room(title: str, start_time_str: str = "") -> Dict[str, Any]:
        provider = get_meeting_provider()
        return provider.create_meeting(title, start_time_str)
