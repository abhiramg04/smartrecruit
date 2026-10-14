from django.db import models
from companies.models import Company

class Category(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Skill(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Job(models.Model):
    EMPLOYMENT_TYPES = (
        ('FULL_TIME', 'Full-time'),
        ('PART_TIME', 'Part-time'),
        ('CONTRACT', 'Contract'),
        ('INTERNSHIP', 'Internship'),
    )
    WORK_MODELS = (
        ('ONSITE', 'On-site'),
        ('REMOTE', 'Remote'),
        ('HYBRID', 'Hybrid'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='jobs')
    title = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='jobs')
    description = models.TextField()
    experience_years = models.IntegerField(default=0)
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPES, default='FULL_TIME')
    work_model = models.CharField(max_length=20, choices=WORK_MODELS, default='ONSITE')
    skills = models.ManyToManyField(Skill, related_name='jobs', blank=True)
    preferred_skills = models.ManyToManyField(Skill, related_name='preferred_jobs', blank=True)
    education = models.CharField(max_length=255, null=True, blank=True)
    openings = models.IntegerField(default=1)
    deadline = models.DateField(null=True, blank=True)
    
    is_published = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    
    ai_metadata = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def status(self):
        if self.is_closed:
            return 'CLOSED'
        elif self.is_published:
            return 'PUBLISHED'
        return 'DRAFT'

    def __str__(self):
        return f"{self.title} at {self.company.name}"
