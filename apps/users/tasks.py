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


@shared_task(name='apps.users.tasks.hard_delete_expired_accounts')
def hard_delete_expired_accounts():
    """
    Hard-delete accounts that have been soft-deleted for 30+ days.

    GDPR compliance: ensures full data removal after the grace period.
    Users who soft-deleted their account have 30 days to recover it.
    After that, all data is permanently removed via CASCADE delete.
    """
    from datetime import timedelta as td
    from django.utils import timezone
    from .models import User

    cutoff = timezone.now() - td(days=30)
    expired_users = User.objects.filter(
        is_active=False,
        updated_at__lt=cutoff,
    )

    count = 0
    for user in expired_users:
        try:
            user_id = user.id
            user.delete()  # CASCADE deletes all related data
            count += 1
            logger.info("Hard-deleted expired account %s", user_id)
        except Exception:
            logger.exception("Failed to hard-delete user %s", user.id)

    logger.info("Hard-deleted %d expired accounts", count)
    return count
