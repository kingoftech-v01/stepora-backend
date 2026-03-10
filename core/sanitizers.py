"""
XSS sanitization utilities for user-generated content.

Uses nh3 (Rust-based HTML sanitizer) — replacement for deprecated bleach library.
"""

from typing import Optional

import nh3

# Allowed HTML tags for rich text fields (if needed)
ALLOWED_TAGS = {"p", "br", "strong", "em", "u", "ul", "ol", "li", "a"}

# Allowed attributes for tags
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
}

# Allowed URL schemes
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def sanitize_text(text: Optional[str], strip: bool = True) -> str:
    """
    Remove all HTML tags from text.
    Use this for plain text fields like titles and names.

    Args:
        text: Input text to sanitize
        strip: If True, remove tags entirely (nh3.clean with no tags).

    Returns:
        Sanitized text with all HTML removed
    """
    if text is None:
        return ""

    if not isinstance(text, str):
        text = str(text)

    import html

    return html.unescape(nh3.clean(text, tags=set()))


def sanitize_html(text: Optional[str], extra_tags: set = None) -> str:
    """
    Sanitize HTML content, keeping only safe tags.
    Use this for rich text fields that need basic formatting.

    Args:
        text: Input HTML to sanitize
        extra_tags: Additional tags to allow beyond the defaults

    Returns:
        Sanitized HTML with only allowed tags
    """
    if text is None:
        return ""

    if not isinstance(text, str):
        text = str(text)

    tags = ALLOWED_TAGS.copy()
    if extra_tags:
        tags.update(extra_tags)

    return nh3.clean(
        text,
        tags=tags,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
    )


def sanitize_url(url: Optional[str]) -> str:
    """
    Validate and sanitize a URL.
    Only allows http, https, and mailto schemes.

    Args:
        url: Input URL to sanitize

    Returns:
        Sanitized URL or empty string if invalid
    """
    if url is None:
        return ""

    if not isinstance(url, str):
        return ""

    url = url.strip()

    # Check if URL uses allowed protocol
    url_lower = url.lower()
    if not any(url_lower.startswith(f"{proto}://") for proto in ["http", "https"]):
        if not url_lower.startswith("mailto:"):
            return ""

    # Basic XSS prevention
    dangerous_patterns = [
        "javascript:",
        "data:",
        "vbscript:",
        "<script",
        "onerror=",
        "onclick=",
        "onload=",
    ]

    for pattern in dangerous_patterns:
        if pattern in url_lower:
            return ""

    return url


def sanitize_json_values(data: dict, keys_to_sanitize: list = None) -> dict:
    """
    Recursively sanitize string values in a dictionary.

    Args:
        data: Dictionary to sanitize
        keys_to_sanitize: Specific keys to sanitize (all if None)

    Returns:
        Dictionary with sanitized string values
    """
    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            if keys_to_sanitize is None or key in keys_to_sanitize:
                result[key] = sanitize_text(value)
            else:
                result[key] = value
        elif isinstance(value, dict):
            result[key] = sanitize_json_values(value, keys_to_sanitize)
        elif isinstance(value, list):
            result[key] = [
                (
                    sanitize_json_values(item, keys_to_sanitize)
                    if isinstance(item, dict)
                    else sanitize_text(item) if isinstance(item, str) else item
                )
                for item in value
            ]
        else:
            result[key] = value

    return result


class SanitizedCharField:
    """
    Mixin for DRF serializer fields that automatically sanitizes input.

    Usage in serializer:
        title = serializers.CharField(max_length=255)

        def validate_title(self, value):
            return sanitize_text(value)
    """


def create_sanitizing_serializer_mixin(fields_to_sanitize: list):
    """
    Create a mixin class that sanitizes specified fields.

    Usage:
        class MySerializer(SanitizingMixin, serializers.ModelSerializer):
            class Meta:
                model = MyModel
                fields = ['title', 'description']

            SANITIZE_FIELDS = ['title', 'description']
    """

    class SanitizingMixin:
        def to_internal_value(self, data):
            # Sanitize specified fields before validation
            if isinstance(data, dict):
                for field in fields_to_sanitize:
                    if field in data and isinstance(data[field], str):
                        data[field] = sanitize_text(data[field])
            return super().to_internal_value(data)

    return SanitizingMixin
