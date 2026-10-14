"""
NotificationService — Centralized notification dispatch for SmartRecruit.
Creates in-app notifications and optionally sends emails.
"""
import logging
from typing import Optional
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationService:
    """
    Central service for creating in-app notifications and optionally sending email notifications.
    This is the ONLY place that should create Notification records.
    """

    # --- Candidate-facing helpers ---

    @classmethod
    def notify_application_submitted(cls, application):
        candidate_user = application.candidate.user
        cls.notify_user(
            user=candidate_user,
            notification_type='APPLICATION_SUBMITTED',
            title='Application Submitted',
            message=f'Your application for "{application.job.title}" has been submitted successfully.',
            target_url=f'/applications/{application.pk}/',
            send_email=True,
        )
        cls._notify_recruiters_new_application(application)

    @classmethod
    def notify_status_changed(cls, application, old_status, new_status, notes=''):
        candidate_user = application.candidate.user
        cls.notify_user(
            user=candidate_user,
            notification_type='STATUS_CHANGED',
            title='Application Status Updated',
            message=f'Your application for "{application.job.title}" status has been updated to: {application.get_status_display()}.',
            target_url=f'/applications/{application.pk}/',
            send_email=True,
        )

    @classmethod
    def notify_shortlisted(cls, application):
        candidate_user = application.candidate.user
        cls.notify_user(
            user=candidate_user,
            notification_type='SHORTLISTED',
            title='🎉 You Have Been Shortlisted!',
            message=f'Congratulations! You have been shortlisted for "{application.job.title}". Our recruiter will reach out soon.',
            target_url=f'/applications/{application.pk}/',
            send_email=True,
        )

    @classmethod
    def notify_assessment_assigned(cls, application, assessment):
        candidate_user = application.candidate.user
        cls.notify_user(
            user=candidate_user,
            notification_type='ASSESSMENT_ASSIGNED',
            title='Assessment Assigned',
            message=f'An assessment "{assessment.title}" has been assigned for your application to "{application.job.title}".',
            target_url=f'/assessments/take/{assessment.pk}/',
            send_email=True,
        )

    @classmethod
    def notify_interview_scheduled(cls, application, interview_datetime_str, meeting_link=''):
        candidate_user = application.candidate.user
        msg = f'Your interview for "{application.job.title}" has been scheduled on {interview_datetime_str}.'
        if meeting_link:
            msg += f' Join link: {meeting_link}'
        cls.notify_user(
            user=candidate_user,
            notification_type='INTERVIEW_SCHEDULED',
            title='Interview Scheduled',
            message=msg,
            target_url=f'/interviews/schedule/{application.pk}/',
            send_email=True,
        )

    @classmethod
    def notify_interview_changed(cls, application, interview_datetime_str):
        candidate_user = application.candidate.user
        cls.notify_user(
            user=candidate_user,
            notification_type='INTERVIEW_CHANGED',
            title='Interview Rescheduled',
            message=f'Your interview for "{application.job.title}" has been rescheduled to {interview_datetime_str}.',
            target_url=f'/interviews/schedule/{application.pk}/',
            send_email=True,
        )

    @classmethod
    def notify_selected(cls, application):
        candidate_user = application.candidate.user
        cls.notify_user(
            user=candidate_user,
            notification_type='SELECTED',
            title='🎊 Offer Extended — Congratulations!',
            message=f'We are pleased to inform you that you have been selected for "{application.job.title}"! Please check your email for next steps.',
            target_url=f'/applications/{application.pk}/',
            send_email=True,
        )

    @classmethod
    def notify_rejected(cls, application, notes=''):
        candidate_user = application.candidate.user
        msg = f'Thank you for your interest in "{application.job.title}". After careful consideration, we are unable to move forward with your application at this time.'
        if notes:
            msg += f' Feedback: {notes}'
        cls.notify_user(
            user=candidate_user,
            notification_type='REJECTED',
            title='Application Update',
            message=msg,
            target_url=f'/applications/{application.pk}/',
            send_email=True,
        )

    # --- Recruiter-facing helpers ---

    @classmethod
    def _notify_recruiters_new_application(cls, application):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        recruiters = User.objects.filter(role='recruiter', is_active=True)
        for recruiter in recruiters:
            cls.notify_user(
                user=recruiter,
                notification_type='NEW_APPLICATION',
                title='New Application Received',
                message=f'{application.candidate.user.get_full_name() or application.candidate.user.username} applied for "{application.job.title}".',
                target_url=f'/applications/{application.pk}/',
                send_email=False,
            )

    @classmethod
    def notify_screening_completed(cls, application):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        recruiters = User.objects.filter(role='recruiter', is_active=True)
        for recruiter in recruiters:
            cls.notify_user(
                user=recruiter,
                notification_type='SCREENING_COMPLETED',
                title='AI Screening Completed',
                message=f'AI screening completed for {application.candidate.user.get_full_name() or application.candidate.user.username} — {application.job.title}.',
                target_url=f'/ranking/detail/{application.pk}/',
                send_email=False,
            )

    @classmethod
    def notify_assessment_completed(cls, application, assessment_result):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        recruiters = User.objects.filter(role='recruiter', is_active=True)
        for recruiter in recruiters:
            cls.notify_user(
                user=recruiter,
                notification_type='ASSESSMENT_COMPLETED',
                title='Assessment Submitted',
                message=f'{application.candidate.user.get_full_name() or application.candidate.user.username} completed an assessment for "{application.job.title}".',
                target_url=f'/assessments/result/{assessment_result.pk}/',
                send_email=False,
            )

    @classmethod
    def notify_interview_reminder(cls, recruiter_user, application, interview_datetime_str):
        cls.notify_user(
            user=recruiter_user,
            notification_type='INTERVIEW_REMINDER',
            title='Interview Reminder',
            message=f'Reminder: Interview with {application.candidate.user.get_full_name()} for "{application.job.title}" is scheduled at {interview_datetime_str}.',
            target_url=f'/interviews/schedule/{application.pk}/',
            send_email=True,
        )

    @classmethod
    def notify_interview_completed(cls, application):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        recruiters = User.objects.filter(role='recruiter', is_active=True)
        for recruiter in recruiters:
            cls.notify_user(
                user=recruiter,
                notification_type='INTERVIEW_COMPLETED',
                title='Interview Completed',
                message=f'Interview completed for {application.candidate.user.get_full_name() or application.candidate.user.username} — {application.job.title}. AI analysis is ready.',
                target_url=f'/interviews/summaries/',
                send_email=False,
            )

    # --- Admin helpers ---

    @classmethod
    def notify_admin_system_event(cls, message: str, target_url: str = ''):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admins = User.objects.filter(role='admin', is_active=True)
        for admin in admins:
            cls.notify_user(
                user=admin,
                notification_type='SYSTEM_EVENT',
                title='System Event',
                message=message,
                target_url=target_url or '/dashboard/admin/',
                send_email=True,
            )

    # --- Core dispatcher ---

    @classmethod
    def notify_user(
        cls,
        user,
        notification_type: str,
        message: str,
        title: str = '',
        target_url: Optional[str] = None,
        send_email: bool = True,
    ):
        """
        Core notification dispatcher.
        Creates DB notification and optionally sends email.
        """
        from dashboard.models import Notification
        from core.integrations.email import get_email_provider

        try:
            notif = Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                target_url=target_url,
                is_read=False,
                email_sent=False,
            )
        except Exception as e:
            logger.error(f"[NotificationService] Failed to create notification for {user}: {e}")
            return

        if send_email and user.email:
            try:
                provider = get_email_provider()
                subject = f"SmartRecruit — {title or 'Notification'}"
                text_body = f"{title}\n\n{message}\n\nVisit SmartRecruit: http://localhost:8000{target_url or '/'}"
                sent = provider.send_email(user.email, subject, text_body)
                if sent:
                    notif.email_sent = True
                    notif.save(update_fields=['email_sent'])
            except Exception as e:
                logger.warning(f"[NotificationService] Email dispatch failed for {user}: {e}")
