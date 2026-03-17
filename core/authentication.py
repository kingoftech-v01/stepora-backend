"""
Token authentication backend for Django and DRF.

Security features:
- Token expiration (configurable via TOKEN_EXPIRY_HOURS)
- Bearer/Token prefix support for flexible API clients
- Conditional CSRF exemption only when token auth header is present
- Failed auth attempt logging
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed

security_logger = logging.getLogger("security")


class ExpiringTokenAuthentication(TokenAuthentication):
    """
    DRF Token authentication with expiration and Bearer keyword support.

    Tokens expire after TOKEN_EXPIRY_HOURS (default 24h).
    Accepts both 'Bearer' and 'Token' prefixes.
    """

    keyword = "Token"

    def authenticate(self, request):
        """Try both 'Token' and 'Bearer' prefixes."""
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")

        if auth_header.startswith("Bearer "):
            request.META["HTTP_AUTHORIZATION"] = "Token " + auth_header[7:]

        return super().authenticate(request)

    def authenticate_credentials(self, key):
        """Validate token and check expiration."""
        try:
            token = Token.objects.select_related("user").get(key=key)
        except Token.DoesNotExist:
            security_logger.warning("auth_failure: invalid token attempted")
            raise AuthenticationFailed("Invalid or expired token.")

        if not token.user.is_active:
            security_logger.warning(
                "auth_failure: inactive user token used, user_id=%s", token.user.id
            )
            raise AuthenticationFailed("User account is disabled.")

        expiry_hours = getattr(settings, "TOKEN_EXPIRY_HOURS", 24)
        if token.created < timezone.now() - timedelta(hours=expiry_hours):
            token.delete()
            security_logger.info("auth_token_expired: user_id=%s", token.user.id)
            raise AuthenticationFailed("Token has expired. Please log in again.")

        return (token.user, token)


class CsrfExemptAPIMiddleware:
    """
    Conditionally skip CSRF checks for /api/ routes that carry token auth.

    Security rationale: Token authentication via the Authorization header
    is immune to CSRF because browsers do not automatically attach it to
    cross-origin requests (unlike cookies). This middleware only exempts
    CSRF when a token is present; unauthenticated API requests still
    require CSRF protection. Admin routes always require CSRF.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/"):
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            if auth_header.startswith(("Token ", "Bearer ")):
                # Only exempt CSRF if the token value is long enough to be valid
                token_value = auth_header.split(" ", 1)[1] if " " in auth_header else ""
                if len(token_value) > 20:
                    setattr(request, "_dont_enforce_csrf_checks", True)
        return self.get_response(request)
