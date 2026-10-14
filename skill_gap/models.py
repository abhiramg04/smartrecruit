from django.db import models
from candidates.models import CandidateProfile
from jobs.models import Job


class SkillGapReport(models.Model):
    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name='skill_gap_reports'
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='skill_gap_reports'
    )

    # Skill comparison results
    matched_skills         = models.JSONField(default=list, blank=True)
    missing_skills         = models.JSONField(default=list, blank=True)
    extra_skills           = models.JSONField(default=list, blank=True)  # Candidate has but job doesn't require
    match_percentage       = models.FloatField(default=0.0)

    # AI Generated outputs (Groq)
    recommended_courses    = models.JSONField(default=list, blank=True)
    recommended_certs      = models.JSONField(default=list, blank=True)
    learning_path          = models.JSONField(default=list, blank=True)  # Ordered list of steps
    estimated_hours        = models.IntegerField(default=0)
    ai_summary             = models.TextField(blank=True, null=True)

    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('candidate', 'job')
        ordering = ['-generated_at']

    def __str__(self):
        return f"Gap: {self.candidate.user.email} vs {self.job.title} ({self.match_percentage:.1f}%)"


class AssessmentTest(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='assessments')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    duration_minutes = models.IntegerField(default=30)
    passing_score = models.FloatField(default=70.0)
    questions = models.JSONField(default=list, help_text="List of questions: [{'id': 1, 'question': '...', 'options': [...], 'correct_answer': 0}]")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.job.title})"


class CandidateAssessment(models.Model):
    STATUS_CHOICES = (
        ('ASSIGNED', 'Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
    )
    test = models.ForeignKey(AssessmentTest, on_delete=models.CASCADE, related_name='candidate_results')
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='assessments')
    application = models.ForeignKey('applications.Application', on_delete=models.CASCADE, related_name='assessments', null=True, blank=True)
    score = models.FloatField(default=0.0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ASSIGNED')
    answers = models.JSONField(default=dict, blank=True)
    passed = models.BooleanField(default=False)
    assigned_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-assigned_at']

    def __str__(self):
        return f"{self.candidate.user.get_full_name() or self.candidate.user.email} - {self.test.title} ({self.score}%)"


