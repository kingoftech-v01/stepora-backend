"""
Tests for referrals services.
"""

import pytest

from apps.referrals.models import Referral, ReferralCode, ReferralReward
from apps.referrals.services import ReferralService
from apps.users.models import User


@pytest.fixture
def svc_referrer(db):
    return User.objects.create_user(
        email="svcreferrer@test.com", password="testpass123"
    )


@pytest.fixture
def svc_referred(db):
    return User.objects.create_user(
        email="svcreferred@test.com", password="testpass123"
    )


@pytest.fixture
def svc_code(svc_referrer):
    code, _ = ReferralCode.objects.get_or_create(user=svc_referrer)
    return code


@pytest.mark.django_db
class TestReferralService:
    def test_create_referral(self, svc_referrer, svc_referred, svc_code):
        referral = ReferralService.create_referral(
            referrer=svc_referrer,
            referred=svc_referred,
            referral_code=svc_code,
        )
        assert referral.status == "completed"
        # Both users should have rewards
        assert ReferralReward.objects.filter(user=svc_referrer).exists()
        assert ReferralReward.objects.filter(user=svc_referred).exists()
        # Code usage should be incremented
        svc_code.refresh_from_db()
        assert svc_code.times_used == 1

    def test_get_stats(self, svc_referrer, svc_referred, svc_code):
        ReferralService.create_referral(
            referrer=svc_referrer,
            referred=svc_referred,
            referral_code=svc_code,
        )
        stats = ReferralService.get_referral_stats(svc_referrer)
        assert stats["total_referrals"] == 1
        assert stats["total_xp_earned"] > 0
