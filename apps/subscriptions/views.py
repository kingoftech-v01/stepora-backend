"""
Views for the Subscriptions app.

Provides endpoints for listing plans, managing the current subscription,
initiating Stripe Checkout, and receiving Stripe webhooks.
"""

import logging

import stripe
from django.http import HttpResponse
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, views, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from core.audit import log_webhook_event

from .models import Subscription, SubscriptionPlan
from .serializers import (
    InvoiceSerializer,
    PromotionSerializer,
    SubscriptionCreateSerializer,
    SubscriptionPlanSerializer,
    SubscriptionSerializer,
)
from .services import PromotionService, StripeService

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List subscription plans",
        description="Returns all active subscription plans with their features and pricing.",
        tags=["Subscriptions"],
    ),
    retrieve=extend_schema(
        summary="Get subscription plan detail",
        description="Returns details for a single subscription plan.",
        tags=["Subscriptions"],
    ),
)
class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """Public read-only viewset for subscription plans."""

    permission_classes = [AllowAny]
    # No custom throttle — uses global defaults (anon: 20/min, user: 100/min).
    # Plans are a public read-only list; no need for per-user search throttle.
    throttle_classes = []
    serializer_class = SubscriptionPlanSerializer
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    lookup_field = "slug"

    def list(self, request, *args, **kwargs):
        """Override list to inject active promotions per plan."""
        queryset = self.filter_queryset(self.get_queryset())

        promos_by_plan = {}
        if request.user.is_authenticated:
            active_promos = PromotionService.get_active_promotions(request.user)
            for promo in active_promos:
                for disc in promo.plan_discounts.all():
                    plan_id = str(disc.plan_id)
                    promos_by_plan.setdefault(plan_id, []).append(promo)

        serializer = self.get_serializer(
            queryset,
            many=True,
            context={
                **self.get_serializer_context(),
                "active_promotions_by_plan": promos_by_plan,
            },
        )
        return Response(serializer.data)


class SubscriptionViewSet(viewsets.GenericViewSet):
    """Viewset for managing the authenticated user's subscription."""

    permission_classes = [IsAuthenticated]
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        """Scope to the current user's subscription only."""
        if getattr(self, "swagger_fake_view", False):
            return Subscription.objects.none()
        return Subscription.objects.filter(user=self.request.user)

    @extend_schema(
        summary="Get current subscription",
        description="Returns the authenticated user's active subscription details.",
        tags=["Subscriptions"],
        responses={
            200: SubscriptionSerializer,
            404: OpenApiResponse(description="No active subscription"),
        },
    )
    @action(detail=False, methods=["get"])
    def current(self, request):
        """Get the current user's subscription."""
        subscription = Subscription.objects.filter(user=request.user).first()
        if not subscription:
            logger.error(
                "User %s has no subscription record. This should never happen — "
                "the post_save signal must create one at registration.",
                request.user.id,
            )
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)

    @extend_schema(
        summary="Create checkout session",
        description="Creates a Stripe Checkout Session and returns the checkout URL.",
        tags=["Subscriptions"],
        request=SubscriptionCreateSerializer,
        responses={
            200: OpenApiResponse(description="Checkout session URL returned"),
            400: OpenApiResponse(description="Invalid plan or validation error"),
            502: OpenApiResponse(description="Payment service error."),
        },
    )
    @action(detail=False, methods=["post"])
    def checkout(self, request):
        """Create a Stripe Checkout Session for a plan upgrade.

        If the target plan is the free tier, this endpoint handles it as a
        downgrade: it cancels the current Stripe subscription instead of
        trying to create a checkout session (which would fail).
        """
        serializer = SubscriptionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        plan = serializer.get_plan()

        # Free-plan downgrade: cancel the Stripe subscription locally
        # instead of routing through Stripe Checkout.
        if plan.is_free:
            try:
                subscription = StripeService.cancel_subscription(request.user)
            except stripe.error.StripeError:
                logger.exception("Stripe error during downgrade to free")
                return Response(
                    {"detail": _("Payment service error. Please try again later.")},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            if not subscription:
                return Response(
                    {"detail": _("No active subscription to cancel.")},
                    status=status.HTTP_404_NOT_FOUND,
                )

            sub_serializer = SubscriptionSerializer(subscription)
            return Response(
                {
                    "action": "downgrade_scheduled",
                    "subscription": sub_serializer.data,
                }
            )

        # Resolve promotion → Stripe coupon code
        coupon_code = serializer.validated_data.get("coupon_code", "")
        promotion_id = serializer.validated_data.get("promotion_id")
        promo_discount = None

        if promotion_id and not coupon_code:
            try:
                promo_discount = PromotionService.get_discount_for_checkout(
                    request.user, promotion_id, plan
                )
                coupon_code = promo_discount.stripe_coupon_id
            except ValueError as e:
                return Response(
                    {"detail": str(e)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            session = StripeService.create_checkout_session(
                user=request.user,
                plan=plan,
                success_url=serializer.validated_data.get("success_url", ""),
                cancel_url=serializer.validated_data.get("cancel_url", ""),
                coupon_code=coupon_code,
                promotion_id=str(promotion_id) if promotion_id else "",
            )
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except stripe.error.StripeError:
            logger.exception("Stripe error during checkout creation")
            return Response(
                {"detail": _("Payment service error. Please try again later.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # NOTE: promotion redemption is recorded in the checkout.session.completed
        # webhook handler — NOT here. Recording it before payment is confirmed
        # would hide the promo if the user cancels checkout.

        return Response(
            {
                "checkout_url": session.url,
                "session_id": session.id,
            }
        )

    @extend_schema(
        summary="Create billing portal session",
        description="Creates a Stripe Billing Portal Session for self-service management.",
        tags=["Subscriptions"],
        responses={
            200: OpenApiResponse(description="Portal URL returned"),
            400: OpenApiResponse(description="No Stripe customer record"),
            502: OpenApiResponse(description="Payment service error."),
        },
    )
    @action(detail=False, methods=["post"])
    def portal(self, request):
        """Create a Stripe Billing Portal session."""
        return_url = request.data.get("return_url", "")

        try:
            session = StripeService.create_portal_session(
                user=request.user,
                return_url=return_url,
            )
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except stripe.error.StripeError:
            logger.exception("Stripe error during portal session creation")
            return Response(
                {"detail": _("Payment service error. Please try again later.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "portal_url": session.url,
            }
        )

    @extend_schema(
        summary="Cancel subscription",
        description="Cancels the current subscription at the end of the billing period.",
        tags=["Subscriptions"],
        responses={
            200: SubscriptionSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="No active subscription to cancel"),
            502: OpenApiResponse(description="Payment service error."),
        },
    )
    @action(detail=False, methods=["post"])
    def cancel(self, request):
        """Cancel the current subscription at period end."""
        try:
            subscription = StripeService.cancel_subscription(request.user)
        except stripe.error.StripeError:
            logger.exception("Stripe error during cancellation")
            return Response(
                {"detail": _("Payment service error. Please try again later.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not subscription:
            return Response(
                {"detail": _("No active subscription to cancel.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)

    @extend_schema(
        summary="Reactivate subscription",
        description="Reverses a pending cancellation.",
        tags=["Subscriptions"],
        responses={
            200: SubscriptionSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="No subscription pending cancellation"),
            502: OpenApiResponse(description="Payment service error."),
        },
    )
    @action(detail=False, methods=["post"])
    def reactivate(self, request):
        """Reactivate a subscription that was set to cancel."""
        try:
            subscription = StripeService.reactivate_subscription(request.user)
        except stripe.error.StripeError:
            logger.exception("Stripe error during reactivation")
            return Response(
                {"detail": _("Payment service error. Please try again later.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not subscription:
            return Response(
                {"detail": _("No subscription pending cancellation to reactivate.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)

    @extend_schema(
        summary="Change subscription plan",
        description=(
            "Upgrade or downgrade the current subscription. "
            "Upgrades apply immediately with proration. "
            "Downgrades are scheduled for the end of the billing period."
        ),
        tags=["Subscriptions"],
        request={
            "application/json": {
                "type": "object",
                "properties": {"plan_slug": {"type": "string"}},
            }
        },
        responses={
            200: OpenApiResponse(description="Plan change result"),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Plan not found"),
            502: OpenApiResponse(description="Payment service error"),
        },
    )
    @action(detail=False, methods=["post"], url_path="change-plan")
    def change_plan(self, request):
        """Change the user's subscription plan (upgrade or downgrade)."""
        plan_slug = request.data.get("plan_slug", "")
        if not plan_slug:
            return Response(
                {"detail": _("plan_slug is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plan = SubscriptionPlan.objects.filter(slug=plan_slug, is_active=True).first()
        if not plan:
            return Response(
                {
                    "detail": _("No active plan found with slug '%(slug)s'.")
                    % {"slug": plan_slug}
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = StripeService.change_plan(request.user, plan)
        except ValueError as e:
            msg = str(e)
            if msg.startswith("requires_checkout:"):
                return Response(
                    {
                        "code": "requires_checkout",
                        "detail": msg[len("requires_checkout:"):],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"detail": msg},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except stripe.error.StripeError:
            logger.exception("Stripe error during plan change")
            return Response(
                {"detail": _("Payment service error. Please try again later.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        serializer = SubscriptionSerializer(result["subscription"])
        return Response(
            {
                "action": result["action"],
                "subscription": serializer.data,
            }
        )

    @extend_schema(
        summary="Cancel pending plan change",
        description="Cancel a scheduled downgrade so the current plan continues.",
        tags=["Subscriptions"],
        responses={
            200: SubscriptionSerializer,
            404: OpenApiResponse(description="No pending change to cancel"),
            502: OpenApiResponse(description="Payment service error"),
        },
    )
    @action(detail=False, methods=["post"], url_path="cancel-pending-change")
    def cancel_pending_change(self, request):
        """Cancel a pending downgrade."""
        try:
            subscription = StripeService.cancel_pending_change(request.user)
        except stripe.error.StripeError:
            logger.exception("Stripe error cancelling pending change")
            return Response(
                {"detail": _("Payment service error. Please try again later.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not subscription:
            return Response(
                {"detail": _("No pending plan change to cancel.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)

    @extend_schema(
        summary="Sync subscription from Stripe",
        description="Forces a refresh of the subscription state from Stripe.",
        tags=["Subscriptions"],
        responses={
            200: SubscriptionSerializer,
            404: OpenApiResponse(description="No subscription to sync"),
            502: OpenApiResponse(description="Payment service error."),
        },
    )
    @action(detail=False, methods=["post"])
    def sync(self, request):
        """Force-sync subscription status from Stripe."""
        try:
            subscription = StripeService.sync_subscription_status(request.user)
        except stripe.error.StripeError:
            logger.exception("Stripe error during subscription sync")
            return Response(
                {"detail": _("Payment service error. Please try again later.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not subscription:
            return Response(
                {"detail": _("No subscription found to sync.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)

    @extend_schema(
        summary="List invoices",
        description="Fetch recent invoices from Stripe for the current user.",
        tags=["Subscriptions"],
        responses={
            200: InvoiceSerializer(many=True),
            502: OpenApiResponse(description="Payment service error."),
        },
    )
    @action(detail=False, methods=["get"])
    def invoices(self, request):
        """Get invoice history for the current user."""
        try:
            invoices = StripeService.list_invoices(request.user)
        except stripe.error.StripeError:
            logger.exception("Stripe error fetching invoices")
            return Response(
                {"detail": _("Payment service error. Please try again later.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        serializer = InvoiceSerializer(invoices, many=True)
        # Return in paginated format compatible with useInfiniteList
        return Response(
            {
                "results": serializer.data,
                "count": len(serializer.data),
                "next": None,
                "previous": None,
            }
        )

    @extend_schema(
        summary="Apply coupon code",
        description="Apply a Stripe coupon/promotion code to the current subscription.",
        tags=["Subscriptions"],
        request={
            "application/json": {
                "type": "object",
                "properties": {"coupon_code": {"type": "string"}},
            }
        },
        responses={
            200: OpenApiResponse(description="Coupon applied successfully"),
            400: OpenApiResponse(
                description="Invalid coupon or no active subscription"
            ),
            502: OpenApiResponse(description="Payment service error"),
        },
    )
    @action(detail=False, methods=["post"], url_path="current/apply-coupon")
    def apply_coupon(self, request):
        """Apply a coupon code to the current subscription."""
        from core.validators import validate_coupon_code

        coupon_code = (request.data.get("coupon_code") or "").strip()
        if not coupon_code:
            return Response(
                {"detail": _("Coupon code is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            coupon_code = validate_coupon_code(coupon_code)
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            subscription = StripeService.apply_coupon(request.user, coupon_code)
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except stripe.error.StripeError:
            logger.exception("Stripe error applying coupon")
            return Response(
                {"detail": _("Payment service error. Please try again later.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        serializer = SubscriptionSerializer(subscription)
        return Response(
            {
                "message": _("Coupon applied successfully!"),
                "subscription": serializer.data,
            }
        )

    @extend_schema(
        summary="Subscription analytics",
        description="Get subscription analytics (MRR, churn, conversion). Admin only.",
        tags=["Subscriptions"],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], permission_classes=[IsAdminUser])
    def analytics(self, request):
        """Get subscription analytics (admin only)."""
        analytics = StripeService.get_analytics()
        return Response(analytics)



# ReferralView moved to apps.referrals.views — /api/v1/referrals/


class PromotionViewSet(viewsets.GenericViewSet):
    """Viewset for listing active promotions available to the current user."""

    permission_classes = [IsAuthenticated]
    serializer_class = PromotionSerializer

    @extend_schema(
        summary="List active promotions",
        description="Returns promotions currently available to the authenticated user.",
        tags=["Subscriptions"],
        responses={200: PromotionSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get active promotions for the current user."""
        promotions = PromotionService.get_active_promotions(request.user)
        serializer = PromotionSerializer(promotions, many=True)
        return Response(serializer.data)


class StripeWebhookView(views.APIView):
    """Endpoint for receiving Stripe webhook events."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Stripe webhook endpoint",
        description="Receives and processes Stripe webhook events.",
        tags=["Subscriptions"],
        request=None,
        responses={
            200: OpenApiResponse(description="Event processed successfully"),
            400: OpenApiResponse(description="Invalid payload or signature"),
        },
    )
    def post(self, request):
        """Handle incoming Stripe webhook events."""
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        if not sig_header:
            return HttpResponse(
                "Missing Stripe-Signature header",
                status=400,
            )

        try:
            result = StripeService.handle_webhook_event(payload, sig_header)
            log_webhook_event(
                result.get("event_type", "unknown"),
                result.get("event_id", "unknown"),
                "processed",
            )
        except ValueError as e:
            logger.warning("Webhook signature verification failed: %s", e)
            log_webhook_event("unknown", "unknown", "signature_failed")
            return HttpResponse(str(e), status=400)
        except Exception:
            logger.exception("Unexpected error processing webhook")
            log_webhook_event("unknown", "unknown", "error")
            return HttpResponse("Webhook processing error", status=500)

        return Response(result, status=status.HTTP_200_OK)
