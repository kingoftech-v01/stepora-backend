"""
Django admin configuration for Friends app.
"""

from django.contrib import admin

from .models import BlockedUser, Friendship, ReportedUser, UserFollow


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ["user1", "user2", "status", "created_at", "updated_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["user1__email", "user2__email"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["user1", "user2"]


@admin.register(UserFollow)
class UserFollowAdmin(admin.ModelAdmin):
    list_display = ["follower", "following", "created_at"]
    search_fields = ["follower__email", "following__email"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["follower", "following"]


@admin.register(BlockedUser)
class BlockedUserAdmin(admin.ModelAdmin):
    list_display = ["blocker", "blocked", "created_at"]
    search_fields = ["blocker__email", "blocked__email"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["blocker", "blocked"]


@admin.register(ReportedUser)
class ReportedUserAdmin(admin.ModelAdmin):
    list_display = ["reporter", "reported", "category", "status", "created_at"]
    list_filter = ["category", "status", "created_at"]
    search_fields = ["reporter__email", "reported__email"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["reporter", "reported"]
