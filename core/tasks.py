"""
Celery tasks for core app (async email sending + security monitoring).
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")

# Auth failure alerting thresholds (V-1222, V-1223)
_AUTH_FAILURE_THRESHOLD = 50  # failures in window triggers alert
_AUTH_FAILURE_WINDOW = 900  # 15-minute window (seconds)
_AUTH_ALERT_COOLDOWN = 3600  # 1 hour between alert emails


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


@shared_task(name="core.tasks.check_auth_failure_anomalies")
def check_auth_failure_anomalies():
    """Check for auth failure anomalies and alert admins (V-1222, V-1223).

    Runs periodically via Celery beat. Counts recent AUTH_FAILURE events
    from the security audit log (stored in cache by record_auth_failure_metric)
    and sends an alert email if the count exceeds the threshold.
    """
    from django.conf import settings
    from django.core.cache import cache

    cache_key = "security:auth_failures:count"
    alert_cooldown_key = "security:auth_failure_alert:sent"

    failure_count = cache.get(cache_key, 0)

    if failure_count < _AUTH_FAILURE_THRESHOLD:
        return f"OK: {failure_count} auth failures (threshold: {_AUTH_FAILURE_THRESHOLD})"

    # Check cooldown to avoid alert fatigue
    if cache.get(alert_cooldown_key):
        return f"ALERT_SUPPRESSED: {failure_count} failures, alert already sent recently"

    # Get top offending IPs from cache
    top_ips_key = "security:auth_failures:top_ips"
    top_ips = cache.get(top_ips_key, {})
    top_ips_str = ", ".join(
        f"{ip} ({count}x)" for ip, count in sorted(
            top_ips.items(), key=lambda x: x[1], reverse=True
        )[:10]
    ) if top_ips else "N/A"

    security_logger.critical(
        "AUTH_ANOMALY_ALERT count=%d threshold=%d window=%ds top_ips=%s",
        failure_count,
        _AUTH_FAILURE_THRESHOLD,
        _AUTH_FAILURE_WINDOW,
        top_ips_str,
    )

    # Send alert email to admins
    admin_email = getattr(settings, "SECURITY_ALERT_EMAIL", None)
    if not admin_email:
        admin_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@stepora.app")

    try:
        from django.core.mail import mail_admins

        mail_admins(
            subject=f"[SECURITY ALERT] {failure_count} auth failures in {_AUTH_FAILURE_WINDOW // 60}min",
            message=(
                f"Auth failure anomaly detected.\n\n"
                f"Failures in window: {failure_count}\n"
                f"Threshold: {_AUTH_FAILURE_THRESHOLD}\n"
                f"Window: {_AUTH_FAILURE_WINDOW // 60} minutes\n"
                f"Top IPs: {top_ips_str}\n\n"
                f"Check CloudWatch logs for details:\n"
                f"  Log group: /ecs/stepora-backend\n"
                f"  Filter: AUTH_FAILURE\n"
            ),
            fail_silently=True,
        )
    except (ConnectionError, OSError):
        logger.error("Failed to send auth anomaly alert email")

    # Set cooldown
    cache.set(alert_cooldown_key, True, timeout=_AUTH_ALERT_COOLDOWN)

    # Reset counter after alert
    cache.delete(cache_key)
    cache.delete(top_ips_key)

    return f"ALERT_SENT: {failure_count} auth failures, alert dispatched"


def record_auth_failure_metric(ip_address):
    """Increment the auth failure counter in cache for anomaly detection.

    Called from core.audit.log_auth_failure() to track failure counts
    without requiring a DB write on every failed login.
    """
    from django.core.cache import cache

    count_key = "security:auth_failures:count"
    top_ips_key = "security:auth_failures:top_ips"

    try:
        cache.incr(count_key)
    except ValueError:
        cache.set(count_key, 1, timeout=_AUTH_FAILURE_WINDOW)

    # Track per-IP counts for the alert
    try:
        top_ips = cache.get(top_ips_key, {})
        top_ips[ip_address] = top_ips.get(ip_address, 0) + 1
        cache.set(top_ips_key, top_ips, timeout=_AUTH_FAILURE_WINDOW)
    except (TypeError, ValueError):
        pass
