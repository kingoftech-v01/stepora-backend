"""
Custom middleware for Stepora.

Includes:
- OriginValidationMiddleware: reject requests from unknown origins
- SecurityHeadersMiddleware: CSP, Referrer-Policy, Permissions-Policy, COOP, CORP, COEP
- CacheControlMiddleware: no-store on authenticated API responses
- FetchMetadataMiddleware: Sec-Fetch-Site validation (defense-in-depth)
- LastActivityMiddleware: online status tracking
- RLSMiddleware: set PostgreSQL session variable for Row-Level Security
"""

import logging

from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


class OriginValidationMiddleware:
    """
    Validates that mutating API requests come from allowed origins.

    Only checks Origin/Referer headers on state-changing methods
    (POST, PUT, PATCH, DELETE).  Safe methods (GET, HEAD, OPTIONS)
    are always allowed through -- browsers never send Origin on
    same-origin navigations, and CSRF-style attacks only apply to
    mutating requests.

    Exempt from validation:
    - Safe HTTP methods (GET, HEAD, OPTIONS)
    - Health check endpoints (/health/)
    - Stripe webhooks (/api/subscriptions/webhook/)
    - Native mobile app requests (X-Client-Platform: native/ios/android/capacitor)
    - Internal IPs (127.0.0.1, 10.x.x.x -- ALB health checks, ECS exec)
    - Localhost origins (development)
    """

    # Derive allowed origins from CORS_ALLOWED_ORIGINS setting, plus localhost
    # fallbacks for development. This avoids maintaining a hardcoded duplicate list.
    ALLOWED_ORIGINS = None  # populated in __init__

    EXEMPT_PATHS = [
        "/health/",
        "/api/subscriptions/webhook/",
    ]

    _NATIVE_PLATFORMS = frozenset(("native", "ios", "android", "capacitor"))
    _SAFE_METHODS = frozenset(("GET", "HEAD", "OPTIONS"))

    def __init__(self, get_response):
        self.get_response = get_response
        self.ALLOWED_ORIGINS = list(
            getattr(settings, "CORS_ALLOWED_ORIGINS", [])
        ) + ["http://localhost", "http://127.0.0.1"]

    def __call__(self, request):
        # 1. Safe methods never need origin validation
        if request.method in self._SAFE_METHODS:
            return self.get_response(request)

        # 2. Skip exempt paths (health checks, Stripe webhooks)
        for path_prefix in self.EXEMPT_PATHS:
            if request.path.startswith(path_prefix):
                return self.get_response(request)

        # 3. Skip native mobile app requests
        platform = request.META.get("HTTP_X_CLIENT_PLATFORM", "").lower().strip()
        if platform in self._NATIVE_PLATFORMS:
            return self.get_response(request)

        # 4. Skip internal IPs (127.0.0.1, 10.x.x.x for ALB/ECS)
        remote_ip = self._get_remote_ip(request)
        # SECURITY: Only bypass for VPC CIDR 10.0.0.0/16, not all 10.x.x.x
        if remote_ip == "127.0.0.1" or remote_ip.startswith("10.0."):
            return self.get_response(request)

        # 5. Check Origin header
        origin = request.META.get("HTTP_ORIGIN", "")
        if origin:
            if self._is_allowed_origin(origin):
                return self.get_response(request)
            logger.warning(
                "Blocked request from disallowed origin: %s (path=%s, method=%s, ip=%s)",
                origin,
                request.path,
                request.method,
                remote_ip,
            )
            return JsonResponse(
                {"error": "Forbidden", "code": "invalid_origin"}, status=403
            )

        # 6. No Origin -- check Referer
        referer = request.META.get("HTTP_REFERER", "")
        if referer:
            if self._is_allowed_origin(referer):
                return self.get_response(request)
            logger.warning(
                "Blocked request with disallowed referer: %s (path=%s, method=%s, ip=%s)",
                referer,
                request.path,
                request.method,
                remote_ip,
            )
            return JsonResponse(
                {"error": "Forbidden", "code": "invalid_origin"}, status=403
            )

        # 7. Neither Origin nor Referer present on mutating request -- block
        logger.warning(
            "Blocked %s request with no Origin/Referer (path=%s, ip=%s)",
            request.method,
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
    - Cross-Origin-Embedder-Policy
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

    def __call__(self, request):
        response = self.get_response(request)

        # Always set transport/framing headers
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["Cross-Origin-Opener-Policy"] = "same-origin"
        response["Cross-Origin-Resource-Policy"] = "cross-origin"
        # COEP: "credentialless" allows cross-origin subresources (fonts, images)
        # without requiring CORS on every resource, while still enabling
        # crossOriginIsolated for SharedArrayBuffer/high-res timers.
        # Audit: #958
        response["Cross-Origin-Embedder-Policy"] = "credentialless"

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


class CacheControlMiddleware:
    """
    Sets Cache-Control headers on API responses to prevent browsers and
    proxies from caching sensitive authenticated data.

    - Authenticated API responses: Cache-Control: private, no-store
    - Unauthenticated API responses: Cache-Control: no-cache
    - Non-API responses: untouched (WhiteNoise handles static assets)

    Audit: #930, #931, #933
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only set cache headers on API responses
        if not request.path.startswith("/api/"):
            return response

        # Skip if a view already set Cache-Control explicitly
        if response.get("Cache-Control"):
            return response

        # Authenticated requests get strict no-store
        has_auth = request.META.get("HTTP_AUTHORIZATION", "").startswith("Bearer ")
        has_cookie = hasattr(request, "user") and getattr(
            request.user, "is_authenticated", False
        )

        if has_auth or has_cookie:
            response["Cache-Control"] = "private, no-store"
        else:
            response["Cache-Control"] = "no-cache"

        return response


class FetchMetadataMiddleware:
    """
    Validates Sec-Fetch-Site header on mutating requests as defense-in-depth.

    Browsers that support Fetch Metadata send Sec-Fetch-Site indicating
    the relationship between the request origin and the target. This
    middleware rejects cross-site mutating requests that bypass CORS
    preflight (e.g., form submissions from attacker sites).

    Policy:
    - Allow: same-origin, same-site, none (direct navigation/bookmarks)
    - Block: cross-site on mutating methods (POST, PUT, PATCH, DELETE)

    Exempt:
    - Safe methods (GET, HEAD, OPTIONS) — no state change
    - Requests without Sec-Fetch-Site — older browsers, non-browser clients
    - Health checks, webhooks, native mobile requests

    Audit: #963
    """

    _SAFE_METHODS = frozenset(("GET", "HEAD", "OPTIONS"))
    _ALLOWED_FETCH_SITES = frozenset(("same-origin", "same-site", "none"))
    _EXEMPT_PATHS = [
        "/health/",
        "/api/subscriptions/webhook/",  # Stripe webhooks
    ]
    _NATIVE_PLATFORMS = frozenset(("native", "ios", "android", "capacitor"))

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only check mutating methods
        if request.method in self._SAFE_METHODS:
            return self.get_response(request)

        # Only check API paths
        if not request.path.startswith("/api/"):
            return self.get_response(request)

        # Exempt paths
        for path_prefix in self._EXEMPT_PATHS:
            if request.path.startswith(path_prefix):
                return self.get_response(request)

        # Skip native mobile requests
        platform = request.META.get("HTTP_X_CLIENT_PLATFORM", "").lower().strip()
        if platform in self._NATIVE_PLATFORMS:
            return self.get_response(request)

        # If Sec-Fetch-Site is absent, allow (non-browser client or older browser)
        fetch_site = request.META.get("HTTP_SEC_FETCH_SITE", "")
        if not fetch_site:
            return self.get_response(request)

        # Allow same-origin, same-site, and direct navigation
        if fetch_site in self._ALLOWED_FETCH_SITES:
            return self.get_response(request)

        # Block cross-site mutating requests
        logger.warning(
            "Blocked cross-site request: Sec-Fetch-Site=%s (path=%s, method=%s)",
            fetch_site,
            request.path,
            request.method,
        )
        return JsonResponse(
            {"error": "Forbidden", "code": "cross_site_request"}, status=403
        )


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

    _EXEMPT_PREFIXES = ("/api/auth/", "/api/users/me/", "/health/", "/admin/")

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
            from rest_framework_simplejwt.exceptions import (
                AuthenticationFailed,
                InvalidToken,
                TokenError,
            )

            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(auth_header[7:])
            user = jwt_auth.get_user(validated_token)
        except (TokenError, InvalidToken, AuthenticationFailed):
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


class AdminIPRestrictionMiddleware:
    """
    Restricts access to /admin/ paths to localhost, internal IPs (10.x.x.x),
    and any IPs listed in settings.ADMIN_ALLOWED_IPS.

    Returns 403 for all other IPs attempting to access Django admin.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Build the set of additionally allowed IPs from settings
        self._extra_ips = set(getattr(settings, "ADMIN_ALLOWED_IPS", []))

    def __call__(self, request):
        if request.path.startswith("/admin/"):
            remote_ip = request.META.get("REMOTE_ADDR", "")
            if not self._is_allowed(remote_ip):
                logger.warning(
                    "Blocked admin access from IP %s (path=%s)",
                    remote_ip,
                    request.path,
                )
                return JsonResponse(
                    {"error": "Forbidden"}, status=403
                )
        return self.get_response(request)

    def _is_allowed(self, ip):
        """Allow localhost, 10.x.x.x (AWS VPC / ALB), and configured IPs."""
        if ip in ("127.0.0.1", "::1"):
            return True
        if ip.startswith("10.0."):  # SECURITY: Restrict to VPC CIDR 10.0.0.0/16 only
            return True
        if ip in self._extra_ips:
            return True
        return False


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
            except (DatabaseError, ConnectionError, ValueError):
                logger.debug("Failed to update last activity", exc_info=True)

        return response


class RLSMiddleware:
    """
    Set PostgreSQL session variable ``app.current_user_id`` for Row-Level Security.

    Security (audit 1015): RLS policies on dreams, goals, tasks, ai_conversations,
    and ai_messages use ``current_setting('app.current_user_id', TRUE)`` to restrict
    data access to the row's owner. This middleware sets the session variable on every
    request so the policies can evaluate correctly.

    The variable is reset to empty string for unauthenticated requests to prevent
    stale values from a previous connection (PgBouncer pool_mode=transaction resets
    session state between transactions, but this is belt-and-suspenders).

    Place this middleware AFTER AuthenticationMiddleware in MIDDLEWARE so that
    ``request.user`` is already resolved.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        user_id = ""
        if user and getattr(user, "is_authenticated", False):
            user_id = str(user.id)

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.current_user_id', %s, TRUE)",
                    [user_id],
                )
        except Exception:
            # If this fails (e.g., DB down), let the request proceed anyway.
            # RLS failure is a defense-in-depth issue, not a primary control.
            logger.debug("Failed to set RLS session variable", exc_info=True)

        return self.get_response(request)


class APIVersionDeprecationMiddleware:
    """
    Add a ``Deprecation`` header to responses for unversioned API paths.

    Security (audit 1056): The unversioned ``/api/`` path serves the same
    endpoints as ``/api/v1/`` for backward compatibility. This middleware
    signals to clients that they should migrate to ``/api/v1/`` before the
    unversioned path is eventually removed or pinned.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only flag /api/ requests that are NOT /api/v1/ (or /api/schema/, /api/docs/)
        path = request.path
        if (
            path.startswith("/api/")
            and not path.startswith("/api/v1/")
            and not path.startswith("/api/schema")
            and not path.startswith("/api/docs")
            and not path.startswith("/api/redoc")
        ):
            response["Deprecation"] = "true"
            response["Sunset"] = "2027-01-01"
            response["Link"] = '</api/v1/>; rel="successor-version"'

        return response
