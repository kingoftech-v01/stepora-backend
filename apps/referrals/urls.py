"""
URLs for the Referrals system.

Routes:
    /code/                    - Get my referral code
    /redeem/                  - Redeem a referral code
    /my-referrals/            - List my referrals
    /rewards/                 - List my rewards
    /rewards/<id>/claim/      - Claim a reward
"""

from django.urls import path

from .views import (
    ClaimRewardView,
    MyReferralCodeView,
    MyReferralsView,
    MyRewardsView,
    RedeemCodeView,
)

urlpatterns = [
    path("code/", MyReferralCodeView.as_view(), name="referral-code"),
    path("redeem/", RedeemCodeView.as_view(), name="referral-redeem"),
    path("my-referrals/", MyReferralsView.as_view(), name="my-referrals"),
    path("rewards/", MyRewardsView.as_view(), name="referral-rewards"),
    path(
        "rewards/<uuid:reward_id>/claim/",
        ClaimRewardView.as_view(),
        name="referral-claim-reward",
    ),
]
