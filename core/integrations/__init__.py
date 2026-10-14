"""
core/integrations package for SmartRecruit.
Exposes clean service interfaces for all external integrations.
"""
from .email import EmailService, BaseEmailProvider, DjangoEmailProvider, get_email_provider
from .calendar import CalendarService, BaseCalendarProvider, ICSCalendarProvider, get_calendar_provider
from .meeting import MeetingService, BaseVideoMeetingProvider, JitsiMeetProvider, get_meeting_provider
from .verification import (
    BaseBackgroundCheckProvider, MockBackgroundCheckProvider, get_background_check_provider,
    BaseJobPortalProvider, MockJobPortalProvider, get_job_portal_provider,
    BaseSMSProvider, MockSMSProvider, get_sms_provider,
)

__all__ = [
    'EmailService', 'BaseEmailProvider', 'DjangoEmailProvider', 'get_email_provider',
    'CalendarService', 'BaseCalendarProvider', 'ICSCalendarProvider', 'get_calendar_provider',
    'MeetingService', 'BaseVideoMeetingProvider', 'JitsiMeetProvider', 'get_meeting_provider',
    'BaseBackgroundCheckProvider', 'get_background_check_provider',
    'BaseJobPortalProvider', 'get_job_portal_provider',
    'BaseSMSProvider', 'get_sms_provider',
]
