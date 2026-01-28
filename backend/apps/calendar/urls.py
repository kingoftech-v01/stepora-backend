"""
URLs for Calendar app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CalendarEventViewSet, TimeBlockViewSet, CalendarViewSet

router = DefaultRouter()
router.register(r'events', CalendarEventViewSet, basename='calendar-event')
router.register(r'timeblocks', TimeBlockViewSet, basename='time-block')
router.register(r'', CalendarViewSet, basename='calendar')

urlpatterns = [
    path('', include(router.urls)),
]
