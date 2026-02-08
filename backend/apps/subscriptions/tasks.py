"""
Celery tasks for the Subscriptions app.

Handles async operations like sending email receipts on successful payment.
"""

import logging

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(name='apps.subscriptions.tasks.send_payment_receipt_email')
def send_payment_receipt_email(user_id: str, plan_name: str, amount: str, invoice_url: str = ''):
    """
    Send an email receipt after a successful subscription payment.

    Args:
        user_id: UUID of the user.
        plan_name: Name of the subscription plan.
        amount: Amount charged (formatted string, e.g. "$9.99").
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
