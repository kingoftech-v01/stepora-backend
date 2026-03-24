"""
Maintenance mode middleware.

Returns HTTP 503 for all requests when maintenance mode is active.
Toggle via:
  - Redis cache: python manage.py maintenance on/off
  - Environment: MAINTENANCE_MODE=true

Health checks and admin are always exempt.
"""

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse


class MaintenanceMiddleware:
    """Return 503 for all requests when maintenance mode is active."""

    EXEMPT_PATHS = [
        "/health/",
        "/health/liveness/",
        "/health/readiness/",
        "/admin/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check maintenance mode (Redis cache first, then settings fallback)
        is_maintenance = cache.get("maintenance_mode", False) or getattr(
            settings, "MAINTENANCE_MODE", False
        )

        if is_maintenance:
            # Allow health checks and admin through
            for path in self.EXEMPT_PATHS:
                if request.path.startswith(path):
                    return self.get_response(request)

            return JsonResponse(
                {
                    "error": "Stepora is being updated. Please try again in a few minutes.",
                    "maintenance": True,
                    "retry_after": 30,
                },
                status=503,
                headers={"Retry-After": "30"},
            )

        return self.get_response(request)
