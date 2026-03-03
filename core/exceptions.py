"""
Custom exception handler for DRF.
"""

from django.utils.translation import gettext as _
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """Custom exception handler for DRF."""
    import logging
    from django.conf import settings

    logger = logging.getLogger('security')

    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Build a human-readable error message
        detail = getattr(exc, 'detail', None)
        if detail is not None:
            message = str(detail)
        else:
            message = str(exc)

        error_code = getattr(exc, 'default_code', 'error')

        # In production, hide internal error details for 500 errors
        if not settings.DEBUG and response.status_code >= 500:
            logger.error("Internal error: %s", message, exc_info=exc)
            message = _('An internal error occurred. Please try again later.')

        # Customize the response data with a consistent format
        response.data = {
            'error': message,
            'code': str(error_code),
            'status_code': response.status_code,
        }

    return response


class OpenAIError(Exception):
    """Custom exception for OpenAI API errors."""
    pass


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class NotificationError(Exception):
    """Custom exception for notification errors."""
    pass
