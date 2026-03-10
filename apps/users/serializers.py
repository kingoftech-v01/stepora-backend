"""
Serializers for Users app.
"""

from typing import Optional

from rest_framework import serializers

from core.sanitizers import sanitize_json_values, sanitize_text, sanitize_url
from core.validators import validate_display_name, validate_location

from .models import GamificationProfile, User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""

    can_create_dream = serializers.BooleanField(
        read_only=True, help_text="Whether user can create more dreams."
    )
    is_premium = serializers.SerializerMethodField(
        help_text="Whether user has premium subscription."
    )
    email_verified = serializers.SerializerMethodField(
        help_text="Whether user email is verified."
    )
    plan_features = serializers.SerializerMethodField(
        help_text="Feature flags from the active subscription plan."
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "display_name",
            "avatar_url",
            "avatar_image",
            "bio",
            "location",
            "social_links",
            "profile_visibility",
            "timezone",
            "theme_mode",
            "accent_color",
            "subscription",
            "subscription_ends",
            "work_schedule",
            "notification_prefs",
            "app_prefs",
            "persona",
            "energy_profile",
            "xp",
            "level",
            "streak_days",
            "last_activity",
            "can_create_dream",
            "is_premium",
            "email_verified",
            "plan_features",
            "onboarding_completed",
            "dreamer_type",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "email",
            "subscription",
            "subscription_ends",
            "xp",
            "level",
            "streak_days",
            "last_activity",
            "email_verified",
            "onboarding_completed",
            "dreamer_type",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "id": {"help_text": "Unique user identifier."},
            "email": {"help_text": "User email address."},
            "display_name": {"help_text": "User display name shown publicly."},
            "avatar_url": {"help_text": "URL to user avatar image."},
            "avatar_image": {"help_text": "Uploaded avatar image file."},
            "bio": {"help_text": "Short user biography."},
            "location": {"help_text": "User location or city."},
            "social_links": {"help_text": "JSON object of social media links."},
            "profile_visibility": {"help_text": "Profile visibility setting."},
            "timezone": {"help_text": "User preferred timezone."},
            "theme_mode": {"help_text": "Preferred theme mode (auto, dark, light)."},
            "accent_color": {"help_text": "User accent color hex code."},
            "subscription": {"help_text": "Current subscription plan."},
            "subscription_ends": {"help_text": "Subscription expiration date."},
            "work_schedule": {"help_text": "Preferred work schedule settings."},
            "notification_prefs": {"help_text": "Notification preference settings."},
            "app_prefs": {"help_text": "Application preference settings."},
            "energy_profile": {"help_text": "Energy profile for smart scheduling."},
            "xp": {"help_text": "Total experience points earned."},
            "level": {"help_text": "Current user level."},
            "streak_days": {"help_text": "Consecutive active days streak."},
            "last_activity": {"help_text": "Timestamp of last user activity."},
            "created_at": {"help_text": "Account creation timestamp."},
            "updated_at": {"help_text": "Last profile update timestamp."},
        }

    def get_is_premium(self, obj) -> bool:
        return obj.is_premium()

    def get_email_verified(self, obj) -> bool:
        from core.auth.models import EmailAddress

        return EmailAddress.objects.filter(user=obj, verified=True).exists()

    def get_plan_features(self, obj) -> dict:
        plan = obj.get_active_plan()
        if not plan:
            return {
                "has_ai": False,
                "has_buddy": False,
                "has_circles": False,
                "has_circle_create": False,
                "has_vision_board": False,
                "has_league": False,
                "has_store": False,
                "has_social_feed": False,
                "dream_limit": 1,
                "plan_name": "Free",
                "plan_slug": "free",
            }
        return {
            "has_ai": plan.has_ai,
            "has_buddy": plan.has_buddy,
            "has_circles": plan.has_circles,
            "has_circle_create": plan.has_circle_create,
            "has_vision_board": plan.has_vision_board,
            "has_league": plan.has_league,
            "has_store": plan.has_store,
            "has_social_feed": plan.has_social_feed,
            "dream_limit": plan.dream_limit,
            "plan_name": plan.name,
            "plan_slug": plan.slug,
        }

    def validate_display_name(self, value):
        """Validate display name uniqueness."""
        user_id = self.instance.pk if self.instance else None
        return validate_display_name(value, exclude_user_id=user_id)


class UserProfileSerializer(serializers.ModelSerializer):
    """Detailed user profile serializer."""

    is_premium = serializers.SerializerMethodField(
        help_text="Whether user has premium subscription."
    )
    email_verified = serializers.SerializerMethodField(
        help_text="Whether user email is verified."
    )
    can_create_dream = serializers.BooleanField(
        read_only=True, help_text="Whether user can create more dreams."
    )
    active_dreams_count = serializers.SerializerMethodField(
        help_text="Number of currently active dreams."
    )
    completed_dreams_count = serializers.SerializerMethodField(
        help_text="Number of completed dreams."
    )
    achievements_summary = serializers.SerializerMethodField(
        help_text="Summary of unlocked achievements."
    )
    equipped_items = serializers.SerializerMethodField(
        help_text="List of currently equipped store items."
    )
    rank = serializers.SerializerMethodField(help_text="Current season league rank.")
    plan_features = serializers.SerializerMethodField(
        help_text="Feature flags from the active subscription plan."
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "display_name",
            "avatar_url",
            "avatar_image",
            "bio",
            "location",
            "social_links",
            "profile_visibility",
            "timezone",
            "theme_mode",
            "accent_color",
            "subscription",
            "subscription_ends",
            "xp",
            "level",
            "streak_days",
            "is_premium",
            "email_verified",
            "can_create_dream",
            "onboarding_completed",
            "active_dreams_count",
            "completed_dreams_count",
            "achievements_summary",
            "equipped_items",
            "rank",
            "plan_features",
            "work_schedule",
            "notification_prefs",
            "app_prefs",
            "persona",
            "dreamer_type",
            "created_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique user identifier."},
            "email": {"help_text": "User email address."},
            "display_name": {"help_text": "User display name shown publicly."},
            "avatar_url": {"help_text": "URL to user avatar image."},
            "avatar_image": {"help_text": "Uploaded avatar image file."},
            "bio": {"help_text": "Short user biography."},
            "location": {"help_text": "User location or city."},
            "social_links": {"help_text": "JSON object of social media links."},
            "profile_visibility": {"help_text": "Profile visibility setting."},
            "timezone": {"help_text": "User preferred timezone."},
            "theme_mode": {"help_text": "Preferred theme mode (auto, dark, light)."},
            "accent_color": {"help_text": "User accent color hex code."},
            "subscription": {"help_text": "Current subscription plan."},
            "subscription_ends": {"help_text": "Subscription expiration date."},
            "xp": {"help_text": "Total experience points earned."},
            "level": {"help_text": "Current user level."},
            "streak_days": {"help_text": "Consecutive active days streak."},
            "created_at": {"help_text": "Account creation timestamp."},
        }

    def get_is_premium(self, obj) -> bool:
        return obj.is_premium()

    def get_email_verified(self, obj) -> bool:
        from core.auth.models import EmailAddress

        return EmailAddress.objects.filter(user=obj, verified=True).exists()

    def get_active_dreams_count(self, obj) -> int:
        return obj.dreams.filter(status="active").count()

    def get_completed_dreams_count(self, obj) -> int:
        return obj.dreams.filter(status="completed").count()

    def get_achievements_summary(self, obj) -> dict:
        """Return achievements summary for profile display."""
        try:
            from .models import Achievement, UserAchievement

            total = Achievement.objects.filter(is_active=True).count()
            user_achievements = (
                UserAchievement.objects.filter(user=obj)
                .select_related("achievement")
                .order_by("-unlocked_at")
            )
            unlocked = user_achievements.count()
            recent = [
                {
                    "name": ua.achievement.name,
                    "icon": ua.achievement.icon,
                    "unlocked_at": ua.unlocked_at,
                }
                for ua in user_achievements[:5]
            ]
            return {"unlocked": unlocked, "total": total, "recent": recent}
        except Exception:
            return {"unlocked": 0, "total": 0, "recent": []}

    def get_equipped_items(self, obj) -> list:
        """Return list of equipped store items."""
        try:
            from apps.store.models import UserInventory

            equipped = UserInventory.objects.filter(
                user=obj, is_equipped=True
            ).select_related("item")
            return [
                {
                    "item_type": inv.item.item_type,
                    "name": inv.item.name,
                    "slug": inv.item.slug,
                    "rarity": inv.item.rarity,
                    "image_url": inv.item.image_url,
                }
                for inv in equipped
            ]
        except Exception:
            return []

    def get_rank(self, obj) -> Optional[dict]:
        """Return user's current season rank."""
        try:
            from apps.leagues.models import LeagueStanding, Season

            season = Season.get_active_season()
            if not season:
                return None
            standing = (
                LeagueStanding.objects.filter(user=obj, season=season)
                .select_related("league")
                .first()
            )
            if not standing:
                return None
            return {
                "rank": standing.rank,
                "league_name": standing.league.name,
                "league_tier": standing.league.tier,
                "xp_this_season": standing.xp_earned_this_season,
            }
        except Exception:
            return None

    def get_plan_features(self, obj) -> dict:
        plan = obj.get_active_plan()
        if not plan:
            return {
                "has_ai": False,
                "has_buddy": False,
                "has_circles": False,
                "has_circle_create": False,
                "has_vision_board": False,
                "has_league": False,
                "has_store": False,
                "has_social_feed": False,
                "dream_limit": 1,
                "plan_name": "Free",
                "plan_slug": "free",
            }
        return {
            "has_ai": plan.has_ai,
            "has_buddy": plan.has_buddy,
            "has_circles": plan.has_circles,
            "has_circle_create": plan.has_circle_create,
            "has_vision_board": plan.has_vision_board,
            "has_league": plan.has_league,
            "has_store": plan.has_store,
            "has_social_feed": plan.has_social_feed,
            "dream_limit": plan.dream_limit,
            "plan_name": plan.name,
            "plan_slug": plan.slug,
        }


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""

    class Meta:
        model = User
        fields = [
            "display_name",
            "avatar_url",
            "bio",
            "location",
            "social_links",
            "profile_visibility",
            "timezone",
            "theme_mode",
            "accent_color",
            "work_schedule",
            "notification_prefs",
            "app_prefs",
        ]
        extra_kwargs = {
            "display_name": {"help_text": "User display name shown publicly."},
            "avatar_url": {"help_text": "URL to user avatar image."},
            "bio": {"help_text": "Short user biography."},
            "location": {"help_text": "User location or city."},
            "social_links": {"help_text": "JSON object of social media links."},
            "profile_visibility": {"help_text": "Profile visibility setting."},
            "timezone": {"help_text": "User preferred timezone."},
            "theme_mode": {"help_text": "Preferred theme mode (auto, dark, light)."},
            "accent_color": {"help_text": "User accent color hex code."},
            "work_schedule": {"help_text": "Preferred work schedule settings."},
            "notification_prefs": {"help_text": "Notification preference settings."},
            "app_prefs": {"help_text": "Application preference settings."},
        }

    def validate_display_name(self, value):
        """Sanitize and validate display name (must be unique)."""
        user_id = self.instance.pk if self.instance else None
        return validate_display_name(value, exclude_user_id=user_id)

    def validate_avatar_url(self, value):
        """Sanitize avatar URL to prevent XSS."""
        return sanitize_url(value)

    def validate_bio(self, value):
        """Sanitize bio text."""
        return sanitize_text(value)

    def validate_location(self, value):
        """Sanitize and validate location."""
        return validate_location(value)

    def validate_social_links(self, value):
        """Sanitize social links JSON values."""
        if value and isinstance(value, dict):
            return sanitize_json_values(value)
        return value

    def validate_work_schedule(self, value):
        """Sanitize work schedule JSON values."""
        if value and isinstance(value, dict):
            return sanitize_json_values(value)
        return value

    def validate_notification_prefs(self, value):
        """Sanitize notification prefs JSON values."""
        if value and isinstance(value, dict):
            return sanitize_json_values(value)
        return value

    def validate_app_prefs(self, value):
        """Sanitize app prefs JSON values."""
        if value and isinstance(value, dict):
            return sanitize_json_values(value)
        return value

    def validate_accent_color(self, value):
        """Validate accent color is a valid hex code."""
        import re

        if value and not re.match(r"^#[0-9A-Fa-f]{6}$", value):
            raise serializers.ValidationError(
                "Must be a valid hex color code (e.g. #8B5CF6)."
            )
        return value


class GamificationProfileSerializer(serializers.ModelSerializer):
    """Serializer for Gamification profile."""

    health_level = serializers.SerializerMethodField(
        help_text="Computed level for health category."
    )
    career_level = serializers.SerializerMethodField(
        help_text="Computed level for career category."
    )
    relationships_level = serializers.SerializerMethodField(
        help_text="Computed level for relationships category."
    )
    personal_growth_level = serializers.SerializerMethodField(
        help_text="Computed level for personal growth category."
    )
    finance_level = serializers.SerializerMethodField(
        help_text="Computed level for finance category."
    )
    hobbies_level = serializers.SerializerMethodField(
        help_text="Computed level for hobbies category."
    )
    skill_radar = serializers.SerializerMethodField(
        help_text="Skill radar data across all categories."
    )

    class Meta:
        model = GamificationProfile
        fields = [
            "id",
            "health_xp",
            "career_xp",
            "relationships_xp",
            "personal_growth_xp",
            "finance_xp",
            "hobbies_xp",
            "health_level",
            "career_level",
            "relationships_level",
            "personal_growth_level",
            "finance_level",
            "hobbies_level",
            "skill_radar",
            "badges",
            "achievements",
            "streak_jokers",
        ]
        read_only_fields = ["id", "badges", "achievements"]
        extra_kwargs = {
            "id": {"help_text": "Unique gamification profile identifier."},
            "health_xp": {"help_text": "Experience points in health category."},
            "career_xp": {"help_text": "Experience points in career category."},
            "relationships_xp": {
                "help_text": "Experience points in relationships category."
            },
            "personal_growth_xp": {
                "help_text": "Experience points in personal growth category."
            },
            "finance_xp": {"help_text": "Experience points in finance category."},
            "hobbies_xp": {"help_text": "Experience points in hobbies category."},
            "badges": {"help_text": "JSON list of earned badges."},
            "achievements": {"help_text": "JSON list of unlocked achievements."},
            "streak_jokers": {"help_text": "Number of available streak jokers."},
        }

    def get_health_level(self, obj) -> int:
        return obj.get_attribute_level("health")

    def get_career_level(self, obj) -> int:
        return obj.get_attribute_level("career")

    def get_relationships_level(self, obj) -> int:
        return obj.get_attribute_level("relationships")

    def get_personal_growth_level(self, obj) -> int:
        return obj.get_attribute_level("personal_growth")

    def get_finance_level(self, obj) -> int:
        return obj.get_attribute_level("finance")

    def get_hobbies_level(self, obj) -> int:
        return obj.get_attribute_level("hobbies")

    def get_skill_radar(self, obj) -> dict:
        """Return skill radar data for all 6 categories."""
        categories = [
            {"category": "health", "label": "Health", "icon": "heart"},
            {"category": "career", "label": "Career", "icon": "briefcase"},
            {"category": "relationships", "label": "Relationships", "icon": "users"},
            {
                "category": "personal_growth",
                "label": "Personal Growth",
                "icon": "brain",
            },
            {"category": "finance", "label": "Finance", "icon": "wallet"},
            {"category": "hobbies", "label": "Hobbies", "icon": "palette"},
        ]
        return [
            {
                **cat,
                "xp": getattr(obj, f"{cat['category']}_xp", 0),
                "level": obj.get_attribute_level(cat["category"]),
            }
            for cat in categories
        ]


class Verify2FASerializer(serializers.Serializer):
    """Serializer to verify a TOTP code during 2FA setup or login."""

    code = serializers.CharField(max_length=6, min_length=6)


class Disable2FASerializer(serializers.Serializer):
    """Serializer to disable 2FA (requires password + TOTP code)."""

    password = serializers.CharField()
    code = serializers.CharField(max_length=6, min_length=6)
