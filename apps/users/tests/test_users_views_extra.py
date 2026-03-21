"""
Extra integration tests for apps/users/views.py — targeting 90%+ coverage.

Covers:
- 2FA full flow (setup, verify, disable, status, backup-codes)
- Avatar upload (valid, invalid type, too large, magic byte mismatch)
- Change email (with password, with 2FA)
- Delete account (soft-delete flow)
- Export data (JSON and CSV)
- Notification preferences
- Energy profile (GET and PUT)
- Motivation (mock OpenAI)
- Onboarding completion
- Persona update
- Public profile vs private profile
- Dashboard, streak details, achievements
- Daily quote, personality quiz, profile completeness
- Notification timing (PUT apply, GET with mock AI)
- Morning briefing
"""

import io
import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

import pyotp
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.dreams.models import Dream, Goal, Task
from apps.friends.models import BlockedUser, Friendship
from apps.notifications.models import Notification
from apps.users.models import (
    Achievement,
    DailyActivity,
    EmailChangeRequest,
    GamificationProfile,
    User,
    UserAchievement,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_png_bytes():
    """Return minimal valid PNG bytes."""
    return (
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        + b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00"
        b"\x00\x00\x00IEND\xaeB`\x82"
    )


def _make_jpeg_bytes():
    """Return minimal valid JPEG bytes."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100


def _make_gif_bytes():
    """Return minimal valid GIF bytes."""
    return b"GIF89a" + b"\x00" * 100


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def xuser(db):
    """Primary test user for extra views tests."""
    return User.objects.create_user(
        email="xtest@example.com",
        password="testpassword123",
        display_name="X Test User",
        timezone="Europe/Paris",
    )


@pytest.fixture
def xclient(xuser):
    client = APIClient()
    client.force_authenticate(user=xuser)
    return client


@pytest.fixture
def xuser2(db):
    """Second test user."""
    return User.objects.create_user(
        email="xtest2@example.com",
        password="testpassword123",
        display_name="X Test User 2",
        timezone="Europe/Paris",
        profile_visibility="public",
    )


@pytest.fixture
def xclient2(xuser2):
    client = APIClient()
    client.force_authenticate(user=xuser2)
    return client


@pytest.fixture
def premium_xuser(xuser):
    """Give xuser a premium subscription for AI access."""
    from decimal import Decimal
    from apps.subscriptions.models import Subscription, SubscriptionPlan

    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="premium",
        defaults={
            "name": "Premium",
            "price_monthly": Decimal("19.99"),
            "has_ai": True,
            "has_buddy": True,
            "has_circles": True,
            "is_active": True,
        },
    )
    Subscription.objects.update_or_create(
        user=xuser,
        defaults={"plan": plan, "status": "active"},
    )
    return xuser


@pytest.fixture
def premium_xclient(premium_xuser):
    client = APIClient()
    client.force_authenticate(user=premium_xuser)
    return client


# ══════════════════════════════════════════════════════════════════════
#  2FA FULL FLOW
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class Test2FAFullFlow:
    """Full 2FA lifecycle: setup -> verify -> backup codes -> disable."""

    def test_setup_2fa_returns_secret_and_uri(self, xclient, xuser):
        """POST /api/users/2fa/setup/ returns secret + provisioning_uri."""
        response = xclient.post("/api/users/2fa/setup/")
        assert response.status_code == status.HTTP_200_OK
        assert "secret" in response.data
        assert "provisioning_uri" in response.data
        xuser.refresh_from_db()
        assert xuser.totp_secret == response.data["secret"]

    def test_setup_2fa_generates_new_secret(self, xclient, xuser):
        """Each setup call generates a new secret."""
        r1 = xclient.post("/api/users/2fa/setup/")
        r2 = xclient.post("/api/users/2fa/setup/")
        assert r1.data["secret"] != r2.data["secret"]

    def test_verify_2fa_setup_success(self, xclient, xuser):
        """Verify setup with correct TOTP code enables 2FA."""
        # Run setup first to set pending flag
        xclient.post("/api/users/2fa/setup/")
        xuser.refresh_from_db()
        secret = xuser.totp_secret

        totp = pyotp.TOTP(secret)
        code = totp.now()
        response = xclient.post(
            "/api/users/2fa/verify/", {"code": code}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["verified"] is True
        xuser.refresh_from_db()
        assert xuser.totp_enabled is True

    def test_verify_2fa_setup_wrong_code(self, xclient, xuser):
        """Verify setup with wrong code returns 400."""
        xclient.post("/api/users/2fa/setup/")
        response = xclient.post(
            "/api/users/2fa/verify/", {"code": "000000"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_2fa_no_secret(self, xclient, xuser):
        """Verify without prior setup returns 400."""
        xuser.totp_secret = ""
        xuser.save(update_fields=["totp_secret"])
        response = xclient.post(
            "/api/users/2fa/verify/", {"code": "123456"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_2fa_empty_code(self, xclient, xuser):
        """Verify with empty code returns 400."""
        xclient.post("/api/users/2fa/setup/")
        response = xclient.post(
            "/api/users/2fa/verify/", {"code": ""}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_disable_2fa_success(self, xclient, xuser):
        """Disable 2FA with correct password."""
        xuser.totp_secret = pyotp.random_base32()
        xuser.totp_enabled = True
        xuser.save(update_fields=["totp_secret", "totp_enabled"])

        response = xclient.post(
            "/api/users/2fa/disable/",
            {"password": "testpassword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["two_factor_enabled"] is False
        xuser.refresh_from_db()
        assert xuser.totp_enabled is False
        assert xuser.totp_secret == ""

    def test_disable_2fa_wrong_password(self, xclient, xuser):
        """Disable 2FA with wrong password returns 400."""
        xuser.totp_secret = pyotp.random_base32()
        xuser.totp_enabled = True
        xuser.save(update_fields=["totp_secret", "totp_enabled"])
        response = xclient.post(
            "/api/users/2fa/disable/",
            {"password": "wrongpass"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_2fa_status(self, xclient, xuser):
        """GET /api/users/2fa/status/ returns 2FA status."""
        response = xclient.get("/api/users/2fa/status/")
        assert response.status_code == status.HTTP_200_OK
        assert "two_factor_enabled" in response.data
        assert "backup_codes_remaining" in response.data

    def test_2fa_status_enabled(self, xclient, xuser):
        """2FA status shows enabled when active."""
        xuser.totp_secret = pyotp.random_base32()
        xuser.totp_enabled = True
        xuser.backup_codes = ["hash1", "hash2"]
        xuser.save(update_fields=["totp_secret", "totp_enabled", "backup_codes"])
        response = xclient.get("/api/users/2fa/status/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["two_factor_enabled"] is True
        assert response.data["backup_codes_remaining"] == 2

    def test_generate_backup_codes(self, xclient, xuser):
        """Generate backup codes when 2FA is enabled."""
        xuser.totp_secret = pyotp.random_base32()
        xuser.totp_enabled = True
        xuser.save(update_fields=["totp_secret", "totp_enabled"])

        response = xclient.post(
            "/api/users/2fa/backup-codes/",
            {"password": "testpassword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "backup_codes" in response.data
        assert len(response.data["backup_codes"]) == 10

    def test_generate_backup_codes_wrong_password(self, xclient, xuser):
        """Backup codes with wrong password returns 400."""
        xuser.totp_secret = pyotp.random_base32()
        xuser.totp_enabled = True
        xuser.save(update_fields=["totp_secret", "totp_enabled"])

        response = xclient.post(
            "/api/users/2fa/backup-codes/",
            {"password": "wrongpass"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════════
#  AVATAR UPLOAD
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAvatarUpload:
    """Tests for POST /api/users/upload_avatar/"""

    def test_upload_valid_png(self, xclient, xuser):
        """Upload a valid PNG avatar."""
        avatar = SimpleUploadedFile(
            "avatar.png", _make_png_bytes(), content_type="image/png"
        )
        response = xclient.post("/api/users/upload_avatar/", {"avatar": avatar})
        assert response.status_code == status.HTTP_200_OK
        xuser.refresh_from_db()
        assert xuser.avatar_image

    def test_upload_valid_jpeg(self, xclient, xuser):
        """Upload a valid JPEG avatar."""
        avatar = SimpleUploadedFile(
            "avatar.jpg", _make_jpeg_bytes(), content_type="image/jpeg"
        )
        response = xclient.post("/api/users/upload_avatar/", {"avatar": avatar})
        assert response.status_code == status.HTTP_200_OK

    def test_upload_valid_gif(self, xclient, xuser):
        """Upload a valid GIF avatar."""
        avatar = SimpleUploadedFile(
            "avatar.gif", _make_gif_bytes(), content_type="image/gif"
        )
        response = xclient.post("/api/users/upload_avatar/", {"avatar": avatar})
        assert response.status_code == status.HTTP_200_OK

    def test_upload_no_file(self, xclient):
        """Upload without a file returns 400."""
        response = xclient.post("/api/users/upload_avatar/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_invalid_content_type(self, xclient):
        """Upload with invalid content type returns 400."""
        avatar = SimpleUploadedFile(
            "avatar.txt", b"not an image", content_type="text/plain"
        )
        response = xclient.post("/api/users/upload_avatar/", {"avatar": avatar})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_too_large(self, xclient):
        """Upload file over 5MB returns 400."""
        big_data = _make_png_bytes() + b"\x00" * (6 * 1024 * 1024)
        avatar = SimpleUploadedFile(
            "avatar.png", big_data, content_type="image/png"
        )
        response = xclient.post("/api/users/upload_avatar/", {"avatar": avatar})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_magic_bytes_mismatch(self, xclient):
        """Upload with valid content-type but wrong magic bytes returns 400."""
        avatar = SimpleUploadedFile(
            "avatar.png", b"this is not a real png", content_type="image/png"
        )
        response = xclient.post("/api/users/upload_avatar/", {"avatar": avatar})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_replaces_old_avatar(self, xclient, xuser):
        """Uploading a new avatar replaces the old one."""
        avatar1 = SimpleUploadedFile(
            "avatar1.png", _make_png_bytes(), content_type="image/png"
        )
        xclient.post("/api/users/upload_avatar/", {"avatar": avatar1})
        xuser.refresh_from_db()
        first_name = xuser.avatar_image.name

        avatar2 = SimpleUploadedFile(
            "avatar2.png", _make_png_bytes(), content_type="image/png"
        )
        xclient.post("/api/users/upload_avatar/", {"avatar": avatar2})
        xuser.refresh_from_db()
        assert xuser.avatar_image.name != first_name


# ══════════════════════════════════════════════════════════════════════
#  CHANGE EMAIL
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestChangeEmail:
    """Tests for POST /api/users/change-email/"""

    @patch("apps.users.views.UserViewSet.change_email")
    def _skip_celery(self):
        pass

    def test_change_email_success(self, xclient, xuser):
        """Change email with correct password sends verification."""
        with patch("apps.users.tasks.send_email_change_verification.delay") as mock_task:
            response = xclient.post(
                "/api/users/change-email/",
                {"new_email": "new@example.com", "password": "testpassword123"},
                format="json",
            )
        assert response.status_code == status.HTTP_200_OK
        assert EmailChangeRequest.objects.filter(
            user=xuser, new_email="new@example.com"
        ).exists()

    def test_change_email_missing_email(self, xclient):
        """Missing new_email returns 400."""
        response = xclient.post(
            "/api/users/change-email/",
            {"password": "testpassword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_email_wrong_password(self, xclient):
        """Wrong password returns 400."""
        response = xclient.post(
            "/api/users/change-email/",
            {"new_email": "new@example.com", "password": "wrongpass"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_email_already_taken(self, xclient, xuser2):
        """Email already in use returns 400."""
        response = xclient.post(
            "/api/users/change-email/",
            {"new_email": xuser2.email, "password": "testpassword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_email_with_2fa(self, xclient, xuser):
        """Change email when 2FA is enabled requires TOTP code."""
        secret = pyotp.random_base32()
        xuser.totp_secret = secret
        xuser.totp_enabled = True
        xuser.save(update_fields=["totp_secret", "totp_enabled"])

        # Without code
        response = xclient.post(
            "/api/users/change-email/",
            {"new_email": "new2fa@example.com", "password": "testpassword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # With wrong code
        response = xclient.post(
            "/api/users/change-email/",
            {
                "new_email": "new2fa@example.com",
                "password": "testpassword123",
                "totp_code": "000000",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # With correct code
        totp = pyotp.TOTP(secret)
        with patch("apps.users.tasks.send_email_change_verification.delay"):
            response = xclient.post(
                "/api/users/change-email/",
                {
                    "new_email": "new2fa@example.com",
                    "password": "testpassword123",
                    "totp_code": totp.now(),
                },
                format="json",
            )
        assert response.status_code == status.HTTP_200_OK


# ══════════════════════════════════════════════════════════════════════
#  DELETE ACCOUNT
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDeleteAccountExtra:
    """Additional delete account tests."""

    @patch("apps.subscriptions.services.StripeService.cancel_subscription")
    def test_delete_account_anonymizes_data(self, mock_stripe, xclient, xuser):
        """Soft delete anonymizes personal data."""
        xuser.bio = "My bio"
        xuser.location = "Paris"
        xuser.save(update_fields=["bio", "location"])

        response = xclient.post(
            "/api/users/delete-account/",
            {"password": "testpassword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        xuser.refresh_from_db()
        assert xuser.is_active is False
        assert xuser.display_name == "Deleted User"
        assert "deleted_" in xuser.email
        assert xuser.bio == ""
        assert xuser.location == ""
        assert xuser.deactivated_at is not None

    def test_delete_account_no_password(self, xclient):
        """Delete without password returns 400."""
        response = xclient.post(
            "/api/users/delete-account/", {}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════════
#  EXPORT DATA
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestExportData:
    """Tests for GET /api/users/export-data/"""

    def test_export_json(self, xclient, xuser):
        """Export data as JSON."""
        Dream.objects.create(
            user=xuser, title="Test Dream", status="active", category="education"
        )
        response = xclient.get("/api/users/export-data/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert "profile" in data
        assert "dreams" in data
        assert data["profile"]["email"] == xuser.email

    def test_export_csv(self, xclient, xuser):
        """Export data as CSV."""
        dream = Dream.objects.create(
            user=xuser, title="CSV Dream", status="active", category="career"
        )
        goal = Goal.objects.create(dream=dream, title="Goal 1", order=0)
        Task.objects.create(goal=goal, title="Task 1", order=0, duration_mins=30)

        response = xclient.get("/api/users/export-data/?export_format=csv")
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "text/csv"
        content = response.content.decode("utf-8")
        assert "dream_title" in content
        assert "CSV Dream" in content

    def test_export_csv_dream_no_goals(self, xclient, xuser):
        """CSV export handles dreams without goals."""
        Dream.objects.create(
            user=xuser, title="No Goal Dream", status="active", category="health"
        )
        response = xclient.get("/api/users/export-data/?export_format=csv")
        assert response.status_code == status.HTTP_200_OK
        assert "No Goal Dream" in response.content.decode("utf-8")

    def test_export_csv_goal_no_tasks(self, xclient, xuser):
        """CSV export handles goals without tasks."""
        dream = Dream.objects.create(
            user=xuser, title="NoTask Dream", status="active", category="finance"
        )
        Goal.objects.create(dream=dream, title="Empty Goal", order=0)
        response = xclient.get("/api/users/export-data/?export_format=csv")
        assert response.status_code == status.HTTP_200_OK
        assert "Empty Goal" in response.content.decode("utf-8")

    def test_export_with_achievements(self, xclient, xuser):
        """Export includes achievements."""
        ach = Achievement.objects.create(
            name="Test Ach",
            description="Desc",
            icon="star",
            category="general",
            xp_reward=10,
            condition_type="dreams_created",
            condition_value=1,
        )
        UserAchievement.objects.create(user=xuser, achievement=ach, progress=1)
        response = xclient.get("/api/users/export-data/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["achievements"]) >= 1


# ══════════════════════════════════════════════════════════════════════
#  NOTIFICATION PREFERENCES
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotificationPreferences:
    """Tests for PUT /api/users/notification-preferences/"""

    def test_update_prefs_success(self, xclient, xuser):
        """Update notification preferences."""
        response = xclient.put(
            "/api/users/notification-preferences/",
            {"push_enabled": True, "email_enabled": False},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        xuser.refresh_from_db()
        assert xuser.notification_prefs["push_enabled"] is True
        assert xuser.notification_prefs["email_enabled"] is False

    def test_update_prefs_merges_existing(self, xclient, xuser):
        """Prefs merge with existing values."""
        xuser.notification_prefs = {"push_enabled": True}
        xuser.save(update_fields=["notification_prefs"])

        response = xclient.put(
            "/api/users/notification-preferences/",
            {"email_enabled": True},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        xuser.refresh_from_db()
        assert xuser.notification_prefs["push_enabled"] is True
        assert xuser.notification_prefs["email_enabled"] is True

    def test_update_prefs_invalid_value(self, xclient):
        """Non-boolean value returns 400."""
        response = xclient.put(
            "/api/users/notification-preferences/",
            {"push_enabled": "yes"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_prefs_not_dict(self, xclient):
        """Non-dict body returns 400."""
        response = xclient.put(
            "/api/users/notification-preferences/",
            data="not a dict",
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_prefs_unknown_keys_ignored(self, xclient, xuser):
        """Unknown keys are silently ignored."""
        response = xclient.put(
            "/api/users/notification-preferences/",
            {"push_enabled": True, "unknown_key": True},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        xuser.refresh_from_db()
        assert "unknown_key" not in xuser.notification_prefs


# ══════════════════════════════════════════════════════════════════════
#  ENERGY PROFILE
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEnergyProfile:
    """Tests for GET/PUT /api/users/energy-profile/"""

    def test_get_energy_profile_default(self, xclient):
        """GET returns default energy profile."""
        response = xclient.get("/api/users/energy-profile/")
        assert response.status_code == status.HTTP_200_OK
        assert "energy_profile" in response.data
        assert response.data["energy_profile"]["energy_pattern"] == "steady"

    def test_put_energy_profile_success(self, xclient, xuser):
        """PUT sets energy profile."""
        data = {
            "peak_hours": [{"start": 9, "end": 12}],
            "low_energy_hours": [{"start": 14, "end": 16}],
            "energy_pattern": "morning_person",
        }
        response = xclient.put(
            "/api/users/energy-profile/", data, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        xuser.refresh_from_db()
        assert xuser.energy_profile["energy_pattern"] == "morning_person"

    def test_put_energy_profile_invalid_pattern(self, xclient):
        """Invalid energy pattern returns 400."""
        response = xclient.put(
            "/api/users/energy-profile/",
            {"energy_pattern": "invalid", "peak_hours": [], "low_energy_hours": []},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_energy_profile_not_dict(self, xclient):
        """Non-dict body returns 400."""
        response = xclient.put(
            "/api/users/energy-profile/",
            data="not json",
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_energy_profile_invalid_hours(self, xclient):
        """Invalid hour ranges return 400."""
        # start >= end
        response = xclient.put(
            "/api/users/energy-profile/",
            {
                "peak_hours": [{"start": 12, "end": 9}],
                "low_energy_hours": [],
                "energy_pattern": "steady",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_energy_profile_hours_out_of_range(self, xclient):
        """Hours outside 0-23 return 400."""
        response = xclient.put(
            "/api/users/energy-profile/",
            {
                "peak_hours": [{"start": 0, "end": 25}],
                "low_energy_hours": [],
                "energy_pattern": "steady",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_energy_profile_hours_not_list(self, xclient):
        """Non-list peak_hours returns 400."""
        response = xclient.put(
            "/api/users/energy-profile/",
            {
                "peak_hours": "not a list",
                "low_energy_hours": [],
                "energy_pattern": "steady",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_energy_profile_range_not_dict(self, xclient):
        """Non-dict range in peak_hours returns 400."""
        response = xclient.put(
            "/api/users/energy-profile/",
            {
                "peak_hours": ["not a dict"],
                "low_energy_hours": [],
                "energy_pattern": "steady",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_energy_profile_range_non_int(self, xclient):
        """Non-int start/end in range returns 400."""
        response = xclient.put(
            "/api/users/energy-profile/",
            {
                "peak_hours": [{"start": "nine", "end": 12}],
                "low_energy_hours": [],
                "energy_pattern": "steady",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_energy_profile_too_many_ranges(self, xclient):
        """More than 10 ranges returns 400."""
        ranges = [{"start": i, "end": i + 1} for i in range(11)]
        response = xclient.put(
            "/api/users/energy-profile/",
            {
                "peak_hours": ranges,
                "low_energy_hours": [],
                "energy_pattern": "steady",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════════
#  MOTIVATION (AI)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMotivation:
    """Tests for POST /api/users/motivation/"""

    def test_motivation_invalid_mood(self, premium_xclient):
        """Invalid mood returns 400."""
        response = premium_xclient.post(
            "/api/users/motivation/",
            {"mood": "angry"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("integrations.openai_service.OpenAIService.generate_motivation")
    def test_motivation_success(self, mock_gen, premium_xclient, premium_xuser):
        """Valid mood with AI returns motivation."""
        mock_gen.return_value = {
            "message": "Keep going!",
            "mood_emoji": "fire",
        }
        Dream.objects.create(
            user=premium_xuser, title="Active Dream", status="active"
        )
        response = premium_xclient.post(
            "/api/users/motivation/",
            {"mood": "tired"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.data

    def test_motivation_requires_ai_permission(self, xclient):
        """Free user gets 403 on motivation endpoint."""
        response = xclient.post(
            "/api/users/motivation/",
            {"mood": "neutral"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ══════════════════════════════════════════════════════════════════════
#  ONBOARDING
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestOnboarding:
    """Tests for POST /api/users/complete-onboarding/"""

    def test_complete_onboarding(self, xclient, xuser):
        """Complete onboarding sets flag."""
        assert not xuser.onboarding_completed
        response = xclient.post("/api/users/complete-onboarding/")
        assert response.status_code == status.HTTP_200_OK
        xuser.refresh_from_db()
        assert xuser.onboarding_completed is True


# ══════════════════════════════════════════════════════════════════════
#  PERSONA
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPersona:
    """Tests for GET/PUT /api/users/persona/"""

    def test_get_persona_default(self, xclient):
        """GET returns empty persona."""
        response = xclient.get("/api/users/persona/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["persona"] == {}

    def test_put_persona(self, xclient, xuser):
        """PUT sets persona data."""
        response = xclient.put(
            "/api/users/persona/",
            {
                "available_hours_per_week": 20,
                "preferred_schedule": "morning",
                "occupation": "Engineer",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        xuser.refresh_from_db()
        assert xuser.persona["available_hours_per_week"] == 20
        assert xuser.persona["preferred_schedule"] == "morning"

    def test_put_persona_not_dict(self, xclient):
        """Non-dict body returns 400."""
        response = xclient.put(
            "/api/users/persona/",
            data='"string"',
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_persona_clamps_hours(self, xclient, xuser):
        """available_hours_per_week is clamped to 0-168."""
        response = xclient.put(
            "/api/users/persona/",
            {"available_hours_per_week": 500},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        xuser.refresh_from_db()
        assert xuser.persona["available_hours_per_week"] == 168

    def test_put_persona_ignores_unknown_keys(self, xclient, xuser):
        """Unknown keys are ignored."""
        response = xclient.put(
            "/api/users/persona/",
            {"unknown_key": "value", "occupation": "Dev"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        xuser.refresh_from_db()
        assert "unknown_key" not in xuser.persona
        assert xuser.persona["occupation"] == "Dev"

    def test_put_persona_long_text_truncated(self, xclient, xuser):
        """Text values are capped at 500 chars."""
        long_text = "A" * 600
        response = xclient.put(
            "/api/users/persona/",
            {"occupation": long_text},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        xuser.refresh_from_db()
        assert len(xuser.persona["occupation"]) == 500


# ══════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDashboard:
    """Tests for GET /api/users/dashboard/"""

    def test_dashboard_success(self, xclient, xuser):
        """Dashboard returns heatmap, stats, tasks, dreams."""
        response = xclient.get("/api/users/dashboard/")
        assert response.status_code == status.HTTP_200_OK
        assert "heatmap" in response.data
        assert "stats" in response.data
        assert "upcoming_tasks" in response.data
        assert "top_dreams" in response.data
        assert len(response.data["heatmap"]) == 28

    def test_dashboard_with_activity(self, xclient, xuser):
        """Dashboard reflects daily activity."""
        from datetime import date

        DailyActivity.objects.create(
            user=xuser,
            date=date.today(),
            tasks_completed=3,
            xp_earned=50,
            minutes_active=45,
        )
        response = xclient.get("/api/users/dashboard/")
        assert response.status_code == status.HTTP_200_OK


# ══════════════════════════════════════════════════════════════════════
#  STREAK DETAILS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStreakDetails:
    """Tests for GET /api/users/streak-details/"""

    def test_streak_details(self, xclient, xuser):
        """Returns streak info."""
        response = xclient.get("/api/users/streak-details/")
        assert response.status_code == status.HTTP_200_OK
        assert "current_streak" in response.data
        assert "longest_streak" in response.data
        assert "streak_history" in response.data
        assert len(response.data["streak_history"]) == 14

    def test_streak_details_with_activity(self, xclient, xuser):
        """Streak history reflects activity."""
        from datetime import date, timedelta

        today = date.today()
        for i in range(3):
            DailyActivity.objects.create(
                user=xuser,
                date=today - timedelta(days=i),
                tasks_completed=1,
                xp_earned=10,
                minutes_active=20,
            )
        xuser.streak_days = 3
        xuser.save(update_fields=["streak_days"])

        response = xclient.get("/api/users/streak-details/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["current_streak"] == 3

    def test_streak_frozen_detection(self, xclient, xuser):
        """Streak frozen when yesterday had no activity but streak > 0."""
        xuser.streak_days = 5
        xuser.save(update_fields=["streak_days"])
        response = xclient.get("/api/users/streak-details/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["streak_frozen"] is True


# ══════════════════════════════════════════════════════════════════════
#  ACHIEVEMENTS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAchievements:
    """Tests for GET /api/users/achievements/"""

    def test_achievements_empty(self, xclient):
        """Returns achievements even when none exist."""
        response = xclient.get("/api/users/achievements/")
        assert response.status_code == status.HTTP_200_OK
        assert "achievements" in response.data
        assert "unlocked_count" in response.data
        assert "total_count" in response.data

    def test_achievements_with_unlocked(self, xclient, xuser):
        """Unlocked achievements appear in the list."""
        ach = Achievement.objects.create(
            name="First Dream",
            description="Create your first dream",
            icon="star",
            category="dreams",
            xp_reward=10,
            condition_type="first_dream",
            condition_value=1,
        )
        UserAchievement.objects.create(user=xuser, achievement=ach, progress=1)
        response = xclient.get("/api/users/achievements/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["unlocked_count"] >= 1


# ══════════════════════════════════════════════════════════════════════
#  GAMIFICATION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGamification:
    """Tests for GET /api/users/gamification/"""

    def test_gamification_profile(self, xclient, xuser):
        """Returns gamification profile, creating one if needed."""
        response = xclient.get("/api/users/gamification/")
        assert response.status_code == status.HTTP_200_OK
        assert GamificationProfile.objects.filter(user=xuser).exists()


# ══════════════════════════════════════════════════════════════════════
#  AI USAGE
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAIUsage:
    """Tests for GET /api/users/ai-usage/"""

    def test_ai_usage(self, xclient):
        """Returns AI usage quotas."""
        response = xclient.get("/api/users/ai-usage/")
        assert response.status_code == status.HTTP_200_OK
        assert "usage" in response.data
        assert "plan" in response.data


# ══════════════════════════════════════════════════════════════════════
#  PERSONALITY QUIZ
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPersonalityQuizExtra:
    """Tests for POST /api/users/personality-quiz/"""

    def test_quiz_success(self, xclient, xuser):
        """Valid quiz answers return dreamer type."""
        response = xclient.post(
            "/api/users/personality-quiz/",
            {"answers": [0, 1, 2, 3, 0, 1, 2, 3]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "dreamer_type" in response.data
        assert "scores" in response.data
        assert "xp_awarded" in response.data
        # First time gets 50 XP
        assert response.data["xp_awarded"] == 50

    def test_quiz_second_time_no_xp(self, xclient, xuser):
        """Second quiz attempt awards no XP."""
        xuser.dreamer_type = "visionary"
        xuser.save(update_fields=["dreamer_type"])
        response = xclient.post(
            "/api/users/personality-quiz/",
            {"answers": [0, 0, 0, 0, 0, 0, 0, 0]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["xp_awarded"] == 0

    def test_quiz_wrong_count(self, xclient):
        """Wrong number of answers returns 400."""
        response = xclient.post(
            "/api/users/personality-quiz/",
            {"answers": [0, 1, 2]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_quiz_invalid_answer_value(self, xclient):
        """Answer out of range returns 400."""
        response = xclient.post(
            "/api/users/personality-quiz/",
            {"answers": [0, 1, 2, 5, 0, 1, 2, 3]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_quiz_no_answers(self, xclient):
        """Missing answers returns 400."""
        response = xclient.post(
            "/api/users/personality-quiz/", {}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════════
#  PROFILE COMPLETENESS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestProfileCompletenessExtra:
    """Tests for GET /api/users/profile-completeness/"""

    def test_profile_completeness(self, xclient, xuser):
        """Returns completeness data."""
        response = xclient.get("/api/users/profile-completeness/")
        assert response.status_code == status.HTTP_200_OK
        assert "percentage" in response.data
        assert "completed" in response.data
        assert "missing" in response.data
        assert "items" in response.data

    def test_profile_completeness_increases(self, xclient, xuser):
        """Filling fields increases completeness."""
        xuser.display_name = "Complete User"
        xuser.bio = "My bio"
        xuser.avatar_url = "https://example.com/avatar.jpg"
        xuser.save(update_fields=["display_name", "bio", "avatar_url"])
        response = xclient.get("/api/users/profile-completeness/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["percentage"] >= 30  # name + avatar + bio


# ══════════════════════════════════════════════════════════════════════
#  DAILY QUOTE
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDailyQuoteExtra:
    """Tests for GET /api/users/daily-quote/"""

    def test_daily_quote(self, xclient):
        """Returns a daily quote."""
        response = xclient.get("/api/users/daily-quote/")
        assert response.status_code == status.HTTP_200_OK
        assert "quote" in response.data
        assert "author" in response.data
        assert "category" in response.data


# ══════════════════════════════════════════════════════════════════════
#  NOTIFICATION TIMING (PUT)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotificationTimingPut:
    """Tests for PUT /api/users/notification-timing/"""

    def test_put_notification_timing(self, premium_xclient, premium_xuser):
        """Apply notification timing preferences."""
        data = {
            "optimal_times": [
                {
                    "notification_type": "reminder",
                    "best_hour": 9,
                    "best_day": "weekday",
                    "reason": "Morning is best",
                }
            ],
            "quiet_hours": {"start": 22, "end": 7},
            "engagement_score": 0.8,
        }
        response = premium_xclient.put(
            "/api/users/notification-timing/", data, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["applied"] is True
        premium_xuser.refresh_from_db()
        assert premium_xuser.notification_timing is not None

    def test_put_notification_timing_invalid_hour(self, premium_xclient):
        """Invalid best_hour returns 400."""
        data = {
            "optimal_times": [
                {
                    "notification_type": "reminder",
                    "best_hour": 25,
                    "best_day": "daily",
                }
            ],
            "quiet_hours": {"start": 22, "end": 7},
        }
        response = premium_xclient.put(
            "/api/users/notification-timing/", data, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_notification_timing_invalid_day(self, premium_xclient):
        """Invalid best_day returns 400."""
        data = {
            "optimal_times": [
                {
                    "notification_type": "reminder",
                    "best_hour": 9,
                    "best_day": "invalid_day",
                }
            ],
            "quiet_hours": {"start": 22, "end": 7},
        }
        response = premium_xclient.put(
            "/api/users/notification-timing/", data, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_notification_timing_not_dict(self, premium_xclient):
        """Non-dict body returns 400."""
        response = premium_xclient.put(
            "/api/users/notification-timing/",
            data='"string"',
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_notification_timing_invalid_quiet_hours(self, premium_xclient):
        """Invalid quiet_hours returns 400."""
        data = {
            "optimal_times": [],
            "quiet_hours": {"start": 25, "end": 7},
        }
        response = premium_xclient.put(
            "/api/users/notification-timing/", data, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_notification_timing_optimal_times_not_list(self, premium_xclient):
        """optimal_times must be an array."""
        data = {
            "optimal_times": "not a list",
            "quiet_hours": {"start": 22, "end": 7},
        }
        response = premium_xclient.put(
            "/api/users/notification-timing/", data, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_notification_timing_quiet_hours_not_dict(self, premium_xclient):
        """quiet_hours must be an object."""
        data = {
            "optimal_times": [],
            "quiet_hours": "not a dict",
        }
        response = premium_xclient.put(
            "/api/users/notification-timing/", data, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════════
#  NOTIFICATION TIMING (GET - AI)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotificationTimingGet:
    """Tests for GET /api/users/notification-timing/"""

    @patch("integrations.openai_service.OpenAIService.optimize_notification_timing")
    def test_get_notification_timing_success(self, mock_ai, premium_xclient, premium_xuser):
        """GET returns AI suggestion."""
        mock_ai.return_value = {
            "optimal_times": [
                {
                    "notification_type": "reminder",
                    "best_hour": 9,
                    "best_day": "weekday",
                    "reason": "Based on activity",
                }
            ],
            "quiet_hours": {"start": 22, "end": 7},
        }
        response = premium_xclient.get("/api/users/notification-timing/")
        assert response.status_code == status.HTTP_200_OK
        assert "suggestion" in response.data
        assert "activity_summary" in response.data

    @patch("integrations.openai_service.OpenAIService.optimize_notification_timing")
    def test_get_notification_timing_ai_error(self, mock_ai, premium_xclient):
        """AI error returns 503."""
        from core.exceptions import OpenAIError

        mock_ai.side_effect = OpenAIError("API down")
        response = premium_xclient.get("/api/users/notification-timing/")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_get_notification_timing_free_user(self, xclient):
        """Free user cannot access AI notification timing."""
        response = xclient.get("/api/users/notification-timing/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ══════════════════════════════════════════════════════════════════════
#  MORNING BRIEFING
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMorningBriefing:
    """Tests for GET /api/users/morning-briefing/"""

    def test_morning_briefing(self, xclient, xuser):
        """Returns morning briefing data."""
        response = xclient.get("/api/users/morning-briefing/")
        assert response.status_code == status.HTTP_200_OK
        assert "greeting" in response.data
        assert "tasks_today" in response.data


# ══════════════════════════════════════════════════════════════════════
#  PUBLIC PROFILE
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPublicProfileExtra:
    """Tests for GET /api/users/{id}/ - public profile visibility."""

    def test_public_profile_shows_dreams(self, xclient, xuser2):
        """Public profile includes public dreams."""
        Dream.objects.create(
            user=xuser2,
            title="Public Dream",
            status="active",
            category="career",
            is_public=True,
        )
        response = xclient.get(f"/api/users/{xuser2.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert "dreams" in response.data
        assert len(response.data["dreams"]) >= 1

    def test_public_profile_mutual_friends(self, xclient, xuser, xuser2):
        """Profile shows mutual friends count."""
        user3 = User.objects.create_user(
            email="mutual_friend@example.com",
            password="testpassword123",
            display_name="Mutual Friend",
        )
        Friendship.objects.create(user1=xuser, user2=user3, status="accepted")
        Friendship.objects.create(user1=xuser2, user2=user3, status="accepted")

        response = xclient.get(f"/api/users/{xuser2.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["mutual_friends"] >= 1

    def test_own_profile_returns_data(self, xclient, xuser):
        """User can view own profile by ID."""
        response = xclient.get(f"/api/users/{xuser.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(xuser.id)

    def test_profile_friend_count(self, xclient, xuser, xuser2):
        """Profile shows friend count."""
        Friendship.objects.create(user1=xuser, user2=xuser2, status="accepted")
        response = xclient.get(f"/api/users/{xuser2.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["friend_count"] >= 1

    def test_profile_categories(self, xclient, xuser2):
        """Profile shows dream categories."""
        Dream.objects.create(
            user=xuser2, title="D1", status="active", category="health", is_public=True
        )
        Dream.objects.create(
            user=xuser2, title="D2", status="active", category="career", is_public=True
        )
        response = xclient.get(f"/api/users/{xuser2.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert "categories" in response.data


# ══════════════════════════════════════════════════════════════════════
#  USER LIST
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUserList:
    """Tests for GET /api/users/"""

    def test_list_returns_only_self(self, xclient, xuser, xuser2):
        """User list only returns the current user."""
        response = xclient.get("/api/users/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        ids = [u["id"] for u in results]
        assert str(xuser.id) in ids
        assert str(xuser2.id) not in ids
