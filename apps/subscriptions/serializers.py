"""
DRF serializers for the Subscriptions app.

Provides serialization for subscription plans, active subscriptions,
Stripe customer records, and checkout initiation payloads.
"""

from rest_framework import serializers

from core.validators import validate_coupon_code
from .models import StripeCustomer, Subscription, SubscriptionPlan


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for SubscriptionPlan."""

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
            'trial_period_days',
            'is_free',
            'has_unlimited_dreams',
            'is_active',
        ]
        read_only_fields = fields


class StripeCustomerSerializer(serializers.ModelSerializer):
    """Serializer for the StripeCustomer mapping."""

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
    """Serializer for the active Subscription record."""

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
    """Input serializer for creating a Stripe Checkout Session."""

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
    coupon_code = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        help_text='Optional Stripe coupon/promo code',
    )

    def validate_coupon_code(self, value):
        """Validate coupon code format."""
        if value:
            return validate_coupon_code(value)
        return value

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
        """Return the validated SubscriptionPlan instance."""
        return SubscriptionPlan.objects.get(
            slug=self.validated_data['plan_slug'],
            is_active=True,
        )


class InvoiceSerializer(serializers.Serializer):
    """Serializer for Stripe invoice data."""

    id = serializers.CharField(help_text='Stripe invoice ID')
    number = serializers.CharField(allow_null=True, help_text='Invoice number')
    amount_due = serializers.IntegerField(help_text='Amount due in cents')
    amount_paid = serializers.IntegerField(help_text='Amount paid in cents')
    currency = serializers.CharField(help_text='Currency code')
    status = serializers.CharField(help_text='Invoice status')
    period_start = serializers.DateTimeField(allow_null=True)
    period_end = serializers.DateTimeField(allow_null=True)
    hosted_invoice_url = serializers.URLField(allow_null=True, allow_blank=True)
    invoice_pdf = serializers.URLField(allow_null=True, allow_blank=True)
    created = serializers.DateTimeField()
