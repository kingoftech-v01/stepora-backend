"""
User models for DreamPlanner.
"""

import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone as django_timezone


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user."""
        if not email:
            raise ValueError('Email is required')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model using email for authentication."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    display_name = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    avatar_image = models.ImageField(
        upload_to='avatars/',
        blank=True,
        help_text='Uploaded avatar image file.'
    )
    bio = models.TextField(
        blank=True,
        default='',
        help_text='Short user biography.'
    )
    location = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text='User location (city, country).'
    )
    social_links = models.JSONField(
        null=True,
        blank=True,
        help_text='Social media links: {twitter: "", instagram: "", ...}'
    )
    VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('friends', 'Friends Only'),
        ('private', 'Private'),
    ]
    profile_visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default='public',
        help_text='Who can see this profile.'
    )
    timezone = models.CharField(max_length=50, default='Europe/Paris')

    # Subscription
    SUBSCRIPTION_CHOICES = [
        ('free', 'Free'),
        ('premium', 'Premium'),
        ('pro', 'Pro'),
    ]
    subscription = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_CHOICES,
        default='free',
        db_index=True
    )
    subscription_ends = models.DateTimeField(null=True, blank=True)

    # JSON preferences
    work_schedule = models.JSONField(
        null=True,
        blank=True,
        help_text='Work schedule: {workDays: [], startTime: "", endTime: ""}'
    )
    notification_prefs = models.JSONField(
        null=True,
        blank=True,
        help_text='Notification preferences'
    )
    app_prefs = models.JSONField(
        null=True,
        blank=True,
        help_text='App preferences: {theme: "", language: ""}'
    )

    # Gamification
    xp = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    streak_days = models.IntegerField(default=0)
    last_activity = models.DateTimeField(default=django_timezone.now)

    # Django admin
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['subscription']),
            models.Index(fields=['last_activity']),
        ]

    def __str__(self):
        return f"{self.email} ({self.display_name or 'No name'})"

    def is_premium(self):
        """Check if user has premium or pro subscription."""
        return self.subscription in ['premium', 'pro']

    def can_create_dream(self):
        """Check if user can create another dream based on subscription."""
        from apps.dreams.models import Dream
        active_dreams = Dream.objects.filter(user=self, status='active').count()

        limits = {
            'free': 3,
            'premium': 10,
            'pro': float('inf'),
        }
        return active_dreams < limits.get(self.subscription, 3)

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = django_timezone.now()
        self.save(update_fields=['last_activity'])

    def add_xp(self, amount):
        """Add XP and check for level up."""
        self.xp += amount

        # Level up calculation (100 XP per level)
        new_level = (self.xp // 100) + 1
        if new_level > self.level:
            self.level = new_level

        self.save(update_fields=['xp', 'level'])
        return new_level > self.level  # Return True if leveled up


class EmailChangeRequest(models.Model):
    """Stores pending email change requests."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_change_requests')
    new_email = models.EmailField()
    token = models.CharField(max_length=128, unique=True, db_index=True)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'email_change_requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} -> {self.new_email}"

    @property
    def is_expired(self):
        return django_timezone.now() > self.expires_at


class GamificationProfile(models.Model):
    """Gamification profile for Life RPG system."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='gamification')

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
        db_table = 'gamification_profiles'

    def __str__(self):
        return f"Gamification - {self.user.email}"

    def get_attribute_level(self, attribute):
        """Get level for a specific attribute."""
        xp = getattr(self, f'{attribute}_xp', 0)
        return (xp // 100) + 1

    def add_attribute_xp(self, attribute, amount):
        """Add XP to a specific attribute."""
        current_xp = getattr(self, f'{attribute}_xp', 0)
        setattr(self, f'{attribute}_xp', current_xp + amount)
        self.save()


