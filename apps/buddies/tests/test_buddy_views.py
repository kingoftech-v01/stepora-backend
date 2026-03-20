"""
Tests for buddies views.

Covers:
- Find match, AI matches
- Pair, accept, reject
- Current buddy, progress
- Encourage
- History
- Contracts CRUD + check-in
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.buddies.models import (
    AccountabilityContract,
    BuddyEncouragement,
    BuddyPairing,
    ContractCheckIn,
)
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


# ── Helpers ──────────────────────────────────────────────────────────

def _make_premium_user(email, display_name="PremiumUser"):
    """Create a user with an active premium subscription."""
    user = User.objects.create_user(
        email=email,
        password="testpass123",
        display_name=display_name,
    )
    plan = SubscriptionPlan.objects.get(slug="premium")
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return user


def _make_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def user1(db):
    return _make_premium_user("buddy_u1@test.com", "BuddyUser1")


@pytest.fixture
def user2(db):
    return _make_premium_user("buddy_u2@test.com", "BuddyUser2")


@pytest.fixture
def user3(db):
    return _make_premium_user("buddy_u3@test.com", "BuddyUser3")


@pytest.fixture
def client1(user1):
    return _make_client(user1)


@pytest.fixture
def client2(user2):
    return _make_client(user2)


@pytest.fixture
def client3(user3):
    return _make_client(user3)


@pytest.fixture
def active_pairing(db, user1, user2):
    return BuddyPairing.objects.create(
        user1=user1,
        user2=user2,
        status="active",
        compatibility_score=0.75,
    )


@pytest.fixture
def pending_pairing(db, user1, user3):
    return BuddyPairing.objects.create(
        user1=user1,
        user2=user3,
        status="pending",
        compatibility_score=0.5,
        expires_at=timezone.now() + timedelta(days=7),
    )


# ── Current buddy ───────────────────────────────────────────────────

class TestCurrentBuddy:
    def test_current_no_buddy(self, client1):
        resp = client1.get("/api/v1/buddies/current/")
        assert resp.status_code == 200
        assert resp.data["buddy"] is None

    def test_current_with_buddy(self, client1, active_pairing):
        resp = client1.get("/api/v1/buddies/current/")
        assert resp.status_code == 200
        assert resp.data["buddy"] is not None
        assert resp.data["buddy"]["status"] == "active"

    def test_current_as_user2(self, client2, active_pairing):
        resp = client2.get("/api/v1/buddies/current/")
        assert resp.status_code == 200
        assert resp.data["buddy"] is not None


# ── Find match ───────────────────────────────────────────────────────

class TestFindMatch:
    def test_find_match_success(self, client1, user2):
        resp = client1.post("/api/v1/buddies/find-match/")
        assert resp.status_code == 200
        # May or may not find a match depending on candidates
        assert "match" in resp.data

    def test_find_match_already_paired(self, client1, active_pairing):
        resp = client1.post("/api/v1/buddies/find-match/")
        assert resp.status_code == 400
        assert "already" in resp.data["error"].lower()


# ── AI matches ───────────────────────────────────────────────────────

class TestAIMatches:
    def test_ai_matches_already_paired(self, client1, active_pairing):
        resp = client1.get("/api/v1/buddies/ai-matches/")
        assert resp.status_code == 400

    def test_ai_matches_no_candidates(self, db):
        # Single premium user, no candidates available
        user = _make_premium_user("solo_ai@test.com", "SoloAI")
        # Need AI permission too - premium plan has has_ai=True
        c = _make_client(user)
        resp = c.get("/api/v1/buddies/ai-matches/")
        # 200 with empty results or 403 if plan lacks has_ai
        assert resp.status_code in (200, 403)


# ── Pair ─────────────────────────────────────────────────────────────

class TestPair:
    def test_pair_success(self, client1, user2):
        resp = client1.post("/api/v1/buddies/pair/", {"partner_id": str(user2.id)})
        assert resp.status_code == 201
        assert "pairing_id" in resp.data

    def test_pair_self(self, client1, user1):
        resp = client1.post("/api/v1/buddies/pair/", {"partner_id": str(user1.id)})
        assert resp.status_code == 400

    def test_pair_already_active(self, client1, user3, active_pairing):
        resp = client1.post("/api/v1/buddies/pair/", {"partner_id": str(user3.id)})
        assert resp.status_code == 400

    def test_pair_partner_not_found(self, client1):
        import uuid
        resp = client1.post("/api/v1/buddies/pair/", {"partner_id": str(uuid.uuid4())})
        assert resp.status_code == 404

    def test_pair_partner_already_paired(self, client3, user1, user2, active_pairing):
        # user2 already paired with user1
        resp = client3.post("/api/v1/buddies/pair/", {"partner_id": str(user2.id)})
        assert resp.status_code == 400


# ── Accept / Reject ──────────────────────────────────────────────────

class TestAcceptReject:
    def test_accept(self, client3, pending_pairing):
        resp = client3.post(f"/api/v1/buddies/{pending_pairing.id}/accept/")
        assert resp.status_code == 200
        pending_pairing.refresh_from_db()
        assert pending_pairing.status == "active"

    def test_accept_not_user2(self, client1, pending_pairing):
        # user1 is user1, not user2 — should not be able to accept
        resp = client1.post(f"/api/v1/buddies/{pending_pairing.id}/accept/")
        assert resp.status_code == 404

    def test_reject(self, client3, pending_pairing):
        resp = client3.post(f"/api/v1/buddies/{pending_pairing.id}/reject/")
        assert resp.status_code == 200
        pending_pairing.refresh_from_db()
        assert pending_pairing.status == "cancelled"

    def test_reject_not_user2(self, client1, pending_pairing):
        resp = client1.post(f"/api/v1/buddies/{pending_pairing.id}/reject/")
        assert resp.status_code == 404


# ── Progress ─────────────────────────────────────────────────────────

class TestProgress:
    def test_progress_success(self, client1, active_pairing):
        resp = client1.get(f"/api/v1/buddies/{active_pairing.id}/progress/")
        assert resp.status_code == 200
        assert "progress" in resp.data
        assert "user" in resp.data["progress"]
        assert "partner" in resp.data["progress"]

    def test_progress_not_in_pairing(self, client3, active_pairing):
        resp = client3.get(f"/api/v1/buddies/{active_pairing.id}/progress/")
        assert resp.status_code == 403

    def test_progress_not_found(self, client1):
        import uuid
        resp = client1.get(f"/api/v1/buddies/{uuid.uuid4()}/progress/")
        assert resp.status_code == 404


# ── Encourage ────────────────────────────────────────────────────────

class TestEncourage:
    def test_encourage_success(self, client1, active_pairing):
        resp = client1.post(
            f"/api/v1/buddies/{active_pairing.id}/encourage/",
            {"message": "Keep going!"},
        )
        assert resp.status_code == 200
        assert "encouragement_streak" in resp.data
        assert BuddyEncouragement.objects.filter(pairing=active_pairing).count() == 1

    def test_encourage_empty_message(self, client1, active_pairing):
        resp = client1.post(
            f"/api/v1/buddies/{active_pairing.id}/encourage/",
            {},
        )
        assert resp.status_code == 200

    def test_encourage_not_in_pairing(self, client3, active_pairing):
        resp = client3.post(
            f"/api/v1/buddies/{active_pairing.id}/encourage/",
            {"message": "Hey"},
        )
        assert resp.status_code == 403

    def test_encourage_not_found(self, client1):
        import uuid
        resp = client1.post(
            f"/api/v1/buddies/{uuid.uuid4()}/encourage/",
            {"message": "Hey"},
        )
        assert resp.status_code == 404

    def test_encourage_streak_increments(self, client1, active_pairing):
        # First encouragement
        client1.post(
            f"/api/v1/buddies/{active_pairing.id}/encourage/",
            {"message": "Day 1"},
        )
        active_pairing.refresh_from_db()
        assert active_pairing.encouragement_streak == 1


# ── Destroy (end pairing) ───────────────────────────────────────────

class TestDestroyPairing:
    def test_destroy_success(self, client1, active_pairing):
        resp = client1.delete(f"/api/v1/buddies/{active_pairing.id}/")
        assert resp.status_code == 200
        active_pairing.refresh_from_db()
        assert active_pairing.status == "cancelled"

    def test_destroy_not_in_pairing(self, client3, active_pairing):
        resp = client3.delete(f"/api/v1/buddies/{active_pairing.id}/")
        assert resp.status_code == 403


# ── History ──────────────────────────────────────────────────────────

class TestHistory:
    def test_history_empty(self, client1):
        resp = client1.get("/api/v1/buddies/history/")
        assert resp.status_code == 200
        assert resp.data["pairings"] == []

    def test_history_with_pairings(self, client1, active_pairing):
        resp = client1.get("/api/v1/buddies/history/")
        assert resp.status_code == 200
        assert len(resp.data["pairings"]) == 1


# ── Contracts ────────────────────────────────────────────────────────

@pytest.fixture
def contract_data(active_pairing):
    return {
        "pairing_id": str(active_pairing.id),
        "title": "Daily Exercise",
        "description": "30 min exercise daily",
        "goals": [{"title": "Exercise", "target": 30, "unit": "minutes"}],
        "check_in_frequency": "daily",
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=30)),
    }


class TestContractList:
    def test_list_empty(self, client1):
        resp = client1.get("/api/v1/buddies/contracts/")
        assert resp.status_code == 200
        assert resp.data["contracts"] == []


class TestContractCreate:
    def test_create_success(self, client1, contract_data):
        resp = client1.post("/api/v1/buddies/contracts/", contract_data, format="json")
        assert resp.status_code == 201
        assert "contract" in resp.data

    def test_create_not_in_pairing(self, client3, contract_data):
        resp = client3.post("/api/v1/buddies/contracts/", contract_data, format="json")
        # user3 is not part of active_pairing (user1, user2)
        assert resp.status_code in (403, 404)


class TestContractAccept:
    def test_accept_success(self, client2, client1, contract_data):
        # user1 creates, user2 accepts
        create_resp = client1.post("/api/v1/buddies/contracts/", contract_data, format="json")
        contract_id = create_resp.data["contract"]["id"]
        resp = client2.post(f"/api/v1/buddies/contracts/{contract_id}/accept/")
        assert resp.status_code == 200

    def test_accept_by_creator_fails(self, client1, contract_data):
        create_resp = client1.post("/api/v1/buddies/contracts/", contract_data, format="json")
        contract_id = create_resp.data["contract"]["id"]
        resp = client1.post(f"/api/v1/buddies/contracts/{contract_id}/accept/")
        assert resp.status_code == 400


class TestContractCheckIn:
    def test_checkin_success(self, client1, contract_data):
        create_resp = client1.post("/api/v1/buddies/contracts/", contract_data, format="json")
        contract_id = create_resp.data["contract"]["id"]
        resp = client1.post(
            f"/api/v1/buddies/contracts/{contract_id}/check-in/",
            {"progress": {"0": 30}, "note": "Good session", "mood": "happy"},
            format="json",
        )
        assert resp.status_code == 201

    def test_checkin_not_in_pairing(self, client3, client1, contract_data):
        create_resp = client1.post("/api/v1/buddies/contracts/", contract_data, format="json")
        contract_id = create_resp.data["contract"]["id"]
        resp = client3.post(
            f"/api/v1/buddies/contracts/{contract_id}/check-in/",
            {"progress": {"0": 10}},
            format="json",
        )
        assert resp.status_code == 403


class TestContractProgress:
    def test_progress_success(self, client1, contract_data):
        create_resp = client1.post("/api/v1/buddies/contracts/", contract_data, format="json")
        contract_id = create_resp.data["contract"]["id"]
        # Submit a check-in first
        client1.post(
            f"/api/v1/buddies/contracts/{contract_id}/check-in/",
            {"progress": {"0": 30}, "note": "Done"},
            format="json",
        )
        resp = client1.get(f"/api/v1/buddies/contracts/{contract_id}/progress/")
        assert resp.status_code == 200
        assert "contract" in resp.data
        assert "user_check_ins" in resp.data

    def test_progress_not_in_pairing(self, client3, client1, contract_data):
        create_resp = client1.post("/api/v1/buddies/contracts/", contract_data, format="json")
        contract_id = create_resp.data["contract"]["id"]
        resp = client3.get(f"/api/v1/buddies/contracts/{contract_id}/progress/")
        assert resp.status_code == 403


# ── Permission check ─────────────────────────────────────────────────

class TestBuddyPermissions:
    def test_unauthenticated(self, db):
        client = APIClient()
        resp = client.get("/api/v1/buddies/current/")
        assert resp.status_code == 401

    def test_free_user_denied(self, db):
        user = User.objects.create_user(
            email="free_buddy@test.com",
            password="testpass123",
            display_name="FreeBuddy",
        )
        # Ensure free plan exists and is assigned
        plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="free",
            defaults={
                "name": "Free",
                "price_monthly": Decimal("0.00"),
                "has_buddy": False,
            },
        )
        Subscription.objects.update_or_create(
            user=user,
            defaults={"plan": plan, "status": "active"},
        )
        client = _make_client(user)
        resp = client.get("/api/v1/buddies/current/")
        assert resp.status_code == 403
