"""
Celery tasks for the Subscriptions app.

Handles async operations like sending email receipts and subscription
lifecycle notifications (upgrade, downgrade, cancellation, reactivation).
"""

import logging
from datetime import datetime

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_user(user_id):
    """Fetch user by ID, return None if not found."""
    from apps.users.models import User
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.warning("User %s not found for subscription email", user_id)
        return None


def _send(subject, body, recipient_email):
    """Send a subscription notification email (fail_silently=True)."""
    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@dreamplanner.com'),
        recipient_list=[recipient_email],
        fail_silently=True,
    )


@shared_task(name='apps.subscriptions.tasks.send_payment_receipt_email')
def send_payment_receipt_email(user_id: str, plan_name: str, amount: str, invoice_url: str = ''):
    """
    Send an email receipt after a successful subscription payment.

    Args:
        user_id: UUID of the user.
        plan_name: Name of the subscription plan.
        amount: Amount charged (formatted string, e.g. "$19.99").
        invoice_url: URL to the Stripe-hosted invoice.
    """
    from apps.users.models import User

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error("User %s not found for payment receipt email", user_id)
        return

    subject = f"DreamPlanner - Payment Receipt for {plan_name}"

    body = (
        f"Hi {user.display_name or 'there'},\n\n"
        f"Thank you for your subscription to DreamPlanner {plan_name}!\n\n"
        f"Amount charged: {amount}\n"
    )

    if invoice_url:
        body += f"\nView your invoice: {invoice_url}\n"

    body += (
        "\nIf you have any questions about your subscription, "
        "please contact support@dreamplanner.com.\n\n"
        "Keep dreaming!\n"
        "The DreamPlanner Team"
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@dreamplanner.com'),
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info("Payment receipt email sent to %s", user.email)
    except Exception:
        logger.exception("Failed to send payment receipt email to %s", user.email)


@shared_task(name='apps.subscriptions.tasks.send_subscription_upgraded_email')
def send_subscription_upgraded_email(user_id: str, plan_name: str):
    """Notify user that their plan was upgraded."""
    user = _get_user(user_id)
    if not user:
        return
    name = user.display_name or 'there'
    frontend = getattr(settings, 'FRONTEND_URL', '')
    _send(
        subject=f'DreamPlanner — Welcome to {plan_name}!',
        body=(
            f'Hi {name},\n\n'
            f'Your plan has been upgraded to {plan_name}! '
            f'All new features are available immediately.\n\n'
            f'Explore your new features: {frontend}/#/subscription\n\n'
            f'— The DreamPlanner Team'
        ),
        recipient_email=user.email,
    )
    logger.info("Upgrade email sent to %s (plan: %s)", user.email, plan_name)


@shared_task(name='apps.subscriptions.tasks.send_subscription_downgrade_scheduled_email')
def send_subscription_downgrade_scheduled_email(user_id: str, new_plan_name: str, effective_date: str = ''):
    """Notify user that a downgrade has been scheduled."""
    user = _get_user(user_id)
    if not user:
        return
    name = user.display_name or 'there'
    date_str = ''
    if effective_date:
        try:
            dt = datetime.fromisoformat(effective_date)
            date_str = dt.strftime('%B %d, %Y')
        except (ValueError, TypeError):
            date_str = effective_date
    _send(
        subject='DreamPlanner — Plan change scheduled',
        body=(
            f'Hi {name},\n\n'
            f'Your plan will change to {new_plan_name}'
            f'{" on " + date_str if date_str else " at the end of your current billing period"}.\n\n'
            f'You will keep full access to your current plan features until then.\n\n'
            f'If you change your mind, you can cancel this change from your subscription settings.\n\n'
            f'— The DreamPlanner Team'
        ),
        recipient_email=user.email,
    )
    logger.info("Downgrade scheduled email sent to %s", user.email)


@shared_task(name='apps.subscriptions.tasks.send_subscription_cancel_scheduled_email')
def send_subscription_cancel_scheduled_email(user_id: str, plan_name: str, period_end: str = ''):
    """Notify user that their subscription will cancel at period end."""
    user = _get_user(user_id)
    if not user:
        return
    name = user.display_name or 'there'
    date_str = ''
    if period_end:
        try:
            dt = datetime.fromisoformat(period_end)
            date_str = dt.strftime('%B %d, %Y')
        except (ValueError, TypeError):
            date_str = period_end
    frontend = getattr(settings, 'FRONTEND_URL', '')
    _send(
        subject='DreamPlanner — Subscription cancellation scheduled',
        body=(
            f'Hi {name},\n\n'
            f'Your {plan_name} subscription has been set to cancel'
            f'{" on " + date_str if date_str else " at the end of your billing period"}.\n\n'
            f'You will keep full access until then. After that, your account '
            f'will revert to the Free plan.\n\n'
            f'Changed your mind? Reactivate anytime: {frontend}/#/subscription\n\n'
            f'— The DreamPlanner Team'
        ),
        recipient_email=user.email,
    )
    logger.info("Cancel scheduled email sent to %s", user.email)


@shared_task(name='apps.subscriptions.tasks.send_subscription_cancelled_email')
def send_subscription_cancelled_email(user_id: str, old_plan_name: str):
    """Notify user that their subscription has been fully cancelled (reverted to free)."""
    user = _get_user(user_id)
    if not user:
        return
    name = user.display_name or 'there'
    frontend = getattr(settings, 'FRONTEND_URL', '')
    _send(
        subject='DreamPlanner — Your subscription has ended',
        body=(
            f'Hi {name},\n\n'
            f'Your {old_plan_name} subscription has ended and your account '
            f'has been moved to the Free plan.\n\n'
            f'You can still access your dreams and basic features. '
            f'To regain premium features, subscribe again anytime: '
            f'{frontend}/#/subscription\n\n'
            f'— The DreamPlanner Team'
        ),
        recipient_email=user.email,
    )
    logger.info("Subscription cancelled email sent to %s", user.email)


@shared_task(name='apps.subscriptions.tasks.send_subscription_reactivated_email')
def send_subscription_reactivated_email(user_id: str, plan_name: str):
    """Notify user that their cancellation was reversed."""
    user = _get_user(user_id)
    if not user:
        return
    name = user.display_name or 'there'
    _send(
        subject='DreamPlanner — Subscription reactivated',
        body=(
            f'Hi {name},\n\n'
            f'Great news! Your {plan_name} subscription has been reactivated '
            f'and will continue to renew as normal.\n\n'
            f'Keep dreaming!\n\n'
            f'— The DreamPlanner Team'
        ),
        recipient_email=user.email,
    )
    logger.info("Reactivation email sent to %s", user.email)
