"""
Custom middleware for DreamPlanner.

Includes:
- SecurityHeadersMiddleware: CSP, Referrer-Policy, Permissions-Policy, COOP, CORP
- LastActivityMiddleware: online status tracking
"""

import logging
import time
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


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

    def __call__(self, request):
        response = self.get_response(request)

        csp = getattr(settings, 'CSP_POLICY', self.DEFAULT_CSP)
        response['Content-Security-Policy'] = csp
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = (
            'geolocation=(), microphone=(self), camera=(self), payment=()'
        )
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Cross-Origin-Opener-Policy'] = 'same-origin'
        response['Cross-Origin-Resource-Policy'] = 'cross-origin'

        # HSTS — enforce HTTPS for 1 year, include subdomains
        if not settings.DEBUG:
            response['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains; preload'
            )

        return response


class LastActivityMiddleware:
    """
    Updates user.last_seen and user.is_online on every authenticated request.
    Throttled to max once per minute per user to avoid DB load.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._cache = {}  # user_id -> last_update_timestamp

    def __call__(self, request):
        response = self.get_response(request)

        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = request.user.id
            now = time.time()

            # Throttle: update at most once per 60 seconds
            last_update = self._cache.get(user_id, 0)
            if now - last_update >= 60:
                self._cache[user_id] = now
                try:
                    from apps.users.models import User
                    User.objects.filter(id=user_id).update(
                        is_online=True,
                        last_seen=timezone.now(),
                    )
                except Exception:
                    logger.debug("Failed to update last activity", exc_info=True)

        return response
