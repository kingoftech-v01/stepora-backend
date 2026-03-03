"""
URL configuration for DreamPlanner backend.
Routes all API endpoints to their respective app URL configurations.

API versioning: All endpoints are served under /api/v1/.
The unversioned /api/ path is kept as a backward-compatible alias.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.views import TokenRefreshView
from core.social_auth import GoogleLoginView, AppleLoginView, AppleRedirectView
from core.auth_views import NativeAwareLoginView, NativeAwareRegisterView, TwoFactorChallengeView
from core.throttles import AuthRateThrottle
from dj_rest_auth.views import PasswordResetView, PasswordResetConfirmView

# Versioned API endpoints (v1)
api_v1_patterns = [
    # Authentication (dj-rest-auth) — custom login/register for native app support
    path('auth/login/', NativeAwareLoginView.as_view(), name='rest_login'),
    path('auth/2fa-challenge/', TwoFactorChallengeView.as_view(), name='2fa_challenge'),
    path('auth/registration/', NativeAwareRegisterView.as_view(), name='rest_register'),
    # Explicit throttled password reset (before the catch-all dj-rest-auth include)
    path('auth/password/reset/', PasswordResetView.as_view(throttle_classes=[AuthRateThrottle]), name='rest_password_reset'),
    path('auth/password/reset/confirm/', PasswordResetConfirmView.as_view(throttle_classes=[AuthRateThrottle]), name='rest_password_reset_confirm'),
    path('auth/', include('dj_rest_auth.urls')),
    path('auth/registration/', include('dj_rest_auth.registration.urls')),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Social authentication (Google, Apple)
    path('auth/google/', GoogleLoginView.as_view(), name='google_login'),
    path('auth/apple/', AppleLoginView.as_view(), name='apple_login'),
    path('auth/apple/redirect/', AppleRedirectView.as_view(), name='apple_redirect'),

    # API endpoints
    path('users/', include('apps.users.urls')),
    path('dreams/', include('apps.dreams.urls')),
    path('conversations/', include('apps.conversations.urls')),
    path('calendar/', include('apps.calendar.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('subscriptions/', include('apps.subscriptions.urls')),
    path('store/', include('apps.store.urls')),
    path('leagues/', include('apps.leagues.urls')),
    path('circles/', include('apps.circles.urls')),
    path('social/', include('apps.social.urls')),
    path('buddies/', include('apps.buddies.urls')),

    # Search (Elasticsearch)
    path('search/', include('apps.search.urls')),
]

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),

    # Health check
    path('health/', include('core.urls')),

    # API Documentation (restricted to staff in production)
    path('api/schema/', SpectacularAPIView.as_view(
        permission_classes=[IsAdminUser] if not settings.DEBUG else [IsAuthenticated]
    ), name='schema'),

    # Versioned API (canonical)
    path('api/v1/', include((api_v1_patterns, 'api-v1'))),

    # Backward-compatible unversioned API (same endpoints)
    path('api/', include(api_v1_patterns)),
]

# Always serve media files (vision board images, etc.)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve API docs and static in development only
if settings.DEBUG:
    urlpatterns += [
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
        path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    ]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Debug toolbar in development
if settings.DEBUG and 'debug_toolbar' in settings.INSTALLED_APPS:
    import debug_toolbar
    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
