"""
URL configuration for the Social system.

Routes:
    /feed/friends                      - Friends activity feed
    /friends                           - List friends
    /friends/requests/pending          - Pending friend requests
    /friends/request                   - Send friend request
    /friends/accept/<id>               - Accept friend request
    /friends/reject/<id>               - Reject friend request
    /follow                            - Follow a user
    /users/search?q=<query>            - Search users
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import FriendshipViewSet, ActivityFeedView, UserSearchView

router = DefaultRouter()
router.register(r'', FriendshipViewSet, basename='social')

urlpatterns = [
    path('feed/friends', ActivityFeedView.as_view(), name='friends-feed'),
    path('users/search', UserSearchView.as_view(), name='user-search'),
    path('', include(router.urls)),
]
