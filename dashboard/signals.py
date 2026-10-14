from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import AuditLog

def get_client_ip(request):
    """Utility to get client IP from request."""
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def log_action(user, action, description, ip_address=None):
    """Utility to create an audit log."""
    AuditLog.objects.create(
        user=user,
        action=action,
        description=description,
        ip_address=ip_address
    )

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    log_action(user, 'LOGIN', f"User {user.email} logged in.", ip)

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    if user:
        log_action(user, 'LOGOUT', f"User {user.email} logged out.", ip)

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    ip = get_client_ip(request)
    email = credentials.get('email') or credentials.get('username') or 'Unknown'
    log_action(None, 'LOGIN_FAILED', f"Failed login attempt for {email}.", ip)
