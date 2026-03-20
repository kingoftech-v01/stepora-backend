"""
Tests for friends views.
"""

import pytest
from rest_framework.test import APIClient

from apps.friends.models import Friendship
from apps.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def view_user_a(db):
    return User.objects.create_user(
        email="fva@test.com", password="testpass123", display_name="User A"
    )


@pytest.fixture
def view_user_b(db):
    return User.objects.create_user(
        email="fvb@test.com", password="testpass123", display_name="User B"
    )


@pytest.fixture
def auth_client(api_client, view_user_a):
    api_client.force_authenticate(user=view_user_a)
    return api_client


@pytest.mark.django_db
class TestFriendshipViewSet:
    def test_list_friends(self, auth_client):
        response = auth_client.get("/api/v1/friends/friends/")
        assert response.status_code == 200
        assert "friends" in response.data

    def test_send_request(self, auth_client, view_user_b):
        response = auth_client.post(
            "/api/v1/friends/request/",
            {"user_id": str(view_user_b.id)},
            format="json",
        )
        assert response.status_code == 201

    def test_send_request_to_self(self, auth_client, view_user_a):
        response = auth_client.post(
            "/api/v1/friends/request/",
            {"user_id": str(view_user_a.id)},
            format="json",
        )
        assert response.status_code == 400

    def test_accept_request(self, auth_client, view_user_a, view_user_b, api_client):
        f = Friendship.objects.create(
            user1=view_user_b, user2=view_user_a, status="pending"
        )
        response = auth_client.post(f"/api/v1/friends/{f.id}/accept/")
        assert response.status_code == 200

    def test_pending_requests(self, auth_client, view_user_a, view_user_b):
        Friendship.objects.create(
            user1=view_user_b, user2=view_user_a, status="pending"
        )
        response = auth_client.get("/api/v1/friends/requests/pending/")
        assert response.status_code == 200
        assert response.data["count"] == 1

    def test_follow(self, auth_client, view_user_b):
        response = auth_client.post(
            "/api/v1/friends/follow/",
            {"user_id": str(view_user_b.id)},
            format="json",
        )
        assert response.status_code == 201

    def test_block(self, auth_client, view_user_b):
        response = auth_client.post(
            "/api/v1/friends/block/",
            {"user_id": str(view_user_b.id)},
            format="json",
        )
        assert response.status_code == 201

    def test_counts(self, auth_client, view_user_b):
        response = auth_client.get(f"/api/v1/friends/counts/{view_user_b.id}/")
        assert response.status_code == 200
        assert "friends" in response.data
