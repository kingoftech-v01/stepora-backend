"""
URL configuration for the Circles system.

Routes:
    /circles/                          - List/create circles
    /circles/?filter={my|public|recommended} - Filtered circle list
    /circles/<id>/                     - Circle detail
    /circles/<id>/join/                - Join a circle
    /circles/<id>/leave/               - Leave a circle
    /circles/<id>/feed/                - Circle post feed
    /circles/<id>/posts/               - Create a post
    /circles/<id>/challenges/          - List circle challenges
    /challenges/<id>/join/             - Join a challenge
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import CircleViewSet, ChallengeViewSet

router = DefaultRouter()
router.register(r'circles', CircleViewSet, basename='circle')
router.register(r'circles/challenges', ChallengeViewSet, basename='circle-challenge')

urlpatterns = [
    path('', include(router.urls)),
]
