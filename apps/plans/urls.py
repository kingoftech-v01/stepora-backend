"""
URLs for the Plans system.

Routes:
    /milestones/              - DreamMilestone CRUD
    /goals/                   - Goal CRUD
    /tasks/                   - Task CRUD
    /obstacles/               - Obstacle CRUD
    /checkins/                - Check-in list/detail
    /checkins/<id>/respond/   - Submit responses
    /checkins/<id>/status/    - Poll status
    /focus/start/             - Start focus session
    /focus/complete/          - Complete focus session
    /focus/history/           - Focus history
    /focus/stats/             - Focus stats
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CheckInViewSet,
    DreamMilestoneViewSet,
    FocusSessionCompleteView,
    FocusSessionHistoryView,
    FocusSessionStartView,
    FocusSessionStatsView,
    GoalViewSet,
    ObstacleViewSet,
    TaskViewSet,
)

router = DefaultRouter()
router.register(r"milestones", DreamMilestoneViewSet, basename="plan-milestone")
router.register(r"goals", GoalViewSet, basename="plan-goal")
router.register(r"tasks", TaskViewSet, basename="plan-task")
router.register(r"obstacles", ObstacleViewSet, basename="plan-obstacle")
router.register(r"checkins", CheckInViewSet, basename="plan-checkin")

urlpatterns = [
    path("focus/start/", FocusSessionStartView.as_view(), name="plan-focus-start"),
    path("focus/complete/", FocusSessionCompleteView.as_view(), name="plan-focus-complete"),
    path("focus/history/", FocusSessionHistoryView.as_view(), name="plan-focus-history"),
    path("focus/stats/", FocusSessionStatsView.as_view(), name="plan-focus-stats"),
    path("", include(router.urls)),
]
