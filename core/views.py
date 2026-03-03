"""
Core views for health checks.
"""

import logging

from django.conf import settings
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import time

logger = logging.getLogger(__name__)


def health_check(request):
    """Complete health check including database and cache."""
    health_status = {
        'status': 'healthy',
        'timestamp': time.time(),
        'services': {
            'database': _check_database(),
            'cache': _check_cache(),
        }
    }

    # Determine overall status
    if not all(service['status'] == 'up' for service in health_status['services'].values()):
        health_status['status'] = 'unhealthy'
        return JsonResponse(health_status, status=503)

    return JsonResponse(health_status)


def liveness_check(request):
    """Simple liveness check - just confirms the app is running."""
    return JsonResponse({'status': 'alive'})


def readiness_check(request):
    """Readiness check - confirms the app is ready to serve traffic."""
    db_status = _check_database()

    if db_status['status'] == 'down':
        return JsonResponse({
            'status': 'not ready',
            'reason': 'database unavailable'
        }, status=503)

    return JsonResponse({'status': 'ready'})


def _check_database():
    """Check database connectivity."""
    start_time = time.time()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        latency = (time.time() - start_time) * 1000
        return {
            'status': 'up',
            'latency_ms': round(latency, 2)
        }
    except Exception as e:
        logger.warning("Health check: database down: %s", e)
        result = {'status': 'down'}
        if settings.DEBUG:
            result['error'] = str(e)
        return result


def _check_cache():
    """Check cache connectivity."""
    start_time = time.time()
    try:
        cache.set('health_check', 'ok', 10)
        cache.get('health_check')
        latency = (time.time() - start_time) * 1000
        return {
            'status': 'up',
            'latency_ms': round(latency, 2)
        }
    except Exception as e:
        logger.warning("Health check: cache down: %s", e)
        result = {'status': 'down'}
        if settings.DEBUG:
            result['error'] = str(e)
        return result
