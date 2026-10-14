from django.core.mail import send_mail
from django.conf import settings
from .models import Notification
from accounts.models import User

def send_in_app_notification(user, message):
    """Core function to create a dashboard alert."""
    return Notification.objects.create(user=user, message=message)

def send_email_alert(user, subject, message):
    """Core function to send an email."""
    try:
        send_mail(
            subject,
            message,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@smartrecruit.com'),
            [user.email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"Email failed: {e}")

def send_sms_alert(phone_number, message):
    """
    Placeholder for SMS notifications. 
    Can be integrated with Twilio or AWS SNS later.
    """
    # TODO: Implement Twilio Client
    print(f"[SMS MOCK] To: {phone_number} | Message: {message}")

def send_application_update_notification(application, new_status):
    """Notify candidate of status change."""
    candidate_user = application.candidate.user
    status_display = application.get_status_display()
    
    msg = f"Your application for {application.job.title} is now: {status_display}"
    
    send_in_app_notification(candidate_user, msg)
    send_email_alert(candidate_user, f"Application Update: {application.job.title}", msg)

def send_interview_reminder(application, interview_date):
    """Notify candidate of an upcoming interview."""
    candidate_user = application.candidate.user
    date_str = interview_date.strftime("%B %d, %Y at %I:%M %p")
    
    msg = f"Reminder: You have an interview for {application.job.title} on {date_str}."
    
    send_in_app_notification(candidate_user, msg)
    send_email_alert(candidate_user, "Interview Reminder", msg)
    
    # Optional SMS
    phone = getattr(application.candidate, 'phone_number', None)
    if phone:
        send_sms_alert(phone, msg)

def send_offer_letter_notification(application):
    """High priority offer notification."""
    candidate_user = application.candidate.user
    
    msg = f"Congratulations! You have received an offer for {application.job.title}."
    
    send_in_app_notification(candidate_user, msg)
    send_email_alert(candidate_user, "Job Offer Received!", msg)

def send_admin_alert(message):
    """Send an alert to all system administrators."""
    admins = User.objects.filter(role='ADMIN')
    for admin in admins:
        send_in_app_notification(admin, message)
        send_email_alert(admin, "System Admin Alert", message)
