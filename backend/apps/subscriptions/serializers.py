"""
DRF serializers for the Subscriptions app.

Provides serialization for subscription plans, active subscriptions,
Stripe customer records, and checkout initiation payloads.
"""

from rest_framework import serializers

from .models import StripeCustomer, Subscription, SubscriptionPlan


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Serializer for SubscriptionPlan.

    Used in the public plan listing so prospective and current users
    can compare tiers and feature sets.
    """

    is_free = serializers.BooleanField(read_only=True)
    has_unlimited_dreams = serializers.BooleanField(read_only=True)

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id',
            'name',
            'slug',
            'price_monthly',
            'features',
            'dream_limit',
            'has_ai',
            'has_buddy',
            'has_circles',
            'has_vision_board',
            'has_league',
            'has_ads',
            'is_free',
            'has_unlimited_dreams',
            'is_active',
        ]
        read_only_fields = fields


class StripeCustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for the StripeCustomer mapping.

    Primarily used in admin or debug endpoints; the customer ID
    itself is not exposed to end users.
    """

    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = StripeCustomer
        fields = [
            'id',
            'user',
            'user_email',
            'stripe_customer_id',
            'created_at',
        ]
        read_only_fields = fields


class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for the active Subscription record.

    Includes nested plan details so the client has everything it needs
    to render the subscription status in a single response.
    """

    plan = SubscriptionPlanSerializer(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'id',
            'plan',
            'stripe_subscription_id',
            'status',
            'current_period_start',
            'current_period_end',
            'cancel_at_period_end',
            'canceled_at',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class SubscriptionCreateSerializer(serializers.Serializer):
    """
    Input serializer for creating a Stripe Checkout Session.

    Accepts the plan slug (or plan ID) and optional redirect URLs.
    Validates that the requested plan exists and is purchasable.
    """

    plan_slug = serializers.SlugField(
        help_text='Slug of the plan to subscribe to (e.g., "premium", "pro")',
    )
    success_url = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text='URL to redirect to after successful payment',
    )
    cancel_url = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text='URL to redirect to if the user cancels checkout',
    )

    def validate_plan_slug(self, value):
        """Ensure the plan exists, is active, and is not the free tier."""
        try:
            plan = SubscriptionPlan.objects.get(slug=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError(
                f"No active subscription plan found with slug '{value}'."
            )

        if plan.is_free:
            raise serializers.ValidationError(
                "Cannot create a checkout session for the free plan."
            )

        return value

    def get_plan(self):
        """
        Return the validated SubscriptionPlan instance.

        Must be called after ``is_valid()`` has passed.
        """
        return SubscriptionPlan.objects.get(
            slug=self.validated_data['plan_slug'],
            is_active=True,
        )
