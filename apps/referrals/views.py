"""
Views for the Referrals system.

Provides API endpoints for referral code management, code redemption,
referral tracking, reward claiming, and a combined dashboard endpoint
for the frontend.
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

# -- Tier thresholds for "3 paid referrals = 1 free month" --
REFERRALS_PER_REWARD = 3


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


class ReferralDashboardView(APIView):
    """
    Combined dashboard endpoint consumed by the frontend ReferralScreen.

    GET  -> returns code, stats, tier progress
    POST -> redeem a referral code (field: ``referral_code``)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Referral dashboard",
        tags=["Referrals"],
        responses={200: dict},
    )
    def get(self, request):
        user = request.user
        code, _ = ReferralCode.objects.get_or_create(user=user)

        # Total referrals made (all statuses)
        total_referrals = code.times_used

        # "Paid" referrals — completed or rewarded
        paid_referrals = Referral.objects.filter(
            referrer=user,
            status__in=["completed", "rewarded"],
        ).count()

        # Free months earned = paid_referrals // REFERRALS_PER_REWARD
        free_months_earned = paid_referrals // REFERRALS_PER_REWARD

        # Progress toward next free month
        progress_to_next = paid_referrals % REFERRALS_PER_REWARD
        referrals_until_next = REFERRALS_PER_REWARD - progress_to_next

        return Response(
            {
                "referral_code": code.code,
                "total_referrals": total_referrals,
                "paid_referrals": paid_referrals,
                "free_months_earned": free_months_earned,
                "progress_to_next": progress_to_next,
                "referrals_until_next_reward": referrals_until_next,
            }
        )

    @extend_schema(
        summary="Apply a referral code (dashboard)",
        tags=["Referrals"],
        request=RedeemCodeSerializer,
        responses={
            200: dict,
            400: OpenApiResponse(description="Invalid or expired code."),
        },
    )
    def post(self, request):
        # Accept both ``code`` and ``referral_code`` field names
        raw_code = request.data.get("referral_code") or request.data.get("code", "")
        serializer = RedeemCodeSerializer(data={"code": raw_code})
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

        if Referral.objects.filter(referred=request.user).exists():
            return Response(
                {"error": "You have already been referred."},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
