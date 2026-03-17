"""
Custom middleware for Stepora.

Includes:
- OriginValidationMiddleware: reject requests from unknown origins
- SecurityHeadersMiddleware: CSP, Referrer-Policy, Permissions-Policy, COOP, CORP
- LastActivityMiddleware: online status tracking
"""

import logging

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


class OriginValidationMiddleware:
    """
    Validates that API requests come from allowed origins.
    Checks Origin and Referer headers to ensure requests originate
    from the Stepora frontend domains.

    Exempt from validation:
    - Health check endpoints (/health/)
    - Stripe webhooks (/api/subscriptions/webhook/)
    - Native mobile app requests (X-Client-Platform: native/ios/android/capacitor)
    - Internal IPs (127.0.0.1, 10.x.x.x — ALB health checks, ECS exec)
    - Localhost origins (development)
    """

    ALLOWED_ORIGINS = [
        "https://stepora.app",
        "https://api.stepora.app",
        "https://dp.jhpetitfrere.com",
        "https://dpapi.jhpetitfrere.com",
        "http://localhost",
        "http://127.0.0.1",
    ]

    EXEMPT_PATHS = [
        "/health/",
        "/api/subscriptions/webhook/",
    ]

    _NATIVE_PLATFORMS = frozenset(("native", "ios", "android", "capacitor"))

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Skip exempt paths (health checks, Stripe webhooks)
        for path_prefix in self.EXEMPT_PATHS:
            if request.path.startswith(path_prefix):
                return self.get_response(request)

        # 2. Skip native mobile app requests
        platform = request.META.get("HTTP_X_CLIENT_PLATFORM", "").lower().strip()
        if platform in self._NATIVE_PLATFORMS:
            return self.get_response(request)

        # 3. Skip internal IPs (127.0.0.1, 10.x.x.x for ALB/ECS)
        remote_ip = self._get_remote_ip(request)
        if remote_ip == "127.0.0.1" or remote_ip.startswith("10."):
            return self.get_response(request)

        # 4. Check Origin header
        origin = request.META.get("HTTP_ORIGIN", "")
        if origin:
            if self._is_allowed_origin(origin):
                return self.get_response(request)
            logger.warning(
                "Blocked request from disallowed origin: %s (path=%s, ip=%s)",
                origin,
                request.path,
                remote_ip,
            )
            return JsonResponse(
                {"error": "Forbidden", "code": "invalid_origin"}, status=403
            )

        # 5. No Origin — check Referer
        referer = request.META.get("HTTP_REFERER", "")
        if referer:
            if self._is_allowed_origin(referer):
                return self.get_response(request)
            logger.warning(
                "Blocked request with disallowed referer: %s (path=%s, ip=%s)",
                referer,
                request.path,
                remote_ip,
            )
            return JsonResponse(
                {"error": "Forbidden", "code": "invalid_origin"}, status=403
            )

        # 6. Neither Origin nor Referer present — block
        logger.warning(
            "Blocked request with no Origin/Referer (path=%s, ip=%s)",
            request.path,
            remote_ip,
        )
        return JsonResponse(
            {"error": "Forbidden", "code": "invalid_origin"}, status=403
        )

    def _get_remote_ip(self, request):
        """Get the direct remote IP (not X-Forwarded-For) for internal IP checks."""
        return request.META.get("REMOTE_ADDR", "")

    def _is_allowed_origin(self, value):
        """Check if the given origin or referer starts with any allowed origin."""
        for allowed in self.ALLOWED_ORIGINS:
            if value.startswith(allowed):
                return True
        return False


class SecurityHeadersMiddleware:
    """
    Adds security headers to every response.

    Headers added:
    - Content-Security-Policy
    - Referrer-Policy
    - Permissions-Policy
    - X-Content-Type-Options
    - X-Frame-Options
    - Cross-Origin-Opener-Policy
    - Cross-Origin-Resource-Policy
    """

    # Default CSP — can be overridden via settings.CSP_POLICY
    # Tightened: explicit domains instead of blanket wss:/https: wildcards
    DEFAULT_CSP = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "object-src 'none'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    # Public endpoints that social media crawlers and search engines need
    # to access cross-origin (e.g., Facebook/Twitter/Slack link unfurlers).
    _PUBLIC_PREFIXES = ("/api/blog/", "/api/seo/", "/robots.txt")

    def __call__(self, request):
        response = self.get_response(request)

        # Always set transport/framing headers
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["Cross-Origin-Opener-Policy"] = "same-origin"

        # Cross-Origin-Resource-Policy:
        # - "cross-origin" for public endpoints (blog, SEO) so social media
        #   crawlers and search engines can fetch these resources.
        # - "same-site" for everything else (authenticated API, admin).
        if any(request.path.startswith(p) for p in self._PUBLIC_PREFIXES):
            response["Cross-Origin-Resource-Policy"] = "cross-origin"
        else:
            response["Cross-Origin-Resource-Policy"] = "same-site"

        # CSP and Permissions-Policy only apply to HTML documents.
        # Setting them on JSON API responses is meaningless and can cause
        # browsers to apply a second, more restrictive policy to the page.
        content_type = response.get("Content-Type", "")
        is_api = request.path.startswith("/api/") and "text/html" not in content_type
        if not is_api:
            csp = getattr(settings, "CSP_POLICY", self.DEFAULT_CSP)
            response["Content-Security-Policy"] = csp
            response["Permissions-Policy"] = (
                "geolocation=(), microphone=(self), camera=(self), payment=()"
            )

        # HSTS — enforce HTTPS for 1 year, include subdomains
        if not settings.DEBUG:
            response["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        return response


class EmailVerificationMiddleware:
    """
    Blocks authenticated users with unverified email from accessing the platform.
    Returns 403 with code 'email_not_verified' so the frontend can show a gate.

    Since DRF handles JWT auth inside views (not Django middleware), this
    middleware authenticates the JWT token itself to check the user.

    Exempt paths (users need these before verifying):
    - /api/auth/        (login, register, verify-email, token refresh)
    - /api/users/me/    (frontend needs profile to check emailVerified)
    - /health/          (health checks)
    - /admin/           (Django admin)
    - Non-API paths     (static, media, etc.)
    """

    _EXEMPT_PREFIXES = (
        "/api/auth/",
        "/api/users/me/",
        "/api/blog/",
        "/api/seo/",
        "/health/",
        "/admin/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only check API paths
        if not request.path.startswith("/api/"):
            return self.get_response(request)

        # Skip exempt paths
        for prefix in self._EXEMPT_PREFIXES:
            if request.path.startswith(prefix):
                return self.get_response(request)

        # Try to identify the user from JWT token
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return self.get_response(request)

        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication

            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(auth_header[7:])
            user = jwt_auth.get_user(validated_token)
        except Exception:
            # Invalid token — let DRF handle the 401
            return self.get_response(request)

        # Check email verification
        if not user.email_addresses.filter(verified=True, primary=True).exists():
            from django.http import JsonResponse

            return JsonResponse(
                {
                    "detail": "Please verify your email address to use the platform.",
                    "code": "email_not_verified",
                },
                status=403,
            )

        return self.get_response(request)


class LastActivityMiddleware:
    """
    Updates user.last_seen and user.is_online on every authenticated request.
    Throttled to max once per minute per user to avoid DB load.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if hasattr(request, "user") and request.user.is_authenticated:
            user_id = str(request.user.id)

            # Throttle using Django cache (shared across workers) — once per 60s
            try:
                from django.core.cache import cache

                cache_key = f"last_activity_{user_id}"
                if not cache.get(cache_key):
                    cache.set(cache_key, True, timeout=60)
                    from apps.users.models import User

                    User.objects.filter(id=request.user.id).update(
                        is_online=True,
                        last_seen=timezone.now(),
                    )
            except Exception:
                logger.debug("Failed to update last activity", exc_info=True)

        return response
