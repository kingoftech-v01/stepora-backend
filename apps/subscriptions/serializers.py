"""
DRF serializers for the Subscriptions app.

Provides serialization for subscription plans, active subscriptions,
Stripe customer records, and checkout initiation payloads.
"""

from rest_framework import serializers

from core.validators import validate_coupon_code

from .models import (
    Promotion,
    PromotionPlanDiscount,
    StripeCustomer,
    Subscription,
    SubscriptionPlan,
)


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for SubscriptionPlan."""

    is_free = serializers.BooleanField(
        read_only=True, help_text="Whether this is the free tier plan."
    )
    has_unlimited_dreams = serializers.BooleanField(
        read_only=True, help_text="Whether the plan allows unlimited dreams."
    )
    active_promotions = serializers.SerializerMethodField(
        help_text="Active promotions available for this plan."
    )

    def get_active_promotions(self, obj):
        promos_by_plan = self.context.get("active_promotions_by_plan", {})
        promos = promos_by_plan.get(str(obj.id), [])
        if not promos:
            return []
        # Avoid circular import — PromotionSerializer is defined later in same file
        return PromotionSerializer(promos, many=True, context=self.context).data

    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "name",
            "slug",
            "price_monthly",
            "features",
            "dream_limit",
            "has_ai",
            "has_buddy",
            "has_circles",
            "has_circle_create",
            "has_vision_board",
            "has_league",
            "has_store",
            "has_social_feed",
            "has_ads",
            "trial_period_days",
            "is_free",
            "has_unlimited_dreams",
            "is_active",
            "active_promotions",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the plan."},
            "name": {"help_text": "Display name of the subscription plan."},
            "slug": {"help_text": "URL-friendly identifier for the plan."},
            "price_monthly": {"help_text": "Monthly price of the plan."},
            "features": {"help_text": "List of features included in the plan."},
            "dream_limit": {"help_text": "Maximum number of dreams allowed."},
            "has_ai": {"help_text": "Whether AI features are included."},
            "has_buddy": {"help_text": "Whether buddy features are included."},
            "has_circles": {"help_text": "Whether circle features are included."},
            "has_circle_create": {"help_text": "Whether the user can create circles."},
            "has_vision_board": {"help_text": "Whether vision board is included."},
            "has_league": {"help_text": "Whether league access is included."},
            "has_store": {"help_text": "Whether rewards store is included."},
            "has_social_feed": {"help_text": "Whether social feed is included."},
            "has_ads": {"help_text": "Whether the plan shows ads."},
            "trial_period_days": {"help_text": "Number of free trial days offered."},
            "is_active": {"help_text": "Whether this plan is currently available."},
        }


class StripeCustomerSerializer(serializers.ModelSerializer):
    """Serializer for the StripeCustomer mapping."""

    user_email = serializers.EmailField(
        source="user.email", read_only=True, help_text="Email address of the customer."
    )

    class Meta:
        model = StripeCustomer
        fields = [
            "id",
            "user",
            "user_email",
            "stripe_customer_id",
            "created_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the customer record."},
            "user": {"help_text": "User linked to this Stripe customer."},
            "stripe_customer_id": {
                "help_text": "Stripe customer ID for payment processing."
            },
            "created_at": {
                "help_text": "Timestamp when the customer record was created."
            },
        }


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for the active Subscription record."""

    plan = SubscriptionPlanSerializer(
        read_only=True, help_text="Details of the subscription plan."
    )
    pending_plan = SubscriptionPlanSerializer(
        read_only=True, help_text="Plan the user is downgrading to at period end."
    )
    is_active = serializers.BooleanField(
        read_only=True, help_text="Whether the subscription is currently active."
    )

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "stripe_subscription_id",
            "status",
            "current_period_start",
            "current_period_end",
            "cancel_at_period_end",
            "canceled_at",
            "pending_plan",
            "pending_plan_effective_date",
            "stripe_schedule_id",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the subscription."},
            "stripe_subscription_id": {
                "help_text": "Stripe subscription ID for billing."
            },
            "status": {"help_text": "Current status of the subscription."},
            "current_period_start": {
                "help_text": "Start of the current billing period."
            },
            "current_period_end": {"help_text": "End of the current billing period."},
            "cancel_at_period_end": {
                "help_text": "Whether the subscription cancels at period end."
            },
            "canceled_at": {
                "help_text": "Timestamp when the subscription was canceled."
            },
            "pending_plan_effective_date": {
                "help_text": "When the pending plan change takes effect."
            },
            "stripe_schedule_id": {
                "help_text": "Stripe SubscriptionSchedule ID for pending downgrades."
            },
            "created_at": {"help_text": "Timestamp when the subscription was created."},
            "updated_at": {
                "help_text": "Timestamp when the subscription was last updated."
            },
        }


class PromotionPlanDiscountSerializer(serializers.ModelSerializer):
    """Serializer for a plan-specific discount within a promotion."""

    plan = SubscriptionPlanSerializer(read_only=True)
    discounted_price = serializers.SerializerMethodField()

    class Meta:
        model = PromotionPlanDiscount
        fields = [
            "id",
            "plan",
            "discount_value",
            "discounted_price",
        ]
        read_only_fields = fields

    def get_discounted_price(self, obj):
        price = float(obj.plan.price_monthly)
        value = float(obj.discount_value)
        if obj.promotion.discount_type == "percentage":
            return round(price * (1 - value / 100), 2)
        return round(max(0.0, price - value), 2)


class PromotionSerializer(serializers.ModelSerializer):
    """Serializer for active promotions visible to users."""

    plan_discounts = PromotionPlanDiscountSerializer(many=True, read_only=True)
    spots_remaining = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Promotion
        fields = [
            "id",
            "name",
            "description",
            "end_date",
            "duration_days",
            "discount_type",
            "plan_discounts",
            "spots_remaining",
        ]
        read_only_fields = fields


class SubscriptionCreateSerializer(serializers.Serializer):
    """Input serializer for creating a Stripe Checkout Session."""

    plan_slug = serializers.SlugField(
        help_text='Slug of the plan to subscribe to (e.g., "premium", "pro")',
    )
    success_url = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="URL to redirect to after successful payment (supports custom schemes)",
    )
    cancel_url = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="URL to redirect to if the user cancels checkout (supports custom schemes)",
    )
    coupon_code = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional Stripe coupon/promo code",
    )
    promotion_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Optional promotion ID to apply the promo discount",
    )

    def validate_coupon_code(self, value):
        """Validate coupon code format."""
        if value:
            return validate_coupon_code(value)
        return value

    def validate_plan_slug(self, value):
        """Ensure the plan exists and is active."""
        try:
            SubscriptionPlan.objects.get(slug=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError(
                f"No active subscription plan found with slug '{value}'."
            )

        return value

    def get_plan(self):
        """Return the validated SubscriptionPlan instance."""
        return SubscriptionPlan.objects.get(
            slug=self.validated_data["plan_slug"],
            is_active=True,
        )


class InvoiceSerializer(serializers.Serializer):
    """Serializer for Stripe invoice data."""

    id = serializers.CharField(help_text="Stripe invoice ID")
    number = serializers.CharField(allow_null=True, help_text="Invoice number")
    amount_due = serializers.IntegerField(help_text="Amount due in cents")
    amount_paid = serializers.IntegerField(help_text="Amount paid in cents")
    currency = serializers.CharField(help_text="Currency code")
    status = serializers.CharField(help_text="Invoice status")
    period_start = serializers.DateTimeField(
        allow_null=True, help_text="Start of the billing period for this invoice."
    )
    period_end = serializers.DateTimeField(
        allow_null=True, help_text="End of the billing period for this invoice."
    )
    hosted_invoice_url = serializers.URLField(
        allow_null=True,
        allow_blank=True,
        help_text="URL to view the hosted invoice on Stripe.",
    )
    invoice_pdf = serializers.URLField(
        allow_null=True,
        allow_blank=True,
        help_text="URL to download the invoice as PDF.",
    )
    created = serializers.DateTimeField(
        help_text="Timestamp when the invoice was created."
    )
