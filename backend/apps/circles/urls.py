"""
URL configuration for the Circles system.

Routes:
    /circles/                                    - List/create circles
    /circles/?filter={my|public|recommended}    - Filtered circle list
    /circles/<id>/                               - Circle detail / update / delete
    /circles/<id>/join/                          - Join a circle
    /circles/<id>/leave/                         - Leave a circle
    /circles/<id>/feed/                          - Circle post feed
    /circles/<id>/posts/                         - Create a post
    /circles/<id>/posts/<post_id>/edit/          - Edit a post
    /circles/<id>/posts/<post_id>/delete/        - Delete a post
    /circles/<id>/posts/<post_id>/react/         - React to a post
    /circles/<id>/posts/<post_id>/unreact/       - Remove reaction
    /circles/<id>/challenges/                    - List circle challenges
    /circles/<id>/members/<member_id>/promote/   - Promote member
    /circles/<id>/members/<member_id>/demote/    - Demote member
    /circles/<id>/members/<member_id>/remove/    - Remove member
    /challenges/<id>/join/                       - Join a challenge
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CircleViewSet, ChallengeViewSet,
    JoinByInviteCodeView, MyInvitationsView,
)

router = DefaultRouter()
router.register(r'circles', CircleViewSet, basename='circle')
router.register(r'circles/challenges', ChallengeViewSet, basename='circle-challenge')

urlpatterns = [
    path('circles/join/<str:invite_code>/', JoinByInviteCodeView.as_view(), name='circle-join-invite'),
    path('circles/my-invitations/', MyInvitationsView.as_view(), name='circle-my-invitations'),
    path('', include(router.urls)),
]
