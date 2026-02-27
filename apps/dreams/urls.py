"""
URLs for Dreams app.

Routes:
    /dreams/                        - Dream CRUD
    /dreams/<id>/analyze/           - AI analysis
    /dreams/<id>/generate-plan/     - Generate AI plan (milestone-based)
    /dreams/<id>/duplicate/         - Deep-copy dream
    /dreams/<id>/share/             - Share with user
    /dreams/<id>/tags/              - Add/remove tags
    /dreams/<id>/export-pdf/        - Export as PDF
    /dreams/shared-with-me/         - Dreams shared with user
    /dreams/tags/                   - List all tags
    /dreams/templates/              - Browse templates
    /dreams/templates/<id>/use/     - Create dream from template
    /milestones/                    - Milestone CRUD (filter by ?dream=uuid)
    /goals/                         - Goal CRUD (filter by ?dream=uuid or ?milestone=uuid)
    /tasks/                         - Task CRUD
    /obstacles/                     - Obstacle CRUD
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DreamViewSet, MilestoneViewSet, GoalViewSet, TaskViewSet, ObstacleViewSet,
    SharedWithMeView, DreamTagListView, DreamTemplateViewSet,
    DreamPDFExportView,
)

router = DefaultRouter()
router.register(r'dreams', DreamViewSet, basename='dream')
router.register(r'milestones', MilestoneViewSet, basename='milestone')
router.register(r'goals', GoalViewSet, basename='goal')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'obstacles', ObstacleViewSet, basename='obstacle')
router.register(r'dreams/templates', DreamTemplateViewSet, basename='dream-template')

urlpatterns = [
    path('dreams/shared-with-me/', SharedWithMeView.as_view(), name='shared-with-me'),
    path('dreams/tags/', DreamTagListView.as_view(), name='dream-tags'),
    path('dreams/<uuid:dream_id>/export-pdf/', DreamPDFExportView.as_view(), name='dream-export-pdf'),
    path('', include(router.urls)),
]
