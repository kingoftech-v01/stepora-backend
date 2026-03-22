"""
Comprehensive tests for the friends app — models, services, views, and edge cases.

Covers:
- Friendship: send request, accept, reject, cancel, remove
- UserFollow: follow, unfollow, followers list, following list
- BlockedUser: block, unblock, blocked list, interaction prevention
- ReportedUser: report, categories
- FriendshipService: is_friend, is_blocked, mutual_friends, suggestions
- Friend counts, friend suggestions algorithm
- IDOR: can't manipulate other users' friendships
- Edge cases: self-friend, already friends, already blocked, double request
"""

import uuid
from unittest.mock import patch

import pytest
from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APIClient

from apps.friends.models import BlockedUser, Friendship, ReportedUser, UserFollow
from apps.friends.services import FriendshipService
from apps.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mock_stripe_signal():
    """Prevent Stripe API calls during user creation in tests."""
    with patch("apps.subscriptions.services.StripeService.create_customer"):
        yield


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def user_a(db):
    return User.objects.create_user(
        email="complete_a@test.com",
        password="testpass123",
        display_name="Alice",
    )


@pytest.fixture
def user_b(db):
    return User.objects.create_user(
        email="complete_b@test.com",
        password="testpass123",
        display_name="Bob",
    )


@pytest.fixture
def user_c(db):
    return User.objects.create_user(
        email="complete_c@test.com",
        password="testpass123",
        display_name="Charlie",
    )


@pytest.fixture
def user_d(db):
    return User.objects.create_user(
        email="complete_d@test.com",
        password="testpass123",
        display_name="Diana",
    )


@pytest.fixture
def client_a(user_a):
    client = APIClient()
    client.force_authenticate(user=user_a)
    return client


@pytest.fixture
def client_b(user_b):
    client = APIClient()
    client.force_authenticate(user=user_b)
    return client


@pytest.fixture
def client_c(user_c):
    client = APIClient()
    client.force_authenticate(user=user_c)
    return client


@pytest.fixture
def unauth_client():
    return APIClient()


# ═════════════════════════════════════════════════════════════════════
# 1. Friendship Model Tests
# ═════════════════════════════════════════════════════════════════════


class TestFriendshipModel:
    """Tests for the Friendship model."""

    def test_create_pending(self, user_a, user_b):
        f = Friendship.objects.create(
            user1=user_a, user2=user_b, status="pending"
        )
        assert f.status == "pending"
        assert f.user1 == user_a
        assert f.user2 == user_b
        assert f.id is not None

    def test_accept_friendship(self, user_a, user_b):
        f = Friendship.objects.create(
            user1=user_a, user2=user_b, status="pending"
        )
        f.status = "accepted"
        f.save(update_fields=["status", "updated_at"])
        f.refresh_from_db()
        assert f.status == "accepted"

    def test_reject_friendship(self, user_a, user_b):
        f = Friendship.objects.create(
            user1=user_a, user2=user_b, status="pending"
        )
        f.status = "rejected"
        f.save(update_fields=["status", "updated_at"])
        f.refresh_from_db()
        assert f.status == "rejected"

    def test_unique_constraint_same_direction(self, user_a, user_b):
        Friendship.objects.create(user1=user_a, user2=user_b)
        with pytest.raises(IntegrityError):
            Friendship.objects.create(user1=user_a, user2=user_b)

    def test_str_representation(self, user_a, user_b):
        f = Friendship.objects.create(
            user1=user_a, user2=user_b, status="pending"
        )
        s = str(f)
        assert "Alice" in s
        assert "Bob" in s
        assert "pending" in s

    def test_ordering_by_created_at_desc(self, user_a, user_b, user_c):
        f1 = Friendship.objects.create(user1=user_a, user2=user_b)
        f2 = Friendship.objects.create(user1=user_a, user2=user_c)
        friends = list(Friendship.objects.all())
        assert friends[0] == f2  # most recent first
        assert friends[1] == f1

    def test_uuid_primary_key(self, user_a, user_b):
        f = Friendship.objects.create(user1=user_a, user2=user_b)
        assert isinstance(f.id, uuid.UUID)

    def test_auto_timestamps(self, user_a, user_b):
        f = Friendship.objects.create(user1=user_a, user2=user_b)
        assert f.created_at is not None
        assert f.updated_at is not None

    def test_default_status_is_pending(self, user_a, user_b):
        f = Friendship.objects.create(user1=user_a, user2=user_b)
        assert f.status == "pending"

    def test_cascade_on_delete_is_configured(self, user_a, user_b):
        """Friendship model uses CASCADE on both ForeignKey fields."""
        user1_field = Friendship._meta.get_field("user1")
        user2_field = Friendship._meta.get_field("user2")
        from django.db import models as m

        assert user1_field.remote_field.on_delete is m.CASCADE
        assert user2_field.remote_field.on_delete is m.CASCADE


# ═════════════════════════════════════════════════════════════════════
# 2. UserFollow Model Tests
# ═════════════════════════════════════════════════════════════════════


class TestUserFollowModel:
    """Tests for the UserFollow model."""

    def test_create_follow(self, user_a, user_b):
        follow = UserFollow.objects.create(follower=user_a, following=user_b)
        assert follow.follower == user_a
        assert follow.following == user_b

    def test_unique_constraint(self, user_a, user_b):
        UserFollow.objects.create(follower=user_a, following=user_b)
        with pytest.raises(IntegrityError):
            UserFollow.objects.create(follower=user_a, following=user_b)

    def test_unidirectional(self, user_a, user_b):
        """A following B does not mean B follows A."""
        UserFollow.objects.create(follower=user_a, following=user_b)
        assert UserFollow.objects.filter(follower=user_b, following=user_a).count() == 0

    def test_mutual_follow(self, user_a, user_b):
        """Both can follow each other independently."""
        UserFollow.objects.create(follower=user_a, following=user_b)
        UserFollow.objects.create(follower=user_b, following=user_a)
        assert UserFollow.objects.count() == 2

    def test_str_representation(self, user_a, user_b):
        follow = UserFollow.objects.create(follower=user_a, following=user_b)
        s = str(follow)
        assert "Alice" in s
        assert "Bob" in s
        assert "follows" in s

    def test_cascade_on_delete_is_configured(self, user_a, user_b):
        """UserFollow model uses CASCADE on both ForeignKey fields."""
        follower_field = UserFollow._meta.get_field("follower")
        following_field = UserFollow._meta.get_field("following")
        from django.db import models as m

        assert follower_field.remote_field.on_delete is m.CASCADE
        assert following_field.remote_field.on_delete is m.CASCADE

    def test_uuid_primary_key(self, user_a, user_b):
        follow = UserFollow.objects.create(follower=user_a, following=user_b)
        assert isinstance(follow.id, uuid.UUID)


# ═════════════════════════════════════════════════════════════════════
# 3. BlockedUser Model Tests
# ═════════════════════════════════════════════════════════════════════


class TestBlockedUserModel:
    """Tests for the BlockedUser model."""

    def test_create_block(self, user_a, user_b):
        block = BlockedUser.objects.create(blocker=user_a, blocked=user_b)
        assert block.blocker == user_a
        assert block.blocked == user_b

    def test_block_with_reason(self, user_a, user_b):
        block = BlockedUser.objects.create(
            blocker=user_a, blocked=user_b, reason="Spam behavior"
        )
        assert block.reason == "Spam behavior"

    def test_is_blocked_forward(self, user_a, user_b):
        BlockedUser.objects.create(blocker=user_a, blocked=user_b)
        assert BlockedUser.is_blocked(user_a, user_b) is True

    def test_is_blocked_reverse(self, user_a, user_b):
        """is_blocked checks both directions."""
        BlockedUser.objects.create(blocker=user_a, blocked=user_b)
        assert BlockedUser.is_blocked(user_b, user_a) is True

    def test_not_blocked(self, user_a, user_b):
        assert BlockedUser.is_blocked(user_a, user_b) is False

    def test_unique_constraint(self, user_a, user_b):
        BlockedUser.objects.create(blocker=user_a, blocked=user_b)
        with pytest.raises(IntegrityError):
            BlockedUser.objects.create(blocker=user_a, blocked=user_b)

    def test_str_representation(self, user_a, user_b):
        block = BlockedUser.objects.create(blocker=user_a, blocked=user_b)
        s = str(block)
        assert "Alice" in s
        assert "Bob" in s
        assert "blocked" in s

    def test_default_empty_reason(self, user_a, user_b):
        block = BlockedUser.objects.create(blocker=user_a, blocked=user_b)
        assert block.reason == ""

    def test_cascade_on_delete_is_configured(self, user_a, user_b):
        """BlockedUser model uses CASCADE on both ForeignKey fields."""
        blocker_field = BlockedUser._meta.get_field("blocker")
        blocked_field = BlockedUser._meta.get_field("blocked")
        from django.db import models as m

        assert blocker_field.remote_field.on_delete is m.CASCADE
        assert blocked_field.remote_field.on_delete is m.CASCADE


# ═════════════════════════════════════════════════════════════════════
# 4. ReportedUser Model Tests
# ═════════════════════════════════════════════════════════════════════


class TestReportedUserModel:
    """Tests for the ReportedUser model."""

    def test_create_report(self, user_a, user_b):
        report = ReportedUser.objects.create(
            reporter=user_a, reported=user_b, reason="Test report"
        )
        assert report.status == "pending"
        assert report.category == "other"

    def test_report_with_category(self, user_a, user_b):
        report = ReportedUser.objects.create(
            reporter=user_a,
            reported=user_b,
            reason="Sending spam",
            category="spam",
        )
        assert report.category == "spam"

    def test_all_categories(self, user_a, user_b):
        for cat, _label in ReportedUser.CATEGORY_CHOICES:
            r = ReportedUser.objects.create(
                reporter=user_a,
                reported=user_b,
                reason=f"Test {cat}",
                category=cat,
            )
            assert r.category == cat

    def test_all_statuses(self, user_a, user_b):
        report = ReportedUser.objects.create(
            reporter=user_a, reported=user_b, reason="Test"
        )
        for stat, _label in ReportedUser.STATUS_CHOICES:
            report.status = stat
            report.save(update_fields=["status"])
            report.refresh_from_db()
            assert report.status == stat

    def test_str_representation(self, user_a, user_b):
        report = ReportedUser.objects.create(
            reporter=user_a, reported=user_b, reason="Test", category="harassment"
        )
        s = str(report)
        assert "Alice" in s
        assert "Bob" in s
        assert "harassment" in s

    def test_admin_notes_default_empty(self, user_a, user_b):
        report = ReportedUser.objects.create(
            reporter=user_a, reported=user_b, reason="Test"
        )
        assert report.admin_notes == ""

    def test_multiple_reports_same_user(self, user_a, user_b, user_c):
        """Multiple users can report the same user."""
        ReportedUser.objects.create(
            reporter=user_a, reported=user_c, reason="Report 1"
        )
        ReportedUser.objects.create(
            reporter=user_b, reported=user_c, reason="Report 2"
        )
        assert ReportedUser.objects.filter(reported=user_c).count() == 2


# ═════════════════════════════════════════════════════════════════════
# 5. FriendshipService Tests
# ═════════════════════════════════════════════════════════════════════


class TestFriendshipService:
    """Tests for FriendshipService business logic."""

    def test_is_friend_accepted(self, user_a, user_b):
        Friendship.objects.create(
            user1=user_a, user2=user_b, status="accepted"
        )
        assert FriendshipService.is_friend(user_a.id, user_b.id) is True
        assert FriendshipService.is_friend(user_b.id, user_a.id) is True

    def test_is_friend_pending_not_friend(self, user_a, user_b):
        Friendship.objects.create(
            user1=user_a, user2=user_b, status="pending"
        )
        assert FriendshipService.is_friend(user_a.id, user_b.id) is False

    def test_is_friend_rejected_not_friend(self, user_a, user_b):
        Friendship.objects.create(
            user1=user_a, user2=user_b, status="rejected"
        )
        assert FriendshipService.is_friend(user_a.id, user_b.id) is False

    def test_is_friend_no_relationship(self, user_a, user_b):
        assert FriendshipService.is_friend(user_a.id, user_b.id) is False

    def test_is_blocked(self, user_a, user_b):
        BlockedUser.objects.create(blocker=user_a, blocked=user_b)
        assert FriendshipService.is_blocked(user_a.id, user_b.id) is True
        assert FriendshipService.is_blocked(user_b.id, user_a.id) is True

    def test_is_blocked_not_blocked(self, user_a, user_b):
        assert FriendshipService.is_blocked(user_a.id, user_b.id) is False

    def test_mutual_friends(self, user_a, user_b, user_c):
        Friendship.objects.create(user1=user_a, user2=user_c, status="accepted")
        Friendship.objects.create(user1=user_b, user2=user_c, status="accepted")
        mutual = FriendshipService.mutual_friends(user_a.id, user_b.id)
        assert len(mutual) == 1
        assert mutual[0]["id"] == str(user_c.id)

    def test_mutual_friends_none(self, user_a, user_b, user_c, user_d):
        Friendship.objects.create(user1=user_a, user2=user_c, status="accepted")
        Friendship.objects.create(user1=user_b, user2=user_d, status="accepted")
        mutual = FriendshipService.mutual_friends(user_a.id, user_b.id)
        assert len(mutual) == 0

    def test_mutual_friends_multiple(self, user_a, user_b, user_c, user_d):
        Friendship.objects.create(user1=user_a, user2=user_c, status="accepted")
        Friendship.objects.create(user1=user_b, user2=user_c, status="accepted")
        Friendship.objects.create(user1=user_a, user2=user_d, status="accepted")
        Friendship.objects.create(user1=user_b, user2=user_d, status="accepted")
        mutual = FriendshipService.mutual_friends(user_a.id, user_b.id)
        ids = {m["id"] for m in mutual}
        assert str(user_c.id) in ids
        assert str(user_d.id) in ids
        assert len(mutual) == 2

    def test_mutual_friends_excludes_pending(self, user_a, user_b, user_c):
        """Pending friendships are not counted as mutual friends."""
        Friendship.objects.create(user1=user_a, user2=user_c, status="pending")
        Friendship.objects.create(user1=user_b, user2=user_c, status="accepted")
        mutual = FriendshipService.mutual_friends(user_a.id, user_b.id)
        assert len(mutual) == 0

    def test_suggestions_excludes_existing(self, user_a, user_b, user_c):
        Friendship.objects.create(user1=user_a, user2=user_b, status="accepted")
        suggestions = FriendshipService.suggestions(user_a, limit=10)
        ids = [s["id"] for s in suggestions]
        assert str(user_a.id) not in ids  # excludes self
        assert str(user_b.id) not in ids  # excludes friend
        assert str(user_c.id) in ids  # includes stranger

    def test_suggestions_excludes_blocked(self, user_a, user_b, user_c):
        BlockedUser.objects.create(blocker=user_a, blocked=user_b)
        suggestions = FriendshipService.suggestions(user_a, limit=10)
        ids = [s["id"] for s in suggestions]
        assert str(user_b.id) not in ids

    def test_suggestions_excludes_pending(self, user_a, user_b, user_c):
        Friendship.objects.create(user1=user_a, user2=user_b, status="pending")
        suggestions = FriendshipService.suggestions(user_a, limit=10)
        ids = [s["id"] for s in suggestions]
        assert str(user_b.id) not in ids

    def test_suggestions_limit(self, user_a, user_b, user_c, user_d):
        suggestions = FriendshipService.suggestions(user_a, limit=1)
        assert len(suggestions) <= 1

    def test_suggestions_returns_expected_fields(self, user_a, user_b):
        suggestions = FriendshipService.suggestions(user_a, limit=5)
        if suggestions:
            s = suggestions[0]
            assert "id" in s
            assert "display_name" in s
            assert "avatar_url" in s
            assert "level" in s


# ═════════════════════════════════════════════════════════════════════
# 6. Friends ViewSet — API Tests (apps/friends/views.py)
# ═════════════════════════════════════════════════════════════════════


class TestFriendshipViewSetAPI:
    """API tests for apps/friends/views.py endpoints at /api/v1/friends/."""

    # ── Authentication ──

    def test_unauthenticated_list_friends(self, unauth_client):
        resp = unauth_client.get("/api/v1/friends/friends/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # ── List Friends ──

    def test_list_friends_empty(self, client_a):
        resp = client_a.get("/api/v1/friends/friends/")
        assert resp.status_code == 200
        assert resp.data["friends"] == []
        assert resp.data["count"] == 0

    def test_list_friends_with_accepted(self, client_a, user_a, user_b):
        Friendship.objects.create(user1=user_a, user2=user_b, status="accepted")
        resp = client_a.get("/api/v1/friends/friends/")
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["friends"][0]["id"] == str(user_b.id)
        assert resp.data["friends"][0]["display_name"] == "Bob"

    def test_list_friends_excludes_pending(self, client_a, user_a, user_b):
        Friendship.objects.create(user1=user_a, user2=user_b, status="pending")
        resp = client_a.get("/api/v1/friends/friends/")
        assert resp.data["count"] == 0

    # ── Send Request ──

    def test_send_request_success(self, client_a, user_b):
        resp = client_a.post(
            "/api/v1/friends/request/",
            {"user_id": str(user_b.id)},
            format="json",
        )
        assert resp.status_code == 201
        assert Friendship.objects.filter(
            user1__email="complete_a@test.com", user2=user_b, status="pending"
        ).exists()

    def test_send_request_to_self(self, client_a, user_a):
        resp = client_a.post(
            "/api/v1/friends/request/",
            {"user_id": str(user_a.id)},
            format="json",
        )
        assert resp.status_code == 400
        assert "yourself" in resp.data["error"].lower()

    def test_send_request_to_nonexistent_user(self, client_a):
        resp = client_a.post(
            "/api/v1/friends/request/",
            {"user_id": str(uuid.uuid4())},
            format="json",
        )
        assert resp.status_code == 404

    def test_send_request_already_friends(self, client_a, user_a, user_b):
        Friendship.objects.create(user1=user_a, user2=user_b, status="accepted")
        resp = client_a.post(
            "/api/v1/friends/request/",
            {"user_id": str(user_b.id)},
            format="json",
        )
        assert resp.status_code == 400
        assert "already" in resp.data["error"].lower()

    def test_send_request_already_pending(self, client_a, user_a, user_b):
        Friendship.objects.create(user1=user_a, user2=user_b, status="pending")
        resp = client_a.post(
            "/api/v1/friends/request/",
            {"user_id": str(user_b.id)},
            format="json",
        )
        assert resp.status_code == 400
        assert "pending" in resp.data["error"].lower()

    def test_send_request_to_blocked_user(self, client_a, user_a, user_b):
        BlockedUser.objects.create(blocker=user_a, blocked=user_b)
        resp = client_a.post(
            "/api/v1/friends/request/",
            {"user_id": str(user_b.id)},
            format="json",
        )
        assert resp.status_code == 400

    def test_send_request_blocked_by_target(self, client_a, user_a, user_b):
        BlockedUser.objects.create(blocker=user_b, blocked=user_a)
        resp = client_a.post(
            "/api/v1/friends/request/",
            {"user_id": str(user_b.id)},
            format="json",
        )
        assert resp.status_code == 400

    # ── Accept Request ──

    def test_accept_request_success(self, client_a, user_a, user_b):
        f = Friendship.objects.create(user1=user_b, user2=user_a, status="pending")
        resp = client_a.post(f"/api/v1/friends/{f.id}/accept/")
        assert resp.status_code == 200
        f.refresh_from_db()
        assert f.status == "accepted"

    def test_accept_request_not_recipient(self, client_a, user_a, user_b):
        """Only user2 (recipient) can accept."""
        f = Friendship.objects.create(user1=user_a, user2=user_b, status="pending")
        resp = client_a.post(f"/api/v1/friends/{f.id}/accept/")
        assert resp.status_code == 404

    def test_accept_nonexistent_request(self, client_a):
        resp = client_a.post(f"/api/v1/friends/{uuid.uuid4()}/accept/")
        assert resp.status_code == 404

    def test_accept_already_accepted(self, client_a, user_a, user_b):
        f = Friendship.objects.create(user1=user_b, user2=user_a, status="accepted")
        resp = client_a.post(f"/api/v1/friends/{f.id}/accept/")
        assert resp.status_code == 404  # only pending can be accepted

    # ── Reject Request ──

    def test_reject_request_success(self, client_a, user_a, user_b):
        f = Friendship.objects.create(user1=user_b, user2=user_a, status="pending")
        resp = client_a.post(f"/api/v1/friends/{f.id}/reject/")
        assert resp.status_code == 200
        f.refresh_from_db()
        assert f.status == "rejected"

    def test_reject_request_not_recipient(self, client_a, user_a, user_b):
        f = Friendship.objects.create(user1=user_a, user2=user_b, status="pending")
        resp = client_a.post(f"/api/v1/friends/{f.id}/reject/")
        assert resp.status_code == 404

    # ── Remove Friend ──

    def test_remove_friend_success(self, client_a, user_a, user_b):
        Friendship.objects.create(user1=user_a, user2=user_b, status="accepted")
        resp = client_a.delete(f"/api/v1/friends/remove/{user_b.id}/")
        assert resp.status_code == 200
        assert Friendship.objects.count() == 0

    def test_remove_friend_reverse_direction(self, client_a, user_a, user_b):
        """Can remove friendship created in reverse direction."""
        Friendship.objects.create(user1=user_b, user2=user_a, status="accepted")
        resp = client_a.delete(f"/api/v1/friends/remove/{user_b.id}/")
        assert resp.status_code == 200
        assert Friendship.objects.count() == 0

    def test_remove_nonexistent_friend(self, client_a, user_b):
        resp = client_a.delete(f"/api/v1/friends/remove/{user_b.id}/")
        assert resp.status_code == 200  # idempotent delete

    # ── Pending Requests ──

    def test_pending_requests(self, client_a, user_a, user_b, user_c):
        Friendship.objects.create(user1=user_b, user2=user_a, status="pending")
        Friendship.objects.create(user1=user_c, user2=user_a, status="pending")
        resp = client_a.get("/api/v1/friends/requests/pending/")
        assert resp.status_code == 200
        assert resp.data["count"] == 2

    def test_pending_requests_excludes_sent(self, client_a, user_a, user_b):
        """Pending requests I sent don't show in my pending received list."""
        Friendship.objects.create(user1=user_a, user2=user_b, status="pending")
        resp = client_a.get("/api/v1/friends/requests/pending/")
        assert resp.data["count"] == 0

    # ── Mutual Friends ──

    def test_mutual_friends_endpoint(self, client_a, user_a, user_b, user_c):
        Friendship.objects.create(user1=user_a, user2=user_c, status="accepted")
        Friendship.objects.create(user1=user_b, user2=user_c, status="accepted")
        resp = client_a.get(f"/api/v1/friends/mutual/{user_b.id}/")
        assert resp.status_code == 200
        assert resp.data["count"] == 1

    # ── Social Counts ──

    def test_counts_endpoint(self, client_a, user_a, user_b, user_c):
        Friendship.objects.create(user1=user_a, user2=user_b, status="accepted")
        UserFollow.objects.create(follower=user_c, following=user_a)
        UserFollow.objects.create(follower=user_a, following=user_c)
        resp = client_a.get(f"/api/v1/friends/counts/{user_a.id}/")
        assert resp.status_code == 200
        assert resp.data["friends"] == 1
        assert resp.data["followers"] == 1
        assert resp.data["following"] == 1

    # ── Follow ──

    def test_follow_success(self, client_a, user_b):
        resp = client_a.post(
            "/api/v1/friends/follow/",
            {"user_id": str(user_b.id)},
            format="json",
        )
        assert resp.status_code == 201
        assert UserFollow.objects.filter(
            follower__email="complete_a@test.com", following=user_b
        ).exists()

    def test_follow_self_rejected(self, client_a, user_a):
        resp = client_a.post(
            "/api/v1/friends/follow/",
            {"user_id": str(user_a.id)},
            format="json",
        )
        assert resp.status_code == 400

    def test_follow_idempotent(self, client_a, user_a, user_b):
        """Following again is idempotent (get_or_create)."""
        UserFollow.objects.create(follower=user_a, following=user_b)
        resp = client_a.post(
            "/api/v1/friends/follow/",
            {"user_id": str(user_b.id)},
            format="json",
        )
        assert resp.status_code == 201
        assert UserFollow.objects.filter(follower=user_a, following=user_b).count() == 1

    # ── Unfollow ──

    def test_unfollow_success(self, client_a, user_a, user_b):
        UserFollow.objects.create(follower=user_a, following=user_b)
        resp = client_a.delete(f"/api/v1/friends/unfollow/{user_b.id}/")
        assert resp.status_code == 200
        assert not UserFollow.objects.filter(follower=user_a, following=user_b).exists()

    def test_unfollow_nonexistent(self, client_a, user_b):
        resp = client_a.delete(f"/api/v1/friends/unfollow/{user_b.id}/")
        assert resp.status_code == 200  # idempotent

    # ── Block ──

    def test_block_success(self, client_a, user_b):
        resp = client_a.post(
            "/api/v1/friends/block/",
            {"user_id": str(user_b.id)},
            format="json",
        )
        assert resp.status_code == 201
        assert BlockedUser.objects.filter(
            blocker__email="complete_a@test.com", blocked=user_b
        ).exists()

    def test_block_removes_friendship(self, client_a, user_a, user_b):
        Friendship.objects.create(user1=user_a, user2=user_b, status="accepted")
        client_a.post(
            "/api/v1/friends/block/",
            {"user_id": str(user_b.id)},
            format="json",
        )
        assert Friendship.objects.count() == 0

    def test_block_removes_follows(self, client_a, user_a, user_b):
        UserFollow.objects.create(follower=user_a, following=user_b)
        UserFollow.objects.create(follower=user_b, following=user_a)
        client_a.post(
            "/api/v1/friends/block/",
            {"user_id": str(user_b.id)},
            format="json",
        )
        assert UserFollow.objects.count() == 0

    def test_block_with_reason(self, client_a, user_b):
        resp = client_a.post(
            "/api/v1/friends/block/",
            {"user_id": str(user_b.id), "reason": "Spam"},
            format="json",
        )
        assert resp.status_code == 201
        block = BlockedUser.objects.first()
        assert block.reason == "Spam"

    def test_block_idempotent(self, client_a, user_a, user_b):
        BlockedUser.objects.create(blocker=user_a, blocked=user_b)
        resp = client_a.post(
            "/api/v1/friends/block/",
            {"user_id": str(user_b.id)},
            format="json",
        )
        assert resp.status_code == 201
        assert BlockedUser.objects.filter(blocker=user_a, blocked=user_b).count() == 1

    # ── Unblock ──

    def test_unblock_success(self, client_a, user_a, user_b):
        BlockedUser.objects.create(blocker=user_a, blocked=user_b)
        resp = client_a.delete(f"/api/v1/friends/unblock/{user_b.id}/")
        assert resp.status_code == 200
        assert not BlockedUser.objects.filter(blocker=user_a, blocked=user_b).exists()

    def test_unblock_nonexistent(self, client_a, user_b):
        resp = client_a.delete(f"/api/v1/friends/unblock/{user_b.id}/")
        assert resp.status_code == 200  # idempotent

    # ── Blocked List ──

    def test_blocked_list(self, client_a, user_a, user_b, user_c):
        BlockedUser.objects.create(blocker=user_a, blocked=user_b)
        BlockedUser.objects.create(blocker=user_a, blocked=user_c)
        resp = client_a.get("/api/v1/friends/blocked/")
        assert resp.status_code == 200
        assert len(resp.data) == 2

    def test_blocked_list_excludes_others(self, client_a, user_a, user_b, user_c):
        """Only blocks by current user are shown."""
        BlockedUser.objects.create(blocker=user_b, blocked=user_c)
        resp = client_a.get("/api/v1/friends/blocked/")
        assert len(resp.data) == 0

    # ── Report ──

    def test_report_success(self, client_a, user_b):
        resp = client_a.post(
            "/api/v1/friends/report/",
            {
                "user_id": str(user_b.id),
                "reason": "Bad behavior",
                "category": "harassment",
            },
            format="json",
        )
        assert resp.status_code == 201
        assert ReportedUser.objects.count() == 1
        report = ReportedUser.objects.first()
        assert report.category == "harassment"
        assert report.reason == "Bad behavior"

    def test_report_default_category(self, client_a, user_b):
        resp = client_a.post(
            "/api/v1/friends/report/",
            {"user_id": str(user_b.id), "reason": "Something bad"},
            format="json",
        )
        assert resp.status_code == 201
        assert ReportedUser.objects.first().category == "other"


# ═════════════════════════════════════════════════════════════════════
# 7. IDOR Tests — Cannot Manipulate Other Users' Friendships
# ═════════════════════════════════════════════════════════════════════


class TestIDOR:
    """IDOR tests: users cannot manipulate others' friendships."""

    def test_cannot_accept_others_request(self, client_c, user_a, user_b):
        """User C cannot accept a request from A to B."""
        f = Friendship.objects.create(user1=user_a, user2=user_b, status="pending")
        resp = client_c.post(f"/api/v1/friends/{f.id}/accept/")
        assert resp.status_code == 404
        f.refresh_from_db()
        assert f.status == "pending"  # unchanged

    def test_cannot_reject_others_request(self, client_c, user_a, user_b):
        """User C cannot reject a request from A to B."""
        f = Friendship.objects.create(user1=user_a, user2=user_b, status="pending")
        resp = client_c.post(f"/api/v1/friends/{f.id}/reject/")
        assert resp.status_code == 404
        f.refresh_from_db()
        assert f.status == "pending"

    def test_sender_cannot_accept_own_request(self, client_a, user_a, user_b):
        """Sender (user1) cannot accept their own request."""
        f = Friendship.objects.create(user1=user_a, user2=user_b, status="pending")
        resp = client_a.post(f"/api/v1/friends/{f.id}/accept/")
        assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════════
# 8. Edge Cases
# ═════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_missing_user_id_on_send_request(self, client_a):
        resp = client_a.post("/api/v1/friends/request/", {}, format="json")
        assert resp.status_code == 400

    def test_invalid_uuid_on_send_request(self, client_a):
        resp = client_a.post(
            "/api/v1/friends/request/",
            {"user_id": "not-a-uuid"},
            format="json",
        )
        assert resp.status_code == 400

    def test_missing_user_id_on_follow(self, client_a):
        resp = client_a.post("/api/v1/friends/follow/", {}, format="json")
        assert resp.status_code == 400

    def test_missing_user_id_on_block(self, client_a):
        resp = client_a.post("/api/v1/friends/block/", {}, format="json")
        assert resp.status_code == 400

    def test_missing_reason_on_report(self, client_a, user_b):
        resp = client_a.post(
            "/api/v1/friends/report/",
            {"user_id": str(user_b.id)},
            format="json",
        )
        assert resp.status_code == 400

    def test_friend_list_both_directions(self, client_a, client_b, user_a, user_b, user_c):
        """Friends list shows friends regardless of who sent the request."""
        Friendship.objects.create(user1=user_a, user2=user_b, status="accepted")
        Friendship.objects.create(user1=user_c, user2=user_a, status="accepted")
        resp = client_a.get("/api/v1/friends/friends/")
        assert resp.data["count"] == 2

    def test_counts_zero_for_new_user(self, client_a, user_a):
        resp = client_a.get(f"/api/v1/friends/counts/{user_a.id}/")
        assert resp.data["friends"] == 0
        assert resp.data["followers"] == 0
        assert resp.data["following"] == 0
