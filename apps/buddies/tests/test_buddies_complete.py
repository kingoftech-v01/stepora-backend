"""
Comprehensive tests for the Buddies app.

Coverage targets:
- BuddyPairing: create, accept, reject, end, history
- BuddyEncouragement: send, list
- AccountabilityContract: create, accept, check-in, progress
- BuddyMatchingService: compatibility scoring, exclude blocked/skipped/paired
- Suggestions: list, accept, skip (frontend endpoint stubs)
- AI buddy matching
- IDOR protection
- Target: 95%+

NOTE: The frontend defines SUGGESTIONS, ACCEPT_SUGGESTION, SKIP_SUGGESTION
endpoints but the backend has no corresponding view actions. These are documented
as feature gaps at the bottom of the file.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

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
from apps.buddies.services import BuddyMatchingService
from apps.dreams.models import Dream
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User

# ════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════


def _make_premium_user(email, display_name="PremiumUser", **kwargs):
    """Create a user with an active premium subscription."""
    user = User.objects.create_user(
        email=email,
        password="testpass123",
        display_name=display_name,
        timezone=kwargs.pop("timezone", "Europe/Paris"),
        **kwargs,
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


def _make_free_user(email, display_name="FreeUser"):
    """Create a user with a free plan (no buddy access)."""
    user = User.objects.create_user(
        email=email,
        password="testpass123",
        display_name=display_name,
    )
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="free",
        defaults={"name": "Free", "price_monthly": Decimal("0.00"), "has_buddy": False},
    )
    Subscription.objects.update_or_create(
        user=user,
        defaults={"plan": plan, "status": "active"},
    )
    return user


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ════════════════════════════════════════════════════════════════════
#  Fixtures
# ════════════════════════════════════════════════════════════════════


@pytest.fixture
def u1(db):
    return _make_premium_user("complete_u1@test.com", "User1")


@pytest.fixture
def u2(db):
    return _make_premium_user("complete_u2@test.com", "User2")


@pytest.fixture
def u3(db):
    return _make_premium_user("complete_u3@test.com", "User3")


@pytest.fixture
def c1(u1):
    return _client(u1)


@pytest.fixture
def c2(u2):
    return _client(u2)


@pytest.fixture
def c3(u3):
    return _client(u3)


@pytest.fixture
def active_pair(u1, u2):
    return BuddyPairing.objects.create(
        user1=u1, user2=u2, status="active", compatibility_score=0.75
    )


@pytest.fixture
def pending_pair(u1, u3):
    return BuddyPairing.objects.create(
        user1=u1,
        user2=u3,
        status="pending",
        compatibility_score=0.5,
        expires_at=timezone.now() + timedelta(days=7),
    )


@pytest.fixture
def contract_payload(active_pair):
    today = date.today()
    return {
        "pairing_id": str(active_pair.id),
        "title": "30-Day Fitness",
        "description": "Exercise every day",
        "goals": [{"title": "Run 5K", "target": 30, "unit": "minutes"}],
        "check_in_frequency": "daily",
        "start_date": str(today),
        "end_date": str(today + timedelta(days=30)),
    }


# ════════════════════════════════════════════════════════════════════
#  1. BuddyPairing — create, accept, reject, end, history
# ════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBuddyPairingLifecycle:
    """Full lifecycle tests for buddy pairings."""

    # -- Create (pair) --

    def test_pair_creates_pending(self, c1, u2):
        resp = c1.post("/api/v1/buddies/pair/", {"partner_id": str(u2.id)})
        assert resp.status_code == status.HTTP_201_CREATED
        assert "pairing_id" in resp.data
        pairing = BuddyPairing.objects.get(id=resp.data["pairing_id"])
        assert pairing.status == "pending"
        assert pairing.user1 == u2 or pairing.user2 == u2

    def test_pair_self_rejected(self, c1, u1):
        resp = c1.post("/api/v1/buddies/pair/", {"partner_id": str(u1.id)})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_pair_nonexistent_user(self, c1):
        resp = c1.post("/api/v1/buddies/pair/", {"partner_id": str(uuid.uuid4())})
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_pair_already_active_blocked(self, c1, u3, active_pair):
        resp = c1.post("/api/v1/buddies/pair/", {"partner_id": str(u3.id)})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_pair_partner_already_paired(self, c3, u2, active_pair):
        resp = c3.post("/api/v1/buddies/pair/", {"partner_id": str(u2.id)})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_pair_missing_partner_id(self, c1):
        resp = c1.post("/api/v1/buddies/pair/", {})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # -- Accept --

    def test_accept_by_user2(self, c3, pending_pair):
        """user2 (u3) can accept a pending pairing."""
        resp = c3.post(f"/api/v1/buddies/{pending_pair.id}/accept/")
        assert resp.status_code == status.HTTP_200_OK
        pending_pair.refresh_from_db()
        assert pending_pair.status == "active"

    def test_accept_by_user1_rejected(self, c1, pending_pair):
        """user1 (creator) cannot accept their own request."""
        resp = c1.post(f"/api/v1/buddies/{pending_pair.id}/accept/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_accept_nonexistent(self, c1):
        resp = c1.post(f"/api/v1/buddies/{uuid.uuid4()}/accept/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_accept_already_active(self, c3, pending_pair):
        """Cannot accept a pairing twice."""
        c3.post(f"/api/v1/buddies/{pending_pair.id}/accept/")
        resp = c3.post(f"/api/v1/buddies/{pending_pair.id}/accept/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND  # no longer pending

    # -- Reject --

    def test_reject_by_user2(self, c3, pending_pair):
        resp = c3.post(f"/api/v1/buddies/{pending_pair.id}/reject/")
        assert resp.status_code == status.HTTP_200_OK
        pending_pair.refresh_from_db()
        assert pending_pair.status == "cancelled"
        assert pending_pair.ended_at is not None

    def test_reject_by_user1_rejected(self, c1, pending_pair):
        resp = c1.post(f"/api/v1/buddies/{pending_pair.id}/reject/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_reject_nonexistent(self, c3):
        resp = c3.post(f"/api/v1/buddies/{uuid.uuid4()}/reject/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    # -- End (destroy) --

    def test_end_active_pairing(self, c1, active_pair):
        resp = c1.delete(f"/api/v1/buddies/{active_pair.id}/")
        assert resp.status_code == status.HTTP_200_OK
        active_pair.refresh_from_db()
        assert active_pair.status == "cancelled"
        assert active_pair.ended_at is not None

    def test_end_as_user2(self, c2, active_pair):
        resp = c2.delete(f"/api/v1/buddies/{active_pair.id}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_end_not_in_pairing(self, c3, active_pair):
        resp = c3.delete(f"/api/v1/buddies/{active_pair.id}/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_end_nonexistent(self, c1):
        resp = c1.delete(f"/api/v1/buddies/{uuid.uuid4()}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    # -- History --

    def test_history_empty(self, c1):
        resp = c1.get("/api/v1/buddies/history/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["pairings"] == []

    def test_history_includes_all_statuses(self, c1, active_pair, pending_pair):
        resp = c1.get("/api/v1/buddies/history/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["pairings"]) == 2

    def test_history_partner_info(self, c1, active_pair, u2):
        resp = c1.get("/api/v1/buddies/history/")
        pairing = resp.data["pairings"][0]
        assert pairing["partner"]["id"] == str(u2.id)
        assert "username" in pairing["partner"]
        assert "encouragement_count" in pairing

    def test_history_as_user2(self, c2, active_pair):
        resp = c2.get("/api/v1/buddies/history/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["pairings"]) == 1


# ════════════════════════════════════════════════════════════════════
#  2. BuddyEncouragement — send, list, streak
# ════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBuddyEncouragement:
    """Tests for encouragement sending and streak tracking."""

    def test_send_encouragement_with_message(self, c1, active_pair):
        resp = c1.post(
            f"/api/v1/buddies/{active_pair.id}/encourage/",
            {"message": "Keep going!"},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "encouragement_streak" in resp.data
        assert BuddyEncouragement.objects.filter(pairing=active_pair).count() == 1

    def test_send_encouragement_empty_message(self, c1, active_pair):
        resp = c1.post(f"/api/v1/buddies/{active_pair.id}/encourage/", {})
        assert resp.status_code == status.HTTP_200_OK

    def test_encouragement_from_user2(self, c2, active_pair):
        resp = c2.post(
            f"/api/v1/buddies/{active_pair.id}/encourage/",
            {"message": "You rock!"},
        )
        assert resp.status_code == status.HTTP_200_OK
        enc = BuddyEncouragement.objects.get(pairing=active_pair)
        assert enc.sender == active_pair.user2

    def test_encouragement_not_in_pairing(self, c3, active_pair):
        resp = c3.post(
            f"/api/v1/buddies/{active_pair.id}/encourage/",
            {"message": "Hi"},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_encouragement_not_found(self, c1):
        resp = c1.post(
            f"/api/v1/buddies/{uuid.uuid4()}/encourage/",
            {"message": "Hi"},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_encouragement_streak_first_msg(self, c1, active_pair):
        c1.post(
            f"/api/v1/buddies/{active_pair.id}/encourage/",
            {"message": "Day 1"},
        )
        active_pair.refresh_from_db()
        assert active_pair.encouragement_streak == 1
        assert active_pair.best_encouragement_streak == 1
        assert active_pair.last_encouragement_at is not None

    def test_encouragement_streak_same_day_no_increment(self, c1, active_pair):
        """Two encouragements on the same day should not increment streak."""
        c1.post(
            f"/api/v1/buddies/{active_pair.id}/encourage/",
            {"message": "Msg 1"},
        )
        c1.post(
            f"/api/v1/buddies/{active_pair.id}/encourage/",
            {"message": "Msg 2"},
        )
        active_pair.refresh_from_db()
        # Streak stays 1 since same day (days_since == 0 and it's already at 1)
        assert active_pair.encouragement_streak == 1

    def test_encouragement_list_in_history(self, c1, active_pair, u1):
        """History endpoint includes encouragement count."""
        BuddyEncouragement.objects.create(
            pairing=active_pair, sender=u1, message="Test"
        )
        BuddyEncouragement.objects.create(
            pairing=active_pair, sender=u1, message="Test 2"
        )
        resp = c1.get("/api/v1/buddies/history/")
        pairing_data = resp.data["pairings"][0]
        assert pairing_data["encouragement_count"] == 2


# ════════════════════════════════════════════════════════════════════
#  3. AccountabilityContract — create, accept, check-in, progress
# ════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAccountabilityContractCreate:
    """Tests for creating accountability contracts."""

    def test_create_success(self, c1, contract_payload):
        resp = c1.post("/api/v1/buddies/contracts/", contract_payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert "contract" in resp.data
        assert resp.data["contract"]["title"] == "30-Day Fitness"

    def test_create_not_in_pairing(self, c3, contract_payload):
        resp = c3.post("/api/v1/buddies/contracts/", contract_payload, format="json")
        assert resp.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    def test_create_invalid_dates(self, c1, active_pair):
        today = date.today()
        payload = {
            "pairing_id": str(active_pair.id),
            "title": "Bad dates",
            "goals": [{"title": "G", "target": 1, "unit": "tasks"}],
            "check_in_frequency": "weekly",
            "start_date": str(today),
            "end_date": str(today - timedelta(days=1)),  # end before start
        }
        resp = c1.post("/api/v1/buddies/contracts/", payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_no_goals(self, c1, active_pair):
        today = date.today()
        payload = {
            "pairing_id": str(active_pair.id),
            "title": "No goals",
            "goals": [],
            "check_in_frequency": "weekly",
            "start_date": str(today),
            "end_date": str(today + timedelta(days=30)),
        }
        resp = c1.post("/api/v1/buddies/contracts/", payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_too_many_goals(self, c1, active_pair):
        today = date.today()
        payload = {
            "pairing_id": str(active_pair.id),
            "title": "Many goals",
            "goals": [
                {"title": f"G{i}", "target": i + 1, "unit": "tasks"} for i in range(11)
            ],
            "check_in_frequency": "weekly",
            "start_date": str(today),
            "end_date": str(today + timedelta(days=30)),
        }
        resp = c1.post("/api/v1/buddies/contracts/", payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_nonexistent_pairing(self, c1):
        today = date.today()
        payload = {
            "pairing_id": str(uuid.uuid4()),
            "title": "Ghost pairing",
            "goals": [{"title": "G", "target": 1, "unit": "tasks"}],
            "check_in_frequency": "weekly",
            "start_date": str(today),
            "end_date": str(today + timedelta(days=30)),
        }
        resp = c1.post("/api/v1/buddies/contracts/", payload, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAccountabilityContractAccept:
    """Tests for accepting contracts."""

    def test_accept_success(self, c2, c1, contract_payload):
        create_resp = c1.post(
            "/api/v1/buddies/contracts/", contract_payload, format="json"
        )
        cid = create_resp.data["contract"]["id"]
        resp = c2.post(f"/api/v1/buddies/contracts/{cid}/accept/")
        assert resp.status_code == status.HTTP_200_OK
        contract = AccountabilityContract.objects.get(id=cid)
        assert contract.accepted_by_partner is True

    def test_accept_by_creator_fails(self, c1, contract_payload):
        create_resp = c1.post(
            "/api/v1/buddies/contracts/", contract_payload, format="json"
        )
        cid = create_resp.data["contract"]["id"]
        resp = c1.post(f"/api/v1/buddies/contracts/{cid}/accept/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_accept_already_accepted(self, c2, c1, contract_payload):
        create_resp = c1.post(
            "/api/v1/buddies/contracts/", contract_payload, format="json"
        )
        cid = create_resp.data["contract"]["id"]
        c2.post(f"/api/v1/buddies/contracts/{cid}/accept/")
        resp = c2.post(f"/api/v1/buddies/contracts/{cid}/accept/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_accept_not_in_pairing(self, c3, c1, contract_payload):
        create_resp = c1.post(
            "/api/v1/buddies/contracts/", contract_payload, format="json"
        )
        cid = create_resp.data["contract"]["id"]
        resp = c3.post(f"/api/v1/buddies/contracts/{cid}/accept/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_accept_nonexistent(self, c1):
        resp = c1.post(f"/api/v1/buddies/contracts/{uuid.uuid4()}/accept/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAccountabilityContractCheckIn:
    """Tests for contract check-ins."""

    def _create_contract(self, c1, contract_payload):
        resp = c1.post("/api/v1/buddies/contracts/", contract_payload, format="json")
        return resp.data["contract"]["id"]

    def test_checkin_success(self, c1, contract_payload):
        cid = self._create_contract(c1, contract_payload)
        resp = c1.post(
            f"/api/v1/buddies/contracts/{cid}/check-in/",
            {"progress": {"0": 30}, "note": "Great run", "mood": "good"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert "check_in" in resp.data

    def test_checkin_by_partner(self, c2, c1, contract_payload):
        cid = self._create_contract(c1, contract_payload)
        resp = c2.post(
            f"/api/v1/buddies/contracts/{cid}/check-in/",
            {"progress": {"0": 15}},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_checkin_not_in_pairing(self, c3, c1, contract_payload):
        cid = self._create_contract(c1, contract_payload)
        resp = c3.post(
            f"/api/v1/buddies/contracts/{cid}/check-in/",
            {"progress": {"0": 10}},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_checkin_nonexistent_contract(self, c1):
        resp = c1.post(
            f"/api/v1/buddies/contracts/{uuid.uuid4()}/check-in/",
            {"progress": {"0": 10}},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_checkin_empty_progress(self, c1, contract_payload):
        cid = self._create_contract(c1, contract_payload)
        resp = c1.post(
            f"/api/v1/buddies/contracts/{cid}/check-in/",
            {"progress": {}},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_multiple_checkins(self, c1, c2, contract_payload):
        cid = self._create_contract(c1, contract_payload)
        c1.post(
            f"/api/v1/buddies/contracts/{cid}/check-in/",
            {"progress": {"0": 20}},
            format="json",
        )
        c2.post(
            f"/api/v1/buddies/contracts/{cid}/check-in/",
            {"progress": {"0": 30}},
            format="json",
        )
        assert ContractCheckIn.objects.filter(contract_id=cid).count() == 2


@pytest.mark.django_db
class TestAccountabilityContractProgress:
    """Tests for viewing contract progress."""

    def _create_contract(self, c1, contract_payload):
        resp = c1.post("/api/v1/buddies/contracts/", contract_payload, format="json")
        return resp.data["contract"]["id"]

    def test_progress_with_checkins(self, c1, c2, contract_payload):
        cid = self._create_contract(c1, contract_payload)
        c1.post(
            f"/api/v1/buddies/contracts/{cid}/check-in/",
            {"progress": {"0": 20}},
            format="json",
        )
        c2.post(
            f"/api/v1/buddies/contracts/{cid}/check-in/",
            {"progress": {"0": 15}},
            format="json",
        )
        resp = c1.get(f"/api/v1/buddies/contracts/{cid}/progress/")
        assert resp.status_code == status.HTTP_200_OK
        assert "contract" in resp.data
        assert "user_check_ins" in resp.data
        assert "partner_check_ins" in resp.data
        assert "user_totals" in resp.data
        assert "partner_totals" in resp.data

    def test_progress_not_in_pairing(self, c3, c1, contract_payload):
        cid = self._create_contract(c1, contract_payload)
        resp = c3.get(f"/api/v1/buddies/contracts/{cid}/progress/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_progress_nonexistent(self, c1):
        resp = c1.get(f"/api/v1/buddies/contracts/{uuid.uuid4()}/progress/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_progress_totals_aggregate(self, c1, c2, contract_payload):
        cid = self._create_contract(c1, contract_payload)
        c1.post(
            f"/api/v1/buddies/contracts/{cid}/check-in/",
            {"progress": {"0": 10}},
            format="json",
        )
        c1.post(
            f"/api/v1/buddies/contracts/{cid}/check-in/",
            {"progress": {"0": 20}},
            format="json",
        )
        resp = c1.get(f"/api/v1/buddies/contracts/{cid}/progress/")
        # user totals for goal 0 should be 10 + 20 = 30
        assert float(resp.data["user_totals"]["0"]) == 30.0


@pytest.mark.django_db
class TestContractList:
    """Tests for listing contracts."""

    def test_list_empty(self, c1):
        resp = c1.get("/api/v1/buddies/contracts/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["contracts"] == []

    def test_list_with_contracts(self, c1, contract_payload):
        c1.post("/api/v1/buddies/contracts/", contract_payload, format="json")
        resp = c1.get("/api/v1/buddies/contracts/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["contracts"]) == 1

    def test_list_filter_by_status(self, c1, contract_payload):
        c1.post("/api/v1/buddies/contracts/", contract_payload, format="json")
        # Default filter is active
        resp = c1.get("/api/v1/buddies/contracts/?status=completed")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["contracts"]) == 0

    def test_list_all_statuses(self, c1, contract_payload):
        c1.post("/api/v1/buddies/contracts/", contract_payload, format="json")
        resp = c1.get("/api/v1/buddies/contracts/?status=all")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["contracts"]) == 1


# ════════════════════════════════════════════════════════════════════
#  4. BuddyMatchingService — compatibility scoring, exclusions
# ════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBuddyMatchingServiceScoring:
    """Tests for the matching service scoring algorithms."""

    @pytest.fixture
    def svc(self):
        return BuddyMatchingService()

    # -- Weights --

    def test_weights_sum_to_one(self, svc):
        total = (
            svc.CATEGORY_WEIGHT
            + svc.ACTIVITY_WEIGHT
            + svc.TIMEZONE_WEIGHT
            + svc.LEVEL_WEIGHT
        )
        assert abs(total - 1.0) < 0.001

    def test_min_compatibility_score(self, svc):
        assert svc.MIN_COMPATIBILITY_SCORE == 0.3

    # -- Activity similarity --

    def test_activity_same_streak(self, svc):
        assert (
            svc._calculate_activity_similarity(
                MagicMock(streak_days=10), MagicMock(streak_days=10)
            )
            == 1.0
        )

    def test_activity_diff_2(self, svc):
        assert (
            svc._calculate_activity_similarity(
                MagicMock(streak_days=5), MagicMock(streak_days=7)
            )
            == 0.8
        )

    def test_activity_diff_6(self, svc):
        assert (
            svc._calculate_activity_similarity(
                MagicMock(streak_days=1), MagicMock(streak_days=7)
            )
            == 0.6
        )

    def test_activity_diff_12(self, svc):
        assert (
            svc._calculate_activity_similarity(
                MagicMock(streak_days=0), MagicMock(streak_days=12)
            )
            == 0.4
        )

    def test_activity_diff_25(self, svc):
        assert (
            svc._calculate_activity_similarity(
                MagicMock(streak_days=0), MagicMock(streak_days=25)
            )
            == 0.2
        )

    def test_activity_diff_large(self, svc):
        assert (
            svc._calculate_activity_similarity(
                MagicMock(streak_days=0), MagicMock(streak_days=100)
            )
            == 0.1
        )

    # -- Timezone proximity --

    def test_tz_same(self, svc):
        assert (
            svc._calculate_timezone_proximity(
                MagicMock(timezone="Europe/Paris"), MagicMock(timezone="Europe/Paris")
            )
            == 1.0
        )

    def test_tz_same_region(self, svc):
        assert (
            svc._calculate_timezone_proximity(
                MagicMock(timezone="Europe/Paris"), MagicMock(timezone="Europe/London")
            )
            == 0.7
        )

    def test_tz_different_region(self, svc):
        assert (
            svc._calculate_timezone_proximity(
                MagicMock(timezone="Europe/Paris"),
                MagicMock(timezone="America/New_York"),
            )
            == 0.3
        )

    def test_tz_null(self, svc):
        assert (
            svc._calculate_timezone_proximity(
                MagicMock(timezone=None), MagicMock(timezone=None)
            )
            == 1.0
        )

    # -- Level similarity --

    def test_level_same(self, svc):
        assert (
            svc._calculate_level_similarity(MagicMock(level=5), MagicMock(level=5))
            == 1.0
        )

    def test_level_diff_2(self, svc):
        assert (
            svc._calculate_level_similarity(MagicMock(level=5), MagicMock(level=7))
            == 0.8
        )

    def test_level_diff_4(self, svc):
        assert (
            svc._calculate_level_similarity(MagicMock(level=5), MagicMock(level=9))
            == 0.6
        )

    def test_level_diff_8(self, svc):
        assert (
            svc._calculate_level_similarity(MagicMock(level=2), MagicMock(level=10))
            == 0.4
        )

    def test_level_diff_20(self, svc):
        assert (
            svc._calculate_level_similarity(MagicMock(level=1), MagicMock(level=21))
            == 0.2
        )

    # -- Category matching --

    def test_get_user_categories(self, svc, u1):
        Dream.objects.create(
            user=u1, title="D1", description="d", category="health", status="active"
        )
        Dream.objects.create(
            user=u1, title="D2", description="d", category="career", status="active"
        )
        Dream.objects.create(
            user=u1, title="D3", description="d", category="health", status="completed"
        )
        cats = svc._get_user_categories(u1)
        assert cats == {"health", "career"}

    def test_get_user_categories_excludes_blank(self, svc, u1):
        Dream.objects.create(
            user=u1, title="D", description="d", category="", status="active"
        )
        assert svc._get_user_categories(u1) == set()

    # -- Full compatibility --

    def test_perfect_compatibility(self, svc, u1, u2):
        for u in (u1, u2):
            Dream.objects.create(
                user=u, title="D", description="d", category="health", status="active"
            )
            u.streak_days = 10
            u.level = 5
            u.timezone = "Europe/Paris"
            u.last_activity = timezone.now()
            u.save()
        score, shared = svc._calculate_compatibility(u1, u2)
        assert abs(score - 1.0) < 0.001
        assert "health" in shared


@pytest.mark.django_db
class TestBuddyMatchingServiceExclusions:
    """Tests for candidate exclusion logic."""

    def _make_eligible(self, email, display_name="Eligible"):
        u = _make_premium_user(email, display_name)
        u.last_activity = timezone.now()
        u.save(update_fields=["last_activity"])
        Dream.objects.create(
            user=u, title="D", description="d", category="health", status="active"
        )
        return u

    def test_excludes_self(self, u1):
        self._make_eligible("elig1@test.com")
        u1.last_activity = timezone.now()
        u1.save(update_fields=["last_activity"])
        Dream.objects.create(user=u1, title="D", description="d", status="active")
        svc = BuddyMatchingService()
        candidates = svc._get_eligible_candidates(u1)
        assert u1 not in candidates

    def test_excludes_active_paired(self, u1, u2, active_pair):
        svc = BuddyMatchingService()
        candidates = svc._get_eligible_candidates(u1)
        assert u2 not in candidates

    def test_excludes_pending_paired(self, u1, u3, pending_pair):
        svc = BuddyMatchingService()
        candidates = svc._get_eligible_candidates(u1)
        assert u3 not in candidates

    def test_includes_completed_paired(self, u1, u2):
        BuddyPairing.objects.create(
            user1=u1, user2=u2, status="completed", compatibility_score=0.5
        )
        u2.last_activity = timezone.now()
        u2.save(update_fields=["last_activity"])
        Dream.objects.create(user=u2, title="D", description="d", status="active")
        svc = BuddyMatchingService()
        candidates = svc._get_eligible_candidates(u1)
        assert u2 in candidates

    def test_excludes_inactive_users(self, u1):
        old = _make_premium_user("old@test.com", "OldUser")
        old.last_activity = timezone.now() - timedelta(days=60)
        old.save(update_fields=["last_activity"])
        Dream.objects.create(user=old, title="D", description="d", status="active")
        svc = BuddyMatchingService()
        candidates = svc._get_eligible_candidates(u1)
        assert old not in candidates

    def test_excludes_users_without_active_dreams(self, u1):
        no_dreams = _make_premium_user("nodream@test.com", "NoDream")
        no_dreams.last_activity = timezone.now()
        no_dreams.save(update_fields=["last_activity"])
        Dream.objects.create(
            user=no_dreams, title="D", description="d", status="paused"
        )
        svc = BuddyMatchingService()
        candidates = svc._get_eligible_candidates(u1)
        assert no_dreams not in candidates

    def test_find_compatible_no_candidates(self, u1):
        svc = BuddyMatchingService()
        result = svc.find_compatible_buddy(u1)
        assert result is None

    def test_find_compatible_returns_best(self, u1, u2, u3):
        for u in (u1, u2, u3):
            u.last_activity = timezone.now()
            u.streak_days = 5
            u.level = 3
            u.save()
        Dream.objects.create(
            user=u1, title="D", description="d", category="health", status="active"
        )
        Dream.objects.create(
            user=u2, title="D", description="d", category="health", status="active"
        )
        Dream.objects.create(
            user=u3, title="D", description="d", category="career", status="active"
        )
        svc = BuddyMatchingService()
        result = svc.find_compatible_buddy(u1)
        assert result is not None
        matched_user, score, shared = result
        assert matched_user == u2
        assert "health" in shared

    def test_below_min_score_returns_none(self, u1):
        far = _make_premium_user("far@test.com", "FarUser", timezone="Pacific/Auckland")
        far.last_activity = timezone.now()
        far.streak_days = 100
        far.level = 50
        far.save()
        Dream.objects.create(
            user=far, title="D", description="d", category="finance", status="active"
        )
        Dream.objects.create(
            user=u1, title="D", description="d", category="health", status="active"
        )
        u1.streak_days = 0
        u1.level = 1
        u1.save()
        svc = BuddyMatchingService()
        result = svc.find_compatible_buddy(u1)
        assert result is None

    def test_create_buddy_request(self, u1, u3):
        svc = BuddyMatchingService()
        with patch.object(svc, "_send_buddy_request_notification"):
            pairing = svc.create_buddy_request(u1, u3, 0.85, ["health"])
        assert pairing.status == "pending"
        assert pairing.compatibility_score == 0.85

    def test_create_buddy_request_sends_notification(self, u1, u3):
        svc = BuddyMatchingService()
        with patch.object(svc, "_send_buddy_request_notification") as mock_notify:
            svc.create_buddy_request(u1, u3, 0.7, ["education"])
            mock_notify.assert_called_once()

    def test_notification_content(self, u1, u3):
        from apps.notifications.models import Notification

        svc = BuddyMatchingService()
        svc._send_buddy_request_notification(u1, u3, ["health", "career"])
        notif = Notification.objects.filter(
            user=u3, notification_type="buddy_request"
        ).first()
        assert notif is not None
        assert "User1" in notif.body


# ════════════════════════════════════════════════════════════════════
#  5. Find match / AI matches view endpoints
# ════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestFindMatch:
    """Tests for POST /api/v1/buddies/find-match/."""

    def test_find_match_returns_match_key(self, c1):
        resp = c1.post("/api/v1/buddies/find-match/")
        assert resp.status_code == status.HTTP_200_OK
        assert "match" in resp.data

    def test_find_match_already_paired(self, c1, active_pair):
        resp = c1.post("/api/v1/buddies/find-match/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "already" in resp.data["error"].lower()

    def test_find_match_no_candidates(self, c1):
        resp = c1.post("/api/v1/buddies/find-match/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["match"] is None


@pytest.mark.django_db
class TestAIMatches:
    """Tests for GET /api/v1/buddies/ai-matches/."""

    def test_ai_matches_already_paired(self, c1, active_pair):
        resp = c1.get("/api/v1/buddies/ai-matches/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_ai_matches_no_candidates(self, c1):
        resp = c1.get("/api/v1/buddies/ai-matches/")
        # 200 with empty results or 403 if plan lacks AI
        assert resp.status_code in (200, 403)


# ════════════════════════════════════════════════════════════════════
#  6. Get current buddy / Progress
# ════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCurrentBuddy:
    """Tests for GET /api/v1/buddies/current/."""

    def test_no_buddy(self, c1):
        resp = c1.get("/api/v1/buddies/current/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["buddy"] is None

    def test_with_active_buddy(self, c1, active_pair):
        resp = c1.get("/api/v1/buddies/current/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["buddy"] is not None
        assert resp.data["buddy"]["status"] == "active"

    def test_ignores_pending(self, c1, pending_pair):
        resp = c1.get("/api/v1/buddies/current/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["buddy"] is None

    def test_as_user2(self, c2, active_pair):
        resp = c2.get("/api/v1/buddies/current/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["buddy"] is not None

    def test_buddy_partner_fields(self, c1, active_pair):
        resp = c1.get("/api/v1/buddies/current/")
        buddy = resp.data["buddy"]
        partner = buddy["partner"]
        assert "id" in partner
        assert "username" in partner
        assert "title" in partner
        assert "current_level" in partner
        assert "influence_score" in partner
        assert "current_streak" in partner


@pytest.mark.django_db
class TestBuddyProgress:
    """Tests for GET /api/v1/buddies/<id>/progress/."""

    def test_progress_success(self, c1, active_pair):
        resp = c1.get(f"/api/v1/buddies/{active_pair.id}/progress/")
        assert resp.status_code == status.HTTP_200_OK
        assert "progress" in resp.data
        assert "user" in resp.data["progress"]
        assert "partner" in resp.data["progress"]

    def test_progress_not_in_pairing(self, c3, active_pair):
        resp = c3.get(f"/api/v1/buddies/{active_pair.id}/progress/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_progress_nonexistent(self, c1):
        resp = c1.get(f"/api/v1/buddies/{uuid.uuid4()}/progress/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ════════════════════════════════════════════════════════════════════
#  7. IDOR Protection
# ════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestIDORProtection:
    """Verify that users cannot access other users' resources."""

    def test_outsider_cannot_view_progress(self, c3, active_pair):
        resp = c3.get(f"/api/v1/buddies/{active_pair.id}/progress/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_outsider_cannot_encourage(self, c3, active_pair):
        resp = c3.post(
            f"/api/v1/buddies/{active_pair.id}/encourage/",
            {"message": "Hi"},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_outsider_cannot_end_pairing(self, c3, active_pair):
        resp = c3.delete(f"/api/v1/buddies/{active_pair.id}/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_outsider_cannot_checkin_contract(self, c3, c1, contract_payload):
        create_resp = c1.post(
            "/api/v1/buddies/contracts/", contract_payload, format="json"
        )
        cid = create_resp.data["contract"]["id"]
        resp = c3.post(
            f"/api/v1/buddies/contracts/{cid}/check-in/",
            {"progress": {"0": 5}},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_outsider_cannot_accept_contract(self, c3, c1, contract_payload):
        create_resp = c1.post(
            "/api/v1/buddies/contracts/", contract_payload, format="json"
        )
        cid = create_resp.data["contract"]["id"]
        resp = c3.post(f"/api/v1/buddies/contracts/{cid}/accept/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_outsider_cannot_view_contract_progress(self, c3, c1, contract_payload):
        create_resp = c1.post(
            "/api/v1/buddies/contracts/", contract_payload, format="json"
        )
        cid = create_resp.data["contract"]["id"]
        resp = c3.get(f"/api/v1/buddies/contracts/{cid}/progress/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ════════════════════════════════════════════════════════════════════
#  8. Permission checks (auth, subscription)
# ════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBuddyPermissions:
    """Tests for authentication and subscription gating."""

    def test_unauthenticated(self):
        client = APIClient()
        resp = client.get("/api/v1/buddies/current/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_free_user_denied(self):
        free = _make_free_user("free_buddy@test.com", "FreeBuddy")
        client = _client(free)
        resp = client.get("/api/v1/buddies/current/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_free_user_cannot_pair(self):
        free = _make_free_user("free2@test.com", "FreePair")
        client = _client(free)
        resp = client.post("/api/v1/buddies/pair/", {"partner_id": str(uuid.uuid4())})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_free_user_cannot_list_contracts(self):
        free = _make_free_user("free3@test.com", "FreeContracts")
        client = _client(free)
        resp = client.get("/api/v1/buddies/contracts/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ════════════════════════════════════════════════════════════════════
#  9. Celery tasks
# ════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBuddyTasks:
    """Tests for Celery tasks."""

    def test_expire_pending_requests(self, u1, u3):
        expired = BuddyPairing.objects.create(
            user1=u1,
            user2=u3,
            status="pending",
            compatibility_score=0.5,
            expires_at=timezone.now() - timedelta(days=1),
        )
        from apps.buddies.tasks import expire_pending_buddy_requests

        count = expire_pending_buddy_requests()
        assert count == 1
        expired.refresh_from_db()
        assert expired.status == "cancelled"
        assert expired.ended_at is not None

    def test_expire_does_not_touch_active(self, active_pair):
        from apps.buddies.tasks import expire_pending_buddy_requests

        count = expire_pending_buddy_requests()
        assert count == 0
        active_pair.refresh_from_db()
        assert active_pair.status == "active"

    def test_send_checkin_reminders_no_stale(self, active_pair):
        """No reminders when encouragement was recent."""
        active_pair.last_encouragement_at = timezone.now()
        active_pair.save(update_fields=["last_encouragement_at"])
        from apps.buddies.tasks import send_buddy_checkin_reminders

        count = send_buddy_checkin_reminders()
        assert count == 0

    def test_send_checkin_reminders_stale(self, active_pair):
        """Reminders sent when last encouragement was > 3 days ago."""
        active_pair.last_encouragement_at = timezone.now() - timedelta(days=5)
        active_pair.save(update_fields=["last_encouragement_at"])
        from apps.buddies.tasks import send_buddy_checkin_reminders

        count = send_buddy_checkin_reminders()
        assert count == 2  # one for each user in the pairing


# ════════════════════════════════════════════════════════════════════
#  10. Model tests
# ════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBuddyModels:
    """Tests for model correctness."""

    def test_pairing_str(self, active_pair):
        s = str(active_pair)
        assert "User1" in s or "User2" in s
        assert "active" in s

    def test_pairing_status_choices(self, u1, u2):
        for code, _ in BuddyPairing.STATUS_CHOICES:
            p = BuddyPairing.objects.create(
                user1=u1, user2=u2, status=code, compatibility_score=0.5
            )
            assert p.status == code
            p.delete()

    def test_encouragement_str(self, active_pair, u1):
        enc = BuddyEncouragement.objects.create(
            pairing=active_pair, sender=u1, message="You're great!"
        )
        s = str(enc)
        assert "User1" in s

    def test_encouragement_empty_str(self, active_pair, u1):
        enc = BuddyEncouragement.objects.create(
            pairing=active_pair, sender=u1, message=""
        )
        assert "(no message)" in str(enc)

    def test_contract_str(self, active_pair, u1):
        c = AccountabilityContract.objects.create(
            pairing=active_pair,
            title="Test Contract",
            goals=[{"title": "G", "target": 1, "unit": "tasks"}],
            check_in_frequency="weekly",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            created_by=u1,
        )
        assert "Test Contract" in str(c)
        assert "active" in str(c)

    def test_checkin_str(self, active_pair, u1):
        contract = AccountabilityContract.objects.create(
            pairing=active_pair,
            title="TC",
            goals=[{"title": "G", "target": 1, "unit": "u"}],
            check_in_frequency="daily",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            created_by=u1,
        )
        ci = ContractCheckIn.objects.create(
            contract=contract, user=u1, progress={"0": 1}
        )
        s = str(ci)
        assert str(u1.id) in s

    def test_contract_frequency_choices(self, active_pair, u1):
        for freq, _ in AccountabilityContract.CHECK_IN_FREQUENCY_CHOICES:
            c = AccountabilityContract.objects.create(
                pairing=active_pair,
                title=f"Test {freq}",
                goals=[{"title": "G", "target": 1, "unit": "u"}],
                check_in_frequency=freq,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=30),
                created_by=u1,
            )
            assert c.check_in_frequency == freq
            c.delete()


# ════════════════════════════════════════════════════════════════════
#  11. Feature gaps — documented missing backend endpoints
# ════════════════════════════════════════════════════════════════════
#
# The frontend defines these endpoints in endpoints.js but the backend
# has no corresponding view actions:
#
#  - BUDDIES.SUGGESTIONS: '/api/buddies/suggestions/'
#    → No `suggestions` action on BuddyViewSet
#
#  - BUDDIES.ACCEPT_SUGGESTION(id): '/api/buddies/<id>/accept-suggestion/'
#    → No `accept_suggestion` action on BuddyViewSet
#
#  - BUDDIES.SKIP_SUGGESTION(id): '/api/buddies/<id>/skip-suggestion/'
#    → No `skip_suggestion` action on BuddyViewSet
#    → No BuddySkip model exists
#
# These would be needed for a skip/accept flow where users browse
# suggestions and can skip profiles they're not interested in.
#
# Also, the backend services.py has a BuddyMatchingService but the
# find_match view duplicates much of its logic inline rather than
# delegating. Consider refactoring to use BuddyMatchingService.
