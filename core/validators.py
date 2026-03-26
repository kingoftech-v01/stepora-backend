"""
Input validation utilities for Stepora.

Provides strict validation for UUIDs, pagination parameters,
search queries, and field-specific regex patterns.
"""

import ipaddress
import re
import socket
import unicodedata
import uuid
from urllib.parse import urlparse

from rest_framework.exceptions import ValidationError

from .sanitizers import sanitize_text

# Regex patterns for field validation
DISPLAY_NAME_PATTERN = re.compile(
    r"^[a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF _\-'.]{1,100}$"
)
LOCATION_PATTERN = re.compile(r"^[a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF ,\-'.()]{0,200}$")
COUPON_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{1,50}$")
TAG_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9\u00C0-\u024F _\-]{1,50}$")
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

MAX_PAGE_SIZE = 100
MAX_SEARCH_QUERY_LENGTH = 200
MAX_TEXT_FIELD_LENGTH = 5000


def validate_uuid(value):
    """Validate that a value is a valid UUID string."""
    if isinstance(value, uuid.UUID):
        return value
    if not isinstance(value, str) or not UUID_PATTERN.match(value):
        raise ValidationError("Invalid UUID format.")
    return uuid.UUID(value)


def validate_pagination_params(page, page_size):
    """Validate pagination parameters."""
    try:
        page = int(page) if page else 1
        page_size = int(page_size) if page_size else 20
    except (ValueError, TypeError):
        raise ValidationError("Invalid pagination parameters.")

    if page < 1:
        raise ValidationError("Page must be >= 1.")
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise ValidationError(f"Page size must be between 1 and {MAX_PAGE_SIZE}.")

    return page, page_size


def validate_search_query(query):
    """Validate and sanitize a search query string."""
    if not query or not isinstance(query, str):
        return ""

    query = sanitize_text(query).strip()

    if len(query) > MAX_SEARCH_QUERY_LENGTH:
        query = query[:MAX_SEARCH_QUERY_LENGTH]

    return query


def _normalize_to_ascii_skeleton(text):
    """
    Produce an ASCII 'skeleton' of text for homoglyph-resistant comparison.

    Applies NFKD decomposition to strip diacritics, then keeps only ASCII
    letters/digits. This makes 'а' (Cyrillic) and 'a' (Latin) compare equal,
    preventing confusable/homoglyph impersonation.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    # Strip combining marks (accents, diacritics)
    stripped = "".join(
        ch for ch in decomposed if not unicodedata.combining(ch)
    )
    # Keep only ASCII letters and digits for skeleton comparison
    return re.sub(r"[^a-zA-Z0-9]", "", stripped).lower()


def validate_display_name(value, exclude_user_id=None):
    """Validate display name against allowed characters and uniqueness."""
    value = sanitize_text(value)

    # V-680: Apply NFKC normalization to catch equivalent Unicode representations
    if value:
        value = unicodedata.normalize("NFKC", value)

    if value and not DISPLAY_NAME_PATTERN.match(value):
        raise ValidationError(
            "Display name contains invalid characters. "
            "Only letters, numbers, spaces, hyphens, apostrophes, and periods are allowed."
        )
    if value:
        from apps.users.models import User

        # EncryptedCharField doesn't support __iexact lookups, so we
        # fetch all non-blank display names and compare in Python.
        qs = User.objects.exclude(display_name="")
        if exclude_user_id:
            qs = qs.exclude(pk=exclude_user_id)

        # V-680: Normalize for case-insensitive comparison
        lower_value = unicodedata.normalize("NFKC", value).lower()
        # V-681: ASCII skeleton for homoglyph-resistant uniqueness check
        skeleton_value = _normalize_to_ascii_skeleton(value)

        for u in qs.only("pk", "display_name").iterator():
            if not u.display_name:
                continue
            existing_normalized = unicodedata.normalize("NFKC", u.display_name).lower()
            if existing_normalized == lower_value:
                raise ValidationError("This display name is already taken.")
            # Homoglyph check: if ASCII skeletons match, names are confusable
            if skeleton_value and _normalize_to_ascii_skeleton(u.display_name) == skeleton_value:
                raise ValidationError(
                    "This display name is too similar to an existing name."
                )
    return value


def validate_location(value):
    """Validate location string."""
    value = sanitize_text(value)
    if value and not LOCATION_PATTERN.match(value):
        raise ValidationError("Location contains invalid characters.")
    return value


def validate_coupon_code(value):
    """Validate coupon code format."""
    value = sanitize_text(value).strip()
    if value and not COUPON_CODE_PATTERN.match(value):
        raise ValidationError(
            "Coupon code must contain only letters, numbers, hyphens, and underscores."
        )
    return value


def validate_tag_name(value):
    """Validate tag name."""
    value = sanitize_text(value).strip()
    if not value:
        raise ValidationError("Tag name cannot be empty.")
    if not TAG_NAME_PATTERN.match(value):
        raise ValidationError("Tag name contains invalid characters.")
    return value


def validate_text_length(value, max_length=MAX_TEXT_FIELD_LENGTH, field_name="Text"):
    """Validate text field does not exceed max length after sanitization."""
    value = sanitize_text(value)
    if len(value) > max_length:
        raise ValidationError(f"{field_name} must be at most {max_length} characters.")
    return value


def validate_url_no_ssrf(url):
    """
    Validate that a URL is safe to fetch (no SSRF).
    Blocks private/reserved IP ranges, non-HTTP schemes, and localhost.

    Returns (url, resolved_ip) so callers can pin the connection to the
    validated IP address, preventing DNS rebinding (TOCTOU) attacks.
    """
    if not url or not isinstance(url, str):
        raise ValidationError("URL is required.")

    parsed = urlparse(url)

    # Only allow http/https schemes
    if parsed.scheme not in ("http", "https"):
        raise ValidationError("Only HTTP/HTTPS URLs are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise ValidationError("Invalid URL: no hostname.")

    # Block localhost and common loopback names
    blocked_hostnames = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}
    if hostname.lower() in blocked_hostnames:
        raise ValidationError("URLs pointing to localhost are not allowed.")

    # Resolve hostname and check for private/reserved IPs
    resolved_ip = None
    try:
        resolved = socket.getaddrinfo(
            hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
        for family, _type, _proto, _canonname, sockaddr in resolved:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
                raise ValidationError(
                    "URLs pointing to private/internal networks are not allowed."
                )
            if resolved_ip is None:
                resolved_ip = str(ip)
    except socket.gaierror:
        raise ValidationError("Could not resolve hostname.")

    return url, resolved_ip
