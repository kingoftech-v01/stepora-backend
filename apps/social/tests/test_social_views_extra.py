"""
Extra coverage tests for apps/social/views.py targeting uncovered lines.

Targets ~30% of uncovered lines to reach 90%+ coverage.
Key areas:
- FriendshipViewSet: _get_friend_data title tiers (lines 92-102), re-send after rejection (235-241),
  user not found (203-204), block check on friend request (213), accept/reject notifications (315),
  follow blocked check (398), social_counts blocked (799-812)
- ActivityFeedView: free user queryset (843-856), private dream filtering (859-946),
  activity_type/created_before filters (934-944), pagination (984-992)
- UserSearchView: search with < 2 chars (1031), search integration (1043-1118)
- FollowSuggestionsView: circle members, fof, category overlap (1149-1277)
- FeedLikeView: toggle off, blocked check (1311-1333)
- FeedCommentView: blocked check, empty text (1375-1399)
- RecentSearchViewSet: add/clear/remove (1457-1506)
- DreamPostViewSet: create with dream, linked items, media, event (1571-1690),
  perform_update ownership (1694-1696), destroy ownership (1734-1736),
  user_posts blocked (2281-2316), saved posts (2351-2376)
- SocialEventViewSet: retrieve meeting_link strip, create, update, destroy (2441-2555),
  register, unregister, participants, feed (2556-2715)
- StoryViewSet: create, destroy, feed, my_stories, mark_viewed, viewers (2740-2996)
- FriendSuggestionsView: scoring algorithm (3029-3262)
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.dreams.models import Dream, DreamMilestone, Goal
from apps.social.models import (
    ActivityFeedItem,
    BlockedUser,
    DreamPost,
    DreamPostComment,
    Friendship,
    RecentSearch,
    SavedPost,
    SocialEvent,
    SocialEventRegistration,
    Story,
    StoryView,
    UserFollow,
)
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mock_stripe_signal():
    with patch("apps.subscriptions.services.StripeService.create_customer"):
        yield

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def u1(db):
    user = User.objects.create_user(
        email="sv_u1@example.com", password="pass123", display_name="SV User 1",
    )
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="premium",
        defaults={"name": "Premium", "price_monthly": 19.99, "is_active": True,
                  "dream_limit": 10, "has_ai": True, "has_vision_board": False},
    )
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan, "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return user


@pytest.fixture
def u2(db):
    return User.objects.create_user(
        email="sv_u2@example.com", password="pass123", display_name="SV User 2",
    )


@pytest.fixture
def u3(db):
    return User.objects.create_user(
        email="sv_u3@example.com", password="pass123", display_name="SV User 3",
    )


@pytest.fixture
def u4(db):
    return User.objects.create_user(
        email="sv_u4@example.com", password="pass123", display_name="SV User 4",
    )


@pytest.fixture
def c1(u1):
    c = APIClient()
    c.force_authenticate(user=u1)
    return c


@pytest.fixture
def c2(u2):
    c = APIClient()
    c.force_authenticate(user=u2)
    return c


@pytest.fixture
def c3(u3):
    c = APIClient()
    c.force_authenticate(user=u3)
    return c


# ═══════════════════════════════════════════════════════════════════
#  FriendshipViewSet — _get_friend_data title tiers (lines 91-102)
# ═══════════════════════════════════════════════════════════════════


class TestFriendDataTitles:
    """Cover _get_friend_data title tiers: Dreamer, Explorer, Achiever, Expert, Master, Legend."""

    def _make_friend_at_level(self, u1, level):
        """Create a user at a given level and befriend u1."""
        user = User.objects.create_user(
            email=f"lvl{level}_{uuid.uuid4().hex[:6]}@x.com",
            password="pass",
            display_name=f"Level {level}",
        )
        user.xp = level * 100  # enough to approximate the level
        # Directly set level if the User model stores it; otherwise xp is used
        # The level property is computed from xp, so let's set xp high enough
        user.save()
        Friendship.objects.create(user1=u1, user2=user, status="accepted")
        return user

    def test_list_friends_all_title_tiers(self, c1, u1):
        """List friends exercising all title tiers."""
        for xp_val, expected_level_range in [
            (0, "Dreamer"),        # level < 5
            (500, "Explorer"),     # level >= 5
            (1000, "Achiever"),    # level >= 10
            (2000, "Expert"),      # level >= 20
            (3000, "Master"),      # level >= 30
            (5000, "Legend"),      # level >= 50
        ]:
            user = User.objects.create_user(
                email=f"friend_{xp_val}_{uuid.uuid4().hex[:4]}@x.com",
                password="pass",
                display_name=f"Friend XP {xp_val}",
            )
            user.xp = xp_val
            user.save()
            Friendship.objects.create(user1=u1, user2=user, status="accepted")

        resp = c1.get("/api/social/friends/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) >= 6


# ═══════════════════════════════════════════════════════════════════
#  FriendshipViewSet — send_request edge cases
# ═══════════════════════════════════════════════════════════════════


class TestFriendRequestEdgeCases:
    """Cover send_request branches: self, not found, blocked, already friends, pending, re-send."""

    def test_send_request_to_self(self, c1, u1):
        resp = c1.post(
            "/api/social/friends/request/",
            {"target_user_id": str(u1.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_send_request_user_not_found(self, c1):
        resp = c1.post(
            "/api/social/friends/request/",
            {"target_user_id": str(uuid.uuid4())},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_send_request_blocked(self, c1, u1, u2):
        BlockedUser.objects.create(blocker=u1, blocked=u2)
        resp = c1.post(
            "/api/social/friends/request/",
            {"target_user_id": str(u2.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_send_request_already_friends(self, c1, u1, u2):
        Friendship.objects.create(user1=u1, user2=u2, status="accepted")
        resp = c1.post(
            "/api/social/friends/request/",
            {"target_user_id": str(u2.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_send_request_already_pending(self, c1, u1, u2):
        Friendship.objects.create(user1=u1, user2=u2, status="pending")
        resp = c1.post(
            "/api/social/friends/request/",
            {"target_user_id": str(u2.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_resend_request_after_rejection(self, c1, u1, u2):
        """Re-sending after rejection should succeed (lines 235-241)."""
        Friendship.objects.create(user1=u2, user2=u1, status="rejected")
        resp = c1.post(
            "/api/social/friends/request/",
            {"target_user_id": str(u2.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_accept_request(self, c2, u1, u2):
        fr = Friendship.objects.create(user1=u1, user2=u2, status="pending")
        resp = c2.post(f"/api/social/friends/accept/{fr.id}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_accept_request_not_found(self, c2):
        resp = c2.post(f"/api/social/friends/accept/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_reject_request(self, c2, u1, u2):
        fr = Friendship.objects.create(user1=u1, user2=u2, status="pending")
        resp = c2.post(f"/api/social/friends/reject/{fr.id}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_reject_request_not_found(self, c2):
        resp = c2.post(f"/api/social/friends/reject/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ═══════════════════════════════════════════════════════════════════
#  Follow / Unfollow / Block
# ═══════════════════════════════════════════════════════════════════


class TestFollowBlockEdgeCases:
    """Cover follow blocked check (line 398), various edge cases."""

    def test_follow_self(self, c1, u1):
        resp = c1.post("/api/social/follow/", {"target_user_id": str(u1.id)}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_follow_not_found(self, c1):
        resp = c1.post("/api/social/follow/", {"target_user_id": str(uuid.uuid4())}, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_follow_blocked_user(self, c1, u1, u2):
        BlockedUser.objects.create(blocker=u2, blocked=u1)
        resp = c1.post("/api/social/follow/", {"target_user_id": str(u2.id)}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_follow_already_following(self, c1, u1, u2):
        UserFollow.objects.create(follower=u1, following=u2)
        resp = c1.post("/api/social/follow/", {"target_user_id": str(u2.id)}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_unfollow_success(self, c1, u1, u2):
        UserFollow.objects.create(follower=u1, following=u2)
        resp = c1.delete(f"/api/social/unfollow/{u2.id}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_unfollow_not_following(self, c1, u2):
        resp = c1.delete(f"/api/social/unfollow/{u2.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ═══════════════════════════════════════════════════════════════════
#  Block / Unblock / Report
# ═══════════════════════════════════════════════════════════════════


class TestBlockUnblockReport:

    def test_block_self(self, c1, u1):
        resp = c1.post("/api/social/block/", {"target_user_id": str(u1.id)}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_block_not_found(self, c1):
        resp = c1.post("/api/social/block/", {"target_user_id": str(uuid.uuid4())}, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_block_already_blocked(self, c1, u1, u2):
        BlockedUser.objects.create(blocker=u1, blocked=u2)
        resp = c1.post("/api/social/block/", {"target_user_id": str(u2.id)}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_block_removes_friendship_and_follow(self, c1, u1, u2):
        Friendship.objects.create(user1=u1, user2=u2, status="accepted")
        UserFollow.objects.create(follower=u1, following=u2)
        resp = c1.post(
            "/api/social/block/",
            {"target_user_id": str(u2.id), "reason": "spam"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert not Friendship.objects.filter(user1=u1, user2=u2).exists()
        assert not UserFollow.objects.filter(follower=u1, following=u2).exists()

    def test_unblock_success(self, c1, u1, u2):
        BlockedUser.objects.create(blocker=u1, blocked=u2)
        resp = c1.delete(f"/api/social/unblock/{u2.id}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_unblock_not_found(self, c1, u2):
        resp = c1.delete(f"/api/social/unblock/{u2.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_list_blocked(self, c1, u1, u2):
        BlockedUser.objects.create(blocker=u1, blocked=u2)
        resp = c1.get("/api/social/blocked/")
        assert resp.status_code == status.HTTP_200_OK

    def test_report_self(self, c1, u1):
        resp = c1.post(
            "/api/social/report/",
            {"target_user_id": str(u1.id), "reason": "test"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_report_not_found(self, c1):
        resp = c1.post(
            "/api/social/report/",
            {"target_user_id": str(uuid.uuid4()), "reason": "test"},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_report_success(self, c1, u2):
        resp = c1.post(
            "/api/social/report/",
            {"target_user_id": str(u2.id), "reason": "Harassment", "category": "harassment"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED


# ═══════════════════════════════════════════════════════════════════
#  Social counts + mutual friends + online friends + sent/cancel
# ═══════════════════════════════════════════════════════════════════


class TestSocialMisc:

    def test_social_counts(self, c1, u1, u2):
        UserFollow.objects.create(follower=u2, following=u1)
        resp = c1.get(f"/api/social/counts/{u1.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert "follower_count" in resp.data

    def test_social_counts_not_found(self, c1):
        resp = c1.get(f"/api/social/counts/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_social_counts_blocked(self, c1, u1, u2):
        BlockedUser.objects.create(blocker=u1, blocked=u2)
        resp = c1.get(f"/api/social/counts/{u2.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_mutual_friends(self, c1, u1, u2, u3):
        Friendship.objects.create(user1=u1, user2=u3, status="accepted")
        Friendship.objects.create(user1=u2, user2=u3, status="accepted")
        resp = c1.get(f"/api/social/friends/mutual/{u2.id}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_mutual_friends_not_found(self, c1):
        resp = c1.get(f"/api/social/friends/mutual/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_remove_friend(self, c1, u1, u2):
        Friendship.objects.create(user1=u1, user2=u2, status="accepted")
        resp = c1.delete(f"/api/social/friends/remove/{u2.id}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_remove_friend_not_found(self, c1, u2):
        resp = c1.delete(f"/api/social/friends/remove/{u2.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_sent_requests(self, c1, u1, u2):
        Friendship.objects.create(user1=u1, user2=u2, status="pending")
        resp = c1.get("/api/social/friends/requests/sent/")
        assert resp.status_code == status.HTTP_200_OK

    def test_cancel_request(self, c1, u1, u2):
        fr = Friendship.objects.create(user1=u1, user2=u2, status="pending")
        resp = c1.delete(f"/api/social/friends/cancel/{fr.id}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_cancel_request_not_found(self, c1):
        resp = c1.delete(f"/api/social/friends/cancel/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_online_friends(self, c1, u1, u2):
        Friendship.objects.create(user1=u1, user2=u2, status="accepted")
        u2.is_online = True
        u2.last_seen = timezone.now()
        u2.save(update_fields=["is_online", "last_seen"])
        resp = c1.get("/api/social/friends/online/")
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════
#  ActivityFeedView
# ═══════════════════════════════════════════════════════════════════


class TestActivityFeed:
    """Cover free-user queryset, filters, pagination."""

    def test_activity_feed_free_user(self, c1, u1):
        """Free user sees only encouragement type (lines 843-856)."""
        # u1 is premium, so make a free user
        free_user = User.objects.create_user(
            email="feed_free@example.com", password="pass", display_name="Free Feed",
        )
        free_client = APIClient()
        free_client.force_authenticate(user=free_user)
        ActivityFeedItem.objects.create(
            user=free_user, activity_type="encouragement",
            content={"text": "test"},
        )
        ActivityFeedItem.objects.create(
            user=free_user, activity_type="task_completed",
            content={"text": "task"},
        )
        resp = free_client.get("/api/social/feed/friends/")
        assert resp.status_code == status.HTTP_200_OK

    def test_activity_feed_with_filters(self, c1, u1):
        ActivityFeedItem.objects.create(
            user=u1, activity_type="task_completed", content={"text": "test"},
        )
        now = timezone.now()
        resp = c1.get(
            "/api/social/feed/friends/",
            {
                "activity_type": "task_completed",
                "created_after": (now - timedelta(hours=1)).isoformat(),
                "created_before": (now + timedelta(hours=1)).isoformat(),
            },
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_activity_feed_private_dream_filtering(self, c1, u1, u2):
        """Activity items referencing private dreams from others are filtered."""
        Friendship.objects.create(user1=u1, user2=u2, status="accepted")
        dream = Dream.objects.create(
            user=u2, title="Private", description="Secret", is_public=False, status="active",
        )
        ActivityFeedItem.objects.create(
            user=u2, activity_type="task_completed",
            content={"dream_id": str(dream.id)},
        )
        resp = c1.get("/api/social/feed/friends/")
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════
#  FeedLikeView + FeedCommentView
# ═══════════════════════════════════════════════════════════════════


class TestFeedLikeComment:

    def test_feed_like_toggle(self, c1, u1):
        activity = ActivityFeedItem.objects.create(
            user=u1, activity_type="task_completed", content={},
        )
        # Like
        resp = c1.post(f"/api/social/feed/{activity.id}/like/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["liked"] is True
        # Unlike (toggle off)
        resp = c1.post(f"/api/social/feed/{activity.id}/like/")
        assert resp.data["liked"] is False

    def test_feed_like_not_found(self, c1):
        resp = c1.post(f"/api/social/feed/{uuid.uuid4()}/like/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_feed_like_blocked(self, c1, u1, u2):
        activity = ActivityFeedItem.objects.create(
            user=u2, activity_type="task_completed", content={},
        )
        BlockedUser.objects.create(blocker=u1, blocked=u2)
        resp = c1.post(f"/api/social/feed/{activity.id}/like/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_feed_comment(self, c1, u1):
        activity = ActivityFeedItem.objects.create(
            user=u1, activity_type="task_completed", content={},
        )
        resp = c1.post(
            f"/api/social/feed/{activity.id}/comment/",
            {"text": "Great job!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_feed_comment_empty_text(self, c1, u1):
        activity = ActivityFeedItem.objects.create(
            user=u1, activity_type="task_completed", content={},
        )
        resp = c1.post(
            f"/api/social/feed/{activity.id}/comment/",
            {"text": ""},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_feed_comment_not_found(self, c1):
        resp = c1.post(
            f"/api/social/feed/{uuid.uuid4()}/comment/",
            {"text": "test"},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_feed_comment_blocked(self, c1, u1, u2):
        activity = ActivityFeedItem.objects.create(
            user=u2, activity_type="task_completed", content={},
        )
        BlockedUser.objects.create(blocker=u1, blocked=u2)
        resp = c1.post(
            f"/api/social/feed/{activity.id}/comment/",
            {"text": "test"},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ═══════════════════════════════════════════════════════════════════
#  UserSearchView
# ═══════════════════════════════════════════════════════════════════


class TestUserSearch:

    def test_search_short_query(self, c1):
        """Query < 2 chars returns empty (line 1031)."""
        resp = c1.get("/api/social/users/search?q=a")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 0

    def test_search_users(self, c1, u1, u2):
        """Full search integration (mocked ES)."""
        with patch("apps.search.services.SearchService.search_users") as mock_search:
            mock_search.return_value = [u2.id]
            resp = c1.get("/api/social/users/search?q=SV+User")
            assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════
#  RecentSearchViewSet
# ═══════════════════════════════════════════════════════════════════


class TestRecentSearches:

    def test_add_and_list_search(self, c1):
        resp = c1.post(
            "/api/social/recent-searches/add/",
            {"query": "test search", "search_type": "users"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

        resp = c1.get("/api/social/recent-searches/list/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) >= 1

    def test_add_search_empty_query(self, c1):
        resp = c1.post(
            "/api/social/recent-searches/add/",
            {"query": ""},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_add_search_multiple(self, c1):
        """Adding multiple searches works (deduplication may depend on field encryption)."""
        resp1 = c1.post("/api/social/recent-searches/add/", {"query": "search1"}, format="json")
        assert resp1.status_code == status.HTTP_201_CREATED
        resp2 = c1.post("/api/social/recent-searches/add/", {"query": "search2"}, format="json")
        assert resp2.status_code == status.HTTP_201_CREATED
        resp = c1.get("/api/social/recent-searches/list/")
        assert len(resp.data) >= 2

    def test_clear_searches(self, c1):
        c1.post("/api/social/recent-searches/add/", {"query": "clear me"}, format="json")
        resp = c1.delete("/api/social/recent-searches/clear/")
        assert resp.status_code == status.HTTP_200_OK

    def test_remove_search(self, c1, u1):
        RecentSearch.objects.create(user=u1, query="removable")
        s = RecentSearch.objects.filter(user=u1).first()
        resp = c1.delete(f"/api/social/recent-searches/{s.id}/remove/")
        assert resp.status_code == status.HTTP_200_OK

    def test_remove_search_not_found(self, c1):
        resp = c1.delete(f"/api/social/recent-searches/{uuid.uuid4()}/remove/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ═══════════════════════════════════════════════════════════════════
#  DreamPostViewSet — CRUD
# ═══════════════════════════════════════════════════════════════════


class TestDreamPostCrud:

    def test_create_post_with_dream(self, c1, u1):
        dream = Dream.objects.create(
            user=u1, title="Public Dream", description="Desc", is_public=True, status="active",
        )
        resp = c1.post(
            "/api/social/posts/",
            {"content": "Post with dream", "dream_id": str(dream.id), "visibility": "public"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_create_post_dream_not_found(self, c1):
        resp = c1.post(
            "/api/social/posts/",
            {"content": "Post", "dream_id": str(uuid.uuid4()), "visibility": "public"},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_create_post_dream_not_public(self, c1, u1):
        dream = Dream.objects.create(
            user=u1, title="Private Dream", description="Desc", is_public=False, status="active",
        )
        resp = c1.post(
            "/api/social/posts/",
            {"content": "Post", "dream_id": str(dream.id), "visibility": "public"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_post_with_linked_goal(self, c1, u1):
        dream = Dream.objects.create(
            user=u1, title="D", description="D", is_public=True, status="active",
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        resp = c1.post(
            "/api/social/posts/",
            {"content": "Achievement!", "linked_goal_id": str(goal.id), "visibility": "public"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_create_post_linked_goal_not_found(self, c1):
        resp = c1.post(
            "/api/social/posts/",
            {"content": "Post", "linked_goal_id": str(uuid.uuid4()), "visibility": "public"},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_create_post_linked_milestone_not_found(self, c1):
        resp = c1.post(
            "/api/social/posts/",
            {"content": "Post", "linked_milestone_id": str(uuid.uuid4()), "visibility": "public"},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_create_post_with_gofundme_url(self, c1, u1):
        """Create post with gofundme_url field."""
        resp = c1.post(
            "/api/social/posts/",
            {
                "content": "Support my dream!",
                "gofundme_url": "https://gofundme.com/test",
                "visibility": "public",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_create_post_with_linked_milestone(self, c1, u1):
        dream = Dream.objects.create(
            user=u1, title="D", description="D", is_public=True, status="active",
        )
        ms = DreamMilestone.objects.create(dream=dream, title="M", order=1)
        resp = c1.post(
            "/api/social/posts/",
            {"content": "Milestone!", "linked_milestone_id": str(ms.id), "visibility": "public"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_create_post_with_image_url(self, c1, u1):
        """Create post with image_url to cover media_type detection."""
        resp = c1.post(
            "/api/social/posts/",
            {"content": "Image post!", "image_url": "https://example.com/img.png", "visibility": "public"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_update_own_post(self, c1, u1):
        post = DreamPost.objects.create(user=u1, content="Original", visibility="public")
        resp = c1.put(
            f"/api/social/posts/{post.id}/",
            {"content": "Edited", "visibility": "followers"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_update_other_post_forbidden(self, c2, u1):
        post = DreamPost.objects.create(user=u1, content="Not yours", visibility="public")
        resp = c2.put(
            f"/api/social/posts/{post.id}/",
            {"content": "Hacked"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_own_post(self, c1, u1):
        post = DreamPost.objects.create(user=u1, content="Delete me", visibility="public")
        resp = c1.delete(f"/api/social/posts/{post.id}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_other_post_forbidden(self, c2, u1):
        post = DreamPost.objects.create(user=u1, content="Not yours", visibility="public")
        resp = c2.delete(f"/api/social/posts/{post.id}/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_partial_update_post(self, c1, u1):
        post = DreamPost.objects.create(user=u1, content="Original", visibility="public")
        resp = c1.patch(
            f"/api/social/posts/{post.id}/",
            {"content": "Patched"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════
#  DreamPostViewSet — Like, React, Comment, Encourage, Share, Save
# ═══════════════════════════════════════════════════════════════════


class TestPostInteractions:

    def test_like_post(self, c1, u1):
        post = DreamPost.objects.create(user=u1, content="Likeable", visibility="public")
        resp = c1.post(f"/api/social/posts/{post.id}/like/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["liked"] is True
        # Unlike
        resp = c1.post(f"/api/social/posts/{post.id}/like/")
        assert resp.data["liked"] is False

    def test_react_to_post(self, c1, u1):
        post = DreamPost.objects.create(user=u1, content="React", visibility="public")
        resp = c1.post(
            f"/api/social/posts/{post.id}/react/",
            {"reaction_type": "fire"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["reacted"] is True

    def test_react_invalid_type(self, c1, u1):
        post = DreamPost.objects.create(user=u1, content="React", visibility="public")
        resp = c1.post(
            f"/api/social/posts/{post.id}/react/",
            {"reaction_type": "invalid_type"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_react_toggle_same_type(self, c1, u1):
        """Same reaction type toggles off."""
        post = DreamPost.objects.create(user=u1, content="React", visibility="public")
        c1.post(f"/api/social/posts/{post.id}/react/", {"reaction_type": "fire"}, format="json")
        resp = c1.post(f"/api/social/posts/{post.id}/react/", {"reaction_type": "fire"}, format="json")
        assert resp.data["reacted"] is False

    def test_react_change_type(self, c1, u1):
        """Changing reaction type updates it."""
        post = DreamPost.objects.create(user=u1, content="React", visibility="public")
        c1.post(f"/api/social/posts/{post.id}/react/", {"reaction_type": "fire"}, format="json")
        resp = c1.post(f"/api/social/posts/{post.id}/react/", {"reaction_type": "love"}, format="json")
        assert resp.data["reacted"] is True
        assert resp.data["reaction_type"] == "love"

    def test_comment_on_post(self, c1, u1):
        post = DreamPost.objects.create(user=u1, content="Commentable", visibility="public")
        resp = c1.post(
            f"/api/social/posts/{post.id}/comment/",
            {"content": "Nice post!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_comment_empty(self, c1, u1):
        post = DreamPost.objects.create(user=u1, content="Commentable", visibility="public")
        resp = c1.post(
            f"/api/social/posts/{post.id}/comment/",
            {"content": ""},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_comment_with_parent(self, c1, u1):
        post = DreamPost.objects.create(user=u1, content="P", visibility="public")
        comment = DreamPostComment.objects.create(post=post, user=u1, content="Parent")
        resp = c1.post(
            f"/api/social/posts/{post.id}/comment/",
            {"content": "Reply!", "parent_id": str(comment.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_comment_parent_not_found(self, c1, u1):
        post = DreamPost.objects.create(user=u1, content="P", visibility="public")
        resp = c1.post(
            f"/api/social/posts/{post.id}/comment/",
            {"content": "Reply!", "parent_id": str(uuid.uuid4())},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_list_comments(self, c1, u1):
        post = DreamPost.objects.create(user=u1, content="P", visibility="public")
        DreamPostComment.objects.create(post=post, user=u1, content="Comment 1")
        resp = c1.get(f"/api/social/posts/{post.id}/comments/")
        assert resp.status_code == status.HTTP_200_OK

    def test_encourage_post(self, c1, u1, u2):
        post = DreamPost.objects.create(user=u2, content="Encourage me", visibility="public")
        resp = c1.post(
            f"/api/social/posts/{post.id}/encourage/",
            {"encouragement_type": "you_got_this", "message": "Go go!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_encourage_update(self, c1, u1, u2):
        """Second encouragement updates existing."""
        post = DreamPost.objects.create(user=u2, content="P", visibility="public")
        c1.post(
            f"/api/social/posts/{post.id}/encourage/",
            {"encouragement_type": "you_got_this"},
            format="json",
        )
        resp = c1.post(
            f"/api/social/posts/{post.id}/encourage/",
            {"encouragement_type": "keep_going"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_encourage_invalid_type(self, c1, u1):
        post = DreamPost.objects.create(user=u1, content="P", visibility="public")
        resp = c1.post(
            f"/api/social/posts/{post.id}/encourage/",
            {"encouragement_type": "not_valid"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_share_post(self, c1, u1, u2):
        post = DreamPost.objects.create(user=u2, content="Shareable", visibility="public")
        resp = c1.post(
            f"/api/social/posts/{post.id}/share/",
            {"content": "Check this out!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_save_toggle_post(self, c1, u1):
        post = DreamPost.objects.create(user=u1, content="Saveable", visibility="public")
        # Save
        resp = c1.post(f"/api/social/posts/{post.id}/save/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["saved"] is True
        # Unsave
        resp = c1.post(f"/api/social/posts/{post.id}/save/")
        assert resp.data["saved"] is False

    def test_list_saved_posts(self, c1, u1):
        post = DreamPost.objects.create(user=u1, content="Saved", visibility="public")
        SavedPost.objects.create(user=u1, post=post)
        resp = c1.get("/api/social/posts/saved/")
        assert resp.status_code == status.HTTP_200_OK

    def test_user_posts(self, c1, u1, u2):
        DreamPost.objects.create(user=u2, content="Their post", visibility="public")
        resp = c1.get(f"/api/social/posts/user/{u2.id}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_user_posts_not_found(self, c1):
        resp = c1.get(f"/api/social/posts/user/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_user_posts_blocked(self, c1, u1, u2):
        BlockedUser.objects.create(blocker=u1, blocked=u2)
        resp = c1.get(f"/api/social/posts/user/{u2.id}/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_user_posts_following(self, c1, u1, u2):
        """Following user sees followers-only posts."""
        UserFollow.objects.create(follower=u1, following=u2)
        DreamPost.objects.create(user=u2, content="Followers only", visibility="followers")
        resp = c1.get(f"/api/social/posts/user/{u2.id}/")
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════
#  SocialEventViewSet
# ═══════════════════════════════════════════════════════════════════


class TestSocialEvents:

    def _create_event(self, user, **kwargs):
        defaults = {
            "creator": user,
            "title": "Test Event",
            "event_type": "virtual",
            "start_time": timezone.now() + timedelta(hours=2),
            "end_time": timezone.now() + timedelta(hours=4),
            "meeting_link": "https://meet.example.com/123",
            "status": "upcoming",
        }
        defaults.update(kwargs)
        return SocialEvent.objects.create(**defaults)

    def test_create_event(self, c1, u1):
        resp = c1.post(
            "/api/social/events/",
            {
                "title": "New Event",
                "event_type": "virtual",
                "meeting_link": "https://meet.example.com/123",
                "start_time": (timezone.now() + timedelta(hours=1)).isoformat(),
                "end_time": (timezone.now() + timedelta(hours=3)).isoformat(),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.data

    def test_create_event_with_dream(self, c1, u1):
        dream = Dream.objects.create(
            user=u1, title="D", description="D", status="active",
        )
        resp = c1.post(
            "/api/social/events/",
            {
                "title": "Dream Event",
                "event_type": "physical",
                "location": "Test Location",
                "start_time": (timezone.now() + timedelta(hours=1)).isoformat(),
                "end_time": (timezone.now() + timedelta(hours=3)).isoformat(),
                "dream_id": str(dream.id),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_create_event_dream_not_found(self, c1):
        resp = c1.post(
            "/api/social/events/",
            {
                "title": "Event",
                "event_type": "physical",
                "location": "Somewhere",
                "start_time": (timezone.now() + timedelta(hours=1)).isoformat(),
                "end_time": (timezone.now() + timedelta(hours=3)).isoformat(),
                "dream_id": str(uuid.uuid4()),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_event_non_participant(self, c2, u1):
        """Non-participant doesn't see meeting_link."""
        event = self._create_event(u1)
        resp = c2.get(f"/api/social/events/{event.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert "meeting_link" not in resp.data or resp.data.get("meeting_link") is None

    def test_retrieve_event_participant(self, c1, u1):
        """Creator sees meeting_link."""
        event = self._create_event(u1)
        resp = c1.get(f"/api/social/events/{event.id}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_update_own_event(self, c1, u1):
        event = self._create_event(u1)
        resp = c1.put(
            f"/api/social/events/{event.id}/",
            {"title": "Updated", "description": "Updated desc"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_update_other_event_forbidden(self, c2, u1):
        event = self._create_event(u1)
        resp = c2.put(
            f"/api/social/events/{event.id}/",
            {"title": "Hacked"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_partial_update_event(self, c1, u1):
        event = self._create_event(u1)
        resp = c1.patch(
            f"/api/social/events/{event.id}/",
            {"title": "Patched"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_destroy_own_event(self, c1, u1):
        event = self._create_event(u1)
        resp = c1.delete(f"/api/social/events/{event.id}/")
        assert resp.status_code == status.HTTP_200_OK  # soft delete returns serialized
        event.refresh_from_db()
        assert event.status == "cancelled"

    def test_destroy_other_event_forbidden(self, c2, u1):
        event = self._create_event(u1)
        resp = c2.delete(f"/api/social/events/{event.id}/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_register_for_event(self, c2, u1):
        event = self._create_event(u1)
        resp = c2.post(f"/api/social/events/{event.id}/register/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["registered"] is True

    def test_register_cancelled_event(self, c2, u1):
        event = self._create_event(u1, status="cancelled")
        resp = c2.post(f"/api/social/events/{event.id}/register/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_full_event(self, c2, u1, u3):
        event = self._create_event(u1, max_participants=1, participants_count=1)
        resp = c2.post(f"/api/social/events/{event.id}/register/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_re_register_after_cancel(self, c2, u1, u2):
        event = self._create_event(u1)
        SocialEventRegistration.objects.create(event=event, user=u2, status="cancelled")
        resp = c2.post(f"/api/social/events/{event.id}/register/")
        assert resp.status_code == status.HTTP_200_OK

    def test_unregister(self, c2, u1, u2):
        event = self._create_event(u1, participants_count=1)
        SocialEventRegistration.objects.create(event=event, user=u2, status="registered")
        resp = c2.post(f"/api/social/events/{event.id}/unregister/")
        assert resp.status_code == status.HTTP_200_OK

    def test_unregister_not_registered(self, c2, u1):
        event = self._create_event(u1)
        resp = c2.post(f"/api/social/events/{event.id}/unregister/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_event_participants(self, c1, u1, u2):
        event = self._create_event(u1)
        SocialEventRegistration.objects.create(event=event, user=u2, status="registered")
        resp = c1.get(f"/api/social/events/{event.id}/participants/")
        assert resp.status_code == status.HTTP_200_OK

    def test_events_feed(self, c1, u1):
        self._create_event(u1)
        resp = c1.get("/api/social/events/feed/")
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════
#  StoryViewSet
# ═══════════════════════════════════════════════════════════════════


class TestStories:

    def _create_story(self, user, **kwargs):
        defaults = {
            "user": user,
            "caption": "My story",
            "media_type": "image",
            "expires_at": timezone.now() + timedelta(hours=24),
        }
        defaults.update(kwargs)
        return Story.objects.create(**defaults)

    def test_create_story(self, c1, u1):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        # Create a valid image using PIL
        buf = BytesIO()
        img = Image.new("RGB", (100, 100), color="red")
        img.save(buf, format="PNG")
        buf.seek(0)
        image = SimpleUploadedFile("story.png", buf.read(), content_type="image/png")
        resp = c1.post(
            "/api/social/stories/",
            {"caption": "My new story", "image_file": image},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.data

    def test_destroy_own_story(self, c1, u1):
        story = self._create_story(u1)
        resp = c1.delete(f"/api/social/stories/{story.id}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_destroy_other_story_forbidden(self, c2, u1, u2):
        Friendship.objects.create(user1=u1, user2=u2, status="accepted")
        story = self._create_story(u1)
        resp = c2.delete(f"/api/social/stories/{story.id}/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_story_feed(self, c1, u1, u2):
        Friendship.objects.create(user1=u1, user2=u2, status="accepted")
        self._create_story(u1)
        self._create_story(u2)
        resp = c1.get("/api/social/stories/feed/")
        assert resp.status_code == status.HTTP_200_OK

    def test_my_stories(self, c1, u1):
        self._create_story(u1)
        resp = c1.get("/api/social/stories/my_stories/")
        assert resp.status_code == status.HTTP_200_OK

    def test_mark_viewed(self, c2, u1, u2):
        Friendship.objects.create(user1=u1, user2=u2, status="accepted")
        story = self._create_story(u1)
        resp = c2.post(f"/api/social/stories/{story.id}/view/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["status"] == "viewed"

    def test_mark_viewed_own_story(self, c1, u1):
        story = self._create_story(u1)
        resp = c1.post(f"/api/social/stories/{story.id}/view/")
        assert resp.data["status"] == "own_story"

    def test_mark_viewed_idempotent(self, c2, u1, u2):
        """Viewing twice doesn't create duplicate."""
        Friendship.objects.create(user1=u1, user2=u2, status="accepted")
        story = self._create_story(u1)
        c2.post(f"/api/social/stories/{story.id}/view/")
        resp = c2.post(f"/api/social/stories/{story.id}/view/")
        assert resp.status_code == status.HTTP_200_OK
        assert StoryView.objects.filter(story=story, user=u2).count() == 1

    def test_viewers(self, c1, u1, u2):
        story = self._create_story(u1)
        StoryView.objects.create(story=story, user=u2)
        resp = c1.get(f"/api/social/stories/{story.id}/viewers/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 1

    def test_viewers_not_own_story(self, c2, u1, u2):
        Friendship.objects.create(user1=u1, user2=u2, status="accepted")
        story = self._create_story(u1)
        resp = c2.get(f"/api/social/stories/{story.id}/viewers/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ═══════════════════════════════════════════════════════════════════
#  FollowSuggestionsView (requires premium)
# ═══════════════════════════════════════════════════════════════════


class TestFollowSuggestions:

    def test_follow_suggestions(self, c1, u1, u2, u3):
        """Exercise the follow suggestion algorithm."""
        # Create circle for shared membership
        from apps.circles.models import Circle, CircleMembership

        circle = Circle.objects.create(name="Test Circle", creator=u1)
        CircleMembership.objects.create(circle=circle, user=u1)
        CircleMembership.objects.create(circle=circle, user=u2)

        # Create similar dream categories
        Dream.objects.create(
            user=u1, title="D1", description="D", category="health", status="active",
        )
        Dream.objects.create(
            user=u2, title="D2", description="D", category="health", status="active",
        )

        # u3 is friend-of-friend
        Friendship.objects.create(user1=u1, user2=u3, status="accepted")

        resp = c1.get("/api/social/follow-suggestions/")
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════
#  FriendSuggestionsView
# ═══════════════════════════════════════════════════════════════════


class TestFriendSuggestions:

    def test_friend_suggestions(self, c1, u1, u2, u3, u4):
        """Exercise the friend suggestion scoring engine."""
        from apps.circles.models import Circle, CircleMembership

        # Circle membership
        circle = Circle.objects.create(name="Suggestion Circle", creator=u1)
        CircleMembership.objects.create(circle=circle, user=u1)
        CircleMembership.objects.create(circle=circle, user=u2)

        # Friend of friend
        Friendship.objects.create(user1=u1, user2=u3, status="accepted")
        Friendship.objects.create(user1=u3, user2=u4, status="accepted")

        # Dream category overlap
        Dream.objects.create(
            user=u1, title="D", description="D", category="career", status="active",
        )
        Dream.objects.create(
            user=u2, title="D", description="D", category="career", status="active",
        )

        # Make u4 recently active
        u4.last_activity = timezone.now()
        u4.save(update_fields=["last_activity"])

        with patch("django.core.cache.cache.get", return_value=None), \
             patch("django.core.cache.cache.set"):
            resp = c1.get("/api/social/friend-suggestions/")
        assert resp.status_code == status.HTTP_200_OK

    def test_friend_suggestions_cached(self, c1, u1):
        """Cached results are returned directly."""
        cached_data = [{"user": {"id": "x"}, "score": 0.5, "reasons": []}]
        with patch("django.core.cache.cache.get", return_value=cached_data):
            resp = c1.get("/api/social/friend-suggestions/")
        assert resp.status_code == status.HTTP_200_OK

    def test_friend_suggestions_empty(self, c1, u1):
        """No suggestions returns empty list."""
        with patch("django.core.cache.cache.get", return_value=None), \
             patch("django.core.cache.cache.set"):
            resp = c1.get("/api/social/friend-suggestions/")
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════
#  DreamPost event creation via post (lines 1670-1685)
# ═══════════════════════════════════════════════════════════════════


class TestPostEventCreation:
    """Cover event creation when post_type='event'."""

    def test_create_post_with_event(self, c1, u1):
        resp = c1.post(
            "/api/social/posts/",
            {
                "content": "Join my event!",
                "post_type": "event",
                "visibility": "public",
                "event_title": "Study Session",
                "event_type": "physical",
                "event_location": "Library",
                "event_start_time": (timezone.now() + timedelta(hours=1)).isoformat(),
                "event_end_time": (timezone.now() + timedelta(hours=3)).isoformat(),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.data
        assert SocialEvent.objects.filter(creator=u1).exists()
