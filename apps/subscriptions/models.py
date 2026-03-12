"""
Models for the Subscriptions app.

Defines the data structures for Stripe integration including customer mapping,
subscription tracking, and plan definitions with feature gating.
"""

import uuid

from django.conf import settings
from django.db import models


class StripeCustomer(models.Model):
    """
    Maps a Stepora user to a Stripe customer.

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
        related_name="stripe_customer",
    )
    stripe_customer_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stripe customer ID (cus_xxxxx)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "stripe_customers"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["stripe_customer_id"]),
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
        help_text="Plan display name (Free, Premium, Pro)",
    )
    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text="URL-safe plan identifier (free, premium, pro)",
    )
    stripe_price_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Stripe Price ID (price_xxxxx). Empty for free tier.",
    )
    price_monthly = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        help_text="Monthly price in USD",
    )
    features = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON object describing plan features for display",
    )

    # Resource limits
    dream_limit = models.IntegerField(
        default=3,
        help_text="Maximum active dreams allowed. -1 for unlimited.",
    )

    # Feature flags
    has_ai = models.BooleanField(
        default=False,
        help_text="Access to AI coaching features",
    )
    has_buddy = models.BooleanField(
        default=False,
        help_text="Access to Dream Buddy matching",
    )
    has_circles = models.BooleanField(
        default=False,
        help_text="Access to Dream Circles (group accountability)",
    )
    has_vision_board = models.BooleanField(
        default=False,
        help_text="Access to AI Vision Board generation",
    )
    has_league = models.BooleanField(
        default=False,
        help_text="Access to competitive leagues",
    )
    has_store = models.BooleanField(
        default=False,
        help_text="Access to store purchases",
    )
    has_social_feed = models.BooleanField(
        default=False,
        help_text="Access to the social activity feed",
    )
    has_circle_create = models.BooleanField(
        default=False,
        help_text="Can create new circles (separate from joining)",
    )
    has_public_dreams = models.BooleanField(
        default=False,
        help_text="Can make dreams publicly visible to other users",
    )
    has_ads = models.BooleanField(
        default=True,
        help_text="Whether ads are shown to users on this plan",
    )

    # AI Usage Quotas (daily limits, 0 = no access)
    ai_chat_daily_limit = models.IntegerField(
        default=0,
        help_text="Daily AI chat messages limit. 0=no access.",
    )
    ai_plan_daily_limit = models.IntegerField(
        default=0,
        help_text="Daily AI plan/analysis operations limit.",
    )
    ai_image_daily_limit = models.IntegerField(
        default=0,
        help_text="Daily AI image generation limit (DALL-E).",
    )
    ai_voice_daily_limit = models.IntegerField(
        default=0,
        help_text="Daily voice transcription limit.",
    )
    ai_background_daily_limit = models.IntegerField(
        default=3,
        help_text="Daily background AI tasks limit (motivation, reports).",
    )
    ai_calibration_daily_limit = models.IntegerField(
        default=0,
        help_text="Daily calibration questions limit. 0=no access.",
    )

    trial_period_days = models.IntegerField(
        default=0,
        help_text="Number of free trial days for new subscribers (0 = no trial)",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this plan is currently available for purchase",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscription_plans"
        ordering = ["price_monthly"]

    def __str__(self):
        return f"{self.name} (${self.price_monthly}/mo)"

    TIER_ORDER = {"free": 0, "premium": 1, "pro": 2}

    @property
    def tier_order(self):
        """Return numeric tier order for upgrade/downgrade comparison."""
        return self.TIER_ORDER.get(self.slug, 0)

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
                "slug": "free",
                "defaults": {
                    "name": "Free",
                    "stripe_price_id": "",
                    "price_monthly": 0,
                    "dream_limit": 3,
                    "has_ai": False,
                    "has_buddy": False,
                    "has_circles": False,
                    "has_circle_create": False,
                    "has_vision_board": False,
                    "has_league": False,
                    "has_store": False,
                    "has_social_feed": False,
                    "has_public_dreams": False,
                    "has_ads": True,
                    "ai_chat_daily_limit": 0,
                    "ai_plan_daily_limit": 0,
                    "ai_calibration_daily_limit": 0,
                    "ai_image_daily_limit": 0,
                    "ai_voice_daily_limit": 0,
                    "ai_background_daily_limit": 0,
                    "features": {
                        "dreams": "3 active dreams",
                        "ai_coaching": False,
                        "buddy_matching": False,
                        "circles": False,
                        "vision_board": False,
                        "league": False,
                        "ads": True,
                    },
                },
            },
            {
                "slug": "premium",
                "defaults": {
                    "name": "Premium",
                    "stripe_price_id": "",
                    "price_monthly": 19.99,
                    "dream_limit": 10,
                    "has_ai": True,
                    "has_buddy": True,
                    "has_circles": True,
                    "has_circle_create": False,
                    "has_vision_board": False,
                    "has_league": True,
                    "has_store": True,
                    "has_social_feed": True,
                    "has_public_dreams": True,
                    "has_ads": False,
                    "ai_chat_daily_limit": 50,
                    "ai_plan_daily_limit": 10,
                    "ai_calibration_daily_limit": 50,
                    "ai_image_daily_limit": 0,
                    "ai_voice_daily_limit": 10,
                    "ai_background_daily_limit": 3,
                    "features": {
                        "dreams": "10 active dreams",
                        "ai_coaching": True,
                        "buddy_matching": True,
                        "circles": "Join only",
                        "vision_board": False,
                        "league": True,
                        "ads": False,
                    },
                },
            },
            {
                "slug": "pro",
                "defaults": {
                    "name": "Pro",
                    "stripe_price_id": "",
                    "price_monthly": 29.99,
                    "dream_limit": -1,
                    "has_ai": True,
                    "has_buddy": True,
                    "has_circles": True,
                    "has_circle_create": True,
                    "has_vision_board": True,
                    "has_league": True,
                    "has_store": True,
                    "has_social_feed": True,
                    "has_public_dreams": True,
                    "has_ads": False,
                    "ai_chat_daily_limit": 150,
                    "ai_plan_daily_limit": 25,
                    "ai_calibration_daily_limit": 50,
                    "ai_image_daily_limit": 3,
                    "ai_voice_daily_limit": 20,
                    "ai_background_daily_limit": 3,
                    "features": {
                        "dreams": "Unlimited active dreams",
                        "ai_coaching": True,
                        "buddy_matching": True,
                        "circles": True,
                        "vision_board": True,
                        "league": True,
                        "ads": False,
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
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("canceled", "Canceled"),
        ("incomplete", "Incomplete"),
        ("incomplete_expired", "Incomplete Expired"),
        ("trialing", "Trialing"),
        ("unpaid", "Unpaid"),
        ("paused", "Paused"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="active_subscription",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    stripe_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="Stripe Subscription ID (sub_xxxxx). Empty for free-tier subscriptions.",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="incomplete",
        db_index=True,
    )
    current_period_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start of the current billing period",
    )
    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End of the current billing period",
    )
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text="If True, subscription cancels at end of current period",
    )
    canceled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the user requested cancellation",
    )
    pending_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pending_subscriptions",
        help_text="Plan the user is downgrading to (takes effect at period end)",
    )
    pending_plan_effective_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the pending plan change takes effect",
    )
    stripe_schedule_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Stripe SubscriptionSchedule ID for pending downgrades",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscriptions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["stripe_subscription_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.plan.name} " f"({self.status})"

    @property
    def is_active(self):
        """Check if the subscription is currently active or trialing."""
        return self.status in ("active", "trialing")


class Referral(models.Model):
    """
    Tracks user referrals for the "Refer 3 paid friends → 1 free month" program.

    When a referred user subscribes to a paid plan, the referrer's
    paid_referral_count increments. At every 3 paid referrals, the referrer
    gets 1 month free Premium.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referrals_made",
        help_text="User who shared the referral link",
    )
    referred = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referred_by",
        help_text="User who signed up via the referral",
    )
    referral_code = models.CharField(
        max_length=50,
        db_index=True,
        help_text="The code used for this referral",
    )
    referred_has_paid = models.BooleanField(
        default=False,
        help_text="Whether the referred user has subscribed to a paid plan",
    )
    reward_granted = models.BooleanField(
        default=False,
        help_text="Whether a free month was granted for this batch of 3",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the referred user first subscribed to a paid plan",
    )

    class Meta:
        db_table = "referrals"
        ordering = ["-created_at"]

    def __str__(self):
        status = "paid" if self.referred_has_paid else "pending"
        return f"{self.referrer.email} → {self.referred.email} ({status})"

    @classmethod
    def get_referral_code(cls, user):
        """Generate a deterministic referral code for a user."""
        short = str(user.id).replace("-", "")[:8].upper()
        return f"DP-REF-{short}"

    @classmethod
    def resolve_referrer(cls, code):
        """
        Resolve a referral code to its owner via indexed UUID range query.

        Code format: DP-REF-<first 8 hex chars of user UUID>.
        We reverse the code into a UUID range and query with __gte/__lte
        which hits the primary key index → O(1).
        """
        import uuid as _uuid

        if not code or not code.startswith("DP-REF-") or len(code) != 15:
            return None
        hex_prefix = code[7:].lower()
        # Validate hex
        try:
            int(hex_prefix, 16)
        except ValueError:
            return None
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            min_id = _uuid.UUID(hex_prefix + "0" * 24)
            max_id = _uuid.UUID(hex_prefix + "f" * 24)
        except ValueError:
            return None
        return (
            User.objects.filter(
                is_active=True,
                id__gte=min_id,
                id__lte=max_id,
            )
            .only("id", "email", "display_name")
            .first()
        )

    @classmethod
    def get_referrer_stats(cls, user):
        """Get referral stats for a user."""
        total = cls.objects.filter(referrer=user).count()
        paid = cls.objects.filter(referrer=user, referred_has_paid=True).count()
        free_months_earned = paid // 3
        progress_to_next = paid % 3
        return {
            "total_referrals": total,
            "paid_referrals": paid,
            "free_months_earned": free_months_earned,
            "referrals_until_next_reward": (
                3 - progress_to_next if progress_to_next > 0 else 3
            ),
            "progress_to_next": progress_to_next,
        }


class StripeWebhookEvent(models.Model):
    """Tracks processed Stripe webhook events for idempotency."""

    stripe_event_id = models.CharField(max_length=255, unique=True, db_index=True)
    event_type = models.CharField(max_length=100)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stripe_webhook_events"
        indexes = [
            models.Index(fields=["stripe_event_id"]),
        ]

    def __str__(self):
        return f"{self.event_type} ({self.stripe_event_id})"


class Promotion(models.Model):
    """
    A promotional offer with configurable discount, eligibility, and duration.

    Promotions can target specific plans with different discount values,
    restrict eligibility by email domain or user type, and auto-create
    Stripe coupons for seamless billing integration.
    """

    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage"),
        ("fixed_amount", "Fixed Amount"),
    ]
    CONDITION_TYPE_CHOICES = [
        ("none", "None (everyone)"),
        ("email_endswith", "Email Ends With"),
    ]
    TARGET_AUDIENCE_CHOICES = [
        ("all", "All Users"),
        ("new_users", "New Users Only"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100,
        help_text="Internal name for this promotion",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Public-facing description shown to users",
    )
    start_date = models.DateTimeField(
        help_text="When the promotion becomes available",
    )
    end_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Deadline to redeem the promotion. After this date, users can no longer use it.",
    )
    duration_months = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="How many months the discount lasts after redemption (e.g. 2, 3, 4 months).",
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        help_text="Whether the discount is a percentage or fixed dollar amount",
    )
    max_redemptions = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum total redemptions. Leave blank for unlimited.",
    )
    condition_type = models.CharField(
        max_length=30,
        choices=CONDITION_TYPE_CHOICES,
        default="none",
        help_text="Eligibility condition type",
    )
    condition_value = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Condition value (e.g. '@school.ca' for email_endswith)",
    )
    target_audience = models.CharField(
        max_length=20,
        choices=TARGET_AUDIENCE_CHOICES,
        default="all",
        help_text="Who can see and redeem this promotion",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Admin toggle to enable/disable the promotion",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "promotions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.discount_type}, {self.duration_months or 0}mo)"

    @property
    def redemption_count(self):
        """Current number of redemptions."""
        return self.redemptions.count()

    @property
    def is_exhausted(self):
        """Whether max redemptions has been reached."""
        if self.max_redemptions is None:
            return False
        return self.redemption_count >= self.max_redemptions

    @property
    def spots_remaining(self):
        """Number of spots remaining, or None if unlimited."""
        if self.max_redemptions is None:
            return None
        return max(0, self.max_redemptions - self.redemption_count)


class PromotionPlanDiscount(models.Model):
    """
    Links a promotion to a specific plan with its own discount value.

    Each promotion can offer different discounts per plan (e.g. Premium -50%,
    Pro -30%). A Stripe coupon is auto-created via signal on save.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion = models.ForeignKey(
        Promotion,
        on_delete=models.CASCADE,
        related_name="plan_discounts",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.CASCADE,
        related_name="promotion_discounts",
    )
    discount_value = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Percentage (0-100) or fixed dollar amount, per promotion.discount_type",
    )
    stripe_coupon_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Auto-created Stripe coupon ID (do not edit manually)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "promotion_plan_discounts"
        unique_together = [("promotion", "plan")]

    def __str__(self):
        return (
            f"{self.promotion.name} → {self.plan.name}: "
            f"{self.discount_value}"
            f"{'%' if self.promotion.discount_type == 'percentage' else '$'}"
        )

    @property
    def discounted_price(self):
        """Calculate the discounted price for this plan."""
        price = float(self.plan.price_monthly)
        value = float(self.discount_value)
        if self.promotion.discount_type == "percentage":
            return round(price * (1 - value / 100), 2)
        return round(max(0.0, price - value), 2)


class PromotionRedemption(models.Model):
    """Tracks which users have redeemed a promotion."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion = models.ForeignKey(
        Promotion,
        on_delete=models.CASCADE,
        related_name="redemptions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="promotion_redemptions",
    )
    promotion_plan_discount = models.ForeignKey(
        PromotionPlanDiscount,
        on_delete=models.PROTECT,
        related_name="redemptions",
    )
    stripe_coupon_id = models.CharField(
        max_length=255,
        help_text="The Stripe coupon ID used for this redemption",
    )
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "promotion_redemptions"
        unique_together = [("promotion", "user")]
        indexes = [
            models.Index(fields=["promotion", "user"]),
        ]

    def __str__(self):
        return f"{self.user.email} redeemed {self.promotion.name}"
