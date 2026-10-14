from django.db import models
from applications.models import Application


class RankingResult(models.Model):
    VERDICT_CHOICES = (
        ('SUITABLE', 'Suitable'),
        ('MAYBE',    'Maybe'),
        ('REJECT',   'Reject'),
    )

    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        related_name='ranking_result'
    )

    # Component scores (0–100)
    skill_score       = models.FloatField(default=0.0)
    experience_score  = models.FloatField(default=0.0)
    education_score   = models.FloatField(default=0.0)
    project_score     = models.FloatField(default=0.0)
    cert_score        = models.FloatField(default=0.0)
    overall_score     = models.FloatField(default=0.0)

    # AI Outputs
    verdict           = models.CharField(max_length=10, choices=VERDICT_CHOICES, default='REJECT')
    matched_skills    = models.JSONField(default=list, blank=True)
    missing_skills    = models.JSONField(default=list, blank=True)
    ai_recommendation = models.TextField(blank=True, null=True)
    explainability    = models.JSONField(default=dict, blank=True)

    ranked_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-overall_score']

    def __str__(self):
        return f"Rank: {self.application} → {self.overall_score:.1f}% ({self.verdict})"

    def verdict_color(self):
        return {'SUITABLE': 'success', 'MAYBE': 'warning', 'REJECT': 'danger'}.get(self.verdict, 'secondary')

