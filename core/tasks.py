"""
Celery tasks for core app (async email sending).
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    name="core.tasks.send_rendered_email",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def send_rendered_email(self, subject, body, from_email, to, alternatives=None):
    """
    Send a pre-rendered email via SMTP.

    The email is already rendered by the adapter — this task only handles
    the slow SMTP I/O so the request cycle isn't blocked.
    """
    try:
        from django.core.mail import EmailMultiAlternatives

        msg = EmailMultiAlternatives(
            subject=subject, body=body, from_email=from_email, to=to
        )
        for content, mimetype in alternatives or []:
            msg.attach_alternative(content, mimetype)
        msg.send()
        logger.info("Sent email to %s: %s", to, subject)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        raise self.retry(exc=exc)
