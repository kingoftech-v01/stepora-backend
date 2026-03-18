"""
Integration tests for the Users app API endpoints.
"""

import pytest
from rest_framework import status

from apps.users.models import User


# ──────────────────────────────────────────────────────────────────────
#  Get User Profile (GET /api/users/me/)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGetUserProfile:
    """Integration tests for retrieving the current user's profile."""

    def test_get_me(self, users_client, users_user):
        """Authenticated user can retrieve their own profile."""
        response = users_client.get("/api/users/me/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data["email"] == users_user.email
        assert data["display_name"] == users_user.display_name

    def test_get_me_unauthenticated(self):
        """Unauthenticated request to /me/ returns 401."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.get("/api/users/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_me_contains_expected_fields(self, users_client):
        """Profile response contains key fields."""
        response = users_client.get("/api/users/me/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        # Check for essential fields
        assert "id" in data
        assert "email" in data
        assert "display_name" in data

    def test_get_me_subscription_field(self, users_client, users_user):
        """Profile includes subscription field."""
        response = users_client.get("/api/users/me/")
        assert response.status_code == status.HTTP_200_OK
        # Default subscription is free
        assert "subscription" in response.data


# ──────────────────────────────────────────────────────────────────────
#  Update Profile
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUpdateProfile:
    """Integration tests for updating the current user's profile."""

    def test_update_display_name(self, users_client, users_user):
        """User can update their display name."""
        response = users_client.patch(
            "/api/users/update_profile/",
            {"display_name": "New Display Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        users_user.refresh_from_db()
        assert users_user.display_name == "New Display Name"

    def test_update_bio(self, users_client, users_user):
        """User can update their bio."""
        response = users_client.patch(
            "/api/users/update_profile/",
            {"bio": "This is my updated bio"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        users_user.refresh_from_db()
        assert users_user.bio == "This is my updated bio"

    def test_update_timezone(self, users_client, users_user):
        """User can update their timezone."""
        response = users_client.patch(
            "/api/users/update_profile/",
            {"timezone": "America/New_York"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        users_user.refresh_from_db()
        assert users_user.timezone == "America/New_York"

    def test_update_profile_unauthenticated(self):
        """Unauthenticated user cannot update profile."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.patch(
            "/api/users/update_profile/",
            {"display_name": "Hacker"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_multiple_fields(self, users_client, users_user):
        """User can update multiple fields at once."""
        response = users_client.patch(
            "/api/users/update_profile/",
            {
                "display_name": "Multi Update",
                "bio": "Updated bio",
                "location": "Paris, France",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        users_user.refresh_from_db()
        assert users_user.display_name == "Multi Update"
        assert users_user.bio == "Updated bio"
        assert users_user.location == "Paris, France"

    def test_update_theme_mode(self, users_client, users_user):
        """User can update their theme mode."""
        response = users_client.patch(
            "/api/users/update_profile/",
            {"theme_mode": "dark"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        users_user.refresh_from_db()
        assert users_user.theme_mode == "dark"


# ──────────────────────────────────────────────────────────────────────
#  Get User by ID
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGetUserById:
    """Integration tests for retrieving a user's public profile by ID."""

    def test_get_user_by_id(self, users_client, users_user2):
        """Authenticated user can retrieve another user's public profile."""
        response = users_client.get(f"/api/users/{users_user2.id}/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data["id"] == str(users_user2.id)
        assert data["display_name"] == users_user2.display_name

    def test_get_own_profile_by_id(self, users_client, users_user):
        """User can retrieve their own profile by ID."""
        response = users_client.get(f"/api/users/{users_user.id}/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data["id"] == str(users_user.id)

    def test_get_nonexistent_user(self, users_client):
        """Requesting a nonexistent user returns 404."""
        import uuid

        fake_id = uuid.uuid4()
        response = users_client.get(f"/api/users/{fake_id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_private_profile_returns_403(self, users_client, users_user2):
        """Requesting a private profile returns 403."""
        users_user2.profile_visibility = "private"
        users_user2.save(update_fields=["profile_visibility"])
        response = users_client.get(f"/api/users/{users_user2.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_friends_only_profile_not_friend(self, users_client, users_user2):
        """Requesting a friends-only profile when not friends returns 403."""
        users_user2.profile_visibility = "friends"
        users_user2.save(update_fields=["profile_visibility"])
        response = users_client.get(f"/api/users/{users_user2.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_friends_only_profile_when_friend(
        self, users_client, users_user, users_user2
    ):
        """Requesting a friends-only profile when friends returns 200."""
        from apps.social.models import Friendship

        Friendship.objects.create(
            user1=users_user, user2=users_user2, status="accepted"
        )
        users_user2.profile_visibility = "friends"
        users_user2.save(update_fields=["profile_visibility"])
        response = users_client.get(f"/api/users/{users_user2.id}/")
        assert response.status_code == status.HTTP_200_OK

    def test_get_user_by_id_unauthenticated(self, users_user2):
        """Unauthenticated request for user profile returns 401."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.get(f"/api/users/{users_user2.id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_public_profile_contains_expected_fields(self, users_client, users_user2):
        """Public profile response contains expected fields."""
        response = users_client.get(f"/api/users/{users_user2.id}/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert "id" in data
        assert "display_name" in data
        assert "level" in data
        assert "xp" in data
        assert "streak" in data
