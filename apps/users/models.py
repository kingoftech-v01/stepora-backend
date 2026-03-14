"""
User models for Stepora.
"""

import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone as django_timezone
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user."""
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model using email for authentication."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    display_name = EncryptedCharField(max_length=255, blank=True)
    avatar_url = EncryptedCharField(max_length=500, blank=True)
    avatar_image = models.ImageField(
        upload_to="avatars/", blank=True, help_text="Uploaded avatar image file."
    )
    bio = EncryptedTextField(
        blank=True, default="", help_text="Short user biography (encrypted at rest)."
    )
    location = EncryptedCharField(
        max_length=200,
        blank=True,
        default="",
        help_text="User location (encrypted at rest).",
    )
    social_links = models.JSONField(
        null=True,
        blank=True,
        help_text='Social media links: {twitter: "", instagram: "", ...}',
    )
    VISIBILITY_CHOICES = [
        ("public", "Public"),
        ("friends", "Friends Only"),
        ("private", "Private"),
    ]
    profile_visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default="public",
        help_text="Who can see this profile.",
    )
    timezone = models.CharField(max_length=50, default="Europe/Paris")

    # Theme / Accent
    THEME_MODE_CHOICES = [
        ("auto", "Auto"),
        ("dark", "Dark"),
        ("light", "Light"),
    ]
    theme_mode = models.CharField(
        max_length=10,
        choices=THEME_MODE_CHOICES,
        default="auto",
        help_text="Preferred theme mode: auto, dark, or light.",
    )
    accent_color = models.CharField(
        max_length=20,
        default="#8B5CF6",
        help_text="User accent/brand color hex code (e.g. #8B5CF6).",
    )

    # Subscription
    SUBSCRIPTION_CHOICES = [
        ("free", "Free"),
        ("premium", "Premium"),
        ("pro", "Pro"),
    ]
    subscription = models.CharField(
        max_length=20, choices=SUBSCRIPTION_CHOICES, default="free", db_index=True
    )
    subscription_ends = models.DateTimeField(null=True, blank=True)

    # JSON preferences
    work_schedule = models.JSONField(
        null=True,
        blank=True,
        help_text='Work schedule: {workDays: [], startTime: "", endTime: ""}',
    )
    notification_prefs = models.JSONField(
        null=True, blank=True, help_text="Notification preferences"
    )
    app_prefs = models.JSONField(
        null=True, blank=True, help_text='App preferences: {theme: "", language: ""}'
    )
    persona = models.JSONField(
        null=True,
        blank=True,
        help_text="User persona for AI calibration: {available_hours_per_week, preferred_schedule, "
        "budget_range, fitness_level, learning_style, typical_day, occupation, "
        "astrological_sign, global_motivation, global_constraints}",
    )
    calendar_preferences = models.JSONField(
        null=True,
        blank=True,
        help_text="Calendar preferences: {buffer_minutes: 0-60, min_event_duration: 15-120}",
    )
    energy_profile = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Energy profile for smart scheduling: "
            '{"peak_hours": [{"start": 9, "end": 12}], '
            '"low_energy_hours": [{"start": 13, "end": 14}], '
            '"energy_pattern": "morning_person"|"night_owl"|"steady"}'
        ),
    )
    notification_timing = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "AI-optimized notification timing preferences: "
            '{"optimal_times": [{"notification_type": "reminder", "best_hour": 9, '
            '"best_day": "weekday", "reason": "..."}], '
            '"quiet_hours": {"start": 22, "end": 7}, '
            '"engagement_score": 0.85, '
            '"last_optimized": "2026-03-01T12:00:00Z"}'
        ),
    )

    # Gamification
    xp = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    streak_days = models.IntegerField(default=0)
    last_activity = models.DateTimeField(default=django_timezone.now)

    # Online status
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)

    # Two-Factor Authentication
    totp_enabled = models.BooleanField(default=False)
    totp_secret = EncryptedCharField(max_length=64, blank=True, default="")
    backup_codes = models.JSONField(
        null=True, blank=True, help_text="Hashed 2FA backup codes"
    )

    # Onboarding
    onboarding_completed = models.BooleanField(default=False)
    DREAMER_TYPES = [
        ("visionary", "Visionary"),
        ("achiever", "Achiever"),
        ("explorer", "Explorer"),
        ("collaborator", "Collaborator"),
        ("strategist", "Strategist"),
    ]
    dreamer_type = models.CharField(max_length=30, blank=True, choices=DREAMER_TYPES)

    # Django admin
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # Account deletion
    deactivated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the account was deactivated. Hard-delete scheduled 30 days after.",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["subscription"]),
            models.Index(fields=["last_activity"]),
        ]

    def __str__(self):
        return f"{self.email} ({self.display_name or 'No name'})"

    def get_effective_avatar_url(self):
        """Return the best available avatar URL.

        Preference order:
        1. ``avatar_url`` (text field — may come from social login or manual URL)
        2. ``avatar_image.url`` (uploaded file — stored on S3 in production)
        3. Empty string (no avatar)
        """
        if self.avatar_url:
            return self.avatar_url
        if self.avatar_image:
            try:
                return self.avatar_image.url
            except Exception:
                return ""
        return ""

    def get_active_plan(self):
        """
        Get the user's active SubscriptionPlan from the database.

        Returns the plan from the active/trialing Subscription, or None if
        no subscription exists. Result is cached on the instance so multiple
        permission checks in a single request only hit the DB once.
        """
        if hasattr(self, "_cached_plan"):
            return self._cached_plan
        import logging

        logger = logging.getLogger(__name__)
        try:
            from apps.subscriptions.models import Subscription

            sub = (
                Subscription.objects.select_related("plan")
                .filter(
                    user=self,
                    status__in=("active", "trialing"),
                )
                .first()
            )
            if sub:
                self._cached_plan = sub.plan
            else:
                logger.error(
                    "User %s has no active subscription — blocking all features. "
                    "This should never happen; check the registration signal.",
                    self.id,
                )
                self._cached_plan = None
        except Exception as exc:
            logger.error(
                "Database error fetching plan for user %s: %s",
                self.id,
                exc,
            )
            self._cached_plan = None
        return self._cached_plan

    def is_premium(self):
        """Check if user has premium or pro subscription (from DB)."""
        plan = self.get_active_plan()
        return plan is not None and plan.slug in ("premium", "pro")

    def can_create_dream(self):
        """Check if user can create another dream based on plan's dream_limit."""
        plan = self.get_active_plan()
        if not plan:
            return False
        if plan.dream_limit == -1:
            return True
        from apps.dreams.models import Dream

        active_dreams = Dream.objects.filter(user=self, status="active").count()
        return active_dreams < plan.dream_limit

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = django_timezone.now()
        self.save(update_fields=["last_activity"])

    def add_xp(self, amount):
        """Add XP and check for level up. Uses atomic F() to prevent race conditions."""
        from django.db.models import F

        old_level = self.level
        User.objects.filter(id=self.id).update(xp=F("xp") + amount)
        self.refresh_from_db(fields=["xp"])

        # Level up calculation (100 XP per level)
        new_level = (self.xp // 100) + 1
        if new_level > old_level:
            self.level = new_level
            self.save(update_fields=["level"])

        return new_level > old_level


class EmailChangeRequest(models.Model):
    """Stores pending email change requests."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="email_change_requests"
    )
    new_email = models.EmailField()
    token = models.CharField(max_length=128, unique=True, db_index=True)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_change_requests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} -> {self.new_email}"

    @property
    def is_expired(self):
        return django_timezone.now() > self.expires_at


class GamificationProfile(models.Model):
    """Gamification profile for Life RPG system."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="gamification"
    )

    # Attributes (Life RPG)
    health_xp = models.IntegerField(default=0)
    career_xp = models.IntegerField(default=0)
    relationships_xp = models.IntegerField(default=0)
    personal_growth_xp = models.IntegerField(default=0)
    finance_xp = models.IntegerField(default=0)
    hobbies_xp = models.IntegerField(default=0)

    # Achievements
    badges = models.JSONField(default=list, blank=True)
    achievements = models.JSONField(default=list, blank=True)

    # Streak insurance (jokers)
    streak_jokers = models.IntegerField(default=3)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gamification_profiles"

    def __str__(self):
        return f"Gamification - {self.user.email}"

    def get_attribute_level(self, attribute):
        """Get level for a specific attribute."""
        xp = getattr(self, f"{attribute}_xp", 0)
        return (xp // 100) + 1

    def add_attribute_xp(self, attribute, amount):
        """Add XP to a specific attribute."""
        field_name = f"{attribute}_xp"
        from django.db.models import F

        GamificationProfile.objects.filter(id=self.id).update(
            **{field_name: F(field_name) + amount}
        )
        self.refresh_from_db(fields=[field_name])


class DailyActivity(models.Model):
    """Tracks daily user activity for heatmap display."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="daily_activities"
    )
    date = models.DateField()
    tasks_completed = models.IntegerField(default=0)
    xp_earned = models.IntegerField(default=0)
    minutes_active = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "daily_activities"
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"], name="unique_daily_activity"
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-date"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.date} ({self.tasks_completed} tasks)"

    @classmethod
    def record_task_completion(cls, user, xp_earned=0, duration_mins=0):
        """Record a task completion for today using atomic DB-level increments."""
        from django.db.models import F

        today = django_timezone.now().date()
        activity, created = cls.objects.get_or_create(user=user, date=today)
        # Use F() expressions for atomic increment to avoid race conditions
        cls.objects.filter(user=user, date=today).update(
            tasks_completed=F("tasks_completed") + 1,
            xp_earned=F("xp_earned") + xp_earned,
            minutes_active=F("minutes_active") + duration_mins,
        )
        activity.refresh_from_db()
        return activity


class Achievement(models.Model):
    """Achievement definition for the gamification system."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField()
    icon = models.CharField(
        max_length=50, help_text="Lucide icon name (e.g. sparkles, flame, trophy)"
    )
    CATEGORY_CHOICES = [
        ("streaks", "Streaks"),
        ("dreams", "Dreams"),
        ("social", "Social"),
        ("tasks", "Tasks"),
        ("special", "Special"),
        ("profile", "Profile"),
    ]
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    RARITY_CHOICES = [
        ("common", "Common"),
        ("uncommon", "Uncommon"),
        ("rare", "Rare"),
        ("epic", "Epic"),
        ("legendary", "Legendary"),
    ]
    rarity = models.CharField(
        max_length=20,
        choices=RARITY_CHOICES,
        default="common",
        db_index=True,
        help_text="Rarity tier that determines badge glow color.",
    )
    xp_reward = models.IntegerField(default=0)
    CONDITION_CHOICES = [
        ("streak_days", "Streak Days"),
        ("dreams_created", "Dreams Created"),
        ("dreams_completed", "Dreams Completed"),
        ("tasks_completed", "Tasks Completed"),
        ("friends_count", "Friends Count"),
        ("circles_joined", "Circles Joined"),
        ("level_reached", "Level Reached"),
        ("xp_earned", "XP Earned"),
        ("early_task", "Early Task (before 8am)"),
        ("late_task", "Late Task (after 10pm)"),
        ("first_dream", "First Dream Created"),
        ("first_buddy", "First Buddy Matched"),
        ("vision_created", "Vision Board Created"),
        ("posts_created", "Posts Created"),
        ("likes_received", "Likes Received"),
        ("profile_completed", "Profile Completed"),
    ]
    condition_type = models.CharField(max_length=30, choices=CONDITION_CHOICES)
    condition_value = models.IntegerField(
        default=1, help_text="Threshold value to unlock"
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "achievements"
        ordering = ["category", "condition_value"]

    def __str__(self):
        return f"{self.icon} {self.name}"


class UserAchievement(models.Model):
    """Tracks which achievements a user has unlocked and their progress."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="user_achievements"
    )
    achievement = models.ForeignKey(
        Achievement, on_delete=models.CASCADE, related_name="user_achievements"
    )
    unlocked_at = models.DateTimeField(auto_now_add=True)
    progress = models.PositiveIntegerField(
        default=0,
        help_text="Current progress towards the achievement requirement value.",
    )

    class Meta:
        db_table = "user_achievements"
        ordering = ["-unlocked_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "achievement"], name="unique_user_achievement"
            ),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.achievement.name}"
