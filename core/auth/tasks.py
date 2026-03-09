"""
Celery tasks for async authentication emails.
All auth emails are sent asynchronously via Celery.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task(name='core.auth.tasks.send_verification_email')
def send_verification_email(user_id, email_address_id):
    """Send an email verification link to the user."""
    from django.contrib.auth import get_user_model
    from core.auth.models import EmailAddress
    from core.auth.tokens import make_email_verification_key

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
        email_addr = EmailAddress.objects.get(pk=email_address_id)
    except (User.DoesNotExist, EmailAddress.DoesNotExist):
        logger.warning('User %s or EmailAddress %s not found', user_id, email_address_id)
        return

    if email_addr.verified:
        logger.info('Email %s already verified, skipping', email_addr.email)
        return

    key = make_email_verification_key(email_address_id)
    verification_url = f'{settings.FRONTEND_URL}/#/verify-email/{key}'
    name = user.display_name or 'there'

    send_mail(
        subject='DreamPlanner — Verify your email address',
        message=(
            f'Hi {name},\n\n'
            f'Welcome to DreamPlanner! Please verify your email address '
            f'by clicking the link below:\n\n'
            f'{verification_url}\n\n'
            f'This link expires in 3 days.\n\n'
            f'If you did not create an account, please ignore this email.\n\n'
            f'— The DreamPlanner Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email_addr.email],
        fail_silently=False,
    )
    logger.info('Verification email sent to %s for user %s', email_addr.email, user_id)


@shared_task(name='core.auth.tasks.send_password_reset_email')
def send_password_reset_email(user_id):
    """Send a password reset link to the user."""
    from django.contrib.auth import get_user_model
    from core.auth.tokens import make_password_reset_token

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        logger.warning('User %s not found for password reset', user_id)
        return

    uid, token = make_password_reset_token(user)
    reset_url = f'{settings.FRONTEND_URL}/#/reset-password/{uid}-{token}'
    name = user.display_name or 'there'

    send_mail(
        subject='DreamPlanner — Reset your password',
        message=(
            f'Hi {name},\n\n'
            f'We received a request to reset your password. '
            f'Click the link below to set a new password:\n\n'
            f'{reset_url}\n\n'
            f'This link expires in 1 hour.\n\n'
            f'If you did not request a password reset, please ignore this email. '
            f'Your password will remain unchanged.\n\n'
            f'— The DreamPlanner Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    logger.info('Password reset email sent to %s', user.email)


@shared_task(name='core.auth.tasks.send_welcome_email')
def send_welcome_email(user_id):
    """Send a welcome email after successful registration."""
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    name = user.display_name or 'there'

    send_mail(
        subject='Welcome to DreamPlanner!',
        message=(
            f'Hi {name},\n\n'
            f'Welcome to DreamPlanner — your personal dream achievement platform!\n\n'
            f'Start by creating your first dream and let our AI help you '
            f'build a roadmap to achieve it.\n\n'
            f'Visit: {settings.FRONTEND_URL}\n\n'
            f'— The DreamPlanner Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


@shared_task(name='core.auth.tasks.send_password_changed_email')
def send_password_changed_email(user_id):
    """Notify user that their password was changed."""
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    name = user.display_name or 'there'

    send_mail(
        subject='DreamPlanner — Your password was changed',
        message=(
            f'Hi {name},\n\n'
            f'Your DreamPlanner password was just changed.\n\n'
            f'If you made this change, no action is needed.\n\n'
            f'If you did not change your password, please reset it immediately '
            f'at {settings.FRONTEND_URL}/#/forgot-password or contact support.\n\n'
            f'— The DreamPlanner Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
    logger.info('Password changed notification sent to %s', user.email)


@shared_task(name='core.auth.tasks.send_login_notification_email')
def send_login_notification_email(user_id, ip_address='', user_agent=''):
    """Notify user of a new login to their account."""
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    name = user.display_name or 'there'

    details = ''
    if ip_address:
        details += f'IP address: {ip_address}\n'
    if user_agent:
        details += f'Device: {user_agent}\n'

    send_mail(
        subject='DreamPlanner — New login to your account',
        message=(
            f'Hi {name},\n\n'
            f'A new login to your DreamPlanner account was detected.\n\n'
            f'{details}\n'
            f'If this was you, no action is needed.\n\n'
            f'If you did not log in, please change your password immediately '
            f'and consider enabling two-factor authentication.\n\n'
            f'— The DreamPlanner Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
    logger.info('Login notification sent to %s', user.email)
