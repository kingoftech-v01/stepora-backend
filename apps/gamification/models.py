"""
Models for the Gamification system.

Implements the Life RPG system with per-category XP, achievements,
daily activity tracking for heatmaps, and streak management.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone as django_timezone


class GamificationProfile(models.Model):
    """Gamification profile for Life RPG system."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gamification"
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
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_activities",
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
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_achievements",
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


class HabitChain(models.Model):
    """Tracks individual habit events contributing to a user's streak.

    Each row represents a single qualifying action on a specific date:
    - ``check_in``: user completed a dream plan check-in
    - ``task_completion``: user completed a task
    - ``focus_timer``: user finished a focus/pomodoro session
    """

    CHAIN_TYPE_CHOICES = [
        ("check_in", "Check-in"),
        ("task_completion", "Task Completion"),
        ("focus_timer", "Focus Timer"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="habit_chains"
    )
    dream = models.ForeignKey(
        "dreams.Dream",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="habit_chains",
    )
    date = models.DateField()
    chain_type = models.CharField(
        max_length=20, choices=CHAIN_TYPE_CHOICES, db_index=True
    )
    completed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "habit_chains"
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "-date"]),
            models.Index(fields=["user", "chain_type", "-date"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.chain_type} on {self.date}"
