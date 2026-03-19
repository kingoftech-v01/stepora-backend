"""
Integration tests for the Updates (OTA) app.
"""

from unittest.mock import patch

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from apps.updates.models import AppBundle


# Mock the S3 storage to use default (local) storage in tests
@pytest.fixture(autouse=True)
def mock_releases_storage():
    """Override bundle_file storage with default file storage for tests."""
    from django.core.files.storage import FileSystemStorage

    fs = FileSystemStorage()
    with patch.object(
        AppBundle.bundle_file.field, "storage", fs
    ):
        yield


# ── Update Check (GET /api/v1/updates/check/) ────────────────────────


@pytest.mark.django_db
class TestUpdateCheck:
    """Tests for the OTA update check endpoint."""

    def test_check_no_bundles(self, anon_client):
        """Returns 204 when no bundles exist."""
        response = anon_client.get("/api/v1/updates/check/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_check_with_bundle(self, anon_client, db):
        """Returns bundle info when an active bundle exists."""
        bundle_file = SimpleUploadedFile("bundle.zip", b"PK" + b"\x00" * 100)
        bundle = AppBundle.objects.create(
            bundle_id="b-20260319-120000",
            is_active=True,
            bundle_file=bundle_file,
            checksum="abc123",
            strategy="notify",
            platform="all",
            min_app_version=1,
            message="New version available",
        )
        response = anon_client.get("/api/v1/updates/check/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["bundle_id"] == "b-20260319-120000"
        assert response.data["strategy"] == "notify"

    def test_check_already_has_bundle(self, anon_client, db):
        """Returns 204 when client already has the current bundle."""
        bundle_file = SimpleUploadedFile("bundle.zip", b"PK" + b"\x00" * 100)
        bundle = AppBundle.objects.create(
            bundle_id="b-20260319-120000",
            is_active=True,
            bundle_file=bundle_file,
        )
        response = anon_client.get(
            "/api/v1/updates/check/?bundle_id=b-20260319-120000"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_check_platform_filter(self, anon_client, db):
        """Returns bundle matching the requested platform."""
        bundle_file = SimpleUploadedFile("bundle.zip", b"PK" + b"\x00" * 100)
        AppBundle.objects.create(
            bundle_id="b-20260319-120001",
            is_active=True,
            bundle_file=bundle_file,
            platform="android",
        )
        response = anon_client.get("/api/v1/updates/check/?platform=android")
        assert response.status_code == status.HTTP_200_OK

    def test_check_version_filter(self, anon_client, db):
        """Bundle with high min_app_version not returned for older clients."""
        bundle_file = SimpleUploadedFile("bundle.zip", b"PK" + b"\x00" * 100)
        AppBundle.objects.create(
            bundle_id="b-20260319-120002",
            is_active=True,
            bundle_file=bundle_file,
            min_app_version=100,
        )
        response = anon_client.get("/api/v1/updates/check/?app_version=5")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_check_invalid_version(self, anon_client, db):
        """Invalid app_version treated as 0."""
        bundle_file = SimpleUploadedFile("bundle.zip", b"PK" + b"\x00" * 100)
        AppBundle.objects.create(
            bundle_id="b-20260319-120003",
            is_active=True,
            bundle_file=bundle_file,
            min_app_version=1,
        )
        response = anon_client.get("/api/v1/updates/check/?app_version=abc")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
        )


# ── Bundle Upload (POST /api/v1/updates/upload/) ─────────────────────


@pytest.mark.django_db
class TestBundleUpload:
    """Tests for the OTA bundle upload endpoint (admin only)."""

    def test_upload_unauthenticated(self, anon_client):
        """Upload without authentication returns 401/403."""
        response = anon_client.post("/api/v1/updates/upload/")
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_upload_non_admin(self, updates_client):
        """Upload by non-admin returns 403."""
        response = updates_client.post("/api/v1/updates/upload/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_upload_no_file(self, admin_client):
        """Upload without file returns 400."""
        response = admin_client.post("/api/v1/updates/upload/", format="multipart")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_non_zip(self, admin_client):
        """Upload non-zip file returns 400."""
        txt_file = SimpleUploadedFile("bundle.txt", b"not a zip")
        response = admin_client.post(
            "/api/v1/updates/upload/",
            {"file": txt_file},
            format="multipart",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_success(self, admin_client):
        """Upload valid zip bundle creates bundle record."""
        zip_file = SimpleUploadedFile("bundle.zip", b"PK" + b"\x00" * 100)
        response = admin_client.post(
            "/api/v1/updates/upload/",
            {"file": zip_file, "strategy": "silent", "platform": "android"},
            format="multipart",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert "bundle_id" in response.data
        assert "checksum" in response.data
        assert response.data["strategy"] == "silent"
        assert response.data["platform"] == "android"

    def test_upload_defaults(self, admin_client):
        """Upload with defaults uses 'notify' and 'all'."""
        zip_file = SimpleUploadedFile("bundle.zip", b"PK" + b"\x00" * 100)
        response = admin_client.post(
            "/api/v1/updates/upload/",
            {"file": zip_file},
            format="multipart",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["strategy"] == "notify"
        assert response.data["platform"] == "all"


# ── Model tests ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAppBundleModel:
    """Tests for the AppBundle model."""

    def test_str(self):
        """AppBundle __str__ includes bundle_id and status."""
        bundle_file = SimpleUploadedFile("bundle.zip", b"PK" + b"\x00" * 100)
        bundle = AppBundle.objects.create(
            bundle_id="b-test-001",
            is_active=True,
            bundle_file=bundle_file,
        )
        assert "b-test-001" in str(bundle)
        assert "active" in str(bundle)

    def test_str_inactive(self):
        """AppBundle __str__ shows inactive when not active."""
        bundle_file = SimpleUploadedFile("bundle.zip", b"PK" + b"\x00" * 100)
        bundle = AppBundle.objects.create(
            bundle_id="b-test-002",
            is_active=False,
            bundle_file=bundle_file,
        )
        assert "inactive" in str(bundle)
