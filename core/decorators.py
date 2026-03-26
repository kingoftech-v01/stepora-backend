"""
Shared decorators for Stepora backend.

- retry_on_deadlock: Retry database operations that hit deadlocks.
- celery_distributed_lock: Prevent concurrent execution of periodic tasks.
"""

import functools
import logging
import time

from django.db import OperationalError

logger = logging.getLogger(__name__)


def celery_distributed_lock(timeout=None, key=None):
    """
    Decorator that prevents concurrent execution of a Celery task using
    a Redis-backed distributed lock via Django's cache framework.

    Usage::

        @shared_task(bind=True, max_retries=3)
        @celery_distributed_lock(timeout=600)
        def my_periodic_task(self):
            ...

    Args:
        timeout: Lock TTL in seconds. Defaults to the task's soft/hard time
                 limit or 900s (15 min) as a fallback.
        key: Custom cache key. Defaults to ``celery_lock:{task_name}``.

    If the lock is already held, the task logs a warning and returns
    without executing. The lock is automatically released when the
    task finishes (or expires after ``timeout``).
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from django.core.cache import cache

            # Determine the task name for the lock key
            task_name = getattr(args[0], "name", func.__qualname__) if args else func.__qualname__
            lock_key = key or f"celery_lock:{task_name}"

            # Determine timeout
            lock_timeout = timeout
            if lock_timeout is None:
                # Try to get from task's time_limit
                if args and hasattr(args[0], "request"):
                    lock_timeout = getattr(args[0], "soft_time_limit", None) or 900
                else:
                    lock_timeout = 900

            # Try to acquire lock (atomic add with nx semantics)
            acquired = cache.add(lock_key, "locked", lock_timeout)
            if not acquired:
                logger.warning(
                    "Skipping task %s — lock %s is already held",
                    task_name,
                    lock_key,
                )
                return None

            try:
                return func(*args, **kwargs)
            finally:
                try:
                    cache.delete(lock_key)
                except Exception:
                    logger.debug("Failed to release lock %s", lock_key, exc_info=True)

        return wrapper

    return decorator

# PostgreSQL deadlock SQLSTATE code
_DEADLOCK_ERROR_CODE = "40P01"

# Default retry parameters
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_RETRY_DELAY = 0.1  # seconds (initial backoff)


def retry_on_deadlock(max_retries=_DEFAULT_MAX_RETRIES, delay=_DEFAULT_RETRY_DELAY):
    """
    Decorator that retries a function when a PostgreSQL deadlock is detected.

    Usage on a DRF view method::

        @retry_on_deadlock()
        def perform_update(self, serializer):
            ...

    Usage on a service function::

        @retry_on_deadlock(max_retries=5, delay=0.2)
        def purchase_item(user, item):
            ...

    The decorator catches ``django.db.OperationalError`` with PostgreSQL
    SQLSTATE 40P01 (deadlock_detected) and retries with exponential backoff.
    After ``max_retries`` exhausted, the original exception is re-raised.

    Security note (audit 1040): Without this decorator, deadlocked
    transactions simply fail with a 500, which is exploitable for DoS
    if an attacker can reliably trigger lock contention.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except OperationalError as exc:
                    # Check if it's a deadlock error specifically
                    pg_code = getattr(exc, "pgcode", None) or _extract_pgcode(exc)
                    if pg_code != _DEADLOCK_ERROR_CODE:
                        raise  # Not a deadlock — propagate immediately

                    last_exc = exc
                    if attempt < max_retries:
                        backoff = delay * (2 ** attempt)
                        logger.warning(
                            "Deadlock detected in %s (attempt %d/%d), "
                            "retrying in %.2fs: %s",
                            func.__qualname__,
                            attempt + 1,
                            max_retries,
                            backoff,
                            exc,
                        )
                        time.sleep(backoff)
                    else:
                        logger.error(
                            "Deadlock in %s after %d retries, giving up: %s",
                            func.__qualname__,
                            max_retries,
                            exc,
                        )
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


def _extract_pgcode(exc):
    """Try to extract pgcode from psycopg2/psycopg OperationalError."""
    # psycopg2 stores it on the exception object
    if hasattr(exc, "pgcode"):
        return exc.pgcode
    # psycopg3 (psycopg) may wrap it differently
    cause = exc.__cause__
    if cause and hasattr(cause, "pgcode"):
        return cause.pgcode
    # Fallback: check the string representation
    err_str = str(exc)
    if "deadlock detected" in err_str.lower():
        return _DEADLOCK_ERROR_CODE
    return None
