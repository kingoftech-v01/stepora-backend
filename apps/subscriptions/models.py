"""
Models for the Subscriptions app.

Defines the data structures for Stripe integration including customer mapping,
subscription tracking, and plan definitions with feature gating.
"""

import uuid
from django.db import models
from django.conf import settings


class StripeCustomer(models.Model):
    """
    Maps a DreamPlanner user to a Stripe customer.

    Created automatically via a post_save signal when a new User is registered.
    Stores the Stripe customer ID so we can look up payment info without
    querying Stripe on every request.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='stripe_customer',
    )
    stripe_customer_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text='Stripe customer ID (cus_xxxxx)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'stripe_customers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stripe_customer_id']),
        ]

    def __str__(self):
        return f"{self.user.email} -> {self.stripe_customer_id}"


class SubscriptionPlan(models.Model):
    """
    Defines the available subscription plans and their feature sets.

    Each plan corresponds to a Stripe Price and determines which features
    the user can access as well as resource limits (dream count, AI access, etc.).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text='Plan display name (Free, Premium, Pro)',
    )
    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text='URL-safe plan identifier (free, premium, pro)',
    )
    stripe_price_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Stripe Price ID (price_xxxxx). Empty for free tier.',
    )
    price_monthly = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        help_text='Monthly price in USD',
    )
    features = models.JSONField(
        default=dict,
        blank=True,
        help_text='JSON object describing plan features for display',
    )

    # Resource limits
    dream_limit = models.IntegerField(
        default=3,
        help_text='Maximum active dreams allowed. -1 for unlimited.',
    )

    # Feature flags
    has_ai = models.BooleanField(
        default=False,
        help_text='Access to AI coaching features',
    )
    has_buddy = models.BooleanField(
        default=False,
        help_text='Access to Dream Buddy matching',
    )
    has_circles = models.BooleanField(
        default=False,
        help_text='Access to Dream Circles (group accountability)',
    )
    has_vision_board = models.BooleanField(
        default=False,
        help_text='Access to AI Vision Board generation',
    )
    has_league = models.BooleanField(
        default=False,
        help_text='Access to competitive leagues',
    )
    has_ads = models.BooleanField(
        default=True,
        help_text='Whether ads are shown to users on this plan',
    )

    # AI Usage Quotas (daily limits, 0 = no access)
    ai_chat_daily_limit = models.IntegerField(
        default=0,
        help_text='Daily AI chat messages limit. 0=no access.',
    )
    ai_plan_daily_limit = models.IntegerField(
        default=0,
        help_text='Daily AI plan/analysis operations limit.',
    )
    ai_image_daily_limit = models.IntegerField(
        default=0,
        help_text='Daily AI image generation limit (DALL-E).',
    )
    ai_voice_daily_limit = models.IntegerField(
        default=0,
        help_text='Daily voice transcription limit.',
    )
    ai_background_daily_limit = models.IntegerField(
        default=3,
        help_text='Daily background AI tasks limit (motivation, reports).',
    )

    trial_period_days = models.IntegerField(
        default=0,
        help_text='Number of free trial days for new subscribers (0 = no trial)',
    )

    is_active = models.BooleanField(
        default=True,
        help_text='Whether this plan is currently available for purchase',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscription_plans'
        ordering = ['price_monthly']

    def __str__(self):
        return f"{self.name} (${self.price_monthly}/mo)"

    @property
    def is_free(self):
        """Check if this is the free tier."""
        return self.price_monthly == 0

    @property
    def has_unlimited_dreams(self):
        """Check if this plan has unlimited dream slots."""
        return self.dream_limit == -1

    @classmethod
    def seed_plans(cls):
        """
        Create or update the default subscription plans.

        This method is idempotent and safe to call multiple times.
        It uses update_or_create so existing plans are updated rather
        than duplicated.
        """
        plans = [
            {
                'slug': 'free',
                'defaults': {
                    'name': 'Free',
                    'stripe_price_id': '',
                    'price_monthly': 0,
                    'dream_limit': 3,
                    'has_ai': False,
                    'has_buddy': False,
                    'has_circles': False,
                    'has_vision_board': False,
                    'has_league': False,
                    'has_ads': True,
                    'ai_chat_daily_limit': 0,
                    'ai_plan_daily_limit': 0,
                    'ai_image_daily_limit': 0,
                    'ai_voice_daily_limit': 0,
                    'ai_background_daily_limit': 0,
                    'features': {
                        'dreams': '3 active dreams',
                        'ai_coaching': False,
                        'buddy_matching': False,
                        'circles': False,
                        'vision_board': False,
                        'league': False,
                        'ads': True,
                    },
                },
            },
            {
                'slug': 'premium',
                'defaults': {
                    'name': 'Premium',
                    'stripe_price_id': '',
                    'price_monthly': 14.99,
                    'dream_limit': 10,
                    'has_ai': True,
                    'has_buddy': True,
                    'has_circles': False,
                    'has_vision_board': False,
                    'has_league': True,
                    'has_ads': False,
                    'ai_chat_daily_limit': 50,
                    'ai_plan_daily_limit': 10,
                    'ai_image_daily_limit': 0,
                    'ai_voice_daily_limit': 10,
                    'ai_background_daily_limit': 3,
                    'features': {
                        'dreams': '10 active dreams',
                        'ai_coaching': True,
                        'buddy_matching': True,
                        'circles': False,
                        'vision_board': False,
                        'league': True,
                        'ads': False,
                    },
                },
            },
            {
                'slug': 'pro',
                'defaults': {
                    'name': 'Pro',
                    'stripe_price_id': '',
                    'price_monthly': 29.99,
                    'dream_limit': -1,
                    'has_ai': True,
                    'has_buddy': True,
                    'has_circles': True,
                    'has_vision_board': True,
                    'has_league': True,
                    'has_ads': False,
                    'ai_chat_daily_limit': 150,
                    'ai_plan_daily_limit': 25,
                    'ai_image_daily_limit': 3,
                    'ai_voice_daily_limit': 20,
                    'ai_background_daily_limit': 3,
                    'features': {
                        'dreams': 'Unlimited active dreams',
                        'ai_coaching': True,
                        'buddy_matching': True,
                        'circles': True,
                        'vision_board': True,
                        'league': True,
                        'ads': False,
                    },
                },
            },
        ]

        created_plans = []
        for plan_data in plans:
            plan, created = cls.objects.update_or_create(**plan_data)
            created_plans.append(plan)

        return created_plans


class Subscription(models.Model):
    """
    Tracks an active subscription linking a user to a plan via Stripe.

    This is the source of truth for the user's current billing status.
    Stripe webhooks keep this model in sync with the actual Stripe
    subscription state.
    """

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('incomplete', 'Incomplete'),
        ('incomplete_expired', 'Incomplete Expired'),
        ('trialing', 'Trialing'),
        ('unpaid', 'Unpaid'),
        ('paused', 'Paused'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='active_subscription',
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
    )
    stripe_subscription_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text='Stripe Subscription ID (sub_xxxxx)',
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='incomplete',
        db_index=True,
    )
    current_period_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Start of the current billing period',
    )
    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text='End of the current billing period',
    )
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text='If True, subscription cancels at end of current period',
    )
    canceled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the user requested cancellation',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscriptions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stripe_subscription_id']),
            models.Index(fields=['status']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return (
            f"{self.user.email} - {self.plan.name} "
            f"({self.status})"
        )

    @property
    def is_active(self):
        """Check if the subscription is currently active or trialing."""
        return self.status in ('active', 'trialing')
