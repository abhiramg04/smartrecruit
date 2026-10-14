"""
WorkflowEngine — Backend-controlled recruitment lifecycle state machine for SmartRecruit.

AUTOMATION SAFETY CONTRACT:
  - AI models may ONLY suggest/recommend actions (e.g., recommend shortlisting a candidate).
  - Actual state transitions MUST be initiated by explicit recruiter or admin actions through this engine.
  - This engine will NEVER call LLMs or AI directly.
  - Decisions that affect candidates (SHORTLIST / REJECT / SELECT / HOLD) require a human actor (recruiter_user).
"""
import logging
from typing import Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Valid state transition graph for the recruitment lifecycle
# ---------------------------------------------------------------------------
ALLOWED_TRANSITIONS = {
    # Candidate submits application
    'APPLIED':              ['SCREENING', 'UNDER_REVIEW', 'SHORTLISTED', 'REJECTED'],
    # System runs AI screening
    'UNDER_REVIEW':         ['SCREENING', 'AI_SCREENED', 'REJECTED'],
    'SCREENING':            ['AI_SCREENED', 'REJECTED'],
    'AI_SCREENED':          ['SHORTLISTED', 'HOLD', 'REJECTED'],
    # Recruiter decision gate
    'SHORTLISTED':          ['ASSESSMENT', 'INTERVIEW_SCHEDULED', 'HOLD', 'REJECTED'],
    'HOLD':                 ['SHORTLISTED', 'REJECTED'],
    # Assessment path
    'ASSESSMENT':           ['INTERVIEW_SCHEDULED', 'HOLD', 'REJECTED'],
    # Interview path
    'INTERVIEW_SCHEDULED':  ['INTERVIEW_COMPLETED', 'INTERVIEW_SCHEDULED', 'REJECTED'],
    'INTERVIEW_COMPLETED':  ['HR_ROUND', 'SELECTED', 'OFFER', 'HOLD', 'REJECTED'],
    'HR_ROUND':             ['SELECTED', 'OFFER', 'HOLD', 'REJECTED'],
    # Final states
    'OFFER':                ['SELECTED', 'REJECTED'],
    'SELECTED':             [],
    'REJECTED':             [],
    # Legacy aliases
    'INTERVIEW':            ['INTERVIEW_COMPLETED', 'REJECTED'],
}

# States that REQUIRE human recruiter/admin authorization (cannot be set by automated code)
PROTECTED_STATES = {'SELECTED', 'OFFER', 'REJECTED', 'HOLD'}


class WorkflowError(Exception):
    """Raised when an illegal workflow transition is attempted."""
    pass


class WorkflowEngine:
    """
    Backend workflow engine controlling the recruitment lifecycle.
    All state transitions are validated, logged, and trigger notifications.
    """

    def __init__(self, application):
        self.application = application

    def _validate_transition(self, new_status: str, recruiter_user=None) -> bool:
        """Validate that the transition is legal from the current state."""
        current = self.application.status
        if current == new_status:
            return True
        allowed = ALLOWED_TRANSITIONS.get(current, [])
        if new_status not in allowed:
            raise WorkflowError(
                f"Illegal transition: Cannot move from '{current}' to '{new_status}'. "
                f"Allowed: {allowed}"
            )
        if new_status in PROTECTED_STATES and recruiter_user is None:
            raise WorkflowError(
                f"Transition to '{new_status}' requires explicit recruiter/admin authorization. "
                f"Pass recruiter_user= to this method."
            )
        return True

    def _do_transition(self, new_status: str, notes: str = '', recruiter_user=None):
        """Execute a validated state transition and log it."""
        from applications.models import WorkflowLog
        old_status = self.application.status
        self._validate_transition(new_status, recruiter_user)

        if old_status == new_status:
            logger.info(f"[WorkflowEngine] Application {self.application.pk} already in state '{new_status}'. No state change.")
            return old_status, new_status

        self.application.status = new_status
        self.application.updated_at = timezone.now()
        self.application.save(update_fields=['status', 'updated_at'])

        WorkflowLog.objects.create(
            application=self.application,
            previous_status=old_status,
            new_status=new_status,
            notes=notes or f"Status changed from {old_status} to {new_status}",
        )
        logger.info(
            f"[WorkflowEngine] Application {self.application.pk} transitioned "
            f"{old_status} → {new_status}" + (f" by {recruiter_user}" if recruiter_user else "")
        )
        return old_status, new_status

    # -----------------------------------------------------------------------
    # AUTOMATED TRANSITIONS (no recruiter_user required)
    # -----------------------------------------------------------------------

    def start_screening(self, notes=''):
        """System-initiated: Application moved to AI screening."""
        old, new = self._do_transition('SCREENING', notes or 'AI resume screening started.')
        return self.application

    def complete_ai_screening(self, notes=''):
        """System-initiated: AI screening completed, awaiting recruiter review."""
        old, new = self._do_transition('AI_SCREENED', notes or 'AI screening complete. Pending recruiter review.')
        from dashboard.services.notification_service import NotificationService
        NotificationService.notify_screening_completed(self.application)
        NotificationService.notify_status_changed(self.application, old, new)
        return self.application

    # -----------------------------------------------------------------------
    # RECRUITER-PROTECTED TRANSITIONS (recruiter_user required)
    # -----------------------------------------------------------------------

    def shortlist_candidate(self, recruiter_user, notes=''):
        """Recruiter action: Shortlist a candidate."""
        old, new = self._do_transition('SHORTLISTED', notes, recruiter_user)
        from dashboard.services.notification_service import NotificationService
        NotificationService.notify_shortlisted(self.application)
        return self.application

    def hold_candidate(self, recruiter_user, notes=''):
        """Recruiter action: Put application on hold."""
        old, new = self._do_transition('HOLD', notes, recruiter_user)
        from dashboard.services.notification_service import NotificationService
        NotificationService.notify_status_changed(self.application, old, new, notes)
        return self.application

    def reject_candidate(self, recruiter_user, notes=''):
        """
        Recruiter action: Reject a candidate.
        PROTECTED — requires human authorization.
        AI may NEVER call this method directly.
        """
        old, new = self._do_transition('REJECTED', notes, recruiter_user)
        # Also update the hiring_decision field
        self.application.hiring_decision = 'REJECT'
        self.application.hiring_decision_notes = notes
        self.application.hiring_decision_at = timezone.now()
        self.application.save(update_fields=['hiring_decision', 'hiring_decision_notes', 'hiring_decision_at'])
        from dashboard.services.notification_service import NotificationService
        NotificationService.notify_rejected(self.application, notes)
        return self.application

    def assign_assessment(self, recruiter_user, assessment, notes=''):
        """Recruiter action: Assign an assessment to a shortlisted candidate."""
        self._do_transition('ASSESSMENT', notes or 'Assessment assigned.', recruiter_user)
        from dashboard.services.notification_service import NotificationService
        NotificationService.notify_assessment_assigned(self.application, assessment)
        return self.application

    def schedule_interview(self, recruiter_user, interview_datetime_str, meeting_link='', notes=''):
        """Recruiter action: Schedule an interview and generate meeting/calendar links."""
        old_status = self.application.status
        if old_status == 'INTERVIEW_SCHEDULED':
            # Rescheduling
            self._do_transition('INTERVIEW_SCHEDULED', notes or f'Interview rescheduled to {interview_datetime_str}.', recruiter_user)
            from dashboard.services.notification_service import NotificationService
            NotificationService.notify_interview_changed(self.application, interview_datetime_str)
        else:
            self._do_transition('INTERVIEW_SCHEDULED', notes or f'Interview scheduled for {interview_datetime_str}.', recruiter_user)
            from dashboard.services.notification_service import NotificationService
            NotificationService.notify_interview_scheduled(self.application, interview_datetime_str, meeting_link)
        return self.application

    def complete_interview(self, notes=''):
        """System or Recruiter: Mark interview as completed and trigger AI analysis notification."""
        old, new = self._do_transition('INTERVIEW_COMPLETED', notes or 'Interview session completed.')
        from dashboard.services.notification_service import NotificationService
        NotificationService.notify_interview_completed(self.application)
        return self.application

    def make_hiring_decision(self, recruiter_user, decision: str, notes=''):
        """
        Recruiter action: Final hiring decision — SELECT, REJECT, or HOLD.
        PROTECTED — requires human authorization.
        AI may NEVER call this method directly.
        """
        decision = decision.upper()
        if decision not in ('SELECT', 'REJECT', 'HOLD'):
            raise WorkflowError(f"Invalid decision: '{decision}'. Must be SELECT, REJECT, or HOLD.")

        if decision == 'SELECT':
            self._do_transition('SELECTED', notes, recruiter_user)
            self.application.hiring_decision = 'SELECT'
            from dashboard.services.notification_service import NotificationService
            NotificationService.notify_selected(self.application)
        elif decision == 'REJECT':
            self._do_transition('REJECTED', notes, recruiter_user)
            self.application.hiring_decision = 'REJECT'
            from dashboard.services.notification_service import NotificationService
            NotificationService.notify_rejected(self.application, notes)
        elif decision == 'HOLD':
            self._do_transition('HOLD', notes, recruiter_user)
            self.application.hiring_decision = 'HOLD'
            from dashboard.services.notification_service import NotificationService
            NotificationService.notify_status_changed(self.application, self.application.status, 'HOLD')

        self.application.hiring_decision_notes = notes
        self.application.hiring_decision_at = timezone.now()
        self.application.save(update_fields=['hiring_decision', 'hiring_decision_notes', 'hiring_decision_at'])
        return self.application

    # -----------------------------------------------------------------------
    # ASSESSMENT COMPLETION (System)
    # -----------------------------------------------------------------------

    def mark_assessment_completed(self, assessment_result, notes=''):
        """System: Mark assessment completed after candidate submission."""
        from dashboard.services.notification_service import NotificationService
        NotificationService.notify_assessment_completed(self.application, assessment_result)
        return self.application

    # -----------------------------------------------------------------------
    # UTILITY
    # -----------------------------------------------------------------------

    def get_allowed_transitions(self):
        return ALLOWED_TRANSITIONS.get(self.application.status, [])

    def get_workflow_history(self):
        return self.application.workflow_logs.all()
