"""
Services for the Referrals system.

Provides business logic for referral creation, reward distribution,
and referral validation.
"""

import logging

from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)

# Default rewards for referrals
REFERRER_XP_REWARD = 200
REFERRED_XP_REWARD = 100


class ReferralService:
    """Service for referral-related business logic."""

    @staticmethod
    def create_referral(referrer, referred, referral_code):
        """Create a referral and distribute rewards."""
        from .models import Referral, ReferralCode, ReferralReward

        # Create the referral record
        referral = Referral.objects.create(
            referrer=referrer,
            referred=referred,
            referral_code=referral_code,
            status="completed",
            completed_at=timezone.now(),
        )

        # Increment usage counter atomically
        ReferralCode.objects.filter(id=referral_code.id).update(
            times_used=F("times_used") + 1
        )

        # Create rewards for both users
        ReferralReward.objects.create(
            referral=referral,
            user=referrer,
            reward_type="xp",
            reward_value=REFERRER_XP_REWARD,
            description=f"Referral reward: {referred.display_name or referred.email} joined!",
        )

        ReferralReward.objects.create(
            referral=referral,
            user=referred,
            reward_type="xp",
            reward_value=REFERRED_XP_REWARD,
            description="Welcome bonus for joining via referral!",
        )

        # Auto-claim XP rewards
        for reward in referral.rewards.filter(reward_type="xp"):
            reward.claim()

        # Send notification to referrer
        try:
            from apps.notifications.services import NotificationService

            NotificationService.create(
                user=referrer,
                notification_type="system",
                title="New Referral!",
                body=f'{referred.display_name or "Someone"} joined using your referral code! +{REFERRER_XP_REWARD} XP',
                scheduled_for=timezone.now(),
                data={
                    "type": "referral",
                    "referred_user_id": str(referred.id),
                    "xp_reward": REFERRER_XP_REWARD,
                },
            )
        except Exception:
            logger.exception(
                "Failed to send referral notification to user %s", referrer.id
            )

        return referral

    @staticmethod
    def get_referral_stats(user):
        """Get referral statistics for a user."""
        from .models import ReferralCode, ReferralReward

        try:
            code = ReferralCode.objects.get(user=user)
            code_str = code.code
            total_referrals = code.times_used
        except ReferralCode.DoesNotExist:
            code_str = None
            total_referrals = 0

        total_xp_earned = sum(
            r.reward_value
            for r in ReferralReward.objects.filter(
                user=user, reward_type="xp", is_claimed=True
            )
        )

        return {
            "referral_code": code_str,
            "total_referrals": total_referrals,
            "total_xp_earned": total_xp_earned,
        }
