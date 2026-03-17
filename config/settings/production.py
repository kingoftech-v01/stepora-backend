"""
Production settings
"""

import sys

from .base import *

try:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    _has_sentry = True
except ImportError:
    _has_sentry = False

DEBUG = False

# ── Required environment variable validation ─────────────────────────
# These MUST be set in production. Fail hard at startup if missing.
_REQUIRED_ENV_VARS = [
    "DJANGO_SECRET_KEY",
    "ALLOWED_HOSTS",
    "DB_PASSWORD",
]

_missing = [var for var in _REQUIRED_ENV_VARS if not os.getenv(var)]
if _missing and "collectstatic" not in sys.argv:
    raise RuntimeError(
        f"Missing required environment variables for production: {', '.join(_missing)}. "
        f"Set them in your .env file or deployment environment."
    )

ALLOWED_HOSTS = [
    h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()
]
if not ALLOWED_HOSTS and "collectstatic" not in sys.argv:
    raise RuntimeError(
        "ALLOWED_HOSTS is empty. Set ALLOWED_HOSTS env var to a comma-separated list of valid hostnames."
    )

# Security settings
# SSL redirect disabled — external nginx handles TLS termination
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Strict cookie security in production
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# JWT refresh cookie must be Secure + SameSite=None in production
# (cross-origin: stepora.app frontend → api.stepora.app backend)
# SameSite=Lax blocks cookies on cross-origin POST — breaks token refresh
DP_AUTH["JWT_AUTH_SECURE"] = True
DP_AUTH["JWT_AUTH_SAMESITE"] = "None"

# CORS - Strict in production (frontend and backend on separate servers)
CORS_ALLOW_ALL_ORIGINS = False
_cors_raw = os.getenv("CORS_ORIGIN", "")
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
CORS_ALLOW_CREDENTIALS = True

# CloudFront domain for CORS (if serving frontend via CloudFront)
CLOUDFRONT_DOMAIN = os.environ.get("CLOUDFRONT_DOMAIN", "")
if CLOUDFRONT_DOMAIN:
    CORS_ALLOWED_ORIGINS.append(f"https://{CLOUDFRONT_DOMAIN}")

# ALB hostname for ALLOWED_HOSTS (ECS health checks come from the ALB)
_alb_hostname = os.environ.get("ALB_HOSTNAME", "")
if _alb_hostname:
    ALLOWED_HOSTS.append(_alb_hostname)

# CSRF trusted origins (required for cross-origin POST from frontend)
_csrf_raw = os.getenv("CSRF_TRUSTED_ORIGINS", os.getenv("CORS_ORIGIN", ""))
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_raw.split(",") if o.strip()]

# Static files (served via S3/CloudFront in production)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME") or os.getenv("AWS_S3_BUCKET")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME") or os.getenv("AWS_REGION", "eu-west-3")
AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_CLOUDFRONT_DOMAIN")
AWS_DEFAULT_ACL = None  # Required for S3 Block Public Access
AWS_S3_FILE_OVERWRITE = False
AWS_QUERYSTRING_AUTH = False  # Generate direct URLs (not pre-signed)
AWS_STATIC_LOCATION = "static"
AWS_MEDIA_LOCATION = "media"

# Use S3 for media files only; WhiteNoise serves static files from disk
# (collectstatic runs at Docker build time without AWS creds, so static
#  files live in /app/staticfiles/ and WhiteNoise serves them directly)
if AWS_STORAGE_BUCKET_NAME:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "location": AWS_MEDIA_LOCATION,
            },
        },
        # Static files served from disk by WhiteNoise ASGI wrapper (see config/asgi.py).
        # Use basic StaticFilesStorage — no manifest needed, collectstatic runs at
        # Docker build time without AWS creds so CompressedManifest would crash.
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
    _s3_domain = AWS_S3_CUSTOM_DOMAIN or f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
    STATIC_URL = "/static/"
    MEDIA_URL = f"https://{_s3_domain}/{AWS_MEDIA_LOCATION}/"

# OTA code signing — path to RSA public key for signature verification
OTA_PUBLIC_KEY_PATH = os.getenv("OTA_PUBLIC_KEY_PATH", "")

# Sentry error tracking
if _has_sentry and os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[DjangoIntegration()],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
        environment="production",
    )

# Logging — stdout-only for ECS (no file handlers)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "security": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Email (production uses real SMTP when configured)
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "").lower() in ("true", "1", "yes")
EMAIL_USE_TLS = not EMAIL_USE_SSL
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@stepora.app")

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    # SMTP not configured — use console backend to prevent crashes
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DP_AUTH["EMAIL_VERIFICATION"] = "none"
    import warnings

    warnings.warn(
        "EMAIL_HOST_USER / EMAIL_HOST_PASSWORD not set. "
        "Email verification is DISABLED. Set SMTP credentials for production.",
        stacklevel=1,
    )

# Database connection pooling
DATABASES["default"]["CONN_MAX_AGE"] = 600
DATABASES["default"]["OPTIONS"] = {
    "connect_timeout": 10,
    "options": "-c statement_timeout=30000",  # 30 seconds
    "sslmode": os.getenv("DB_SSLMODE", "require"),
}

# Elasticsearch — auto-sync only when an ES host is explicitly configured.
# On AWS (no ES instance) the env var is unset, so autosync stays off.
# On VPS (Docker ES container) the env var points to the ES service.
ELASTICSEARCH_DSL_AUTOSYNC = bool(os.getenv("ELASTICSEARCH_URL"))

# Sessions via Redis (shared across ECS tasks)
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# Redis connection for production (supports redis:// and rediss:// schemes)
_redis_url = os.getenv("REDIS_URL", "")
if _redis_url:
    CACHES["default"]["LOCATION"] = _redis_url
    CHANNEL_LAYERS["default"]["CONFIG"]["hosts"] = [_redis_url]
