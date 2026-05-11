from django.conf import settings
from django.core.mail import send_mail


def send_approval_email(user):
    """
    Send an approval notification email to a newly approved doctor or secretary.
    Called automatically by a post_save signal when status changes to APPROVED.
    """
    if not user.email:
        return

    role_display = user.get_role_display()  # e.g. "Doctor" or "Secretary"
    first_name = user.first_name or user.username

    subject = f'Your account has been approved — Medical Cabinet'

    message = (
        f'Dear {first_name},\n\n'
        f'Congratulations! Your {role_display} account on the Medical Cabinet platform '
        f'has been reviewed and approved by an administrator.\n\n'
        f'You can now log in and access your dashboard:\n'
        f'  Username: {user.username}\n\n'
        f'If you have any questions, please contact the administration.\n\n'
        f'Best regards,\n'
        f'The Medical Cabinet Team'
    )

    send_mail(
        subject,
        message,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'clinic@example.com'),
        [user.email],
        fail_silently=True,
    )
