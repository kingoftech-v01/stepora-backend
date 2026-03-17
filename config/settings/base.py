"""
Django settings for Stepora backend.
Base settings shared across all environments.
"""

import os
from datetime import timedelta
from pathlib import Path

from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

# Load environment variables (graceful — may fail in containers where env is injected)
try:
    load_dotenv()
except PermissionError:
    pass

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# The insecure default is only for local development. Production settings
# validate that DJANGO_SECRET_KEY is set and will fail hard if missing.
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY", "django-insecure-dev-key-DO-NOT-USE-IN-PRODUCTION"
)

# DEBUG defaults to False for safety. Explicitly set to True in development.py.
DEBUG = False

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party apps
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "corsheaders",
    "channels",
    "django_celery_beat",
    "drf_spectacular",
    # JWT
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    # Custom authentication
    "core.auth.apps.DPAuthConfig",
    # Encryption
    "encrypted_model_fields",
    # Search
    "django_elasticsearch_dsl",
    "apps.search",
    # Local apps
    "apps.users",
    "apps.dreams",
    "apps.chat",
    "apps.conversations",
    "apps.notifications",
    "apps.calendar",
    "apps.subscriptions",
    "apps.store",
    "apps.leagues",
    "apps.circles",
    "apps.social",
    "apps.buddies",
    "apps.updates",
    "apps.blog",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "core.middleware.OriginValidationMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "core.authentication.CsrfExemptAPIMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.EmailVerificationMiddleware",
    "core.middleware.LastActivityMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database (overridden per environment in development.py / production.py)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "stepora"),
        "USER": os.getenv("DB_USER", "stepora"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# Custom user model
AUTH_USER_MODEL = "users.User"

# Authentication backends
AUTHENTICATION_BACKENDS = [
    "core.auth.backends.EmailAuthBackend",
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Supported languages (16 languages)
LANGUAGES = [
    ("en", _("English")),
    ("fr", _("French")),
    ("es", _("Spanish")),
    ("de", _("German")),
    ("pt", _("Portuguese")),
    ("it", _("Italian")),
    ("nl", _("Dutch")),
    ("ru", _("Russian")),
    ("ja", _("Japanese")),
    ("ko", _("Korean")),
    ("zh", _("Chinese")),
    ("ar", _("Arabic")),
    ("hi", _("Hindi")),
    ("tr", _("Turkish")),
    ("pl", _("Polish")),
    ("ht", _("Haitian Creole")),
]

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Upload size limits — 110 MB ceiling to accommodate 100 MB video uploads.
# Nginx should also enforce client_max_body_size at the same level.
DATA_UPLOAD_MAX_MEMORY_SIZE = 115_343_360  # ~110 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10_485_760  # 10 MB (files > this go to disk)

# Frontend URL for email links
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8100")

# Email
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@stepora.app")

# Web Push (VAPID)
WEBPUSH_SETTINGS = {
    "VAPID_PUBLIC_KEY": os.getenv("VAPID_PUBLIC_KEY", ""),
    "VAPID_PRIVATE_KEY": os.getenv("VAPID_PRIVATE_KEY", ""),
    "VAPID_ADMIN_EMAIL": os.getenv("VAPID_ADMIN_EMAIL", "admin@stepora.app"),
}

# Firebase Cloud Messaging (FCM)
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "core.authentication.ExpiringTokenAuthentication",  # Legacy fallback during migration
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardLimitOffsetPagination",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "auth": "5/minute",
        "auth_login": "5/minute",
        "auth_register": "5/minute",
        "auth_password": "5/minute",
        "api_read": "60/minute",
        "api_write": "30/minute",
        "upload": "10/minute",
        "anon": "20/minute",
        "ai_chat": "10/minute",
        "ai_plan": "5/minute",
        "ai_calibration": "15/minute",
        "subscription": "5/minute",
        "store_purchase": "5/minute",
        "search": "15/minute",
        "referral": "10/minute",
        "export": "1/day",
        "ai_motivation": "5/day",
        "ai_checkin": "10/day",
        "ai_notification_timing": "10/day",
    },
}

# DRF Spectacular - OpenAPI/Swagger Documentation
SPECTACULAR_SETTINGS = {
    "TITLE": "Stepora API",
    "DESCRIPTION": "API for dream and goal management with AI coaching, subscriptions, and gamification",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/",
    "TAGS": [
        {"name": "Auth", "description": "Authentication and registration"},
        {"name": "Users", "description": "User profile management"},
        {"name": "Dreams", "description": "Dream and goal management"},
        {"name": "Goals", "description": "Goal management within dreams"},
        {"name": "Tasks", "description": "Task management within goals"},
        {"name": "Obstacles", "description": "Obstacle tracking for dreams"},
        {"name": "Dream Templates", "description": "Pre-built dream templates"},
        {"name": "Conversations", "description": "AI chat conversations"},
        {"name": "Messages", "description": "Messages within AI conversations"},
        {"name": "Notifications", "description": "Push notifications and alerts"},
        {
            "name": "Notification Templates",
            "description": "Notification template management",
        },
        {"name": "Calendar", "description": "Calendar events and scheduling"},
        {"name": "Subscriptions", "description": "Stripe subscription management"},
        {"name": "Store", "description": "In-app store for cosmetic items"},
        {"name": "Leagues", "description": "League and ranking system"},
        {
            "name": "Circles",
            "description": "Dream Circles for group goals and challenges",
        },
        {"name": "Social", "description": "Friends, follows, and activity feed"},
        {"name": "Buddies", "description": "Dream Buddy accountability pairing"},
    ],
    "APPEND_COMPONENTS": {
        "schemas": {
            "ErrorResponse": {
                "type": "object",
                "properties": {
                    "detail": {
                        "type": "string",
                        "description": "Human-readable error message.",
                    },
                },
                "example": {"detail": "A descriptive error message."},
            },
            "ValidationErrorResponse": {
                "type": "object",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "example": {
                    "title": ["This field is required."],
                    "non_field_errors": ["Invalid data."],
                },
            },
            "SubscriptionRequiredResponse": {
                "type": "object",
                "properties": {
                    "detail": {"type": "string"},
                },
                "example": {
                    "detail": "This feature requires a Premium or Pro subscription.",
                },
            },
            "RateLimitResponse": {
                "type": "object",
                "properties": {
                    "detail": {"type": "string"},
                },
                "example": {
                    "detail": "Request was throttled. Expected available in 42 seconds.",
                },
            },
            "AIServiceErrorResponse": {
                "type": "object",
                "properties": {
                    "error": {"type": "string"},
                },
                "example": {
                    "error": "AI service returned an invalid response.",
                },
            },
            "PaymentServiceErrorResponse": {
                "type": "object",
                "properties": {
                    "detail": {"type": "string"},
                },
                "example": {
                    "detail": "Payment service error. Please try again later.",
                },
            },
        },
    },
}

# Channels (WebSocket)
# Use REDIS_URL (includes password) when available, fall back to REDIS_HOST/PORT for local dev
_channels_redis_url = os.getenv("REDIS_URL", "")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": (
                [_channels_redis_url]
                if _channels_redis_url
                else [
                    (
                        os.getenv("REDIS_HOST", "localhost"),
                        int(os.getenv("REDIS_PORT", 6379)),
                    )
                ]
            ),
            "capacity": 5000,  # Max messages per channel before oldest dropped
            "expiry": 300,  # Message expiry in seconds
            "group_expiry": 86400,  # Group membership expiry (24 hours)
        },
    },
}

# Celery Configuration
# REDIS_URL should include auth if Redis requires a password: redis://:password@host:port/db
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# Redis Cache
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://localhost:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_CLASS_KWARGS": {
                "max_connections": 50,
                "retry_on_timeout": True,
            },
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
        },
        "KEY_PREFIX": "stepora",
        "TIMEOUT": 300,  # 5 minutes default
    }
}

# Elasticsearch Configuration
ELASTICSEARCH_DSL = {
    "default": {
        "hosts": os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"),
    },
}

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ORGANIZATION_ID = os.getenv("OPENAI_ORGANIZATION_ID")
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TIMEOUT = 30

# Content Moderation Configuration
CONTENT_MODERATION = {
    "ENABLED": True,
    "OPENAI_MODERATION_ENABLED": bool(os.environ.get("OPENAI_API_KEY")),
    "CUSTOM_PATTERNS_ENABLED": True,
    "MODERATION_CACHE_TTL": 300,  # Cache moderation results for 5 minutes
}

# AI Usage Quotas (daily limits per subscription tier)
AI_QUOTAS = {
    "ENABLED": True,
    "REDIS_KEY_PREFIX": "ai_usage",
    "KEY_TTL_HOURS": 25,
    "DEFAULT_LIMITS": {
        "free": {
            "ai_chat": 0,
            "ai_plan": 0,
            "ai_calibration": 0,
            "ai_image": 0,
            "ai_voice": 0,
            "ai_background": 0,
        },
        "premium": {
            "ai_chat": 50,
            "ai_plan": 10,
            "ai_calibration": 50,
            "ai_image": 0,
            "ai_voice": 10,
            "ai_background": 3,
        },
        "pro": {
            "ai_chat": 150,
            "ai_plan": 25,
            "ai_calibration": 100,
            "ai_image": 3,
            "ai_voice": 20,
            "ai_background": 3,
        },
    },
}

# Stepora custom auth configuration
DP_AUTH = {
    "JWT_AUTH_REFRESH_COOKIE": "dp-refresh",
    "JWT_AUTH_SAMESITE": "Lax",
    "JWT_AUTH_SECURE": not DEBUG,
    "JWT_AUTH_COOKIE_PATH": "/api/auth/",
    "JWT_AUTH_COOKIE_DOMAIN": os.getenv(
        "JWT_AUTH_COOKIE_DOMAIN"
    ),  # None = host-only (same-origin proxy)
    "EMAIL_VERIFICATION": os.getenv("EMAIL_VERIFICATION", "mandatory"),
    "VERIFICATION_KEY_MAX_AGE": 60 * 60 * 24 * 3,  # 3 days
    "PASSWORD_RESET_MAX_AGE": 60 * 60,  # 1 hour
    "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID", ""),
    "APPLE_CLIENT_ID": os.getenv("APPLE_CLIENT_ID", ""),
}

# Google Calendar OAuth
GOOGLE_CALENDAR_CLIENT_ID = os.getenv("GOOGLE_CALENDAR_CLIENT_ID", "")
GOOGLE_CALENDAR_CLIENT_SECRET = os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET", "")
GOOGLE_CALENDAR_REDIRECT_URI = os.getenv(
    "GOOGLE_CALENDAR_REDIRECT_URI", ""
)

# SimpleJWT Configuration
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
}


# CORS Configuration
_cors_raw = os.getenv("CORS_ORIGIN", "http://localhost:3000")
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
CORS_ALLOW_CREDENTIALS = (
    True  # Required: frontend sends credentials: "include" cross-origin
)
CORS_EXPOSE_HEADERS = ["Content-Type", "X-Request-Id"]
CORS_ALLOWED_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]
CORS_ALLOWED_HEADERS = [
    "accept",
    "accept-encoding",
    "accept-language",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-client-platform",
]

# Stripe Configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Subscription plan Stripe Price IDs
STRIPE_PRICES = {
    "premium_monthly": os.getenv("STRIPE_PREMIUM_MONTHLY_PRICE_ID", ""),
    "premium_yearly": os.getenv("STRIPE_PREMIUM_YEARLY_PRICE_ID", ""),
    "pro_monthly": os.getenv("STRIPE_PRO_MONTHLY_PRICE_ID", ""),
    "pro_yearly": os.getenv("STRIPE_PRO_YEARLY_PRICE_ID", ""),
}

# Subscription pricing (for display and validation)
SUBSCRIPTION_PRICES = {
    "premium": {"monthly": 19.99, "yearly": 199.99},
    "pro": {"monthly": 29.99, "yearly": 299.99},
}

# Free tier limits — free users only get basic todo list (dreams/goals/tasks)
FREE_TIER_LIMITS = {
    "max_dreams": 3,
    "ai_access": False,
    "buddy_access": False,
    "circle_access": False,
    "vision_board_access": False,
    "league_access": False,
    "store_purchase": False,
    "social_feed": False,
    "advanced_notifications": False,
    "has_ads": True,
}

# Token expiration
TOKEN_EXPIRY_HOURS = int(os.getenv("TOKEN_EXPIRY_HOURS", 4))

# Security settings (will be overridden in production)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Session & Cookie security
SESSION_COOKIE_NAME = "dp_session"
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# Field-level encryption key for PII (required for encrypted model fields)
# MUST be set via FIELD_ENCRYPTION_KEY env var in all environments.
FIELD_ENCRYPTION_KEY = os.environ["FIELD_ENCRYPTION_KEY"]

# WebRTC TURN server (required for NAT traversal behind symmetric NATs)
# Set these env vars when deploying with a TURN server (e.g. coturn)
TURN_SERVER_URL = os.getenv("TURN_SERVER_URL", "")  # e.g. turn:turn.example.com:3478
TURN_SERVER_USERNAME = os.getenv("TURN_SERVER_USERNAME", "")
TURN_SERVER_CREDENTIAL = os.getenv("TURN_SERVER_CREDENTIAL", "")

# Agora.io (RTM messaging + RTC voice/video)
AGORA_APP_ID = os.getenv("AGORA_APP_ID", "")
AGORA_APP_CERTIFICATE = os.getenv("AGORA_APP_CERTIFICATE", "")

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "security.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 10,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "security": {
            "handlers": ["console", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
