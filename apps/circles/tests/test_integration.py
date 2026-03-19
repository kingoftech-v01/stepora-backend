"""
Integration tests for the Circles app API endpoints.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from apps.circles.models import Circle, CircleMembership


# ── List Circles ──────────────────────────────────────────────────────


class TestListCircles:
    """Tests for listing circles."""

    def test_list_circles(self, circle_client, test_circle):
        """Premium user can list circles."""
        response = circle_client.get("/api/circles/circles/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_circles_unauthenticated(self, anon_client):
        """Unauthenticated users get 401."""
        response = anon_client.get("/api/circles/circles/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── Create Circle ─────────────────────────────────────────────────────


class TestCreateCircle:
    """Tests for creating circles."""

    def test_create_circle_pro_user(self, circle_pro_client):
        """Pro user can create a circle."""
        response = circle_pro_client.post(
            "/api/circles/circles/",
            {
                "name": "New Circle",
                "description": "A new circle",
                "category": "health",
                "is_public": True,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Circle"
        assert response.data["category"] == "health"

    def test_create_circle_missing_name(self, circle_pro_client):
        """Circle creation fails without name."""
        response = circle_pro_client.post(
            "/api/circles/circles/",
            {"description": "No name circle", "category": "health"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_circle_unauthenticated(self, anon_client):
        """Unauthenticated users cannot create circles."""
        response = anon_client.post(
            "/api/circles/circles/",
            {"name": "Anon Circle", "category": "health"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── Join Circle ───────────────────────────────────────────────────────


class TestJoinCircle:
    """Tests for joining circles."""

    def test_join_public_circle(self, circle_pro_client, test_circle):
        """Pro user can join a public circle."""
        # Create a separate pro user to join (the fixture pro user is the creator)
        from apps.users.models import User
        from apps.subscriptions.models import Subscription, SubscriptionPlan
        from datetime import timedelta
        from decimal import Decimal

        user2 = User.objects.create_user(
            email="joiner@example.com", password="testpass123"
        )
        plan = SubscriptionPlan.objects.get(slug="pro")
        Subscription.objects.update_or_create(
            user=user2,
            defaults={
                "plan": plan,
                "status": "active",
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now() + timedelta(days=30),
            },
        )
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user2)
        response = client.post(
            f"/api/circles/circles/{test_circle.id}/join/",
        )
        assert response.status_code == status.HTTP_200_OK
        assert CircleMembership.objects.filter(
            circle=test_circle, user=user2
        ).exists()

    def test_join_circle_already_member(
        self, circle_pro_client, test_circle, circle_pro_user
    ):
        """Joining a circle you're already in returns appropriate error."""
        # circle_pro_user is already the admin/creator
        response = circle_pro_client.post(
            f"/api/circles/circles/{test_circle.id}/join/",
        )
        assert response.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_409_CONFLICT,
        )

    def test_join_nonexistent_circle(self, circle_pro_client):
        """Joining a nonexistent circle returns 404."""
        import uuid

        fake_id = uuid.uuid4()
        response = circle_pro_client.post(
            f"/api/circles/circles/{fake_id}/join/",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_join_free_user_forbidden(self, free_circle_client, test_circle):
        """Free user cannot join circles (permission denied)."""
        response = free_circle_client.post(
            f"/api/circles/circles/{test_circle.id}/join/",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ── Create Post in Circle ────────────────────────────────────────────


class TestCreatePostInCircle:
    """Tests for creating posts in circles."""

    def test_create_post_as_member(self, circle_pro_client, test_circle):
        """Circle member can create a post."""
        response = circle_pro_client.post(
            f"/api/circles/circles/{test_circle.id}/posts/",
            {"content": "Hello from the circle!"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["content"] == "Hello from the circle!"

    def test_create_post_non_member(self, circle_client, test_circle):
        """Non-member cannot create a post."""
        response = circle_client.post(
            f"/api/circles/circles/{test_circle.id}/posts/",
            {"content": "I am not a member"},
            format="json",
        )
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_create_post_empty_content(self, circle_pro_client, test_circle):
        """Post with empty content fails."""
        response = circle_pro_client.post(
            f"/api/circles/circles/{test_circle.id}/posts/",
            {"content": ""},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_circle_feed(self, circle_pro_client, test_circle, test_post):
        """Circle feed returns posts."""
        response = circle_pro_client.get(
            f"/api/circles/circles/{test_circle.id}/feed/",
        )
        assert response.status_code == status.HTTP_200_OK


# ── Circle Settings Update ───────────────────────────────────────────


class TestCircleUpdate:
    """Tests for updating circle settings."""

    def test_update_circle_as_admin(self, circle_pro_client, test_circle):
        """Admin can update circle settings."""
        response = circle_pro_client.patch(
            f"/api/circles/circles/{test_circle.id}/",
            {"name": "Updated Circle Name", "description": "New description"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_update_circle_non_admin(self, circle_client, test_circle):
        """Non-admin cannot update circle settings."""
        # circle_client is premium but not a member/admin
        response = circle_client.patch(
            f"/api/circles/circles/{test_circle.id}/",
            {"name": "Hacked Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ── Leave Circle ────────────────────────────────────────────────────


class TestLeaveCircle:
    """Tests for leaving circles."""

    def test_leave_circle_as_member(self, test_circle):
        """Member can leave a circle."""
        from apps.users.models import User
        from apps.subscriptions.models import Subscription, SubscriptionPlan
        from rest_framework.test import APIClient

        user = User.objects.create_user(
            email="leaver@example.com", password="testpass123"
        )
        plan = SubscriptionPlan.objects.get(slug="pro")
        Subscription.objects.update_or_create(
            user=user,
            defaults={
                "plan": plan,
                "status": "active",
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now() + timedelta(days=30),
            },
        )
        CircleMembership.objects.create(
            circle=test_circle, user=user, role="member"
        )
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post(
            f"/api/circles/circles/{test_circle.id}/leave/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert not CircleMembership.objects.filter(
            circle=test_circle, user=user
        ).exists()

    def test_leave_circle_not_member(self, circle_pro_client, test_circle):
        """Non-member leaving returns 400 (pro user who is not a member but is the admin)."""
        # circle_pro_user is already admin, let's create another pro user
        from apps.users.models import User
        from apps.subscriptions.models import Subscription, SubscriptionPlan
        from rest_framework.test import APIClient

        user = User.objects.create_user(
            email="notmember@example.com", password="testpass123"
        )
        plan = SubscriptionPlan.objects.get(slug="pro")
        Subscription.objects.update_or_create(
            user=user,
            defaults={
                "plan": plan,
                "status": "active",
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now() + timedelta(days=30),
            },
        )
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post(
            f"/api/circles/circles/{test_circle.id}/leave/"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_leave_circle_as_sole_admin_auto_transfers(
        self, circle_pro_client, test_circle, circle_pro_user
    ):
        """Last admin leaving auto-transfers ownership."""
        from apps.users.models import User
        from apps.subscriptions.models import Subscription, SubscriptionPlan

        user2 = User.objects.create_user(
            email="leaver_member@example.com", password="testpass123"
        )
        plan = SubscriptionPlan.objects.get(slug="pro")
        Subscription.objects.update_or_create(
            user=user2,
            defaults={
                "plan": plan,
                "status": "active",
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now() + timedelta(days=30),
            },
        )
        CircleMembership.objects.create(
            circle=test_circle, user=user2, role="member"
        )
        response = circle_pro_client.post(
            f"/api/circles/circles/{test_circle.id}/leave/"
        )
        assert response.status_code == status.HTTP_200_OK
        # user2 should now be admin
        user2_membership = CircleMembership.objects.filter(
            circle=test_circle, user=user2
        ).first()
        assert user2_membership is not None
        assert user2_membership.role == "admin"


# ── Circle Challenges ──────────────────────────────────────────────


class TestCircleChallenges:
    """Tests for circle challenge endpoints."""

    def test_list_challenges(self, circle_pro_client, test_circle, test_challenge):
        """List circle challenges."""
        response = circle_pro_client.get(
            f"/api/circles/circles/{test_circle.id}/challenges/"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_create_challenge_as_admin(self, circle_pro_client, test_circle):
        """Admin can create a challenge."""
        response = circle_pro_client.post(
            f"/api/circles/circles/{test_circle.id}/challenges/create/",
            {
                "title": "Weekly Task Sprint",
                "description": "Complete 10 tasks this week",
                "challenge_type": "tasks_completed",
                "target_value": 10,
                "start_date": timezone.now().isoformat(),
                "end_date": (timezone.now() + timedelta(days=7)).isoformat(),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_challenge_as_non_admin(self, circle_client, test_circle, circle_user):
        """Non-admin member cannot create a challenge."""
        CircleMembership.objects.create(
            circle=test_circle, user=circle_user, role="member"
        )
        response = circle_client.post(
            f"/api/circles/circles/{test_circle.id}/challenges/create/",
            {
                "title": "Unauthorized Challenge",
                "challenge_type": "tasks_completed",
                "target_value": 5,
                "start_date": timezone.now().isoformat(),
                "end_date": (timezone.now() + timedelta(days=7)).isoformat(),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_challenges_non_member(self, circle_client, test_circle):
        """Non-member cannot view challenges."""
        response = circle_client.get(
            f"/api/circles/circles/{test_circle.id}/challenges/"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ── Circle Feed (non-member) ────────────────────────────────────────


class TestCircleFeedNonMember:
    """Tests for circle feed access by non-members."""

    def test_feed_non_member(self, circle_client, test_circle):
        """Non-member cannot view circle feed."""
        response = circle_client.get(
            f"/api/circles/circles/{test_circle.id}/feed/"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ── Circle Retrieve ──────────────────────────────────────────────────


class TestCircleRetrieve:
    """Tests for retrieving circle details."""

    def test_retrieve_public_circle(self, circle_pro_client, test_circle):
        """Retrieve details of a public circle."""
        response = circle_pro_client.get(
            f"/api/circles/circles/{test_circle.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert "circle" in response.data

    def test_retrieve_private_circle_non_member(self, circle_client, private_circle):
        """Non-member cannot retrieve private circle details."""
        response = circle_client.get(
            f"/api/circles/circles/{private_circle.id}/"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_retrieve_nonexistent_circle(self, circle_pro_client):
        """Retrieve nonexistent circle returns 404."""
        import uuid

        response = circle_pro_client.get(
            f"/api/circles/circles/{uuid.uuid4()}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ── Circle Delete ────────────────────────────────────────────────────


class TestCircleDelete:
    """Tests for deleting circles."""

    def test_delete_circle_as_admin(self, circle_pro_client, circle_pro_user):
        """Admin can delete their circle."""
        circle = Circle.objects.create(
            name="Delete Me",
            description="To be deleted",
            category="health",
            is_public=True,
            creator=circle_pro_user,
        )
        CircleMembership.objects.create(
            circle=circle, user=circle_pro_user, role="admin"
        )
        response = circle_pro_client.delete(
            f"/api/circles/circles/{circle.id}/"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_circle_non_admin(self, circle_client, test_circle):
        """Non-admin cannot delete circle."""
        response = circle_client.delete(
            f"/api/circles/circles/{test_circle.id}/"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ── Circle List Filters ──────────────────────────────────────────────


class TestCircleListFilters:
    """Tests for circle list with filters."""

    def test_list_my_circles(self, circle_pro_client, test_circle):
        """List user's circles with 'my' filter."""
        response = circle_pro_client.get(
            "/api/circles/circles/?filter=my"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_list_public_circles(self, circle_pro_client, test_circle):
        """List public circles."""
        response = circle_pro_client.get(
            "/api/circles/circles/?filter=public"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_list_recommended_circles(self, circle_pro_client, test_circle):
        """List recommended circles."""
        response = circle_pro_client.get(
            "/api/circles/circles/?filter=recommended"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_join_private_circle(self, test_circle, circle_user):
        """Cannot join a private circle without invitation."""
        from apps.subscriptions.models import Subscription, SubscriptionPlan
        from rest_framework.test import APIClient

        # Make it private
        test_circle.is_public = False
        test_circle.save()

        # Need pro plan to access circles
        plan = SubscriptionPlan.objects.get(slug="pro")
        Subscription.objects.update_or_create(
            user=circle_user,
            defaults={
                "plan": plan,
                "status": "active",
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now() + timedelta(days=30),
            },
        )

        client = APIClient()
        client.force_authenticate(user=circle_user)
        response = client.post(
            f"/api/circles/circles/{test_circle.id}/join/"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
