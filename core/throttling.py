"""
Custom DRF throttle classes for DreamPlanner.

Implements per-feature rate limiting to prevent abuse:
- AI endpoints: Stricter limits to control API costs
- Subscription endpoints: Moderate limits for payment operations
- Store purchases: Moderate limits to prevent duplicate charges
"""

from rest_framework.throttling import UserRateThrottle


class AIChatThrottle(UserRateThrottle):
    """Rate limit for AI chat messages (premium/pro feature)."""
    scope = 'ai_chat'


class AIPlanGenerationThrottle(UserRateThrottle):
    """Rate limit for AI plan generation requests (premium/pro feature)."""
    scope = 'ai_plan'


class SubscriptionThrottle(UserRateThrottle):
    """Rate limit for subscription management operations."""
    scope = 'subscription'


class StorePurchaseThrottle(UserRateThrottle):
    """Rate limit for store purchase operations."""
    scope = 'store_purchase'
