"""
Django settings for DreamPlanner backend.
Base settings shared across all environments.
"""

import os
from pathlib import Path
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-dev-key-change-in-production')

# Application definition
INSTALLED_APPS = [
    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Sites framework (required by allauth)
    'django.contrib.sites',

    # Third party apps
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'corsheaders',
    'channels',
    'django_celery_beat',
    'drf_spectacular',

    # Authentication
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.apple',
    'dj_rest_auth',
    'dj_rest_auth.registration',

    # Encryption
    'encrypted_model_fields',

    # Local apps
    'apps.users',
    'apps.dreams',
    'apps.conversations',
    'apps.notifications',
    'apps.calendar',
    'apps.subscriptions',
    'apps.store',
    'apps.leagues',
    'apps.circles',
    'apps.social',
    'apps.buddies',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.SecurityHeadersMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'core.authentication.CsrfExemptAPIMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'core.middleware.LastActivityMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database (overridden per environment in development.py / production.py)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'dreamplanner'),
        'USER': os.getenv('DB_USER', 'dreamplanner'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'password'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# Custom user model
AUTH_USER_MODEL = 'users.User'

# Sites framework
SITE_ID = 1

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Supported languages (15 languages)
LANGUAGES = [
    ('en', _('English')),
    ('fr', _('French')),
    ('es', _('Spanish')),
    ('pt', _('Portuguese')),
    ('ar', _('Arabic')),
    ('zh', _('Chinese')),
    ('hi', _('Hindi')),
    ('ja', _('Japanese')),
    ('de', _('German')),
    ('ru', _('Russian')),
    ('ko', _('Korean')),
    ('it', _('Italian')),
    ('tr', _('Turkish')),
    ('nl', _('Dutch')),
    ('pl', _('Polish')),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Frontend URL for email links
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:8100')

# Email
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@dreamplanner.app')

# Web Push (VAPID)
WEBPUSH_SETTINGS = {
    'VAPID_PUBLIC_KEY': os.getenv('VAPID_PUBLIC_KEY', ''),
    'VAPID_PRIVATE_KEY': os.getenv('VAPID_PRIVATE_KEY', ''),
    'VAPID_ADMIN_EMAIL': os.getenv('VAPID_ADMIN_EMAIL', 'admin@dreamplanner.app'),
}

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.authentication.ExpiringTokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/minute',
        'user': '100/minute',
        'ai_chat': '10/minute',
        'ai_plan': '5/minute',
        'subscription': '5/minute',
        'store_purchase': '5/minute',
        'auth': '5/minute',
        'search': '15/minute',
        'export': '1/day',
    },
}

# DRF Spectacular - OpenAPI/Swagger Documentation
SPECTACULAR_SETTINGS = {
    'TITLE': 'DreamPlanner API',
    'DESCRIPTION': 'API for dream and goal management with AI coaching, subscriptions, and gamification',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/api/',
    'TAGS': [
        {'name': 'auth', 'description': 'Authentication and registration'},
        {'name': 'users', 'description': 'User profile management'},
        {'name': 'dreams', 'description': 'Dream and goal management'},
        {'name': 'conversations', 'description': 'AI chat in real-time'},
        {'name': 'notifications', 'description': 'Push notifications'},
        {'name': 'calendar', 'description': 'Calendar and planning'},
        {'name': 'subscriptions', 'description': 'Stripe subscription management'},
        {'name': 'store', 'description': 'In-app store for cosmetic items'},
        {'name': 'leagues', 'description': 'League and ranking system'},
        {'name': 'Circles', 'description': 'Dream Circles for group goals and challenges'},
        {'name': 'Social', 'description': 'Friends, follows, and activity feed'},
        {'name': 'Buddies', 'description': 'Dream Buddy accountability pairing'},
    ],
}

# Channels (WebSocket)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(os.getenv('REDIS_HOST', 'localhost'), int(os.getenv('REDIS_PORT', 6379)))],
        },
    },
}

# Celery Configuration
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# Redis Cache
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'CONNECTION_POOL_CLASS_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        },
        'KEY_PREFIX': 'dreamplanner',
        'TIMEOUT': 300,  # 5 minutes default
    }
}

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_ORGANIZATION_ID = os.getenv('OPENAI_ORGANIZATION_ID')
OPENAI_MODEL = 'gpt-4o-mini'
OPENAI_TIMEOUT = 30

# Content Moderation Configuration
CONTENT_MODERATION = {
    'ENABLED': True,
    'OPENAI_MODERATION_ENABLED': True,
    'CUSTOM_PATTERNS_ENABLED': True,
    'MODERATION_CACHE_TTL': 300,  # Cache moderation results for 5 minutes
}

# AI Usage Quotas (daily limits per subscription tier)
AI_QUOTAS = {
    'ENABLED': True,
    'REDIS_KEY_PREFIX': 'ai_usage',
    'KEY_TTL_HOURS': 25,
    'DEFAULT_LIMITS': {
        'free': {'ai_chat': 0, 'ai_plan': 0, 'ai_image': 0, 'ai_voice': 0, 'ai_background': 0},
        'premium': {'ai_chat': 50, 'ai_plan': 10, 'ai_image': 0, 'ai_voice': 10, 'ai_background': 3},
        'pro': {'ai_chat': 150, 'ai_plan': 25, 'ai_image': 3, 'ai_voice': 20, 'ai_background': 3},
    },
}

# django-allauth Configuration
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None

# dj-rest-auth Configuration
REST_AUTH = {
    'USE_JWT': False,
    'TOKEN_MODEL': 'rest_framework.authtoken.models.Token',
    'USER_DETAILS_SERIALIZER': 'apps.users.serializers.UserSerializer',
    'REGISTER_SERIALIZER': 'core.serializers.RegisterSerializer',
}

# Social Account Providers
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.getenv('GOOGLE_CLIENT_ID', ''),
            'secret': os.getenv('GOOGLE_CLIENT_SECRET', ''),
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'apple': {
        'APP': {
            'client_id': os.getenv('APPLE_CLIENT_ID', ''),
            'secret': os.getenv('APPLE_CLIENT_SECRET', ''),
            'key': os.getenv('APPLE_KEY_ID', ''),
        },
        'SCOPE': ['email', 'name'],
    },
}
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# CORS Configuration
_cors_raw = os.getenv('CORS_ORIGIN', 'http://localhost:3000')
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_raw.split(',') if o.strip()]
CORS_ALLOW_CREDENTIALS = False  # Token auth via header, no cross-origin cookies needed
CORS_EXPOSE_HEADERS = ['Content-Type', 'X-Request-Id']
CORS_ALLOWED_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOWED_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Stripe Configuration
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

# Subscription plan Stripe Price IDs
STRIPE_PRICES = {
    'premium_monthly': os.getenv('STRIPE_PREMIUM_MONTHLY_PRICE_ID', ''),
    'premium_yearly': os.getenv('STRIPE_PREMIUM_YEARLY_PRICE_ID', ''),
    'pro_monthly': os.getenv('STRIPE_PRO_MONTHLY_PRICE_ID', ''),
    'pro_yearly': os.getenv('STRIPE_PRO_YEARLY_PRICE_ID', ''),
}

# Subscription pricing (for display and validation)
SUBSCRIPTION_PRICES = {
    'premium': {'monthly': 9.99, 'yearly': 99.99},
    'pro': {'monthly': 19.99, 'yearly': 199.99},
}

# Free tier limits — free users only get basic todo list (dreams/goals/tasks)
FREE_TIER_LIMITS = {
    'max_dreams': 3,
    'ai_access': False,
    'buddy_access': False,
    'circle_access': False,
    'vision_board_access': False,
    'league_access': False,
    'store_purchase': False,
    'social_feed': False,
    'advanced_notifications': False,
    'has_ads': True,
}

# Token expiration
TOKEN_EXPIRY_HOURS = int(os.getenv('TOKEN_EXPIRY_HOURS', 24))

# Security settings (will be overridden in production)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Session & Cookie security
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# Field-level encryption key for PII (required for encrypted model fields)
# In production, set FIELD_ENCRYPTION_KEY env var. For dev, a default is used.
FIELD_ENCRYPTION_KEY = os.getenv(
    'FIELD_ENCRYPTION_KEY',
    'XT94MCe7dwrIRNEwVri4TzphlFiVnkj6xF3y3gpT2mg='
)

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'security_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'security': {
            'handlers': ['console', 'security_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
