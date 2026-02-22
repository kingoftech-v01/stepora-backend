"""
Custom exception handler for DRF.
"""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """Custom exception handler for DRF."""
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Customize the response data
        custom_response_data = {
            'error': True,
            'message': str(exc),
            'status_code': response.status_code,
        }

        # Add detail if available
        if hasattr(response, 'data') and isinstance(response.data, dict):
            if 'detail' in response.data:
                custom_response_data['detail'] = response.data['detail']
            else:
                custom_response_data['details'] = response.data

        response.data = custom_response_data

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
