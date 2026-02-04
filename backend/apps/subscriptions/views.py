"""
Views for the Subscriptions app.

Provides endpoints for listing plans, managing the current subscription,
initiating Stripe Checkout, and receiving Stripe webhooks.
"""

import logging

import stripe
from django.http import HttpResponse
from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

from .models import SubscriptionPlan, Subscription
from .serializers import (
    SubscriptionPlanSerializer,
    SubscriptionSerializer,
    SubscriptionCreateSerializer,
)
from .services import StripeService

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
    """
    Public read-only viewset for subscription plans.

    Anyone (authenticated or not) can view available plans so the
    pricing page works without requiring login.
    """

    permission_classes = [AllowAny]
    serializer_class = SubscriptionPlanSerializer
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    lookup_field = 'slug'


@extend_schema_view()
class SubscriptionViewSet(viewsets.GenericViewSet):
    """
    Viewset for managing the authenticated user's subscription.

    Provides actions to view the current subscription, create a checkout
    session, cancel, and reactivate.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        """Scope to the current user's subscription only."""
        return Subscription.objects.filter(user=self.request.user)

    @extend_schema(
        summary="Get current subscription",
        description=(
            "Returns the authenticated user's active subscription details. "
            "Returns 404 if the user has no subscription (free tier)."
        ),
        tags=["Subscriptions"],
        responses={
            200: SubscriptionSerializer,
            404: OpenApiResponse(description="No active subscription"),
        },
    )
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get the current user's subscription."""
        subscription = Subscription.objects.filter(user=request.user).first()
        if not subscription:
            return Response(
                {
                    'detail': 'No active subscription. You are on the free plan.',
                    'plan': 'free',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)

    @extend_schema(
        summary="Create checkout session",
        description=(
            "Creates a Stripe Checkout Session and returns the checkout URL. "
            "The client should redirect the user to this URL to complete payment."
        ),
        tags=["Subscriptions"],
        request=SubscriptionCreateSerializer,
        responses={
            200: OpenApiResponse(description="Checkout session URL returned"),
            400: OpenApiResponse(description="Invalid plan or validation error"),
        },
    )
    @action(detail=False, methods=['post'])
    def checkout(self, request):
        """Create a Stripe Checkout Session for a plan upgrade."""
        serializer = SubscriptionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        plan = serializer.get_plan()

        try:
            session = StripeService.create_checkout_session(
                user=request.user,
                plan=plan,
                success_url=serializer.validated_data.get('success_url', ''),
                cancel_url=serializer.validated_data.get('cancel_url', ''),
            )
        except ValueError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except stripe.error.StripeError as e:
            logger.exception("Stripe error during checkout creation")
            return Response(
                {'detail': 'Payment service error. Please try again later.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({
            'checkout_url': session.url,
            'session_id': session.id,
        })

    @extend_schema(
        summary="Create billing portal session",
        description=(
            "Creates a Stripe Billing Portal Session for self-service "
            "subscription management. Returns the portal URL."
        ),
        tags=["Subscriptions"],
        responses={
            200: OpenApiResponse(description="Portal URL returned"),
            400: OpenApiResponse(description="No Stripe customer record"),
        },
    )
    @action(detail=False, methods=['post'])
    def portal(self, request):
        """Create a Stripe Billing Portal session."""
        return_url = request.data.get('return_url', '')

        try:
            session = StripeService.create_portal_session(
                user=request.user,
                return_url=return_url,
            )
        except ValueError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except stripe.error.StripeError:
            logger.exception("Stripe error during portal session creation")
            return Response(
                {'detail': 'Payment service error. Please try again later.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({
            'portal_url': session.url,
        })

    @extend_schema(
        summary="Cancel subscription",
        description=(
            "Cancels the current subscription at the end of the billing period. "
            "The user retains access until the period ends."
        ),
        tags=["Subscriptions"],
        responses={
            200: SubscriptionSerializer,
            404: OpenApiResponse(description="No active subscription to cancel"),
        },
    )
    @action(detail=False, methods=['post'])
    def cancel(self, request):
        """Cancel the current subscription at period end."""
        try:
            subscription = StripeService.cancel_subscription(request.user)
        except stripe.error.StripeError:
            logger.exception("Stripe error during cancellation")
            return Response(
                {'detail': 'Payment service error. Please try again later.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not subscription:
            return Response(
                {'detail': 'No active subscription to cancel.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)

    @extend_schema(
        summary="Reactivate subscription",
        description=(
            "Reverses a pending cancellation so the subscription renews "
            "at the next billing cycle."
        ),
        tags=["Subscriptions"],
        responses={
            200: SubscriptionSerializer,
            404: OpenApiResponse(description="No subscription pending cancellation"),
        },
    )
    @action(detail=False, methods=['post'])
    def reactivate(self, request):
        """Reactivate a subscription that was set to cancel."""
        try:
            subscription = StripeService.reactivate_subscription(request.user)
        except stripe.error.StripeError:
            logger.exception("Stripe error during reactivation")
            return Response(
                {'detail': 'Payment service error. Please try again later.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not subscription:
            return Response(
                {'detail': 'No subscription pending cancellation to reactivate.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)

    @extend_schema(
        summary="Sync subscription from Stripe",
        description=(
            "Forces a refresh of the subscription state from Stripe. "
            "Useful if webhook delivery was delayed."
        ),
        tags=["Subscriptions"],
        responses={
            200: SubscriptionSerializer,
            404: OpenApiResponse(description="No subscription to sync"),
        },
    )
    @action(detail=False, methods=['post'])
    def sync(self, request):
        """Force-sync subscription status from Stripe."""
        try:
            subscription = StripeService.sync_subscription_status(request.user)
        except stripe.error.StripeError:
            logger.exception("Stripe error during subscription sync")
            return Response(
                {'detail': 'Payment service error. Please try again later.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not subscription:
            return Response(
                {'detail': 'No subscription found to sync.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)


class StripeWebhookView(views.APIView):
    """
    Endpoint for receiving Stripe webhook events.

    This view is exempt from authentication because Stripe sends
    the events directly. We verify authenticity using the webhook
    signing secret instead.
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # No auth required for webhooks

    @extend_schema(
        summary="Stripe webhook endpoint",
        description=(
            "Receives and processes Stripe webhook events. "
            "Verifies the payload signature before processing."
        ),
        tags=["Subscriptions"],
        request=None,
        responses={
            200: OpenApiResponse(description="Event processed successfully"),
            400: OpenApiResponse(description="Invalid payload or signature"),
        },
    )
    def post(self, request):
        """
        Handle incoming Stripe webhook events.

        The raw body is passed to the service layer which verifies the
        signature and dispatches to the appropriate handler.
        """
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

        if not sig_header:
            return HttpResponse(
                'Missing Stripe-Signature header',
                status=400,
            )

        try:
            result = StripeService.handle_webhook_event(payload, sig_header)
        except ValueError as e:
            logger.warning("Webhook signature verification failed: %s", e)
            return HttpResponse(str(e), status=400)
        except Exception:
            logger.exception("Unexpected error processing webhook")
            return HttpResponse('Webhook processing error', status=500)

        return Response(result, status=status.HTTP_200_OK)
