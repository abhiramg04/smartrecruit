"""
Modular Background Verification, Job Portal, and SMS Integration Services for SmartRecruit.
These are optional/modular integrations with abstract base classes and Null/Mock implementations.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


# ==========================================
# 2. BACKGROUND VERIFICATION SERVICE
# ==========================================

class BaseBackgroundCheckProvider(ABC):
    @abstractmethod
    def initiate_check(self, candidate_email: str, candidate_name: str, job_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_check_status(self, check_id: str) -> Dict[str, Any]:
        pass


class MockBackgroundCheckProvider(BaseBackgroundCheckProvider):
    """Null/mock provider — logs call but takes no real action. Replace with SpringVerify, Checkr, etc."""
    def initiate_check(self, candidate_email: str, candidate_name: str, job_id: str) -> Dict[str, Any]:
        logger.info(f"[MOCK] Background check initiated for {candidate_name} ({candidate_email}) for job {job_id}")
        return {'check_id': f"MOCK-BGC-{candidate_email}", 'status': 'PENDING', 'provider': 'Mock'}

    def get_check_status(self, check_id: str) -> Dict[str, Any]:
        logger.info(f"[MOCK] Background check status queried for {check_id}")
        return {'check_id': check_id, 'status': 'PENDING', 'result': None}


def get_background_check_provider() -> BaseBackgroundCheckProvider:
    """Factory function — swap to a real provider via settings (e.g. BACKGROUND_CHECK_PROVIDER='checkr')."""
    return MockBackgroundCheckProvider()


# ==========================================
# 3. JOB PORTAL / API INTEGRATION
# ==========================================

class BaseJobPortalProvider(ABC):
    @abstractmethod
    def post_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def pull_applications(self, job_id: str) -> list:
        pass


class MockJobPortalProvider(BaseJobPortalProvider):
    """Null/mock provider — logs call. Replace with LinkedIn, Naukri, Indeed APIs."""
    def post_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[MOCK] Job posting sent to portal: {job_data.get('title', 'N/A')}")
        return {'portal_job_id': 'MOCK-JOB-001', 'status': 'posted', 'url': '#'}

    def pull_applications(self, job_id: str) -> list:
        logger.info(f"[MOCK] Pulling applications from portal for job {job_id}")
        return []


def get_job_portal_provider() -> BaseJobPortalProvider:
    return MockJobPortalProvider()


# ==========================================
# 4. SMS / COMMUNICATION API
# ==========================================

class BaseSMSProvider(ABC):
    @abstractmethod
    def send_sms(self, phone_number: str, message: str) -> bool:
        pass


class MockSMSProvider(BaseSMSProvider):
    """Null/mock provider — logs call. Replace with Twilio, MSG91, etc."""
    def send_sms(self, phone_number: str, message: str) -> bool:
        logger.info(f"[MOCK] SMS to {phone_number}: {message[:60]}...")
        return True


def get_sms_provider() -> BaseSMSProvider:
    return MockSMSProvider()
