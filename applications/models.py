from django.db import models
from candidates.models import CandidateProfile
from jobs.models import Job


class Application(models.Model):
    STATUS_CHOICES = (
        ('APPLIED',             'APPLIED'),
        ('UNDER_REVIEW',        'UNDER REVIEW'),
        ('SCREENING',           'UNDER REVIEW'),
        ('AI_SCREENED',         'AI SCREENED'),
        ('SHORTLISTED',         'SHORTLISTED'),
        ('ASSESSMENT',          'ASSESSMENT'),
        ('INTERVIEW',           'INTERVIEW SCHEDULED'),
        ('INTERVIEW_SCHEDULED', 'INTERVIEW SCHEDULED'),
        ('INTERVIEW_COMPLETED', 'INTERVIEW COMPLETED'),
        ('HR_ROUND',            'HR ROUND'),
        ('OFFER',               'SELECTED'),
        ('SELECTED',            'SELECTED'),
        ('HOLD',                'ON HOLD'),
        ('REJECTED',            'REJECTED'),
    )

    HIRING_DECISION_CHOICES = (
        ('PENDING', 'Pending'),
        ('SELECT',  'Select'),
        ('REJECT',  'Reject'),
        ('HOLD',    'Hold'),
    )

    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='APPLIED')
    hiring_decision = models.CharField(max_length=20, choices=HIRING_DECISION_CHOICES, default='PENDING')
    hiring_decision_notes = models.TextField(blank=True, null=True)
    hiring_decision_at = models.DateTimeField(blank=True, null=True)
    cover_letter = models.TextField(blank=True, null=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('candidate', 'job')
        ordering = ['-applied_at']

    def __str__(self):
        return f"{self.candidate.user.get_full_name()} → {self.job.title}"

class WorkflowLog(models.Model):
    application = models.ForeignKey(
        Application, 
        on_delete=models.CASCADE, 
        related_name='workflow_logs'
    )
    previous_status = models.CharField(max_length=20, choices=Application.STATUS_CHOICES, blank=True, null=True)
    new_status = models.CharField(max_length=20, choices=Application.STATUS_CHOICES)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.application.candidate.user.get_full_name()} status changed to {self.get_new_status_display()}"


class ApplicationAIScore(models.Model):
    """Stores the Phase 07 deterministic and Groq AI ranking data for an application."""
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='ai_score')
    
    overall_score = models.FloatField(default=0.0)
    skill_score = models.FloatField(default=0.0)
    experience_score = models.FloatField(default=0.0)
    education_score = models.FloatField(default=0.0)
    semantic_score = models.FloatField(default=0.0)
    ai_evaluation_score = models.FloatField(default=0.0)
    
    ai_recommendation = models.CharField(max_length=50, blank=True, null=True) # SUITABLE, MAYBE, REJECT
    ai_strengths = models.JSONField(default=list, blank=True)
    ai_missing_skills = models.JSONField(default=list, blank=True)
    ai_rationale = models.TextField(blank=True, null=True)
    
    scored_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-overall_score']
        
    def __str__(self):
        return f"AI Score {self.overall_score} for {self.application}"

