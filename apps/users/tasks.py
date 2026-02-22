"""
Celery tasks for the Users app.

Handles async operations like sending email change verification emails
and account data export.
"""

import logging

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(name='apps.users.tasks.send_email_change_verification')
def send_email_change_verification(user_id: int, new_email: str, token: str):
    """
    Send a verification email when a user requests an email change.
    """
    from .models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning('User %s not found for email change verification', user_id)
        return

    verification_url = f"{settings.FRONTEND_URL}/verify-email/{token}"

    send_mail(
        subject='DreamPlanner - Verify your new email address',
        message=(
            f'Hi {user.display_name or "there"},\n\n'
            f'You requested to change your email to {new_email}.\n\n'
            f'Please verify this email by clicking the link below:\n'
            f'{verification_url}\n\n'
            f'This link expires in 24 hours.\n\n'
            f'If you did not request this change, please ignore this email.\n\n'
            f'— The DreamPlanner Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[new_email],
        fail_silently=False,
    )

    logger.info('Email change verification sent to %s for user %s', new_email, user_id)


@shared_task(name='apps.users.tasks.export_user_data')
def export_user_data(user_id: int):
    """
    Export all user data as JSON and email a download link.
    """
    import json
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from .models import User
    from .serializers import UserSerializer

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning('User %s not found for data export', user_id)
        return

    user_data = UserSerializer(user).data

    # Include related data
    export = {
        'user': user_data,
        'dreams': list(user.dreams.values()),
        'conversations': list(user.conversations.values()),
        'notifications': list(user.notifications.values('id', 'title', 'body', 'created_at', 'is_read')),
    }

    json_content = json.dumps(export, default=str, indent=2)
    file_path = f'exports/user_{user_id}_data.json'
    default_storage.save(file_path, ContentFile(json_content.encode()))

    download_url = f"{settings.FRONTEND_URL}/api/media/{file_path}"

    send_mail(
        subject='DreamPlanner - Your data export is ready',
        message=(
            f'Hi {user.display_name or "there"},\n\n'
            f'Your data export is ready for download:\n'
            f'{download_url}\n\n'
            f'This file will be available for 7 days.\n\n'
            f'— The DreamPlanner Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    logger.info('Data export completed and emailed for user %s', user_id)
