"""
Testing settings
"""

from .base import *

DEBUG = True

# Use in-memory SQLite for faster tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Password hashers (faster for tests)
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Celery eager execution (synchronous)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True


# Disable migrations in tests
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# Email backend (memory for tests)
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Logging (minimal in tests)
LOGGING["root"]["level"] = "ERROR"
LOGGING["loggers"]["apps"]["level"] = "ERROR"

# Redis (use fake Redis for tests)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# Enable search feature flag in tests (so existing search tests pass).
# Individual tests use @override_settings(USE_SEARCH=False) to test the disabled path.
USE_SEARCH = True

# Disable Elasticsearch auto-sync in tests (no ES server available)
ELASTICSEARCH_DSL_AUTOSYNC = False
ELASTICSEARCH_DSL_SIGNAL_PROCESSOR = (
    "django_elasticsearch_dsl.signals.BaseSignalProcessor"
)

# Set very high throttle rates in tests to prevent rate limit interference
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "10000/minute",
    "user": "10000/minute",
    "ai_chat": "10000/minute",
    "ai_plan": "10000/minute",
    "ai_calibration": "10000/minute",
    "ai_voice": "10000/minute",
    "ai_motivation": "10000/minute",
    "ai_checkin": "10000/minute",
    "ai_notification_timing": "10000/minute",
    "subscription": "10000/minute",
    "store_purchase": "10000/minute",
    "auth": "10000/minute",
    "auth_login": "10000/minute",
    "auth_register": "10000/minute",
    "auth_password": "10000/minute",
    "search": "10000/minute",
    "export": "10000/minute",
    "api_read": "10000/minute",
    "api_write": "10000/minute",
    "upload": "10000/minute",
    "referral": "10000/minute",
    "two_factor": "10000/minute",
    "email_verification": "10000/minute",
}
