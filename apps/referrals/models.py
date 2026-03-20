"""
Models for the Referrals system.

Implements invite codes, referral tracking, and reward distribution.
"""

import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ReferralCode(models.Model):
    """
    A unique invite code owned by a user.

    Each user gets one referral code upon registration. The code can be
    shared with others to earn referral rewards.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral_code",
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Unique invite code (auto-generated)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this referral code is currently active",
    )
    max_uses = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of times this code can be used. Null = unlimited.",
    )
    times_used = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "referral_codes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.code} ({self.user.email})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_code():
        """Generate a unique 8-character referral code."""
        while True:
            code = secrets.token_urlsafe(6)[:8].upper()
            if not ReferralCode.objects.filter(code=code).exists():
                return code

    @property
    def is_exhausted(self):
        """Check if the code has reached its max usage."""
        if self.max_uses is None:
            return False
        return self.times_used >= self.max_uses

    @property
    def uses_remaining(self):
        """Return remaining uses, or None if unlimited."""
        if self.max_uses is None:
            return None
        return max(0, self.max_uses - self.times_used)


class Referral(models.Model):
    """
    Tracks a successful referral (new user sign-up via a referral code).
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("rewarded", "Rewarded"),
        ("expired", "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referrals_made",
        help_text="The user who shared the referral code.",
    )
    referred = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referred_by",
        help_text="The new user who signed up via the code.",
    )
    referral_code = models.ForeignKey(
        ReferralCode,
        on_delete=models.CASCADE,
        related_name="referrals",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "referrals"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["referrer", "referred"], name="unique_referral_pair"
            ),
        ]
        indexes = [
            models.Index(fields=["referrer", "status"]),
            models.Index(fields=["referred"]),
        ]

    def __str__(self):
        return f"{self.referrer.email} -> {self.referred.email} ({self.status})"

    def complete(self):
        """Mark the referral as completed."""
        if self.status == "completed":
            return
        self.status = "completed"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])


class ReferralReward(models.Model):
    """
    Tracks rewards given for referrals.

    Reward types:
    - xp: XP bonus
    - premium_days: temporary premium access
    - cosmetic: avatar frame or other cosmetic
    - discount: lifetime discount on premium
    - subscription_days: extra subscription days
    - streak_freeze: streak freeze tokens
    """

    REWARD_TYPE_CHOICES = [
        ("xp", "XP Bonus"),
        ("premium_days", "Premium Days"),
        ("cosmetic", "Cosmetic Reward"),
        ("discount", "Lifetime Discount"),
        ("subscription_days", "Extra Subscription Days"),
        ("streak_freeze", "Streak Freeze"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referral = models.ForeignKey(
        Referral,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rewards",
        help_text="The referral that triggered this reward (null for tier milestones)",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral_rewards",
        help_text="The user receiving the reward.",
    )
    reward_type = models.CharField(
        max_length=30,
        choices=REWARD_TYPE_CHOICES,
        help_text="Type of reward granted",
    )
    reward_value = models.IntegerField(
        default=0,
        help_text="Amount: XP points, premium days, discount %, or 1 for cosmetic",
    )
    description = models.CharField(max_length=255, blank=True, default="")
    tier_name = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Tier that unlocked this reward (bronze/silver/gold/diamond)",
    )
    is_claimed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "referral_rewards"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_claimed"]),
        ]

    def __str__(self):
        return f"{self.reward_type}:{self.reward_value} for {self.user.email}"

    def claim(self):
        """Claim the reward and apply it to the user."""
        if self.is_claimed:
            return

        self.is_claimed = True
        self.claimed_at = timezone.now()
        self.save(update_fields=["is_claimed", "claimed_at"])

        # Apply the reward
        if self.reward_type == "xp":
            self.user.add_xp(self.reward_value)
        elif self.reward_type == "streak_freeze":
            from apps.gamification.models import GamificationProfile

            profile, _ = GamificationProfile.objects.get_or_create(user=self.user)
            profile.streak_jokers += self.reward_value
            profile.save(update_fields=["streak_jokers"])
