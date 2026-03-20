"""
Django admin configuration for Gamification app.
"""

from django.contrib import admin

from .models import (
    Achievement,
    DailyActivity,
    GamificationProfile,
    HabitChain,
    UserAchievement,
)


@admin.register(GamificationProfile)
class GamificationProfileAdmin(admin.ModelAdmin):
    """Admin interface for Gamification profiles."""

    list_display = [
        "user",
        "health_level",
        "career_level",
        "relationships_level",
        "streak_jokers",
    ]
    list_filter = ["created_at"]
    search_fields = ["user__email"]
    readonly_fields = ["created_at", "updated_at"]

    def health_level(self, obj):
        return obj.get_attribute_level("health")

    def career_level(self, obj):
        return obj.get_attribute_level("career")

    def relationships_level(self, obj):
        return obj.get_attribute_level("relationships")


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    """Admin interface for Achievement model."""

    list_display = [
        "name",
        "icon",
        "category",
        "condition_type",
        "condition_value",
        "xp_reward",
        "is_active",
        "created_at",
    ]
    list_filter = ["category", "condition_type", "is_active"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at"]


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    """Admin interface for UserAchievement model."""

    list_display = ["user", "achievement", "unlocked_at"]
    list_filter = ["unlocked_at"]
    search_fields = ["user__email", "user__display_name", "achievement__name"]
    readonly_fields = ["unlocked_at"]
    raw_id_fields = ["user", "achievement"]


@admin.register(DailyActivity)
class DailyActivityAdmin(admin.ModelAdmin):
    """Admin interface for DailyActivity model."""

    list_display = [
        "user",
        "date",
        "tasks_completed",
        "xp_earned",
        "minutes_active",
        "created_at",
    ]
    list_filter = ["date"]
    search_fields = ["user__email", "user__display_name"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["user"]


@admin.register(HabitChain)
class HabitChainAdmin(admin.ModelAdmin):
    """Admin interface for HabitChain model."""

    list_display = [
        "user",
        "chain_type",
        "date",
        "completed",
        "created_at",
    ]
    list_filter = ["chain_type", "completed", "date"]
    search_fields = ["user__email"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["user", "dream"]
