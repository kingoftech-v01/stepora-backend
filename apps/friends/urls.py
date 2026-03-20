"""
URLs for the Friends system.

Routes:
    /friends/               - List friends
    /request/               - Send friend request
    /<id>/accept/           - Accept request
    /<id>/reject/           - Reject request
    /remove/<user_id>/      - Remove friend
    /requests/pending/      - Pending requests
    /mutual/<user_id>/      - Mutual friends
    /follow/                - Follow a user
    /unfollow/<user_id>/    - Unfollow
    /block/                 - Block a user
    /unblock/<user_id>/     - Unblock
    /blocked/               - List blocked users
    /report/                - Report a user
    /counts/<user_id>/      - Social counts
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FriendshipViewSet

router = DefaultRouter()
router.register(r"", FriendshipViewSet, basename="friends")

urlpatterns = [
    path("", include(router.urls)),
]
