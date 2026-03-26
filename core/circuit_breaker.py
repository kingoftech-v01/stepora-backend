"""
Circuit breaker pattern for external service calls.

Prevents cascading failures when external services (OpenAI, Stripe, Agora,
Google Calendar) go down. Instead of piling up timeout requests, the circuit
breaker "opens" after consecutive failures and immediately rejects calls for
a cooldown period.

Security audit fix: V-326 (No circuit breaker for external services).

States:
- CLOSED:    Normal operation. Calls go through.
- OPEN:      Service is down. Calls are immediately rejected.
- HALF_OPEN: After cooldown, allow a single probe call to test recovery.

Usage:
    from core.circuit_breaker import circuit_breaker

    @circuit_breaker("openai")
    def call_openai():
        ...

    # Or use as a context manager:
    with CircuitBreaker("stripe"):
        stripe.Customer.create(...)
"""

import logging
import threading
import time
from functools import wraps

logger = logging.getLogger(__name__)

# Default configuration per service
_DEFAULT_CONFIG = {
    "failure_threshold": 5,     # failures before opening
    "recovery_timeout": 60,     # seconds to wait before half-open probe
    "success_threshold": 2,     # successes in half-open to close again
}

# Per-service overrides
SERVICE_CONFIG = {
    "openai": {
        "failure_threshold": 3,
        "recovery_timeout": 30,
        "success_threshold": 1,
    },
    "stripe": {
        "failure_threshold": 5,
        "recovery_timeout": 60,
        "success_threshold": 2,
    },
    "agora": {
        "failure_threshold": 5,
        "recovery_timeout": 45,
        "success_threshold": 1,
    },
    "google_calendar": {
        "failure_threshold": 5,
        "recovery_timeout": 60,
        "success_threshold": 2,
    },
}

# States
CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half_open"


class CircuitBreakerError(Exception):
    """Raised when the circuit breaker is open and the call is rejected."""

    def __init__(self, service_name, time_until_retry=None):
        self.service_name = service_name
        self.time_until_retry = time_until_retry
        msg = f"Circuit breaker OPEN for '{service_name}'."
        if time_until_retry is not None:
            msg += f" Retry in {time_until_retry:.0f}s."
        super().__init__(msg)


class CircuitBreaker:
    """
    Thread-safe circuit breaker for a named external service.

    Can be used as a decorator, context manager, or called directly.
    """

    # Shared state across all instances for the same service
    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, service_name, **kwargs):
        with cls._lock:
            if service_name not in cls._instances:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instances[service_name] = instance
            return cls._instances[service_name]

    def __init__(self, service_name, **kwargs):
        if self._initialized:
            return
        self._initialized = True

        self.service_name = service_name
        config = {**_DEFAULT_CONFIG, **SERVICE_CONFIG.get(service_name, {}), **kwargs}
        self.failure_threshold = config["failure_threshold"]
        self.recovery_timeout = config["recovery_timeout"]
        self.success_threshold = config["success_threshold"]

        self._state = CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0
        self._state_lock = threading.Lock()

    @property
    def state(self):
        with self._state_lock:
            if self._state == OPEN:
                # Check if recovery timeout has elapsed
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = HALF_OPEN
                    self._success_count = 0
                    logger.info(
                        "Circuit breaker %s: OPEN -> HALF_OPEN (probe allowed)",
                        self.service_name,
                    )
            return self._state

    def _record_success(self):
        with self._state_lock:
            if self._state == HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(
                        "Circuit breaker %s: HALF_OPEN -> CLOSED (service recovered)",
                        self.service_name,
                    )
            elif self._state == CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    def _record_failure(self, exc=None):
        with self._state_lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == HALF_OPEN:
                # Probe failed — go back to OPEN
                self._state = OPEN
                logger.warning(
                    "Circuit breaker %s: HALF_OPEN -> OPEN (probe failed: %s)",
                    self.service_name,
                    exc,
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = OPEN
                logger.error(
                    "Circuit breaker %s: CLOSED -> OPEN after %d consecutive failures",
                    self.service_name,
                    self._failure_count,
                )

    def _check_state(self):
        """Check if a call is allowed. Raises CircuitBreakerError if not."""
        current = self.state
        if current == OPEN:
            time_until = self.recovery_timeout - (
                time.monotonic() - self._last_failure_time
            )
            raise CircuitBreakerError(
                self.service_name, max(0, time_until)
            )

    def call(self, func, *args, **kwargs):
        """Execute func through the circuit breaker."""
        self._check_state()
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except CircuitBreakerError:
            raise
        except Exception as exc:
            self._record_failure(exc)
            raise

    async def async_call(self, func, *args, **kwargs):
        """Execute an async func through the circuit breaker."""
        self._check_state()
        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except CircuitBreakerError:
            raise
        except Exception as exc:
            self._record_failure(exc)
            raise

    # Context manager interface
    def __enter__(self):
        self._check_state()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._record_success()
        elif exc_type is not CircuitBreakerError:
            self._record_failure(exc_val)
        return False  # Do not suppress exceptions

    async def __aenter__(self):
        self._check_state()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._record_success()
        elif exc_type is not CircuitBreakerError:
            self._record_failure(exc_val)
        return False

    def reset(self):
        """Manually reset the circuit breaker to closed state."""
        with self._state_lock:
            self._state = CLOSED
            self._failure_count = 0
            self._success_count = 0
            logger.info("Circuit breaker %s: manually reset to CLOSED", self.service_name)


def circuit_breaker(service_name, **kwargs):
    """
    Decorator to wrap a function with circuit breaker protection.

    Usage:
        @circuit_breaker("openai")
        def call_openai_api(...):
            ...
    """
    cb = CircuitBreaker(service_name, **kwargs)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kw):
            return cb.call(func, *args, **kw)

        wrapper.circuit_breaker = cb
        return wrapper

    return decorator


def async_circuit_breaker(service_name, **kwargs):
    """
    Decorator for async functions with circuit breaker protection.

    Usage:
        @async_circuit_breaker("openai")
        async def call_openai_api(...):
            ...
    """
    cb = CircuitBreaker(service_name, **kwargs)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kw):
            return await cb.async_call(func, *args, **kw)

        wrapper.circuit_breaker = cb
        return wrapper

    return decorator
