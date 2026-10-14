from django.db import models
from django.conf import settings
from applications.validators import validate_resume_file


class CandidateProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='candidate_profile'
    )
    resume_file = models.FileField(upload_to='resumes/', null=True, blank=True, validators=[validate_resume_file])
    raw_text = models.TextField(blank=True, null=True)

    # Parsed basic fields
    full_name = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)
    github_url = models.URLField(blank=True, null=True)

    # Parsed structured fields stored as JSON
    skills = models.JSONField(default=list, blank=True)
    education = models.JSONField(default=list, blank=True)
    experience = models.JSONField(default=list, blank=True)
    projects = models.JSONField(default=list, blank=True)
    certifications = models.JSONField(default=list, blank=True)
    languages = models.JSONField(default=list, blank=True)
    embedding_vector = models.JSONField(default=list, blank=True, null=True)

    # Metadata
    is_parsed = models.BooleanField(default=False)
    parse_error = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile: {self.user.get_full_name() or self.user.email}"

    @property
    def experience_structured(self):
        """Returns experience as a list of dicts, normalising string elements."""
        normalized = []
        for item in self.experience or []:
            if isinstance(item, dict):
                normalized.append(item)
            elif isinstance(item, str):
                normalized.append({
                    'title': item,
                    'role': item,
                    'company': '',
                    'organization': '',
                    'duration': '',
                    'dates': '',
                    'description': ''
                })
        return normalized

    @property
    def education_structured(self):
        """Returns education as a list of dicts, normalising string elements."""
        normalized = []
        for item in self.education or []:
            if isinstance(item, dict):
                normalized.append(item)
            elif isinstance(item, str):
                normalized.append({
                    'degree': item,
                    'qualification': item,
                    'institution': '',
                    'college': '',
                    'year': '',
                    'duration': ''
                })
        return normalized

    @property
    def projects_structured(self):
        """Returns projects as a list of dicts, normalising string elements."""
        normalized = []
        for item in self.projects or []:
            if isinstance(item, dict):
                normalized.append(item)
            elif isinstance(item, str):
                normalized.append({
                    'name': item,
                    'title': item,
                    'description': ''
                })
        return normalized

