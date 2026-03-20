"""
Views for the Referrals system.

Provides API endpoints for referral code management, code redemption,
referral tracking, and reward claiming.
"""

import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Referral, ReferralCode, ReferralReward
from .serializers import (
    RedeemCodeSerializer,
    ReferralCodeSerializer,
    ReferralRewardSerializer,
    ReferralSerializer,
)

logger = logging.getLogger(__name__)


class MyReferralCodeView(APIView):
    """Get or create the current user's referral code."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get my referral code",
        tags=["Referrals"],
        responses={200: ReferralCodeSerializer},
    )
    def get(self, request):
        code, _ = ReferralCode.objects.get_or_create(user=request.user)
        return Response(ReferralCodeSerializer(code).data)


class RedeemCodeView(APIView):
    """Redeem a referral code."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Redeem referral code",
        tags=["Referrals"],
        request=RedeemCodeSerializer,
        responses={
            200: dict,
            400: OpenApiResponse(description="Invalid or expired code."),
        },
    )
    def post(self, request):
        serializer = RedeemCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code_str = serializer.validated_data["code"].upper()

        try:
            referral_code = ReferralCode.objects.get(code=code_str)
        except ReferralCode.DoesNotExist:
            return Response(
                {"error": "Invalid referral code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not referral_code.is_active:
            return Response(
                {"error": "This referral code is no longer active."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if referral_code.is_exhausted:
            return Response(
                {"error": "This referral code has reached its maximum uses."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if referral_code.user == request.user:
            return Response(
                {"error": "Cannot use your own referral code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if already referred
        if Referral.objects.filter(referred=request.user).exists():
            return Response(
                {"error": "You have already been referred."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create the referral
        from .services import ReferralService

        referral = ReferralService.create_referral(
            referrer=referral_code.user,
            referred=request.user,
            referral_code=referral_code,
        )

        return Response(
            {
                "message": "Referral code redeemed successfully!",
                "referral_id": str(referral.id),
            }
        )


class MyReferralsView(APIView):
    """List referrals made by the current user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="My referrals",
        tags=["Referrals"],
        responses={200: ReferralSerializer(many=True)},
    )
    def get(self, request):
        referrals = Referral.objects.filter(referrer=request.user).select_related(
            "referred", "referral_code"
        )
        return Response(
            {
                "referrals": ReferralSerializer(referrals, many=True).data,
                "count": referrals.count(),
            }
        )


class MyRewardsView(APIView):
    """List referral rewards for the current user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="My referral rewards",
        tags=["Referrals"],
        responses={200: ReferralRewardSerializer(many=True)},
    )
    def get(self, request):
        rewards = ReferralReward.objects.filter(user=request.user)
        return Response(
            {
                "rewards": ReferralRewardSerializer(rewards, many=True).data,
                "unclaimed": rewards.filter(is_claimed=False).count(),
            }
        )


class ClaimRewardView(APIView):
    """Claim a referral reward."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Claim referral reward",
        tags=["Referrals"],
        responses={
            200: ReferralRewardSerializer,
            400: OpenApiResponse(description="Reward already claimed."),
            404: OpenApiResponse(description="Reward not found."),
        },
    )
    def post(self, request, reward_id):
        try:
            reward = ReferralReward.objects.get(id=reward_id, user=request.user)
        except ReferralReward.DoesNotExist:
            return Response(
                {"error": "Reward not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if reward.is_claimed:
            return Response(
                {"error": "Reward already claimed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reward.claim()
        return Response(ReferralRewardSerializer(reward).data)
