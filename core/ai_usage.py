"""
AI Usage Tracker for DreamPlanner.

Tracks AI usage per user per day using Redis atomic counters.
Each subscription tier has daily limits for different AI operation categories.
"""

import logging
from datetime import date, datetime, timedelta, timezone

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Categories and what operations they cover
QUOTA_CATEGORIES = {
    'ai_chat': ['send_message', 'websocket_chat', 'send_image'],
    'ai_plan': ['analyze_dream', 'calibration', 'generate_plan', 'two_minute_start'],
    'ai_image': ['generate_vision'],
    'ai_voice': ['send_voice', 'transcribe'],
    'ai_background': ['daily_motivation', 'weekly_report', 'rescue_message', 'conversation_summary'],
}


class AIUsageTracker:
    """Tracks AI usage per user per day using Redis atomic counters."""

    def __init__(self):
        self.config = getattr(settings, 'AI_QUOTAS', {})
        self.enabled = self.config.get('ENABLED', True)
        self.prefix = self.config.get('REDIS_KEY_PREFIX', 'ai_usage')
        self.ttl_seconds = self.config.get('KEY_TTL_HOURS', 25) * 3600

    def _get_key(self, user_id, category):
        """Build Redis key: ai_usage:{user_id}:{category}:{YYYY-MM-DD}."""
        today = date.today().isoformat()
        return f"{self.prefix}:{user_id}:{category}:{today}"

    # Zero limits — used when no subscription exists or DB is unreachable.
    _BLOCKED_LIMITS = {
        'ai_chat': 0, 'ai_plan': 0, 'ai_calibration': 0,
        'ai_image': 0, 'ai_voice': 0, 'ai_background': 0,
    }

    def get_limits(self, user):
        """
        Get daily limits for a user from their Subscription plan.

        The Subscription model is the single source of truth.
        If no subscription exists or the DB is unreachable, the user is
        blocked (all limits = 0) and the error is logged.
        """
        try:
            from apps.subscriptions.models import Subscription
            sub = Subscription.objects.select_related('plan').filter(
                user=user,
                status__in=('active', 'trialing'),
            ).first()
        except Exception as exc:
            # Real infrastructure error (DB down, etc.) — block and log
            logger.error(
                "Database error fetching subscription for user %s: %s",
                user.id, exc,
            )
            return dict(self._BLOCKED_LIMITS)

        if not sub or not sub.plan:
            logger.error(
                "User %s has no active subscription — blocking AI access. "
                "This should never happen; check the registration signal.",
                user.id,
            )
            return dict(self._BLOCKED_LIMITS)

        plan = sub.plan
        return {
            'ai_chat': plan.ai_chat_daily_limit,
            'ai_plan': plan.ai_plan_daily_limit,
            'ai_calibration': plan.ai_calibration_daily_limit,
            'ai_image': plan.ai_image_daily_limit,
            'ai_voice': plan.ai_voice_daily_limit,
            'ai_background': plan.ai_background_daily_limit,
        }

    def check_quota(self, user, category):
        """
        Check if user has remaining quota for a category.

        Returns:
            tuple: (allowed: bool, info: dict) where info contains
                   used, limit, remaining counts.
        """
        if not self.enabled:
            return True, {'used': 0, 'limit': -1, 'remaining': -1}

        limits = self.get_limits(user)
        limit = limits.get(category, 0)

        # 0 means no access
        if limit == 0:
            return False, {
                'used': 0,
                'limit': 0,
                'remaining': 0,
                'category': category,
            }

        # -1 means unlimited
        if limit == -1:
            return True, {'used': 0, 'limit': -1, 'remaining': -1}

        key = self._get_key(user.id, category)
        used = cache.get(key, 0)

        remaining = max(0, limit - used)
        allowed = used < limit

        info = {
            'used': used,
            'limit': limit,
            'remaining': remaining,
            'category': category,
        }

        if not allowed:
            logger.info(
                f"AI quota exceeded: user={user.id} category={category} "
                f"used={used} limit={limit}"
            )

        return allowed, info

    def increment(self, user, category):
        """
        Atomically increment usage counter for a category.

        Sets TTL on first use (auto-cleanup after 25h).

        Returns:
            int: New usage count.
        """
        if not self.enabled:
            return 0

        key = self._get_key(user.id, category)
        current = cache.get(key)

        if current is None:
            # First usage today - set with TTL
            cache.set(key, 1, timeout=self.ttl_seconds)
            return 1
        else:
            new_value = current + 1
            # Get remaining TTL and preserve it
            ttl = cache.ttl(key) if hasattr(cache, 'ttl') else self.ttl_seconds
            if ttl is None or ttl <= 0:
                ttl = self.ttl_seconds
            cache.set(key, new_value, timeout=ttl)
            return new_value

    def get_usage(self, user):
        """
        Get all category usage for today.

        Returns:
            dict: {category: {used, limit, remaining}} for all categories.
        """
        limits = self.get_limits(user)
        usage = {}

        for category in QUOTA_CATEGORIES:
            limit = limits.get(category, 0)
            key = self._get_key(user.id, category)
            used = cache.get(key, 0) if self.enabled else 0
            remaining = max(0, limit - used) if limit >= 0 else -1

            usage[category] = {
                'used': used,
                'limit': limit,
                'remaining': remaining,
            }

        return usage

    @staticmethod
    def get_reset_time():
        """Get the next midnight UTC as the quota reset time."""
        now = datetime.now(timezone.utc)
        tomorrow = now.date() + timedelta(days=1)
        return datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc)
