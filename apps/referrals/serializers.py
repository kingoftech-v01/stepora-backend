"""
Serializers for the Referrals system.
"""

from rest_framework import serializers

from .models import Referral, ReferralCode, ReferralReward


class ReferralCodeSerializer(serializers.ModelSerializer):
    """Serializer for ReferralCode model."""

    uses_remaining = serializers.ReadOnlyField()

    class Meta:
        model = ReferralCode
        fields = [
            "id",
            "code",
            "is_active",
            "max_uses",
            "times_used",
            "uses_remaining",
            "created_at",
        ]
        read_only_fields = ["id", "code", "times_used", "created_at"]


class ReferralSerializer(serializers.ModelSerializer):
    """Serializer for Referral model."""

    referrer_email = serializers.CharField(source="referrer.email", read_only=True)
    referred_email = serializers.CharField(source="referred.email", read_only=True)

    class Meta:
        model = Referral
        fields = [
            "id",
            "referrer",
            "referred",
            "referrer_email",
            "referred_email",
            "referral_code",
            "status",
            "created_at",
            "completed_at",
        ]
        read_only_fields = fields


class ReferralRewardSerializer(serializers.ModelSerializer):
    """Serializer for ReferralReward model."""

    class Meta:
        model = ReferralReward
        fields = [
            "id",
            "referral",
            "user",
            "reward_type",
            "reward_value",
            "description",
            "is_claimed",
            "created_at",
            "claimed_at",
        ]
        read_only_fields = fields


class RedeemCodeSerializer(serializers.Serializer):
    """Serializer for redeeming a referral code."""

    code = serializers.CharField(
        max_length=20,
        help_text="The referral code to redeem.",
    )
