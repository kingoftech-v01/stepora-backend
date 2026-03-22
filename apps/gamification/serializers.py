"""
Serializers for the Gamification system.
"""

from rest_framework import serializers

from .models import (
    Achievement,
    DailyActivity,
    GamificationProfile,
    HabitChain,
    UserAchievement,
)


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


class AchievementSerializer(serializers.ModelSerializer):
    """Serializer for Achievement model."""

    class Meta:
        model = Achievement
        fields = [
            "id",
            "name",
            "description",
            "icon",
            "category",
            "rarity",
            "xp_reward",
            "condition_type",
            "condition_value",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class UserAchievementSerializer(serializers.ModelSerializer):
    """Serializer for UserAchievement model."""

    achievement = AchievementSerializer(read_only=True)

    class Meta:
        model = UserAchievement
        fields = [
            "id",
            "achievement",
            "unlocked_at",
            "progress",
        ]
        read_only_fields = fields


class DailyActivitySerializer(serializers.ModelSerializer):
    """Serializer for DailyActivity model."""

    class Meta:
        model = DailyActivity
        fields = [
            "id",
            "date",
            "tasks_completed",
            "xp_earned",
            "minutes_active",
            "created_at",
        ]
        read_only_fields = fields


class HabitChainSerializer(serializers.ModelSerializer):
    """Serializer for HabitChain model."""

    class Meta:
        model = HabitChain
        fields = [
            "id",
            "date",
            "chain_type",
            "completed",
            "created_at",
        ]
        read_only_fields = fields
