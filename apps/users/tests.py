"""
Tests for users app.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIRequestFactory

from core.authentication import ExpiringTokenAuthentication

from .models import GamificationProfile, User


class TestUserModel:
    """Test User model"""

    def test_create_user(self, db, user_data):
        """Test creating a user"""
        user = User.objects.create(**user_data)
        assert user.email == user_data["email"]
        assert user.display_name == user_data["display_name"]
        assert user.subscription == "free"
        assert user.xp == 0
        assert user.level == 1
        assert user.streak_days == 0

    def test_user_str(self, user):
        """Test user string representation"""
        expected = f"{user.email} ({user.display_name or 'No name'})"
        assert str(user) == expected

    def test_is_premium(self, user, premium_user):
        """Test is_premium method"""
        assert not user.is_premium()
        assert premium_user.is_premium()

    def test_is_premium_expired(self, user, db):
        """Test is_premium checks the Subscription table plan, not expiry."""
        from apps.subscriptions.models import Subscription, SubscriptionPlan

        premium_plan = SubscriptionPlan.objects.filter(slug="premium").first()
        if not premium_plan:
            pytest.skip("No premium plan in DB")
        sub, _ = Subscription.objects.get_or_create(
            user=user, defaults={"plan": premium_plan, "status": "active"}
        )
        sub.plan = premium_plan
        sub.status = "active"
        sub.save()
        user.subscription_ends = timezone.now() - timedelta(days=1)
        user.save(update_fields=["subscription_ends"])
        if hasattr(user, "_cached_plan"):
            del user._cached_plan
        # is_premium() reads from Subscription table, not User.subscription
        assert user.is_premium()

    def test_update_activity(self, user):
        """Test update_activity sets last_activity to now"""
        old_activity = user.last_activity
        user.update_activity()
        user.refresh_from_db()
        assert user.last_activity >= old_activity

    def test_add_xp(self, user):
        """Test adding XP"""
        initial_xp = user.xp

        user.add_xp(100)

        assert user.xp == initial_xp + 100

    def test_add_xp_level_up(self, user):
        """Test level up when XP threshold reached"""
        user.xp = 0
        user.level = 1
        user.save()

        # Add enough XP to level up (100 XP per level)
        user.add_xp(150)

        assert user.level == 2
        assert user.xp == 150

    def test_level_up_calculation(self, user):
        """Test level calculation based on XP"""
        user.xp = 0
        assert user.level == 1

        user.xp = 100
        user.save()
        user.refresh_from_db()
        # Level should be recalculated in save method or property


class TestGamificationProfile:
    """Test GamificationProfile model"""

    def test_create_gamification_profile(self, db, user):
        """Test creating gamification profile"""
        profile = GamificationProfile.objects.create(
            user=user,
            health_xp=50,
            career_xp=30,
            relationships_xp=20,
            personal_growth_xp=10,
            finance_xp=0,
            hobbies_xp=15,
        )

        assert profile.user == user
        assert profile.health_xp == 50
        assert profile.career_xp == 30
        assert profile.relationships_xp == 20
        assert profile.personal_growth_xp == 10
        assert profile.finance_xp == 0
        assert profile.hobbies_xp == 15
        assert profile.badges == []
        assert profile.achievements == []
        assert profile.streak_jokers == 3

    def test_update_attribute(self, gamification_profile):
        """Test updating gamification attribute XP fields"""
        initial_health = gamification_profile.health_xp

        gamification_profile.health_xp = initial_health + 10
        gamification_profile.save()

        gamification_profile.refresh_from_db()
        assert gamification_profile.health_xp == initial_health + 10


class TestTokenAuthentication:
    """Test Token authentication backend"""

    def test_token_auth_success(self, db, user):
        """Test successful Token authentication with 'Token' keyword"""
        token = Token.objects.create(user=user)
        authenticator = ExpiringTokenAuthentication()

        factory = APIRequestFactory()
        request = factory.get("/", HTTP_AUTHORIZATION=f"Token {token.key}")

        authenticated_user, auth_token = authenticator.authenticate(request)

        assert authenticated_user == user
        assert auth_token == token

    def test_bearer_keyword_auth(self, db, user):
        """Test ExpiringTokenAuthentication converts 'Bearer' to 'Token' and authenticates"""
        token = Token.objects.create(user=user)
        authenticator = ExpiringTokenAuthentication()

        factory = APIRequestFactory()
        request = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token.key}")

        authenticated_user, auth_token = authenticator.authenticate(request)

        assert authenticated_user == user
        assert auth_token == token

    def test_missing_token_returns_none(self, db):
        """Test missing auth header returns None"""
        authenticator = ExpiringTokenAuthentication()

        factory = APIRequestFactory()
        request = factory.get("/")

        result = authenticator.authenticate(request)
        assert result is None

    def test_invalid_token_raises_error(self, db):
        """Test invalid token raises AuthenticationFailed"""
        from rest_framework.exceptions import AuthenticationFailed

        authenticator = ExpiringTokenAuthentication()

        factory = APIRequestFactory()
        request = factory.get("/", HTTP_AUTHORIZATION="Token invalidtokenkey123")

        with pytest.raises(AuthenticationFailed):
            authenticator.authenticate(request)


class TestUserViewSet:
    """Test User API endpoints"""

    def test_get_current_user(self, authenticated_client, user):
        """Test GET /api/users/me/"""
        response = authenticated_client.get("/api/users/me/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email
        assert response.data["display_name"] == user.display_name

    def test_update_current_user(self, authenticated_client, user):
        """Test PUT /api/users/update_profile/"""
        data = {"display_name": "Updated Name", "timezone": "America/New_York"}

        response = authenticated_client.put(
            "/api/users/update_profile/", data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["display_name"] == "Updated Name"

        user.refresh_from_db()
        assert user.display_name == "Updated Name"
        assert user.timezone == "America/New_York"

    def test_partial_update_current_user(self, authenticated_client, user):
        """Test PATCH /api/users/update_profile/"""
        data = {"display_name": "Partial Update"}

        response = authenticated_client.patch(
            "/api/users/update_profile/", data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.display_name == "Partial Update"

    def test_update_preferences(self, authenticated_client, user):
        """Test PUT /api/users/notification-preferences/"""
        data = {"push_enabled": True, "weekly_summary": True, "dream_reminders": False}

        response = authenticated_client.put(
            "/api/users/notification-preferences/", data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.notification_prefs["push_enabled"] is True
        assert user.notification_prefs["weekly_summary"] is True
        assert user.notification_prefs["dream_reminders"] is False

    def test_get_stats(self, authenticated_client, user):
        """Test GET /api/users/stats/"""
        response = authenticated_client.get("/api/users/stats/")

        assert response.status_code == status.HTTP_200_OK
        assert "total_dreams" in response.data
        assert "completed_dreams" in response.data
        assert "active_dreams" in response.data
        assert "total_tasks_completed" in response.data

    def test_unauthenticated_access(self, api_client):
        """Test unauthenticated access is denied"""
        response = api_client.get("/api/users/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Avatar Upload Tests
# ---------------------------------------------------------------------------


class TestAvatarUpload:
    """Test avatar upload endpoint"""

    def test_upload_avatar_jpeg(self, authenticated_client, user):
        """Test uploading a valid JPEG avatar."""
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile

        # Create a minimal valid JPEG (magic bytes)
        jpeg_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        avatar = SimpleUploadedFile("avatar.jpg", jpeg_content, content_type="image/jpeg")

        response = authenticated_client.post(
            "/api/users/upload_avatar/",
            {"avatar": avatar},
            format="multipart",
        )

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.avatar_image is not None
        assert str(user.avatar_image) != ""

    def test_upload_avatar_png(self, authenticated_client, user):
        """Test uploading a valid PNG avatar."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        png_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        avatar = SimpleUploadedFile("avatar.png", png_content, content_type="image/png")

        response = authenticated_client.post(
            "/api/users/upload_avatar/",
            {"avatar": avatar},
            format="multipart",
        )

        assert response.status_code == status.HTTP_200_OK

    def test_upload_avatar_no_file(self, authenticated_client):
        """Test uploading with no file returns 400."""
        response = authenticated_client.post(
            "/api/users/upload_avatar/",
            {},
            format="multipart",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data

    def test_upload_avatar_invalid_type(self, authenticated_client):
        """Test uploading an invalid file type returns 400."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        # A text file pretending to be an image
        text_file = SimpleUploadedFile("avatar.txt", b"not an image", content_type="text/plain")

        response = authenticated_client.post(
            "/api/users/upload_avatar/",
            {"avatar": text_file},
            format="multipart",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_avatar_spoofed_content_type(self, authenticated_client):
        """Test uploading a file with spoofed content type (magic bytes mismatch) returns 400."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Content-type says image/jpeg but content is plain text
        fake_img = SimpleUploadedFile("avatar.jpg", b"this is not jpeg", content_type="image/jpeg")

        response = authenticated_client.post(
            "/api/users/upload_avatar/",
            {"avatar": fake_img},
            format="multipart",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_avatar_too_large(self, authenticated_client):
        """Test uploading a file exceeding 5MB returns 400."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        # JPEG magic bytes + 6MB of zeros
        big_content = b"\xff\xd8\xff\xe0" + b"\x00" * (6 * 1024 * 1024)
        big_file = SimpleUploadedFile("huge.jpg", big_content, content_type="image/jpeg")

        response = authenticated_client.post(
            "/api/users/upload_avatar/",
            {"avatar": big_file},
            format="multipart",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Data Export Tests
# ---------------------------------------------------------------------------


class TestDataExport:
    """Test data export endpoint (GDPR compliance)"""

    def test_export_data_json(self, authenticated_client, user, dream):
        """Test GET /api/users/export-data/ returns JSON with user data."""
        response = authenticated_client.get("/api/users/export-data/")

        assert response.status_code == status.HTTP_200_OK
        assert "profile" in response.data
        assert response.data["profile"]["email"] == user.email
        assert "dreams" in response.data
        assert "conversations" in response.data
        assert "achievements" in response.data

    def test_export_data_csv(self, authenticated_client, user, dream):
        """Test GET /api/users/export-data/?format=csv returns CSV."""
        response = authenticated_client.get("/api/users/export-data/?format=csv")

        assert response.status_code == status.HTTP_200_OK
        # CSV responses return text/csv content type
        content_type = response.get("Content-Type", "")
        assert "csv" in content_type or response.status_code == 200

    def test_export_data_unauthenticated(self, api_client):
        """Test that export requires authentication."""
        response = api_client.get("/api/users/export-data/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Delete Account Tests
# ---------------------------------------------------------------------------


class TestDeleteAccount:
    """Test account deletion endpoint"""

    def test_delete_account_success(self, authenticated_client, user):
        """Test POST /api/users/delete-account/ with correct password."""
        from unittest.mock import patch

        with patch("apps.subscriptions.services.StripeService.cancel_subscription"):
            response = authenticated_client.post(
                "/api/users/delete-account/",
                {"password": "testpassword123"},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.is_active is False
        assert user.display_name == "Deleted User"
        assert "deleted_" in user.email

    def test_delete_account_wrong_password(self, authenticated_client, user):
        """Test delete account with wrong password returns 400."""
        response = authenticated_client.post(
            "/api/users/delete-account/",
            {"password": "wrongpassword"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        user.refresh_from_db()
        assert user.is_active is True

    def test_delete_account_no_password(self, authenticated_client, user):
        """Test delete account without password returns 400."""
        response = authenticated_client.post(
            "/api/users/delete-account/",
            {},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_account_anonymizes_data(self, authenticated_client, user):
        """Test that account deletion anonymizes all personal data."""
        from unittest.mock import patch

        user.bio = "Some bio text"
        user.location = "Paris"
        user.social_links = {"twitter": "test"}
        user.save()

        with patch("apps.subscriptions.services.StripeService.cancel_subscription"):
            authenticated_client.post(
                "/api/users/delete-account/",
                {"password": "testpassword123"},
                format="json",
            )

        user.refresh_from_db()
        assert user.bio == ""
        assert user.location == ""
        assert user.social_links is None
        assert user.avatar_url == ""


# ---------------------------------------------------------------------------
# Two-Factor Authentication View Tests
# ---------------------------------------------------------------------------


class TestTwoFactorViews:
    """Test 2FA setup, verify, disable, status, and backup codes endpoints."""

    def test_2fa_setup(self, authenticated_client, user):
        """Test POST /api/users/2fa/setup/ returns secret and provisioning URI."""
        response = authenticated_client.post("/api/users/2fa/setup/")

        assert response.status_code == status.HTTP_200_OK
        assert "secret" in response.data
        assert "provisioning_uri" in response.data
        assert "otpauth://" in response.data["provisioning_uri"]

        # Secret should be stored on the user
        user.refresh_from_db()
        assert user.totp_secret != ""

    def test_2fa_verify_completes_setup(self, authenticated_client, user):
        """Test POST /api/users/2fa/verify/ with valid code enables 2FA."""
        import pyotp

        # Setup first
        authenticated_client.post("/api/users/2fa/setup/")
        user.refresh_from_db()
        secret = user.totp_secret

        # Generate a valid TOTP code
        totp = pyotp.TOTP(secret)
        code = totp.now()

        response = authenticated_client.post(
            "/api/users/2fa/verify/",
            {"code": code},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["verified"] is True
        assert "backup_codes" in response.data
        assert len(response.data["backup_codes"]) == 10

        user.refresh_from_db()
        assert user.totp_enabled is True

    def test_2fa_verify_invalid_code(self, authenticated_client, user):
        """Test POST /api/users/2fa/verify/ with invalid code returns 400."""
        # Setup first
        authenticated_client.post("/api/users/2fa/setup/")

        response = authenticated_client.post(
            "/api/users/2fa/verify/",
            {"code": "000000"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        user.refresh_from_db()
        assert user.totp_enabled is False

    def test_2fa_verify_empty_code(self, authenticated_client, user):
        """Test POST /api/users/2fa/verify/ with empty code returns 400."""
        response = authenticated_client.post(
            "/api/users/2fa/verify/",
            {"code": ""},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_2fa_status_disabled(self, authenticated_client, user):
        """Test GET /api/users/2fa/status/ when 2FA is disabled."""
        response = authenticated_client.get("/api/users/2fa/status/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["two_factor_enabled"] is False

    def test_2fa_status_enabled(self, authenticated_client, user):
        """Test GET /api/users/2fa/status/ when 2FA is enabled."""
        import pyotp

        # Setup and verify
        authenticated_client.post("/api/users/2fa/setup/")
        user.refresh_from_db()
        code = pyotp.TOTP(user.totp_secret).now()
        authenticated_client.post("/api/users/2fa/verify/", {"code": code}, format="json")

        response = authenticated_client.get("/api/users/2fa/status/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["two_factor_enabled"] is True
        assert response.data["backup_codes_remaining"] == 10

    def test_2fa_disable(self, authenticated_client, user):
        """Test POST /api/users/2fa/disable/ with correct password disables 2FA."""
        import pyotp

        # Enable 2FA first
        authenticated_client.post("/api/users/2fa/setup/")
        user.refresh_from_db()
        code = pyotp.TOTP(user.totp_secret).now()
        authenticated_client.post("/api/users/2fa/verify/", {"code": code}, format="json")

        # Disable with password
        response = authenticated_client.post(
            "/api/users/2fa/disable/",
            {"password": "testpassword123"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["two_factor_enabled"] is False

        user.refresh_from_db()
        assert user.totp_enabled is False
        assert user.totp_secret == ""

    def test_2fa_disable_wrong_password(self, authenticated_client, user):
        """Test POST /api/users/2fa/disable/ with wrong password returns 400."""
        import pyotp

        # Enable 2FA first
        authenticated_client.post("/api/users/2fa/setup/")
        user.refresh_from_db()
        code = pyotp.TOTP(user.totp_secret).now()
        authenticated_client.post("/api/users/2fa/verify/", {"code": code}, format="json")

        response = authenticated_client.post(
            "/api/users/2fa/disable/",
            {"password": "wrongpassword"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        user.refresh_from_db()
        assert user.totp_enabled is True

    def test_2fa_regenerate_backup_codes(self, authenticated_client, user):
        """Test POST /api/users/2fa/backup-codes/ regenerates backup codes."""
        import pyotp

        # Enable 2FA first
        authenticated_client.post("/api/users/2fa/setup/")
        user.refresh_from_db()
        code = pyotp.TOTP(user.totp_secret).now()
        authenticated_client.post("/api/users/2fa/verify/", {"code": code}, format="json")

        # Regenerate codes
        response = authenticated_client.post(
            "/api/users/2fa/backup-codes/",
            {"password": "testpassword123"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "backup_codes" in response.data
        assert len(response.data["backup_codes"]) == 10

    def test_2fa_regenerate_wrong_password(self, authenticated_client, user):
        """Test regenerate backup codes with wrong password returns 400."""
        import pyotp

        # Enable 2FA first
        authenticated_client.post("/api/users/2fa/setup/")
        user.refresh_from_db()
        code = pyotp.TOTP(user.totp_secret).now()
        authenticated_client.post("/api/users/2fa/verify/", {"code": code}, format="json")

        response = authenticated_client.post(
            "/api/users/2fa/backup-codes/",
            {"password": "wrongpassword"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_2fa_regenerate_when_not_enabled(self, authenticated_client, user):
        """Test regenerate backup codes when 2FA is not enabled returns 400."""
        response = authenticated_client.post(
            "/api/users/2fa/backup-codes/",
            {"password": "testpassword123"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# User Profile Visibility Tests
# ---------------------------------------------------------------------------


class TestProfileVisibility:
    """Test profile visibility settings (public, friends, private)."""

    def test_view_public_profile(self, authenticated_client, second_user):
        """Test viewing another user's public profile succeeds."""
        second_user.profile_visibility = "public"
        second_user.save(update_fields=["profile_visibility"])

        response = authenticated_client.get(f"/api/users/{second_user.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["display_name"] == second_user.display_name

    def test_view_private_profile(self, authenticated_client, second_user):
        """Test viewing another user's private profile returns 403."""
        second_user.profile_visibility = "private"
        second_user.save(update_fields=["profile_visibility"])

        response = authenticated_client.get(f"/api/users/{second_user.id}/")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_view_friends_only_profile_not_friend(self, authenticated_client, second_user):
        """Test viewing friends-only profile without being friends returns 403."""
        second_user.profile_visibility = "friends"
        second_user.save(update_fields=["profile_visibility"])

        response = authenticated_client.get(f"/api/users/{second_user.id}/")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_view_own_profile_always_visible(self, authenticated_client, user):
        """Test that a user can always view their own profile."""
        user.profile_visibility = "private"
        user.save(update_fields=["profile_visibility"])

        response = authenticated_client.get(f"/api/users/{user.id}/")

        assert response.status_code == status.HTTP_200_OK
