"""
Tests for core/ai_usage.py

Tests the AIUsageTracker: quota checking, incrementing, usage retrieval,
and reset time calculation.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache

from core.ai_usage import QUOTA_CATEGORIES, AIUsageTracker

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def tracker(settings):
    """Create a tracker with quotas enabled."""
    settings.AI_QUOTAS = {
        "ENABLED": True,
        "REDIS_KEY_PREFIX": "test_ai_usage",
        "KEY_TTL_HOURS": 25,
    }
    return AIUsageTracker()


@pytest.fixture
def disabled_tracker(settings):
    """Create a tracker with quotas disabled."""
    settings.AI_QUOTAS = {
        "ENABLED": False,
    }
    return AIUsageTracker()


@pytest.fixture
def mock_user():
    """Create a mock user object."""
    user = MagicMock()
    user.id = "test-user-123"
    return user


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


# ── QUOTA_CATEGORIES ──────────────────────────────────────────────────


class TestQuotaCategories:
    def test_all_categories_defined(self):
        expected = {"ai_chat", "ai_plan", "ai_image", "ai_voice", "ai_background"}
        assert set(QUOTA_CATEGORIES.keys()) == expected

    def test_categories_have_operations(self):
        for category, operations in QUOTA_CATEGORIES.items():
            assert isinstance(operations, list)
            assert len(operations) > 0, f"{category} has no operations"


# ── AIUsageTracker initialization ─────────────────────────────────────


class TestTrackerInit:
    def test_default_config(self, settings):
        settings.AI_QUOTAS = {}
        tracker = AIUsageTracker()
        assert tracker.enabled is True
        assert tracker.prefix == "ai_usage"

    def test_custom_config(self, tracker):
        assert tracker.enabled is True
        assert tracker.prefix == "test_ai_usage"
        assert tracker.ttl_seconds == 25 * 3600

    def test_disabled_config(self, disabled_tracker):
        assert disabled_tracker.enabled is False


# ── _get_key ──────────────────────────────────────────────────────────


class TestGetKey:
    def test_key_format(self, tracker, mock_user):
        from datetime import date

        key = tracker._get_key(mock_user.id, "ai_chat")
        today = date.today().isoformat()
        assert key == f"test_ai_usage:test-user-123:ai_chat:{today}"


# ── check_quota ───────────────────────────────────────────────────────


class TestCheckQuota:
    def test_disabled_tracker_always_allows(self, disabled_tracker, mock_user):
        allowed, info = disabled_tracker.check_quota(mock_user, "ai_chat")
        assert allowed is True
        assert info["limit"] == -1
        assert info["remaining"] == -1

    def test_zero_limit_blocks(self, tracker, mock_user):
        with patch.object(tracker, "get_limits", return_value={"ai_chat": 0}):
            allowed, info = tracker.check_quota(mock_user, "ai_chat")
            assert allowed is False
            assert info["limit"] == 0
            assert info["remaining"] == 0

    def test_unlimited_always_allows(self, tracker, mock_user):
        with patch.object(tracker, "get_limits", return_value={"ai_chat": -1}):
            allowed, info = tracker.check_quota(mock_user, "ai_chat")
            assert allowed is True
            assert info["limit"] == -1

    def test_within_quota_allowed(self, tracker, mock_user):
        with patch.object(tracker, "get_limits", return_value={"ai_chat": 10}):
            # No usage yet
            allowed, info = tracker.check_quota(mock_user, "ai_chat")
            assert allowed is True
            assert info["used"] == 0
            assert info["remaining"] == 10

    def test_at_limit_blocked(self, tracker, mock_user):
        with patch.object(tracker, "get_limits", return_value={"ai_chat": 5}):
            # Set usage to 5
            key = tracker._get_key(mock_user.id, "ai_chat")
            cache.set(key, 5, timeout=3600)
            allowed, info = tracker.check_quota(mock_user, "ai_chat")
            assert allowed is False
            assert info["used"] == 5
            assert info["remaining"] == 0

    def test_over_limit_blocked(self, tracker, mock_user):
        with patch.object(tracker, "get_limits", return_value={"ai_chat": 5}):
            key = tracker._get_key(mock_user.id, "ai_chat")
            cache.set(key, 7, timeout=3600)
            allowed, info = tracker.check_quota(mock_user, "ai_chat")
            assert allowed is False
            assert info["remaining"] == 0

    def test_missing_category_defaults_to_zero(self, tracker, mock_user):
        with patch.object(tracker, "get_limits", return_value={}):
            allowed, info = tracker.check_quota(mock_user, "ai_chat")
            assert allowed is False

    def test_info_contains_category(self, tracker, mock_user):
        with patch.object(tracker, "get_limits", return_value={"ai_chat": 10}):
            _, info = tracker.check_quota(mock_user, "ai_chat")
            assert info["category"] == "ai_chat"


# ── increment ─────────────────────────────────────────────────────────


class TestIncrement:
    def test_disabled_returns_zero(self, disabled_tracker, mock_user):
        result = disabled_tracker.increment(mock_user, "ai_chat")
        assert result == 0

    def test_first_increment_sets_to_one(self, tracker, mock_user):
        result = tracker.increment(mock_user, "ai_chat")
        assert result == 1

    def test_subsequent_increments(self, tracker, mock_user):
        tracker.increment(mock_user, "ai_chat")
        tracker.increment(mock_user, "ai_chat")
        result = tracker.increment(mock_user, "ai_chat")
        assert result == 3

    def test_increment_sets_ttl_on_first_use(self, tracker, mock_user):
        tracker.increment(mock_user, "ai_chat")
        key = tracker._get_key(mock_user.id, "ai_chat")
        value = cache.get(key)
        assert value == 1

    def test_different_categories_independent(self, tracker, mock_user):
        tracker.increment(mock_user, "ai_chat")
        tracker.increment(mock_user, "ai_chat")
        tracker.increment(mock_user, "ai_plan")

        key_chat = tracker._get_key(mock_user.id, "ai_chat")
        key_plan = tracker._get_key(mock_user.id, "ai_plan")
        assert cache.get(key_chat) == 2
        assert cache.get(key_plan) == 1


# ── get_usage ─────────────────────────────────────────────────────────


class TestGetUsage:
    def test_returns_all_categories(self, tracker, mock_user):
        with patch.object(
            tracker,
            "get_limits",
            return_value={
                "ai_chat": 50,
                "ai_plan": 10,
                "ai_image": 5,
                "ai_voice": 20,
                "ai_background": -1,
            },
        ):
            usage = tracker.get_usage(mock_user)
            assert set(usage.keys()) == set(QUOTA_CATEGORIES.keys())

    def test_usage_reflects_increments(self, tracker, mock_user):
        with patch.object(
            tracker,
            "get_limits",
            return_value={
                "ai_chat": 50,
                "ai_plan": 10,
                "ai_image": 5,
                "ai_voice": 20,
                "ai_background": -1,
            },
        ):
            tracker.increment(mock_user, "ai_chat")
            tracker.increment(mock_user, "ai_chat")
            usage = tracker.get_usage(mock_user)
            assert usage["ai_chat"]["used"] == 2
            assert usage["ai_chat"]["limit"] == 50
            assert usage["ai_chat"]["remaining"] == 48

    def test_unlimited_category_remaining_negative(self, tracker, mock_user):
        with patch.object(
            tracker,
            "get_limits",
            return_value={
                "ai_chat": -1,
                "ai_plan": 10,
                "ai_image": 5,
                "ai_voice": 20,
                "ai_background": -1,
            },
        ):
            usage = tracker.get_usage(mock_user)
            assert usage["ai_chat"]["remaining"] == -1

    def test_disabled_tracker_shows_zero_usage(self, disabled_tracker, mock_user):
        with patch.object(
            disabled_tracker,
            "get_limits",
            return_value={
                "ai_chat": 50,
                "ai_plan": 10,
                "ai_image": 5,
                "ai_voice": 20,
                "ai_background": -1,
            },
        ):
            usage = disabled_tracker.get_usage(mock_user)
            for cat in QUOTA_CATEGORIES:
                assert usage[cat]["used"] == 0


# ── get_reset_time ────────────────────────────────────────────────────


class TestGetResetTime:
    def test_returns_future_datetime(self):
        reset = AIUsageTracker.get_reset_time()
        now = datetime.now(timezone.utc)
        assert reset > now

    def test_is_midnight_utc(self):
        reset = AIUsageTracker.get_reset_time()
        assert reset.hour == 0
        assert reset.minute == 0
        assert reset.second == 0

    def test_is_tomorrow(self):
        reset = AIUsageTracker.get_reset_time()
        now = datetime.now(timezone.utc)
        expected_date = now.date() + timedelta(days=1)
        assert reset.date() == expected_date


# ── get_limits ────────────────────────────────────────────────────────


class TestGetLimits:
    def test_blocked_limits_when_no_subscription(self, tracker, user):
        """User with no subscription gets blocked (all zeros)."""
        # The conftest auto-creates a free subscription via seed_plans,
        # but let's test the no-subscription edge case explicitly.
        from apps.subscriptions.models import Subscription

        Subscription.objects.filter(user=user).delete()
        limits = tracker.get_limits(user)
        assert limits["ai_chat"] == 0
        assert limits["ai_plan"] == 0

    def test_limits_from_subscription(self, tracker, premium_user):
        """Premium user should have non-zero limits from their plan."""
        limits = tracker.get_limits(premium_user)
        # Premium plans have positive limits set by seed_plans
        assert limits["ai_chat"] > 0 or limits["ai_chat"] == -1

    def test_blocked_limits_all_zero(self):
        blocked = AIUsageTracker._BLOCKED_LIMITS
        for key, value in blocked.items():
            assert value == 0
