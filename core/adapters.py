"""
Custom allauth account adapter for DreamPlanner.

- Email confirmation/reset URLs point to the frontend SPA (FRONTEND_URL).
- All emails are sent asynchronously via Celery to avoid blocking requests.
"""

import logging

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings

logger = logging.getLogger(__name__)


class DreamPlannerAccountAdapter(DefaultAccountAdapter):

    def get_email_confirmation_url(self, request, emailconfirmation):
        frontend_url = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
        if frontend_url:
            return f"{frontend_url}/verify-email?key={emailconfirmation.key}"
        return super().get_email_confirmation_url(request, emailconfirmation)

    def get_reset_password_from_key_url(self, key):
        frontend_url = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
        if frontend_url:
            return f"{frontend_url}/reset-password?key={key}"
        return super().get_reset_password_from_key_url(key)

    def send_mail(self, template_prefix, email, context):
        """
        Render email synchronously (fast), send via Celery (slow SMTP I/O).
        Context contains model instances that can't be serialized, so we
        render first and pass the plain strings to the Celery task.
        """
        from core.tasks import send_rendered_email
        try:
            msg = self.render_mail(template_prefix, email, context)
            send_rendered_email.delay(
                subject=msg.subject,
                body=msg.body,
                from_email=msg.from_email,
                to=msg.to,
                alternatives=getattr(msg, 'alternatives', []),
            )
        except Exception:
            logger.warning("Celery unavailable, sending email synchronously", exc_info=True)
            super().send_mail(template_prefix, email, context)
