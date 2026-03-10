"""
URLs for Calendar app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter, SimpleRouter
from .views import (
    CalendarEventViewSet, TimeBlockViewSet, TimeBlockTemplateViewSet, CalendarViewSet,
    HabitViewSet,
    FocusModeActiveView, FocusBlockEventsView,
    GoogleCalendarStatusView,
    GoogleCalendarAuthView, GoogleCalendarCallbackView,
    GoogleCalendarNativeRedirectView,
    GoogleCalendarSyncView, GoogleCalendarDisconnectView,
    GoogleCalendarSyncSettingsView,
    ICalFeedView, ICalImportView,
    SmartScheduleView, AcceptScheduleView,
    CalendarShareView, CalendarSharedWithMeView, CalendarMySharesView,
    CalendarShareRevokeView, CalendarShareLinkView,
    SharedCalendarView, SharedCalendarSuggestView,
)

router = SimpleRouter()
router.register(r'events', CalendarEventViewSet, basename='calendar-event')
router.register(r'timeblocks', TimeBlockViewSet, basename='time-block')
router.register(r'timeblock-templates', TimeBlockTemplateViewSet, basename='timeblock-template')
router.register(r'habits', HabitViewSet, basename='habit')
router.register(r'', CalendarViewSet, basename='calendar')

urlpatterns = [
    # Google Calendar integration
    path('google/status/', GoogleCalendarStatusView.as_view(), name='google-calendar-status'),
    path('google/auth/', GoogleCalendarAuthView.as_view(), name='google-calendar-auth'),
    path('google/callback/', GoogleCalendarCallbackView.as_view(), name='google-calendar-callback'),
    path('google/native-callback/', GoogleCalendarNativeRedirectView.as_view(), name='google-calendar-native-callback'),
    path('google/sync/', GoogleCalendarSyncView.as_view(), name='google-calendar-sync'),
    path('google/disconnect/', GoogleCalendarDisconnectView.as_view(), name='google-calendar-disconnect'),
    path('google/sync-settings/', GoogleCalendarSyncSettingsView.as_view(), name='google-calendar-sync-settings'),
    # Focus mode integration
    path('focus-mode-active/', FocusModeActiveView.as_view(), name='focus-mode-active'),
    path('focus-block-events/', FocusBlockEventsView.as_view(), name='focus-block-events'),
    # Smart scheduling
    path('smart-schedule/', SmartScheduleView.as_view(), name='smart-schedule'),
    path('accept-schedule/', AcceptScheduleView.as_view(), name='accept-schedule'),
    # iCal feed (public, authenticated by token)
    path('ical-feed/<str:feed_token>/', ICalFeedView.as_view(), name='ical-feed'),
    # iCal import (authenticated)
    path('ical-import/', ICalImportView.as_view(), name='ical-import'),
    # Calendar sharing
    path('share/', CalendarShareView.as_view(), name='calendar-share'),
    path('shared-with-me/', CalendarSharedWithMeView.as_view(), name='calendar-shared-with-me'),
    path('my-shares/', CalendarMySharesView.as_view(), name='calendar-my-shares'),
    path('share/<uuid:share_id>/', CalendarShareRevokeView.as_view(), name='calendar-share-revoke'),
    path('share-link/', CalendarShareLinkView.as_view(), name='calendar-share-link'),
    path('shared/<str:token>/', SharedCalendarView.as_view(), name='shared-calendar-view'),
    path('shared/<str:token>/suggest/', SharedCalendarSuggestView.as_view(), name='shared-calendar-suggest'),
    # Router URLs
    path('', include(router.urls)),
]
