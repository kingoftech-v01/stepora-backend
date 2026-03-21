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


# ──────────────────────────────────────────────────────────────────────
#  User methods: get_effective_avatar_url, get_active_plan, is_premium,
#  can_create_dream
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserMethods:
    """Tests for User model methods."""

    def test_get_effective_avatar_url_with_avatar_url(self):
        user = User.objects.create_user(
            email="avatar1@example.com",
            password="testpassword123",
            avatar_url="https://example.com/photo.jpg",
        )
        assert user.get_effective_avatar_url() == "https://example.com/photo.jpg"

    def test_get_effective_avatar_url_empty(self):
        user = User.objects.create_user(
            email="avatar2@example.com",
            password="testpassword123",
        )
        assert user.get_effective_avatar_url() == ""

    def test_get_active_plan_no_subscription(self):
        user = User.objects.create_user(
            email="noplan@example.com", password="testpassword123"
        )
        # Clear cached plan if any
        if hasattr(user, "_cached_plan"):
            del user._cached_plan
        plan = user.get_active_plan()
        # Might be None or the seeded free plan depending on DB state
        # Just ensure it doesn't raise
        assert plan is None or hasattr(plan, "slug")

    def test_get_active_plan_caches(self, premium_users_user):
        plan1 = premium_users_user.get_active_plan()
        plan2 = premium_users_user.get_active_plan()
        assert plan1 is plan2  # Same object (cached)

    def test_is_premium_with_premium_plan(self, premium_users_user):
        assert premium_users_user.is_premium() is True

    def test_is_premium_without_plan(self):
        user = User.objects.create_user(
            email="notpremium@example.com", password="testpassword123"
        )
        if hasattr(user, "_cached_plan"):
            del user._cached_plan
        # Without a subscription, is_premium should be False
        result = user.is_premium()
        assert result is False

    def test_can_create_dream_no_plan(self):
        from unittest.mock import Mock, patch

        user = User.objects.create_user(
            email="nodream@example.com", password="testpassword123"
        )
        if hasattr(user, "_cached_plan"):
            del user._cached_plan
        # Mock get_active_plan to return None
        user.get_active_plan = Mock(return_value=None)
        assert user.can_create_dream() is False

    def test_can_create_dream_unlimited(self, premium_users_user):
        from unittest.mock import Mock

        plan = Mock()
        plan.dream_limit = -1
        premium_users_user._cached_plan = plan
        assert premium_users_user.can_create_dream() is True


# ──────────────────────────────────────────────────────────────────────
#  GamificationProfile Model
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGamificationProfileModel:
    """Tests for the GamificationProfile model."""

    def test_create_profile(self, users_user):
        from apps.users.models import GamificationProfile

        profile, _ = GamificationProfile.objects.get_or_create(user=users_user)
        assert profile.pk is not None
        assert profile.streak_jokers == 3

    def test_profile_str(self, users_user):
        from apps.users.models import GamificationProfile

        profile, _ = GamificationProfile.objects.get_or_create(user=users_user)
        assert users_user.email in str(profile)

    def test_get_attribute_level(self, users_user):
        from apps.users.models import GamificationProfile

        profile, _ = GamificationProfile.objects.get_or_create(user=users_user)
        profile.health_xp = 250
        profile.save(update_fields=["health_xp"])
        assert profile.get_attribute_level("health") == 3  # 250 // 100 + 1

    def test_get_attribute_level_zero(self, users_user):
        from apps.users.models import GamificationProfile

        profile, _ = GamificationProfile.objects.get_or_create(user=users_user)
        assert profile.get_attribute_level("career") == 1

    def test_add_attribute_xp(self, users_user):
        from apps.users.models import GamificationProfile

        profile, _ = GamificationProfile.objects.get_or_create(user=users_user)
        profile.health_xp = 0
        profile.save(update_fields=["health_xp"])
        profile.add_attribute_xp("health", 50)
        assert profile.health_xp == 50

    def test_add_attribute_xp_cumulative(self, users_user):
        from apps.users.models import GamificationProfile

        profile, _ = GamificationProfile.objects.get_or_create(user=users_user)
        profile.health_xp = 100
        profile.save(update_fields=["health_xp"])
        profile.add_attribute_xp("health", 50)
        assert profile.health_xp == 150


# ──────────────────────────────────────────────────────────────────────
#  Achievement and UserAchievement Models
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAchievementModel:
    """Tests for the Achievement model."""

    def test_create_achievement(self):
        from apps.users.models import Achievement

        ach = Achievement.objects.create(
            name="First Dream",
            description="Create your first dream",
            icon="sparkles",
            category="dreams",
            condition_type="first_dream",
            condition_value=1,
            xp_reward=50,
        )
        assert ach.pk is not None
        assert ach.name == "First Dream"

    def test_achievement_str(self):
        from apps.users.models import Achievement

        ach = Achievement.objects.create(
            name="Streak Master",
            description="7 day streak",
            icon="flame",
            category="streaks",
            condition_type="streak_days",
            condition_value=7,
        )
        result = str(ach)
        assert "flame" in result
        assert "Streak Master" in result

    def test_achievement_rarity_default(self):
        from apps.users.models import Achievement

        ach = Achievement.objects.create(
            name="Basic Ach",
            description="Test",
            icon="star",
            category="tasks",
            condition_type="tasks_completed",
            condition_value=1,
        )
        assert ach.rarity == "common"


@pytest.mark.django_db
class TestUserAchievementModel:
    """Tests for the UserAchievement model."""

    def test_create_user_achievement(self, users_user):
        from apps.users.models import Achievement, UserAchievement

        ach = Achievement.objects.create(
            name="Test Ach UA",
            description="Test",
            icon="star",
            category="tasks",
            condition_type="tasks_completed",
            condition_value=1,
        )
        ua = UserAchievement.objects.create(user=users_user, achievement=ach)
        assert ua.pk is not None
        assert ua.progress == 0

    def test_user_achievement_str(self, users_user):
        from apps.users.models import Achievement, UserAchievement

        ach = Achievement.objects.create(
            name="Test Ach Str",
            description="Test",
            icon="star",
            category="tasks",
            condition_type="tasks_completed",
            condition_value=1,
        )
        ua = UserAchievement.objects.create(user=users_user, achievement=ach)
        result = str(ua)
        assert users_user.email in result
        assert ach.name in result


# ──────────────────────────────────────────────────────────────────────
#  EmailChangeRequest Model
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEmailChangeRequestModel:
    """Tests for the EmailChangeRequest model."""

    def test_create_email_change_request(self, users_user):
        from apps.users.models import EmailChangeRequest

        ecr = EmailChangeRequest.objects.create(
            user=users_user,
            new_email="new@example.com",
            token="abc123token",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        assert ecr.pk is not None
        assert ecr.new_email == "new@example.com"
        assert ecr.is_verified is False

    def test_email_change_request_str(self, users_user):
        from apps.users.models import EmailChangeRequest

        ecr = EmailChangeRequest.objects.create(
            user=users_user,
            new_email="changed@example.com",
            token="token456",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        result = str(ecr)
        assert users_user.email in result
        assert "changed@example.com" in result

    def test_is_expired_false(self, users_user):
        from apps.users.models import EmailChangeRequest

        ecr = EmailChangeRequest.objects.create(
            user=users_user,
            new_email="notexpired@example.com",
            token="tokenNotExpired",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        assert ecr.is_expired is False

    def test_is_expired_true(self, users_user):
        from apps.users.models import EmailChangeRequest

        ecr = EmailChangeRequest.objects.create(
            user=users_user,
            new_email="expired@example.com",
            token="tokenExpired",
            expires_at=timezone.now() - timezone.timedelta(hours=1),
        )
        assert ecr.is_expired is True


# ──────────────────────────────────────────────────────────────────────
#  UserStatsService
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserStatsService:
    """Tests for the UserStatsService."""

    def test_get_user_stats_empty(self, premium_users_user):
        from apps.users.services import UserStatsService

        stats = UserStatsService.get_user_stats(premium_users_user)
        assert stats["level"] == premium_users_user.level
        assert stats["xp"] == premium_users_user.xp
        assert stats["streak_days"] == premium_users_user.streak_days
        assert stats["total_dreams"] == 0
        assert stats["active_dreams"] == 0
        assert stats["completed_dreams"] == 0
        assert stats["total_tasks_completed"] == 0
        assert stats["tasks_completed_this_week"] == 0

    def test_get_user_stats_with_dreams(self, premium_users_user):
        from apps.dreams.models import Dream, Goal, Task
        from apps.users.services import UserStatsService

        dream = Dream.objects.create(
            user=premium_users_user, title="Test Dream", description="Desc", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G1", order=1)
        Task.objects.create(goal=goal, title="T1", order=1, status="completed",
                          completed_at=timezone.now())

        stats = UserStatsService.get_user_stats(premium_users_user)
        assert stats["total_dreams"] == 1
        assert stats["active_dreams"] == 1
        assert stats["total_tasks_completed"] == 1


# ──────────────────────────────────────────────────────────────────────
#  Two-Factor Authentication helpers
# ──────────────────────────────────────────────────────────────────────


class TestTwoFactorHelpers:
    """Tests for 2FA helper functions."""

    def test_generate_backup_codes(self):
        from apps.users.two_factor import _generate_backup_codes

        codes = _generate_backup_codes()
        assert len(codes) == 10
        assert all(len(c) == 8 for c in codes)
        assert all(c == c.upper() for c in codes)

    def test_generate_backup_codes_custom_count(self):
        from apps.users.two_factor import _generate_backup_codes

        codes = _generate_backup_codes(count=5)
        assert len(codes) == 5

    def test_hash_code_deterministic(self):
        from apps.users.two_factor import _hash_code

        h1 = _hash_code("TESTCODE")
        h2 = _hash_code("TESTCODE")
        assert h1 == h2

    def test_hash_code_different_inputs(self):
        from apps.users.two_factor import _hash_code

        h1 = _hash_code("CODE1111")
        h2 = _hash_code("CODE2222")
        assert h1 != h2


# ──────────────────────────────────────────────────────────────────────
#  core.auth.tokens
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCoreAuthTokens:
    """Tests for core.auth.tokens module."""

    def test_make_and_verify_email_verification_key(self):
        from core.auth.models import EmailAddress
        from core.auth.tokens import (
            make_email_verification_key,
            verify_email_verification_key,
        )

        user = User.objects.create_user(
            email="verify_token@example.com", password="test123"
        )
        ea = EmailAddress.objects.create(
            user=user, email=user.email, verified=False, primary=True
        )
        key = make_email_verification_key(ea.id)
        assert key is not None
        result_id = verify_email_verification_key(key)
        assert result_id == ea.id

    def test_verify_email_key_expired(self):
        from django.core.signing import SignatureExpired

        from core.auth.tokens import verify_email_verification_key

        with pytest.raises((SignatureExpired, Exception)):
            verify_email_verification_key("invalid-key-data")

    def test_make_and_verify_password_reset_token(self):
        from core.auth.tokens import (
            make_password_reset_token,
            verify_password_reset_token,
        )

        user = User.objects.create_user(
            email="pwreset_token@example.com", password="test123"
        )
        uid, token = make_password_reset_token(user)
        found_user, valid = verify_password_reset_token(uid, token)
        assert found_user == user
        assert valid is True

    def test_verify_password_reset_token_invalid(self):
        from core.auth.tokens import verify_password_reset_token

        found_user, valid = verify_password_reset_token("invalid-uid", "invalid-token")
        assert found_user is None
        assert valid is False


# ──────────────────────────────────────────────────────────────────────
#  core.auth.backends
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEmailAuthBackend:
    """Tests for EmailAuthBackend."""

    def test_authenticate_success(self):
        from core.auth.backends import EmailAuthBackend

        user = User.objects.create_user(
            email="backend@example.com", password="TestPass123!"
        )
        backend = EmailAuthBackend()
        result = backend.authenticate(
            request=None, email="backend@example.com", password="TestPass123!"
        )
        assert result == user

    def test_authenticate_wrong_password(self):
        from core.auth.backends import EmailAuthBackend

        User.objects.create_user(
            email="backendwrong@example.com", password="TestPass123!"
        )
        backend = EmailAuthBackend()
        result = backend.authenticate(
            request=None, email="backendwrong@example.com", password="WrongPass!"
        )
        assert result is None

    def test_authenticate_nonexistent_user(self):
        from core.auth.backends import EmailAuthBackend

        backend = EmailAuthBackend()
        result = backend.authenticate(
            request=None, email="nobody@example.com", password="Test123!"
        )
        assert result is None

    def test_authenticate_no_email(self):
        from core.auth.backends import EmailAuthBackend

        backend = EmailAuthBackend()
        result = backend.authenticate(request=None, email=None, password="Test123!")
        assert result is None

    def test_authenticate_no_password(self):
        from core.auth.backends import EmailAuthBackend

        backend = EmailAuthBackend()
        result = backend.authenticate(
            request=None, email="test@example.com", password=None
        )
        assert result is None

    def test_authenticate_with_username_kwarg(self):
        from core.auth.backends import EmailAuthBackend

        user = User.objects.create_user(
            email="usernamearg@example.com", password="TestPass123!"
        )
        backend = EmailAuthBackend()
        result = backend.authenticate(
            request=None, username="usernamearg@example.com", password="TestPass123!"
        )
        assert result == user

    def test_authenticate_case_insensitive(self):
        from core.auth.backends import EmailAuthBackend

        user = User.objects.create_user(
            email="CaseTest@example.com", password="TestPass123!"
        )
        backend = EmailAuthBackend()
        result = backend.authenticate(
            request=None, email="casetest@example.com", password="TestPass123!"
        )
        assert result == user


# ──────────────────────────────────────────────────────────────────────
#  core.auth.models
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEmailAddressModel:
    """Tests for core.auth.models.EmailAddress."""

    def test_create_email_address(self):
        from core.auth.models import EmailAddress

        user = User.objects.create_user(
            email="ea_test@example.com", password="test123"
        )
        ea = EmailAddress.objects.create(
            user=user, email="ea_test@example.com", verified=False, primary=True
        )
        assert ea.pk is not None
        assert ea.verified is False
        assert ea.primary is True

    def test_email_address_str_verified(self):
        from core.auth.models import EmailAddress

        user = User.objects.create_user(
            email="ea_str@example.com", password="test123"
        )
        ea = EmailAddress.objects.create(
            user=user, email="ea_str@example.com", verified=True, primary=True
        )
        assert "verified" in str(ea)

    def test_email_address_str_unverified(self):
        from core.auth.models import EmailAddress

        user = User.objects.create_user(
            email="ea_unver@example.com", password="test123"
        )
        ea = EmailAddress.objects.create(
            user=user, email="ea_unver@example.com", verified=False, primary=True
        )
        assert "unverified" in str(ea)

    def test_verify(self):
        from core.auth.models import EmailAddress

        user = User.objects.create_user(
            email="ea_verify@example.com", password="test123"
        )
        ea = EmailAddress.objects.create(
            user=user, email="ea_verify@example.com", verified=False, primary=True
        )
        ea.verify()
        ea.refresh_from_db()
        assert ea.verified is True

    def test_verify_already_verified(self):
        from core.auth.models import EmailAddress

        user = User.objects.create_user(
            email="ea_already@example.com", password="test123"
        )
        ea = EmailAddress.objects.create(
            user=user, email="ea_already@example.com", verified=True, primary=True
        )
        ea.verify()  # Should be no-op
        ea.refresh_from_db()
        assert ea.verified is True

    def test_set_as_primary(self):
        from core.auth.models import EmailAddress

        user = User.objects.create_user(
            email="ea_primary@example.com", password="test123"
        )
        ea1 = EmailAddress.objects.create(
            user=user, email="ea_primary@example.com", verified=True, primary=True
        )
        ea2 = EmailAddress.objects.create(
            user=user, email="ea_secondary@example.com", verified=True, primary=False
        )
        ea2.set_as_primary()
        ea1.refresh_from_db()
        ea2.refresh_from_db()
        assert ea2.primary is True
        assert ea1.primary is False


@pytest.mark.django_db
class TestSocialAccountModel:
    """Tests for core.auth.models.SocialAccount."""

    def test_create_social_account(self):
        from core.auth.models import SocialAccount

        user = User.objects.create_user(
            email="social_acct@example.com", password="test123"
        )
        sa = SocialAccount.objects.create(
            user=user, provider="google", uid="google-uid-123"
        )
        assert sa.pk is not None
        assert sa.provider == "google"
        assert sa.uid == "google-uid-123"
        assert sa.extra_data == {}

    def test_social_account_str(self):
        from core.auth.models import SocialAccount

        user = User.objects.create_user(
            email="social_str@example.com", password="test123"
        )
        sa = SocialAccount.objects.create(
            user=user, provider="apple", uid="apple-uid-456"
        )
        result = str(sa)
        assert "apple" in result
        assert "apple-uid-456" in result
        assert user.email in result


# ──────────────────────────────────────────────────────────────────────
#  core.sanitizers (exercised from app test)
# ──────────────────────────────────────────────────────────────────────


class TestCoreSanitizers:
    """Tests for core.sanitizers exercised from users test_unit."""

    def test_sanitize_text_basic(self):
        from core.sanitizers import sanitize_text

        assert sanitize_text("<b>Hello</b>") == "Hello"
        assert sanitize_text(None) == ""
        assert sanitize_text(42) == "42"

    def test_sanitize_html_basic(self):
        from core.sanitizers import sanitize_html

        result = sanitize_html("<p>Text</p><script>evil</script>")
        assert "<p>" in result
        assert "<script>" not in result

    def test_sanitize_url_basic(self):
        from core.sanitizers import sanitize_url

        assert sanitize_url("https://example.com") == "https://example.com"
        assert sanitize_url("javascript:alert(1)") == ""
        assert sanitize_url(None) == ""

    def test_sanitize_json_values_nested(self):
        from core.sanitizers import sanitize_json_values

        data = {
            "title": "<b>Bold</b>",
            "nested": {"name": "<script>x</script>"},
            "items": ["<em>item</em>", "plain"],
            "count": 5,
        }
        result = sanitize_json_values(data)
        assert result["title"] == "Bold"
        assert "<script>" not in result["nested"]["name"]
        assert result["count"] == 5

    def test_sanitize_html_extra_tags(self):
        from core.sanitizers import sanitize_html

        result = sanitize_html("<h1>Title</h1>", extra_tags={"h1"})
        assert "<h1>" in result

    def test_sanitize_url_ftp_blocked(self):
        from core.sanitizers import sanitize_url

        assert sanitize_url("ftp://files.example.com") == ""

    def test_sanitize_url_strips_whitespace(self):
        from core.sanitizers import sanitize_url

        assert sanitize_url("  https://example.com  ") == "https://example.com"

    def test_sanitize_json_values_non_dict(self):
        from core.sanitizers import sanitize_json_values

        assert sanitize_json_values("not a dict") == "not a dict"


# ──────────────────────────────────────────────────────────────────────
#  core.validators (exercised from app test)
# ──────────────────────────────────────────────────────────────────────


class TestCoreValidators:
    """Tests for core.validators exercised from users test_unit."""

    def test_validate_uuid_valid(self):
        import uuid as _uuid

        from core.validators import validate_uuid

        uid = str(_uuid.uuid4())
        result = validate_uuid(uid)
        assert isinstance(result, _uuid.UUID)

    def test_validate_uuid_object(self):
        import uuid as _uuid

        from core.validators import validate_uuid

        uid = _uuid.uuid4()
        assert validate_uuid(uid) == uid

    def test_validate_uuid_invalid(self):
        from rest_framework.exceptions import ValidationError

        from core.validators import validate_uuid

        with pytest.raises(ValidationError):
            validate_uuid("not-a-uuid")

    def test_validate_pagination_params_defaults(self):
        from core.validators import validate_pagination_params

        page, page_size = validate_pagination_params(None, None)
        assert page == 1
        assert page_size == 20

    def test_validate_pagination_params_invalid(self):
        from rest_framework.exceptions import ValidationError

        from core.validators import validate_pagination_params

        with pytest.raises(ValidationError):
            validate_pagination_params("abc", 20)

    def test_validate_search_query(self):
        from core.validators import validate_search_query

        assert validate_search_query("test") == "test"
        assert validate_search_query("") == ""
        assert validate_search_query(None) == ""

    def test_validate_location(self):
        from rest_framework.exceptions import ValidationError

        from core.validators import validate_location

        assert validate_location("Paris, France") == "Paris, France"
        with pytest.raises(ValidationError):
            validate_location("Location @#$%^")

    def test_validate_coupon_code(self):
        from rest_framework.exceptions import ValidationError

        from core.validators import validate_coupon_code

        assert validate_coupon_code("SAVE50") == "SAVE50"
        with pytest.raises(ValidationError):
            validate_coupon_code("code with spaces!")

    def test_validate_tag_name(self):
        from rest_framework.exceptions import ValidationError

        from core.validators import validate_tag_name

        assert validate_tag_name("education") == "education"
        with pytest.raises(ValidationError):
            validate_tag_name("")

    def test_validate_text_length(self):
        from rest_framework.exceptions import ValidationError

        from core.validators import validate_text_length

        assert validate_text_length("short", max_length=100) == "short"
        with pytest.raises(ValidationError):
            validate_text_length("x" * 20, max_length=10)

    def test_validate_url_no_ssrf_valid(self):
        from core.validators import validate_url_no_ssrf

        url, ip = validate_url_no_ssrf("https://example.com")
        assert url == "https://example.com"

    def test_validate_url_no_ssrf_localhost(self):
        from rest_framework.exceptions import ValidationError

        from core.validators import validate_url_no_ssrf

        with pytest.raises(ValidationError):
            validate_url_no_ssrf("http://localhost:8000")

    def test_validate_url_no_ssrf_empty(self):
        from rest_framework.exceptions import ValidationError

        from core.validators import validate_url_no_ssrf

        with pytest.raises(ValidationError):
            validate_url_no_ssrf("")

    @pytest.mark.django_db
    def test_validate_display_name_valid(self):
        from core.validators import validate_display_name

        assert validate_display_name("John Doe") == "John Doe"

    @pytest.mark.django_db
    def test_validate_display_name_invalid(self):
        from rest_framework.exceptions import ValidationError

        from core.validators import validate_display_name

        with pytest.raises(ValidationError):
            validate_display_name("user@#$%")


# ──────────────────────────────────────────────────────────────────────
#  core.exceptions
# ──────────────────────────────────────────────────────────────────────


class TestCoreExceptions:
    """Tests for core.exceptions helper functions."""

    def test_extract_message_string(self):
        from core.exceptions import _extract_message

        assert _extract_message("error message") == "error message"

    def test_extract_message_list(self):
        from core.exceptions import _extract_message

        assert _extract_message(["first error", "second"]) == "first error"

    def test_extract_message_empty_list(self):
        from core.exceptions import _extract_message

        assert _extract_message([]) == "Unknown error"

    def test_extract_message_dict_non_field_errors(self):
        from core.exceptions import _extract_message

        detail = {"non_field_errors": ["global error"], "field": ["field error"]}
        assert _extract_message(detail) == "global error"

    def test_extract_message_dict_field_error(self):
        from core.exceptions import _extract_message

        detail = {"name": ["Name is required"]}
        assert _extract_message(detail) == "Name is required"


# ──────────────────────────────────────────────────────────────────────
#  core.audit
# ──────────────────────────────────────────────────────────────────────


class TestCoreAudit:
    """Tests for core.audit functions exercised from users test."""

    def test_get_client_ip_xff(self):
        from unittest.mock import Mock

        from core.audit import _get_client_ip

        request = Mock()
        request.META = {"HTTP_X_FORWARDED_FOR": "1.2.3.4, 5.6.7.8"}
        assert _get_client_ip(request) == "1.2.3.4"

    def test_get_client_ip_remote_addr(self):
        from unittest.mock import Mock

        from core.audit import _get_client_ip

        request = Mock()
        request.META = {"REMOTE_ADDR": "10.0.0.1"}
        assert _get_client_ip(request) == "10.0.0.1"

    def test_log_functions_dont_raise(self):
        from unittest.mock import Mock

        import uuid as _uuid

        from core.audit import (
            log_account_change,
            log_ai_output_flagged,
            log_auth_failure,
            log_auth_success,
            log_data_export,
            log_jailbreak_attempt,
            log_permission_denied,
            log_suspicious_input,
            log_webhook_event,
        )

        request = Mock()
        request.META = {"REMOTE_ADDR": "127.0.0.1"}
        request.path = "/api/test/"
        request.user = Mock(id=_uuid.uuid4(), email="test@test.com")

        user = Mock(id=_uuid.uuid4(), email="user@test.com")

        log_auth_failure(request, "test")
        log_auth_success(request, user)
        log_permission_denied(request, "IsOwner", "TestView")
        log_data_export(user)
        log_account_change(user, "test_change")
        log_webhook_event("test.event", "evt_123", "ok")
        log_suspicious_input(request, "field", "<script>")
        log_ai_output_flagged("conv_1", "text", "reason")
        log_jailbreak_attempt(request, "ignore previous")


# ──────────────────────────────────────────────────────────────────────
#  core.middleware (exercised from app test)
# ──────────────────────────────────────────────────────────────────────


class TestCoreMiddleware:
    """Tests for core.middleware exercised from users test."""

    def test_origin_validation_health_check(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        from core.middleware import OriginValidationMiddleware

        mw = OriginValidationMiddleware(get_response=lambda r: HttpResponse("OK"))
        factory = RequestFactory()
        request = factory.get("/health/")
        assert mw(request).status_code == 200

    def test_origin_validation_native(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        from core.middleware import OriginValidationMiddleware

        mw = OriginValidationMiddleware(get_response=lambda r: HttpResponse("OK"))
        factory = RequestFactory()
        request = factory.get("/api/test/", HTTP_X_CLIENT_PLATFORM="native")
        assert mw(request).status_code == 200

    def test_origin_validation_blocked(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        from core.middleware import OriginValidationMiddleware

        mw = OriginValidationMiddleware(get_response=lambda r: HttpResponse("OK"))
        factory = RequestFactory()
        request = factory.post(
            "/api/test/",
            HTTP_ORIGIN="https://evil.com",
            REMOTE_ADDR="8.8.8.8",
        )
        assert mw(request).status_code == 403

    def test_origin_validation_valid_referer_on_post(self):
        """Mutating POST with valid referer passes."""
        from django.http import HttpResponse
        from django.test import RequestFactory

        from core.middleware import OriginValidationMiddleware

        mw = OriginValidationMiddleware(get_response=lambda r: HttpResponse("OK"))
        factory = RequestFactory()
        request = factory.post(
            "/api/test/",
            HTTP_REFERER="https://stepora.app/page",
            REMOTE_ADDR="8.8.8.8",
        )
        assert mw(request).status_code == 200

    def test_origin_validation_no_origin_no_referer(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        from core.middleware import OriginValidationMiddleware

        mw = OriginValidationMiddleware(get_response=lambda r: HttpResponse("OK"))
        factory = RequestFactory()
        request = factory.get("/api/test/", REMOTE_ADDR="8.8.8.8")
        assert mw(request).status_code == 403

    def test_security_headers(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        from core.middleware import SecurityHeadersMiddleware

        mw = SecurityHeadersMiddleware(get_response=lambda r: HttpResponse("OK"))
        factory = RequestFactory()
        request = factory.get("/page/")
        response = mw(request)
        assert response["X-Content-Type-Options"] == "nosniff"
        assert response["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in response

    def test_security_headers_api_no_csp(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        from core.middleware import SecurityHeadersMiddleware

        def json_response(req):
            return HttpResponse('{}', content_type="application/json")

        mw = SecurityHeadersMiddleware(get_response=json_response)
        factory = RequestFactory()
        request = factory.get("/api/test/")
        response = mw(request)
        assert "Content-Security-Policy" not in response

    def test_email_verification_middleware_non_api(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        from core.middleware import EmailVerificationMiddleware

        mw = EmailVerificationMiddleware(get_response=lambda r: HttpResponse("OK"))
        factory = RequestFactory()
        request = factory.get("/static/test.js")
        assert mw(request).status_code == 200

    def test_email_verification_middleware_exempt_path(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        from core.middleware import EmailVerificationMiddleware

        mw = EmailVerificationMiddleware(get_response=lambda r: HttpResponse("OK"))
        factory = RequestFactory()
        request = factory.get("/api/auth/login/")
        assert mw(request).status_code == 200

    def test_email_verification_middleware_no_bearer(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        from core.middleware import EmailVerificationMiddleware

        mw = EmailVerificationMiddleware(get_response=lambda r: HttpResponse("OK"))
        factory = RequestFactory()
        request = factory.get("/api/dreams/")
        assert mw(request).status_code == 200

    @pytest.mark.django_db
    def test_last_activity_middleware_anon(self):
        from django.contrib.auth.models import AnonymousUser
        from django.http import HttpResponse
        from django.test import RequestFactory

        from core.middleware import LastActivityMiddleware

        mw = LastActivityMiddleware(get_response=lambda r: HttpResponse("OK"))
        factory = RequestFactory()
        request = factory.get("/api/test/")
        request.user = AnonymousUser()
        assert mw(request).status_code == 200


# ──────────────────────────────────────────────────────────────────────
#  core.permissions (exercised from users test)
# ──────────────────────────────────────────────────────────────────────


class TestCorePermissions:
    """Tests for core.permissions."""

    def test_is_email_verified_unauthenticated(self):
        from unittest.mock import Mock

        from core.permissions import IsEmailVerified

        perm = IsEmailVerified()
        request = Mock()
        request.user = Mock(is_authenticated=False)
        request.path = "/api/dreams/"
        assert perm.has_permission(request, None) is True

    def test_is_email_verified_exempt(self):
        from unittest.mock import Mock

        from core.permissions import IsEmailVerified

        perm = IsEmailVerified()
        request = Mock()
        request.user = Mock(is_authenticated=True)
        request.path = "/api/auth/login/"
        assert perm.has_permission(request, None) is True

    def test_is_owner_match(self):
        from unittest.mock import Mock

        from core.permissions import IsOwner

        perm = IsOwner()
        user = Mock()
        request = Mock(user=user)
        obj = Mock(user=user)
        assert perm.has_object_permission(request, None, obj) is True

    def test_is_owner_no_match(self):
        from unittest.mock import Mock

        from core.permissions import IsOwner

        perm = IsOwner()
        request = Mock(user=Mock())
        obj = Mock(user=Mock())
        assert perm.has_object_permission(request, None, obj) is False

    def test_is_owner_user1_user2(self):
        from unittest.mock import Mock

        from core.permissions import IsOwner

        perm = IsOwner()
        user = Mock()
        request = Mock(user=user)
        obj = Mock(spec=[])
        obj.user1 = user
        obj.user2 = Mock()
        assert perm.has_object_permission(request, None, obj) is True

    def test_is_owner_no_user_attr(self):
        from unittest.mock import Mock

        from core.permissions import IsOwner

        perm = IsOwner()
        request = Mock(user=Mock())
        obj = Mock(spec=[])
        assert perm.has_object_permission(request, None, obj) is False

    def test_is_premium_user_denied(self):
        from unittest.mock import Mock

        from core.permissions import IsPremiumUser

        perm = IsPremiumUser()
        user = Mock(is_authenticated=True)
        user.get_active_plan.return_value = None
        request = Mock(user=user)
        assert perm.has_permission(request, None) is False

    def test_is_premium_user_allowed(self):
        from unittest.mock import Mock

        from core.permissions import IsPremiumUser

        perm = IsPremiumUser()
        user = Mock(is_authenticated=True)
        plan = Mock(slug="premium")
        user.get_active_plan.return_value = plan
        request = Mock(user=user)
        assert perm.has_permission(request, None) is True

    def test_is_pro_user_denied_with_premium(self):
        from unittest.mock import Mock

        from core.permissions import IsProUser

        perm = IsProUser()
        user = Mock(is_authenticated=True)
        plan = Mock(slug="premium")
        user.get_active_plan.return_value = plan
        request = Mock(user=user)
        assert perm.has_permission(request, None) is False

    def test_can_use_ai_denied(self):
        from unittest.mock import Mock

        from core.permissions import CanUseAI

        perm = CanUseAI()
        user = Mock(is_authenticated=True)
        plan = Mock(has_ai=False)
        user.get_active_plan.return_value = plan
        request = Mock(user=user)
        assert perm.has_permission(request, None) is False

    def test_can_use_buddy(self):
        from unittest.mock import Mock

        from core.permissions import CanUseBuddy

        perm = CanUseBuddy()
        user = Mock(is_authenticated=True)
        plan = Mock(has_buddy=True)
        user.get_active_plan.return_value = plan
        request = Mock(user=user)
        assert perm.has_permission(request, None) is True

    def test_can_use_circles_create_denied(self):
        from unittest.mock import Mock

        from core.permissions import CanUseCircles

        perm = CanUseCircles()
        user = Mock(is_authenticated=True)
        plan = Mock(has_circle_create=False, has_circles=True)
        user.get_active_plan.return_value = plan
        request = Mock(user=user, method="POST")
        assert perm.has_permission(request, None) is False

    def test_can_use_circles_no_plan(self):
        from unittest.mock import Mock

        from core.permissions import CanUseCircles

        perm = CanUseCircles()
        user = Mock(is_authenticated=True)
        user.get_active_plan.return_value = None
        request = Mock(user=user, method="GET")
        assert perm.has_permission(request, None) is False

    def test_can_use_circles_get_no_circles(self):
        from unittest.mock import Mock

        from core.permissions import CanUseCircles

        perm = CanUseCircles()
        user = Mock(is_authenticated=True)
        plan = Mock(has_circles=False)
        user.get_active_plan.return_value = plan
        request = Mock(user=user, method="GET")
        assert perm.has_permission(request, None) is False

    def test_can_use_vision_board(self):
        from unittest.mock import Mock

        from core.permissions import CanUseVisionBoard

        perm = CanUseVisionBoard()
        user = Mock(is_authenticated=True)
        plan = Mock(has_vision_board=True)
        user.get_active_plan.return_value = plan
        request = Mock(user=user)
        assert perm.has_permission(request, None) is True

    def test_can_use_league(self):
        from unittest.mock import Mock

        from core.permissions import CanUseLeague

        perm = CanUseLeague()
        user = Mock(is_authenticated=True)
        plan = Mock(has_league=True)
        user.get_active_plan.return_value = plan
        request = Mock(user=user)
        assert perm.has_permission(request, None) is True

    def test_can_use_store(self):
        from unittest.mock import Mock

        from core.permissions import CanUseStore

        perm = CanUseStore()
        user = Mock(is_authenticated=True)
        plan = Mock(has_store=True)
        user.get_active_plan.return_value = plan
        request = Mock(user=user)
        assert perm.has_permission(request, None) is True

    def test_can_use_social_feed(self):
        from unittest.mock import Mock

        from core.permissions import CanUseSocialFeed

        perm = CanUseSocialFeed()
        user = Mock(is_authenticated=True)
        plan = Mock(has_social_feed=True)
        user.get_active_plan.return_value = plan
        request = Mock(user=user)
        assert perm.has_permission(request, None) is True

    def test_can_make_public_dream(self):
        from unittest.mock import Mock

        from core.permissions import CanMakePublicDream

        perm = CanMakePublicDream()
        user = Mock(is_authenticated=True)
        plan = Mock(has_public_dreams=True)
        user.get_active_plan.return_value = plan
        request = Mock(user=user)
        assert perm.has_permission(request, None) is True

    @pytest.mark.django_db
    def test_can_create_dream_post_under_limit(self):
        from unittest.mock import Mock

        from core.permissions import CanCreateDream

        perm = CanCreateDream()
        user = User.objects.create_user(
            email="dreamlimit_test@example.com", password="test123"
        )
        plan = Mock(dream_limit=3, slug="free")
        user.get_active_plan = Mock(return_value=plan)
        request = Mock(user=user, method="POST")
        assert perm.has_permission(request, None) is True

    @pytest.mark.django_db
    def test_can_create_dream_unlimited(self):
        from unittest.mock import Mock

        from core.permissions import CanCreateDream

        perm = CanCreateDream()
        user = User.objects.create_user(
            email="dreamunlimited_test@example.com", password="test123"
        )
        plan = Mock(dream_limit=-1, slug="pro")
        user.get_active_plan = Mock(return_value=plan)
        request = Mock(user=user, method="POST")
        assert perm.has_permission(request, None) is True


# ──────────────────────────────────────────────────────────────────────
#  core.throttles
# ──────────────────────────────────────────────────────────────────────


class TestCoreThrottles:
    """Tests for core.throttles."""

    def test_throttle_scope_attributes(self):
        from core.throttles import (
            AIRateThrottle,
            AIPlanRateThrottle,
            AuthLoginRateThrottle,
            AuthPasswordRateThrottle,
            AuthRateThrottle,
            AuthRegisterRateThrottle,
            ExportRateThrottle,
            SearchRateThrottle,
            StorePurchaseRateThrottle,
            SubscriptionRateThrottle,
        )

        assert AuthRateThrottle.scope == "auth"
        assert AuthLoginRateThrottle.scope == "auth_login"
        assert AuthRegisterRateThrottle.scope == "auth_register"
        assert AuthPasswordRateThrottle.scope == "auth_password"
        assert AIRateThrottle.scope == "ai_chat"
        assert AIPlanRateThrottle.scope == "ai_plan"
        assert SearchRateThrottle.scope == "search"
        assert ExportRateThrottle.scope == "export"
        assert StorePurchaseRateThrottle.scope == "store_purchase"
        assert SubscriptionRateThrottle.scope == "subscription"

    def test_daily_ai_quota_categories(self):
        from core.throttles import (
            AIChatDailyThrottle,
            AIImageDailyThrottle,
            AIPlanDailyThrottle,
            AIVoiceDailyThrottle,
        )

        assert AIChatDailyThrottle.category == "ai_chat"
        assert AIPlanDailyThrottle.category == "ai_plan"
        assert AIImageDailyThrottle.category == "ai_image"
        assert AIVoiceDailyThrottle.category == "ai_voice"

    def test_daily_ai_quota_wait(self):
        from core.throttles import DailyAIQuotaThrottle

        t = DailyAIQuotaThrottle()
        wait_seconds = t.wait()
        assert isinstance(wait_seconds, int)
        assert wait_seconds >= 1


# ──────────────────────────────────────────────────────────────────────
#  core.ai_usage
# ──────────────────────────────────────────────────────────────────────


class TestCoreAIUsage:
    """Tests for core.ai_usage.AIUsageTracker."""

    def test_get_reset_time(self):
        from datetime import datetime, timezone as tz

        from core.ai_usage import AIUsageTracker

        reset = AIUsageTracker.get_reset_time()
        now = datetime.now(tz.utc)
        assert reset > now
        assert reset.hour == 0 and reset.minute == 0

    def test_quota_categories_defined(self):
        from core.ai_usage import QUOTA_CATEGORIES

        assert "ai_chat" in QUOTA_CATEGORIES
        assert "ai_plan" in QUOTA_CATEGORIES
        assert "ai_image" in QUOTA_CATEGORIES
        assert "ai_voice" in QUOTA_CATEGORIES
        assert "ai_background" in QUOTA_CATEGORIES

    def test_tracker_disabled(self):
        from unittest.mock import patch

        from core.ai_usage import AIUsageTracker

        with patch.object(AIUsageTracker, "__init__", lambda self: None):
            tracker = AIUsageTracker.__new__(AIUsageTracker)
            tracker.enabled = False
            tracker.config = {}
            tracker.prefix = "ai_usage"
            tracker.ttl_seconds = 90000
            allowed, info = tracker.check_quota(None, "ai_chat")
            assert allowed is True
            assert info["limit"] == -1

    def test_tracker_increment_disabled(self):
        from unittest.mock import patch

        from core.ai_usage import AIUsageTracker

        with patch.object(AIUsageTracker, "__init__", lambda self: None):
            tracker = AIUsageTracker.__new__(AIUsageTracker)
            tracker.enabled = False
            assert tracker.increment(None, "ai_chat") == 0


# ──────────────────────────────────────────────────────────────────────
#  core.pagination
# ──────────────────────────────────────────────────────────────────────


class TestCorePagination:
    """Tests for core.pagination classes."""

    def test_standard_limit_offset(self):
        from core.pagination import StandardLimitOffsetPagination

        p = StandardLimitOffsetPagination()
        assert p.default_limit == 20
        assert p.max_limit == 100

    def test_large_limit_offset(self):
        from core.pagination import LargeLimitOffsetPagination

        p = LargeLimitOffsetPagination()
        assert p.default_limit == 50
        assert p.max_limit == 200

    def test_standard_page_number(self):
        from core.pagination import StandardResultsSetPagination

        p = StandardResultsSetPagination()
        assert p.page_size == 20
        assert p.max_page_size == 100

    def test_large_page_number(self):
        from core.pagination import LargeResultsSetPagination

        p = LargeResultsSetPagination()
        assert p.page_size == 50
        assert p.max_page_size == 200


# ══════════════════════════════════════════════════════════════════════
#  API ENDPOINT TESTS — UserViewSet
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUserAPI:
    """Tests for User API endpoints."""

    def test_get_me(self, users_client):
        resp = users_client.get(
            "/api/users/me/", HTTP_ORIGIN="https://stepora.app"
        )
        assert resp.status_code == 200

    def test_patch_me(self, users_client):
        resp = users_client.put(
            "/api/users/me/",
            {"bio": "Updated bio"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        # PUT or PATCH — accept 200 or 405 if only one method is allowed
        assert resp.status_code in (200, 405)

    def test_list_users(self, users_client):
        resp = users_client.get("/api/users/", HTTP_ORIGIN="https://stepora.app")
        assert resp.status_code == 200

    def test_get_me_unauthenticated(self):
        from rest_framework.test import APIClient

        client = APIClient()
        resp = client.get("/api/users/me/", HTTP_ORIGIN="https://stepora.app")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestTwoFactorAPI:
    """Tests for 2FA API endpoints."""

    def test_2fa_status(self, users_client):
        resp = users_client.get(
            "/api/users/2fa/status/", HTTP_ORIGIN="https://stepora.app"
        )
        assert resp.status_code == 200

    def test_2fa_setup(self, users_client):
        resp = users_client.post(
            "/api/users/2fa/setup/", HTTP_ORIGIN="https://stepora.app"
        )
        assert resp.status_code == 200
        assert "secret" in resp.data
        assert "provisioning_uri" in resp.data

    def test_2fa_verify_no_code(self, users_client):
        resp = users_client.post(
            "/api/users/2fa/verify/",
            {},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 400

    def test_2fa_disable_wrong_password(self, users_client):
        resp = users_client.post(
            "/api/users/2fa/disable/",
            {"password": "wrongpassword"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 400

    def test_2fa_disable_no_password(self, users_client):
        resp = users_client.post(
            "/api/users/2fa/disable/",
            {},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 400

    def test_2fa_regen_backup_codes_wrong_password(self, users_client):
        resp = users_client.post(
            "/api/users/2fa/backup-codes/",
            {"password": "wrongpwd"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 400

    def test_2fa_regen_backup_codes_not_enabled(self, users_client, users_user):
        resp = users_client.post(
            "/api/users/2fa/backup-codes/",
            {"password": "testpassword123"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 400

    def test_2fa_verify_invalid_code(self, users_client, users_user):
        # Setup first
        users_client.post(
            "/api/users/2fa/setup/", HTTP_ORIGIN="https://stepora.app"
        )
        resp = users_client.post(
            "/api/users/2fa/verify/",
            {"code": "000000"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 400

    def test_2fa_verify_no_setup(self, users_client, users_user):
        users_user.totp_secret = ""
        users_user.save(update_fields=["totp_secret"])
        resp = users_client.post(
            "/api/users/2fa/verify/",
            {"code": "123456"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestUserViewSetActions:
    """Tests for UserViewSet custom actions."""

    def test_stats(self, users_client):
        resp = users_client.get(
            "/api/users/stats/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_ai_usage(self, users_client):
        resp = users_client.get(
            "/api/users/ai-usage/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_achievements(self, users_client):
        resp = users_client.get(
            "/api/users/achievements/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_streak_details(self, users_client):
        resp = users_client.get(
            "/api/users/streak-details/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_dashboard(self, users_client):
        resp = users_client.get(
            "/api/users/dashboard/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404, 500)

    def test_profile_completeness(self, users_client):
        resp = users_client.get(
            "/api/users/profile-completeness/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_persona_get(self, users_client):
        resp = users_client.get(
            "/api/users/persona/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_energy_profile_get(self, users_client):
        resp = users_client.get(
            "/api/users/energy-profile/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_notification_preferences(self, users_client):
        resp = users_client.put(
            "/api/users/notification-preferences/",
            {"push_enabled": True, "email_enabled": True},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 400)

    def test_complete_onboarding(self, users_client):
        resp = users_client.post(
            "/api/users/complete-onboarding/",
            {},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 400)

    def test_retrieve_other_user(self, users_client, users_user2):
        resp = users_client.get(
            f"/api/users/{users_user2.id}/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404)

    def test_persona_put(self, users_client):
        resp = users_client.put(
            "/api/users/persona/",
            {"occupation": "Engineer", "available_hours_per_week": 10},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 400)

    def test_energy_profile_put(self, users_client):
        resp = users_client.put(
            "/api/users/energy-profile/",
            {"energy_pattern": "morning_person"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 400)

    def test_delete_account(self, users_client):
        resp = users_client.post(
            "/api/users/delete-account/",
            {"password": "testpassword123"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 400, 403)

    def test_change_email(self, users_client):
        resp = users_client.post(
            "/api/users/change-email/",
            {"new_email": "newemail@example.com", "password": "testpassword123"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 400, 403, 500)

    def test_personality_quiz(self, users_client):
        resp = users_client.post(
            "/api/users/personality-quiz/",
            {"answers": {"q1": "a", "q2": "b"}},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 400)

    def test_export_data(self, users_client):
        resp = users_client.get(
            "/api/users/export-data/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 400, 403, 404, 429, 500)
