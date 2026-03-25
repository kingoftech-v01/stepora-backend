"""
URL configuration for Stepora backend.
Routes all API endpoints to their respective app URL configurations.

API versioning: All endpoints are served under /api/v1/.
The unversioned /api/ path is kept as a backward-compatible alias.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from core.sync_views import BatchSyncView

# Versioned API endpoints (v1)
api_v1_patterns = [
    # Authentication (custom — replaces dj-rest-auth + allauth)
    path("auth/", include("core.auth.urls")),
    # API endpoints
    path("users/", include("apps.users.urls")),
    path("dreams/", include("apps.dreams.urls")),
    path("plans/", include("apps.plans.urls")),
    path("gamification/", include("apps.gamification.urls")),
    path("friends/", include("apps.friends.urls")),
    path("referrals/", include("apps.referrals.urls")),
    path("chat/", include("apps.chat.urls")),
    path("ai/", include("apps.ai.urls")),
    path("calendar/", include("apps.calendar.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("subscriptions/", include("apps.subscriptions.urls")),
    path("store/", include("apps.store.urls")),
    path("leagues/", include("apps.leagues.urls")),
    path("circles/", include("apps.circles.urls")),
    path("social/", include("apps.social.urls")),
    path("buddies/", include("apps.buddies.urls")),
    # Search (Elasticsearch)
    path("search/", include("apps.search.urls")),
    # App Updates (OTA live updates)
    path("updates/", include("apps.updates.urls")),
    # Batch sync (offline queue replay)
    path("sync/batch/", BatchSyncView.as_view(), name="batch-sync"),
]

urlpatterns = [
    # Django Admin (non-default path for security)
    path("stepora-manage/", admin.site.urls),
    # Health check
    path("health/", include("core.urls")),
    # API Documentation (restricted to staff in production)
    path(
        "api/schema/",
        SpectacularAPIView.as_view(
            permission_classes=(
                [IsAdminUser] if not settings.DEBUG else [IsAuthenticated]
            )
        ),
        name="schema",
    ),
    # Versioned API (canonical)
    path("api/v1/", include((api_v1_patterns, "api-v1"))),
    # Backward-compatible unversioned API (same endpoints)
    path("api/", include(api_v1_patterns)),
]

# Always serve media files (vision board images, etc.)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve API docs and static in development only
if settings.DEBUG:
    urlpatterns += [
        path(
            "api/docs/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path(
            "api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"
        ),
    ]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Debug toolbar in development
if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
