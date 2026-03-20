"""
Django admin configuration for Referrals app.
"""

from django.contrib import admin

from .models import Referral, ReferralCode, ReferralReward


@admin.register(ReferralCode)
class ReferralCodeAdmin(admin.ModelAdmin):
    list_display = ["code", "user", "is_active", "times_used", "max_uses", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["code", "user__email"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["user"]


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ["referrer", "referred", "status", "created_at", "completed_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["referrer__email", "referred__email"]
    readonly_fields = ["created_at", "completed_at"]
    raw_id_fields = ["referrer", "referred", "referral_code"]


@admin.register(ReferralReward)
class ReferralRewardAdmin(admin.ModelAdmin):
    list_display = ["user", "reward_type", "reward_value", "is_claimed", "created_at"]
    list_filter = ["reward_type", "is_claimed", "created_at"]
    search_fields = ["user__email"]
    readonly_fields = ["created_at", "claimed_at"]
    raw_id_fields = ["user", "referral"]
