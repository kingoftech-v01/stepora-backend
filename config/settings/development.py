"""
Development settings - DEBUG=True
Uses SQLite, in-memory channels, local cache. No Docker/Redis/Postgres needed.
"""

from .base import *

DEBUG = True

_hosts = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]')
ALLOWED_HOSTS = [h.strip() for h in _hosts.split(',') if h.strip()]

# --- Database: SQLite for local development ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# --- Channels: in-memory (no Redis needed) ---
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# --- Cache: local memory (no Redis needed) ---
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'dreamplanner-dev',
    }
}

# --- Celery: run tasks synchronously (no Redis/worker needed) ---
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'

# --- CORS: allow all origins ---
CORS_ALLOW_ALL_ORIGINS = True

# --- Email: print to console ---
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# --- Security: disabled for local dev ---
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# --- Optional dev tools ---
try:
    import debug_toolbar  # noqa: F401
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1', 'localhost']
except ImportError:
    pass

try:
    import django_extensions  # noqa: F401
    INSTALLED_APPS += ['django_extensions']
except ImportError:
    pass

# --- Logging ---
LOGGING['root']['level'] = 'DEBUG'
LOGGING['loggers']['apps']['level'] = 'DEBUG'
