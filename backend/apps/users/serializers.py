"""
Serializers for Users app.
"""

from rest_framework import serializers
from core.sanitizers import sanitize_text, sanitize_url
from .models import User, FcmToken, GamificationProfile


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

    class Meta:
        model = User
        fields = [
            'id', 'email', 'display_name', 'avatar_url', 'avatar_image',
            'bio', 'location', 'social_links', 'profile_visibility',
            'timezone', 'subscription', 'subscription_ends',
            'xp', 'level', 'streak_days',
            'is_premium', 'active_dreams_count', 'completed_dreams_count',
            'created_at'
        ]
        read_only_fields = fields

    def get_is_premium(self, obj):
        return obj.is_premium()

    def get_active_dreams_count(self, obj):
        return obj.dreams.filter(status='active').count()

    def get_completed_dreams_count(self, obj):
        return obj.dreams.filter(status='completed').count()


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
        """Sanitize display name to prevent XSS."""
        return sanitize_text(value)

    def validate_avatar_url(self, value):
        """Sanitize avatar URL to prevent XSS."""
        return sanitize_url(value)


class FcmTokenSerializer(serializers.ModelSerializer):
    """Serializer for FCM tokens."""

    class Meta:
        model = FcmToken
        fields = ['id', 'token', 'platform', 'is_active', 'created_at']
        read_only_fields = ['id', 'is_active', 'created_at']


class GamificationProfileSerializer(serializers.ModelSerializer):
    """Serializer for Gamification profile."""

    health_level = serializers.SerializerMethodField()
    career_level = serializers.SerializerMethodField()
    relationships_level = serializers.SerializerMethodField()
    personal_growth_level = serializers.SerializerMethodField()

    class Meta:
        model = GamificationProfile
        fields = [
            'id', 'health_xp', 'career_xp', 'relationships_xp',
            'personal_growth_xp', 'finance_xp', 'hobbies_xp',
            'health_level', 'career_level', 'relationships_level', 'personal_growth_level',
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


