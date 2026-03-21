"""
Tests for custom throttle classes and AI usage tracking.
"""

from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest
from django.core.cache import cache

from .ai_usage import QUOTA_CATEGORIES, AIUsageTracker
from .throttles import (
    AIChatDailyThrottle,
    AIImageDailyThrottle,
    AIPlanDailyThrottle,
    AIPlanRateThrottle,
    AIRateThrottle,
    AIVoiceDailyThrottle,
    AuthRateThrottle,
    DailyAIQuotaThrottle,
    ExportRateThrottle,
    SearchRateThrottle,
    StorePurchaseRateThrottle,
    SubscriptionRateThrottle,
)

# ============================================================
# Original throttle scope tests
# ============================================================


class TestAuthRateThrottle:
    """Tests for AuthRateThrottle."""

    def test_scope(self):
        throttle = AuthRateThrottle()
        assert throttle.scope == "auth"

    def test_is_anon_throttle(self):
        from rest_framework.throttling import AnonRateThrottle

        assert issubclass(AuthRateThrottle, AnonRateThrottle)


class TestAIRateThrottle:
    """Tests for AIRateThrottle."""

    def test_scope(self):
        throttle = AIRateThrottle()
        assert throttle.scope == "ai_chat"

    def test_is_user_throttle(self):
        from rest_framework.throttling import UserRateThrottle

        assert issubclass(AIRateThrottle, UserRateThrottle)


class TestAIPlanRateThrottle:
    """Tests for AIPlanRateThrottle."""

    def test_scope(self):
        throttle = AIPlanRateThrottle()
        assert throttle.scope == "ai_plan"

    def test_is_user_throttle(self):
        from rest_framework.throttling import UserRateThrottle

        assert issubclass(AIPlanRateThrottle, UserRateThrottle)


class TestSearchRateThrottle:
    """Tests for SearchRateThrottle."""

    def test_scope(self):
        throttle = SearchRateThrottle()
        assert throttle.scope == "search"

    def test_is_user_throttle(self):
        from rest_framework.throttling import UserRateThrottle

        assert issubclass(SearchRateThrottle, UserRateThrottle)


class TestExportRateThrottle:
    """Tests for ExportRateThrottle."""

    def test_scope(self):
        throttle = ExportRateThrottle()
        assert throttle.scope == "export"

    def test_is_user_throttle(self):
        from rest_framework.throttling import UserRateThrottle

        assert issubclass(ExportRateThrottle, UserRateThrottle)


class TestStorePurchaseRateThrottle:
    """Tests for StorePurchaseRateThrottle."""

    def test_scope(self):
        throttle = StorePurchaseRateThrottle()
        assert throttle.scope == "store_purchase"

    def test_is_user_throttle(self):
        from rest_framework.throttling import UserRateThrottle

        assert issubclass(StorePurchaseRateThrottle, UserRateThrottle)


class TestSubscriptionRateThrottle:
    """Tests for SubscriptionRateThrottle."""

    def test_scope(self):
        throttle = SubscriptionRateThrottle()
        assert throttle.scope == "subscription"

    def test_is_user_throttle(self):
        from rest_framework.throttling import UserRateThrottle

        assert issubclass(SubscriptionRateThrottle, UserRateThrottle)


# ============================================================
# Daily AI Quota Throttle tests
# ============================================================


class TestDailyAIQuotaThrottleClasses:
    """Tests for DailyAIQuotaThrottle subclasses."""

    def test_chat_throttle_category(self):
        throttle = AIChatDailyThrottle()
        assert throttle.category == "ai_chat"

    def test_plan_throttle_category(self):
        throttle = AIPlanDailyThrottle()
        assert throttle.category == "ai_plan"

    def test_image_throttle_category(self):
        throttle = AIImageDailyThrottle()
        assert throttle.category == "ai_image"

    def test_voice_throttle_category(self):
        throttle = AIVoiceDailyThrottle()
        assert throttle.category == "ai_voice"

    def test_all_inherit_from_base(self):
        assert issubclass(AIChatDailyThrottle, DailyAIQuotaThrottle)
        assert issubclass(AIPlanDailyThrottle, DailyAIQuotaThrottle)
        assert issubclass(AIImageDailyThrottle, DailyAIQuotaThrottle)
        assert issubclass(AIVoiceDailyThrottle, DailyAIQuotaThrottle)

    def test_wait_returns_seconds_until_midnight(self):
        throttle = AIChatDailyThrottle()
        seconds = throttle.wait()
        assert isinstance(seconds, int)
        assert seconds > 0
        assert seconds <= 86400  # Max 24 hours


# ============================================================
# AI Usage Tracker tests
# ============================================================

AI_QUOTAS_TEST = {
    "ENABLED": True,
    "REDIS_KEY_PREFIX": "test_ai_usage",
    "KEY_TTL_HOURS": 25,
    "DEFAULT_LIMITS": {
        "free": {
            "ai_chat": 0,
            "ai_plan": 0,
            "ai_image": 0,
            "ai_voice": 0,
            "ai_background": 0,
        },
        "premium": {
            "ai_chat": 50,
            "ai_plan": 10,
            "ai_image": 0,
            "ai_voice": 10,
            "ai_background": 3,
        },
        "pro": {
            "ai_chat": 150,
            "ai_plan": 25,
            "ai_image": 3,
            "ai_voice": 20,
            "ai_background": 3,
        },
    },
}


class TestAIUsageTracker:
    """Tests for AIUsageTracker service."""

    @pytest.fixture(autouse=True)
    def _setup(self, settings):
        settings.AI_QUOTAS = AI_QUOTAS_TEST
        cache.clear()

    def test_free_user_blocked(self, user):
        """Free user should be blocked (0 quota)."""
        tracker = AIUsageTracker()
        allowed, info = tracker.check_quota(user, "ai_chat")
        assert allowed is False
        assert info["limit"] == 0
        assert info["remaining"] == 0

    def test_premium_user_allowed(self, premium_user):
        """Premium user should be allowed (50 chat quota)."""
        tracker = AIUsageTracker()
        allowed, info = tracker.check_quota(premium_user, "ai_chat")
        assert allowed is True
        assert info["limit"] == 50
        assert info["remaining"] == 50

    def test_pro_user_higher_limits(self, pro_user):
        """Pro user should have higher limits."""
        tracker = AIUsageTracker()
        allowed, info = tracker.check_quota(pro_user, "ai_chat")
        assert allowed is True
        assert info["limit"] == 150

    def test_increment_increases_count(self, premium_user):
        """Increment should increase usage count."""
        tracker = AIUsageTracker()
        count = tracker.increment(premium_user, "ai_chat")
        assert count == 1

        count = tracker.increment(premium_user, "ai_chat")
        assert count == 2

    def test_quota_blocks_at_limit(self, premium_user):
        """User should be blocked when quota is reached."""
        tracker = AIUsageTracker()

        # Manually set usage to limit
        key = tracker._get_key(premium_user.id, "ai_chat")
        cache.set(key, 50, timeout=tracker.ttl_seconds)

        allowed, info = tracker.check_quota(premium_user, "ai_chat")
        assert allowed is False
        assert info["used"] == 50
        assert info["limit"] == 50
        assert info["remaining"] == 0

    def test_different_categories_tracked_independently(self, premium_user):
        """Different categories should have independent counters."""
        tracker = AIUsageTracker()

        tracker.increment(premium_user, "ai_chat")
        tracker.increment(premium_user, "ai_chat")
        tracker.increment(premium_user, "ai_plan")

        _, chat_info = tracker.check_quota(premium_user, "ai_chat")
        _, plan_info = tracker.check_quota(premium_user, "ai_plan")

        assert chat_info["used"] == 2
        assert plan_info["used"] == 1

    def test_get_usage_returns_all_categories(self, premium_user):
        """get_usage should return all category usage."""
        tracker = AIUsageTracker()
        tracker.increment(premium_user, "ai_chat")

        usage = tracker.get_usage(premium_user)
        assert "ai_chat" in usage
        assert "ai_plan" in usage
        assert "ai_image" in usage
        assert "ai_voice" in usage
        assert "ai_background" in usage
        assert usage["ai_chat"]["used"] == 1
        assert usage["ai_plan"]["used"] == 0

    def test_get_limits_fallback_to_settings(self, premium_user):
        """get_limits should use settings defaults when no Subscription model match."""
        tracker = AIUsageTracker()
        limits = tracker.get_limits(premium_user)
        assert limits["ai_chat"] == 50
        assert limits["ai_plan"] == 10
        assert limits["ai_image"] == 0
        assert limits["ai_voice"] == 10

    def test_redis_key_includes_date(self, premium_user):
        """Redis key should include today's date."""
        tracker = AIUsageTracker()
        key = tracker._get_key(premium_user.id, "ai_chat")
        today = date.today().isoformat()
        assert today in key
        assert str(premium_user.id) in key
        assert "ai_chat" in key

    def test_disabled_tracker_always_allows(self, settings, premium_user):
        """When disabled, should always allow."""
        settings.AI_QUOTAS = {"ENABLED": False}
        tracker = AIUsageTracker()
        allowed, info = tracker.check_quota(premium_user, "ai_chat")
        assert allowed is True
        assert info["limit"] == -1

    def test_get_reset_time(self):
        """get_reset_time should return next midnight UTC."""
        reset = AIUsageTracker.get_reset_time()
        now = datetime.now(timezone.utc)
        assert reset > now
        assert reset.hour == 0
        assert reset.minute == 0

    def test_premium_image_blocked(self, premium_user):
        """Premium user should be blocked from image generation (0 quota)."""
        tracker = AIUsageTracker()
        allowed, info = tracker.check_quota(premium_user, "ai_image")
        assert allowed is False
        assert info["limit"] == 0

    def test_pro_image_allowed(self, pro_user):
        """Pro user should be allowed image generation."""
        tracker = AIUsageTracker()
        allowed, info = tracker.check_quota(pro_user, "ai_image")
        assert allowed is True
        assert info["limit"] == 3

    def test_quota_info_includes_category(self, premium_user):
        """Usage info should include the category name."""
        tracker = AIUsageTracker()
        _, info = tracker.check_quota(premium_user, "ai_plan")
        assert info["category"] == "ai_plan"

    def test_increment_when_disabled_returns_zero(self, settings, premium_user):
        """When disabled, increment should return 0."""
        settings.AI_QUOTAS = {"ENABLED": False}
        tracker = AIUsageTracker()
        result = tracker.increment(premium_user, "ai_chat")
        assert result == 0


# ============================================================
# Daily AI Quota Throttle integration tests
# ============================================================


class TestDailyAIQuotaThrottleIntegration:
    """Integration tests for DailyAIQuotaThrottle with real requests."""

    @pytest.fixture(autouse=True)
    def _setup(self, settings):
        settings.AI_QUOTAS = AI_QUOTAS_TEST
        cache.clear()

    def test_throttle_blocks_unauthenticated(self):
        """Unauthenticated request should be blocked."""
        throttle = AIChatDailyThrottle()
        request = Mock()
        request.user = Mock()
        request.user.is_authenticated = False
        assert throttle.allow_request(request, None) is False

    def test_throttle_allows_premium_user(self, premium_user):
        """Premium user within quota should be allowed."""
        throttle = AIChatDailyThrottle()
        request = Mock()
        request.user = premium_user
        assert throttle.allow_request(request, None) is True

    def test_throttle_blocks_free_user(self, user):
        """Free user should be blocked with PermissionDenied (0 quota)."""
        from rest_framework.exceptions import PermissionDenied

        throttle = AIChatDailyThrottle()
        request = Mock()
        request.user = user
        with pytest.raises(PermissionDenied):
            throttle.allow_request(request, None)

    def test_throttle_blocks_at_limit(self, premium_user):
        """Should raise Throttled when daily limit reached."""
        from rest_framework.exceptions import Throttled

        tracker = AIUsageTracker()
        key = tracker._get_key(premium_user.id, "ai_chat")
        cache.set(key, 50, timeout=90000)

        throttle = AIChatDailyThrottle()
        request = Mock()
        request.user = premium_user
        with pytest.raises(Throttled):
            throttle.allow_request(request, None)


# ============================================================
# AI Usage endpoint tests
# ============================================================


@pytest.mark.django_db
class TestAIUsageEndpoint:
    """Tests for the /api/users/ai-usage/ endpoint."""

    @pytest.fixture(autouse=True)
    def _setup(self, settings):
        settings.AI_QUOTAS = AI_QUOTAS_TEST
        cache.clear()

    def test_ai_usage_returns_all_categories(self, premium_client):
        """Should return usage for all AI categories."""
        response = premium_client.get("/api/users/ai-usage/")
        assert response.status_code == 200
        data = response.data
        assert "usage" in data
        assert "ai_chat" in data["usage"]
        assert "ai_plan" in data["usage"]
        assert "ai_image" in data["usage"]
        assert "ai_voice" in data["usage"]
        assert "ai_background" in data["usage"]

    def test_ai_usage_shows_correct_limits(self, premium_client):
        """Premium user should see correct limits."""
        response = premium_client.get("/api/users/ai-usage/")
        assert response.status_code == 200
        assert response.data["usage"]["ai_chat"]["limit"] == 50
        assert response.data["usage"]["ai_plan"]["limit"] == 10

    def test_ai_usage_reflects_increments(self, premium_client, premium_user):
        """Usage should reflect actual usage."""
        tracker = AIUsageTracker()
        tracker.increment(premium_user, "ai_chat")
        tracker.increment(premium_user, "ai_chat")

        response = premium_client.get("/api/users/ai-usage/")
        assert response.status_code == 200
        assert response.data["usage"]["ai_chat"]["used"] == 2
        assert response.data["usage"]["ai_chat"]["remaining"] == 48

    def test_ai_usage_includes_date_and_reset(self, premium_client):
        """Response should include date and reset time."""
        response = premium_client.get("/api/users/ai-usage/")
        assert response.status_code == 200
        assert "date" in response.data
        assert "resets_at" in response.data

    def test_free_user_sees_zero_limits(self, authenticated_client):
        """Free user should see 0 limits."""
        response = authenticated_client.get("/api/users/ai-usage/")
        assert response.status_code == 200
        assert response.data["usage"]["ai_chat"]["limit"] == 0

    def test_pro_user_sees_higher_limits(self, pro_client):
        """Pro user should see higher limits."""
        response = pro_client.get("/api/users/ai-usage/")
        assert response.status_code == 200
        assert response.data["usage"]["ai_chat"]["limit"] == 150
        assert response.data["usage"]["ai_image"]["limit"] == 3


# ============================================================
# Quota categories constant tests
# ============================================================


class TestQuotaCategories:
    """Tests for QUOTA_CATEGORIES constant."""

    def test_all_categories_exist(self):
        assert "ai_chat" in QUOTA_CATEGORIES
        assert "ai_plan" in QUOTA_CATEGORIES
        assert "ai_image" in QUOTA_CATEGORIES
        assert "ai_voice" in QUOTA_CATEGORIES
        assert "ai_background" in QUOTA_CATEGORIES

    def test_chat_includes_expected_operations(self):
        assert "send_message" in QUOTA_CATEGORIES["ai_chat"]
        assert "websocket_chat" in QUOTA_CATEGORIES["ai_chat"]
        assert "send_image" in QUOTA_CATEGORIES["ai_chat"]

    def test_plan_includes_expected_operations(self):
        assert "analyze_dream" in QUOTA_CATEGORIES["ai_plan"]
        assert "generate_plan" in QUOTA_CATEGORIES["ai_plan"]
        assert "calibration" in QUOTA_CATEGORIES["ai_plan"]

    def test_image_includes_vision(self):
        assert "generate_vision" in QUOTA_CATEGORIES["ai_image"]

    def test_background_includes_system_tasks(self):
        assert "daily_motivation" in QUOTA_CATEGORIES["ai_background"]
        assert "weekly_report" in QUOTA_CATEGORIES["ai_background"]
        assert "conversation_summary" in QUOTA_CATEGORIES["ai_background"]
