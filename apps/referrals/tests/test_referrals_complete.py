"""
Comprehensive tests for the Referrals app.

Covers:
- ReferralCode: auto-creation via signal, uniqueness, exhaustion, uses_remaining
- Referral: creation, completion, unique constraint, status tracking
- ReferralReward: claim XP, claim streak freeze, idempotent claim, tier_name
- ReferralService: create_referral flow, stats calculation
- API endpoints: GET code, redeem, my-referrals, rewards, claim, dashboard
- Edge cases: own code, invalid code, already referred, max uses, inactive code
- IDOR: user cannot see/claim another user's rewards
- Dashboard: GET stats, POST redeem, combined data shape
"""

import uuid

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.referrals.models import Referral, ReferralCode, ReferralReward
from apps.referrals.services import (
    REFERRER_XP_REWARD,
    REFERRED_XP_REWARD,
    ReferralService,
)
from apps.referrals.views import REFERRALS_PER_REWARD
from apps.users.models import User


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def alice(db):
    """Referrer user."""
    return User.objects.create_user(
        email="alice@test.com",
        password="testpass123",
        display_name="Alice",
    )


@pytest.fixture
def bob(db):
    """Referred user."""
    return User.objects.create_user(
        email="bob@test.com",
        password="testpass123",
        display_name="Bob",
    )


@pytest.fixture
def charlie(db):
    """Third user for multi-referral tests."""
    return User.objects.create_user(
        email="charlie@test.com",
        password="testpass123",
        display_name="Charlie",
    )


@pytest.fixture
def diana(db):
    """Fourth user."""
    return User.objects.create_user(
        email="diana@test.com",
        password="testpass123",
        display_name="Diana",
    )


@pytest.fixture
def eve(db):
    """Fifth user (for IDOR tests)."""
    return User.objects.create_user(
        email="eve@test.com",
        password="testpass123",
        display_name="Eve",
    )


@pytest.fixture
def alice_code(alice):
    """Alice's referral code (auto-created by signal)."""
    return ReferralCode.objects.get(user=alice)


@pytest.fixture
def alice_client(alice):
    c = APIClient()
    c.force_authenticate(user=alice)
    return c


@pytest.fixture
def bob_client(bob):
    c = APIClient()
    c.force_authenticate(user=bob)
    return c


@pytest.fixture
def eve_client(eve):
    c = APIClient()
    c.force_authenticate(user=eve)
    return c


@pytest.fixture
def unauth_client():
    return APIClient()


# =====================================================================
# 1. ReferralCode model tests
# =====================================================================

@pytest.mark.django_db
class TestReferralCodeModel:
    """Tests for the ReferralCode model."""

    def test_auto_created_on_user_signup(self, alice):
        """Signal creates a ReferralCode when a user is created."""
        assert ReferralCode.objects.filter(user=alice).exists()
        code = ReferralCode.objects.get(user=alice)
        assert len(code.code) == 8
        assert code.code == code.code.upper()
        assert code.is_active is True
        assert code.times_used == 0

    def test_code_uniqueness(self, alice, bob):
        """Each user gets a unique code."""
        alice_code = ReferralCode.objects.get(user=alice)
        bob_code = ReferralCode.objects.get(user=bob)
        assert alice_code.code != bob_code.code

    def test_one_code_per_user(self, alice):
        """OneToOneField prevents duplicate codes."""
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            ReferralCode.objects.create(user=alice, code="DUPL1CAT")

    def test_is_exhausted_true(self, alice_code):
        alice_code.max_uses = 5
        alice_code.times_used = 5
        alice_code.save()
        assert alice_code.is_exhausted is True

    def test_is_exhausted_false(self, alice_code):
        alice_code.max_uses = 10
        alice_code.times_used = 3
        alice_code.save()
        assert alice_code.is_exhausted is False

    def test_unlimited_uses(self, alice_code):
        """max_uses=None means unlimited."""
        assert alice_code.max_uses is None
        assert alice_code.is_exhausted is False
        assert alice_code.uses_remaining is None

    def test_uses_remaining_computed(self, alice_code):
        alice_code.max_uses = 10
        alice_code.times_used = 7
        alice_code.save()
        assert alice_code.uses_remaining == 3

    def test_uses_remaining_zero(self, alice_code):
        alice_code.max_uses = 2
        alice_code.times_used = 5  # over limit
        alice_code.save()
        assert alice_code.uses_remaining == 0
        assert alice_code.is_exhausted is True

    def test_str_representation(self, alice, alice_code):
        assert alice.email in str(alice_code)
        assert alice_code.code in str(alice_code)

    def test_generate_code_format(self):
        """_generate_code produces 8 uppercase chars."""
        code = ReferralCode._generate_code()
        assert len(code) == 8
        assert code == code.upper()


# =====================================================================
# 2. Referral model tests
# =====================================================================

@pytest.mark.django_db
class TestReferralModel:
    """Tests for the Referral model."""

    def test_create_default_status(self, alice, bob, alice_code):
        ref = Referral.objects.create(
            referrer=alice,
            referred=bob,
            referral_code=alice_code,
        )
        assert ref.status == "pending"
        assert ref.completed_at is None

    def test_complete(self, alice, bob, alice_code):
        ref = Referral.objects.create(
            referrer=alice, referred=bob, referral_code=alice_code,
        )
        ref.complete()
        ref.refresh_from_db()
        assert ref.status == "completed"
        assert ref.completed_at is not None

    def test_complete_idempotent(self, alice, bob, alice_code):
        """Calling complete() twice does not fail."""
        ref = Referral.objects.create(
            referrer=alice, referred=bob, referral_code=alice_code,
            status="completed", completed_at=timezone.now(),
        )
        ref.complete()
        assert ref.status == "completed"

    def test_unique_referral_pair(self, alice, bob, alice_code):
        """Cannot create two referrals for the same pair."""
        from django.db import IntegrityError

        Referral.objects.create(
            referrer=alice, referred=bob, referral_code=alice_code,
        )
        with pytest.raises(IntegrityError):
            Referral.objects.create(
                referrer=alice, referred=bob, referral_code=alice_code,
            )

    def test_str_representation(self, alice, bob, alice_code):
        ref = Referral.objects.create(
            referrer=alice, referred=bob, referral_code=alice_code,
        )
        s = str(ref)
        assert alice.email in s
        assert bob.email in s
        assert "pending" in s


# =====================================================================
# 3. ReferralReward model tests
# =====================================================================

@pytest.mark.django_db
class TestReferralRewardModel:
    """Tests for the ReferralReward model."""

    def test_claim_xp(self, alice, bob, alice_code):
        referral = Referral.objects.create(
            referrer=alice, referred=bob, referral_code=alice_code,
            status="completed",
        )
        reward = ReferralReward.objects.create(
            referral=referral, user=alice,
            reward_type="xp", reward_value=200,
        )
        initial_xp = alice.xp
        reward.claim()
        alice.refresh_from_db()
        assert reward.is_claimed is True
        assert reward.claimed_at is not None
        assert alice.xp == initial_xp + 200

    def test_claim_streak_freeze(self, alice, bob, alice_code):
        from apps.gamification.models import GamificationProfile

        profile, _ = GamificationProfile.objects.get_or_create(user=alice)
        initial_jokers = profile.streak_jokers

        referral = Referral.objects.create(
            referrer=alice, referred=bob, referral_code=alice_code,
            status="completed",
        )
        reward = ReferralReward.objects.create(
            referral=referral, user=alice,
            reward_type="streak_freeze", reward_value=2,
        )
        reward.claim()
        profile.refresh_from_db()
        assert profile.streak_jokers == initial_jokers + 2

    def test_claim_idempotent(self, alice, bob, alice_code):
        referral = Referral.objects.create(
            referrer=alice, referred=bob, referral_code=alice_code,
            status="completed",
        )
        reward = ReferralReward.objects.create(
            referral=referral, user=alice,
            reward_type="xp", reward_value=200,
        )
        reward.claim()
        xp_after = alice.xp
        reward.claim()  # second call — should be no-op
        alice.refresh_from_db()
        assert alice.xp == xp_after

    def test_tier_name_field(self, alice):
        reward = ReferralReward.objects.create(
            user=alice, reward_type="premium_days",
            reward_value=30, tier_name="gold",
            description="Gold tier bonus",
        )
        assert reward.tier_name == "gold"

    def test_str_representation(self, alice):
        reward = ReferralReward.objects.create(
            user=alice, reward_type="xp", reward_value=100,
        )
        s = str(reward)
        assert "xp" in s
        assert "100" in s


# =====================================================================
# 4. ReferralService tests
# =====================================================================

@pytest.mark.django_db
class TestReferralService:
    """Tests for the ReferralService business logic."""

    def test_create_referral_creates_records(self, alice, bob, alice_code):
        referral = ReferralService.create_referral(
            referrer=alice, referred=bob, referral_code=alice_code,
        )
        assert referral.status == "completed"
        assert referral.completed_at is not None

    def test_create_referral_increments_usage(self, alice, bob, alice_code):
        ReferralService.create_referral(
            referrer=alice, referred=bob, referral_code=alice_code,
        )
        alice_code.refresh_from_db()
        assert alice_code.times_used == 1

    def test_create_referral_creates_rewards(self, alice, bob, alice_code):
        ReferralService.create_referral(
            referrer=alice, referred=bob, referral_code=alice_code,
        )
        # Both users should have XP rewards
        assert ReferralReward.objects.filter(
            user=alice, reward_type="xp", reward_value=REFERRER_XP_REWARD,
        ).exists()
        assert ReferralReward.objects.filter(
            user=bob, reward_type="xp", reward_value=REFERRED_XP_REWARD,
        ).exists()

    def test_create_referral_auto_claims_xp(self, alice, bob, alice_code):
        initial_alice_xp = alice.xp
        initial_bob_xp = bob.xp
        ReferralService.create_referral(
            referrer=alice, referred=bob, referral_code=alice_code,
        )
        alice.refresh_from_db()
        bob.refresh_from_db()
        assert alice.xp == initial_alice_xp + REFERRER_XP_REWARD
        assert bob.xp == initial_bob_xp + REFERRED_XP_REWARD

    def test_get_stats_no_referrals(self, alice):
        stats = ReferralService.get_referral_stats(alice)
        assert stats["referral_code"] is not None
        assert stats["total_referrals"] == 0
        assert stats["total_xp_earned"] == 0

    def test_get_stats_with_referrals(self, alice, bob, alice_code):
        ReferralService.create_referral(
            referrer=alice, referred=bob, referral_code=alice_code,
        )
        stats = ReferralService.get_referral_stats(alice)
        assert stats["total_referrals"] == 1
        assert stats["total_xp_earned"] == REFERRER_XP_REWARD

    def test_get_stats_no_code_yet(self, db):
        """User created but code somehow missing."""
        new_user = User.objects.create_user(
            email="nocode@test.com", password="pass123",
        )
        # Delete the auto-created code
        ReferralCode.objects.filter(user=new_user).delete()
        stats = ReferralService.get_referral_stats(new_user)
        assert stats["referral_code"] is None
        assert stats["total_referrals"] == 0


# =====================================================================
# 5. API endpoint tests
# =====================================================================

@pytest.mark.django_db
class TestMyReferralCodeEndpoint:
    """GET /api/v1/referrals/code/"""

    def test_get_code(self, alice_client, alice):
        resp = alice_client.get("/api/v1/referrals/code/")
        assert resp.status_code == 200
        assert "code" in resp.data
        assert len(resp.data["code"]) == 8

    def test_unauthenticated(self, unauth_client):
        resp = unauth_client.get("/api/v1/referrals/code/")
        assert resp.status_code in (401, 403)


@pytest.mark.django_db
class TestRedeemCodeEndpoint:
    """POST /api/v1/referrals/redeem/"""

    def test_redeem_valid(self, bob_client, alice, alice_code):
        resp = bob_client.post(
            "/api/v1/referrals/redeem/",
            {"code": alice_code.code},
            format="json",
        )
        assert resp.status_code == 200
        assert "referral_id" in resp.data

    def test_redeem_own_code(self, alice_client, alice_code):
        resp = alice_client.post(
            "/api/v1/referrals/redeem/",
            {"code": alice_code.code},
            format="json",
        )
        assert resp.status_code == 400
        assert "own" in resp.data["error"].lower()

    def test_redeem_invalid_code(self, bob_client):
        resp = bob_client.post(
            "/api/v1/referrals/redeem/",
            {"code": "XXXXXXXX"},
            format="json",
        )
        assert resp.status_code == 400
        assert "invalid" in resp.data["error"].lower()

    def test_redeem_inactive_code(self, bob_client, alice_code):
        alice_code.is_active = False
        alice_code.save()
        resp = bob_client.post(
            "/api/v1/referrals/redeem/",
            {"code": alice_code.code},
            format="json",
        )
        assert resp.status_code == 400
        assert "active" in resp.data["error"].lower()

    def test_redeem_exhausted_code(self, bob_client, alice_code):
        alice_code.max_uses = 1
        alice_code.times_used = 1
        alice_code.save()
        resp = bob_client.post(
            "/api/v1/referrals/redeem/",
            {"code": alice_code.code},
            format="json",
        )
        assert resp.status_code == 400
        assert "maximum" in resp.data["error"].lower()

    def test_already_referred(self, bob_client, alice, bob, alice_code):
        # First redeem
        bob_client.post(
            "/api/v1/referrals/redeem/",
            {"code": alice_code.code},
            format="json",
        )
        # Attempt to redeem again
        resp = bob_client.post(
            "/api/v1/referrals/redeem/",
            {"code": alice_code.code},
            format="json",
        )
        assert resp.status_code == 400
        assert "already" in resp.data["error"].lower()

    def test_case_insensitive(self, bob_client, alice_code):
        resp = bob_client.post(
            "/api/v1/referrals/redeem/",
            {"code": alice_code.code.lower()},
            format="json",
        )
        assert resp.status_code == 200

    def test_unauthenticated(self, unauth_client):
        resp = unauth_client.post(
            "/api/v1/referrals/redeem/",
            {"code": "WHATEVER"},
            format="json",
        )
        assert resp.status_code in (401, 403)


@pytest.mark.django_db
class TestMyReferralsEndpoint:
    """GET /api/v1/referrals/my-referrals/"""

    def test_empty_list(self, alice_client):
        resp = alice_client.get("/api/v1/referrals/my-referrals/")
        assert resp.status_code == 200
        assert resp.data["referrals"] == []
        assert resp.data["count"] == 0

    def test_with_referrals(self, alice_client, alice, bob, alice_code):
        ReferralService.create_referral(
            referrer=alice, referred=bob, referral_code=alice_code,
        )
        resp = alice_client.get("/api/v1/referrals/my-referrals/")
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert len(resp.data["referrals"]) == 1

    def test_idor_cannot_see_others(self, bob_client, alice, bob, charlie, alice_code):
        """Bob cannot see Alice's referrals list."""
        ReferralService.create_referral(
            referrer=alice, referred=charlie, referral_code=alice_code,
        )
        resp = bob_client.get("/api/v1/referrals/my-referrals/")
        assert resp.status_code == 200
        assert resp.data["count"] == 0


@pytest.mark.django_db
class TestMyRewardsEndpoint:
    """GET /api/v1/referrals/rewards/"""

    def test_empty(self, alice_client):
        resp = alice_client.get("/api/v1/referrals/rewards/")
        assert resp.status_code == 200
        assert resp.data["rewards"] == []
        assert resp.data["unclaimed"] == 0

    def test_with_rewards(self, alice_client, alice, bob, alice_code):
        ReferralService.create_referral(
            referrer=alice, referred=bob, referral_code=alice_code,
        )
        resp = alice_client.get("/api/v1/referrals/rewards/")
        assert resp.status_code == 200
        assert len(resp.data["rewards"]) >= 1

    def test_idor_cannot_see_others_rewards(self, eve_client, alice, bob, alice_code):
        ReferralService.create_referral(
            referrer=alice, referred=bob, referral_code=alice_code,
        )
        resp = eve_client.get("/api/v1/referrals/rewards/")
        assert resp.status_code == 200
        assert len(resp.data["rewards"]) == 0


@pytest.mark.django_db
class TestClaimRewardEndpoint:
    """POST /api/v1/referrals/rewards/<id>/claim/"""

    def test_claim_success(self, alice_client, alice):
        reward = ReferralReward.objects.create(
            user=alice, reward_type="xp", reward_value=50,
        )
        resp = alice_client.post(f"/api/v1/referrals/rewards/{reward.id}/claim/")
        assert resp.status_code == 200
        assert resp.data["is_claimed"] is True

    def test_claim_already_claimed(self, alice_client, alice):
        reward = ReferralReward.objects.create(
            user=alice, reward_type="xp", reward_value=50,
            is_claimed=True, claimed_at=timezone.now(),
        )
        resp = alice_client.post(f"/api/v1/referrals/rewards/{reward.id}/claim/")
        assert resp.status_code == 400
        assert "already" in resp.data["error"].lower()

    def test_claim_nonexistent(self, alice_client):
        fake_id = uuid.uuid4()
        resp = alice_client.post(f"/api/v1/referrals/rewards/{fake_id}/claim/")
        assert resp.status_code == 404

    def test_idor_cannot_claim_others_reward(self, eve_client, alice):
        """Eve cannot claim Alice's reward."""
        reward = ReferralReward.objects.create(
            user=alice, reward_type="xp", reward_value=50,
        )
        resp = eve_client.post(f"/api/v1/referrals/rewards/{reward.id}/claim/")
        assert resp.status_code == 404  # filtered by user


# =====================================================================
# 6. Dashboard endpoint tests (frontend-facing)
# =====================================================================

@pytest.mark.django_db
class TestReferralDashboardEndpoint:
    """
    GET  /api/v1/referrals/dashboard/ — stats
    POST /api/v1/referrals/dashboard/ — redeem code
    """

    def test_get_dashboard_empty(self, alice_client, alice):
        resp = alice_client.get("/api/v1/referrals/dashboard/")
        assert resp.status_code == 200
        data = resp.data
        assert "referral_code" in data
        assert data["total_referrals"] == 0
        assert data["paid_referrals"] == 0
        assert data["free_months_earned"] == 0
        assert data["progress_to_next"] == 0
        assert data["referrals_until_next_reward"] == REFERRALS_PER_REWARD

    def test_get_dashboard_with_referrals(
        self, alice_client, alice, bob, charlie, diana, alice_code,
    ):
        # Create 3 referrals (= 1 free month)
        for referred in [bob, charlie, diana]:
            ReferralService.create_referral(
                referrer=alice, referred=referred, referral_code=alice_code,
            )
        resp = alice_client.get("/api/v1/referrals/dashboard/")
        assert resp.status_code == 200
        data = resp.data
        assert data["total_referrals"] == 3
        assert data["paid_referrals"] == 3
        assert data["free_months_earned"] == 1
        assert data["progress_to_next"] == 0
        assert data["referrals_until_next_reward"] == REFERRALS_PER_REWARD

    def test_get_dashboard_partial_progress(
        self, alice_client, alice, bob, alice_code,
    ):
        ReferralService.create_referral(
            referrer=alice, referred=bob, referral_code=alice_code,
        )
        resp = alice_client.get("/api/v1/referrals/dashboard/")
        data = resp.data
        assert data["paid_referrals"] == 1
        assert data["progress_to_next"] == 1
        assert data["referrals_until_next_reward"] == REFERRALS_PER_REWARD - 1

    def test_post_redeem_via_dashboard(self, bob_client, alice_code):
        resp = bob_client.post(
            "/api/v1/referrals/dashboard/",
            {"referral_code": alice_code.code},
            format="json",
        )
        assert resp.status_code == 200
        assert "referral_id" in resp.data

    def test_post_redeem_code_field(self, bob_client, alice_code):
        """Also accepts ``code`` field name."""
        resp = bob_client.post(
            "/api/v1/referrals/dashboard/",
            {"code": alice_code.code},
            format="json",
        )
        assert resp.status_code == 200

    def test_post_redeem_own_code(self, alice_client, alice_code):
        resp = alice_client.post(
            "/api/v1/referrals/dashboard/",
            {"referral_code": alice_code.code},
            format="json",
        )
        assert resp.status_code == 400

    def test_post_redeem_invalid_code(self, bob_client):
        resp = bob_client.post(
            "/api/v1/referrals/dashboard/",
            {"referral_code": "ZZZZZZZZ"},
            format="json",
        )
        assert resp.status_code == 400

    def test_unauthenticated_dashboard(self, unauth_client):
        resp = unauth_client.get("/api/v1/referrals/dashboard/")
        assert resp.status_code in (401, 403)

    def test_backward_compat_unversioned_url(self, alice_client):
        """The /api/ unversioned alias also works."""
        resp = alice_client.get("/api/referrals/dashboard/")
        assert resp.status_code == 200


# =====================================================================
# 7. Signal tests
# =====================================================================

@pytest.mark.django_db
class TestReferralSignals:
    """Test that signals fire correctly."""

    def test_code_auto_created_for_new_user(self, db):
        user = User.objects.create_user(
            email="sigtest@test.com", password="pass123",
        )
        assert ReferralCode.objects.filter(user=user).count() == 1

    def test_code_not_duplicated_on_save(self, alice):
        """Saving a user again does not create a second code."""
        alice.display_name = "Alice Updated"
        alice.save()
        assert ReferralCode.objects.filter(user=alice).count() == 1


# =====================================================================
# 8. Serializer tests
# =====================================================================

@pytest.mark.django_db
class TestSerializers:
    """Test serializer output shapes."""

    def test_referral_code_serializer_fields(self, alice_client):
        resp = alice_client.get("/api/v1/referrals/code/")
        data = resp.data
        assert "id" in data
        assert "code" in data
        assert "is_active" in data
        assert "times_used" in data
        assert "uses_remaining" in data

    def test_referral_serializer_fields(self, alice_client, alice, bob, alice_code):
        ReferralService.create_referral(
            referrer=alice, referred=bob, referral_code=alice_code,
        )
        resp = alice_client.get("/api/v1/referrals/my-referrals/")
        ref = resp.data["referrals"][0]
        assert "referrer_email" in ref
        assert "referred_email" in ref
        assert "status" in ref

    def test_reward_serializer_fields(self, alice_client, alice, bob, alice_code):
        ReferralService.create_referral(
            referrer=alice, referred=bob, referral_code=alice_code,
        )
        resp = alice_client.get("/api/v1/referrals/rewards/")
        reward = resp.data["rewards"][0]
        assert "reward_type" in reward
        assert "reward_value" in reward
        assert "is_claimed" in reward
