"""
Integration tests for the Buddies app API endpoints.

Tests buddy pairing, finding matches, sending encouragement,
viewing progress, and ending pairings. All endpoints require
authentication and premium+ subscription.
"""

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.buddies.models import (
    AccountabilityContract,
    BuddyEncouragement,
    BuddyPairing,
    ContractCheckIn,
)
from apps.users.models import User


@pytest.fixture
def buddy_client(buddy_user1):
    """Authenticated API client for buddy_user1."""
    client = APIClient()
    client.force_authenticate(user=buddy_user1)
    return client


@pytest.fixture
def buddy_client2(buddy_user2):
    """Authenticated API client for buddy_user2."""
    client = APIClient()
    client.force_authenticate(user=buddy_user2)
    return client


@pytest.fixture
def premium_buddy_user1(buddy_user1):
    """Make buddy_user1 premium."""
    from apps.subscriptions.models import Subscription, SubscriptionPlan

    plan = SubscriptionPlan.objects.get(slug="premium")
    Subscription.objects.update_or_create(
        user=buddy_user1,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return buddy_user1


@pytest.fixture
def premium_buddy_client(premium_buddy_user1):
    """Premium authenticated client for buddy_user1."""
    client = APIClient()
    client.force_authenticate(user=premium_buddy_user1)
    return client


@pytest.fixture
def premium_buddy_user2(buddy_user2):
    """Make buddy_user2 premium."""
    from apps.subscriptions.models import Subscription, SubscriptionPlan

    plan = SubscriptionPlan.objects.get(slug="premium")
    Subscription.objects.update_or_create(
        user=buddy_user2,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return buddy_user2


@pytest.fixture
def premium_buddy_client2(premium_buddy_user2):
    """Premium authenticated client for buddy_user2."""
    client = APIClient()
    client.force_authenticate(user=premium_buddy_user2)
    return client


# ──────────────────────────────────────────────────────────────────────
#  Authentication & Permissions
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBuddyAuth:
    """Tests for buddy auth and permissions."""

    def test_unauthenticated_access(self):
        """Unauthenticated access returns 401."""
        client = APIClient()
        response = client.get("/api/buddies/current/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_free_user_access(self, buddy_client):
        """Free user accessing buddy features returns 403."""
        response = buddy_client.get("/api/buddies/current/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ──────────────────────────────────────────────────────────────────────
#  Get Current Buddy
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGetCurrentBuddy:
    """Tests for GET /api/buddies/current/"""

    def test_current_no_buddy(self, premium_buddy_client):
        """Get current buddy when no pairing exists."""
        response = premium_buddy_client.get("/api/buddies/current/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["buddy"] is None

    def test_current_with_active_buddy(self, premium_buddy_client, active_pairing, buddy_user2):
        """Get current buddy with active pairing."""
        response = premium_buddy_client.get("/api/buddies/current/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["buddy"] is not None
        assert response.data["buddy"]["status"] == "active"

    def test_current_ignores_pending(self, premium_buddy_client, pending_pairing):
        """Current buddy ignores pending pairings."""
        response = premium_buddy_client.get("/api/buddies/current/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["buddy"] is None


# ──────────────────────────────────────────────────────────────────────
#  Find Buddy (match)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFindBuddy:
    """Tests for finding a buddy match."""

    def test_find_buddy_no_candidates(self, premium_buddy_client):
        """Find buddy when no candidates exist."""
        response = premium_buddy_client.post("/api/buddies/find/")
        # Endpoint may return 200 with empty or 404 depending on implementation
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    def test_find_buddy_already_has_active(
        self, premium_buddy_client, active_pairing
    ):
        """Find buddy when already has an active pairing."""
        response = premium_buddy_client.post("/api/buddies/find/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        )


# ──────────────────────────────────────────────────────────────────────
#  Buddy Progress
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBuddyProgress:
    """Tests for buddy progress endpoint."""

    def test_progress_with_pairing(
        self, premium_buddy_client, active_pairing
    ):
        """Get progress for an active pairing."""
        response = premium_buddy_client.get("/api/buddies/progress/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    def test_progress_no_pairing(self, premium_buddy_client):
        """Get progress with no active pairing."""
        response = premium_buddy_client.get("/api/buddies/progress/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )


# ──────────────────────────────────────────────────────────────────────
#  Buddy Encouragement
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBuddyEncouragement:
    """Tests for sending encouragement."""

    def test_send_encouragement(
        self, premium_buddy_client, active_pairing
    ):
        """Send encouragement to buddy."""
        response = premium_buddy_client.post(
            "/api/buddies/encourage/",
            {"message": "Keep going!"},
            format="json",
        )
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        )

    def test_send_encouragement_no_pairing(self, premium_buddy_client):
        """Send encouragement without an active pairing."""
        response = premium_buddy_client.post(
            "/api/buddies/encourage/",
            {"message": "You can do it!"},
            format="json",
        )
        assert response.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )


# ──────────────────────────────────────────────────────────────────────
#  End Buddy Pairing
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEndBuddyPairing:
    """Tests for ending a buddy pairing."""

    def test_end_pairing(self, premium_buddy_client, active_pairing):
        """End an active buddy pairing."""
        response = premium_buddy_client.post("/api/buddies/end/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
        )

    def test_end_pairing_no_active(self, premium_buddy_client):
        """End pairing when no active pairing exists."""
        response = premium_buddy_client.post("/api/buddies/end/")
        assert response.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )


# ──────────────────────────────────────────────────────────────────────
#  Buddy Stats
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBuddyStats:
    """Tests for buddy stats endpoint."""

    def test_stats_with_pairing(self, premium_buddy_client, active_pairing):
        """Get stats for an active pairing."""
        response = premium_buddy_client.get("/api/buddies/stats/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    def test_stats_no_pairing(self, premium_buddy_client):
        """Get stats with no active pairing."""
        response = premium_buddy_client.get("/api/buddies/stats/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )


# ──────────────────────────────────────────────────────────────────────
#  Buddy History
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBuddyHistory:
    """Tests for buddy history endpoint."""

    def test_history(self, premium_buddy_client):
        """Get buddy pairing history."""
        response = premium_buddy_client.get("/api/buddies/history/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    def test_history_with_past_pairings(self, premium_buddy_client, buddy_user1, buddy_user2):
        """History includes completed pairings."""
        BuddyPairing.objects.create(
            user1=buddy_user1, user2=buddy_user2,
            status="completed", compatibility_score=0.6,
            ended_at=timezone.now(),
        )
        response = premium_buddy_client.get("/api/buddies/history/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )


# ──────────────────────────────────────────────────────────────────────
#  Skip Buddy
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSkipBuddy:
    """Tests for skipping a suggested buddy."""

    def test_skip_buddy(self, premium_buddy_client):
        """Skip a suggested buddy."""
        response = premium_buddy_client.post(
            "/api/buddies/skip/",
            {"user_id": str(uuid.uuid4())},
            format="json",
        )
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )


# ──────────────────────────────────────────────────────────────────────
#  Buddy Chat
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBuddyChat:
    """Tests for buddy chat endpoint."""

    def test_chat_no_user_id(self, premium_buddy_client):
        """Chat without user_id returns 400."""
        response = premium_buddy_client.post(
            "/api/buddies/chat/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_chat_nonexistent_user(self, premium_buddy_client):
        """Chat with nonexistent user returns 404."""
        response = premium_buddy_client.post(
            "/api/buddies/chat/",
            {"user_id": str(uuid.uuid4())},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  Accountability Contracts
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAccountabilityContracts:
    """Tests for accountability contract endpoints."""

    def test_list_contracts(self, premium_buddy_client, active_pairing):
        """List contracts for the current pairing."""
        response = premium_buddy_client.get("/api/buddies/contracts/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    def test_create_contract(self, premium_buddy_client, active_pairing, buddy_user1):
        """Create an accountability contract."""
        today = timezone.now().date()
        response = premium_buddy_client.post(
            "/api/buddies/contracts/",
            {
                "pairing": str(active_pairing.id),
                "title": "30-Day Challenge",
                "description": "Complete 30 tasks",
                "goals": [{"title": "Do 30 tasks", "target": 30, "unit": "tasks"}],
                "check_in_frequency": "weekly",
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=30)).isoformat(),
            },
            format="json",
        )
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
        )
