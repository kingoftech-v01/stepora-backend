"""
Unit tests for the Users app models.
"""

import pytest
from django.utils import timezone

from apps.users.models import DailyActivity, User


# ──────────────────────────────────────────────────────────────────────
#  User Model
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserModel:
    """Tests for the User model."""

    def test_create_user_with_email(self):
        """User can be created with email as the username field."""
        user = User.objects.create_user(
            email="newuser@example.com",
            password="securepassword123",
        )
        assert user.pk is not None
        assert user.email == "newuser@example.com"
        assert user.check_password("securepassword123")
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_superuser is False

    def test_create_user_normalizes_email(self):
        """Email is normalized (domain lowercased) on creation."""
        user = User.objects.create_user(
            email="TestUser@EXAMPLE.COM",
            password="testpassword123",
        )
        assert user.email == "TestUser@example.com"

    def test_create_user_without_email_raises(self):
        """Creating a user without email raises ValueError."""
        with pytest.raises(ValueError, match="Email is required"):
            User.objects.create_user(email="", password="testpassword123")

    def test_create_superuser(self):
        """Superuser is created with is_staff and is_superuser flags."""
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpassword123",
        )
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_create_superuser_requires_is_staff(self):
        """create_superuser raises if is_staff is False."""
        with pytest.raises(ValueError, match="is_staff=True"):
            User.objects.create_superuser(
                email="admin2@example.com",
                password="adminpassword123",
                is_staff=False,
            )

    def test_create_superuser_requires_is_superuser(self):
        """create_superuser raises if is_superuser is False."""
        with pytest.raises(ValueError, match="is_superuser=True"):
            User.objects.create_superuser(
                email="admin3@example.com",
                password="adminpassword123",
                is_superuser=False,
            )

    def test_user_str(self):
        """User __str__ returns email and display name."""
        user = User.objects.create_user(
            email="strtest@example.com",
            password="testpassword123",
            display_name="String Test",
        )
        result = str(user)
        assert "strtest@example.com" in result
        assert "String Test" in result

    def test_user_str_no_display_name(self):
        """User __str__ shows 'No name' when display_name is empty."""
        user = User.objects.create_user(
            email="noname@example.com",
            password="testpassword123",
        )
        result = str(user)
        assert "No name" in result

    def test_username_field_is_email(self):
        """User model uses email as USERNAME_FIELD."""
        assert User.USERNAME_FIELD == "email"

    def test_user_default_values(self):
        """User model has correct default values."""
        user = User.objects.create_user(
            email="defaults@example.com",
            password="testpassword123",
        )
        assert user.subscription == "free"
        assert user.xp == 0
        assert user.level == 1
        assert user.streak_days == 0
        assert user.is_online is False
        assert user.theme_mode == "auto"
        assert user.accent_color == "#8B5CF6"
        assert user.profile_visibility == "public"
        assert user.onboarding_completed is False
        assert user.totp_enabled is False

    def test_user_subscription_choices(self):
        """User subscription field supports free, premium, and pro."""
        for sub in ("free", "premium", "pro"):
            user = User.objects.create_user(
                email=f"sub_{sub}@example.com",
                password="testpassword123",
                subscription=sub,
            )
            assert user.subscription == sub

    def test_user_uuid_primary_key(self):
        """User id is a UUID."""
        import uuid

        user = User.objects.create_user(
            email="uuidtest@example.com", password="testpassword123"
        )
        assert isinstance(user.id, uuid.UUID)


# ──────────────────────────────────────────────────────────────────────
#  User display_name
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserDisplayName:
    """Tests for User display_name field."""

    def test_display_name_set(self):
        """User display_name can be set on creation."""
        user = User.objects.create_user(
            email="displayname@example.com",
            password="testpassword123",
            display_name="John Doe",
        )
        assert user.display_name == "John Doe"

    def test_display_name_blank(self):
        """User display_name defaults to blank when not provided."""
        user = User.objects.create_user(
            email="nodntest@example.com",
            password="testpassword123",
        )
        assert user.display_name == ""

    def test_display_name_update(self):
        """User display_name can be updated after creation."""
        user = User.objects.create_user(
            email="updatedn@example.com",
            password="testpassword123",
            display_name="Original Name",
        )
        user.display_name = "Updated Name"
        user.save(update_fields=["display_name"])
        user.refresh_from_db()
        assert user.display_name == "Updated Name"


# ──────────────────────────────────────────────────────────────────────
#  DailyActivity Model
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDailyActivityModel:
    """Tests for the DailyActivity model."""

    def test_create_daily_activity(self, users_user):
        """DailyActivity can be created with required fields."""
        today = timezone.now().date()
        activity = DailyActivity.objects.create(
            user=users_user,
            date=today,
            tasks_completed=3,
            xp_earned=45,
            minutes_active=60,
        )
        assert activity.pk is not None
        assert activity.user == users_user
        assert activity.date == today
        assert activity.tasks_completed == 3
        assert activity.xp_earned == 45
        assert activity.minutes_active == 60

    def test_daily_activity_str(self, users_user):
        """DailyActivity __str__ returns readable representation."""
        today = timezone.now().date()
        activity = DailyActivity.objects.create(
            user=users_user, date=today, tasks_completed=5
        )
        result = str(activity)
        assert users_user.email in result
        assert "5 tasks" in result

    def test_daily_activity_defaults(self, users_user):
        """DailyActivity defaults to zero counts."""
        today = timezone.now().date()
        activity = DailyActivity.objects.create(
            user=users_user, date=today
        )
        assert activity.tasks_completed == 0
        assert activity.xp_earned == 0
        assert activity.minutes_active == 0

    def test_unique_user_date_constraint(self, users_user):
        """Only one DailyActivity per user per date."""
        from django.db import IntegrityError

        today = timezone.now().date()
        DailyActivity.objects.create(user=users_user, date=today)
        with pytest.raises(IntegrityError):
            DailyActivity.objects.create(user=users_user, date=today)

    def test_record_task_completion(self, users_user):
        """DailyActivity.record_task_completion() atomically increments counters."""
        activity = DailyActivity.record_task_completion(
            user=users_user, xp_earned=10, duration_mins=15
        )
        assert activity.tasks_completed == 1
        assert activity.xp_earned == 10
        assert activity.minutes_active == 15

    def test_record_task_completion_multiple(self, users_user):
        """Multiple record_task_completion calls increment counters cumulatively."""
        DailyActivity.record_task_completion(
            user=users_user, xp_earned=10, duration_mins=15
        )
        activity = DailyActivity.record_task_completion(
            user=users_user, xp_earned=20, duration_mins=30
        )
        assert activity.tasks_completed == 2
        assert activity.xp_earned == 30
        assert activity.minutes_active == 45


# ──────────────────────────────────────────────────────────────────────
#  User streak_days
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserStreakDays:
    """Tests for User streak_days field."""

    def test_streak_days_default(self):
        """User streak_days defaults to 0."""
        user = User.objects.create_user(
            email="streak_default@example.com",
            password="testpassword123",
        )
        assert user.streak_days == 0

    def test_streak_days_increment(self, users_user):
        """User streak_days can be incremented."""
        users_user.streak_days = 7
        users_user.save(update_fields=["streak_days"])
        users_user.refresh_from_db()
        assert users_user.streak_days == 7

    def test_streak_days_reset(self, users_user):
        """User streak_days can be reset to 0."""
        users_user.streak_days = 10
        users_user.save(update_fields=["streak_days"])
        users_user.streak_days = 0
        users_user.save(update_fields=["streak_days"])
        users_user.refresh_from_db()
        assert users_user.streak_days == 0

    def test_add_xp_and_level_up(self):
        """User.add_xp() increments XP and levels up at 100 XP thresholds."""
        user = User.objects.create_user(
            email="levelup@example.com",
            password="testpassword123",
        )
        assert user.level == 1
        assert user.xp == 0
        # Add 150 XP: should level up to level 2 (150 // 100 + 1 = 2)
        leveled_up = user.add_xp(150)
        assert leveled_up is True
        user.refresh_from_db()
        assert user.xp == 150
        assert user.level == 2

    def test_add_xp_no_level_up(self):
        """User.add_xp() with small amount does not level up."""
        user = User.objects.create_user(
            email="nolevelup@example.com",
            password="testpassword123",
        )
        leveled_up = user.add_xp(50)
        assert leveled_up is False
        user.refresh_from_db()
        assert user.xp == 50
        assert user.level == 1

    def test_update_activity(self, users_user):
        """User.update_activity() updates last_activity timestamp."""
        old_activity = users_user.last_activity
        users_user.update_activity()
        users_user.refresh_from_db()
        assert users_user.last_activity >= old_activity
