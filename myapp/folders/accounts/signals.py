from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import CustomUser
from .notifications import send_approval_email


# Store the previous status before save so we can detect transitions
@receiver(pre_save, sender=CustomUser)
def capture_previous_status(sender, instance, **kwargs):
    """Attach the previous status to the instance before it is saved."""
    if instance.pk:
        try:
            instance._previous_status = CustomUser.objects.get(pk=instance.pk).status
        except CustomUser.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=CustomUser)
def on_user_saved(sender, instance, created, **kwargs):
    """
    After a CustomUser is saved, check if the status transitioned to APPROVED.
    If so, send a notification email to doctors and secretaries.
    """
    # Only care about doctors and secretaries (patients self-approve silently)
    if instance.role not in (CustomUser.Role.DOCTOR, CustomUser.Role.SECRETARY):
        return

    previous_status = getattr(instance, '_previous_status', None)
    current_status = instance.status

    # Fire email only on a genuine PENDING → APPROVED transition
    if previous_status != CustomUser.Status.APPROVED and current_status == CustomUser.Status.APPROVED:
        send_approval_email(instance)
