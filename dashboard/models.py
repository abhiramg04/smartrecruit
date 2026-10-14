from django.db import models
from django.conf import settings

class Notification(models.Model):
    # Notification type constants
    # Candidate-facing
    APPLICATION_SUBMITTED = 'APPLICATION_SUBMITTED'
    STATUS_CHANGED = 'STATUS_CHANGED'
    SHORTLISTED = 'SHORTLISTED'
    ASSESSMENT_ASSIGNED = 'ASSESSMENT_ASSIGNED'
    INTERVIEW_SCHEDULED = 'INTERVIEW_SCHEDULED'
    INTERVIEW_CHANGED = 'INTERVIEW_CHANGED'
    SELECTED = 'SELECTED'
    REJECTED = 'REJECTED'
    # Recruiter-facing
    NEW_APPLICATION = 'NEW_APPLICATION'
    SCREENING_COMPLETED = 'SCREENING_COMPLETED'
    ASSESSMENT_COMPLETED = 'ASSESSMENT_COMPLETED'
    INTERVIEW_REMINDER = 'INTERVIEW_REMINDER'
    INTERVIEW_COMPLETED = 'INTERVIEW_COMPLETED'
    # Admin
    SYSTEM_EVENT = 'SYSTEM_EVENT'

    NOTIFICATION_TYPE_CHOICES = [
        (APPLICATION_SUBMITTED, 'Application Submitted'),
        (STATUS_CHANGED, 'Status Changed'),
        (SHORTLISTED, 'Shortlisted'),
        (ASSESSMENT_ASSIGNED, 'Assessment Assigned'),
        (INTERVIEW_SCHEDULED, 'Interview Scheduled'),
        (INTERVIEW_CHANGED, 'Interview Changed'),
        (SELECTED, 'Selected'),
        (REJECTED, 'Rejected'),
        (NEW_APPLICATION, 'New Application'),
        (SCREENING_COMPLETED, 'Screening Completed'),
        (ASSESSMENT_COMPLETED, 'Assessment Completed'),
        (INTERVIEW_REMINDER, 'Interview Reminder'),
        (INTERVIEW_COMPLETED, 'Interview Completed'),
        (SYSTEM_EVENT, 'System Event'),
    ]

    ICON_MAP = {
        APPLICATION_SUBMITTED: 'fa-paper-plane',
        STATUS_CHANGED: 'fa-sync',
        SHORTLISTED: 'fa-star',
        ASSESSMENT_ASSIGNED: 'fa-tasks',
        INTERVIEW_SCHEDULED: 'fa-calendar-check',
        INTERVIEW_CHANGED: 'fa-calendar-alt',
        SELECTED: 'fa-trophy',
        REJECTED: 'fa-times-circle',
        NEW_APPLICATION: 'fa-user-plus',
        SCREENING_COMPLETED: 'fa-robot',
        ASSESSMENT_COMPLETED: 'fa-check-square',
        INTERVIEW_REMINDER: 'fa-bell',
        INTERVIEW_COMPLETED: 'fa-flag-checkered',
        SYSTEM_EVENT: 'fa-shield-alt',
    }

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=40, choices=NOTIFICATION_TYPE_CHOICES, default=STATUS_CHANGED)
    title = models.CharField(max_length=120, blank=True, default='')
    message = models.CharField(max_length=512)
    target_url = models.CharField(max_length=255, blank=True, null=True, help_text="Optional link for click-through")
    is_read = models.BooleanField(default=False, db_index=True)
    email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.get_notification_type_display()}: {self.message[:50]}"

    def get_icon(self):
        return self.ICON_MAP.get(self.notification_type, 'fa-bell')

    @classmethod
    def unread_count(cls, user):
        return cls.objects.filter(user=user, is_read=False).count()

    @classmethod
    def mark_all_read(cls, user):
        return cls.objects.filter(user=user, is_read=False).update(is_read=True)

class SystemConfiguration(models.Model):
    site_name = models.CharField(max_length=255, default='SmartRecruit')
    support_email = models.EmailField(default='support@smartrecruit.com')
    maintenance_mode = models.BooleanField(default=False)
    allow_new_registrations = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "System Configuration"
        verbose_name_plural = "System Configuration"

    def __str__(self):
        return "System Configuration"

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj

class AIConfiguration(models.Model):
    groq_api_key = models.CharField(max_length=255, blank=True, null=True, help_text="Optional. Overrides the GROQ_API_KEY environment variable if set.")
    default_model = models.CharField(max_length=100, default='openai/gpt-oss-120b', help_text="Model used for complex tasks (e.g. analysis, matching).")
    fast_model = models.CharField(max_length=100, default='openai/gpt-oss-120b', help_text="Model used for fast tasks (e.g. simple generation).")
    temperature = models.FloatField(default=0.2, help_text="Creativity level of the AI (0.0 to 1.0).")
    max_tokens = models.IntegerField(default=2048, help_text="Maximum tokens to generate.")
    
    # Prompt Templates
    resume_parser_prompt = models.TextField(default="Extract candidate skills, experience, education, projects, and contact info into structured JSON.", blank=True)
    ranking_prompt = models.TextField(default="Evaluate candidate match percentage, strengths, weaknesses, and suitability verdict for the job position.", blank=True)

    # Feature Toggles
    enable_resume_parsing = models.BooleanField(default=True)
    enable_ai_ranking = models.BooleanField(default=True)
    enable_interview_gen = models.BooleanField(default=True)

    # Configurable Scoring Weights (Must sum to 1.0)
    weight_skill_match = models.FloatField(default=0.40, help_text="Weight for Skills Match (e.g. 0.40)")
    weight_experience_match = models.FloatField(default=0.20, help_text="Weight for Experience Match (e.g. 0.20)")
    weight_education_match = models.FloatField(default=0.10, help_text="Weight for Education Match (e.g. 0.10)")
    weight_semantic_similarity = models.FloatField(default=0.20, help_text="Weight for overall Semantic Similarity (e.g. 0.20)")
    weight_ai_evaluation = models.FloatField(default=0.10, help_text="Weight for Groq AI Evaluation (e.g. 0.10)")

    class Meta:
        verbose_name = "AI Configuration"
        verbose_name_plural = "AI Configuration"

    def __str__(self):
        return "AI Configuration"

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj

class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=255)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} - {self.action} at {self.timestamp}"

    @classmethod
    def log_event(cls, user, action, description, ip_address=None):
        """Helper to create audit log records."""
        try:
            return cls.objects.create(
                user=user if getattr(user, 'is_authenticated', False) else None,
                action=action,
                description=description[:1000] if description else '',
                ip_address=ip_address
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to record audit log: {e}")
            return None


class SecurityConfiguration(models.Model):
    enforce_strong_passwords = models.BooleanField(default=True, help_text="Require complex passwords (min 8 chars, numbers, symbols)")
    session_timeout_minutes = models.IntegerField(default=60, help_text="Idle time in minutes before automatic logout")
    max_login_attempts = models.IntegerField(default=5, help_text="Number of failed attempts before account lockout")
    two_factor_auth_required = models.BooleanField(default=False, help_text="Force all admins to use Two-Factor Authentication")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Security Configuration"
        verbose_name_plural = "Security Configuration"

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj

    def __str__(self):
        return "Security Configuration"
