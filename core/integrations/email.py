"""
Modular External Integration Interfaces & Providers for SmartRecruit.
"""
from abc import ABC, abstractmethod
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


# ==========================================
# 1. EMAIL SERVICE INTEGRATION
# ==========================================

class BaseEmailProvider(ABC):
    @abstractmethod
    def send_email(self, recipient_email: str, subject: str, message: str, html_message: Optional[str] = None) -> bool:
        pass


class DjangoEmailProvider(BaseEmailProvider):
    """Default SMTP Email Provider using Django's built-in email framework."""
    def send_email(self, recipient_email: str, subject: str, message: str, html_message: Optional[str] = None) -> bool:
        try:
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@smartrecruit.com')
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[recipient_email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Email sent successfully to {recipient_email} via DjangoEmailProvider")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {recipient_email}: {e}")
            return False


def get_email_provider() -> BaseEmailProvider:
    """Factory function returning configured Email Provider."""
    return DjangoEmailProvider()


class EmailService:
    @staticmethod
    def send_notification_email(recipient_email: str, subject: str, message: str, html_message: Optional[str] = None) -> bool:
        provider = get_email_provider()
        return provider.send_email(recipient_email, subject, message, html_message)
