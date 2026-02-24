"""
URLs for Calendar app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter, SimpleRouter
from .views import (
    CalendarEventViewSet, TimeBlockViewSet, CalendarViewSet,
    GoogleCalendarStatusView,
    GoogleCalendarAuthView, GoogleCalendarCallbackView,
    GoogleCalendarNativeRedirectView,
    GoogleCalendarSyncView, GoogleCalendarDisconnectView,
    ICalFeedView,
)

router = SimpleRouter()
router.register(r'events', CalendarEventViewSet, basename='calendar-event')
router.register(r'timeblocks', TimeBlockViewSet, basename='time-block')
router.register(r'', CalendarViewSet, basename='calendar')

urlpatterns = [
    # Google Calendar integration
    path('google/status/', GoogleCalendarStatusView.as_view(), name='google-calendar-status'),
    path('google/auth/', GoogleCalendarAuthView.as_view(), name='google-calendar-auth'),
    path('google/callback/', GoogleCalendarCallbackView.as_view(), name='google-calendar-callback'),
    path('google/native-callback/', GoogleCalendarNativeRedirectView.as_view(), name='google-calendar-native-callback'),
    path('google/sync/', GoogleCalendarSyncView.as_view(), name='google-calendar-sync'),
    path('google/disconnect/', GoogleCalendarDisconnectView.as_view(), name='google-calendar-disconnect'),
    # iCal feed (public, authenticated by token)
    path('ical-feed/<str:feed_token>/', ICalFeedView.as_view(), name='ical-feed'),
    # Router URLs
    path('', include(router.urls)),
]
