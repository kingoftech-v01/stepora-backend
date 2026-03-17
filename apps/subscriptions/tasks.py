"""
Celery tasks for the Subscriptions app.

Handles async operations like sending email receipts and subscription
lifecycle notifications (upgrade, downgrade, cancellation, reactivation).
"""

import logging
from datetime import datetime

from celery import shared_task
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


@shared_task(name="apps.subscriptions.tasks.send_payment_receipt_email")
def send_payment_receipt_email(
    user_id: str, plan_name: str, amount: str, invoice_url: str = ""
):
    """
    Send an email receipt after a successful subscription payment.
    """
    from core.email import send_templated_email

    user = _get_user(user_id)
    if not user:
        return

    name = user.display_name or "there"
    frontend = getattr(settings, "FRONTEND_URL", "")

    try:
        send_templated_email(
            template_name="subscriptions/payment_receipt",
            subject=f"Stepora — Payment Receipt for {plan_name}",
            to=[user.email],
            context={
                "user_name": name,
                "plan_name": plan_name,
                "amount": amount,
                "invoice_url": invoice_url,
                "action_url": invoice_url or frontend,
            },
            from_name="Stepora Billing",
        )
        logger.info("Payment receipt email sent to %s", user.email)
    except Exception:
        logger.exception("Failed to send payment receipt email to %s", user.email)


@shared_task(name="apps.subscriptions.tasks.send_subscription_upgraded_email")
def send_subscription_upgraded_email(user_id: str, plan_name: str):
    """Notify user that their plan was upgraded."""
    from core.email import send_templated_email

    user = _get_user(user_id)
    if not user:
        return

    name = user.display_name or "there"
    frontend = getattr(settings, "FRONTEND_URL", "")
    subscription_url = f"{frontend}/#/subscription"

    send_templated_email(
        template_name="subscriptions/upgraded",
        subject=f"Stepora — Welcome to {plan_name}!",
        to=[user.email],
        context={
            "user_name": name,
            "plan_name": plan_name,
            "subscription_url": subscription_url,
            "action_url": subscription_url,
        },
        from_name="Stepora Billing",
        fail_silently=True,
    )
    logger.info("Upgrade email sent to %s (plan: %s)", user.email, plan_name)


@shared_task(
    name="apps.subscriptions.tasks.send_subscription_downgrade_scheduled_email"
)
def send_subscription_downgrade_scheduled_email(
    user_id: str, new_plan_name: str, effective_date: str = ""
):
    """Notify user that a downgrade has been scheduled."""
    from core.email import send_templated_email

    user = _get_user(user_id)
    if not user:
        return

    name = user.display_name or "there"
    frontend = getattr(settings, "FRONTEND_URL", "")
    subscription_url = f"{frontend}/#/subscription"

    date_str = ""
    if effective_date:
        try:
            dt = datetime.fromisoformat(effective_date)
            date_str = dt.strftime("%B %d, %Y")
        except (ValueError, TypeError):
            date_str = effective_date

    send_templated_email(
        template_name="subscriptions/downgrade_scheduled",
        subject="Stepora — Plan change scheduled",
        to=[user.email],
        context={
            "user_name": name,
            "new_plan_name": new_plan_name,
            "effective_date": date_str,
            "action_url": subscription_url,
        },
        from_name="Stepora Billing",
        fail_silently=True,
    )
    logger.info("Downgrade scheduled email sent to %s", user.email)


@shared_task(name="apps.subscriptions.tasks.send_subscription_cancel_scheduled_email")
def send_subscription_cancel_scheduled_email(
    user_id: str, plan_name: str, period_end: str = ""
):
    """Notify user that their subscription will cancel at period end."""
    from core.email import send_templated_email

    user = _get_user(user_id)
    if not user:
        return

    name = user.display_name or "there"
    frontend = getattr(settings, "FRONTEND_URL", "")
    subscription_url = f"{frontend}/#/subscription"

    date_str = ""
    if period_end:
        try:
            dt = datetime.fromisoformat(period_end)
            date_str = dt.strftime("%B %d, %Y")
        except (ValueError, TypeError):
            date_str = period_end

    send_templated_email(
        template_name="subscriptions/cancel_scheduled",
        subject="Stepora — Subscription cancellation scheduled",
        to=[user.email],
        context={
            "user_name": name,
            "plan_name": plan_name,
            "period_end": date_str,
            "subscription_url": subscription_url,
            "action_url": subscription_url,
        },
        from_name="Stepora Billing",
        fail_silently=True,
    )
    logger.info("Cancel scheduled email sent to %s", user.email)


@shared_task(name="apps.subscriptions.tasks.send_subscription_cancelled_email")
def send_subscription_cancelled_email(user_id: str, old_plan_name: str):
    """Notify user that their subscription has been fully cancelled (reverted to free)."""
    from core.email import send_templated_email

    user = _get_user(user_id)
    if not user:
        return

    name = user.display_name or "there"
    frontend = getattr(settings, "FRONTEND_URL", "")
    subscription_url = f"{frontend}/#/subscription"

    send_templated_email(
        template_name="subscriptions/cancelled",
        subject="Stepora — Your subscription has ended",
        to=[user.email],
        context={
            "user_name": name,
            "old_plan_name": old_plan_name,
            "subscription_url": subscription_url,
            "action_url": subscription_url,
        },
        from_name="Stepora Billing",
        fail_silently=True,
    )
    logger.info("Subscription cancelled email sent to %s", user.email)


@shared_task(name="apps.subscriptions.tasks.send_subscription_reactivated_email")
def send_subscription_reactivated_email(user_id: str, plan_name: str):
    """Notify user that their cancellation was reversed."""
    from core.email import send_templated_email

    user = _get_user(user_id)
    if not user:
        return

    name = user.display_name or "there"
    frontend = getattr(settings, "FRONTEND_URL", "")

    send_templated_email(
        template_name="subscriptions/reactivated",
        subject="Stepora — Subscription reactivated",
        to=[user.email],
        context={
            "user_name": name,
            "plan_name": plan_name,
            "action_url": frontend,
        },
        from_name="Stepora Billing",
        fail_silently=True,
    )
    logger.info("Reactivation email sent to %s", user.email)


@shared_task(name="apps.subscriptions.tasks.send_free_user_upgrade_reminders")
def send_free_user_upgrade_reminders():
    """
    Send push notifications to active free users encouraging upgrade.

    Targets users who:
    - Are on the free plan
    - Have been active in the last 7 days
    - Registered more than 3 days ago
    - Haven't received this reminder in the last 7 days
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.users.models import User

    now = timezone.now()
    three_days_ago = now - timedelta(days=3)
    seven_days_ago = now - timedelta(days=7)

    # Users on free plan, registered >3 days ago, active in last 7 days
    free_users = User.objects.filter(
        is_active=True,
        subscription="free",
        date_joined__lte=three_days_ago,
        last_login__gte=seven_days_ago,
    ).values_list("id", flat=True)[:100]

    sent = 0
    for user_id in free_users:
        try:
            _send_upgrade_push.delay(str(user_id))
            sent += 1
        except Exception:
            logger.exception(
                "Failed to queue upgrade push for user %s", user_id
            )

    logger.info(
        "Queued %d free-user upgrade reminder pushes", sent
    )


@shared_task(name="apps.subscriptions.tasks._send_upgrade_push")
def _send_upgrade_push(user_id: str):
    """Send a single upgrade push notification to a free user."""
    user = _get_user(user_id)
    if not user:
        return

    try:
        from apps.notifications.services import NotificationService

        # Check for active promotions
        from apps.subscriptions.services import PromotionService

        promos = PromotionService.get_active_promotions(user)
        if promos:
            title = promos[0].name
            body = promos[0].description or "Upgrade now and save!"
        else:
            name = user.display_name or "there"
            title = "Ready to level up?"
            body = f"Hey {name}, unlock AI coaching, unlimited dreams, and more with Premium!"

        NotificationService.send_push(
            user=user,
            title=title,
            body=body,
            data={"type": "upgrade_reminder", "route": "/subscription"},
        )
        logger.info("Upgrade push sent to %s", user.email)
    except Exception:
        logger.exception("Failed to send upgrade push to %s", user_id)
