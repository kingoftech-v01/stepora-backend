"""
Serializers for Users app.
"""

from rest_framework import serializers
from core.sanitizers import sanitize_text, sanitize_url, sanitize_json_values
from core.validators import validate_display_name, validate_location
from .models import User, GamificationProfile


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""

    can_create_dream = serializers.BooleanField(read_only=True)
    is_premium = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'display_name', 'avatar_url', 'avatar_image',
            'bio', 'location', 'social_links', 'profile_visibility',
            'timezone', 'subscription', 'subscription_ends',
            'work_schedule', 'notification_prefs', 'app_prefs',
            'xp', 'level', 'streak_days', 'last_activity',
            'can_create_dream', 'is_premium',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'email', 'xp', 'level', 'streak_days', 'last_activity', 'created_at', 'updated_at']

    def get_is_premium(self, obj):
        return obj.is_premium()


class UserProfileSerializer(serializers.ModelSerializer):
    """Detailed user profile serializer."""

    is_premium = serializers.SerializerMethodField()
    active_dreams_count = serializers.SerializerMethodField()
    completed_dreams_count = serializers.SerializerMethodField()
    achievements_summary = serializers.SerializerMethodField()
    equipped_items = serializers.SerializerMethodField()
    rank = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'display_name', 'avatar_url', 'avatar_image',
            'bio', 'location', 'social_links', 'profile_visibility',
            'timezone', 'subscription', 'subscription_ends',
            'xp', 'level', 'streak_days',
            'is_premium', 'active_dreams_count', 'completed_dreams_count',
            'achievements_summary', 'equipped_items', 'rank',
            'created_at'
        ]
        read_only_fields = fields

    def get_is_premium(self, obj):
        return obj.is_premium()

    def get_active_dreams_count(self, obj):
        return obj.dreams.filter(status='active').count()

    def get_completed_dreams_count(self, obj):
        return obj.dreams.filter(status='completed').count()

    def get_achievements_summary(self, obj):
        """Return achievements summary for profile display."""
        try:
            from .models import Achievement, UserAchievement
            total = Achievement.objects.filter(is_active=True).count()
            user_achievements = UserAchievement.objects.filter(
                user=obj
            ).select_related('achievement').order_by('-unlocked_at')
            unlocked = user_achievements.count()
            recent = [
                {
                    'name': ua.achievement.name,
                    'icon': ua.achievement.icon,
                    'unlocked_at': ua.unlocked_at,
                }
                for ua in user_achievements[:5]
            ]
            return {'unlocked': unlocked, 'total': total, 'recent': recent}
        except Exception:
            return {'unlocked': 0, 'total': 0, 'recent': []}

    def get_equipped_items(self, obj):
        """Return list of equipped store items."""
        try:
            from apps.store.models import UserInventory
            equipped = UserInventory.objects.filter(
                user=obj, is_equipped=True
            ).select_related('item')
            return [
                {
                    'item_type': inv.item.item_type,
                    'name': inv.item.name,
                    'slug': inv.item.slug,
                    'rarity': inv.item.rarity,
                    'image_url': inv.item.image_url,
                }
                for inv in equipped
            ]
        except Exception:
            return []

    def get_rank(self, obj):
        """Return user's current season rank."""
        try:
            from apps.leagues.models import LeagueStanding, Season
            season = Season.get_active_season()
            if not season:
                return None
            standing = LeagueStanding.objects.filter(
                user=obj, season=season
            ).select_related('league').first()
            if not standing:
                return None
            return {
                'rank': standing.rank,
                'league_name': standing.league.name,
                'league_tier': standing.league.tier,
                'xp_this_season': standing.xp_earned_this_season,
            }
        except Exception:
            return None


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""

    class Meta:
        model = User
        fields = [
            'display_name', 'avatar_url', 'bio', 'location',
            'social_links', 'profile_visibility', 'timezone',
            'work_schedule', 'notification_prefs', 'app_prefs'
        ]

    def validate_display_name(self, value):
        """Sanitize and validate display name."""
        return validate_display_name(value)

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


class GamificationProfileSerializer(serializers.ModelSerializer):
    """Serializer for Gamification profile."""

    health_level = serializers.SerializerMethodField()
    career_level = serializers.SerializerMethodField()
    relationships_level = serializers.SerializerMethodField()
    personal_growth_level = serializers.SerializerMethodField()
    finance_level = serializers.SerializerMethodField()
    hobbies_level = serializers.SerializerMethodField()
    skill_radar = serializers.SerializerMethodField()

    class Meta:
        model = GamificationProfile
        fields = [
            'id', 'health_xp', 'career_xp', 'relationships_xp',
            'personal_growth_xp', 'finance_xp', 'hobbies_xp',
            'health_level', 'career_level', 'relationships_level',
            'personal_growth_level', 'finance_level', 'hobbies_level',
            'skill_radar',
            'badges', 'achievements', 'streak_jokers'
        ]
        read_only_fields = ['id', 'badges', 'achievements']

    def get_health_level(self, obj):
        return obj.get_attribute_level('health')

    def get_career_level(self, obj):
        return obj.get_attribute_level('career')

    def get_relationships_level(self, obj):
        return obj.get_attribute_level('relationships')

    def get_personal_growth_level(self, obj):
        return obj.get_attribute_level('personal_growth')

    def get_finance_level(self, obj):
        return obj.get_attribute_level('finance')

    def get_hobbies_level(self, obj):
        return obj.get_attribute_level('hobbies')

    def get_skill_radar(self, obj):
        """Return skill radar data for all 6 categories."""
        categories = [
            {'category': 'health', 'label': 'Health', 'icon': 'heart'},
            {'category': 'career', 'label': 'Career', 'icon': 'briefcase'},
            {'category': 'relationships', 'label': 'Relationships', 'icon': 'users'},
            {'category': 'personal_growth', 'label': 'Personal Growth', 'icon': 'brain'},
            {'category': 'finance', 'label': 'Finance', 'icon': 'wallet'},
            {'category': 'hobbies', 'label': 'Hobbies', 'icon': 'palette'},
        ]
        return [
            {
                **cat,
                'xp': getattr(obj, f"{cat['category']}_xp", 0),
                'level': obj.get_attribute_level(cat['category']),
            }
            for cat in categories
        ]


