from django.db import models
from django.conf import settings
from jobs.models import Job
from applications.models import Application

class Assessment(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    duration_minutes = models.IntegerField(default=30)
    pass_percentage = models.FloatField(default=60.0)
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name='technical_assessments')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_assessments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class Question(models.Model):
    QUESTION_TYPES = (
        ('MCQ', 'Multiple Choice Question'),
        ('APTITUDE', 'Aptitude Question'),
        ('TECHNICAL', 'Technical Question'),
        ('CODING', 'Coding Challenge'),
    )

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='questions')
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='MCQ')
    text = models.TextField()
    marks = models.IntegerField(default=10)
    options = models.JSONField(default=list, blank=True, help_text="List of choices for MCQ")
    correct_answer = models.TextField(help_text="Correct option index or expected answer text")
    code_snippet = models.TextField(blank=True, null=True)
    expected_output = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.get_question_type_display()}] {self.text[:50]}"

class AssessmentAssignment(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
    )
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='assessment_assignments')
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    class Meta:
        unique_together = ('application', 'assessment')

    def __str__(self):
        return f"{self.assessment.title} assigned to {self.application.candidate.user.get_full_name()}"

class AssessmentResult(models.Model):
    application  = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='assessment_results')
    assessment   = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='results')
    score        = models.FloatField(default=0.0)
    total_score  = models.FloatField(default=0.0)
    final_score  = models.FloatField(default=0.0, help_text="Percentage 0-100")
    is_passed    = models.BooleanField(default=False)
    answers      = models.JSONField(default=dict)
    # Timing
    time_started   = models.DateTimeField(null=True, blank=True, help_text="When candidate started the assessment")
    time_submitted = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.IntegerField(default=0, help_text="Computed on submit: time_submitted - time_started")

    def __str__(self):
        return f"Result for {self.application.candidate.user.get_full_name()} - {self.final_score}%"

