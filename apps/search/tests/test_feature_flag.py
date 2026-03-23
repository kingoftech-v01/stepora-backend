"""
Tests for the USE_SEARCH feature flag.

Written FIRST (TDD) — implementation follows.

When USE_SEARCH=False:
  - Search endpoints return 501 Not Implemented
  - Response includes {error, coming_soon} payload

When USE_SEARCH=True:
  - Search endpoints work normally (200/400 depending on params)
"""

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.users.models import User


@pytest.fixture
def flag_user(db):
    return User.objects.create_user(
        email="flag@test.com",
        password="test123",
        display_name="Flag User",
    )


@pytest.fixture
def flag_client(flag_user):
    c = APIClient()
    c.force_authenticate(user=flag_user)
    return c


@pytest.mark.django_db
class TestSearchFeatureFlag:
    """Feature flag controls search endpoint availability."""

    @override_settings(USE_SEARCH=False)
    def test_search_returns_501_when_disabled(self, flag_client):
        """GET /api/v1/search/?q=test should return 501 when USE_SEARCH=False."""
        r = flag_client.get("/api/v1/search/?q=test")
        assert r.status_code == 501

    @override_settings(USE_SEARCH=False)
    def test_search_501_body_has_coming_soon(self, flag_client):
        """501 response should include coming_soon=True for frontend."""
        r = flag_client.get("/api/v1/search/?q=test")
        assert r.data["coming_soon"] is True
        assert "error" in r.data

    @override_settings(USE_SEARCH=False)
    def test_search_501_ignores_query_validation(self, flag_client):
        """Feature flag check runs before query validation."""
        r = flag_client.get("/api/v1/search/")
        assert r.status_code == 501

    @override_settings(USE_SEARCH=True)
    def test_search_works_when_enabled_valid_query(self, flag_client):
        """GET /api/v1/search/?q=test should return 200 when USE_SEARCH=True."""
        r = flag_client.get("/api/v1/search/?q=test")
        assert r.status_code == 200

    @override_settings(USE_SEARCH=True)
    def test_search_validation_still_applies_when_enabled(self, flag_client):
        """Query validation (min 2 chars) still works when flag is on."""
        r = flag_client.get("/api/v1/search/?q=a")
        assert r.status_code == 400

    def test_search_disabled_for_unauthenticated(self):
        """Unauthenticated users get 401 regardless of flag."""
        c = APIClient()
        r = c.get("/api/v1/search/?q=test")
        assert r.status_code == 401


@pytest.mark.django_db
class TestSearchFeatureFlagSetting:
    """USE_SEARCH setting defaults and configuration."""

    def test_use_search_exists_in_settings(self):
        """USE_SEARCH should be defined in Django settings."""
        from django.conf import settings

        assert hasattr(settings, "USE_SEARCH")

    def test_use_search_is_boolean(self):
        """USE_SEARCH should be a boolean value."""
        from django.conf import settings

        assert isinstance(settings.USE_SEARCH, bool)
