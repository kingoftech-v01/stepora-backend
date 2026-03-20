"""
Test fixtures for referrals app tests.
"""

import pytest

from apps.users.models import User


@pytest.fixture
def referrer(db):
    return User.objects.create_user(
        email="referrer@test.com",
        password="testpass123",
        display_name="Referrer",
    )


@pytest.fixture
def referred_user(db):
    return User.objects.create_user(
        email="referred@test.com",
        password="testpass123",
        display_name="Referred",
    )


@pytest.fixture
def referral_code(referrer):
    from apps.referrals.models import ReferralCode

    code, _ = ReferralCode.objects.get_or_create(user=referrer)
    return code
