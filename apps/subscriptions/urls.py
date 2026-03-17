"""
URL routing for the Subscriptions app.

Registers the plan listing, subscription management, and webhook
endpoints under a single router.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    PromotionViewSet,
    ReferralHistoryView,
    ReferralShareView,
    ReferralView,
    StripeWebhookView,
    SubscriptionPlanViewSet,
    SubscriptionViewSet,
)

router = DefaultRouter()
router.register(r"plans", SubscriptionPlanViewSet, basename="subscription-plan")
router.register(r"subscription", SubscriptionViewSet, basename="subscription")
router.register(r"promotions", PromotionViewSet, basename="promotion")

urlpatterns = [
    path("", include(router.urls)),
    path("referral/", ReferralView.as_view(), name="referral"),
    path("referral/share/", ReferralShareView.as_view(), name="referral-share"),
    path("referral/history/", ReferralHistoryView.as_view(), name="referral-history"),
    path("webhook/stripe/", StripeWebhookView.as_view(), name="stripe-webhook"),
]
