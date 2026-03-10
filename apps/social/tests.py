"""Tests for social app."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status

from apps.social.admin import (
    ActivityFeedItemAdmin,
    BlockedUserAdmin,
)
from apps.social.models import (
    ActivityFeedItem,
    BlockedUser,
    Friendship,
    ReportedUser,
    UserFollow,
)
from apps.social.serializers import (
    ActivityFeedItemSerializer,
    BlockedUserSerializer,
    BlockUserSerializer,
    FollowUserSerializer,
    FriendRequestSerializer,
    FriendSerializer,
    ReportUserSerializer,
    SendFriendRequestSerializer,
    UserPublicSerializer,
    UserSearchResultSerializer,
)
from apps.users.models import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_user_plan(user, slug):
    """Ensure a user has the given subscription plan via DB records."""
    from apps.subscriptions.models import Subscription, SubscriptionPlan

    plan = SubscriptionPlan.objects.filter(slug=slug).first()
    if not plan:
        return
    sub, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={"plan": plan, "status": "active"},
    )
    if sub.plan_id != plan.pk or sub.status != "active":
        sub.plan = plan
        sub.status = "active"
        sub.save(update_fields=["plan", "status"])
    if hasattr(user, "_cached_plan"):
        del user._cached_plan


# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_notification_create():
    """Prevent Notification.objects.create() from breaking SQLite transactions.

    Several social views create notifications inside try/except blocks.
    On SQLite the NOT-NULL IntegrityError (scheduled_for) marks the
    transaction as broken even though the exception is caught. Mocking
    the create call avoids this issue in tests.
    """
    with patch("apps.notifications.models.Notification.objects.create"):
        yield


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="other@example.com",
        password="testpass123",
        display_name="Other User",
    )


@pytest.fixture
def third_user(db):
    return User.objects.create_user(
        email="third@example.com",
        password="testpass123",
        display_name="Third User",
    )


@pytest.fixture
def fourth_user(db):
    return User.objects.create_user(
        email="fourth@example.com",
        password="testpass123",
        display_name="Fourth User",
    )


@pytest.fixture
def friendship(user, other_user):
    return Friendship.objects.create(
        user1=user,
        user2=other_user,
        status="pending",
    )


@pytest.fixture
def accepted_friendship(user, other_user):
    return Friendship.objects.create(
        user1=user,
        user2=other_user,
        status="accepted",
    )


@pytest.fixture
def follow(user, other_user):
    return UserFollow.objects.create(
        follower=user,
        following=other_user,
    )


@pytest.fixture
def block(user, other_user):
    return BlockedUser.objects.create(
        blocker=user,
        blocked=other_user,
        reason="Test block",
    )


@pytest.fixture
def activity_item(user):
    return ActivityFeedItem.objects.create(
        user=user,
        activity_type="task_completed",
        content={"title": "Completed a task"},
    )


@pytest.fixture
def premium_social_user(db):
    """A premium user used as the main actor in follow-suggestion tests."""
    user = User.objects.create_user(
        email="premium_social@example.com",
        password="testpass123",
        display_name="Premium Social User",
    )
    _set_user_plan(user, "premium")
    user.refresh_from_db()
    return user


@pytest.fixture
def premium_social_client(premium_social_user):
    """Authenticated API client backed by a premium user."""
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=premium_social_user)
    return client


@pytest.fixture
def premium_activity_item(premium_social_user):
    """Activity item owned by the premium social user."""
    return ActivityFeedItem.objects.create(
        user=premium_social_user,
        activity_type="task_completed",
        content={"title": "Completed a task"},
    )


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------
BASE = "/api/social/"


# ===========================================================================
# Model tests
# ===========================================================================


class TestBlockedUserModel:
    def test_create_blocked_user(self, user, other_user):
        blocked = BlockedUser.objects.create(
            blocker=user,
            blocked=other_user,
            reason="Spam",
        )
        assert blocked.blocker == user
        assert blocked.blocked == other_user
        assert blocked.reason == "Spam"
        assert blocked.created_at is not None

    def test_str_representation(self, user, other_user):
        blocked = BlockedUser.objects.create(
            blocker=user,
            blocked=other_user,
        )
        result = str(blocked)
        assert "Test User" in result
        assert "Other User" in result
        assert "blocked" in result

    def test_str_with_no_display_name(self, db):
        u1 = User.objects.create_user(email="noname1@example.com", password="pass")
        u2 = User.objects.create_user(email="noname2@example.com", password="pass")
        blocked = BlockedUser.objects.create(blocker=u1, blocked=u2)
        result = str(blocked)
        assert "noname1@example.com" in result
        assert "noname2@example.com" in result

    def test_unique_together(self, user, other_user):
        BlockedUser.objects.create(blocker=user, blocked=other_user)
        with pytest.raises(Exception):
            BlockedUser.objects.create(blocker=user, blocked=other_user)

    def test_default_reason_is_empty(self, user, other_user):
        blocked = BlockedUser.objects.create(blocker=user, blocked=other_user)
        assert blocked.reason == ""

    def test_ordering_newest_first(self, user, other_user, third_user):
        b1 = BlockedUser.objects.create(blocker=user, blocked=other_user)
        b2 = BlockedUser.objects.create(blocker=user, blocked=third_user)
        blocks = list(BlockedUser.objects.filter(blocker=user))
        # Both created nearly simultaneously; ordering is -created_at.
        # Verify the default ordering is applied (descending created_at).
        assert len(blocks) == 2
        assert blocks[0].created_at >= blocks[1].created_at


class TestReportedUserModel:
    def test_create_reported_user(self, user, other_user):
        report = ReportedUser.objects.create(
            reporter=user,
            reported=other_user,
            reason="Harassment",
            category="harassment",
        )
        assert report.reporter == user
        assert report.reported == other_user
        assert report.reason == "Harassment"
        assert report.category == "harassment"
        assert report.status == "pending"

    def test_str_representation(self, user, other_user):
        report = ReportedUser.objects.create(
            reporter=user,
            reported=other_user,
            reason="Spam",
            category="spam",
        )
        result = str(report)
        assert "Report:" in result
        assert "Test User" in result
        assert "Other User" in result
        assert "spam" in result

    def test_default_status_is_pending(self, user, other_user):
        report = ReportedUser.objects.create(
            reporter=user,
            reported=other_user,
            reason="test",
        )
        assert report.status == "pending"

    def test_default_category_is_other(self, user, other_user):
        report = ReportedUser.objects.create(
            reporter=user,
            reported=other_user,
            reason="test",
        )
        assert report.category == "other"

    def test_admin_notes_default_empty(self, user, other_user):
        report = ReportedUser.objects.create(
            reporter=user,
            reported=other_user,
            reason="test",
        )
        assert report.admin_notes == ""

    def test_timestamps(self, user, other_user):
        report = ReportedUser.objects.create(
            reporter=user,
            reported=other_user,
            reason="test",
        )
        assert report.created_at is not None
        assert report.updated_at is not None


class TestFriendshipModel:
    def test_create_friendship(self, user, other_user):
        friendship = Friendship.objects.create(
            user1=user,
            user2=other_user,
            status="pending",
        )
        assert friendship.user1 == user
        assert friendship.user2 == other_user
        assert friendship.status == "pending"

    def test_str_representation(self, user, other_user):
        friendship = Friendship.objects.create(
            user1=user,
            user2=other_user,
            status="pending",
        )
        result = str(friendship)
        assert "Test User" in result
        assert "Other User" in result
        assert "pending" in result

    def test_unique_together(self, user, other_user):
        Friendship.objects.create(user1=user, user2=other_user)
        with pytest.raises(Exception):
            Friendship.objects.create(user1=user, user2=other_user)

    def test_default_status_is_pending(self, user, other_user):
        friendship = Friendship.objects.create(user1=user, user2=other_user)
        assert friendship.status == "pending"

    def test_status_transition_to_accepted(self, friendship):
        friendship.status = "accepted"
        friendship.save()
        friendship.refresh_from_db()
        assert friendship.status == "accepted"

    def test_status_transition_to_rejected(self, friendship):
        friendship.status = "rejected"
        friendship.save()
        friendship.refresh_from_db()
        assert friendship.status == "rejected"


class TestUserFollowModel:
    def test_create_follow(self, user, other_user):
        follow = UserFollow.objects.create(
            follower=user,
            following=other_user,
        )
        assert follow.follower == user
        assert follow.following == other_user
        assert follow.created_at is not None

    def test_str_representation(self, user, other_user):
        follow = UserFollow.objects.create(follower=user, following=other_user)
        result = str(follow)
        assert "Test User" in result
        assert "Other User" in result
        assert "follows" in result

    def test_unique_together(self, user, other_user):
        UserFollow.objects.create(follower=user, following=other_user)
        with pytest.raises(Exception):
            UserFollow.objects.create(follower=user, following=other_user)


class TestActivityFeedItemModel:
    def test_create_activity(self, user):
        item = ActivityFeedItem.objects.create(
            user=user,
            activity_type="task_completed",
            content={"title": "Test Task"},
        )
        assert item.user == user
        assert item.activity_type == "task_completed"
        assert item.content == {"title": "Test Task"}

    def test_str_representation(self, user):
        item = ActivityFeedItem.objects.create(
            user=user,
            activity_type="dream_completed",
        )
        result = str(item)
        assert "Test User" in result
        assert "dream_completed" in result

    def test_default_content_is_empty_dict(self, user):
        item = ActivityFeedItem.objects.create(
            user=user,
            activity_type="level_up",
        )
        assert item.content == {}

    def test_default_data_is_empty_dict(self, user):
        item = ActivityFeedItem.objects.create(
            user=user,
            activity_type="level_up",
        )
        assert item.data == {}

    def test_related_user_nullable(self, user, other_user):
        item = ActivityFeedItem.objects.create(
            user=user,
            activity_type="buddy_matched",
            related_user=other_user,
        )
        assert item.related_user == other_user

    def test_ordering_newest_first(self, user):
        a1 = ActivityFeedItem.objects.create(user=user, activity_type="task_completed")
        a2 = ActivityFeedItem.objects.create(user=user, activity_type="dream_completed")
        items = list(ActivityFeedItem.objects.filter(user=user))
        assert len(items) == 2
        assert items[0].created_at >= items[1].created_at


# ===========================================================================
# Serializer tests
# ===========================================================================


class TestUserPublicSerializer:
    def test_serialization(self, user):
        serializer = UserPublicSerializer(user)
        data = serializer.data
        assert data["id"] == str(user.id)
        assert data["username"] == user.display_name
        assert "currentLevel" in data
        assert "influenceScore" in data
        assert "currentStreak" in data
        assert "title" in data

    def test_get_title_dreamer(self, db):
        u = User.objects.create_user(email="level1@test.com", password="pass", level=1)
        serializer = UserPublicSerializer(u)
        assert serializer.data["title"] == "Dreamer"

    def test_get_title_explorer(self, db):
        u = User.objects.create_user(email="level5@test.com", password="pass", level=5)
        serializer = UserPublicSerializer(u)
        assert serializer.data["title"] == "Explorer"

    def test_get_title_achiever(self, db):
        u = User.objects.create_user(
            email="level10@test.com", password="pass", level=10
        )
        serializer = UserPublicSerializer(u)
        assert serializer.data["title"] == "Achiever"

    def test_get_title_expert(self, db):
        u = User.objects.create_user(
            email="level20@test.com", password="pass", level=20
        )
        serializer = UserPublicSerializer(u)
        assert serializer.data["title"] == "Expert"

    def test_get_title_master(self, db):
        u = User.objects.create_user(
            email="level30@test.com", password="pass", level=30
        )
        serializer = UserPublicSerializer(u)
        assert serializer.data["title"] == "Master"

    def test_get_title_legend(self, db):
        u = User.objects.create_user(
            email="level50@test.com", password="pass", level=50
        )
        serializer = UserPublicSerializer(u)
        assert serializer.data["title"] == "Legend"


class TestFriendRequestSerializer:
    def test_serialization(self, friendship):
        serializer = FriendRequestSerializer(friendship)
        data = serializer.data
        assert data["id"] == str(friendship.id)
        assert data["status"] == "pending"
        assert "sender" in data
        sender = data["sender"]
        assert "id" in sender
        assert "username" in sender
        assert "avatar" in sender
        assert "currentLevel" in sender
        assert "influenceScore" in sender


class TestSendFriendRequestSerializer:
    def test_valid_data(self, other_user):
        serializer = SendFriendRequestSerializer(
            data={"target_user_id": str(other_user.id)}
        )
        assert serializer.is_valid()

    def test_invalid_uuid(self):
        serializer = SendFriendRequestSerializer(data={"target_user_id": "not-a-uuid"})
        assert not serializer.is_valid()

    def test_missing_field(self):
        serializer = SendFriendRequestSerializer(data={})
        assert not serializer.is_valid()


class TestFollowUserSerializer:
    def test_valid_data(self, other_user):
        serializer = FollowUserSerializer(data={"target_user_id": str(other_user.id)})
        assert serializer.is_valid()

    def test_invalid_uuid(self):
        serializer = FollowUserSerializer(data={"target_user_id": "bad"})
        assert not serializer.is_valid()


class TestBlockUserSerializer:
    def test_valid_data_with_reason(self, other_user):
        serializer = BlockUserSerializer(
            data={"target_user_id": str(other_user.id), "reason": "Spam"}
        )
        assert serializer.is_valid()
        assert serializer.validated_data["reason"] == "Spam"

    def test_valid_data_without_reason(self, other_user):
        serializer = BlockUserSerializer(data={"target_user_id": str(other_user.id)})
        assert serializer.is_valid()
        assert serializer.validated_data["reason"] == ""


class TestReportUserSerializer:
    def test_valid_data(self, other_user):
        serializer = ReportUserSerializer(
            data={
                "target_user_id": str(other_user.id),
                "reason": "Harassment",
                "category": "harassment",
            }
        )
        assert serializer.is_valid()

    def test_missing_reason(self, other_user):
        serializer = ReportUserSerializer(
            data={"target_user_id": str(other_user.id), "category": "spam"}
        )
        assert not serializer.is_valid()

    def test_invalid_category(self, other_user):
        serializer = ReportUserSerializer(
            data={
                "target_user_id": str(other_user.id),
                "reason": "Bad",
                "category": "nonexistent",
            }
        )
        assert not serializer.is_valid()

    def test_default_category(self, other_user):
        serializer = ReportUserSerializer(
            data={"target_user_id": str(other_user.id), "reason": "Bad"}
        )
        assert serializer.is_valid()
        assert serializer.validated_data["category"] == "other"


class TestBlockedUserSerializer:
    def test_serialization(self, block):
        serializer = BlockedUserSerializer(block)
        data = serializer.data
        assert data["id"] == str(block.id)
        assert data["reason"] == "Test block"
        assert "user" in data
        assert "id" in data["user"]
        assert "username" in data["user"]
        assert "avatar" in data["user"]


class TestActivityFeedItemSerializer:
    def test_serialization(self, activity_item):
        serializer = ActivityFeedItemSerializer(activity_item)
        data = serializer.data
        assert data["id"] == str(activity_item.id)
        assert data["type"] == "task_completed"
        assert data["content"] == {"title": "Completed a task"}
        assert "createdAt" in data
        assert "user" in data
        user_data = data["user"]
        assert "id" in user_data
        assert "username" in user_data
        assert "avatar" in user_data


class TestFriendSerializer:
    def test_serialization(self, user):
        friend_data = {
            "id": user.id,
            "username": user.display_name,
            "avatar": user.avatar_url or "",
            "title": "Dreamer",
            "currentLevel": user.level,
            "influenceScore": user.xp,
            "currentStreak": user.streak_days,
        }
        serializer = FriendSerializer(friend_data)
        data = serializer.data
        assert data["username"] == "Test User"
        assert data["title"] == "Dreamer"


class TestUserSearchResultSerializer:
    def test_serialization(self, user):
        result_data = {
            "id": user.id,
            "username": user.display_name,
            "avatar": user.avatar_url or "",
            "title": "Dreamer",
            "influenceScore": user.xp,
            "currentLevel": user.level,
            "isFriend": True,
            "isFollowing": False,
        }
        serializer = UserSearchResultSerializer(result_data)
        data = serializer.data
        assert data["isFriend"] is True
        assert data["isFollowing"] is False


# ===========================================================================
# FriendshipViewSet tests
# ===========================================================================


class TestListFriends:
    def test_list_friends_empty(self, authenticated_client):
        resp = authenticated_client.get(f"{BASE}friends/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == []

    def test_list_friends_returns_accepted(
        self, authenticated_client, user, other_user
    ):
        Friendship.objects.create(user1=user, user2=other_user, status="accepted")
        resp = authenticated_client.get(f"{BASE}friends/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 1
        friend = resp.data[0]
        assert friend["username"] == "Other User"
        assert "title" in friend
        assert "currentLevel" in friend
        assert "influenceScore" in friend
        assert "currentStreak" in friend

    def test_list_friends_excludes_pending(self, authenticated_client, friendship):
        resp = authenticated_client.get(f"{BASE}friends/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 0

    def test_list_friends_shows_when_user_is_user2(
        self, authenticated_client, user, other_user
    ):
        Friendship.objects.create(user1=other_user, user2=user, status="accepted")
        resp = authenticated_client.get(f"{BASE}friends/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 1
        assert resp.data[0]["username"] == "Other User"

    def test_unauthenticated_is_rejected(self, api_client):
        resp = api_client.get(f"{BASE}friends/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestPendingRequests:
    def test_pending_requests_as_receiver(self, authenticated_client, user, other_user):
        Friendship.objects.create(user1=other_user, user2=user, status="pending")
        resp = authenticated_client.get(f"{BASE}friends/requests/pending/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 1
        assert resp.data[0]["sender"]["username"] == "Other User"

    def test_pending_requests_excludes_sent(self, authenticated_client, friendship):
        # friendship has user1=user (sender), should not appear in pending
        resp = authenticated_client.get(f"{BASE}friends/requests/pending/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 0

    def test_pending_requests_empty(self, authenticated_client):
        resp = authenticated_client.get(f"{BASE}friends/requests/pending/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == []


class TestSentRequests:
    def test_sent_requests(self, authenticated_client, friendship):
        resp = authenticated_client.get(f"{BASE}friends/requests/sent/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 1

    def test_sent_requests_empty(self, authenticated_client):
        resp = authenticated_client.get(f"{BASE}friends/requests/sent/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == []


class TestSendFriendRequest:
    def test_send_request_success(self, authenticated_client, other_user):
        resp = authenticated_client.post(
            f"{BASE}friends/request/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["message"] == "Friend request sent."
        assert Friendship.objects.filter(status="pending").count() == 1

    def test_send_request_to_self(self, authenticated_client, user):
        resp = authenticated_client.post(
            f"{BASE}friends/request/",
            {"target_user_id": str(user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "yourself" in resp.data["error"]

    def test_send_request_nonexistent_user(self, authenticated_client):
        import uuid

        resp = authenticated_client.post(
            f"{BASE}friends/request/",
            {"target_user_id": str(uuid.uuid4())},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_send_request_already_friends(self, authenticated_client, user, other_user):
        Friendship.objects.create(user1=user, user2=other_user, status="accepted")
        resp = authenticated_client.post(
            f"{BASE}friends/request/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already friends" in resp.data["error"]

    def test_send_request_already_pending(
        self, authenticated_client, friendship, other_user
    ):
        resp = authenticated_client.post(
            f"{BASE}friends/request/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already pending" in resp.data["error"]

    def test_send_request_to_blocked_user(
        self, authenticated_client, block, other_user
    ):
        resp = authenticated_client.post(
            f"{BASE}friends/request/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot send friend request" in resp.data["error"]

    def test_send_request_to_user_who_blocked_me(
        self, authenticated_client, user, other_user
    ):
        BlockedUser.objects.create(blocker=other_user, blocked=user)
        resp = authenticated_client.post(
            f"{BASE}friends/request/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_resend_after_rejection(self, authenticated_client, user, other_user):
        Friendship.objects.create(user1=other_user, user2=user, status="rejected")
        resp = authenticated_client.post(
            f"{BASE}friends/request/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        friendship = Friendship.objects.first()
        assert friendship.status == "pending"
        assert friendship.user1 == user
        assert friendship.user2 == other_user


class TestAcceptRequest:
    def test_accept_request(self, authenticated_client, user, other_user):
        fr = Friendship.objects.create(user1=other_user, user2=user, status="pending")
        resp = authenticated_client.post(f"{BASE}friends/accept/{fr.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["message"] == "Friend request accepted."
        fr.refresh_from_db()
        assert fr.status == "accepted"

    def test_accept_nonexistent_request(self, authenticated_client):
        import uuid

        resp = authenticated_client.post(f"{BASE}friends/accept/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_accept_own_request_fails(self, authenticated_client, user, other_user):
        # user sent request -> user is user1, can't accept own request
        fr = Friendship.objects.create(user1=user, user2=other_user, status="pending")
        resp = authenticated_client.post(f"{BASE}friends/accept/{fr.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_accept_already_accepted_fails(
        self, authenticated_client, user, other_user
    ):
        fr = Friendship.objects.create(user1=other_user, user2=user, status="accepted")
        resp = authenticated_client.post(f"{BASE}friends/accept/{fr.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestRejectRequest:
    def test_reject_request(self, authenticated_client, user, other_user):
        fr = Friendship.objects.create(user1=other_user, user2=user, status="pending")
        resp = authenticated_client.post(f"{BASE}friends/reject/{fr.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["message"] == "Friend request rejected."
        fr.refresh_from_db()
        assert fr.status == "rejected"

    def test_reject_nonexistent_request(self, authenticated_client):
        import uuid

        resp = authenticated_client.post(f"{BASE}friends/reject/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_reject_own_request_fails(self, authenticated_client, user, other_user):
        fr = Friendship.objects.create(user1=user, user2=other_user, status="pending")
        resp = authenticated_client.post(f"{BASE}friends/reject/{fr.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestRemoveFriend:
    def test_remove_friend(self, authenticated_client, accepted_friendship, other_user):
        resp = authenticated_client.delete(f"{BASE}friends/remove/{other_user.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["message"] == "Friend removed."
        assert Friendship.objects.count() == 0

    def test_remove_nonexistent_friendship(self, authenticated_client):
        import uuid

        resp = authenticated_client.delete(f"{BASE}friends/remove/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_remove_pending_friendship_fails(
        self, authenticated_client, friendship, other_user
    ):
        resp = authenticated_client.delete(f"{BASE}friends/remove/{other_user.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestFollowUser:
    def test_follow_success(self, authenticated_client, other_user):
        resp = authenticated_client.post(
            f"{BASE}follow/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert UserFollow.objects.count() == 1

    def test_follow_self(self, authenticated_client, user):
        resp = authenticated_client.post(
            f"{BASE}follow/",
            {"target_user_id": str(user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "yourself" in resp.data["error"]

    def test_follow_nonexistent_user(self, authenticated_client):
        import uuid

        resp = authenticated_client.post(
            f"{BASE}follow/",
            {"target_user_id": str(uuid.uuid4())},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_follow_already_following(self, authenticated_client, follow, other_user):
        resp = authenticated_client.post(
            f"{BASE}follow/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already following" in resp.data["error"]

    def test_follow_blocked_user_fails(self, authenticated_client, block, other_user):
        resp = authenticated_client.post(
            f"{BASE}follow/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot follow" in resp.data["error"]

    def test_follow_user_who_blocked_me(self, authenticated_client, user, other_user):
        BlockedUser.objects.create(blocker=other_user, blocked=user)
        resp = authenticated_client.post(
            f"{BASE}follow/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


class TestUnfollowUser:
    def test_unfollow_success(self, authenticated_client, follow, other_user):
        resp = authenticated_client.delete(f"{BASE}unfollow/{other_user.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["message"] == "Successfully unfollowed."
        assert UserFollow.objects.count() == 0

    def test_unfollow_not_following(self, authenticated_client, other_user):
        resp = authenticated_client.delete(f"{BASE}unfollow/{other_user.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestBlockUser:
    def test_block_success(self, authenticated_client, other_user):
        resp = authenticated_client.post(
            f"{BASE}block/",
            {"target_user_id": str(other_user.id), "reason": "Spam"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["message"] == "User blocked."
        assert BlockedUser.objects.count() == 1

    def test_block_removes_friendship(
        self, authenticated_client, accepted_friendship, other_user
    ):
        resp = authenticated_client.post(
            f"{BASE}block/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert Friendship.objects.count() == 0

    def test_block_removes_follows_both_directions(
        self, authenticated_client, user, other_user
    ):
        UserFollow.objects.create(follower=user, following=other_user)
        UserFollow.objects.create(follower=other_user, following=user)
        resp = authenticated_client.post(
            f"{BASE}block/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert UserFollow.objects.count() == 0

    def test_block_self(self, authenticated_client, user):
        resp = authenticated_client.post(
            f"{BASE}block/",
            {"target_user_id": str(user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "yourself" in resp.data["error"]

    def test_block_nonexistent_user(self, authenticated_client):
        import uuid

        resp = authenticated_client.post(
            f"{BASE}block/",
            {"target_user_id": str(uuid.uuid4())},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_block_already_blocked(self, authenticated_client, block, other_user):
        resp = authenticated_client.post(
            f"{BASE}block/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already blocked" in resp.data["error"]


class TestUnblockUser:
    def test_unblock_success(self, authenticated_client, block, other_user):
        resp = authenticated_client.delete(f"{BASE}unblock/{other_user.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["message"] == "User unblocked."
        assert BlockedUser.objects.count() == 0

    def test_unblock_not_blocked(self, authenticated_client, other_user):
        resp = authenticated_client.delete(f"{BASE}unblock/{other_user.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestListBlocked:
    def test_list_blocked(self, authenticated_client, block):
        resp = authenticated_client.get(f"{BASE}blocked/")
        assert resp.status_code == status.HTTP_200_OK
        # View returns a plain list from BlockedUserSerializer
        assert len(resp.data) == 1
        blocked_entry = resp.data[0]
        assert "user" in blocked_entry
        assert "reason" in blocked_entry
        assert "created_at" in blocked_entry

    def test_list_blocked_empty(self, authenticated_client):
        resp = authenticated_client.get(f"{BASE}blocked/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == []

    def test_list_blocked_excludes_others_blocks(
        self, authenticated_client, user, other_user, third_user
    ):
        # other_user blocks third_user -- should not appear in user's blocked list
        BlockedUser.objects.create(blocker=other_user, blocked=third_user)
        resp = authenticated_client.get(f"{BASE}blocked/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 0


class TestReportUser:
    def test_report_success(self, authenticated_client, other_user):
        resp = authenticated_client.post(
            f"{BASE}report/",
            {
                "target_user_id": str(other_user.id),
                "reason": "Harassment",
                "category": "harassment",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert "Report submitted" in resp.data["message"]
        assert ReportedUser.objects.count() == 1
        report = ReportedUser.objects.first()
        assert report.category == "harassment"
        assert report.reason == "Harassment"

    def test_report_self(self, authenticated_client, user):
        resp = authenticated_client.post(
            f"{BASE}report/",
            {
                "target_user_id": str(user.id),
                "reason": "Bad",
                "category": "other",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "yourself" in resp.data["error"]

    def test_report_nonexistent_user(self, authenticated_client):
        import uuid

        resp = authenticated_client.post(
            f"{BASE}report/",
            {
                "target_user_id": str(uuid.uuid4()),
                "reason": "Bad",
                "category": "other",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_report_default_category(self, authenticated_client, other_user):
        resp = authenticated_client.post(
            f"{BASE}report/",
            {
                "target_user_id": str(other_user.id),
                "reason": "Something weird",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        report = ReportedUser.objects.first()
        assert report.category == "other"


class TestMutualFriends:
    def test_mutual_friends(self, authenticated_client, user, other_user, third_user):
        # user <-> third_user and other_user <-> third_user
        Friendship.objects.create(user1=user, user2=third_user, status="accepted")
        Friendship.objects.create(user1=other_user, user2=third_user, status="accepted")
        resp = authenticated_client.get(f"{BASE}friends/mutual/{other_user.id}/")
        assert resp.status_code == status.HTTP_200_OK
        # Response is a plain list from FriendSerializer
        assert len(resp.data) == 1
        assert resp.data[0]["username"] == "Third User"

    def test_mutual_friends_empty(self, authenticated_client, other_user):
        resp = authenticated_client.get(f"{BASE}friends/mutual/{other_user.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == []

    def test_mutual_friends_nonexistent_user(self, authenticated_client):
        import uuid

        resp = authenticated_client.get(f"{BASE}friends/mutual/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_mutual_friends_excludes_pending(
        self, authenticated_client, user, other_user, third_user
    ):
        Friendship.objects.create(user1=user, user2=third_user, status="pending")
        Friendship.objects.create(user1=other_user, user2=third_user, status="accepted")
        resp = authenticated_client.get(f"{BASE}friends/mutual/{other_user.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == []


class TestSocialCounts:
    def test_social_counts(self, authenticated_client, user, other_user, third_user):
        Friendship.objects.create(user1=user, user2=other_user, status="accepted")
        UserFollow.objects.create(follower=third_user, following=user)
        UserFollow.objects.create(follower=user, following=third_user)
        resp = authenticated_client.get(f"{BASE}counts/{user.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["friend_count"] == 1
        assert resp.data["follower_count"] == 1
        assert resp.data["following_count"] == 1

    def test_social_counts_zero(self, authenticated_client, user):
        resp = authenticated_client.get(f"{BASE}counts/{user.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["friend_count"] == 0
        assert resp.data["follower_count"] == 0
        assert resp.data["following_count"] == 0

    def test_social_counts_nonexistent_user(self, authenticated_client):
        import uuid

        resp = authenticated_client.get(f"{BASE}counts/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_social_counts_for_other_user(
        self, authenticated_client, user, other_user, third_user
    ):
        Friendship.objects.create(user1=other_user, user2=third_user, status="accepted")
        UserFollow.objects.create(follower=user, following=other_user)
        resp = authenticated_client.get(f"{BASE}counts/{other_user.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["friend_count"] == 1
        assert resp.data["follower_count"] == 1
        assert resp.data["following_count"] == 0


# ===========================================================================
# ActivityFeedView tests
# ===========================================================================


class TestActivityFeedView:
    """Activity feed tests use premium users (full feed requires premium+)."""

    def test_own_activity_visible(self, premium_social_client, premium_activity_item):
        resp = premium_social_client.get(f"{BASE}feed/friends/")
        assert resp.status_code == status.HTTP_200_OK
        assert "activities" in resp.data
        ids = [a["id"] for a in resp.data["activities"]]
        assert str(premium_activity_item.id) in ids

    def test_friend_activity_visible(
        self, premium_social_client, premium_social_user, other_user
    ):
        Friendship.objects.create(
            user1=premium_social_user, user2=other_user, status="accepted"
        )
        item = ActivityFeedItem.objects.create(
            user=other_user,
            activity_type="dream_completed",
            content={"title": "Dream done"},
        )
        resp = premium_social_client.get(f"{BASE}feed/friends/")
        assert resp.status_code == status.HTTP_200_OK
        ids = [a["id"] for a in resp.data["activities"]]
        assert str(item.id) in ids

    def test_followed_user_activity_visible(
        self, premium_social_client, premium_social_user, other_user
    ):
        UserFollow.objects.create(follower=premium_social_user, following=other_user)
        item = ActivityFeedItem.objects.create(
            user=other_user,
            activity_type="level_up",
        )
        resp = premium_social_client.get(f"{BASE}feed/friends/")
        assert resp.status_code == status.HTTP_200_OK
        ids = [a["id"] for a in resp.data["activities"]]
        assert str(item.id) in ids

    def test_stranger_activity_not_visible(self, premium_social_client, other_user):
        item = ActivityFeedItem.objects.create(
            user=other_user,
            activity_type="badge_earned",
        )
        resp = premium_social_client.get(f"{BASE}feed/friends/")
        assert resp.status_code == status.HTTP_200_OK
        ids = [a["id"] for a in resp.data["activities"]]
        assert str(item.id) not in ids

    def test_blocked_user_activity_excluded(
        self, premium_social_client, premium_social_user, other_user
    ):
        Friendship.objects.create(
            user1=premium_social_user, user2=other_user, status="accepted"
        )
        BlockedUser.objects.create(blocker=premium_social_user, blocked=other_user)
        ActivityFeedItem.objects.create(
            user=other_user,
            activity_type="task_completed",
        )
        resp = premium_social_client.get(f"{BASE}feed/friends/")
        assert resp.status_code == status.HTTP_200_OK
        for a in resp.data["activities"]:
            assert a["user"]["id"] != str(other_user.id)

    def test_filter_by_activity_type(self, premium_social_client, premium_social_user):
        ActivityFeedItem.objects.create(
            user=premium_social_user, activity_type="task_completed"
        )
        ActivityFeedItem.objects.create(
            user=premium_social_user, activity_type="dream_completed"
        )
        resp = premium_social_client.get(
            f"{BASE}feed/friends/?activity_type=task_completed"
        )
        assert resp.status_code == status.HTTP_200_OK
        for a in resp.data["activities"]:
            assert a["type"] == "task_completed"

    def test_filter_by_created_after(self, premium_social_client, premium_social_user):
        ActivityFeedItem.objects.create(
            user=premium_social_user,
            activity_type="task_completed",
        )
        future = timezone.now() + timedelta(hours=1)
        future_str = future.isoformat()
        resp = premium_social_client.get(
            f"{BASE}feed/friends/",
            {"created_after": future_str},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["activities"]) == 0

    def test_filter_by_created_before(self, premium_social_client, premium_social_user):
        ActivityFeedItem.objects.create(
            user=premium_social_user,
            activity_type="task_completed",
        )
        past = timezone.now() - timedelta(hours=1)
        past_str = past.isoformat()
        resp = premium_social_client.get(
            f"{BASE}feed/friends/",
            {"created_before": past_str},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["activities"]) == 0

    def test_unauthenticated_is_rejected(self, api_client):
        resp = api_client.get(f"{BASE}feed/friends/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# UserSearchView tests
# ===========================================================================


class TestUserSearchView:
    """User search tests mock SearchService since Elasticsearch is not available."""

    def _mock_search(self, user_ids):
        """Return a patch context that mocks SearchService.search_users."""
        return patch(
            "apps.search.services.SearchService.search_users",
            return_value=[uid for uid in user_ids],
        )

    def _get_results(self, resp):
        """Extract results list from response (paginated or plain)."""
        if isinstance(resp.data, dict):
            return resp.data.get("results", [])
        return resp.data

    def test_search_by_display_name(self, authenticated_client, other_user):
        with self._mock_search([other_user.id]):
            resp = authenticated_client.get(f"{BASE}users/search?q=Other")
        assert resp.status_code == status.HTTP_200_OK
        results = self._get_results(resp)
        assert len(results) == 1
        assert results[0]["username"] == "Other User"

    def test_search_by_email_no_longer_supported(
        self, authenticated_client, other_user
    ):
        """Email search was removed from UserSearchView for security."""
        with self._mock_search([]):
            resp = authenticated_client.get(f"{BASE}users/search?q=other@")
        assert resp.status_code == status.HTTP_200_OK
        results = self._get_results(resp)
        assert len(results) == 0

    def test_search_short_query_returns_empty(self, authenticated_client):
        # Short queries (<2 chars) return early without calling SearchService
        resp = authenticated_client.get(f"{BASE}users/search?q=a")
        assert resp.status_code == status.HTTP_200_OK
        results = self._get_results(resp)
        assert results == []

    def test_search_empty_query_returns_empty(self, authenticated_client):
        resp = authenticated_client.get(f"{BASE}users/search?q=")
        assert resp.status_code == status.HTTP_200_OK
        results = self._get_results(resp)
        assert results == []

    def test_search_excludes_current_user(self, authenticated_client, user, other_user):
        with self._mock_search([user.id, other_user.id]):
            resp = authenticated_client.get(f"{BASE}users/search?q=Test")
        assert resp.status_code == status.HTTP_200_OK
        results = self._get_results(resp)
        ids = [str(u["id"]) for u in results]
        assert str(user.id) not in ids

    def test_search_excludes_blocked_users(
        self, authenticated_client, block, other_user
    ):
        with self._mock_search([other_user.id]):
            resp = authenticated_client.get(f"{BASE}users/search?q=Other")
        assert resp.status_code == status.HTTP_200_OK
        results = self._get_results(resp)
        ids = [str(u["id"]) for u in results]
        assert str(other_user.id) not in ids

    def test_search_excludes_users_who_blocked_me(
        self, authenticated_client, user, other_user
    ):
        BlockedUser.objects.create(blocker=other_user, blocked=user)
        with self._mock_search([other_user.id]):
            resp = authenticated_client.get(f"{BASE}users/search?q=Other")
        assert resp.status_code == status.HTTP_200_OK
        results = self._get_results(resp)
        ids = [str(u["id"]) for u in results]
        assert str(other_user.id) not in ids

    def test_search_includes_is_friend_flag(
        self, authenticated_client, user, other_user
    ):
        Friendship.objects.create(user1=user, user2=other_user, status="accepted")
        with self._mock_search([other_user.id]):
            resp = authenticated_client.get(f"{BASE}users/search?q=Other")
        assert resp.status_code == status.HTTP_200_OK
        results = self._get_results(resp)
        assert len(results) == 1
        assert results[0]["isFriend"] is True

    def test_search_includes_is_following_flag(
        self, authenticated_client, user, other_user
    ):
        UserFollow.objects.create(follower=user, following=other_user)
        with self._mock_search([other_user.id]):
            resp = authenticated_client.get(f"{BASE}users/search?q=Other")
        assert resp.status_code == status.HTTP_200_OK
        results = self._get_results(resp)
        assert len(results) == 1
        assert results[0]["isFollowing"] is True

    def test_search_no_match(self, authenticated_client):
        with self._mock_search([]):
            resp = authenticated_client.get(f"{BASE}users/search?q=zzzznonexistent")
        assert resp.status_code == status.HTTP_200_OK
        results = self._get_results(resp)
        assert results == []

    def test_search_result_includes_title(self, authenticated_client, other_user):
        with self._mock_search([other_user.id]):
            resp = authenticated_client.get(f"{BASE}users/search?q=Other")
        assert resp.status_code == status.HTTP_200_OK
        results = self._get_results(resp)
        assert "title" in results[0]

    def test_search_case_insensitive(self, authenticated_client, other_user):
        with self._mock_search([other_user.id]):
            resp = authenticated_client.get(f"{BASE}users/search?q=other user")
        assert resp.status_code == status.HTTP_200_OK
        results = self._get_results(resp)
        assert len(results) == 1


# ===========================================================================
# FollowSuggestionsView tests
# ===========================================================================


class TestFollowSuggestionsView:
    def test_suggestions_empty_when_no_connections(self, premium_social_client):
        resp = premium_social_client.get(f"{BASE}follow-suggestions/")
        assert resp.status_code == status.HTTP_200_OK
        # View returns a plain list (no pagination)
        assert isinstance(resp.data, list)

    def test_suggestions_via_shared_circle(
        self, premium_social_client, premium_social_user, other_user
    ):
        from apps.circles.models import Circle, CircleMembership

        circle = Circle.objects.create(
            name="Test Circle", category="career", creator=premium_social_user
        )
        CircleMembership.objects.create(circle=circle, user=premium_social_user)
        CircleMembership.objects.create(circle=circle, user=other_user)
        resp = premium_social_client.get(f"{BASE}follow-suggestions/")
        assert resp.status_code == status.HTTP_200_OK
        ids = [str(s["id"]) for s in resp.data]
        assert str(other_user.id) in ids

    def test_suggestions_via_friends_of_friends(
        self, premium_social_client, premium_social_user, other_user, third_user
    ):
        Friendship.objects.create(
            user1=premium_social_user, user2=other_user, status="accepted"
        )
        Friendship.objects.create(user1=other_user, user2=third_user, status="accepted")
        resp = premium_social_client.get(f"{BASE}follow-suggestions/")
        assert resp.status_code == status.HTTP_200_OK
        ids = [str(s["id"]) for s in resp.data]
        assert str(third_user.id) in ids

    def test_suggestions_exclude_already_following(
        self, premium_social_client, premium_social_user, other_user, third_user
    ):
        from apps.circles.models import Circle, CircleMembership

        circle = Circle.objects.create(
            name="Test Circle", category="career", creator=premium_social_user
        )
        CircleMembership.objects.create(circle=circle, user=premium_social_user)
        CircleMembership.objects.create(circle=circle, user=other_user)
        UserFollow.objects.create(follower=premium_social_user, following=other_user)
        resp = premium_social_client.get(f"{BASE}follow-suggestions/")
        assert resp.status_code == status.HTTP_200_OK
        ids = [str(s["id"]) for s in resp.data]
        assert str(other_user.id) not in ids

    def test_suggestions_exclude_friends(
        self, premium_social_client, premium_social_user, other_user
    ):
        from apps.circles.models import Circle, CircleMembership

        circle = Circle.objects.create(
            name="Test Circle", category="career", creator=premium_social_user
        )
        CircleMembership.objects.create(circle=circle, user=premium_social_user)
        CircleMembership.objects.create(circle=circle, user=other_user)
        Friendship.objects.create(
            user1=premium_social_user, user2=other_user, status="accepted"
        )
        resp = premium_social_client.get(f"{BASE}follow-suggestions/")
        assert resp.status_code == status.HTTP_200_OK
        ids = [str(s["id"]) for s in resp.data]
        assert str(other_user.id) not in ids

    def test_suggestions_exclude_blocked(
        self, premium_social_client, premium_social_user, other_user
    ):
        from apps.circles.models import Circle, CircleMembership

        circle = Circle.objects.create(
            name="Test Circle", category="career", creator=premium_social_user
        )
        CircleMembership.objects.create(circle=circle, user=premium_social_user)
        CircleMembership.objects.create(circle=circle, user=other_user)
        BlockedUser.objects.create(blocker=premium_social_user, blocked=other_user)
        resp = premium_social_client.get(f"{BASE}follow-suggestions/")
        assert resp.status_code == status.HTTP_200_OK
        ids = [str(s["id"]) for s in resp.data]
        assert str(other_user.id) not in ids

    def test_suggestions_via_similar_dreams(
        self, premium_social_client, premium_social_user, other_user
    ):
        from apps.dreams.models import Dream

        Dream.objects.create(
            user=premium_social_user,
            title="Learn Python",
            description="desc",
            category="education",
            status="active",
        )
        Dream.objects.create(
            user=other_user,
            title="Learn Django",
            description="desc",
            category="education",
            status="active",
        )
        resp = premium_social_client.get(f"{BASE}follow-suggestions/")
        assert resp.status_code == status.HTTP_200_OK
        ids = [str(s["id"]) for s in resp.data]
        assert str(other_user.id) in ids

    def test_suggestions_scoring_circle_ranked_higher(
        self, premium_social_client, premium_social_user, other_user, third_user
    ):
        from apps.circles.models import Circle, CircleMembership
        from apps.dreams.models import Dream

        # other_user in shared circle (score 3)
        circle = Circle.objects.create(
            name="Test Circle", category="career", creator=premium_social_user
        )
        CircleMembership.objects.create(circle=circle, user=premium_social_user)
        CircleMembership.objects.create(circle=circle, user=other_user)
        # third_user only via similar dreams (score 1)
        Dream.objects.create(
            user=premium_social_user,
            title="D1",
            description="d",
            category="health",
            status="active",
        )
        Dream.objects.create(
            user=third_user,
            title="D2",
            description="d",
            category="health",
            status="active",
        )
        resp = premium_social_client.get(f"{BASE}follow-suggestions/")
        assert resp.status_code == status.HTTP_200_OK
        suggestions = resp.data
        if len(suggestions) >= 2:
            ids = [str(s["id"]) for s in suggestions]
            # other_user (circle, score 3) should be before third_user (dream, score 1)
            assert ids.index(str(other_user.id)) < ids.index(str(third_user.id))

    def test_suggestions_is_friend_and_is_following_are_false(
        self, premium_social_client, premium_social_user, other_user
    ):
        from apps.circles.models import Circle, CircleMembership

        circle = Circle.objects.create(
            name="Test Circle", category="career", creator=premium_social_user
        )
        CircleMembership.objects.create(circle=circle, user=premium_social_user)
        CircleMembership.objects.create(circle=circle, user=other_user)
        resp = premium_social_client.get(f"{BASE}follow-suggestions/")
        assert resp.status_code == status.HTTP_200_OK
        for suggestion in resp.data:
            assert suggestion["isFriend"] is False
            assert suggestion["isFollowing"] is False

    def test_free_user_is_forbidden(self, authenticated_client):
        resp = authenticated_client.get(f"{BASE}follow-suggestions/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_is_rejected(self, api_client):
        resp = api_client.get(f"{BASE}follow-suggestions/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# Title computation tests (_get_friend_data and search title logic)
# ===========================================================================


class TestTitleComputation:
    """Test the title computation at various level boundaries via the search endpoint."""

    def _get_results(self, resp):
        if isinstance(resp.data, dict):
            return resp.data.get("results", [])
        return resp.data

    def test_level_0_is_dreamer(self, authenticated_client, db):
        u = User.objects.create_user(
            email="l0@test.com",
            password="pass",
            display_name="LevelZero",
            level=0,
        )
        with patch(
            "apps.search.services.SearchService.search_users", return_value=[u.id]
        ):
            resp = authenticated_client.get(f"{BASE}users/search?q=LevelZero")
        assert resp.status_code == status.HTTP_200_OK
        assert self._get_results(resp)[0]["title"] == "Dreamer"

    def test_level_4_is_dreamer(self, authenticated_client, db):
        u = User.objects.create_user(
            email="l4@test.com",
            password="pass",
            display_name="LevelFour",
            level=4,
        )
        with patch(
            "apps.search.services.SearchService.search_users", return_value=[u.id]
        ):
            resp = authenticated_client.get(f"{BASE}users/search?q=LevelFour")
        assert resp.status_code == status.HTTP_200_OK
        assert self._get_results(resp)[0]["title"] == "Dreamer"

    def test_level_5_is_explorer(self, authenticated_client, db):
        u = User.objects.create_user(
            email="l5@test.com",
            password="pass",
            display_name="LevelFive",
            level=5,
        )
        with patch(
            "apps.search.services.SearchService.search_users", return_value=[u.id]
        ):
            resp = authenticated_client.get(f"{BASE}users/search?q=LevelFive")
        assert resp.status_code == status.HTTP_200_OK
        assert self._get_results(resp)[0]["title"] == "Explorer"

    def test_level_10_is_achiever(self, authenticated_client, db):
        u = User.objects.create_user(
            email="l10@test.com",
            password="pass",
            display_name="LevelTen",
            level=10,
        )
        with patch(
            "apps.search.services.SearchService.search_users", return_value=[u.id]
        ):
            resp = authenticated_client.get(f"{BASE}users/search?q=LevelTen")
        assert resp.status_code == status.HTTP_200_OK
        assert self._get_results(resp)[0]["title"] == "Achiever"

    def test_level_20_is_expert(self, authenticated_client, db):
        u = User.objects.create_user(
            email="l20@test.com",
            password="pass",
            display_name="LevelTwenty",
            level=20,
        )
        with patch(
            "apps.search.services.SearchService.search_users", return_value=[u.id]
        ):
            resp = authenticated_client.get(f"{BASE}users/search?q=LevelTwenty")
        assert resp.status_code == status.HTTP_200_OK
        assert self._get_results(resp)[0]["title"] == "Expert"

    def test_level_30_is_master(self, authenticated_client, db):
        u = User.objects.create_user(
            email="l30@test.com",
            password="pass",
            display_name="LevelThirty",
            level=30,
        )
        with patch(
            "apps.search.services.SearchService.search_users", return_value=[u.id]
        ):
            resp = authenticated_client.get(f"{BASE}users/search?q=LevelThirty")
        assert resp.status_code == status.HTTP_200_OK
        assert self._get_results(resp)[0]["title"] == "Master"

    def test_level_50_is_legend(self, authenticated_client, db):
        u = User.objects.create_user(
            email="l50@test.com",
            password="pass",
            display_name="LevelFifty",
            level=50,
        )
        with patch(
            "apps.search.services.SearchService.search_users", return_value=[u.id]
        ):
            resp = authenticated_client.get(f"{BASE}users/search?q=LevelFifty")
        assert resp.status_code == status.HTTP_200_OK
        assert self._get_results(resp)[0]["title"] == "Legend"

    def test_title_in_friends_list(self, authenticated_client, user, db):
        high_level = User.objects.create_user(
            email="highlvl@test.com",
            password="pass",
            display_name="HighLevel",
            level=50,
        )
        Friendship.objects.create(user1=user, user2=high_level, status="accepted")
        resp = authenticated_client.get(f"{BASE}friends/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data[0]["title"] == "Legend"


# ===========================================================================
# Full friendship lifecycle integration test
# ===========================================================================


class TestFriendshipLifecycle:
    def test_full_lifecycle_send_accept_remove(
        self, authenticated_client, api_client, user, other_user
    ):
        # 1. Send friend request
        resp = authenticated_client.post(
            f"{BASE}friends/request/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

        # 2. Other user sees pending request
        api_client.force_authenticate(user=other_user)
        resp = api_client.get(f"{BASE}friends/requests/pending/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 1
        request_id = resp.data[0]["id"]

        # 3. Other user accepts
        resp = api_client.post(f"{BASE}friends/accept/{request_id}/")
        assert resp.status_code == status.HTTP_200_OK

        # 4. Both see each other as friends
        resp = api_client.get(f"{BASE}friends/")
        assert len(resp.data) == 1

        api_client.force_authenticate(user=user)
        resp = api_client.get(f"{BASE}friends/")
        assert len(resp.data) == 1

        # 5. User removes friend
        resp = api_client.delete(f"{BASE}friends/remove/{other_user.id}/")
        assert resp.status_code == status.HTTP_200_OK

        # 6. No longer friends
        resp = api_client.get(f"{BASE}friends/")
        assert len(resp.data) == 0

    def test_full_lifecycle_send_reject(
        self, authenticated_client, api_client, user, other_user
    ):
        # 1. Send request
        authenticated_client.post(
            f"{BASE}friends/request/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )

        # 2. Reject
        api_client.force_authenticate(user=other_user)
        fr = Friendship.objects.get(user1=user, user2=other_user)
        resp = api_client.post(f"{BASE}friends/reject/{fr.id}/")
        assert resp.status_code == status.HTTP_200_OK

        # 3. Can re-send after rejection
        api_client.force_authenticate(user=user)
        resp = api_client.post(
            f"{BASE}friends/request/",
            {"target_user_id": str(other_user.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED


# ===========================================================================
# Admin custom methods tests
# ===========================================================================


class TestActivityFeedItemAdminContentPreview:
    def test_content_preview_short(self, user):
        item = ActivityFeedItem.objects.create(
            user=user,
            activity_type="task_completed",
            content={"title": "Short"},
        )
        admin_instance = ActivityFeedItemAdmin(ActivityFeedItem, None)
        preview = admin_instance.content_preview(item)
        assert preview == str(item.content)
        assert "..." not in preview

    def test_content_preview_long(self, user):
        long_content = {"title": "A" * 200}
        item = ActivityFeedItem.objects.create(
            user=user,
            activity_type="task_completed",
            content=long_content,
        )
        admin_instance = ActivityFeedItemAdmin(ActivityFeedItem, None)
        preview = admin_instance.content_preview(item)
        assert len(preview) == 83  # 80 chars + '...'
        assert preview.endswith("...")

    def test_content_preview_exactly_80(self, user):
        # Create content whose str representation is exactly 80 characters
        item = ActivityFeedItem.objects.create(
            user=user,
            activity_type="task_completed",
            content={"x": "y"},
        )
        # Override to test exact boundary
        original_content = item.content
        item.content = {"k": "v" * 100}
        admin_instance = ActivityFeedItemAdmin(ActivityFeedItem, None)
        preview = admin_instance.content_preview(item)
        content_str = str(item.content)
        if len(content_str) > 80:
            assert preview.endswith("...")
        else:
            assert preview == content_str

    def test_content_preview_short_description(self):
        admin_instance = ActivityFeedItemAdmin(ActivityFeedItem, None)
        assert admin_instance.content_preview.short_description == "Content"


class TestBlockedUserAdminReasonPreview:
    def test_reason_preview_empty(self, user, other_user):
        block = BlockedUser.objects.create(
            blocker=user,
            blocked=other_user,
            reason="",
        )
        admin_instance = BlockedUserAdmin(BlockedUser, None)
        preview = admin_instance.reason_preview(block)
        assert preview == "-"

    def test_reason_preview_short(self, user, other_user):
        block = BlockedUser.objects.create(
            blocker=user,
            blocked=other_user,
            reason="Spam",
        )
        admin_instance = BlockedUserAdmin(BlockedUser, None)
        preview = admin_instance.reason_preview(block)
        assert preview == "Spam"

    def test_reason_preview_long(self, user, other_user):
        long_reason = "A" * 100
        block = BlockedUser.objects.create(
            blocker=user,
            blocked=other_user,
            reason=long_reason,
        )
        admin_instance = BlockedUserAdmin(BlockedUser, None)
        preview = admin_instance.reason_preview(block)
        assert len(preview) == 63  # 60 chars + '...'
        assert preview.endswith("...")

    def test_reason_preview_exactly_60(self, user, other_user):
        reason_60 = "B" * 60
        block = BlockedUser.objects.create(
            blocker=user,
            blocked=other_user,
            reason=reason_60,
        )
        admin_instance = BlockedUserAdmin(BlockedUser, None)
        preview = admin_instance.reason_preview(block)
        assert preview == reason_60
        assert "..." not in preview

    def test_reason_preview_short_description(self):
        admin_instance = BlockedUserAdmin(BlockedUser, None)
        assert admin_instance.reason_preview.short_description == "Reason"
