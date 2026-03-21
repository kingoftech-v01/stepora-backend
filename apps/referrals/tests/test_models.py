"""
Tests for referrals models.
"""

import pytest

from apps.referrals.models import Referral, ReferralCode, ReferralReward


@pytest.mark.django_db
class TestReferralCode:
    def test_auto_generate_code(self, referrer):
        # Signal auto-creates a ReferralCode on user creation
        code = ReferralCode.objects.get(user=referrer)
        assert len(code.code) == 8
        assert code.is_active is True
        assert code.times_used == 0

    def test_is_exhausted(self, referral_code):
        referral_code.max_uses = 1
        referral_code.times_used = 1
        referral_code.save()
        assert referral_code.is_exhausted is True

    def test_not_exhausted(self, referral_code):
        referral_code.max_uses = 10
        referral_code.save()
        assert referral_code.is_exhausted is False

    def test_unlimited_uses(self, referral_code):
        assert referral_code.uses_remaining is None
        assert referral_code.is_exhausted is False


@pytest.mark.django_db
class TestReferral:
    def test_create(self, referrer, referred_user, referral_code):
        ref = Referral.objects.create(
            referrer=referrer,
            referred=referred_user,
            referral_code=referral_code,
        )
        assert ref.status == "pending"

    def test_complete(self, referrer, referred_user, referral_code):
        ref = Referral.objects.create(
            referrer=referrer,
            referred=referred_user,
            referral_code=referral_code,
        )
        ref.complete()
        ref.refresh_from_db()
        assert ref.status == "completed"
        assert ref.completed_at is not None


@pytest.mark.django_db
class TestReferralReward:
    def test_claim_xp(self, referrer, referred_user, referral_code):
        referral = Referral.objects.create(
            referrer=referrer,
            referred=referred_user,
            referral_code=referral_code,
            status="completed",
        )
        reward = ReferralReward.objects.create(
            referral=referral,
            user=referrer,
            reward_type="xp",
            reward_value=200,
        )
        initial_xp = referrer.xp
        reward.claim()
        referrer.refresh_from_db()
        assert reward.is_claimed is True
        assert referrer.xp == initial_xp + 200

    def test_claim_idempotent(self, referrer, referred_user, referral_code):
        referral = Referral.objects.create(
            referrer=referrer,
            referred=referred_user,
            referral_code=referral_code,
            status="completed",
        )
        reward = ReferralReward.objects.create(
            referral=referral,
            user=referrer,
            reward_type="xp",
            reward_value=200,
        )
        reward.claim()
        xp_after_first = referrer.xp
        reward.claim()  # Should be no-op
        referrer.refresh_from_db()
        assert referrer.xp == xp_after_first
