"""
URLs for Dreams app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DreamViewSet, GoalViewSet, TaskViewSet, ObstacleViewSet

router = DefaultRouter()
router.register(r'dreams', DreamViewSet, basename='dream')
router.register(r'goals', GoalViewSet, basename='goal')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'obstacles', ObstacleViewSet, basename='obstacle')

urlpatterns = [
    path('', include(router.urls)),
]
