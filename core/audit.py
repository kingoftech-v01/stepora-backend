"""
Security audit logging for Stepora.

Provides structured logging for security-relevant events:
- Authentication failures
- Permission denials
- Data exports
- Account changes
- Webhook events
"""

import logging

security_logger = logging.getLogger('security')


def _get_client_ip(request):
    """Extract client IP from request, respecting X-Forwarded-For."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def log_auth_failure(request, reason):
    """Log a failed authentication attempt."""
    ip = _get_client_ip(request)
    path = request.path
    security_logger.warning(
        'AUTH_FAILURE ip=%s path=%s reason=%s',
        ip, path, reason
    )


def log_auth_success(request, user):
    """Log a successful authentication."""
    ip = _get_client_ip(request)
    security_logger.info(
        'AUTH_SUCCESS ip=%s user_id=%s email=%s',
        ip, user.id, user.email
    )


def log_permission_denied(request, permission_class, view_name):
    """Log a permission denial."""
    ip = _get_client_ip(request)
    user_id = getattr(request.user, 'id', 'anonymous')
    security_logger.warning(
        'PERMISSION_DENIED ip=%s user_id=%s permission=%s view=%s path=%s',
        ip, user_id, permission_class, view_name, request.path
    )


def log_data_export(user, export_type='full'):
    """Log a data export request."""
    security_logger.info(
        'DATA_EXPORT user_id=%s email=%s type=%s',
        user.id, user.email, export_type
    )


def log_account_change(user, change_type, details=''):
    """Log account modifications (password change, email change, deletion)."""
    security_logger.info(
        'ACCOUNT_CHANGE user_id=%s email=%s type=%s details=%s',
        user.id, user.email, change_type, details
    )


def log_webhook_event(event_type, event_id, status, details=''):
    """Log incoming webhook events."""
    security_logger.info(
        'WEBHOOK event_type=%s event_id=%s status=%s details=%s',
        event_type, event_id, status, details
    )


def log_suspicious_input(request, field_name, original_value):
    """Log when sanitization strips potentially malicious content."""
    ip = _get_client_ip(request)
    user_id = getattr(request.user, 'id', 'anonymous')
    # Truncate value to avoid log injection
    truncated = str(original_value)[:200]
    security_logger.warning(
        'SUSPICIOUS_INPUT ip=%s user_id=%s field=%s value=%s',
        ip, user_id, field_name, truncated
    )


def log_content_moderation(request, text, result, context):
    """Log a content moderation event (flagged content)."""
    ip = _get_client_ip(request)
    user_id = getattr(request.user, 'id', 'anonymous')
    truncated = str(text)[:300]
    security_logger.warning(
        'CONTENT_MODERATION ip=%s user_id=%s context=%s source=%s categories=%s severity=%s text=%.300s',
        ip, user_id, context, result.detection_source,
        ','.join(result.categories), result.severity, truncated
    )


def log_ai_output_flagged(conversation_id, content_preview, reason):
    """Log when AI output fails safety check."""
    security_logger.warning(
        'AI_OUTPUT_FLAGGED conversation_id=%s reason=%s preview=%.200s',
        conversation_id, reason, str(content_preview)[:200]
    )


def log_jailbreak_attempt(request, text):
    """Log a detected jailbreak attempt (critical severity)."""
    ip = _get_client_ip(request)
    user_id = getattr(request.user, 'id', 'anonymous')
    security_logger.critical(
        'JAILBREAK_ATTEMPT ip=%s user_id=%s text=%.300s',
        ip, user_id, str(text)[:300]
    )
