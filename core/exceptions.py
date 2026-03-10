"""
Custom exception handler for DRF.
"""

from django.utils.translation import gettext as _
from rest_framework.views import exception_handler


def _extract_message(detail):
    """Extract a clean human-readable message from DRF exception detail.

    DRF detail can be:
    - str / ErrorDetail  → use directly
    - list[ErrorDetail]  → first item
    - dict               → non_field_errors first, then first field error
    """
    if isinstance(detail, list):
        return str(detail[0]) if detail else "Unknown error"
    if isinstance(detail, dict):
        # Prefer non_field_errors (general validation errors)
        nfe = detail.get("non_field_errors")
        if nfe and isinstance(nfe, list):
            return str(nfe[0])
        # Fall back to first field error
        for errors in detail.values():
            if isinstance(errors, list) and errors:
                return str(errors[0])
            return str(errors)
    # str or ErrorDetail — str() gives the human-readable form
    return str(detail)


def custom_exception_handler(exc, context):
    """Custom exception handler for DRF."""
    import logging

    from django.conf import settings

    logger = logging.getLogger("security")

    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        detail = getattr(exc, "detail", None)

        error_code = getattr(exc, "default_code", "error")

        # Check if the exception carries a specific code (e.g. from permission .code attr)
        if hasattr(detail, "code") and detail.code:
            error_code = str(detail.code)

        # Extract a clean human-readable message from DRF's detail structure.
        # detail can be: str, list[ErrorDetail], or dict[str, list[ErrorDetail]]
        message = _extract_message(detail) if detail is not None else str(exc)

        # In production, hide internal error details for 500 errors
        if not settings.DEBUG and response.status_code >= 500:
            logger.error("Internal error: %s", message, exc_info=exc)
            message = _("An internal error occurred. Please try again later.")

        # Customize the response data with a consistent format
        response.data = {
            "error": message,
            "code": str(error_code),
            "status_code": response.status_code,
        }

        # Include structured field errors so the frontend can display per-field messages
        if isinstance(detail, dict):
            field_errors = {}
            for key, val in detail.items():
                if key == "non_field_errors":
                    continue
                if isinstance(val, list):
                    field_errors[key] = [str(e) for e in val]
                else:
                    field_errors[key] = [str(val)]
            if field_errors:
                response.data["field_errors"] = field_errors

        # Enrich subscription-related 403s with tier and feature info
        if error_code == "subscription_required" and response.status_code == 403:
            # Check the exception itself first (e.g. from DailyAIQuotaThrottle)
            if hasattr(exc, "required_tier"):
                response.data["required_tier"] = exc.required_tier
                response.data["feature_name"] = getattr(exc, "feature_name", "")
            else:
                # Fall back to permission class attributes
                view = context.get("view")
                if view:
                    for perm in view.get_permissions():
                        if getattr(perm, "code", None) == "subscription_required":
                            response.data["required_tier"] = getattr(
                                perm, "required_tier", "premium"
                            )
                            response.data["feature_name"] = getattr(
                                perm, "feature_name", ""
                            )
                            break

        # Enrich daily quota 429s with usage info and reset time
        if (
            response.status_code == 429
            and getattr(exc, "default_code", "") == "daily_quota_exceeded"
        ):
            response.data["code"] = "daily_quota_exceeded"
            usage_info = getattr(exc, "usage_info", {})
            response.data["category"] = getattr(exc, "category", "")
            response.data["limit"] = usage_info.get("limit", 0)
            response.data["used"] = usage_info.get("used", 0)
            response.data["remaining"] = usage_info.get("remaining", 0)
            try:
                from core.ai_usage import AIUsageTracker

                response.data["reset_at"] = AIUsageTracker.get_reset_time().isoformat()
            except Exception:
                pass

    return response


class OpenAIError(Exception):
    """Custom exception for OpenAI API errors."""


class ValidationError(Exception):
    """Custom exception for validation errors."""


class NotificationError(Exception):
    """Custom exception for notification errors."""
