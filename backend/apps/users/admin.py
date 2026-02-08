"""
Django admin configuration for Users app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, FcmToken, GamificationProfile, DreamBuddy


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model."""

    list_display = ['email', 'display_name', 'subscription', 'level', 'xp', 'streak_days', 'is_staff', 'created_at']
    list_filter = ['subscription', 'is_staff', 'is_active', 'created_at']
    search_fields = ['email', 'display_name']
    ordering = ['-created_at']

    fieldsets = (
        (None, {'fields': ('email', 'display_name', 'avatar_url')}),
        ('Subscription', {'fields': ('subscription', 'subscription_ends')}),
        ('Preferences', {'fields': ('timezone', 'work_schedule', 'notification_prefs', 'app_prefs')}),
        ('Gamification', {'fields': ('xp', 'level', 'streak_days', 'last_activity')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('created_at', 'updated_at')}),
    )

    readonly_fields = ['created_at', 'updated_at', 'last_activity']

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'display_name', 'subscription'),
        }),
    )


@admin.register(FcmToken)
class FcmTokenAdmin(admin.ModelAdmin):
    """Admin interface for FCM tokens."""

    list_display = ['user', 'platform', 'is_active', 'created_at']
    list_filter = ['platform', 'is_active', 'created_at']
    search_fields = ['user__email', 'token']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(GamificationProfile)
class GamificationProfileAdmin(admin.ModelAdmin):
    """Admin interface for Gamification profiles."""

    list_display = ['user', 'health_level', 'career_level', 'relationships_level', 'streak_jokers']
    list_filter = ['created_at']
    search_fields = ['user__email']
    readonly_fields = ['created_at', 'updated_at']

    def health_level(self, obj):
        return obj.get_attribute_level('health')

    def career_level(self, obj):
        return obj.get_attribute_level('career')

    def relationships_level(self, obj):
        return obj.get_attribute_level('relationships')


@admin.register(DreamBuddy)
class DreamBuddyAdmin(admin.ModelAdmin):
    """Admin interface for Dream Buddy pairings."""

    list_display = ['user1', 'user2', 'status', 'compatibility_score', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user1__email', 'user2__email']
    readonly_fields = ['created_at', 'updated_at']
