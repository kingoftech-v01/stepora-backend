"""Tests for circles app."""
import pytest
import secrets
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone as django_timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User
from apps.circles.models import (
    Circle,
    CircleMembership,
    CirclePost,
    CircleChallenge,
    PostReaction,
    CircleInvitation,
    ChallengeProgress,
)
from apps.circles.admin import (
    CircleAdmin,
    CirclePostAdmin,
    CircleChallengeAdmin,
)


# ---------------------------------------------------------------------------
# Local fixtures – override the global ``user`` / ``authenticated_client``
# so that the default test user has a *pro* subscription (circle creation
# requires pro; joining/reading requires premium+).
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    """Create a pro user (overrides global free-tier ``user`` fixture).

    Uses the same email as the global fixture to avoid conflicts with tests
    that reference 'testuser@example.com'.
    """
    return User.objects.create_user(
        email="testuser@example.com",
        password="testpassword123",
        display_name="Test User",
        subscription="pro",
        subscription_ends=django_timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def authenticated_client(api_client, user):
    """Return an API client authenticated as the local pro ``user``."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def other_user(db):
    """Create a second pro user for multi-user tests.

    Pro subscription is needed because many tests force-authenticate as
    ``other_user`` and hit CanUseCircles-gated endpoints (including POST
    actions like join, invite-accept, etc.).
    """
    return User.objects.create_user(
        email="otheruser@example.com",
        password="testpassword123",
        display_name="Other User",
        subscription="pro",
        subscription_ends=django_timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def third_user(db):
    """Create a third pro user."""
    return User.objects.create_user(
        email="thirduser@example.com",
        password="testpassword123",
        display_name="Third User",
        subscription="pro",
        subscription_ends=django_timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def circle(db, user):
    """Create a public circle owned by ``user`` with an admin membership."""
    c = Circle.objects.create(
        name="Dream Achievers",
        description="A circle for dreamers",
        category="personal_growth",
        is_public=True,
        creator=user,
        max_members=20,
    )
    CircleMembership.objects.create(circle=c, user=user, role="admin")
    return c


@pytest.fixture
def private_circle(db, user):
    """Create a private circle owned by ``user`` with an admin membership."""
    c = Circle.objects.create(
        name="Secret Circle",
        description="Private circle",
        category="career",
        is_public=False,
        creator=user,
        max_members=10,
    )
    CircleMembership.objects.create(circle=c, user=user, role="admin")
    return c


@pytest.fixture
def membership(db, circle, other_user):
    """Add ``other_user`` as a regular member of ``circle``."""
    return CircleMembership.objects.create(
        circle=circle, user=other_user, role="member"
    )


@pytest.fixture
def moderator_membership(db, circle, other_user):
    """Add ``other_user`` as a moderator of ``circle``."""
    return CircleMembership.objects.create(
        circle=circle, user=other_user, role="moderator"
    )


@pytest.fixture
def post(db, circle, user):
    """Create a post in ``circle`` by ``user``."""
    return CirclePost.objects.create(
        circle=circle,
        author=user,
        content="Making great progress on my goals!",
    )


@pytest.fixture
def challenge(db, circle):
    """Create an active challenge in ``circle``."""
    now = django_timezone.now()
    return CircleChallenge.objects.create(
        circle=circle,
        title="30-Day Fitness",
        description="Stay fit for 30 days",
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=29),
        status="active",
    )


@pytest.fixture
def upcoming_challenge(db, circle):
    """Create an upcoming challenge in ``circle``."""
    now = django_timezone.now()
    return CircleChallenge.objects.create(
        circle=circle,
        title="Future Challenge",
        description="Starting soon",
        start_date=now + timedelta(days=5),
        end_date=now + timedelta(days=35),
        status="upcoming",
    )


@pytest.fixture
def invitation(db, circle, user, other_user):
    """Create a pending direct invitation for ``other_user``."""
    return CircleInvitation.objects.create(
        circle=circle,
        inviter=user,
        invitee=other_user,
        invite_code=secrets.token_urlsafe(12),
        status="pending",
        expires_at=django_timezone.now() + timedelta(days=7),
    )


@pytest.fixture
def link_invitation(db, circle, user):
    """Create a pending link-based invitation (no invitee)."""
    return CircleInvitation.objects.create(
        circle=circle,
        inviter=user,
        invitee=None,
        invite_code=secrets.token_urlsafe(12),
        status="pending",
        expires_at=django_timezone.now() + timedelta(days=14),
    )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestCircleModel:
    """Tests for the Circle model."""

    def test_str_public(self, circle):
        assert str(circle) == "Dream Achievers (Public, personal_growth)"

    def test_str_private(self, private_circle):
        assert str(private_circle) == "Secret Circle (Private, career)"

    def test_member_count(self, circle):
        assert circle.member_count == 1

    def test_member_count_with_extra(self, circle, membership):
        assert circle.member_count == 2

    def test_is_full_false(self, circle):
        assert circle.is_full is False

    def test_is_full_true(self, circle, user):
        circle.max_members = 1
        circle.save()
        assert circle.is_full is True

    def test_default_category(self, user):
        c = Circle.objects.create(name="No Category", creator=user)
        assert c.category == "other"

    def test_default_is_public(self, user):
        c = Circle.objects.create(name="Public by default", creator=user)
        assert c.is_public is True

    def test_default_max_members(self, user):
        c = Circle.objects.create(name="Default max", creator=user)
        assert c.max_members == 20

    def test_uuid_primary_key(self, circle):
        import uuid
        assert isinstance(circle.id, uuid.UUID)

    def test_ordering_is_newest_first(self, user):
        """Meta ordering is -created_at (newest first)."""
        c1 = Circle.objects.create(name="First", creator=user)
        c2 = Circle.objects.create(name="Second", creator=user)
        ids = list(Circle.objects.values_list("id", flat=True))
        # Both should be present; ordering is -created_at
        assert c1.id in ids
        assert c2.id in ids
        assert Circle._meta.ordering == ["-created_at"]

    def test_category_choices(self, user):
        valid_categories = [
            "career", "health", "fitness", "education", "finance",
            "creativity", "relationships", "personal_growth", "hobbies", "other",
        ]
        for cat in valid_categories:
            c = Circle.objects.create(name=f"Circle {cat}", creator=user, category=cat)
            assert c.category == cat


class TestCircleMembershipModel:
    """Tests for the CircleMembership model."""

    def test_str(self, circle, user):
        m = CircleMembership.objects.get(circle=circle, user=user)
        assert "Test User" in str(m)
        assert "Dream Achievers" in str(m)
        assert "admin" in str(m)

    def test_str_fallback_to_email(self, circle):
        no_name_user = User.objects.create_user(
            email="noname@example.com", password="testpassword123", display_name=""
        )
        m = CircleMembership.objects.create(
            circle=circle, user=no_name_user, role="member"
        )
        assert "noname@example.com" in str(m)

    def test_default_role(self, circle, other_user):
        m = CircleMembership.objects.create(circle=circle, user=other_user)
        assert m.role == "member"

    def test_unique_together(self, circle, membership, other_user):
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            CircleMembership.objects.create(circle=circle, user=other_user, role="member")

    def test_role_choices(self, circle, other_user):
        m = CircleMembership.objects.create(circle=circle, user=other_user, role="moderator")
        assert m.role == "moderator"

    def test_cascade_delete_circle(self, circle, membership):
        circle_id = circle.id
        circle.delete()
        assert CircleMembership.objects.filter(circle_id=circle_id).count() == 0

    def test_cascade_delete_user(self, circle, membership, other_user):
        membership_id = membership.id
        other_user.delete()
        assert CircleMembership.objects.filter(id=membership_id).count() == 0


class TestCirclePostModel:
    """Tests for the CirclePost model."""

    def test_str_short_content(self, circle, user):
        p = CirclePost.objects.create(circle=circle, author=user, content="Short")
        assert str(p) == "Test User: Short"

    def test_str_long_content(self, circle, user):
        long = "A" * 60
        p = CirclePost.objects.create(circle=circle, author=user, content=long)
        assert str(p).endswith("...")
        assert len(str(p).split(": ", 1)[1]) == 53  # 50 chars + '...'

    def test_str_fallback_to_email(self, circle):
        no_name_user = User.objects.create_user(
            email="noname2@example.com", password="testpassword123", display_name=""
        )
        p = CirclePost.objects.create(circle=circle, author=no_name_user, content="Hi")
        assert "noname2@example.com" in str(p)

    def test_ordering_is_newest_first(self, circle, user):
        """Meta ordering is -created_at (newest first)."""
        p1 = CirclePost.objects.create(circle=circle, author=user, content="First")
        p2 = CirclePost.objects.create(circle=circle, author=user, content="Second")
        ids = list(CirclePost.objects.values_list("id", flat=True))
        assert p1.id in ids
        assert p2.id in ids
        assert CirclePost._meta.ordering == ["-created_at"]

    def test_cascade_delete_circle(self, post, circle):
        circle.delete()
        assert CirclePost.objects.filter(id=post.id).count() == 0


class TestCircleChallengeModel:
    """Tests for the CircleChallenge model."""

    def test_str(self, challenge):
        assert str(challenge) == "30-Day Fitness (Dream Achievers) - active"

    def test_is_active_true(self, challenge):
        assert challenge.is_active is True

    def test_is_active_false_upcoming(self, upcoming_challenge):
        assert upcoming_challenge.is_active is False

    def test_is_active_false_wrong_status(self, challenge):
        challenge.status = "completed"
        challenge.save()
        assert challenge.is_active is False

    def test_is_active_false_expired(self, circle):
        now = django_timezone.now()
        ch = CircleChallenge.objects.create(
            circle=circle,
            title="Old",
            start_date=now - timedelta(days=60),
            end_date=now - timedelta(days=30),
            status="active",
        )
        assert ch.is_active is False

    def test_participant_count_zero(self, challenge):
        assert challenge.participant_count == 0

    def test_participant_count(self, challenge, user, other_user):
        challenge.participants.add(user, other_user)
        assert challenge.participant_count == 2

    def test_default_status(self, circle):
        now = django_timezone.now()
        ch = CircleChallenge.objects.create(
            circle=circle,
            title="Default",
            start_date=now,
            end_date=now + timedelta(days=7),
        )
        assert ch.status == "upcoming"

    def test_cascade_delete_circle(self, challenge, circle):
        circle.delete()
        assert CircleChallenge.objects.filter(id=challenge.id).count() == 0


class TestPostReactionModel:
    """Tests for the PostReaction model."""

    def test_str(self, post, user):
        r = PostReaction.objects.create(post=post, user=user, reaction_type="fire")
        assert "Test User" in str(r)
        assert "fire" in str(r)

    def test_str_fallback_to_email(self, post):
        no_name_user = User.objects.create_user(
            email="noname3@example.com", password="testpassword123", display_name=""
        )
        r = PostReaction.objects.create(
            post=post, user=no_name_user, reaction_type="heart"
        )
        assert "noname3@example.com" in str(r)

    def test_unique_together(self, post, user):
        PostReaction.objects.create(post=post, user=user, reaction_type="fire")
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            PostReaction.objects.create(post=post, user=user, reaction_type="heart")

    def test_cascade_delete_post(self, post, user):
        PostReaction.objects.create(post=post, user=user, reaction_type="clap")
        post.delete()
        assert PostReaction.objects.filter(user=user).count() == 0

    def test_reaction_types(self, post, user, other_user, third_user):
        u4 = User.objects.create_user(email="u4@example.com", password="test123")
        for rt, u in zip(
            ["thumbs_up", "fire", "clap", "heart"],
            [user, other_user, third_user, u4],
        ):
            PostReaction.objects.create(post=post, user=u, reaction_type=rt)
        assert PostReaction.objects.filter(post=post).count() == 4


class TestCircleInvitationModel:
    """Tests for the CircleInvitation model."""

    def test_str_direct_invite(self, invitation, other_user):
        assert other_user.email in str(invitation)
        assert "Dream Achievers" in str(invitation)

    def test_str_link_invite(self, link_invitation):
        assert "code:" in str(link_invitation)

    def test_is_expired_false(self, invitation):
        assert invitation.is_expired is False

    def test_is_expired_true(self, circle, user):
        inv = CircleInvitation.objects.create(
            circle=circle,
            inviter=user,
            invite_code=secrets.token_urlsafe(12),
            expires_at=django_timezone.now() - timedelta(days=1),
        )
        assert inv.is_expired is True

    def test_status_choices(self, circle, user):
        for st in ["pending", "accepted", "declined", "expired"]:
            inv = CircleInvitation.objects.create(
                circle=circle,
                inviter=user,
                invite_code=secrets.token_urlsafe(12),
                expires_at=django_timezone.now() + timedelta(days=7),
                status=st,
            )
            assert inv.status == st

    def test_unique_invite_code(self, circle, user):
        code = secrets.token_urlsafe(12)
        CircleInvitation.objects.create(
            circle=circle,
            inviter=user,
            invite_code=code,
            expires_at=django_timezone.now() + timedelta(days=7),
        )
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            CircleInvitation.objects.create(
                circle=circle,
                inviter=user,
                invite_code=code,
                expires_at=django_timezone.now() + timedelta(days=7),
            )

    def test_invitee_nullable(self, link_invitation):
        assert link_invitation.invitee is None


class TestChallengeProgressModel:
    """Tests for the ChallengeProgress model."""

    def test_str(self, challenge, user):
        p = ChallengeProgress.objects.create(
            challenge=challenge, user=user, progress_value=42.5
        )
        assert "Test User" in str(p)
        assert "42.5" in str(p)
        assert "30-Day Fitness" in str(p)

    def test_str_fallback_to_email(self, challenge):
        no_name = User.objects.create_user(
            email="noname4@example.com", password="testpassword123", display_name=""
        )
        p = ChallengeProgress.objects.create(
            challenge=challenge, user=no_name, progress_value=10
        )
        assert "noname4@example.com" in str(p)

    def test_default_progress_value(self, challenge, user):
        p = ChallengeProgress.objects.create(challenge=challenge, user=user)
        assert p.progress_value == 0

    def test_default_notes_blank(self, challenge, user):
        p = ChallengeProgress.objects.create(challenge=challenge, user=user)
        assert p.notes == ""

    def test_cascade_delete_challenge(self, challenge, user):
        ChallengeProgress.objects.create(challenge=challenge, user=user, progress_value=5)
        challenge.delete()
        assert ChallengeProgress.objects.filter(user=user).count() == 0


# ---------------------------------------------------------------------------
# View / API tests
# ---------------------------------------------------------------------------

# URL prefix: /api/circles/  (circles app included at path('api/', ...))
BASE_URL = "/api/circles/"


class TestCircleListView:
    """Tests for listing circles."""

    def test_list_recommended_default(self, authenticated_client, circle):
        """Default filter is 'recommended': public circles user has NOT joined."""
        # user is already a member of `circle`, so it should NOT appear
        resp = authenticated_client.get(BASE_URL)
        assert resp.status_code == status.HTTP_200_OK
        ids = [c["id"] for c in resp.data["circles"]]
        assert str(circle.id) not in ids

    def test_list_my_circles(self, authenticated_client, circle):
        resp = authenticated_client.get(BASE_URL, {"filter": "my"})
        assert resp.status_code == status.HTTP_200_OK
        ids = [c["id"] for c in resp.data["circles"]]
        assert str(circle.id) in ids

    def test_list_public_circles(self, authenticated_client, circle, private_circle):
        resp = authenticated_client.get(BASE_URL, {"filter": "public"})
        assert resp.status_code == status.HTTP_200_OK
        ids = [c["id"] for c in resp.data["circles"]]
        assert str(circle.id) in ids
        assert str(private_circle.id) not in ids

    def test_list_unauthenticated(self, api_client):
        resp = api_client.get(BASE_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestCircleCreateView:
    """Tests for creating circles."""

    def test_create_circle(self, authenticated_client, user):
        data = {
            "name": "New Circle",
            "description": "A brand new circle",
            "category": "fitness",
            "isPublic": True,
        }
        resp = authenticated_client.post(BASE_URL, data, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        new_circle = Circle.objects.get(name="New Circle")
        assert new_circle.creator == user
        assert new_circle.is_public is True
        assert new_circle.category == "fitness"
        # Creator should be admin member
        assert CircleMembership.objects.filter(
            circle=new_circle, user=user, role="admin"
        ).exists()

    def test_create_circle_minimal(self, authenticated_client):
        data = {"name": "Minimal"}
        resp = authenticated_client.post(BASE_URL, data, format="json")
        assert resp.status_code == status.HTTP_201_CREATED

    def test_create_circle_missing_name(self, authenticated_client):
        resp = authenticated_client.post(BASE_URL, {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_unauthenticated(self, api_client):
        resp = api_client.post(BASE_URL, {"name": "X"}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestCircleRetrieveView:
    """Tests for retrieving circle details."""

    def test_retrieve_circle(self, authenticated_client, circle):
        url = f"{BASE_URL}{circle.id}/"
        resp = authenticated_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["circle"]["name"] == "Dream Achievers"
        assert "members" in resp.data["circle"]
        assert "challenges" in resp.data["circle"]

    def test_retrieve_nonexistent(self, authenticated_client):
        import uuid
        url = f"{BASE_URL}{uuid.uuid4()}/"
        resp = authenticated_client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestCircleUpdateView:
    """Tests for updating circles (admin only)."""

    def test_update_as_admin(self, authenticated_client, circle):
        url = f"{BASE_URL}{circle.id}/"
        resp = authenticated_client.put(
            url, {"name": "Updated Name"}, format="json"
        )
        assert resp.status_code == status.HTTP_200_OK
        circle.refresh_from_db()
        assert circle.name == "Updated Name"

    def test_partial_update_as_admin(self, authenticated_client, circle):
        url = f"{BASE_URL}{circle.id}/"
        resp = authenticated_client.patch(
            url, {"description": "New desc"}, format="json"
        )
        assert resp.status_code == status.HTTP_200_OK
        circle.refresh_from_db()
        assert circle.description == "New desc"

    def test_update_as_non_admin(self, api_client, circle, other_user, membership):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/"
        resp = api_client.put(url, {"name": "Hack"}, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_update_as_non_member(self, api_client, circle, other_user):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/"
        resp = api_client.put(url, {"name": "Hack"}, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestCircleDeleteView:
    """Tests for deleting circles (admin only)."""

    def test_delete_as_admin(self, authenticated_client, circle):
        url = f"{BASE_URL}{circle.id}/"
        resp = authenticated_client.delete(url)
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert Circle.objects.filter(id=circle.id).count() == 0

    def test_delete_as_non_admin(self, api_client, circle, other_user, membership):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/"
        resp = api_client.delete(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_as_non_member(self, api_client, circle, other_user):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/"
        resp = api_client.delete(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestCircleJoinView:
    """Tests for joining circles."""

    def test_join_public_circle(self, api_client, circle, other_user):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/join/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_200_OK
        assert CircleMembership.objects.filter(
            circle=circle, user=other_user, role="member"
        ).exists()

    def test_join_already_member(self, authenticated_client, circle):
        url = f"{BASE_URL}{circle.id}/join/"
        resp = authenticated_client.post(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already a member" in resp.data["error"]

    def test_join_full_circle(self, api_client, circle, other_user):
        circle.max_members = 1
        circle.save()
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/join/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "maximum" in resp.data["error"]

    def test_join_private_circle(self, api_client, private_circle, other_user):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{private_circle.id}/join/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert "private" in resp.data["error"].lower()


class TestCircleLeaveView:
    """Tests for leaving circles."""

    def test_leave_as_member(self, api_client, circle, other_user, membership):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/leave/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_200_OK
        assert not CircleMembership.objects.filter(
            circle=circle, user=other_user
        ).exists()

    def test_leave_not_member(self, api_client, circle, other_user):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/leave/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_leave_sole_admin_with_other_members(
        self, authenticated_client, circle, membership
    ):
        """Sole admin cannot leave while other members exist."""
        url = f"{BASE_URL}{circle.id}/leave/"
        resp = authenticated_client.post(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "only admin" in resp.data["error"].lower()

    def test_leave_sole_admin_last_member(self, authenticated_client, circle):
        """Sole admin CAN leave when they are the only member."""
        url = f"{BASE_URL}{circle.id}/leave/"
        resp = authenticated_client.post(url)
        assert resp.status_code == status.HTTP_200_OK

    def test_leave_admin_with_other_admins(
        self, authenticated_client, circle, other_user
    ):
        """Admin can leave when another admin exists."""
        CircleMembership.objects.create(
            circle=circle, user=other_user, role="admin"
        )
        url = f"{BASE_URL}{circle.id}/leave/"
        resp = authenticated_client.post(url)
        assert resp.status_code == status.HTTP_200_OK


class TestCircleFeedView:
    """Tests for the circle feed (GET)."""

    def test_feed_as_member(self, authenticated_client, circle, post):
        url = f"{BASE_URL}{circle.id}/feed/"
        resp = authenticated_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert "feed" in resp.data
        assert len(resp.data["feed"]) == 1

    def test_feed_as_non_member(self, api_client, circle, other_user):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/feed/"
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_feed_empty(self, authenticated_client, circle):
        url = f"{BASE_URL}{circle.id}/feed/"
        resp = authenticated_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["feed"] == []


class TestCirclePostCreateView:
    """Tests for creating posts (POST to /posts/)."""

    def test_create_post(self, authenticated_client, circle):
        url = f"{BASE_URL}{circle.id}/posts/"
        resp = authenticated_client.post(
            url, {"content": "Hello circle!"}, format="json"
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["content"] == "Hello circle!"
        assert CirclePost.objects.filter(circle=circle).count() == 1

    def test_create_post_non_member(self, api_client, circle, other_user):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/posts/"
        resp = api_client.post(url, {"content": "Hi"}, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_create_post_empty_content(self, authenticated_client, circle):
        url = f"{BASE_URL}{circle.id}/posts/"
        resp = authenticated_client.post(url, {"content": ""}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_post_missing_content(self, authenticated_client, circle):
        url = f"{BASE_URL}{circle.id}/posts/"
        resp = authenticated_client.post(url, {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


class TestCirclePostEditView:
    """Tests for editing posts."""

    def test_edit_own_post(self, authenticated_client, circle, post):
        url = f"{BASE_URL}{circle.id}/posts/{post.id}/edit/"
        resp = authenticated_client.put(
            url, {"content": "Updated content"}, format="json"
        )
        assert resp.status_code == status.HTTP_200_OK
        post.refresh_from_db()
        assert post.content == "Updated content"

    def test_edit_post_as_moderator(
        self, api_client, circle, post, other_user, moderator_membership
    ):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/posts/{post.id}/edit/"
        resp = api_client.put(
            url, {"content": "Moderated"}, format="json"
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_edit_post_as_regular_member(
        self, api_client, circle, post, other_user, membership
    ):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/posts/{post.id}/edit/"
        resp = api_client.put(
            url, {"content": "Hack"}, format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_edit_nonexistent_post(self, authenticated_client, circle):
        import uuid
        url = f"{BASE_URL}{circle.id}/posts/{uuid.uuid4()}/edit/"
        resp = authenticated_client.put(
            url, {"content": "nope"}, format="json"
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestCirclePostDeleteView:
    """Tests for deleting posts."""

    def test_delete_own_post(self, authenticated_client, circle, post):
        url = f"{BASE_URL}{circle.id}/posts/{post.id}/delete/"
        resp = authenticated_client.delete(url)
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert CirclePost.objects.filter(id=post.id).count() == 0

    def test_delete_post_as_moderator(
        self, api_client, circle, post, other_user, moderator_membership
    ):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/posts/{post.id}/delete/"
        resp = api_client.delete(url)
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_post_as_admin_of_circle(
        self, api_client, circle, other_user, membership
    ):
        """Admin (the circle fixture user) can delete other's posts."""
        other_post = CirclePost.objects.create(
            circle=circle, author=other_user, content="Delete me"
        )
        # authenticated as `user` who is admin
        from apps.users.models import User
        admin_user = circle.creator
        api_client.force_authenticate(user=admin_user)
        url = f"{BASE_URL}{circle.id}/posts/{other_post.id}/delete/"
        resp = api_client.delete(url)
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_post_as_regular_member(
        self, api_client, circle, post, other_user, membership
    ):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/posts/{post.id}/delete/"
        resp = api_client.delete(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_nonexistent_post(self, authenticated_client, circle):
        import uuid
        url = f"{BASE_URL}{circle.id}/posts/{uuid.uuid4()}/delete/"
        resp = authenticated_client.delete(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestReactToPostView:
    """Tests for reacting to posts."""

    def test_add_reaction(self, authenticated_client, circle, post):
        url = f"{BASE_URL}{circle.id}/posts/{post.id}/react/"
        resp = authenticated_client.post(
            url, {"reaction_type": "fire"}, format="json"
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert PostReaction.objects.filter(post=post, user=circle.creator).exists()

    def test_update_reaction(self, authenticated_client, circle, post, user):
        PostReaction.objects.create(post=post, user=user, reaction_type="fire")
        url = f"{BASE_URL}{circle.id}/posts/{post.id}/react/"
        resp = authenticated_client.post(
            url, {"reaction_type": "heart"}, format="json"
        )
        assert resp.status_code == status.HTTP_200_OK
        r = PostReaction.objects.get(post=post, user=user)
        assert r.reaction_type == "heart"

    def test_react_non_member(self, api_client, circle, post, other_user):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/posts/{post.id}/react/"
        resp = api_client.post(
            url, {"reaction_type": "fire"}, format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_react_invalid_type(self, authenticated_client, circle, post):
        url = f"{BASE_URL}{circle.id}/posts/{post.id}/react/"
        resp = authenticated_client.post(
            url, {"reaction_type": "invalid"}, format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_react_nonexistent_post(self, authenticated_client, circle):
        import uuid
        url = f"{BASE_URL}{circle.id}/posts/{uuid.uuid4()}/react/"
        resp = authenticated_client.post(
            url, {"reaction_type": "fire"}, format="json"
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestUnreactToPostView:
    """Tests for removing reactions."""

    def test_unreact(self, authenticated_client, circle, post, user):
        PostReaction.objects.create(post=post, user=user, reaction_type="fire")
        url = f"{BASE_URL}{circle.id}/posts/{post.id}/unreact/"
        resp = authenticated_client.delete(url)
        assert resp.status_code == status.HTTP_200_OK
        assert PostReaction.objects.filter(post=post, user=user).count() == 0

    def test_unreact_no_reaction(self, authenticated_client, circle, post):
        url = f"{BASE_URL}{circle.id}/posts/{post.id}/unreact/"
        resp = authenticated_client.delete(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_unreact_nonexistent_post(self, authenticated_client, circle):
        import uuid
        url = f"{BASE_URL}{circle.id}/posts/{uuid.uuid4()}/unreact/"
        resp = authenticated_client.delete(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestCircleChallengesView:
    """Tests for listing circle challenges."""

    def test_list_challenges(
        self, authenticated_client, circle, challenge, upcoming_challenge
    ):
        url = f"{BASE_URL}{circle.id}/challenges/"
        resp = authenticated_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["challenges"]) == 2

    def test_list_challenges_excludes_completed(
        self, authenticated_client, circle, challenge
    ):
        challenge.status = "completed"
        challenge.save()
        url = f"{BASE_URL}{circle.id}/challenges/"
        resp = authenticated_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["challenges"]) == 0

    def test_list_challenges_excludes_cancelled(
        self, authenticated_client, circle, challenge
    ):
        challenge.status = "cancelled"
        challenge.save()
        url = f"{BASE_URL}{circle.id}/challenges/"
        resp = authenticated_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["challenges"]) == 0


class TestPromoteMemberView:
    """Tests for promoting members."""

    def test_promote_member_to_moderator(
        self, authenticated_client, circle, other_user, membership
    ):
        url = f"{BASE_URL}{circle.id}/members/{membership.id}/promote/"
        resp = authenticated_client.post(url)
        assert resp.status_code == status.HTTP_200_OK
        membership.refresh_from_db()
        assert membership.role == "moderator"

    def test_promote_not_admin(
        self, api_client, circle, other_user, membership, third_user
    ):
        # third_user is a regular member trying to promote
        CircleMembership.objects.create(
            circle=circle, user=third_user, role="member"
        )
        api_client.force_authenticate(user=third_user)
        url = f"{BASE_URL}{circle.id}/members/{membership.id}/promote/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_promote_admin_fails(
        self, authenticated_client, circle, other_user, user
    ):
        """Cannot promote an existing admin."""
        admin_membership = CircleMembership.objects.get(circle=circle, user=user)
        url = f"{BASE_URL}{circle.id}/members/{admin_membership.id}/promote/"
        resp = authenticated_client.post(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_promote_nonexistent_member(self, authenticated_client, circle):
        import uuid
        url = f"{BASE_URL}{circle.id}/members/{uuid.uuid4()}/promote/"
        resp = authenticated_client.post(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestDemoteMemberView:
    """Tests for demoting members."""

    def test_demote_moderator_to_member(
        self, authenticated_client, circle, other_user, moderator_membership
    ):
        url = f"{BASE_URL}{circle.id}/members/{moderator_membership.id}/demote/"
        resp = authenticated_client.post(url)
        assert resp.status_code == status.HTTP_200_OK
        moderator_membership.refresh_from_db()
        assert moderator_membership.role == "member"

    def test_demote_regular_member_fails(
        self, authenticated_client, circle, other_user, membership
    ):
        url = f"{BASE_URL}{circle.id}/members/{membership.id}/demote/"
        resp = authenticated_client.post(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_demote_not_admin(
        self, api_client, circle, other_user, moderator_membership, third_user
    ):
        CircleMembership.objects.create(
            circle=circle, user=third_user, role="member"
        )
        api_client.force_authenticate(user=third_user)
        url = f"{BASE_URL}{circle.id}/members/{moderator_membership.id}/demote/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_demote_nonexistent_member(self, authenticated_client, circle):
        import uuid
        url = f"{BASE_URL}{circle.id}/members/{uuid.uuid4()}/demote/"
        resp = authenticated_client.post(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestRemoveMemberView:
    """Tests for removing members."""

    def test_remove_member_as_admin(
        self, authenticated_client, circle, other_user, membership
    ):
        url = f"{BASE_URL}{circle.id}/members/{membership.id}/remove/"
        resp = authenticated_client.delete(url)
        assert resp.status_code == status.HTTP_200_OK
        assert not CircleMembership.objects.filter(id=membership.id).exists()

    def test_remove_member_as_moderator(
        self, api_client, circle, other_user, third_user
    ):
        mod = CircleMembership.objects.create(
            circle=circle, user=other_user, role="moderator"
        )
        target = CircleMembership.objects.create(
            circle=circle, user=third_user, role="member"
        )
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/members/{target.id}/remove/"
        resp = api_client.delete(url)
        assert resp.status_code == status.HTTP_200_OK

    def test_remove_admin_fails(self, authenticated_client, circle, user):
        admin_membership = CircleMembership.objects.get(circle=circle, user=user)
        # Need another admin/moderator to try removing
        other = User.objects.create_user(email="adm2@example.com", password="test123")
        CircleMembership.objects.create(circle=circle, user=other, role="admin")
        url = f"{BASE_URL}{circle.id}/members/{admin_membership.id}/remove/"
        # Authenticate as the other admin
        api_client = authenticated_client  # still authenticated as `user`
        resp = api_client.delete(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_remove_not_admin_or_moderator(
        self, api_client, circle, other_user, membership, third_user
    ):
        target = CircleMembership.objects.create(
            circle=circle, user=third_user, role="member"
        )
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/members/{target.id}/remove/"
        resp = api_client.delete(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_remove_nonexistent_member(self, authenticated_client, circle):
        import uuid
        url = f"{BASE_URL}{circle.id}/members/{uuid.uuid4()}/remove/"
        resp = authenticated_client.delete(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestInviteView:
    """Tests for sending direct invitations."""

    def test_invite_user(self, authenticated_client, circle, other_user):
        url = f"{BASE_URL}{circle.id}/invite/"
        resp = authenticated_client.post(
            url, {"user_id": str(other_user.id)}, format="json"
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert CircleInvitation.objects.filter(
            circle=circle, invitee=other_user, status="pending"
        ).exists()

    def test_invite_already_member(
        self, authenticated_client, circle, other_user, membership
    ):
        url = f"{BASE_URL}{circle.id}/invite/"
        resp = authenticated_client.post(
            url, {"user_id": str(other_user.id)}, format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already a member" in resp.data["error"]

    def test_invite_already_pending(
        self, authenticated_client, circle, other_user, invitation
    ):
        url = f"{BASE_URL}{circle.id}/invite/"
        resp = authenticated_client.post(
            url, {"user_id": str(other_user.id)}, format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already pending" in resp.data["error"]

    def test_invite_nonexistent_user(self, authenticated_client, circle):
        import uuid
        url = f"{BASE_URL}{circle.id}/invite/"
        resp = authenticated_client.post(
            url, {"user_id": str(uuid.uuid4())}, format="json"
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_invite_not_admin_or_moderator(
        self, api_client, circle, other_user, membership, third_user
    ):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/invite/"
        resp = api_client.post(
            url, {"user_id": str(third_user.id)}, format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_invite_as_moderator(
        self, api_client, circle, other_user, moderator_membership, third_user
    ):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/invite/"
        resp = api_client.post(
            url, {"user_id": str(third_user.id)}, format="json"
        )
        assert resp.status_code == status.HTTP_201_CREATED


class TestInviteLinkView:
    """Tests for generating invite links."""

    def test_generate_invite_link(self, authenticated_client, circle):
        url = f"{BASE_URL}{circle.id}/invite-link/"
        resp = authenticated_client.post(url)
        assert resp.status_code == status.HTTP_201_CREATED
        assert "invite_code" in resp.data
        inv = CircleInvitation.objects.get(invite_code=resp.data["invite_code"])
        assert inv.invitee is None

    def test_generate_invite_link_not_admin(
        self, api_client, circle, other_user, membership
    ):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/invite-link/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_generate_invite_link_as_moderator(
        self, api_client, circle, other_user, moderator_membership
    ):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/invite-link/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_201_CREATED


class TestInvitationsListView:
    """Tests for listing pending invitations."""

    def test_list_invitations_as_admin(
        self, authenticated_client, circle, invitation
    ):
        url = f"{BASE_URL}{circle.id}/invitations/"
        resp = authenticated_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["invitations"]) == 1

    def test_list_invitations_as_non_admin(
        self, api_client, circle, other_user, membership
    ):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/invitations/"
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestJoinByInviteCodeView:
    """Tests for joining via invite code."""

    def test_join_via_direct_invite(self, api_client, circle, other_user, invitation):
        api_client.force_authenticate(user=other_user)
        url = f"/api/circles/join/{invitation.invite_code}/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_200_OK
        assert CircleMembership.objects.filter(
            circle=circle, user=other_user
        ).exists()
        invitation.refresh_from_db()
        assert invitation.status == "accepted"

    def test_join_via_link_invite(
        self, api_client, circle, other_user, link_invitation
    ):
        api_client.force_authenticate(user=other_user)
        url = f"/api/circles/join/{link_invitation.invite_code}/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_200_OK
        assert CircleMembership.objects.filter(
            circle=circle, user=other_user
        ).exists()
        # Link invitations stay pending (for reuse) since invitee is None
        link_invitation.refresh_from_db()
        assert link_invitation.status == "pending"

    def test_join_invite_wrong_user(
        self, api_client, circle, invitation, third_user
    ):
        """A direct invite for other_user cannot be used by third_user."""
        api_client.force_authenticate(user=third_user)
        url = f"/api/circles/join/{invitation.invite_code}/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_join_expired_invite(self, api_client, circle, user, other_user):
        inv = CircleInvitation.objects.create(
            circle=circle,
            inviter=user,
            invitee=other_user,
            invite_code=secrets.token_urlsafe(12),
            status="pending",
            expires_at=django_timezone.now() - timedelta(days=1),
        )
        api_client.force_authenticate(user=other_user)
        url = f"/api/circles/join/{inv.invite_code}/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        inv.refresh_from_db()
        assert inv.status == "expired"

    def test_join_invalid_code(self, api_client, other_user):
        api_client.force_authenticate(user=other_user)
        url = "/api/circles/join/nonexistent_code/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_join_already_member(self, api_client, circle, user, invitation):
        """User who is already a member cannot join again via invite."""
        # `user` is already admin member
        api_client.force_authenticate(user=user)
        # We need an invitation for `user`, not `other_user`
        inv = CircleInvitation.objects.create(
            circle=circle,
            inviter=user,
            invitee=user,
            invite_code=secrets.token_urlsafe(12),
            status="pending",
            expires_at=django_timezone.now() + timedelta(days=7),
        )
        url = f"/api/circles/join/{inv.invite_code}/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already a member" in resp.data["error"]

    def test_join_full_circle_via_invite(
        self, api_client, circle, other_user, link_invitation
    ):
        circle.max_members = 1
        circle.save()
        api_client.force_authenticate(user=other_user)
        url = f"/api/circles/join/{link_invitation.invite_code}/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "maximum" in resp.data["error"]


class TestMyInvitationsView:
    """Tests for listing user's received invitations."""

    def test_my_invitations(self, api_client, circle, user, other_user, invitation):
        api_client.force_authenticate(user=other_user)
        url = "/api/circles/my-invitations/"
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["invitations"]) == 1

    def test_my_invitations_excludes_expired(
        self, api_client, circle, user, other_user
    ):
        CircleInvitation.objects.create(
            circle=circle,
            inviter=user,
            invitee=other_user,
            invite_code=secrets.token_urlsafe(12),
            status="pending",
            expires_at=django_timezone.now() - timedelta(days=1),
        )
        api_client.force_authenticate(user=other_user)
        url = "/api/circles/my-invitations/"
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["invitations"]) == 0

    def test_my_invitations_empty(self, api_client, other_user):
        api_client.force_authenticate(user=other_user)
        url = "/api/circles/my-invitations/"
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["invitations"]) == 0

    def test_my_invitations_unauthenticated(self, api_client):
        url = "/api/circles/my-invitations/"
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestChallengeJoinView:
    """Tests for joining challenges via ChallengeViewSet."""

    def test_join_challenge(self, authenticated_client, circle, challenge):
        url = f"/api/circles/challenges/{challenge.id}/join/"
        resp = authenticated_client.post(url)
        assert resp.status_code == status.HTTP_200_OK
        assert challenge.participants.filter(id=circle.creator.id).exists()

    def test_join_challenge_already_joined(
        self, authenticated_client, circle, challenge, user
    ):
        challenge.participants.add(user)
        url = f"/api/circles/challenges/{challenge.id}/join/"
        resp = authenticated_client.post(url)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already joined" in resp.data["error"]

    def test_join_challenge_not_circle_member(
        self, api_client, circle, challenge, other_user
    ):
        api_client.force_authenticate(user=other_user)
        url = f"/api/circles/challenges/{challenge.id}/join/"
        resp = api_client.post(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestSubmitProgressView:
    """Tests for submitting challenge progress."""

    def test_submit_progress(
        self, authenticated_client, circle, challenge, user
    ):
        challenge.participants.add(user)
        url = f"{BASE_URL}{circle.id}/challenges/{challenge.id}/progress/"
        resp = authenticated_client.post(
            url,
            {"progress_value": 10.5, "notes": "Ran 10k"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert ChallengeProgress.objects.filter(
            challenge=challenge, user=user
        ).exists()
        p = ChallengeProgress.objects.get(challenge=challenge, user=user)
        assert p.progress_value == 10.5
        assert p.notes == "Ran 10k"

    def test_submit_progress_not_participant(
        self, authenticated_client, circle, challenge
    ):
        url = f"{BASE_URL}{circle.id}/challenges/{challenge.id}/progress/"
        resp = authenticated_client.post(
            url, {"progress_value": 5}, format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "join the challenge" in resp.data["error"]

    def test_submit_progress_not_circle_member(
        self, api_client, circle, challenge, other_user
    ):
        api_client.force_authenticate(user=other_user)
        url = f"{BASE_URL}{circle.id}/challenges/{challenge.id}/progress/"
        resp = api_client.post(
            url, {"progress_value": 5}, format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_submit_progress_nonexistent_challenge(
        self, authenticated_client, circle
    ):
        import uuid
        url = f"{BASE_URL}{circle.id}/challenges/{uuid.uuid4()}/progress/"
        resp = authenticated_client.post(
            url, {"progress_value": 5}, format="json"
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_submit_progress_negative_value(
        self, authenticated_client, circle, challenge, user
    ):
        challenge.participants.add(user)
        url = f"{BASE_URL}{circle.id}/challenges/{challenge.id}/progress/"
        resp = authenticated_client.post(
            url, {"progress_value": -1}, format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_submit_progress_without_notes(
        self, authenticated_client, circle, challenge, user
    ):
        challenge.participants.add(user)
        url = f"{BASE_URL}{circle.id}/challenges/{challenge.id}/progress/"
        resp = authenticated_client.post(
            url, {"progress_value": 7}, format="json"
        )
        assert resp.status_code == status.HTTP_201_CREATED
        p = ChallengeProgress.objects.get(challenge=challenge, user=user)
        assert p.notes == ""


class TestChallengeLeaderboardView:
    """Tests for challenge leaderboard."""

    def test_leaderboard(
        self, authenticated_client, circle, challenge, user, other_user, membership
    ):
        challenge.participants.add(user, other_user)
        ChallengeProgress.objects.create(
            challenge=challenge, user=user, progress_value=50
        )
        ChallengeProgress.objects.create(
            challenge=challenge, user=user, progress_value=30
        )
        ChallengeProgress.objects.create(
            challenge=challenge, user=other_user, progress_value=60
        )
        url = f"{BASE_URL}{circle.id}/challenges/{challenge.id}/leaderboard/"
        resp = authenticated_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        lb = resp.data["leaderboard"]
        assert len(lb) == 2
        # user total = 80, other_user total = 60 => user ranked first
        assert lb[0]["rank"] == 1
        assert lb[0]["total_progress"] == 80
        assert lb[1]["rank"] == 2
        assert lb[1]["total_progress"] == 60

    def test_leaderboard_empty(self, authenticated_client, circle, challenge):
        url = f"{BASE_URL}{circle.id}/challenges/{challenge.id}/leaderboard/"
        resp = authenticated_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["leaderboard"] == []

    def test_leaderboard_nonexistent_challenge(self, authenticated_client, circle):
        import uuid
        url = f"{BASE_URL}{circle.id}/challenges/{uuid.uuid4()}/leaderboard/"
        resp = authenticated_client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_leaderboard_contains_current_user_flag(
        self, authenticated_client, circle, challenge, user
    ):
        challenge.participants.add(user)
        ChallengeProgress.objects.create(
            challenge=challenge, user=user, progress_value=10
        )
        url = f"{BASE_URL}{circle.id}/challenges/{challenge.id}/leaderboard/"
        resp = authenticated_client.get(url)
        assert resp.data["leaderboard"][0]["is_current_user"] is True


# ---------------------------------------------------------------------------
# Admin tests
# ---------------------------------------------------------------------------


class TestCircleAdmin:
    """Tests for CircleAdmin custom methods."""

    def test_member_count(self, circle):
        admin_instance = CircleAdmin(Circle, None)
        assert admin_instance.member_count(circle) == 1

    def test_member_count_with_members(self, circle, membership):
        admin_instance = CircleAdmin(Circle, None)
        assert admin_instance.member_count(circle) == 2

    def test_member_count_short_description(self):
        admin_instance = CircleAdmin(Circle, None)
        assert admin_instance.member_count.short_description == "Members"


class TestCirclePostAdmin:
    """Tests for CirclePostAdmin custom methods."""

    def test_content_preview_short(self, post):
        admin_instance = CirclePostAdmin(CirclePost, None)
        result = admin_instance.content_preview(post)
        assert result == post.content

    def test_content_preview_long(self, circle, user):
        long_content = "A" * 100
        p = CirclePost.objects.create(
            circle=circle, author=user, content=long_content
        )
        admin_instance = CirclePostAdmin(CirclePost, None)
        result = admin_instance.content_preview(p)
        assert result.endswith("...")
        assert len(result) == 83  # 80 chars + '...'

    def test_content_preview_short_description(self):
        admin_instance = CirclePostAdmin(CirclePost, None)
        assert admin_instance.content_preview.short_description == "Content"


class TestCircleChallengeAdmin:
    """Tests for CircleChallengeAdmin custom methods."""

    def test_participant_count_zero(self, challenge):
        admin_instance = CircleChallengeAdmin(CircleChallenge, None)
        assert admin_instance.participant_count(challenge) == 0

    def test_participant_count_nonzero(self, challenge, user, other_user):
        challenge.participants.add(user, other_user)
        admin_instance = CircleChallengeAdmin(CircleChallenge, None)
        assert admin_instance.participant_count(challenge) == 2

    def test_participant_count_short_description(self):
        admin_instance = CircleChallengeAdmin(CircleChallenge, None)
        assert admin_instance.participant_count.short_description == "Participants"


# ---------------------------------------------------------------------------
# Serializer edge-case tests
# ---------------------------------------------------------------------------


class TestCircleCreateSerializer:
    """Tests for CircleCreateSerializer auto-membership on create."""

    def test_create_adds_admin_membership(self, authenticated_client):
        resp = authenticated_client.post(
            BASE_URL,
            {"name": "Serializer Test", "category": "health"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        c = Circle.objects.get(name="Serializer Test")
        admin_mem = CircleMembership.objects.filter(circle=c, role="admin")
        assert admin_mem.count() == 1

    def test_create_default_public(self, authenticated_client):
        resp = authenticated_client.post(
            BASE_URL, {"name": "Default Public"}, format="json"
        )
        c = Circle.objects.get(name="Default Public")
        assert c.is_public is True

    def test_create_private(self, authenticated_client):
        resp = authenticated_client.post(
            BASE_URL,
            {"name": "Private One", "isPublic": False},
            format="json",
        )
        c = Circle.objects.get(name="Private One")
        assert c.is_public is False


class TestCirclePostSerializer:
    """Tests for CirclePostSerializer reaction aggregation."""

    def test_reaction_counts(self, authenticated_client, circle, post, user, other_user):
        CircleMembership.objects.create(
            circle=circle, user=other_user, role="member"
        )
        PostReaction.objects.create(post=post, user=user, reaction_type="fire")
        PostReaction.objects.create(post=post, user=other_user, reaction_type="fire")
        url = f"{BASE_URL}{circle.id}/feed/"
        resp = authenticated_client.get(url)
        feed_post = resp.data["feed"][0]
        assert feed_post["reactions"]["fire"] == 2

    def test_user_info_in_post(self, authenticated_client, circle, post):
        url = f"{BASE_URL}{circle.id}/feed/"
        resp = authenticated_client.get(url)
        feed_post = resp.data["feed"][0]
        assert "user" in feed_post
        assert feed_post["user"]["username"] == "Test User"
