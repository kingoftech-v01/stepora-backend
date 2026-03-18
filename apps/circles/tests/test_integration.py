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
