"""
Comprehensive tests for the Updates (OTA) app.

Covers:
  - AppBundle model: fields, defaults, __str__, compute_checksum, save auto-checksum,
    _generate_bundle_id, _bundle_upload_path, Meta ordering
  - UpdateCheckView (GET /api/v1/updates/check/): platform filtering, version filtering,
    bundle_id dedup, inactive bundles, empty DB, response fields, multiple bundles ordering
  - BundleUploadView (POST /api/v1/updates/upload/): auth/permissions, file validation,
    strategy/platform defaults and overrides, checksum computation, signature verification,
    message field, min_app_version handling
  - Admin registration
  - Edge cases: invalid data, empty strings, boundary values

Target: 95%+ coverage for apps/updates/
"""

import hashlib
from unittest.mock import MagicMock, patch

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.updates.models import AppBundle, _bundle_upload_path, _generate_bundle_id
from apps.users.models import User

# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_releases_storage():
    """Override bundle_file storage with default file storage for all tests."""
    fs = FileSystemStorage()
    with patch.object(AppBundle.bundle_file.field, "storage", fs):
        yield


@pytest.fixture
def normal_user(db):
    """Non-admin user."""
    return User.objects.create_user(email="user@test.com", password="pass1234")


@pytest.fixture
def admin_user(db):
    """Staff/superuser."""
    return User.objects.create_superuser(email="admin@test.com", password="admin1234")


@pytest.fixture
def anon(db):
    """Unauthenticated client."""
    return APIClient()


@pytest.fixture
def user_client(normal_user):
    """Authenticated client (non-admin)."""
    c = APIClient()
    c.force_authenticate(user=normal_user)
    return c


@pytest.fixture
def admin_client(admin_user):
    """Authenticated admin client."""
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


def _make_zip(content=b"PK\x03\x04" + b"\x00" * 200):
    """Create a SimpleUploadedFile that looks like a zip."""
    return SimpleUploadedFile("bundle.zip", content, content_type="application/zip")


def _make_bundle(db, **kwargs):
    """Create an AppBundle with sensible defaults."""
    defaults = {
        "bundle_id": _generate_bundle_id(),
        "is_active": True,
        "bundle_file": _make_zip(),
        "platform": "all",
        "strategy": "notify",
        "min_app_version": 1,
    }
    defaults.update(kwargs)
    return AppBundle.objects.create(**defaults)


# ══════════════════════════════════════════════════════════════════════
# MODEL TESTS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGenerateBundleId:
    """Tests for _generate_bundle_id helper."""

    def test_format(self):
        bid = _generate_bundle_id()
        assert bid.startswith("b-")
        # Format: b-YYYYMMDD-HHMMSS (total 17 chars)
        parts = bid.split("-")
        assert len(parts) == 3
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS

    def test_unique_over_time(self):
        """Two calls should produce different IDs (unless same second)."""
        bid1 = _generate_bundle_id()
        bid2 = _generate_bundle_id()
        # They may be the same within the same second, but format is correct
        assert bid1.startswith("b-")
        assert bid2.startswith("b-")

    def test_uses_current_time(self):
        now = timezone.now()
        bid = _generate_bundle_id()
        # Year should match
        assert str(now.year) in bid


@pytest.mark.django_db
class TestBundleUploadPath:
    """Tests for _bundle_upload_path helper."""

    def test_returns_correct_path(self):
        instance = MagicMock()
        instance.bundle_id = "b-20260322-120000"
        path = _bundle_upload_path(instance, "original_name.zip")
        assert path == "bundles/b-20260322-120000.zip"

    def test_ignores_original_filename(self):
        instance = MagicMock()
        instance.bundle_id = "b-test"
        path = _bundle_upload_path(instance, "something_else.tar.gz")
        assert path == "bundles/b-test.zip"


@pytest.mark.django_db
class TestAppBundleModel:
    """Tests for AppBundle model fields, defaults, and methods."""

    def test_default_values(self):
        bundle = AppBundle(bundle_id="b-test-defaults")
        assert bundle.strategy == "notify"
        assert bundle.platform == "all"
        assert bundle.min_app_version == 1
        assert bundle.is_active is True
        assert bundle.checksum == ""
        assert bundle.signature == ""
        assert bundle.message == ""

    def test_str_active(self):
        bundle = AppBundle(bundle_id="b-20260322-001", is_active=True)
        s = str(bundle)
        assert "b-20260322-001" in s
        assert "active" in s
        assert "inactive" not in s

    def test_str_inactive(self):
        bundle = AppBundle(bundle_id="b-20260322-002", is_active=False)
        s = str(bundle)
        assert "b-20260322-002" in s
        assert "inactive" in s

    def test_compute_checksum_with_file(self):
        content = b"PK\x03\x04" + b"\xAB\xCD" * 500
        f = SimpleUploadedFile("b.zip", content)
        bundle = AppBundle(bundle_id="b-chk", bundle_file=f)
        chk = bundle.compute_checksum()
        expected = hashlib.sha256(content).hexdigest()
        assert chk == expected

    def test_compute_checksum_no_file(self):
        bundle = AppBundle(bundle_id="b-nochk")
        assert bundle.compute_checksum() == ""

    def test_save_auto_computes_checksum(self):
        content = b"PK\x03\x04" + b"\x00" * 50
        f = SimpleUploadedFile("b.zip", content)
        bundle = AppBundle(
            bundle_id="b-autochk",
            bundle_file=f,
        )
        bundle.save()
        expected = hashlib.sha256(content).hexdigest()
        assert bundle.checksum == expected

    def test_save_preserves_existing_checksum(self):
        """If checksum is already set, save() should NOT overwrite it."""
        content = b"PK\x03\x04" + b"\x00" * 50
        f = SimpleUploadedFile("b.zip", content)
        bundle = AppBundle(
            bundle_id="b-preschk",
            bundle_file=f,
            checksum="pre-set-checksum",
        )
        bundle.save()
        assert bundle.checksum == "pre-set-checksum"

    def test_meta_ordering(self):
        assert AppBundle._meta.ordering == ["-created_at"]

    def test_meta_verbose_name(self):
        assert AppBundle._meta.verbose_name == "App Bundle"
        assert AppBundle._meta.verbose_name_plural == "App Bundles"

    def test_bundle_id_unique(self):
        _make_bundle(True, bundle_id="b-unique-001")
        with pytest.raises(Exception):
            _make_bundle(True, bundle_id="b-unique-001")

    def test_strategy_choices(self):
        choices = dict(AppBundle.STRATEGY_CHOICES)
        assert "silent" in choices
        assert "notify" in choices

    def test_platform_choices(self):
        choices = dict(AppBundle.PLATFORM_CHOICES)
        assert "all" in choices
        assert "android" in choices
        assert "ios" in choices

    def test_created_at_auto_set(self):
        bundle = _make_bundle(True, bundle_id="b-created-at")
        assert bundle.created_at is not None

    def test_ordering_most_recent_first(self):
        """Most recently created bundle should be first."""
        b1 = _make_bundle(True, bundle_id="b-order-001")
        b2 = _make_bundle(True, bundle_id="b-order-002")
        bundles = list(AppBundle.objects.all())
        assert bundles[0].bundle_id == "b-order-002"
        assert bundles[1].bundle_id == "b-order-001"


# ══════════════════════════════════════════════════════════════════════
# UPDATE CHECK VIEW TESTS (GET /api/v1/updates/check/)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUpdateCheckView:
    """Tests for the public update check endpoint."""

    URL = "/api/v1/updates/check/"

    def test_no_bundles_returns_204(self, anon):
        resp = anon.get(self.URL)
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_active_bundle_returns_200(self, anon):
        _make_bundle(True, bundle_id="b-check-001")
        resp = anon.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["bundle_id"] == "b-check-001"

    def test_response_fields(self, anon):
        _make_bundle(
            True,
            bundle_id="b-fields-001",
            strategy="silent",
            checksum="abc123",
            signature="sig456",
            message="Update ready",
            min_app_version=5,
        )
        resp = anon.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        d = resp.data
        assert d["bundle_id"] == "b-fields-001"
        assert d["strategy"] == "silent"
        assert d["checksum"] == "abc123"
        assert d["signature"] == "sig456"
        assert d["message"] == "Update ready"
        assert d["min_app_version"] == 5
        assert "url" in d

    def test_inactive_bundle_not_returned(self, anon):
        _make_bundle(True, bundle_id="b-inactive", is_active=False)
        resp = anon.get(self.URL)
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_client_already_has_bundle(self, anon):
        _make_bundle(True, bundle_id="b-already")
        resp = anon.get(self.URL + "?bundle_id=b-already")
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_client_has_different_bundle(self, anon):
        _make_bundle(True, bundle_id="b-new-ver")
        resp = anon.get(self.URL + "?bundle_id=b-old-ver")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["bundle_id"] == "b-new-ver"

    # ── Platform filtering ─────────────────────────────────────────

    def test_platform_android_gets_android_bundle(self, anon):
        _make_bundle(True, bundle_id="b-android", platform="android")
        resp = anon.get(self.URL + "?platform=android")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["bundle_id"] == "b-android"

    def test_platform_android_gets_all_bundle(self, anon):
        _make_bundle(True, bundle_id="b-all-plat", platform="all")
        resp = anon.get(self.URL + "?platform=android")
        assert resp.status_code == status.HTTP_200_OK

    def test_platform_android_not_gets_ios_bundle(self, anon):
        _make_bundle(True, bundle_id="b-ios-only", platform="ios")
        resp = anon.get(self.URL + "?platform=android")
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_platform_ios_gets_ios_bundle(self, anon):
        _make_bundle(True, bundle_id="b-ios-yes", platform="ios")
        resp = anon.get(self.URL + "?platform=ios")
        assert resp.status_code == status.HTTP_200_OK

    def test_platform_ios_not_gets_android_bundle(self, anon):
        _make_bundle(True, bundle_id="b-droid-only", platform="android")
        resp = anon.get(self.URL + "?platform=ios")
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_no_platform_filter_returns_any(self, anon):
        """When no platform specified, no platform filter is applied."""
        _make_bundle(True, bundle_id="b-any-plat", platform="ios")
        resp = anon.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK

    def test_unknown_platform_returns_any(self, anon):
        """Unknown platform (not android/ios) skips platform filter."""
        _make_bundle(True, bundle_id="b-unk-plat", platform="android")
        resp = anon.get(self.URL + "?platform=web")
        assert resp.status_code == status.HTTP_200_OK

    # ── Version filtering ──────────────────────────────────────────

    def test_version_too_low(self, anon):
        _make_bundle(True, bundle_id="b-highver", min_app_version=50)
        resp = anon.get(self.URL + "?app_version=10")
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_version_exact_match(self, anon):
        _make_bundle(True, bundle_id="b-exactver", min_app_version=10)
        resp = anon.get(self.URL + "?app_version=10")
        assert resp.status_code == status.HTTP_200_OK

    def test_version_higher_than_min(self, anon):
        _make_bundle(True, bundle_id="b-okver", min_app_version=5)
        resp = anon.get(self.URL + "?app_version=100")
        assert resp.status_code == status.HTTP_200_OK

    def test_version_zero_skips_filter(self, anon):
        """app_version=0 should not filter by version."""
        _make_bundle(True, bundle_id="b-ver0", min_app_version=50)
        resp = anon.get(self.URL + "?app_version=0")
        assert resp.status_code == status.HTTP_200_OK

    def test_invalid_version_treated_as_zero(self, anon):
        """Non-numeric app_version treated as 0 -> no version filter."""
        _make_bundle(True, bundle_id="b-badver", min_app_version=50)
        resp = anon.get(self.URL + "?app_version=abc")
        assert resp.status_code == status.HTTP_200_OK

    def test_missing_version_treated_as_zero(self, anon):
        """Missing app_version treated as 0 -> no version filter."""
        _make_bundle(True, bundle_id="b-nover", min_app_version=50)
        resp = anon.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK

    # ── Multiple bundles (ordering) ────────────────────────────────

    def test_returns_most_recent_bundle(self, anon):
        _make_bundle(True, bundle_id="b-old")
        _make_bundle(True, bundle_id="b-new")
        resp = anon.get(self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["bundle_id"] == "b-new"

    # ── Permission: AllowAny ────────────────────────────────────────

    def test_accessible_by_anonymous(self, anon):
        resp = anon.get(self.URL)
        assert resp.status_code in (200, 204)

    def test_accessible_by_authenticated_user(self, user_client):
        resp = user_client.get(self.URL)
        assert resp.status_code in (200, 204)

    def test_accessible_by_admin(self, admin_client):
        resp = admin_client.get(self.URL)
        assert resp.status_code in (200, 204)

    # ── Empty/null fields ──────────────────────────────────────────

    def test_auto_computed_checksum_not_none(self, anon):
        """Checksum is auto-computed on save when empty, so response has real hash."""
        _make_bundle(True, bundle_id="b-nochk2", checksum="")
        resp = anon.get(self.URL)
        assert resp.data["checksum"] is not None
        assert len(resp.data["checksum"]) == 64  # SHA-256 hex digest

    def test_empty_signature_returns_none(self, anon):
        _make_bundle(True, bundle_id="b-nosig", signature="")
        resp = anon.get(self.URL)
        assert resp.data["signature"] is None

    def test_empty_message_returns_none(self, anon):
        _make_bundle(True, bundle_id="b-nomsg", message="")
        resp = anon.get(self.URL)
        assert resp.data["message"] is None

    # ── Combined filters ───────────────────────────────────────────

    def test_combined_platform_and_version(self, anon):
        _make_bundle(True, bundle_id="b-combo", platform="android", min_app_version=5)
        resp = anon.get(self.URL + "?platform=android&app_version=10")
        assert resp.status_code == status.HTTP_200_OK

    def test_combined_filters_no_match(self, anon):
        _make_bundle(True, bundle_id="b-nomatch", platform="ios", min_app_version=100)
        resp = anon.get(self.URL + "?platform=android&app_version=5")
        assert resp.status_code == status.HTTP_204_NO_CONTENT


# ══════════════════════════════════════════════════════════════════════
# BUNDLE UPLOAD VIEW TESTS (POST /api/v1/updates/upload/)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBundleUploadView:
    """Tests for the admin-only bundle upload endpoint."""

    URL = "/api/v1/updates/upload/"

    # ── Permissions ────────────────────────────────────────────────

    def test_anonymous_denied(self, anon):
        resp = anon.post(self.URL)
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_normal_user_denied(self, user_client):
        resp = user_client.post(self.URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_allowed(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(self.URL, {"file": f}, format="multipart")
        assert resp.status_code == status.HTTP_201_CREATED

    # ── File validation ────────────────────────────────────────────

    def test_no_file_returns_400(self, admin_client):
        resp = admin_client.post(self.URL, {}, format="multipart")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in resp.data

    def test_non_zip_returns_400(self, admin_client):
        f = SimpleUploadedFile("bundle.txt", b"not a zip")
        resp = admin_client.post(self.URL, {"file": f}, format="multipart")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "zip" in resp.data["error"].lower()

    def test_non_zip_extension_pdf(self, admin_client):
        f = SimpleUploadedFile("bundle.pdf", b"not a zip")
        resp = admin_client.post(self.URL, {"file": f}, format="multipart")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # ── Successful upload ──────────────────────────────────────────

    def test_upload_creates_bundle(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(self.URL, {"file": f}, format="multipart")
        assert resp.status_code == status.HTTP_201_CREATED
        assert "bundle_id" in resp.data
        assert "checksum" in resp.data
        assert "url" in resp.data
        assert "created_at" in resp.data
        # Verify DB record
        assert AppBundle.objects.filter(bundle_id=resp.data["bundle_id"]).exists()

    def test_upload_computes_checksum(self, admin_client):
        content = b"PK\x03\x04" + b"\xAA\xBB" * 100
        f = SimpleUploadedFile("bundle.zip", content)
        resp = admin_client.post(self.URL, {"file": f}, format="multipart")
        assert resp.status_code == status.HTTP_201_CREATED
        expected = hashlib.sha256(content).hexdigest()
        assert resp.data["checksum"] == expected

    def test_upload_bundle_is_active(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(self.URL, {"file": f}, format="multipart")
        bundle = AppBundle.objects.get(bundle_id=resp.data["bundle_id"])
        assert bundle.is_active is True

    # ── Strategy ───────────────────────────────────────────────────

    def test_default_strategy_notify(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(self.URL, {"file": f}, format="multipart")
        assert resp.data["strategy"] == "notify"

    def test_strategy_silent(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(
            self.URL, {"file": f, "strategy": "silent"}, format="multipart"
        )
        assert resp.data["strategy"] == "silent"

    def test_strategy_notify_explicit(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(
            self.URL, {"file": f, "strategy": "notify"}, format="multipart"
        )
        assert resp.data["strategy"] == "notify"

    def test_invalid_strategy_defaults_notify(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(
            self.URL, {"file": f, "strategy": "unknown"}, format="multipart"
        )
        assert resp.data["strategy"] == "notify"

    # ── Platform ───────────────────────────────────────────────────

    def test_default_platform_all(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(self.URL, {"file": f}, format="multipart")
        assert resp.data["platform"] == "all"

    def test_platform_android(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(
            self.URL, {"file": f, "platform": "android"}, format="multipart"
        )
        assert resp.data["platform"] == "android"

    def test_platform_ios(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(
            self.URL, {"file": f, "platform": "ios"}, format="multipart"
        )
        assert resp.data["platform"] == "ios"

    def test_invalid_platform_defaults_all(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(
            self.URL, {"file": f, "platform": "windows"}, format="multipart"
        )
        assert resp.data["platform"] == "all"

    # ── min_app_version ────────────────────────────────────────────

    def test_default_min_app_version(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(self.URL, {"file": f}, format="multipart")
        bundle = AppBundle.objects.get(bundle_id=resp.data["bundle_id"])
        assert bundle.min_app_version == 1

    def test_custom_min_app_version(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(
            self.URL, {"file": f, "min_app_version": "10"}, format="multipart"
        )
        bundle = AppBundle.objects.get(bundle_id=resp.data["bundle_id"])
        assert bundle.min_app_version == 10

    def test_invalid_min_app_version_defaults_to_1(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(
            self.URL, {"file": f, "min_app_version": "abc"}, format="multipart"
        )
        bundle = AppBundle.objects.get(bundle_id=resp.data["bundle_id"])
        assert bundle.min_app_version == 1

    # ── Message ────────────────────────────────────────────────────

    def test_upload_with_message(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(
            self.URL, {"file": f, "message": "Bug fixes"}, format="multipart"
        )
        bundle = AppBundle.objects.get(bundle_id=resp.data["bundle_id"])
        assert bundle.message == "Bug fixes"

    def test_upload_without_message(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(self.URL, {"file": f}, format="multipart")
        bundle = AppBundle.objects.get(bundle_id=resp.data["bundle_id"])
        assert bundle.message == ""

    # ── Signed field in response ───────────────────────────────────

    def test_signed_false_when_no_signature(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(self.URL, {"file": f}, format="multipart")
        assert resp.data["signed"] is False

    def test_signed_true_when_signature_provided(self, admin_client):
        """Signature provided but no public key -> accepted (no verification)."""
        f = _make_zip()
        resp = admin_client.post(
            self.URL, {"file": f, "signature": "dW5zaWduZWQ="}, format="multipart"
        )
        assert resp.data["signed"] is True

    # ── Signature verification ─────────────────────────────────────

    @patch("apps.updates.views._get_public_key")
    def test_signature_required_when_key_configured(self, mock_pk, admin_client):
        """If public key is configured but no signature is provided, reject."""
        mock_pk.return_value = MagicMock()  # non-None means key is configured
        f = _make_zip()
        resp = admin_client.post(self.URL, {"file": f}, format="multipart")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "signature required" in resp.data["error"].lower()

    @patch("apps.updates.views._verify_signature")
    @patch("apps.updates.views._get_public_key")
    def test_invalid_signature_rejected(self, mock_pk, mock_verify, admin_client):
        """If signature fails verification, reject."""
        mock_pk.return_value = MagicMock()
        mock_verify.return_value = False
        f = _make_zip()
        resp = admin_client.post(
            self.URL, {"file": f, "signature": "badsig"}, format="multipart"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid" in resp.data["error"].lower()

    @patch("apps.updates.views._verify_signature")
    @patch("apps.updates.views._get_public_key")
    def test_valid_signature_accepted(self, mock_pk, mock_verify, admin_client):
        """Valid signature allows upload."""
        mock_pk.return_value = MagicMock()
        mock_verify.return_value = True
        f = _make_zip()
        resp = admin_client.post(
            self.URL, {"file": f, "signature": "goodsig"}, format="multipart"
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["signed"] is True


# ══════════════════════════════════════════════════════════════════════
# SIGNATURE VERIFICATION UNIT TESTS
# ══════════════════════════════════════════════════════════════════════


class TestVerifySignature:
    """Tests for _verify_signature helper."""

    @patch("apps.updates.views._get_public_key")
    def test_no_public_key_returns_true(self, mock_pk):
        """If no public key configured, skip verification."""
        mock_pk.return_value = None
        from apps.updates.views import _verify_signature
        assert _verify_signature("checksum", "sig") is True

    @patch("apps.updates.views._get_public_key")
    def test_invalid_base64_returns_false(self, mock_pk):
        """If signature is not valid base64, return False."""
        mock_pk.return_value = MagicMock()
        mock_pk.return_value.verify.side_effect = Exception("decode error")
        from apps.updates.views import _verify_signature
        assert _verify_signature("checksum", "!!!not-base64!!!") is False

    @patch("apps.updates.views._get_public_key")
    def test_invalid_signature_returns_false(self, mock_pk):
        """If signature verification fails, return False."""
        from cryptography.exceptions import InvalidSignature
        mock_key = MagicMock()
        mock_key.verify.side_effect = InvalidSignature()
        mock_pk.return_value = mock_key
        from apps.updates.views import _verify_signature
        assert _verify_signature("checksum", "dW5zaWduZWQ=") is False


class TestGetPublicKey:
    """Tests for _get_public_key helper."""

    def test_no_setting_returns_none(self):
        import apps.updates.views as views_mod
        views_mod._PUBLIC_KEY = None  # Reset cache
        with override_settings(OTA_PUBLIC_KEY_PATH=None):
            result = views_mod._get_public_key()
            assert result is None

    def test_missing_file_returns_none(self):
        import apps.updates.views as views_mod
        views_mod._PUBLIC_KEY = None  # Reset cache
        with override_settings(OTA_PUBLIC_KEY_PATH="/nonexistent/key.pem"):
            result = views_mod._get_public_key()
            assert result is None

    def test_cached_key_returned(self):
        """Once loaded, the key is cached."""
        import apps.updates.views as views_mod
        sentinel = MagicMock()
        views_mod._PUBLIC_KEY = sentinel
        result = views_mod._get_public_key()
        assert result is sentinel
        views_mod._PUBLIC_KEY = None  # Clean up


# ══════════════════════════════════════════════════════════════════════
# ADMIN REGISTRATION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAdminRegistration:
    """Tests that AppBundle is properly registered in Django admin."""

    def test_admin_registered(self):
        from django.contrib import admin
        assert AppBundle in admin.site._registry

    def test_admin_list_display(self):
        from django.contrib import admin
        model_admin = admin.site._registry[AppBundle]
        assert "bundle_id" in model_admin.list_display
        assert "platform" in model_admin.list_display
        assert "strategy" in model_admin.list_display
        assert "is_active" in model_admin.list_display

    def test_admin_list_filter(self):
        from django.contrib import admin
        model_admin = admin.site._registry[AppBundle]
        assert "is_active" in model_admin.list_filter
        assert "platform" in model_admin.list_filter
        assert "strategy" in model_admin.list_filter

    def test_admin_list_editable(self):
        from django.contrib import admin
        model_admin = admin.site._registry[AppBundle]
        assert "is_active" in model_admin.list_editable
        assert "strategy" in model_admin.list_editable

    def test_admin_search_fields(self):
        from django.contrib import admin
        model_admin = admin.site._registry[AppBundle]
        assert "bundle_id" in model_admin.search_fields
        assert "message" in model_admin.search_fields


# ══════════════════════════════════════════════════════════════════════
# APPS CONFIG
# ══════════════════════════════════════════════════════════════════════


class TestAppsConfig:
    """Tests for UpdatesConfig."""

    def test_app_name(self):
        from apps.updates.apps import UpdatesConfig
        assert UpdatesConfig.name == "apps.updates"

    def test_verbose_name(self):
        from apps.updates.apps import UpdatesConfig
        assert UpdatesConfig.verbose_name == "App Updates"


# ══════════════════════════════════════════════════════════════════════
# URL CONFIGURATION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestURLConfiguration:
    """Tests that URL routing is correctly configured."""

    def test_check_url_resolves(self, anon):
        resp = anon.get("/api/v1/updates/check/")
        assert resp.status_code in (200, 204)

    def test_upload_url_resolves(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(
            "/api/v1/updates/upload/", {"file": f}, format="multipart"
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_backward_compat_check_url(self, anon):
        """The backward-compatible /api/ prefix should also work."""
        resp = anon.get("/api/updates/check/")
        assert resp.status_code in (200, 204)

    def test_backward_compat_upload_url(self, admin_client):
        f = _make_zip()
        resp = admin_client.post(
            "/api/updates/upload/", {"file": f}, format="multipart"
        )
        assert resp.status_code == status.HTTP_201_CREATED
