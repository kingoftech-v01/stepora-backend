"""
Tests for the Subscriptions app.

Covers models, serializers, views, the StripeService, webhook handling,
and the post-save signal. All Stripe API calls are mocked so tests run
without network access or a real Stripe account.
"""

import json
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User
from apps.subscriptions.models import (
    StripeCustomer,
    Subscription,
    SubscriptionPlan,
)
from apps.subscriptions.serializers import (
    SubscriptionPlanSerializer,
    SubscriptionSerializer,
    SubscriptionCreateSerializer,
)
from apps.subscriptions.services import (
    StripeService,
    _timestamp_to_datetime,
    _sync_user_subscription,
)


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

@pytest.fixture
def free_plan(db):
    """Return the free plan (seeded by conftest django_db_setup)."""
    plan = SubscriptionPlan.objects.filter(slug='free').first()
    if plan is None:
        plan = SubscriptionPlan.objects.create(
            name='Free',
            slug='free',
            stripe_price_id='',
            price_monthly=Decimal('0.00'),
            dream_limit=3,
            has_ai=False,
            has_buddy=False,
            has_circles=False,
            has_vision_board=False,
            has_league=False,
            has_ads=True,
            features={'dreams': '3 active dreams'},
        )
    else:
        # Ensure test-relevant fields match expectations
        plan.stripe_price_id = plan.stripe_price_id or ''
        plan.save(update_fields=['stripe_price_id'])
    return plan


@pytest.fixture
def premium_plan(db):
    """Return the premium plan (seeded by conftest django_db_setup)."""
    plan = SubscriptionPlan.objects.filter(slug='premium').first()
    if plan is None:
        plan = SubscriptionPlan.objects.create(
            name='Premium',
            slug='premium',
            stripe_price_id='price_premium_test',
            price_monthly=Decimal('19.99'),
            dream_limit=10,
            has_ai=True,
            has_buddy=True,
            has_circles=False,
            has_vision_board=False,
            has_league=True,
            has_ads=False,
            features={'dreams': '10 active dreams', 'ai_coaching': True},
        )
    else:
        # Ensure stripe_price_id is set for checkout tests
        if not plan.stripe_price_id:
            plan.stripe_price_id = 'price_premium_test'
            plan.save(update_fields=['stripe_price_id'])
    return plan


@pytest.fixture
def pro_plan(db):
    """Return the pro plan (seeded by conftest django_db_setup)."""
    plan = SubscriptionPlan.objects.filter(slug='pro').first()
    if plan is None:
        plan = SubscriptionPlan.objects.create(
            name='Pro',
            slug='pro',
            stripe_price_id='price_pro_test',
            price_monthly=Decimal('29.99'),
            dream_limit=-1,
            has_ai=True,
            has_buddy=True,
            has_circles=True,
            has_vision_board=True,
            has_league=True,
            has_ads=False,
            features={'dreams': 'Unlimited active dreams'},
        )
    else:
        # Ensure stripe_price_id is set for checkout tests
        if not plan.stripe_price_id:
            plan.stripe_price_id = 'price_pro_test'
            plan.save(update_fields=['stripe_price_id'])
    return plan


@pytest.fixture
def all_plans(free_plan, premium_plan, pro_plan):
    """Convenience fixture that creates all three plans."""
    return [free_plan, premium_plan, pro_plan]


@pytest.fixture
def test_user(db):
    """Create a test user without triggering the Stripe signal."""
    with patch('apps.subscriptions.services.StripeService.create_customer'):
        user = User.objects.create(
            email=f'test_{uuid.uuid4().hex[:8]}@example.com',
            display_name='Test User',
        )
    return user


@pytest.fixture
def stripe_customer(db, test_user):
    """Create a StripeCustomer record for the test user."""
    return StripeCustomer.objects.create(
        user=test_user,
        stripe_customer_id=f'cus_{uuid.uuid4().hex[:14]}',
    )


@pytest.fixture
def active_subscription(db, test_user, premium_plan, stripe_customer):
    """Create or update to an active premium subscription for the test user."""
    now = timezone.now()
    sub, _ = Subscription.objects.update_or_create(
        user=test_user,
        defaults={
            'plan': premium_plan,
            'stripe_subscription_id': f'sub_{uuid.uuid4().hex[:14]}',
            'status': 'active',
            'current_period_start': now,
            'current_period_end': now + timedelta(days=30),
            'cancel_at_period_end': False,
        },
    )
    return sub


@pytest.fixture
def authenticated_client(test_user):
    """Return an API client authenticated as the test user."""
    client = APIClient()
    client.force_authenticate(user=test_user)
    return client


# ===================================================================
# Model tests
# ===================================================================


class TestSubscriptionPlanModel:
    """Tests for the SubscriptionPlan model."""

    def test_create_plan(self, free_plan):
        """Plan is created with correct attributes."""
        assert free_plan.name == 'Free'
        assert free_plan.slug == 'free'
        assert free_plan.price_monthly == Decimal('0.00')
        assert free_plan.dream_limit == 3
        assert free_plan.has_ads is True
        assert free_plan.has_ai is False

    def test_is_free_property(self, free_plan, premium_plan):
        """is_free returns True only for the zero-cost plan."""
        assert free_plan.is_free is True
        assert premium_plan.is_free is False

    def test_has_unlimited_dreams(self, free_plan, pro_plan):
        """has_unlimited_dreams returns True when dream_limit is -1."""
        assert free_plan.has_unlimited_dreams is False
        assert pro_plan.has_unlimited_dreams is True

    def test_str_representation(self, premium_plan):
        """String representation includes name and price."""
        result = str(premium_plan)
        assert 'Premium' in result
        assert '9.99' in result

    def test_ordering(self, all_plans):
        """Plans are ordered by price_monthly ascending."""
        plans = list(SubscriptionPlan.objects.all())
        assert plans[0].slug == 'free'
        assert plans[1].slug == 'premium'
        assert plans[2].slug == 'pro'

    def test_seed_plans(self, db):
        """seed_plans creates all three default plans."""
        plans = SubscriptionPlan.seed_plans()
        assert len(plans) == 3
        slugs = {p.slug for p in plans}
        assert slugs == {'free', 'premium', 'pro'}

    def test_seed_plans_idempotent(self, db):
        """Calling seed_plans twice does not duplicate plans."""
        SubscriptionPlan.seed_plans()
        SubscriptionPlan.seed_plans()
        assert SubscriptionPlan.objects.count() == 3


class TestStripeCustomerModel:
    """Tests for the StripeCustomer model."""

    def test_create_stripe_customer(self, stripe_customer, test_user):
        """StripeCustomer is linked to the correct user."""
        assert stripe_customer.user == test_user
        assert stripe_customer.stripe_customer_id.startswith('cus_')

    def test_str_representation(self, stripe_customer, test_user):
        """String representation includes user email and customer ID."""
        result = str(stripe_customer)
        assert test_user.email in result
        assert stripe_customer.stripe_customer_id in result

    def test_one_to_one_constraint(self, stripe_customer, test_user):
        """Cannot create a second StripeCustomer for the same user."""
        with pytest.raises(Exception):
            StripeCustomer.objects.create(
                user=test_user,
                stripe_customer_id='cus_duplicate',
            )


class TestSubscriptionModel:
    """Tests for the Subscription model."""

    def test_create_subscription(self, active_subscription, test_user, premium_plan):
        """Subscription is created with correct attributes."""
        assert active_subscription.user == test_user
        assert active_subscription.plan == premium_plan
        assert active_subscription.status == 'active'
        assert active_subscription.cancel_at_period_end is False

    def test_is_active_property(self, active_subscription):
        """is_active returns True for active status."""
        assert active_subscription.is_active is True

        active_subscription.status = 'trialing'
        assert active_subscription.is_active is True

        active_subscription.status = 'canceled'
        assert active_subscription.is_active is False

        active_subscription.status = 'past_due'
        assert active_subscription.is_active is False

    def test_str_representation(self, active_subscription):
        """String representation includes user email, plan name, and status."""
        result = str(active_subscription)
        assert active_subscription.user.email in result
        assert 'Premium' in result
        assert 'active' in result


# ===================================================================
# Service tests
# ===================================================================


class TestStripeServiceCreateCustomer:
    """Tests for StripeService.create_customer."""

    @patch('apps.subscriptions.services.stripe.Customer.create')
    def test_creates_stripe_customer(self, mock_stripe_create, test_user):
        """Creates a new Stripe customer and saves the mapping."""
        mock_stripe_create.return_value = Mock(id='cus_new_123')

        result = StripeService.create_customer(test_user)

        assert result.stripe_customer_id == 'cus_new_123'
        assert result.user == test_user
        mock_stripe_create.assert_called_once()

        # Verify metadata was passed
        call_kwargs = mock_stripe_create.call_args[1]
        assert call_kwargs['email'] == test_user.email
        assert call_kwargs['metadata']['stepora_user_id'] == str(test_user.id)

    def test_returns_existing_customer(self, stripe_customer, test_user):
        """Returns existing StripeCustomer without calling Stripe API."""
        with patch('apps.subscriptions.services.stripe.Customer.create') as mock_create:
            result = StripeService.create_customer(test_user)
            assert result == stripe_customer
            mock_create.assert_not_called()


class TestStripeServiceCheckout:
    """Tests for StripeService.create_checkout_session."""

    @patch('apps.subscriptions.services.stripe.checkout.Session.create')
    def test_creates_checkout_session(
        self, mock_session_create, test_user, premium_plan, stripe_customer,
    ):
        """Creates a Stripe Checkout Session with correct parameters."""
        mock_session_create.return_value = Mock(
            id='cs_test_123',
            url='https://checkout.stripe.com/pay/cs_test_123',
        )

        session = StripeService.create_checkout_session(
            user=test_user,
            plan=premium_plan,
        )

        assert session.id == 'cs_test_123'
        mock_session_create.assert_called_once()

        call_kwargs = mock_session_create.call_args[1]
        assert call_kwargs['customer'] == stripe_customer.stripe_customer_id
        assert call_kwargs['mode'] == 'subscription'
        assert call_kwargs['line_items'][0]['price'] == 'price_premium_test'

    def test_raises_for_free_plan(self, test_user, free_plan, stripe_customer):
        """Raises ValueError when trying to checkout for the free plan."""
        with pytest.raises(ValueError, match="free plan"):
            StripeService.create_checkout_session(
                user=test_user,
                plan=free_plan,
            )


class TestStripeServicePortal:
    """Tests for StripeService.create_portal_session."""

    @patch('apps.subscriptions.services.stripe.billing_portal.Session.create')
    def test_creates_portal_session(
        self, mock_portal_create, test_user, stripe_customer,
    ):
        """Creates a billing portal session with correct customer."""
        mock_portal_create.return_value = Mock(
            url='https://billing.stripe.com/session/portal_123',
        )

        session = StripeService.create_portal_session(user=test_user)

        assert 'billing.stripe.com' in session.url
        call_kwargs = mock_portal_create.call_args[1]
        assert call_kwargs['customer'] == stripe_customer.stripe_customer_id

    def test_raises_without_stripe_customer(self, test_user):
        """Raises ValueError if user has no StripeCustomer record."""
        with pytest.raises(ValueError, match="no Stripe customer"):
            StripeService.create_portal_session(user=test_user)


class TestStripeServiceCancel:
    """Tests for StripeService.cancel_subscription."""

    @patch('apps.subscriptions.services.stripe.Subscription.modify')
    def test_cancels_at_period_end(
        self, mock_modify, test_user, active_subscription,
    ):
        """Sets cancel_at_period_end on Stripe and locally."""
        result = StripeService.cancel_subscription(test_user)

        assert result is not None
        assert result.cancel_at_period_end is True
        assert result.canceled_at is not None
        mock_modify.assert_called_once_with(
            active_subscription.stripe_subscription_id,
            cancel_at_period_end=True,
        )

    def test_returns_none_without_subscription(self, test_user):
        """Returns None when user has no active subscription."""
        # Signal auto-creates a free sub; deactivate it first
        Subscription.objects.filter(user=test_user).update(status='canceled')
        result = StripeService.cancel_subscription(test_user)
        assert result is None


class TestStripeServiceReactivate:
    """Tests for StripeService.reactivate_subscription."""

    @patch('apps.subscriptions.services.stripe.Subscription.modify')
    def test_reactivates_subscription(
        self, mock_modify, test_user, active_subscription,
    ):
        """Reverses cancellation on Stripe and locally."""
        active_subscription.cancel_at_period_end = True
        active_subscription.canceled_at = timezone.now()
        active_subscription.save()

        result = StripeService.reactivate_subscription(test_user)

        assert result is not None
        assert result.cancel_at_period_end is False
        assert result.canceled_at is None
        mock_modify.assert_called_once_with(
            active_subscription.stripe_subscription_id,
            cancel_at_period_end=False,
        )

    def test_returns_none_without_canceling_subscription(self, test_user):
        """Returns None when no subscription is pending cancellation."""
        result = StripeService.reactivate_subscription(test_user)
        assert result is None


class TestStripeServiceSync:
    """Tests for StripeService.sync_subscription_status."""

    @patch('apps.subscriptions.services.stripe.Subscription.retrieve')
    def test_syncs_from_stripe(
        self, mock_retrieve, test_user, active_subscription, premium_plan,
    ):
        """Syncs subscription status from Stripe to local DB."""
        now_ts = int(timezone.now().timestamp())
        end_ts = now_ts + (30 * 86400)

        mock_retrieve.return_value = {
            'status': 'active',
            'current_period_start': now_ts,
            'current_period_end': end_ts,
            'cancel_at_period_end': False,
        }

        result = StripeService.sync_subscription_status(test_user)

        assert result is not None
        assert result.status == 'active'
        mock_retrieve.assert_called_once_with(
            active_subscription.stripe_subscription_id,
        )

    def test_returns_subscription_for_free_user(self, test_user):
        """Returns the free-tier subscription without calling Stripe."""
        result = StripeService.sync_subscription_status(test_user)
        # Signal auto-creates a free subscription; sync returns it unchanged
        assert result is not None
        assert result.plan.slug == 'free'

    def test_returns_none_without_any_subscription(self, test_user):
        """Returns None when user has no subscription at all."""
        Subscription.objects.filter(user=test_user).delete()
        result = StripeService.sync_subscription_status(test_user)
        assert result is None


# ===================================================================
# Webhook handler tests
# ===================================================================


class TestWebhookHandleCheckoutCompleted:
    """Tests for the checkout.session.completed webhook handler."""

    @patch('apps.subscriptions.services.stripe.Subscription.retrieve')
    def test_creates_subscription_on_checkout(
        self, mock_retrieve, test_user, premium_plan,
    ):
        """checkout.session.completed creates a local subscription."""
        now_ts = int(timezone.now().timestamp())
        end_ts = now_ts + (30 * 86400)

        mock_retrieve.return_value = {
            'status': 'active',
            'current_period_start': now_ts,
            'current_period_end': end_ts,
            'cancel_at_period_end': False,
        }

        session_data = {
            'metadata': {
                'stepora_user_id': str(test_user.id),
                'plan_slug': 'premium',
            },
            'subscription': 'sub_checkout_123',
        }

        StripeService._handle_checkout_completed(session_data)

        sub = Subscription.objects.get(user=test_user)
        assert sub.stripe_subscription_id == 'sub_checkout_123'
        assert sub.plan == premium_plan
        assert sub.status == 'active'

        test_user.refresh_from_db()
        assert test_user.subscription == 'premium'

    def test_skips_if_missing_metadata(self):
        """Gracefully handles missing metadata in session."""
        session_data = {'metadata': {}, 'subscription': None}
        # Should not raise
        StripeService._handle_checkout_completed(session_data)


class TestWebhookHandleInvoicePaid:
    """Tests for the invoice.paid webhook handler."""

    @patch('apps.subscriptions.services.stripe.Subscription.retrieve')
    def test_updates_billing_period(
        self, mock_retrieve, test_user, active_subscription, premium_plan,
    ):
        """invoice.paid updates the subscription's billing period."""
        now_ts = int(timezone.now().timestamp())
        end_ts = now_ts + (30 * 86400)

        mock_retrieve.return_value = {
            'status': 'active',
            'current_period_start': now_ts,
            'current_period_end': end_ts,
        }

        invoice_data = {
            'subscription': active_subscription.stripe_subscription_id,
        }

        StripeService._handle_invoice_paid(invoice_data)

        active_subscription.refresh_from_db()
        assert active_subscription.status == 'active'
        assert active_subscription.current_period_end is not None


class TestWebhookHandleInvoicePaymentFailed:
    """Tests for the invoice.payment_failed webhook handler."""

    def test_marks_subscription_past_due(self, active_subscription):
        """invoice.payment_failed sets status to past_due."""
        invoice_data = {
            'subscription': active_subscription.stripe_subscription_id,
        }

        StripeService._handle_invoice_payment_failed(invoice_data)

        active_subscription.refresh_from_db()
        assert active_subscription.status == 'past_due'


class TestWebhookHandleSubscriptionUpdated:
    """Tests for the customer.subscription.updated webhook handler."""

    def test_updates_subscription_status(self, active_subscription, premium_plan):
        """subscription.updated syncs status and period."""
        now_ts = int(timezone.now().timestamp())
        end_ts = now_ts + (30 * 86400)

        stripe_sub_data = {
            'id': active_subscription.stripe_subscription_id,
            'status': 'active',
            'current_period_start': now_ts,
            'current_period_end': end_ts,
            'cancel_at_period_end': True,
            'items': {'data': []},
        }

        StripeService._handle_subscription_updated(stripe_sub_data)

        active_subscription.refresh_from_db()
        assert active_subscription.cancel_at_period_end is True

    def test_updates_plan_on_change(
        self, active_subscription, premium_plan, pro_plan,
    ):
        """subscription.updated detects a plan change via price ID."""
        now_ts = int(timezone.now().timestamp())
        end_ts = now_ts + (30 * 86400)

        stripe_sub_data = {
            'id': active_subscription.stripe_subscription_id,
            'status': 'active',
            'current_period_start': now_ts,
            'current_period_end': end_ts,
            'cancel_at_period_end': False,
            'items': {
                'data': [
                    {
                        'price': {
                            'id': 'price_pro_test',
                        },
                    },
                ],
            },
        }

        StripeService._handle_subscription_updated(stripe_sub_data)

        active_subscription.refresh_from_db()
        assert active_subscription.plan == pro_plan


class TestWebhookHandleSubscriptionDeleted:
    """Tests for the customer.subscription.deleted webhook handler."""

    @patch('apps.subscriptions.services.send_subscription_cancelled_email', create=True)
    def test_reverts_to_free_tier(self, mock_email, active_subscription, test_user, free_plan):
        """subscription.deleted reverts the sub to free tier."""
        stripe_sub_data = {
            'id': active_subscription.stripe_subscription_id,
        }

        with patch('apps.subscriptions.tasks.send_subscription_cancelled_email.delay'):
            StripeService._handle_subscription_deleted(stripe_sub_data)

        active_subscription.refresh_from_db()
        # Handler reverts to free plan with status='active'
        assert active_subscription.status == 'active'
        assert active_subscription.plan == free_plan

        test_user.refresh_from_db()
        assert test_user.subscription == 'free'
        assert test_user.subscription_ends is None


class TestWebhookDispatch:
    """Tests for the top-level handle_webhook_event dispatcher."""

    @patch('apps.subscriptions.services.STRIPE_WEBHOOK_SECRET', 'whsec_test')
    @patch('apps.subscriptions.services.stripe.Webhook.construct_event')
    def test_dispatches_known_event(self, mock_construct):
        """Known event types are dispatched to the correct handler."""
        mock_construct.return_value = {
            'id': 'evt_test',
            'type': 'invoice.payment_failed',
            'data': {
                'object': {'subscription': 'sub_nonexistent'},
            },
        }

        result = StripeService.handle_webhook_event(b'payload', 'sig_header')
        assert result['status'] == 'ok'
        assert result['event_type'] == 'invoice.payment_failed'

    @patch('apps.subscriptions.services.STRIPE_WEBHOOK_SECRET', 'whsec_test')
    @patch('apps.subscriptions.services.stripe.Webhook.construct_event')
    def test_handles_unknown_event_gracefully(self, mock_construct):
        """Unknown event types are logged but do not raise."""
        mock_construct.return_value = {
            'id': 'evt_test',
            'type': 'some.unknown.event',
            'data': {'object': {}},
        }

        result = StripeService.handle_webhook_event(b'payload', 'sig_header')
        assert result['status'] == 'ok'
        assert result['event_type'] == 'some.unknown.event'

    @patch('apps.subscriptions.services.STRIPE_WEBHOOK_SECRET', 'whsec_test')
    @patch('apps.subscriptions.services.stripe.Webhook.construct_event')
    def test_raises_on_invalid_signature(self, mock_construct):
        """Invalid signatures raise ValueError."""
        import stripe as stripe_lib

        mock_construct.side_effect = stripe_lib.error.SignatureVerificationError(
            'Bad signature', 'sig_header'
        )

        with pytest.raises(ValueError, match="Invalid webhook signature"):
            StripeService.handle_webhook_event(b'payload', 'bad_sig')


# ===================================================================
# Helper function tests
# ===================================================================


class TestHelpers:
    """Tests for module-level helper functions."""

    def test_timestamp_to_datetime(self):
        """Converts a Unix timestamp to a timezone-aware datetime."""
        result = _timestamp_to_datetime(1700000000)
        assert result is not None
        assert result.tzinfo is not None

    def test_timestamp_to_datetime_none(self):
        """Returns None for a None timestamp."""
        assert _timestamp_to_datetime(None) is None

    def test_sync_user_subscription(self, test_user, premium_plan):
        """Syncs user.subscription_ends from the given plan."""
        end = timezone.now() + timedelta(days=30)
        _sync_user_subscription(test_user, premium_plan, end)

        test_user.refresh_from_db()
        # _sync_user_subscription only updates subscription_ends;
        # subscription CharField is synced by the Subscription post_save signal.
        assert test_user.subscription_ends is not None


# ===================================================================
# Signal tests
# ===================================================================


class TestSignals:
    """Tests for the post_save signal on User creation."""

    @patch('apps.subscriptions.services.stripe.Customer.create')
    def test_signal_creates_stripe_customer(self, mock_stripe_create, db):
        """Creating a User triggers Stripe customer creation."""
        mock_stripe_create.return_value = Mock(id='cus_signal_test')

        user = User.objects.create(
            email=f'signal_{uuid.uuid4().hex[:8]}@example.com',
            display_name='Signal Test',
        )

        assert StripeCustomer.objects.filter(user=user).exists()
        customer = StripeCustomer.objects.get(user=user)
        assert customer.stripe_customer_id == 'cus_signal_test'

    @patch('apps.subscriptions.services.stripe.Customer.create')
    def test_signal_does_not_block_on_error(self, mock_stripe_create, db):
        """User creation succeeds even if Stripe API fails."""
        mock_stripe_create.side_effect = Exception('Stripe is down')

        user = User.objects.create(
            email=f'sigfail_{uuid.uuid4().hex[:8]}@example.com',
            display_name='Signal Fail Test',
        )

        # User was created successfully
        assert user.pk is not None
        # But no StripeCustomer was created
        assert not StripeCustomer.objects.filter(user=user).exists()


# ===================================================================
# View tests
# ===================================================================


class TestSubscriptionPlanViews:
    """Tests for the SubscriptionPlanViewSet (public)."""

    def test_list_plans(self, all_plans):
        """GET /api/subscriptions/plans/ returns all active plans."""
        client = APIClient()
        response = client.get('/api/subscriptions/plans/')

        assert response.status_code == status.HTTP_200_OK
        # Response is paginated
        results = response.data.get('results', response.data)
        assert len(results) == 3

    def test_retrieve_plan_by_slug(self, premium_plan):
        """GET /api/subscriptions/plans/premium/ returns plan details."""
        client = APIClient()
        response = client.get('/api/subscriptions/plans/premium/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Premium'
        assert response.data['slug'] == 'premium'

    def test_plan_endpoint_is_public(self, all_plans):
        """Plan listing does not require authentication."""
        client = APIClient()
        response = client.get('/api/subscriptions/plans/')
        assert response.status_code == status.HTTP_200_OK


class TestSubscriptionViews:
    """Tests for the SubscriptionViewSet (authenticated)."""

    def test_get_current_subscription(
        self, authenticated_client, active_subscription,
    ):
        """GET current/ returns the user's active subscription."""
        response = authenticated_client.get(
            '/api/subscriptions/subscription/current/',
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'active'
        assert response.data['plan']['name'] == 'Premium'

    def test_get_current_free_subscription(self, authenticated_client):
        """GET current/ returns the auto-created free subscription."""
        response = authenticated_client.get(
            '/api/subscriptions/subscription/current/',
        )
        # Signal auto-creates a free subscription for every user
        assert response.status_code == status.HTTP_200_OK
        assert response.data['plan']['slug'] == 'free'

    @patch('apps.subscriptions.views.StripeService.create_checkout_session')
    def test_create_checkout(
        self, mock_checkout, authenticated_client, premium_plan,
    ):
        """POST checkout/ returns a checkout URL."""
        mock_checkout.return_value = Mock(
            id='cs_test_xxx',
            url='https://checkout.stripe.com/pay/cs_test_xxx',
        )

        response = authenticated_client.post(
            '/api/subscriptions/subscription/checkout/',
            {'plan_slug': 'premium'},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert 'checkout_url' in response.data
        assert 'session_id' in response.data

    def test_checkout_invalid_plan(self, authenticated_client):
        """POST checkout/ with an invalid plan slug returns 400."""
        response = authenticated_client.post(
            '/api/subscriptions/subscription/checkout/',
            {'plan_slug': 'nonexistent'},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_checkout_free_plan(self, authenticated_client, free_plan):
        """POST checkout/ with the free plan slug returns 400."""
        response = authenticated_client.post(
            '/api/subscriptions/subscription/checkout/',
            {'plan_slug': 'free'},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('apps.subscriptions.views.StripeService.cancel_subscription')
    def test_cancel_subscription(
        self, mock_cancel, authenticated_client, active_subscription,
    ):
        """POST cancel/ cancels the subscription at period end."""
        active_subscription.cancel_at_period_end = True
        active_subscription.canceled_at = timezone.now()
        active_subscription.save()
        mock_cancel.return_value = active_subscription

        response = authenticated_client.post(
            '/api/subscriptions/subscription/cancel/',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['cancel_at_period_end'] is True

    @patch('apps.subscriptions.views.StripeService.cancel_subscription')
    def test_cancel_no_subscription(self, mock_cancel, authenticated_client):
        """POST cancel/ returns 404 when no subscription exists."""
        mock_cancel.return_value = None

        response = authenticated_client.post(
            '/api/subscriptions/subscription/cancel/',
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('apps.subscriptions.views.StripeService.reactivate_subscription')
    def test_reactivate_subscription(
        self, mock_reactivate, authenticated_client, active_subscription,
    ):
        """POST reactivate/ reverses a pending cancellation."""
        active_subscription.cancel_at_period_end = False
        active_subscription.canceled_at = None
        active_subscription.save()
        mock_reactivate.return_value = active_subscription

        response = authenticated_client.post(
            '/api/subscriptions/subscription/reactivate/',
        )

        assert response.status_code == status.HTTP_200_OK

    @patch('apps.subscriptions.views.StripeService.create_portal_session')
    def test_portal_session(
        self, mock_portal, authenticated_client, stripe_customer,
    ):
        """POST portal/ returns a billing portal URL."""
        mock_portal.return_value = Mock(
            url='https://billing.stripe.com/session/test',
        )

        response = authenticated_client.post(
            '/api/subscriptions/subscription/portal/',
        )

        assert response.status_code == status.HTTP_200_OK
        assert 'portal_url' in response.data

    def test_subscription_endpoints_require_auth(self):
        """Subscription endpoints require authentication."""
        client = APIClient()
        endpoints = [
            '/api/subscriptions/subscription/current/',
            '/api/subscriptions/subscription/cancel/',
            '/api/subscriptions/subscription/reactivate/',
        ]
        for url in endpoints:
            response = client.get(url) if 'current' in url else client.post(url)
            assert response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ), f"Expected 401/403 for {url}, got {response.status_code}"


class TestStripeWebhookView:
    """Tests for the Stripe webhook endpoint."""

    @patch('apps.subscriptions.views.StripeService.handle_webhook_event')
    def test_valid_webhook(self, mock_handle):
        """POST webhook/stripe/ processes a valid webhook."""
        mock_handle.return_value = {
            'status': 'ok',
            'event_type': 'invoice.paid',
        }

        client = APIClient()
        response = client.post(
            '/api/subscriptions/webhook/stripe/',
            data=b'raw_payload',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='valid_sig',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'ok'

    def test_missing_signature_header(self):
        """POST webhook/stripe/ without Stripe-Signature returns 400."""
        client = APIClient()
        response = client.post(
            '/api/subscriptions/webhook/stripe/',
            data=b'raw_payload',
            content_type='application/json',
        )

        assert response.status_code == 400

    @patch('apps.subscriptions.views.StripeService.handle_webhook_event')
    def test_invalid_signature(self, mock_handle):
        """POST webhook/stripe/ with bad signature returns 400."""
        mock_handle.side_effect = ValueError("Invalid webhook signature")

        client = APIClient()
        response = client.post(
            '/api/subscriptions/webhook/stripe/',
            data=b'raw_payload',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='bad_sig',
        )

        assert response.status_code == 400

    def test_webhook_does_not_require_auth(self):
        """Webhook endpoint allows unauthenticated requests."""
        client = APIClient()
        # Even with no auth, should not get 401/403 - just 400 for missing sig
        response = client.post(
            '/api/subscriptions/webhook/stripe/',
            data=b'test',
            content_type='application/json',
        )
        assert response.status_code != status.HTTP_401_UNAUTHORIZED
        assert response.status_code != status.HTTP_403_FORBIDDEN


# ===================================================================
# Serializer tests
# ===================================================================


class TestSerializers:
    """Tests for subscription serializers."""

    def test_plan_serializer(self, premium_plan):
        """SubscriptionPlanSerializer includes all feature flags."""
        serializer = SubscriptionPlanSerializer(premium_plan)
        data = serializer.data

        assert data['name'] == 'Premium'
        assert data['slug'] == 'premium'
        assert data['has_ai'] is True
        assert data['has_buddy'] is True
        assert data['has_circles'] is True
        assert data['has_ads'] is False
        assert data['is_free'] is False
        assert data['has_unlimited_dreams'] is False
        assert data['dream_limit'] == 10

    def test_subscription_serializer(self, active_subscription):
        """SubscriptionSerializer includes nested plan and is_active."""
        serializer = SubscriptionSerializer(active_subscription)
        data = serializer.data

        assert data['status'] == 'active'
        assert data['is_active'] is True
        assert data['cancel_at_period_end'] is False
        assert data['plan']['name'] == 'Premium'

    def test_create_serializer_valid(self, premium_plan):
        """SubscriptionCreateSerializer validates a valid plan slug."""
        serializer = SubscriptionCreateSerializer(
            data={'plan_slug': 'premium'},
        )
        assert serializer.is_valid(), serializer.errors
        plan = serializer.get_plan()
        assert plan.slug == 'premium'

    def test_create_serializer_invalid_slug(self, db):
        """SubscriptionCreateSerializer rejects a nonexistent slug."""
        serializer = SubscriptionCreateSerializer(
            data={'plan_slug': 'nonexistent'},
        )
        assert not serializer.is_valid()
        assert 'plan_slug' in serializer.errors

    def test_create_serializer_free_slug(self, free_plan):
        """SubscriptionCreateSerializer rejects the free plan slug."""
        serializer = SubscriptionCreateSerializer(
            data={'plan_slug': 'free'},
        )
        assert not serializer.is_valid()
        assert 'plan_slug' in serializer.errors
