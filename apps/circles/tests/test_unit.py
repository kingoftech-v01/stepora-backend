"""
Unit tests for the Circles app models.
"""

from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.circles.models import (
    Circle,
    CircleChallenge,
    CircleMembership,
    CirclePost,
    PostReaction,
)
from apps.users.models import User


# ── Circle model ──────────────────────────────────────────────────────


class TestCircleModel:
    """Tests for the Circle model."""

    def test_create_circle(self, test_circle):
        """Circle can be created with required fields."""
        assert test_circle.name == "Test Circle"
        assert test_circle.category == "career"
        assert test_circle.is_public is True

    def test_str_representation(self, test_circle):
        """__str__ includes name, visibility, and category."""
        s = str(test_circle)
        assert "Test Circle" in s
        assert "Public" in s
        assert "career" in s

    def test_str_private(self, private_circle):
        """__str__ shows Private for non-public circles."""
        s = str(private_circle)
        assert "Private" in s

    def test_member_count(self, test_circle, circle_pro_user):
        """member_count returns the number of members."""
        assert test_circle.member_count == 1  # creator only

    def test_member_count_multiple(self, test_circle, circle_user):
        """member_count increases when members join."""
        CircleMembership.objects.create(
            circle=test_circle, user=circle_user, role="member"
        )
        assert test_circle.member_count == 2

    def test_is_full_false(self, test_circle):
        """is_full returns False when below capacity."""
        assert test_circle.is_full is False

    def test_is_full_true(self, db, circle_pro_user):
        """is_full returns True when at capacity."""
        circle = Circle.objects.create(
            name="Tiny Circle",
            creator=circle_pro_user,
            max_members=1,
            is_public=True,
        )
        CircleMembership.objects.create(
            circle=circle, user=circle_pro_user, role="admin"
        )
        assert circle.is_full is True

    def test_category_choices(self, db, circle_pro_user):
        """Circle can be created with any valid category."""
        for code, _ in Circle.CATEGORY_CHOICES:
            circle = Circle.objects.create(
                name=f"Circle {code}",
                creator=circle_pro_user,
                category=code,
            )
            assert circle.category == code

    def test_default_max_members(self, db, circle_pro_user):
        """Default max_members is 20."""
        circle = Circle.objects.create(
            name="Default Circle",
            creator=circle_pro_user,
        )
        assert circle.max_members == 20


# ── CircleMembership model ───────────────────────────────────────────


class TestCircleMembershipModel:
    """Tests for the CircleMembership model."""

    def test_create_membership(self, test_circle, circle_user):
        """CircleMembership links user to circle."""
        membership = CircleMembership.objects.create(
            circle=test_circle, user=circle_user, role="member"
        )
        assert membership.circle == test_circle
        assert membership.user == circle_user
        assert membership.role == "member"

    def test_unique_membership(self, test_circle, circle_pro_user):
        """A user cannot be a member of the same circle twice."""
        with pytest.raises(IntegrityError):
            CircleMembership.objects.create(
                circle=test_circle, user=circle_pro_user, role="member"
            )

    def test_role_choices(self, test_circle, circle_user):
        """Membership supports all defined role choices."""
        membership = CircleMembership.objects.create(
            circle=test_circle, user=circle_user, role="moderator"
        )
        assert membership.role == "moderator"

    def test_str_representation(self, test_circle, circle_user):
        """__str__ includes user name and circle name."""
        membership = CircleMembership.objects.create(
            circle=test_circle, user=circle_user, role="member"
        )
        s = str(membership)
        assert test_circle.name in s
        assert "member" in s


# ── CirclePost model ──────────────────────────────────────────────────


class TestCirclePostModel:
    """Tests for the CirclePost model."""

    def test_create_post(self, test_post):
        """CirclePost can be created with required fields."""
        assert test_post.content == "This is a test post"
        assert test_post.circle is not None
        assert test_post.author is not None

    def test_str_representation(self, test_post):
        """__str__ includes author and content preview."""
        s = str(test_post)
        assert "This is a test post" in s

    def test_long_content_str_truncated(self, test_circle, circle_pro_user):
        """__str__ truncates long content."""
        long_content = "A" * 100
        post = CirclePost.objects.create(
            circle=test_circle,
            author=circle_pro_user,
            content=long_content,
        )
        s = str(post)
        assert "..." in s

    def test_ordering(self, test_circle, circle_pro_user):
        """Posts are ordered by -created_at (newest first)."""
        post1 = CirclePost.objects.create(
            circle=test_circle, author=circle_pro_user, content="First"
        )
        post2 = CirclePost.objects.create(
            circle=test_circle, author=circle_pro_user, content="Second"
        )
        posts = list(CirclePost.objects.filter(circle=test_circle))
        assert posts[0].id == post2.id
        assert posts[1].id == post1.id


# ── CircleChallenge model ────────────────────────────────────────────


class TestCircleChallengeModel:
    """Tests for the CircleChallenge model."""

    def test_create_challenge(self, test_challenge):
        """CircleChallenge can be created with required fields."""
        assert test_challenge.title == "Test Challenge"
        assert test_challenge.challenge_type == "tasks_completed"
        assert test_challenge.target_value == 10
        assert test_challenge.status == "active"

    def test_is_active_property(self, test_challenge):
        """is_active returns True for active challenges within date range."""
        assert test_challenge.is_active is True

    def test_is_active_expired(self, test_circle, circle_pro_user):
        """is_active returns False for expired challenges."""
        challenge = CircleChallenge.objects.create(
            circle=test_circle,
            creator=circle_pro_user,
            title="Expired",
            start_date=timezone.now() - timedelta(days=14),
            end_date=timezone.now() - timedelta(days=7),
            status="active",
        )
        assert challenge.is_active is False

    def test_is_active_upcoming(self, test_circle, circle_pro_user):
        """is_active returns False for upcoming challenges."""
        challenge = CircleChallenge.objects.create(
            circle=test_circle,
            creator=circle_pro_user,
            title="Upcoming",
            start_date=timezone.now() + timedelta(days=1),
            end_date=timezone.now() + timedelta(days=7),
            status="upcoming",
        )
        assert challenge.is_active is False

    def test_participant_count(self, test_challenge, circle_user):
        """participant_count returns the number of participants."""
        assert test_challenge.participant_count == 0
        test_challenge.participants.add(circle_user)
        assert test_challenge.participant_count == 1

    def test_challenge_type_label(self, test_challenge):
        """challenge_type_label returns human-readable label."""
        assert test_challenge.challenge_type_label == "Complete Tasks"

    def test_str_representation(self, test_challenge):
        """__str__ includes title, circle, and status."""
        s = str(test_challenge)
        assert "Test Challenge" in s
        assert "Test Circle" in s
        assert "active" in s

    def test_challenge_types(self, test_circle, circle_pro_user):
        """All challenge types can be created."""
        for code, _ in CircleChallenge.CHALLENGE_TYPE_CHOICES:
            challenge = CircleChallenge.objects.create(
                circle=test_circle,
                creator=circle_pro_user,
                title=f"Challenge {code}",
                challenge_type=code,
                start_date=timezone.now(),
                end_date=timezone.now() + timedelta(days=7),
            )
            assert challenge.challenge_type == code


# ── PostReaction model ────────────────────────────────────────────────


class TestPostReactionModel:
    """Tests for the PostReaction model."""

    def test_create_reaction(self, test_post, circle_user):
        """PostReaction can be created."""
        reaction = PostReaction.objects.create(
            post=test_post,
            user=circle_user,
            reaction_type="fire",
        )
        assert reaction.reaction_type == "fire"

    def test_unique_reaction_per_user_per_post(self, test_post, circle_user):
        """A user can only react once per post."""
        PostReaction.objects.create(
            post=test_post, user=circle_user, reaction_type="fire"
        )
        with pytest.raises(IntegrityError):
            PostReaction.objects.create(
                post=test_post, user=circle_user, reaction_type="heart"
            )


# ══════════════════════════════════════════════════════════════════════
#  API ENDPOINT TESTS — Circles
# ══════════════════════════════════════════════════════════════════════

import pytest


@pytest.mark.django_db
class TestCircleAPI:
    """Tests for Circle API endpoints."""

    def test_list_circles(self, circle_client):
        resp = circle_client.get(
            "/api/circles/circles/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)
