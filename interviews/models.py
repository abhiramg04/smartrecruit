"""
Interview models — Phase 08.

InterviewQuestionSet  → config + stores generated question set per application
InterviewQuestion     → individual editable question linked to a set
InterviewSummary      → AI intelligence report (transcript + Groq analysis)
InterviewSchedule     → scheduling metadata
"""

from django.db import models
from applications.models import Application


# ── Module 5: Interview Question Generator ────────────────────────────────────

CATEGORY_CHOICES = [
    ('TECHNICAL',     'Technical'),
    ('RESUME',        'Resume-Based'),
    ('SCENARIO',      'Scenario'),
    ('PROBLEM',       'Problem-Solving'),
    ('BEHAVIORAL',    'Behavioral'),
    ('HR',            'HR'),
]

DIFFICULTY_CHOICES = [
    ('EASY',   'Easy'),
    ('MEDIUM', 'Medium'),
    ('HARD',   'Hard'),
]

EXPERIENCE_CHOICES = [
    ('JUNIOR',  'Junior (0-2 yrs)'),
    ('MID',     'Mid-level (2-5 yrs)'),
    ('SENIOR',  'Senior (5+ yrs)'),
]


class InterviewQuestionSet(models.Model):
    """
    Configuration + storage for an AI-generated interview question bank
    for a specific application.
    """
    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        related_name='interview_questions'
    )

    # Generation config (persisted so recruiter can regenerate with same settings)
    difficulty      = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='MEDIUM')
    num_questions   = models.IntegerField(default=15)
    experience_level = models.CharField(max_length=10, choices=EXPERIENCE_CHOICES, default='MID')
    # Comma-separated list of selected categories, e.g. "TECHNICAL,BEHAVIORAL,HR"
    selected_categories = models.CharField(max_length=200, default='TECHNICAL,BEHAVIORAL,HR')

    # Legacy flat JSON (kept for backward-compatibility; new code uses InterviewQuestion rows)
    questions_data  = models.JSONField(default=dict, blank=True)

    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"Questions for {self.application.candidate.user.get_full_name()} "
            f"({self.application.job.title})"
        )

    def get_selected_categories(self):
        return [c.strip() for c in self.selected_categories.split(',') if c.strip()]


class InterviewQuestion(models.Model):
    """Individual editable interview question stored in the Interview Database."""
    question_set = models.ForeignKey(
        InterviewQuestionSet,
        on_delete=models.CASCADE,
        related_name='interview_questions'
    )
    category     = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='TECHNICAL')
    difficulty   = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='MEDIUM')
    question_text = models.TextField()
    model_answer  = models.TextField(blank=True, null=True)
    is_edited     = models.BooleanField(default=False, help_text="True if recruiter edited this question")
    order         = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['category', 'order']

    def __str__(self):
        return f"[{self.get_category_display()} / {self.get_difficulty_display()}] {self.question_text[:60]}"


# ── Module 7: Interview Intelligence ─────────────────────────────────────────

class InterviewSummary(models.Model):
    """AI-generated intelligence report for a completed interview."""

    TRANSCRIPT_SOURCE_CHOICES = [
        ('MANUAL',    'Manually Pasted'),
        ('AUDIO_STT', 'Audio → Groq Whisper STT'),
    ]

    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        related_name='interview_summary'
    )

    # Transcript
    transcript        = models.TextField(help_text="Raw interview transcript")
    transcript_source = models.CharField(
        max_length=20, choices=TRANSCRIPT_SOURCE_CHOICES, default='MANUAL'
    )
    audio_file = models.FileField(
        upload_to='interview_audio/',
        blank=True,
        null=True,
        help_text="Uploaded audio/video file for STT transcription"
    )

    # AI Analysis
    summary               = models.TextField()
    strengths             = models.JSONField(default=list)
    weaknesses            = models.JSONField(default=list)
    relevant_answers      = models.JSONField(default=list)
    areas_of_concern      = models.JSONField(default=list)
    overall_evaluation    = models.TextField(blank=True, null=True)

    # Scores
    communication_score   = models.FloatField(default=0.0)
    technical_score       = models.FloatField(default=0.0)
    confidence_score      = models.FloatField(default=0.0)
    problem_solving_score = models.FloatField(default=0.0)

    # Recommendation (decision support only — recruiter decides)
    hiring_recommendation = models.CharField(max_length=100, blank=True)
    next_round_suggestion = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Interview Intelligence: {self.application.candidate.user.get_full_name()}"

    @property
    def avg_score(self):
        scores = [
            self.communication_score,
            self.technical_score,
            self.confidence_score,
            self.problem_solving_score,
        ]
        return round(sum(scores) / len(scores), 1)


# ── Interview Scheduling (unchanged) ─────────────────────────────────────────

class InterviewSchedule(models.Model):
    STATUS_CHOICES = (
        ('SCHEDULED',   'Scheduled'),
        ('COMPLETED',   'Completed'),
        ('CANCELLED',   'Cancelled'),
        ('RESCHEDULED', 'Rescheduled'),
    )
    TYPE_CHOICES = (
        ('TECHNICAL',  'Technical Interview'),
        ('BEHAVIORAL', 'Behavioral / Cultural'),
        ('HR',         'HR / Screening'),
        ('FINAL',      'Final Round'),
    )

    application      = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='interview_schedules')
    scheduled_time   = models.DateTimeField()
    duration_minutes = models.IntegerField(default=60)
    interview_type   = models.CharField(max_length=30, choices=TYPE_CHOICES, default='TECHNICAL')
    meeting_link     = models.URLField(blank=True, null=True)
    notes            = models.TextField(blank=True, null=True)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_time']

    def __str__(self):
        return f"Interview for {self.application.candidate.user.get_full_name()} at {self.scheduled_time}"
