from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('RECRUITER', 'Recruiter'),
        ('CANDIDATE', 'Candidate'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CANDIDATE')
    company = models.ForeignKey('companies.Company', on_delete=models.SET_NULL, null=True, blank=True, related_name='recruiters')
    profile_photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    bio = models.TextField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    designation = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.username} - {self.role}"

class OTPRecord(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        # OTP is valid for 10 minutes
        return not self.is_used and (timezone.now() - self.created_at).total_seconds() < 600

class ActivityLog(models.Model):
    ACTION_CHOICES = (
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('PASSWORD_CHANGE', 'Password Change'),
        ('PROFILE_UPDATE', 'Profile Update'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.action} at {self.timestamp}"
