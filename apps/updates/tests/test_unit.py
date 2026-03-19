"""
Unit tests for the Updates app.

Tests AppBundle model and update check/upload API endpoints.
"""

import pytest
from rest_framework.test import APIClient

from apps.updates.models import AppBundle


@pytest.mark.django_db
class TestAppBundleModel:
    """Tests for AppBundle model."""

    def test_generate_bundle_id(self):
        from apps.updates.models import _generate_bundle_id

        bid = _generate_bundle_id()
        assert bid.startswith("b-")
        assert len(bid) > 5

    def test_bundle_str(self):
        # Can't fully create without a file, but test __str__
        bundle = AppBundle(bundle_id="b-20260319-120000", is_active=True)
        result = str(bundle)
        assert "b-20260319-120000" in result
        assert "active" in result

    def test_bundle_str_inactive(self):
        bundle = AppBundle(bundle_id="b-20260319-120001", is_active=False)
        result = str(bundle)
        assert "inactive" in result

    def test_bundle_defaults(self):
        bundle = AppBundle(bundle_id="b-test")
        assert bundle.strategy == "notify"
        assert bundle.platform == "all"
        assert bundle.min_app_version == 1
        assert bundle.is_active is True


@pytest.mark.django_db
class TestUpdateCheckAPI:
    """Tests for Update Check API."""

    def test_check_update_no_params(self, anon_client):
        resp = anon_client.get(
            "/api/updates/check/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 204, 400)

    def test_check_update_with_params(self, anon_client):
        resp = anon_client.get(
            "/api/updates/check/?platform=android&app_version=1&current_bundle=none",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 204)

    def test_upload_requires_admin(self, updates_client):
        resp = updates_client.post(
            "/api/updates/upload/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 403

    def test_upload_admin_no_file(self, admin_client):
        resp = admin_client.post(
            "/api/updates/upload/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (400, 415)
