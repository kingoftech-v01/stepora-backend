"""
Centralized email rendering and sending for Stepora.

All emails go through `send_templated_email()` which:
1. Renders both HTML and plain-text Django templates
2. Dispatches via the existing `core.tasks.send_rendered_email` Celery task
   (async SMTP with retry logic)

Usage:
    from core.email import send_templated_email

    send_templated_email(
        template_name='auth/verify_email',       # looks for templates/email/auth/verify_email.html + .txt
        subject='Verify your email',
        to=[user.email],
        context={'user_name': user.display_name, 'verification_url': url},
    )
"""

import logging
from datetime import datetime

from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_templated_email(template_name, subject, to, context=None, fail_silently=False):
    """
    Render and send an HTML email with plain-text fallback.

    Args:
        template_name: Template path relative to templates/email/ (without extension).
                       E.g. 'auth/verify_email' -> templates/email/auth/verify_email.html
        subject: Email subject line.
        to: List of recipient email addresses.
        context: Template context dict. 'frontend_url' and 'year' are auto-injected.
        fail_silently: If True, swallow SMTP errors (logged as warning).
    """
    from core.tasks import send_rendered_email

    ctx = {
        'frontend_url': getattr(settings, 'FRONTEND_URL', ''),
        'year': datetime.now().year,
    }
    if context:
        ctx.update(context)

    # Ensure action_url has a default
    if 'action_url' not in ctx:
        ctx['action_url'] = ctx['frontend_url']

    html_path = f'email/{template_name}.html'
    txt_path = f'email/{template_name}.txt'

    try:
        html_body = render_to_string(html_path, ctx)
    except Exception:
        logger.exception('Failed to render HTML email template: %s', html_path)
        raise

    try:
        text_body = render_to_string(txt_path, ctx)
    except Exception:
        # Plain-text template is optional; fall back to a stripped version
        logger.debug('No plain-text template for %s, using subject as body', txt_path)
        text_body = subject

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@stepora.app')

    if fail_silently:
        try:
            send_rendered_email.delay(
                subject=subject,
                body=text_body,
                from_email=from_email,
                to=to,
                alternatives=[(html_body, 'text/html')],
            )
        except Exception:
            logger.warning('Failed to dispatch email to %s: %s', to, subject, exc_info=True)
    else:
        send_rendered_email.delay(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=to,
            alternatives=[(html_body, 'text/html')],
        )

    logger.info('Dispatched email "%s" to %s', subject, to)
