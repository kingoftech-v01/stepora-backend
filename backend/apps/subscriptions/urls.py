"""
URL routing for the Subscriptions app.

Registers the plan listing, subscription management, and webhook
endpoints under a single router.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import SubscriptionPlanViewSet, SubscriptionViewSet, StripeWebhookView

router = DefaultRouter()
router.register(r'plans', SubscriptionPlanViewSet, basename='subscription-plan')
router.register(r'subscription', SubscriptionViewSet, basename='subscription')

urlpatterns = [
    path('', include(router.urls)),
    path('webhook/stripe/', StripeWebhookView.as_view(), name='stripe-webhook'),
]
