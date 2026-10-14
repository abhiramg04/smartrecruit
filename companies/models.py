from django.db import models
from django.conf import settings

class Subscription(models.Model):
    name = models.CharField(max_length=50)
    max_jobs = models.IntegerField(default=5)
    max_recruiters = models.IntegerField(default=2)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return self.name

class Company(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_company')
    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    industry = models.CharField(max_length=100, null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Department(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.company.name}"
