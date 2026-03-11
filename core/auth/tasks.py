"""
Celery tasks for async authentication emails.
All auth emails are sent asynchronously via Celery.
"""

import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(name="core.auth.tasks.send_verification_email")
def send_verification_email(user_id, email_address_id):
    """Send an email verification link to the user."""
    from django.contrib.auth import get_user_model

    from core.auth.models import EmailAddress
    from core.auth.tokens import make_email_verification_key
    from core.email import send_templated_email

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
        email_addr = EmailAddress.objects.get(pk=email_address_id)
    except (User.DoesNotExist, EmailAddress.DoesNotExist):
        logger.warning(
            "User %s or EmailAddress %s not found", user_id, email_address_id
        )
        return

    if email_addr.verified:
        logger.info("Email %s already verified, skipping", email_addr.email)
        return

    key = make_email_verification_key(email_address_id)
    verification_url = f"{settings.FRONTEND_URL}/#/verify-email/{key}"
    name = user.display_name or "there"

    send_templated_email(
        template_name="auth/verify_email",
        subject="Stepora — Verify your email address",
        to=[email_addr.email],
        context={
            "user_name": name,
            "verification_url": verification_url,
            "action_url": verification_url,
        },
    )
    logger.info("Verification email sent to %s for user %s", email_addr.email, user_id)


@shared_task(name="core.auth.tasks.send_password_reset_email")
def send_password_reset_email(user_id):
    """Send a password reset link to the user."""
    from django.contrib.auth import get_user_model

    from core.auth.tokens import make_password_reset_token
    from core.email import send_templated_email

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        logger.warning("User %s not found for password reset", user_id)
        return

    uid, token = make_password_reset_token(user)
    reset_url = f"{settings.FRONTEND_URL}/#/reset-password/{uid}~{token}"
    name = user.display_name or "there"

    send_templated_email(
        template_name="auth/password_reset",
        subject="Stepora — Reset your password",
        to=[user.email],
        context={
            "user_name": name,
            "reset_url": reset_url,
            "action_url": reset_url,
        },
    )
    logger.info("Password reset email sent to %s", user.email)


@shared_task(name="core.auth.tasks.send_welcome_email")
def send_welcome_email(user_id):
    """Send a welcome email after successful registration."""
    from django.contrib.auth import get_user_model

    from core.email import send_templated_email

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    name = user.display_name or "there"

    send_templated_email(
        template_name="auth/welcome",
        subject="Welcome to Stepora!",
        to=[user.email],
        context={
            "user_name": name,
            "action_url": settings.FRONTEND_URL,
        },
        fail_silently=True,
    )


@shared_task(name="core.auth.tasks.send_password_changed_email")
def send_password_changed_email(user_id):
    """Notify user that their password was changed."""
    from django.contrib.auth import get_user_model

    from core.email import send_templated_email

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    name = user.display_name or "there"
    reset_url = f"{settings.FRONTEND_URL}/#/forgot-password"

    send_templated_email(
        template_name="auth/password_changed",
        subject="Stepora — Your password was changed",
        to=[user.email],
        context={
            "user_name": name,
            "reset_url": reset_url,
            "action_url": reset_url,
        },
        fail_silently=True,
    )
    logger.info("Password changed notification sent to %s", user.email)


@shared_task(name="core.auth.tasks.send_login_notification_email")
def send_login_notification_email(user_id, ip_address="", user_agent=""):
    """Notify user of a new login to their account."""
    from django.contrib.auth import get_user_model

    from core.email import send_templated_email

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    name = user.display_name or "there"

    send_templated_email(
        template_name="auth/login_notification",
        subject="Stepora — New login to your account",
        to=[user.email],
        context={
            "user_name": name,
            "ip_address": ip_address,
            "user_agent": user_agent,
        },
        fail_silently=True,
    )
    logger.info("Login notification sent to %s", user.email)
