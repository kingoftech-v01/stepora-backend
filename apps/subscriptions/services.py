"""
Stripe service layer for the Subscriptions app.

Encapsulates all Stripe API interactions so that views and webhook handlers
never call the Stripe SDK directly. This makes the business logic testable
and keeps a single place to manage API keys and error handling.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import stripe
from django.conf import settings
from django.utils import timezone

from apps.users.models import User
from .models import StripeCustomer, Subscription, SubscriptionPlan

logger = logging.getLogger(__name__)

# Configure Stripe API key from environment
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')

# Webhook secret for signature verification
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')


class StripeService:
    """
    Service class that wraps all Stripe API calls.

    Every public method in this class corresponds to a single logical
    operation (create customer, start checkout, cancel, etc.). Errors
    from the Stripe SDK are caught, logged, and re-raised so callers
    can present user-friendly messages.
    """

    # -----------------------------------------------------------------
    # Customer management
    # -----------------------------------------------------------------

    @staticmethod
    def create_customer(user: User) -> StripeCustomer:
        """
        Create a Stripe customer for the given user and persist the mapping.

        If the user already has a StripeCustomer record this method returns
        the existing record instead of creating a duplicate in Stripe.

        Args:
            user: The DreamPlanner user to create a customer for.

        Returns:
            The StripeCustomer instance linking the user to Stripe.

        Raises:
            stripe.error.StripeError: If the Stripe API call fails.
        """
        # Return existing customer if present
        existing = StripeCustomer.objects.filter(user=user).first()
        if existing:
            logger.info(
                "Stripe customer already exists for user %s: %s",
                user.email,
                existing.stripe_customer_id,
            )
            return existing

        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.display_name or user.email,
                metadata={
                    'dreamplanner_user_id': str(user.id),
                },
            )

            stripe_customer = StripeCustomer.objects.create(
                user=user,
                stripe_customer_id=customer.id,
            )

            logger.info(
                "Created Stripe customer %s for user %s",
                customer.id,
                user.email,
            )
            return stripe_customer

        except stripe.error.StripeError:
            logger.exception(
                "Failed to create Stripe customer for user %s", user.email
            )
            raise

    # -----------------------------------------------------------------
    # Checkout / Portal sessions
    # -----------------------------------------------------------------

    @staticmethod
    def create_checkout_session(
        user: User,
        plan: SubscriptionPlan,
        success_url: str = '',
        cancel_url: str = '',
        coupon_code: str = '',
    ) -> stripe.checkout.Session:
        """
        Create a Stripe Checkout Session for subscribing to a plan.

        The session redirects the user to Stripe's hosted payment page.
        On success, Stripe fires a ``checkout.session.completed`` webhook
        that we handle to activate the subscription.

        Args:
            user: The user initiating checkout.
            plan: The SubscriptionPlan to subscribe to.
            success_url: URL to redirect to after successful payment.
            cancel_url: URL to redirect to if the user cancels checkout.

        Returns:
            The Stripe Checkout Session object (contains ``url`` for redirect).

        Raises:
            ValueError: If the plan has no Stripe price or is the free tier.
            stripe.error.StripeError: If the Stripe API call fails.
        """
        if plan.is_free or not plan.stripe_price_id:
            raise ValueError(
                "Cannot create a checkout session for the free plan."
            )

        # Ensure user has a Stripe customer
        stripe_customer = StripeService.create_customer(user)

        default_success = os.getenv(
            'STRIPE_SUCCESS_URL',
            'https://app.dreamplanner.com/subscription/success?session_id={CHECKOUT_SESSION_ID}',
        )
        default_cancel = os.getenv(
            'STRIPE_CANCEL_URL',
            'https://app.dreamplanner.com/subscription/cancel',
        )

        # Build subscription_data with optional trial period
        subscription_data = {
            'metadata': {
                'dreamplanner_user_id': str(user.id),
                'plan_slug': plan.slug,
            },
        }
        if plan.trial_period_days > 0:
            subscription_data['trial_period_days'] = plan.trial_period_days

        # Build optional discounts from coupon code
        discounts = []
        if coupon_code:
            discounts.append({'coupon': coupon_code})

        try:
            session_kwargs = {
                'customer': stripe_customer.stripe_customer_id,
                'payment_method_types': ['card'],
                'mode': 'subscription',
                'line_items': [
                    {
                        'price': plan.stripe_price_id,
                        'quantity': 1,
                    }
                ],
                'success_url': success_url or default_success,
                'cancel_url': cancel_url or default_cancel,
                'metadata': {
                    'dreamplanner_user_id': str(user.id),
                    'plan_slug': plan.slug,
                },
                'subscription_data': subscription_data,
            }

            if discounts:
                session_kwargs['discounts'] = discounts

            session = stripe.checkout.Session.create(**session_kwargs)

            logger.info(
                "Created checkout session %s for user %s (plan: %s)",
                session.id,
                user.email,
                plan.name,
            )
            return session

        except stripe.error.StripeError:
            logger.exception(
                "Failed to create checkout session for user %s", user.email
            )
            raise

    @staticmethod
    def create_portal_session(
        user: User,
        return_url: str = '',
    ) -> stripe.billing_portal.Session:
        """
        Create a Stripe Billing Portal session for self-service management.

        The portal allows the user to update payment methods, view invoices,
        and cancel/change subscriptions without our intervention.

        Args:
            user: The user requesting portal access.
            return_url: URL to redirect to when the user exits the portal.

        Returns:
            The Stripe BillingPortal Session (contains ``url``).

        Raises:
            ValueError: If the user has no Stripe customer record.
            stripe.error.StripeError: If the Stripe API call fails.
        """
        stripe_customer = StripeCustomer.objects.filter(user=user).first()
        if not stripe_customer:
            raise ValueError(
                "User has no Stripe customer record. "
                "They must subscribe before accessing the billing portal."
            )

        default_return = os.getenv(
            'STRIPE_PORTAL_RETURN_URL',
            'https://app.dreamplanner.com/settings/subscription',
        )

        try:
            session = stripe.billing_portal.Session.create(
                customer=stripe_customer.stripe_customer_id,
                return_url=return_url or default_return,
            )

            logger.info(
                "Created portal session for user %s", user.email
            )
            return session

        except stripe.error.StripeError:
            logger.exception(
                "Failed to create portal session for user %s", user.email
            )
            raise

    # -----------------------------------------------------------------
    # Subscription lifecycle
    # -----------------------------------------------------------------

    @staticmethod
    def cancel_subscription(user: User) -> Optional[Subscription]:
        """
        Cancel the user's subscription at the end of the current billing period.

        This does NOT immediately revoke access. The user retains their plan
        benefits until ``current_period_end``.

        Args:
            user: The user requesting cancellation.

        Returns:
            The updated Subscription instance, or None if no active sub found.

        Raises:
            stripe.error.StripeError: If the Stripe API call fails.
        """
        subscription = Subscription.objects.filter(
            user=user,
            status__in=('active', 'trialing'),
        ).first()

        if not subscription:
            logger.warning(
                "Cancel requested but no active subscription for user %s",
                user.email,
            )
            return None

        try:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True,
            )

            subscription.cancel_at_period_end = True
            subscription.canceled_at = timezone.now()
            subscription.save(update_fields=['cancel_at_period_end', 'canceled_at', 'updated_at'])

            logger.info(
                "Subscription %s set to cancel at period end for user %s",
                subscription.stripe_subscription_id,
                user.email,
            )
            return subscription

        except stripe.error.StripeError:
            logger.exception(
                "Failed to cancel subscription for user %s", user.email
            )
            raise

    @staticmethod
    def reactivate_subscription(user: User) -> Optional[Subscription]:
        """
        Reactivate a subscription that was set to cancel at period end.

        This reverses a cancellation so the subscription auto-renews as
        normal at the next billing cycle.

        Args:
            user: The user requesting reactivation.

        Returns:
            The updated Subscription instance, or None if not applicable.

        Raises:
            stripe.error.StripeError: If the Stripe API call fails.
        """
        subscription = Subscription.objects.filter(
            user=user,
            cancel_at_period_end=True,
            status__in=('active', 'trialing'),
        ).first()

        if not subscription:
            logger.warning(
                "Reactivate requested but no canceling subscription for user %s",
                user.email,
            )
            return None

        try:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=False,
            )

            subscription.cancel_at_period_end = False
            subscription.canceled_at = None
            subscription.save(update_fields=['cancel_at_period_end', 'canceled_at', 'updated_at'])

            logger.info(
                "Subscription %s reactivated for user %s",
                subscription.stripe_subscription_id,
                user.email,
            )
            return subscription

        except stripe.error.StripeError:
            logger.exception(
                "Failed to reactivate subscription for user %s", user.email
            )
            raise

    # -----------------------------------------------------------------
    # Webhook handling
    # -----------------------------------------------------------------

    @staticmethod
    def handle_webhook_event(payload: bytes, sig_header: str) -> dict:
        """
        Verify and dispatch a Stripe webhook event.

        Stripe signs every webhook payload with the endpoint's signing secret.
        This method verifies the signature, identifies the event type, and
        calls the appropriate handler.

        Args:
            payload: Raw request body bytes.
            sig_header: Value of the ``Stripe-Signature`` header.

        Returns:
            A dict with ``status`` and ``event_type`` keys.

        Raises:
            ValueError: If the signature verification fails.
        """
        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                STRIPE_WEBHOOK_SECRET,
            )
        except stripe.error.SignatureVerificationError as e:
            logger.error("Webhook signature verification failed: %s", e)
            raise ValueError("Invalid webhook signature") from e

        event_type = event['type']
        event_id = event.get('id', '')
        data_object = event['data']['object']

        logger.info("Processing webhook event: %s (id: %s)", event_type, event_id)

        # Idempotency: skip if already processed
        from apps.subscriptions.models import StripeWebhookEvent
        if event_id and StripeWebhookEvent.objects.filter(stripe_event_id=event_id).exists():
            logger.info("Webhook event %s already processed, skipping", event_id)
            return {'status': 'already_processed', 'event_type': event_type, 'event_id': event_id}

        handler_map = {
            'checkout.session.completed': StripeService._handle_checkout_completed,
            'invoice.paid': StripeService._handle_invoice_paid,
            'invoice.payment_failed': StripeService._handle_invoice_payment_failed,
            'customer.subscription.updated': StripeService._handle_subscription_updated,
            'customer.subscription.deleted': StripeService._handle_subscription_deleted,
        }

        handler = handler_map.get(event_type)
        if handler:
            handler(data_object)
            # Record processed event for idempotency
            if event_id:
                StripeWebhookEvent.objects.get_or_create(
                    stripe_event_id=event_id,
                    defaults={'event_type': event_type},
                )
        else:
            logger.info("Unhandled webhook event type: %s", event_type)

        return {'status': 'ok', 'event_type': event_type, 'event_id': event_id}

    # -----------------------------------------------------------------
    # Webhook event handlers (private)
    # -----------------------------------------------------------------

    @staticmethod
    def _handle_checkout_completed(session: dict) -> None:
        """
        Handle checkout.session.completed event.

        This fires when a user successfully completes the Stripe Checkout
        flow. We create or update a Subscription record and sync the user's
        plan on the User model.
        """
        user_id = session.get('metadata', {}).get('dreamplanner_user_id')
        plan_slug = session.get('metadata', {}).get('plan_slug')
        stripe_subscription_id = session.get('subscription')

        if not user_id or not stripe_subscription_id:
            logger.error(
                "checkout.session.completed missing metadata: user_id=%s, sub_id=%s",
                user_id,
                stripe_subscription_id,
            )
            return

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error("User %s from checkout metadata not found", user_id)
            return

        plan = SubscriptionPlan.objects.filter(slug=plan_slug).first()
        if not plan:
            logger.error("Plan '%s' from checkout metadata not found", plan_slug)
            return

        # Retrieve the full subscription from Stripe for period info
        try:
            stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
        except stripe.error.StripeError:
            logger.exception("Failed to retrieve subscription %s", stripe_subscription_id)
            return

        period_start = _timestamp_to_datetime(stripe_sub.get('current_period_start'))
        period_end = _timestamp_to_datetime(stripe_sub.get('current_period_end'))

        # Create or update local subscription record
        Subscription.objects.update_or_create(
            user=user,
            defaults={
                'plan': plan,
                'stripe_subscription_id': stripe_subscription_id,
                'status': stripe_sub.get('status', 'active'),
                'current_period_start': period_start,
                'current_period_end': period_end,
                'cancel_at_period_end': stripe_sub.get('cancel_at_period_end', False),
            },
        )

        # Sync user model
        _sync_user_subscription(user, plan, period_end)

        logger.info(
            "Checkout completed: user %s subscribed to %s (sub: %s)",
            user.email,
            plan.name,
            stripe_subscription_id,
        )

    @staticmethod
    def _handle_invoice_paid(invoice: dict) -> None:
        """
        Handle invoice.paid event.

        Fires when a recurring invoice is successfully paid. We update
        the billing period on the subscription to reflect the new cycle.
        """
        stripe_subscription_id = invoice.get('subscription')
        if not stripe_subscription_id:
            return

        subscription = Subscription.objects.filter(
            stripe_subscription_id=stripe_subscription_id,
        ).first()

        if not subscription:
            logger.warning(
                "invoice.paid for unknown subscription %s", stripe_subscription_id
            )
            return

        # Retrieve updated subscription from Stripe
        try:
            stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
        except stripe.error.StripeError:
            logger.exception("Failed to retrieve subscription %s", stripe_subscription_id)
            return

        period_start = _timestamp_to_datetime(stripe_sub.get('current_period_start'))
        period_end = _timestamp_to_datetime(stripe_sub.get('current_period_end'))

        subscription.status = stripe_sub.get('status', 'active')
        subscription.current_period_start = period_start
        subscription.current_period_end = period_end
        subscription.save(update_fields=[
            'status', 'current_period_start', 'current_period_end', 'updated_at',
        ])

        # Sync user model
        _sync_user_subscription(subscription.user, subscription.plan, period_end)

        # Send email receipt asynchronously
        try:
            from apps.subscriptions.tasks import send_payment_receipt_email
            amount_str = f"${invoice.get('amount_paid', 0) / 100:.2f}"
            send_payment_receipt_email.delay(
                user_id=str(subscription.user.id),
                plan_name=subscription.plan.name,
                amount=amount_str,
                invoice_url=invoice.get('hosted_invoice_url', ''),
            )
        except Exception:
            logger.exception("Failed to queue payment receipt email")

        logger.info(
            "Invoice paid for subscription %s (user: %s)",
            stripe_subscription_id,
            subscription.user.email,
        )

    @staticmethod
    def _handle_invoice_payment_failed(invoice: dict) -> None:
        """
        Handle invoice.payment_failed event.

        Fires when a payment attempt on a subscription invoice fails.
        We mark the subscription as ``past_due`` so the app can display
        a warning to the user.
        """
        stripe_subscription_id = invoice.get('subscription')
        if not stripe_subscription_id:
            return

        subscription = Subscription.objects.filter(
            stripe_subscription_id=stripe_subscription_id,
        ).first()

        if not subscription:
            logger.warning(
                "invoice.payment_failed for unknown subscription %s",
                stripe_subscription_id,
            )
            return

        subscription.status = 'past_due'
        subscription.save(update_fields=['status', 'updated_at'])

        logger.warning(
            "Payment failed for subscription %s (user: %s)",
            stripe_subscription_id,
            subscription.user.email,
        )

    @staticmethod
    def _handle_subscription_updated(stripe_sub: dict) -> None:
        """
        Handle customer.subscription.updated event.

        Fires whenever a subscription's attributes change (plan switch,
        status change, cancellation scheduled, etc.). We mirror the
        relevant fields into our local record.
        """
        stripe_subscription_id = stripe_sub.get('id')

        subscription = Subscription.objects.filter(
            stripe_subscription_id=stripe_subscription_id,
        ).select_related('user', 'plan').first()

        if not subscription:
            logger.warning(
                "subscription.updated for unknown subscription %s",
                stripe_subscription_id,
            )
            return

        period_start = _timestamp_to_datetime(stripe_sub.get('current_period_start'))
        period_end = _timestamp_to_datetime(stripe_sub.get('current_period_end'))

        # Check if the plan changed (by looking at the price in the items)
        items = stripe_sub.get('items', {}).get('data', [])
        if items:
            new_price_id = items[0].get('price', {}).get('id', '')
            if new_price_id:
                new_plan = SubscriptionPlan.objects.filter(
                    stripe_price_id=new_price_id,
                ).first()
                if new_plan and new_plan.id != subscription.plan_id:
                    subscription.plan = new_plan
                    logger.info(
                        "Subscription %s plan changed to %s",
                        stripe_subscription_id,
                        new_plan.name,
                    )

        subscription.status = stripe_sub.get('status', subscription.status)
        subscription.current_period_start = period_start
        subscription.current_period_end = period_end
        subscription.cancel_at_period_end = stripe_sub.get(
            'cancel_at_period_end', subscription.cancel_at_period_end
        )
        subscription.save()

        # Sync user model
        _sync_user_subscription(subscription.user, subscription.plan, period_end)

        logger.info(
            "Subscription %s updated (status: %s, user: %s)",
            stripe_subscription_id,
            subscription.status,
            subscription.user.email,
        )

    @staticmethod
    def _handle_subscription_deleted(stripe_sub: dict) -> None:
        """
        Handle customer.subscription.deleted event.

        Fires when a subscription is fully canceled (not just scheduled to
        cancel). We mark the local record as canceled and revert the user
        to the free tier.
        """
        stripe_subscription_id = stripe_sub.get('id')

        subscription = Subscription.objects.filter(
            stripe_subscription_id=stripe_subscription_id,
        ).select_related('user').first()

        if not subscription:
            logger.warning(
                "subscription.deleted for unknown subscription %s",
                stripe_subscription_id,
            )
            return

        subscription.status = 'canceled'
        subscription.save(update_fields=['status', 'updated_at'])

        # Revert user to free tier
        user = subscription.user
        user.subscription = 'free'
        user.subscription_ends = None
        user.save(update_fields=['subscription', 'subscription_ends', 'updated_at'])

        logger.info(
            "Subscription %s deleted, user %s reverted to free tier",
            stripe_subscription_id,
            user.email,
        )

    # -----------------------------------------------------------------
    # Invoice & Analytics
    # -----------------------------------------------------------------

    @staticmethod
    def list_invoices(user: User, limit: int = 10) -> list:
        """
        Fetch recent invoices for the user from Stripe.

        Args:
            user: The user whose invoices to fetch.
            limit: Maximum number of invoices to return.

        Returns:
            List of invoice dicts.
        """
        stripe_customer = StripeCustomer.objects.filter(user=user).first()
        if not stripe_customer:
            return []

        try:
            invoices = stripe.Invoice.list(
                customer=stripe_customer.stripe_customer_id,
                limit=limit,
            )
        except stripe.error.StripeError:
            logger.exception(
                "Failed to fetch invoices for user %s", user.email
            )
            raise

        result = []
        for inv in invoices.get('data', []):
            result.append({
                'id': inv['id'],
                'number': inv.get('number'),
                'amount_due': inv.get('amount_due', 0),
                'amount_paid': inv.get('amount_paid', 0),
                'currency': inv.get('currency', 'usd'),
                'status': inv.get('status', ''),
                'period_start': _timestamp_to_datetime(inv.get('period_start')),
                'period_end': _timestamp_to_datetime(inv.get('period_end')),
                'hosted_invoice_url': inv.get('hosted_invoice_url', ''),
                'invoice_pdf': inv.get('invoice_pdf', ''),
                'created': _timestamp_to_datetime(inv.get('created')),
            })
        return result

    @staticmethod
    def get_analytics() -> dict:
        """
        Compute subscription analytics (MRR, churn rate, conversion rate).

        Returns:
            Dict with analytics data.
        """
        from django.db.models import Sum, Count

        total_users = User.objects.filter(is_active=True).count()

        active_subs = Subscription.objects.filter(
            status__in=('active', 'trialing')
        ).select_related('plan')

        active_count = active_subs.count()

        # MRR = sum of all active subscription plan prices
        mrr = sum(
            float(sub.plan.price_monthly) for sub in active_subs
        )

        # Churn: canceled in last 30 days / active at start of period
        thirty_days_ago = timezone.now() - timedelta(days=30)
        canceled_count = Subscription.objects.filter(
            status='canceled',
            updated_at__gte=thirty_days_ago,
        ).count()

        churn_rate = 0.0
        if (active_count + canceled_count) > 0:
            churn_rate = round(
                canceled_count / (active_count + canceled_count) * 100, 2
            )

        # Conversion rate: paid / total users
        conversion_rate = 0.0
        if total_users > 0:
            conversion_rate = round(active_count / total_users * 100, 2)

        # Trialing count
        trialing_count = Subscription.objects.filter(status='trialing').count()

        return {
            'mrr': round(mrr, 2),
            'active_subscriptions': active_count,
            'trialing': trialing_count,
            'canceled_last_30d': canceled_count,
            'churn_rate_percent': churn_rate,
            'conversion_rate_percent': conversion_rate,
            'total_users': total_users,
        }

    # -----------------------------------------------------------------
    # Synchronization
    # -----------------------------------------------------------------

    @staticmethod
    def sync_subscription_status(user: User) -> Optional[Subscription]:
        """
        Synchronize a user's subscription state from Stripe into the database.

        Useful as a fallback when webhooks might have been missed or
        when you need to guarantee fresh data (e.g., before feature gating).

        Args:
            user: The user whose subscription to sync.

        Returns:
            The updated Subscription instance, or None if the user has no
            subscription.
        """
        subscription = Subscription.objects.filter(user=user).first()
        if not subscription:
            return None

        try:
            stripe_sub = stripe.Subscription.retrieve(
                subscription.stripe_subscription_id,
            )
        except stripe.error.InvalidRequestError:
            # Subscription no longer exists in Stripe
            logger.warning(
                "Subscription %s not found in Stripe, marking as canceled",
                subscription.stripe_subscription_id,
            )
            subscription.status = 'canceled'
            subscription.save(update_fields=['status', 'updated_at'])

            user.subscription = 'free'
            user.subscription_ends = None
            user.save(update_fields=['subscription', 'subscription_ends', 'updated_at'])
            return subscription

        except stripe.error.StripeError:
            logger.exception(
                "Failed to sync subscription %s from Stripe",
                subscription.stripe_subscription_id,
            )
            raise

        period_start = _timestamp_to_datetime(stripe_sub.get('current_period_start'))
        period_end = _timestamp_to_datetime(stripe_sub.get('current_period_end'))

        subscription.status = stripe_sub.get('status', subscription.status)
        subscription.current_period_start = period_start
        subscription.current_period_end = period_end
        subscription.cancel_at_period_end = stripe_sub.get(
            'cancel_at_period_end', False
        )
        subscription.save()

        # Sync user model
        _sync_user_subscription(user, subscription.plan, period_end)

        logger.info(
            "Synced subscription %s for user %s (status: %s)",
            subscription.stripe_subscription_id,
            user.email,
            subscription.status,
        )
        return subscription


# -------------------------------------------------------------------
# Module-level helpers
# -------------------------------------------------------------------

def _timestamp_to_datetime(ts) -> Optional[datetime]:
    """
    Convert a Unix timestamp (int/float) to a timezone-aware datetime.

    Args:
        ts: Unix timestamp or None.

    Returns:
        Timezone-aware datetime or None if input is falsy.
    """
    if ts is None:
        return None
    import datetime as _dt
    return datetime.fromtimestamp(int(ts), tz=_dt.timezone.utc)


def _sync_user_subscription(
    user: User,
    plan: SubscriptionPlan,
    period_end: Optional[datetime],
) -> None:
    """
    Sync the User model's subscription fields to match the given plan.

    This keeps the denormalized ``subscription`` and ``subscription_ends``
    fields on the User model in sync so that permission checks (e.g.,
    ``user.is_premium()``) work without joining to the Subscription table.

    Args:
        user: The user to update.
        plan: The plan to sync to.
        period_end: The end of the current billing period.
    """
    user.subscription = plan.slug
    user.subscription_ends = period_end
    user.save(update_fields=['subscription', 'subscription_ends', 'updated_at'])

    # Revoke features if downgrading
    _revoke_downgraded_features(user, plan)


def _revoke_downgraded_features(user, new_plan):
    """Revoke features that the user no longer has access to after a plan change."""
    import logging
    _logger = logging.getLogger(__name__)

    # Unequip store items if no longer premium
    if new_plan.slug not in ('premium', 'pro'):
        try:
            from apps.store.models import UserInventory
            UserInventory.objects.filter(
                user=user, is_equipped=True
            ).update(is_equipped=False)
        except Exception:
            _logger.exception("Failed to unequip store items for user %s", user.email)

    # End buddy pairings if buddy not included in plan
    if not getattr(new_plan, 'has_buddy', False):
        try:
            from apps.buddies.models import BuddyPairing
            from django.db.models import Q
            from django.utils import timezone
            BuddyPairing.objects.filter(
                Q(user1=user) | Q(user2=user),
                status__in=['pending', 'active']
            ).update(status='cancelled', ended_at=timezone.now())
        except Exception:
            _logger.exception("Failed to end buddy pairings for user %s on downgrade", user.email)
