"""
Core views for health checks.

Security: The public /health/ endpoint returns only aggregate status
(healthy/unhealthy) without exposing service-level details (V-292).
Detailed service info is only returned when DEBUG is enabled.
"""

import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health_check(request):
    """
    Health check endpoint.

    Returns minimal information externally (V-292).
    Full service details only in DEBUG mode to avoid leaking
    infrastructure information (database status, cache status, latency).
    """
    db_status = _check_database()
    cache_status = _check_cache()

    all_up = db_status["status"] == "up" and cache_status["status"] == "up"
    overall = "healthy" if all_up else "unhealthy"
    http_code = 200 if all_up else 503

    # Only expose service-level details in DEBUG mode (V-292: Health check
    # should not expose infrastructure details publicly)
    if settings.DEBUG:
        health_status = {
            "status": overall,
            "timestamp": time.time(),
            "services": {
                "database": db_status,
                "cache": cache_status,
            },
        }
    else:
        health_status = {
            "status": overall,
        }

    return JsonResponse(health_status, status=http_code)


def liveness_check(request):
    """Simple liveness check - just confirms the app is running."""
    return JsonResponse({"status": "alive"})


def readiness_check(request):
    """Readiness check - confirms the app is ready to serve traffic."""
    db_status = _check_database()

    if db_status["status"] == "down":
        return JsonResponse(
            {"status": "not ready", "reason": "database unavailable"}, status=503
        )

    return JsonResponse({"status": "ready"})


def _check_database():
    """Check database connectivity."""
    start_time = time.time()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        latency = (time.time() - start_time) * 1000
        return {"status": "up", "latency_ms": round(latency, 2)}
    except Exception as e:
        logger.warning("Health check: database down: %s", e)
        result = {"status": "down"}
        if settings.DEBUG:
            result["error"] = str(e)
        return result


def _check_cache():
    """Check cache connectivity."""
    start_time = time.time()
    try:
        cache.set("health_check", "ok", 10)
        cache.get("health_check")
        latency = (time.time() - start_time) * 1000
        return {"status": "up", "latency_ms": round(latency, 2)}
    except Exception as e:
        logger.warning("Health check: cache down: %s", e)
        result = {"status": "down"}
        if settings.DEBUG:
            result["error"] = str(e)
        return result
