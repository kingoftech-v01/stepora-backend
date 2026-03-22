"""
Tests for referrals views.
"""

import pytest
from rest_framework.test import APIClient

from apps.referrals.models import ReferralCode
from apps.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def ref_user_a(db):
    return User.objects.create_user(
        email="refa@test.com", password="testpass123"
    )


@pytest.fixture
def ref_user_b(db):
    return User.objects.create_user(
        email="refb@test.com", password="testpass123"
    )


@pytest.fixture
def auth_client_a(api_client, ref_user_a):
    api_client.force_authenticate(user=ref_user_a)
    return api_client


@pytest.fixture
def auth_client_b(api_client, ref_user_b):
    client = APIClient()
    client.force_authenticate(user=ref_user_b)
    return client


@pytest.mark.django_db
class TestMyReferralCodeView:
    def test_get_code(self, auth_client_a, ref_user_a):
        response = auth_client_a.get("/api/v1/referrals/code/")
        assert response.status_code == 200
        assert "code" in response.data


@pytest.mark.django_db
class TestRedeemCodeView:
    def test_redeem_valid_code(self, auth_client_b, ref_user_a, ref_user_b):
        code, _ = ReferralCode.objects.get_or_create(user=ref_user_a)
        response = auth_client_b.post(
            "/api/v1/referrals/redeem/",
            {"code": code.code},
            format="json",
        )
        assert response.status_code == 200

    def test_redeem_own_code(self, auth_client_a, ref_user_a):
        code, _ = ReferralCode.objects.get_or_create(user=ref_user_a)
        response = auth_client_a.post(
            "/api/v1/referrals/redeem/",
            {"code": code.code},
            format="json",
        )
        assert response.status_code == 400

    def test_redeem_invalid_code(self, auth_client_b):
        response = auth_client_b.post(
            "/api/v1/referrals/redeem/",
            {"code": "INVALIDX"},
            format="json",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestMyReferralsView:
    def test_list(self, auth_client_a):
        response = auth_client_a.get("/api/v1/referrals/my-referrals/")
        assert response.status_code == 200
        assert "referrals" in response.data


@pytest.mark.django_db
class TestMyRewardsView:
    def test_list(self, auth_client_a):
        response = auth_client_a.get("/api/v1/referrals/rewards/")
        assert response.status_code == 200
        assert "rewards" in response.data
