"""
URL configuration for DreamPlanner backend.
Routes all API endpoints to their respective app URL configurations.
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
from core.social_auth import GoogleLoginView, AppleLoginView

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),

    # Health check
    path('health/', include('core.urls')),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Authentication (dj-rest-auth)
    path('api/auth/', include('dj_rest_auth.urls')),
    path('api/auth/registration/', include('dj_rest_auth.registration.urls')),

    # Social authentication (Google, Apple)
    path('api/auth/google/', GoogleLoginView.as_view(), name='google_login'),
    path('api/auth/apple/', AppleLoginView.as_view(), name='apple_login'),

    # API endpoints
    path('api/users/', include('apps.users.urls')),
    path('api/dreams/', include('apps.dreams.urls')),
    path('api/conversations/', include('apps.conversations.urls')),
    path('api/calendar/', include('apps.calendar.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/subscriptions/', include('apps.subscriptions.urls')),
    path('api/store/', include('apps.store.urls')),
    path('api/leagues/', include('apps.leagues.urls')),
    path('api/', include('apps.circles.urls')),
    path('api/social/', include('apps.social.urls')),
    path('api/buddies/', include('apps.buddies.urls')),

    # Search (Elasticsearch)
    path('api/search/', include('apps.search.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Debug toolbar in development
if settings.DEBUG and 'debug_toolbar' in settings.INSTALLED_APPS:
    import debug_toolbar
    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
