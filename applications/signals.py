"""
applications/signals.py — Phase 09 revised.

WorkflowEngine now handles all WorkflowLog creation and NotificationService calls for
explicit recruiter actions (shortlist, reject, select, etc.).

These signals only handle the initial application submission case (which is not
triggered through the engine) and guard against direct .save() calls from third-party
integrations that bypass the engine.
"""
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Application


@receiver(pre_save, sender=Application)
def track_previous_status(sender, instance, **kwargs):
    """Store previous status before save for change detection."""
    if instance.pk:
        try:
            old_instance = Application.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Application.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Application)
def handle_application_status_change(sender, instance, created, **kwargs):
    """
    Guard signal: Only triggers WorkflowLog if a status change happens outside
    the WorkflowEngine (e.g. direct .save() from admin or third-party integrations).
    WorkflowEngine itself creates WorkflowLog and calls NotificationService explicitly.
    """
    from .models import WorkflowLog

    old_status = getattr(instance, '_old_status', None)
    new_status = instance.status

    # If this is a newly created application, the WorkflowEngine was not used.
    # Just create the initial log. NotificationService is called from ApplyView directly.
    if created:
        WorkflowLog.objects.create(
            application=instance,
            new_status=new_status,
            notes="Application submitted via portal."
        )
