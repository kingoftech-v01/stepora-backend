"""
Django admin configuration for the Subscriptions app.

Registers StripeCustomer, SubscriptionPlan, and Subscription models
with rich list displays, filters, and search capabilities.
"""

from django.contrib import admin

from .models import StripeCustomer, Subscription, SubscriptionPlan


@admin.register(StripeCustomer)
class StripeCustomerAdmin(admin.ModelAdmin):
    """Admin interface for Stripe customer mappings."""

    list_display = [
        'user',
        'stripe_customer_id',
        'created_at',
    ]
    list_filter = ['created_at']
    search_fields = [
        'user__email',
        'user__display_name',
        'stripe_customer_id',
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['user']


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """Admin interface for subscription plan definitions."""

    list_display = [
        'name',
        'slug',
        'price_monthly',
        'dream_limit',
        'has_ai',
        'has_buddy',
        'has_circles',
        'has_circle_create',
        'has_store',
        'has_social_feed',
        'has_vision_board',
        'has_league',
        'has_public_dreams',
        'has_ads',
        'is_active',
    ]
    list_filter = [
        'is_active',
        'has_ai',
        'has_buddy',
        'has_circles',
        'has_circle_create',
        'has_store',
        'has_social_feed',
        'has_vision_board',
        'has_league',
        'has_public_dreams',
        'has_ads',
    ]
    search_fields = ['name', 'slug', 'stripe_price_id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    prepopulated_fields = {'slug': ('name',)}

    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'stripe_price_id', 'price_monthly', 'is_active'),
        }),
        ('Resource Limits', {
            'fields': ('dream_limit',),
        }),
        ('Feature Flags', {
            'fields': (
                'has_ai',
                'has_buddy',
                'has_circles',
                'has_circle_create',
                'has_store',
                'has_social_feed',
                'has_vision_board',
                'has_league',
                'has_public_dreams',
                'has_ads',
            ),
        }),
        ('AI Daily Limits', {
            'fields': (
                'ai_chat_daily_limit',
                'ai_plan_daily_limit',
                'ai_calibration_daily_limit',
                'ai_image_daily_limit',
                'ai_voice_daily_limit',
                'ai_background_daily_limit',
            ),
            'classes': ('collapse',),
        }),
        ('Display', {
            'fields': ('features',),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Admin interface for active subscriptions."""

    list_display = [
        'user',
        'plan',
        'status',
        'current_period_start',
        'current_period_end',
        'cancel_at_period_end',
        'created_at',
    ]
    list_filter = [
        'status',
        'cancel_at_period_end',
        'plan',
        'created_at',
    ]
    search_fields = [
        'user__email',
        'user__display_name',
        'stripe_subscription_id',
    ]
    readonly_fields = [
        'id',
        'stripe_subscription_id',
        'created_at',
        'updated_at',
    ]
    raw_id_fields = ['user', 'plan']

    fieldsets = (
        (None, {
            'fields': ('user', 'plan', 'stripe_subscription_id', 'status'),
        }),
        ('Billing Period', {
            'fields': (
                'current_period_start',
                'current_period_end',
                'cancel_at_period_end',
                'canceled_at',
            ),
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
