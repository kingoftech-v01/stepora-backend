"""
Integration tests for the Subscriptions app API endpoints.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone
from rest_framework import status

from apps.subscriptions.models import (
    Subscription,
    SubscriptionPlan,
)
from apps.users.models import User


# ── List Plans (GET /api/subscriptions/plans/) ────────────────────────


class TestListPlans:
    """Tests for the subscription plans list endpoint."""

    def test_list_plans_authenticated(self, sub_client, free_plan, premium_plan, pro_plan):
        """Authenticated user can list all active plans."""
        response = sub_client.get("/api/subscriptions/plans/")
        assert response.status_code == status.HTTP_200_OK
        slugs = {p["slug"] for p in response.data}
        assert "free" in slugs
        assert "premium" in slugs
        assert "pro" in slugs

    def test_list_plans_anonymous(self, anon_client, free_plan):
        """Anonymous users can list plans (AllowAny permission)."""
        response = anon_client.get("/api/subscriptions/plans/")
        assert response.status_code == status.HTTP_200_OK

    def test_plan_fields(self, sub_client, premium_plan):
        """Plan response includes expected fields."""
        response = sub_client.get("/api/subscriptions/plans/")
        assert response.status_code == status.HTTP_200_OK
        plan_data = next(
            (p for p in response.data if p["slug"] == "premium"),
            None,
        )
        assert plan_data is not None
        assert "name" in plan_data
        assert "price_monthly" in plan_data
        assert "features" in plan_data
        assert "dream_limit" in plan_data
        assert "is_free" in plan_data
        assert "has_unlimited_dreams" in plan_data

    def test_inactive_plans_excluded(self, db, sub_client, free_plan):
        """Inactive plans are not returned."""
        SubscriptionPlan.objects.create(
            slug="hidden",
            name="Hidden Plan",
            price_monthly=Decimal("99.99"),
            is_active=False,
        )
        response = sub_client.get("/api/subscriptions/plans/")
        slugs = {p["slug"] for p in response.data}
        assert "hidden" not in slugs

    def test_retrieve_plan_by_slug(self, sub_client, premium_plan):
        """Can retrieve a single plan by slug."""
        response = sub_client.get("/api/subscriptions/plans/premium/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["slug"] == "premium"


# ── Get Current Subscription ──────────────────────────────────────────


class TestGetCurrentSubscription:
    """Tests for the current subscription endpoint."""

    def test_get_current_subscription(self, sub_client, free_subscription):
        """Authenticated user can get their current subscription."""
        response = sub_client.get("/api/subscriptions/subscription/current/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "active"

    def test_get_current_no_subscription(self, db):
        """Returns 404 when user has no subscription record."""
        user = User.objects.create_user(
            email="nosub@example.com",
            password="testpass123",
        )
        # Delete any auto-created subscription
        Subscription.objects.filter(user=user).delete()
        client_no_sub = __import__(
            "rest_framework.test", fromlist=["APIClient"]
        ).APIClient()
        client_no_sub.force_authenticate(user=user)
        response = client_no_sub.get("/api/subscriptions/subscription/current/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_current_unauthenticated(self, anon_client):
        """Unauthenticated users get 401."""
        response = anon_client.get("/api/subscriptions/subscription/current/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── Checkout Flow (mock Stripe) ───────────────────────────────────────


class TestCheckoutFlow:
    """Tests for the checkout endpoint with mocked Stripe."""

    @patch("apps.subscriptions.views.StripeService.create_checkout_session")
    def test_checkout_success(
        self, mock_create_session, sub_client, free_subscription, premium_plan
    ):
        """Checkout creates a Stripe session and returns URL."""
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/test_session"
        mock_session.id = "cs_test_123"
        mock_create_session.return_value = mock_session

        response = sub_client.post(
            "/api/subscriptions/subscription/checkout/",
            {
                "plan_slug": "premium",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "checkout_url" in response.data
        assert "session_id" in response.data
        mock_create_session.assert_called_once()

    def test_checkout_invalid_plan(self, sub_client, free_subscription):
        """Checkout with non-existent plan returns 400."""
        response = sub_client.post(
            "/api/subscriptions/subscription/checkout/",
            {"plan_slug": "nonexistent"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_checkout_unauthenticated(self, anon_client):
        """Unauthenticated checkout returns 401."""
        response = anon_client.post(
            "/api/subscriptions/subscription/checkout/",
            {"plan_slug": "premium"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("apps.subscriptions.views.StripeService.cancel_subscription")
    def test_checkout_free_plan_triggers_downgrade(
        self, mock_cancel, sub_client, premium_subscription, free_plan
    ):
        """Checking out with the free plan triggers a downgrade (cancel)."""
        mock_cancel.return_value = premium_subscription
        premium_subscription.cancel_at_period_end = True
        premium_subscription.save()

        response = sub_client.post(
            "/api/subscriptions/subscription/checkout/",
            {"plan_slug": "free"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["action"] == "downgrade_scheduled"
        mock_cancel.assert_called_once()

    @patch("apps.subscriptions.views.StripeService.cancel_subscription")
    def test_cancel_subscription(self, mock_cancel, sub_client, premium_subscription):
        """Cancel endpoint schedules cancellation at period end."""
        premium_subscription.cancel_at_period_end = True
        premium_subscription.save()
        mock_cancel.return_value = premium_subscription

        response = sub_client.post("/api/subscriptions/subscription/cancel/")
        assert response.status_code == status.HTTP_200_OK
        mock_cancel.assert_called_once()

    @patch("apps.subscriptions.views.StripeService.cancel_subscription")
    def test_cancel_no_subscription(self, mock_cancel, sub_client, free_subscription):
        """Cancel returns 404 when no active paid subscription."""
        mock_cancel.return_value = None

        response = sub_client.post("/api/subscriptions/subscription/cancel/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("apps.subscriptions.views.StripeService.change_plan")
    def test_change_plan(self, mock_change, sub_client, premium_subscription, pro_plan):
        """Change plan endpoint processes upgrade."""
        mock_change.return_value = {
            "action": "upgraded",
            "subscription": premium_subscription,
        }

        response = sub_client.post(
            "/api/subscriptions/subscription/change-plan/",
            {"plan_slug": "pro"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["action"] == "upgraded"

    def test_change_plan_missing_slug(self, sub_client, premium_subscription):
        """Change plan without plan_slug returns 400."""
        response = sub_client.post(
            "/api/subscriptions/subscription/change-plan/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_plan_nonexistent_slug(self, sub_client, premium_subscription):
        """Change plan with invalid slug returns 404."""
        response = sub_client.post(
            "/api/subscriptions/subscription/change-plan/",
            {"plan_slug": "nonexistent"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
