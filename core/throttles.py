"""
Custom throttle classes for DreamPlanner.

Provides rate limiting for sensitive operations:
- Auth endpoints (login, register)
- AI features (chat, plan generation) - per-minute burst + daily quota
- Search queries
- Data export
"""

from datetime import datetime, timezone

from rest_framework.exceptions import PermissionDenied, Throttled
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, BaseThrottle

from core.ai_usage import AIUsageTracker


# --- Per-minute burst rate throttles (DRF built-in) ---

class AuthRateThrottle(AnonRateThrottle):
    """Rate limiting for authentication endpoints (login, register, password reset)."""
    scope = 'auth'


class AIRateThrottle(UserRateThrottle):
    """Per-minute burst rate limiting for AI chat (10/min)."""
    scope = 'ai_chat'


class AIPlanRateThrottle(UserRateThrottle):
    """Per-minute burst rate limiting for AI plan generation (5/min)."""
    scope = 'ai_plan'


class AICalibrationRateThrottle(UserRateThrottle):
    """Per-minute burst rate limiting for calibration questions (15/min)."""
    scope = 'ai_calibration'


class SearchRateThrottle(UserRateThrottle):
    """Rate limiting for search endpoints."""
    scope = 'search'


class ExportRateThrottle(UserRateThrottle):
    """Rate limiting for data export (1/day)."""
    scope = 'export'


class StorePurchaseRateThrottle(UserRateThrottle):
    """Rate limiting for store purchases."""
    scope = 'store_purchase'


class SubscriptionRateThrottle(UserRateThrottle):
    """Rate limiting for subscription operations."""
    scope = 'subscription'


# --- Daily AI Quota throttles (Redis counters) ---

class DailyAIQuotaThrottle(BaseThrottle):
    """
    Base throttle that checks daily AI quota from Redis.

    Subclasses set `category` to one of: ai_chat, ai_plan, ai_image, ai_voice.
    The daily limit is determined by the user's subscription plan.

    When limit == 0 (no access on current plan), raises 403 PermissionDenied
    with subscription_required code so the frontend shows the upgrade modal.
    When limit > 0 but exceeded, returns 429 (standard throttle behavior).
    """
    category = None

    def allow_request(self, request, view):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return False

        tracker = AIUsageTracker()
        allowed, info = tracker.check_quota(request.user, self.category)
        self.usage_info = info

        if not allowed:
            limit = info.get('limit', 0)

            # limit == 0 means the plan doesn't include this feature at all.
            # This is an access control issue (403), not a rate limit (429).
            if limit == 0:
                exc = PermissionDenied(
                    detail="This feature is not available on your current plan.",
                    code='subscription_required',
                )
                exc.required_tier = 'premium'
                exc.feature_name = self.category
                raise exc

            # limit > 0 but exhausted: daily quota exceeded (429).
            # Raise Throttled with enriched info. DRF's exception_handler
            # reads exc.wait to set the Retry-After header, and our
            # custom_exception_handler reads the extra attrs.
            exc = Throttled(wait=self.wait())
            exc.default_code = 'daily_quota_exceeded'
            exc.usage_info = info
            exc.category = self.category
            raise exc

        return allowed

    def wait(self):
        """Return seconds until midnight (quota reset)."""
        now = datetime.now(timezone.utc)
        reset = AIUsageTracker.get_reset_time()
        delta = (reset - now).total_seconds()
        return max(1, int(delta))


class AIChatDailyThrottle(DailyAIQuotaThrottle):
    """Daily quota for AI chat messages."""
    category = 'ai_chat'


class AIPlanDailyThrottle(DailyAIQuotaThrottle):
    """Daily quota for AI plan/analysis operations."""
    category = 'ai_plan'


class AICalibrationDailyThrottle(DailyAIQuotaThrottle):
    """Daily quota for calibration questions (separate from plan generation)."""
    category = 'ai_calibration'


class AIImageDailyThrottle(DailyAIQuotaThrottle):
    """Daily quota for AI image generation (DALL-E)."""
    category = 'ai_image'


class AIVoiceDailyThrottle(DailyAIQuotaThrottle):
    """Daily quota for voice transcription."""
    category = 'ai_voice'


class TwoFactorRateThrottle(UserRateThrottle):
    """Rate limiting for 2FA operations (backup codes, setup)."""
    rate = '5/hour'


class EmailVerificationRateThrottle(AnonRateThrottle):
    """Rate limiting for email verification token attempts."""
    rate = '10/hour'
