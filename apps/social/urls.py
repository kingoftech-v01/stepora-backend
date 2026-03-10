"""
URL configuration for the Social system.

Routes:
    /feed/friends                            - Friends activity feed (filterable)
    /friends                                 - List friends
    /friends/requests/pending               - Pending friend requests (received)
    /friends/requests/sent                  - Sent friend requests
    /friends/request                        - Send friend request
    /friends/accept/<id>                    - Accept friend request
    /friends/reject/<id>                    - Reject friend request
    /friends/remove/<user_id>              - Remove friend
    /friends/mutual/<user_id>              - Mutual friends
    /follow                                 - Follow a user
    /unfollow/<user_id>                    - Unfollow a user
    /block                                  - Block a user
    /unblock/<user_id>                     - Unblock a user
    /blocked                                - List blocked users
    /report                                 - Report a user
    /counts/<user_id>                      - Follower/following/friend counts
    /users/search?q=<query>                - Search users
    /posts/                                 - Dream posts CRUD
    /posts/feed/                            - Social feed
    /posts/<id>/like/                       - Like/unlike a post
    /posts/<id>/comment/                    - Comment on a post
    /posts/<id>/comments/                   - List comments
    /posts/<id>/encourage/                  - Send encouragement
    /posts/<id>/share/                      - Share/repost
    /posts/user/<user_id>/                  - User's posts
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActivityFeedView,
    DreamPostViewSet,
    FeedCommentView,
    FeedLikeView,
    FollowSuggestionsView,
    FriendshipViewSet,
    FriendSuggestionsView,
    RecentSearchViewSet,
    SocialEventViewSet,
    StoryViewSet,
    UserSearchView,
)

router = DefaultRouter()
router.register(r"", FriendshipViewSet, basename="social")
router.register(r"recent-searches", RecentSearchViewSet, basename="recent-searches")
router.register(r"posts", DreamPostViewSet, basename="dream-post")
router.register(r"events", SocialEventViewSet, basename="social-event")
router.register(r"stories", StoryViewSet, basename="story")

urlpatterns = [
    path("feed/friends/", ActivityFeedView.as_view(), name="friends-feed"),
    path("feed/<uuid:activity_id>/like/", FeedLikeView.as_view(), name="feed-like"),
    path(
        "feed/<uuid:activity_id>/comment/",
        FeedCommentView.as_view(),
        name="feed-comment",
    ),
    path("users/search", UserSearchView.as_view(), name="user-search"),
    path(
        "follow-suggestions/",
        FollowSuggestionsView.as_view(),
        name="follow-suggestions",
    ),
    path(
        "friend-suggestions/",
        FriendSuggestionsView.as_view(),
        name="friend-suggestions",
    ),
    path("", include(router.urls)),
]
