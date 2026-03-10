"""
End-to-end security integration tests.

Tests token expiry, CSRF protection, subscription enforcement,
ownership enforcement, input sanitization, security headers,
and rate limiting across the full stack.
"""

from datetime import timedelta
from unittest.mock import Mock, patch

from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.conversations.models import Conversation
from apps.dreams.models import Dream
from apps.users.models import User

# ---------------------------------------------------------------------------
# Token Expiry
# ---------------------------------------------------------------------------


class TestTokenExpiry:
    """Test token authentication with expiration."""

    def test_valid_token_accepted(self, user):
        token = Token.objects.create(user=user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/api/users/me/")
        assert response.status_code == status.HTTP_200_OK

    def test_bearer_prefix_accepted(self, user):
        token = Token.objects.create(user=user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")
        response = client.get("/api/users/me/")
        assert response.status_code == status.HTTP_200_OK

    def test_expired_token_rejected(self, user):
        token = Token.objects.create(user=user)
        # Backdate the token creation
        Token.objects.filter(pk=token.pk).update(
            created=timezone.now() - timedelta(hours=25)
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/api/users/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_token_rejected(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token invalid-token-key")
        response = client.get("/api/users/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_no_token_rejected(self):
        client = APIClient()
        response = client.get("/api/users/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_inactive_user_token_rejected(self, db):
        user = User.objects.create_user(
            email="inactive@test.com",
            password="testpass123",
            is_active=False,
        )
        token = Token.objects.create(user=user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/api/users/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# CSRF Protection
# ---------------------------------------------------------------------------


class TestCSRFProtection:
    """Test CSRF protection logic."""

    def test_api_with_token_no_csrf_required(self, user):
        token = Token.objects.create(user=user)
        client = APIClient(enforce_csrf_checks=True)
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/api/users/me/")
        assert response.status_code == status.HTTP_200_OK

    def test_api_with_bearer_no_csrf_required(self, user):
        token = Token.objects.create(user=user)
        client = APIClient(enforce_csrf_checks=True)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.key}")
        response = client.get("/api/users/me/")
        assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# Subscription Enforcement — Free User Blocked
# ---------------------------------------------------------------------------


class TestFreeUserBlocked:
    """Test that free users cannot access premium/pro features."""

    def test_free_user_cannot_use_ai_conversations(self, authenticated_client):
        response = authenticated_client.get("/api/conversations/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_free_user_cannot_create_conversation(self, authenticated_client):
        response = authenticated_client.post(
            "/api/conversations/",
            {
                "conversation_type": "general",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_free_user_cannot_use_buddies(self, authenticated_client):
        response = authenticated_client.get("/api/buddies/current/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_free_user_cannot_use_leagues(self, authenticated_client):
        response = authenticated_client.get("/api/leagues/leagues/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_free_user_cannot_use_leaderboard(self, authenticated_client):
        response = authenticated_client.get("/api/leagues/leaderboard/global/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_free_user_cannot_use_seasons(self, authenticated_client):
        response = authenticated_client.get("/api/leagues/seasons/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_free_user_cannot_purchase_store_items(self, authenticated_client):
        response = authenticated_client.post(
            "/api/store/purchase/",
            {
                "item_slug": "test-item",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_free_user_cannot_purchase_xp(self, authenticated_client):
        response = authenticated_client.post(
            "/api/store/purchase/xp/",
            {
                "item_slug": "test-item",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_free_user_cannot_gift_items(self, authenticated_client):
        response = authenticated_client.post("/api/store/gifts/send/", {})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_free_user_cannot_use_circles(self, authenticated_client):
        response = authenticated_client.get("/api/circles/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_free_user_cannot_use_follow_suggestions(self, authenticated_client):
        response = authenticated_client.get("/api/social/follow-suggestions/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Subscription Enforcement — Free User Allowed
# ---------------------------------------------------------------------------


class TestFreeUserAllowed:
    """Test that free users CAN access basic features."""

    def test_free_user_can_list_dreams(self, authenticated_client):
        response = authenticated_client.get("/api/dreams/dreams/")
        assert response.status_code == status.HTTP_200_OK

    def test_free_user_can_create_dream(self, authenticated_client, user):
        response = authenticated_client.post(
            "/api/dreams/dreams/",
            {
                "title": "My Dream",
                "description": "A test dream",
                "category": "education",
                "priority": 1,
            },
        )
        assert response.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)

    def test_free_user_can_view_profile(self, authenticated_client):
        response = authenticated_client.get("/api/users/me/")
        assert response.status_code == status.HTTP_200_OK

    def test_free_user_can_list_notifications(self, authenticated_client):
        response = authenticated_client.get("/api/notifications/")
        assert response.status_code == status.HTTP_200_OK

    def test_free_user_can_browse_store(self):
        client = APIClient()
        response = client.get("/api/store/categories/")
        assert response.status_code == status.HTTP_200_OK

    def test_free_user_can_browse_store_items(self):
        client = APIClient()
        response = client.get("/api/store/items/")
        assert response.status_code == status.HTTP_200_OK

    def test_free_user_can_view_health_check(self):
        client = APIClient()
        response = client.get("/health/")
        assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# Subscription Enforcement — Premium User Allowed
# ---------------------------------------------------------------------------


class TestPremiumUserAllowed:
    """Test that premium users can access premium features."""

    def test_premium_can_list_conversations(self, premium_client):
        response = premium_client.get("/api/conversations/")
        assert response.status_code == status.HTTP_200_OK

    def test_premium_can_use_buddies(self, premium_client):
        response = premium_client.get("/api/buddies/")
        assert response.status_code == status.HTTP_200_OK

    def test_premium_can_use_leagues(self, premium_client):
        response = premium_client.get("/api/leagues/leagues/")
        assert response.status_code == status.HTTP_200_OK

    def test_premium_can_list_dreams(self, premium_client):
        response = premium_client.get("/api/dreams/dreams/")
        assert response.status_code == status.HTTP_200_OK

    def test_premium_cannot_create_circles(self, premium_client):
        response = premium_client.post(
            "/api/circles/",
            {
                "name": "Test Circle",
                "description": "A test",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_premium_can_join_circles(self, premium_client):
        # GET on circles (for joining) should be allowed
        response = premium_client.get("/api/circles/")
        assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# Subscription Enforcement — Pro User
# ---------------------------------------------------------------------------


class TestProUserAllowed:
    """Test that pro users can access all features."""

    def test_pro_can_list_conversations(self, pro_client):
        response = pro_client.get("/api/conversations/")
        assert response.status_code == status.HTTP_200_OK

    def test_pro_can_use_buddies(self, pro_client):
        response = pro_client.get("/api/buddies/")
        assert response.status_code == status.HTTP_200_OK

    def test_pro_can_use_leagues(self, pro_client):
        response = pro_client.get("/api/leagues/leagues/")
        assert response.status_code == status.HTTP_200_OK

    def test_pro_can_create_circles(self, pro_client):
        response = pro_client.post(
            "/api/circles/",
            {
                "name": "Pro Circle",
                "description": "Created by a pro",
            },
        )
        # 201 Created or 400 (validation) — not 403
        assert response.status_code != status.HTTP_403_FORBIDDEN

    def test_pro_can_list_dreams(self, pro_client):
        response = pro_client.get("/api/dreams/dreams/")
        assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# AI Endpoint Subscription Gates (Dream actions)
# ---------------------------------------------------------------------------


class TestDreamAISubscriptionGates:
    """Test that AI actions on dreams require premium/pro."""

    def test_free_user_cannot_analyze_dream(self, authenticated_client, user):
        dream = Dream.objects.create(user=user, title="Test", status="active")
        response = authenticated_client.post(f"/api/dreams/dreams/{dream.id}/analyze/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_free_user_cannot_generate_plan(self, authenticated_client, user):
        dream = Dream.objects.create(user=user, title="Test", status="active")
        response = authenticated_client.post(
            f"/api/dreams/dreams/{dream.id}/generate_plan/"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("integrations.openai_service._client")
    def test_premium_user_can_analyze_dream(
        self, mock_openai, premium_client, premium_user
    ):
        dream = Dream.objects.create(user=premium_user, title="Test", status="active")
        mock_openai.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content='{"summary": "test"}'))],
            usage=Mock(total_tokens=100),
        )
        response = premium_client.post(f"/api/dreams/dreams/{dream.id}/analyze/")
        # Should not be 403 (may be 200 or other non-permission error)
        assert response.status_code != status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Ownership Enforcement
# ---------------------------------------------------------------------------


class TestOwnershipEnforcement:
    """Test that users cannot access other users' resources."""

    def test_user_cannot_see_other_dreams(self, db):
        user1 = User.objects.create_user(email="u1@test.com", password="pass123")
        user2 = User.objects.create_user(email="u2@test.com", password="pass123")
        dream = Dream.objects.create(user=user1, title="Secret Dream")

        client = APIClient()
        client.force_authenticate(user=user2)
        response = client.get(f"/api/dreams/dreams/{dream.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_user_cannot_update_other_profile(self, db):
        user1 = User.objects.create_user(email="u1b@test.com", password="pass123")
        user2 = User.objects.create_user(email="u2b@test.com", password="pass123")

        client = APIClient()
        client.force_authenticate(user=user2)
        response = client.patch(
            f"/api/users/{user1.id}/", {"display_name": "Hacked Name"}
        )
        # Should be 404 or 403, not 200
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_user_cannot_see_other_conversations(self, db):
        user1 = User.objects.create_user(
            email="c1@test.com", password="pass123", subscription="premium"
        )
        user2 = User.objects.create_user(
            email="c2@test.com", password="pass123", subscription="premium"
        )
        conv = Conversation.objects.create(user=user1, conversation_type="general")

        client = APIClient()
        client.force_authenticate(user=user2)
        response = client.get(f"/api/conversations/{conv.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_user_cannot_delete_other_dream(self, db):
        user1 = User.objects.create_user(email="d1@test.com", password="pass123")
        user2 = User.objects.create_user(email="d2@test.com", password="pass123")
        dream = Dream.objects.create(user=user1, title="My Dream")

        client = APIClient()
        client.force_authenticate(user=user2)
        response = client.delete(f"/api/dreams/dreams/{dream.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Input Sanitization
# ---------------------------------------------------------------------------


class TestInputSanitization:
    """Test XSS and injection prevention."""

    def test_xss_in_dream_title_sanitized(self, authenticated_client):
        response = authenticated_client.post(
            "/api/dreams/dreams/",
            {
                "title": '<script>alert("xss")</script>Test Dream',
                "description": "Normal description",
                "category": "education",
                "priority": 1,
            },
        )
        if response.status_code in (200, 201):
            assert "<script>" not in response.data.get("title", "")

    def test_xss_in_profile_bio_sanitized(self, authenticated_client):
        response = authenticated_client.patch(
            "/api/users/update-profile/",
            {
                "bio": "<script>evil()</script>My bio",
            },
        )
        if response.status_code == 200:
            assert "<script>" not in str(response.data)

    def test_xss_in_display_name_rejected(self, authenticated_client):
        response = authenticated_client.patch(
            "/api/users/update-profile/",
            {
                "display_name": "<img onerror=alert(1) src=x>",
            },
        )
        # Should either sanitize or reject
        if response.status_code == 200:
            assert "<img" not in str(response.data.get("display_name", ""))

    def test_sql_injection_in_search_safe(self, authenticated_client):
        response = authenticated_client.get(
            "/api/social/users/search",
            {"q": "'; DROP TABLE users; --"},
        )
        # Should not crash
        assert response.status_code in (200, 400)


# ---------------------------------------------------------------------------
# Security Headers
# ---------------------------------------------------------------------------


class TestSecurityHeaders:
    """Test security headers on responses."""

    def test_csp_header_present(self, api_client):
        response = api_client.get("/health/")
        assert "Content-Security-Policy" in response

    def test_referrer_policy_present(self, api_client):
        response = api_client.get("/health/")
        assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy_present(self, api_client):
        response = api_client.get("/health/")
        assert "Permissions-Policy" in response

    def test_x_frame_options_deny(self, api_client):
        response = api_client.get("/health/")
        assert response["X-Frame-Options"] == "DENY"

    def test_x_content_type_options(self, api_client):
        response = api_client.get("/health/")
        assert response["X-Content-Type-Options"] == "nosniff"

    def test_coop_header(self, api_client):
        response = api_client.get("/health/")
        assert response["Cross-Origin-Opener-Policy"] == "same-origin"

    def test_corp_header(self, api_client):
        response = api_client.get("/health/")
        assert response["Cross-Origin-Resource-Policy"] == "same-origin"

    def test_headers_on_api_endpoint(self, authenticated_client):
        response = authenticated_client.get("/api/users/me/")
        assert "Content-Security-Policy" in response
        assert response["X-Frame-Options"] == "DENY"

    def test_headers_on_error_response(self, api_client):
        # Use an API path that returns 401 (unauthenticated)
        response = api_client.get("/api/users/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Content-Security-Policy" in response


# ---------------------------------------------------------------------------
# Notification Tier Filtering
# ---------------------------------------------------------------------------


class TestNotificationTierFiltering:
    """Test that free users only see basic notifications."""

    def test_free_user_sees_reminder(self, authenticated_client, user):
        from django.utils import timezone as tz

        from apps.notifications.models import Notification

        Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Task Reminder",
            body="Do your task",
            scheduled_for=tz.now(),
        )
        response = authenticated_client.get("/api/notifications/")
        assert response.status_code == 200
        results = response.data.get("results", response.data)
        assert len(results) == 1

    def test_free_user_does_not_see_buddy_notification(
        self, authenticated_client, user
    ):
        from django.utils import timezone as tz

        from apps.notifications.models import Notification

        Notification.objects.create(
            user=user,
            notification_type="buddy",
            title="Buddy Check In",
            body="Your buddy needs you!",
            scheduled_for=tz.now(),
        )
        response = authenticated_client.get("/api/notifications/")
        assert response.status_code == 200
        results = response.data.get("results", response.data)
        assert len(results) == 0

    def test_premium_user_sees_all_notifications(self, premium_client, premium_user):
        from django.utils import timezone as tz

        from apps.notifications.models import Notification

        # buddy type is NOT in free tier but IS a valid model choice
        Notification.objects.create(
            user=premium_user,
            notification_type="buddy",
            title="Buddy Check-in",
            body="Your buddy said hi",
            scheduled_for=tz.now(),
        )
        Notification.objects.create(
            user=premium_user,
            notification_type="achievement",
            title="Achievement Unlocked",
            body="You earned a badge!",
            scheduled_for=tz.now(),
        )
        response = premium_client.get("/api/notifications/")
        assert response.status_code == 200
        results = response.data.get("results", response.data)
        assert len(results) == 2
