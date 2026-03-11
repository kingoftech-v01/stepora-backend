"""
Django admin configuration for the Subscriptions app.

Registers StripeCustomer, SubscriptionPlan, and Subscription models
with rich list displays, filters, and search capabilities.
"""

from django.contrib import admin

from .models import (
    Promotion,
    PromotionPlanDiscount,
    PromotionRedemption,
    Referral,
    StripeCustomer,
    StripeWebhookEvent,
    Subscription,
    SubscriptionPlan,
)


@admin.register(StripeCustomer)
class StripeCustomerAdmin(admin.ModelAdmin):
    """Admin interface for Stripe customer mappings."""

    list_display = [
        "user",
        "stripe_customer_id",
        "created_at",
    ]
    list_filter = ["created_at"]
    search_fields = [
        "user__email",
        "user__display_name",
        "stripe_customer_id",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["user"]


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """Admin interface for subscription plan definitions."""

    list_display = [
        "name",
        "slug",
        "price_monthly",
        "dream_limit",
        "has_ai",
        "has_buddy",
        "has_circles",
        "has_circle_create",
        "has_store",
        "has_social_feed",
        "has_vision_board",
        "has_league",
        "has_public_dreams",
        "has_ads",
        "is_active",
    ]
    list_filter = [
        "is_active",
        "has_ai",
        "has_buddy",
        "has_circles",
        "has_circle_create",
        "has_store",
        "has_social_feed",
        "has_vision_board",
        "has_league",
        "has_public_dreams",
        "has_ads",
    ]
    search_fields = ["name", "slug", "stripe_price_id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    prepopulated_fields = {"slug": ("name",)}

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "slug",
                    "stripe_price_id",
                    "price_monthly",
                    "is_active",
                ),
            },
        ),
        (
            "Resource Limits",
            {
                "fields": ("dream_limit",),
            },
        ),
        (
            "Feature Flags",
            {
                "fields": (
                    "has_ai",
                    "has_buddy",
                    "has_circles",
                    "has_circle_create",
                    "has_store",
                    "has_social_feed",
                    "has_vision_board",
                    "has_league",
                    "has_public_dreams",
                    "has_ads",
                ),
            },
        ),
        (
            "AI Daily Limits",
            {
                "fields": (
                    "ai_chat_daily_limit",
                    "ai_plan_daily_limit",
                    "ai_calibration_daily_limit",
                    "ai_image_daily_limit",
                    "ai_voice_daily_limit",
                    "ai_background_daily_limit",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Display",
            {
                "fields": ("features",),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Admin interface for active subscriptions."""

    list_display = [
        "user",
        "plan",
        "status",
        "current_period_start",
        "current_period_end",
        "cancel_at_period_end",
        "created_at",
    ]
    list_filter = [
        "status",
        "cancel_at_period_end",
        "plan",
        "created_at",
    ]
    search_fields = [
        "user__email",
        "user__display_name",
        "stripe_subscription_id",
    ]
    readonly_fields = [
        "id",
        "stripe_subscription_id",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["user", "plan"]

    fieldsets = (
        (
            None,
            {
                "fields": ("user", "plan", "stripe_subscription_id", "status"),
            },
        ),
        (
            "Billing Period",
            {
                "fields": (
                    "current_period_start",
                    "current_period_end",
                    "cancel_at_period_end",
                    "canceled_at",
                ),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    """Admin interface for Referral model."""

    list_display = [
        "referrer",
        "referred",
        "referral_code",
        "referred_has_paid",
        "reward_granted",
        "created_at",
        "paid_at",
    ]
    list_filter = ["referred_has_paid", "reward_granted", "created_at"]
    search_fields = ["referrer__email", "referred__email", "referral_code"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["referrer", "referred"]


@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):
    """Admin interface for StripeWebhookEvent model."""

    list_display = ["stripe_event_id", "event_type", "processed_at"]
    list_filter = ["event_type", "processed_at"]
    search_fields = ["stripe_event_id", "event_type"]
    readonly_fields = ["processed_at"]


class PromotionPlanDiscountInline(admin.TabularInline):
    """Inline editor for plan-specific discounts within a promotion."""

    model = PromotionPlanDiscount
    extra = 1
    readonly_fields = ["stripe_coupon_id", "created_at"]
    fields = ["plan", "discount_value", "stripe_coupon_id"]


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    """Admin interface for managing promotions."""

    list_display = [
        "name",
        "discount_type",
        "start_date",
        "end_date",
        "duration_days",
        "max_redemptions",
        "redemption_count",
        "condition_type",
        "target_audience",
        "is_active",
    ]
    list_filter = [
        "is_active",
        "discount_type",
        "condition_type",
        "target_audience",
    ]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [PromotionPlanDiscountInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "description",
                    "is_active",
                ),
            },
        ),
        (
            "Discount",
            {
                "fields": (
                    "discount_type",
                    "duration_days",
                ),
            },
        ),
        (
            "Schedule",
            {
                "fields": (
                    "start_date",
                    "end_date",
                ),
            },
        ),
        (
            "Eligibility",
            {
                "fields": (
                    "max_redemptions",
                    "condition_type",
                    "condition_value",
                    "target_audience",
                ),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Redemptions")
    def redemption_count(self, obj):
        return obj.redemptions.count()


@admin.register(PromotionRedemption)
class PromotionRedemptionAdmin(admin.ModelAdmin):
    """Admin interface for viewing promotion redemptions (read-only)."""

    list_display = [
        "user",
        "promotion",
        "promotion_plan_discount",
        "stripe_coupon_id",
        "redeemed_at",
    ]
    list_filter = ["redeemed_at", "promotion"]
    search_fields = ["user__email", "promotion__name"]
    readonly_fields = [
        "id",
        "promotion",
        "user",
        "promotion_plan_discount",
        "stripe_coupon_id",
        "redeemed_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
