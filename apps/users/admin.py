"""
Django admin configuration for Users app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.subscriptions.models import Subscription, SubscriptionPlan

from .models import (
    EmailChangeRequest,
    User,
)


class SubscriptionInline(admin.StackedInline):
    """Inline editor for the user's Subscription (the real source of truth)."""

    model = Subscription
    extra = 0
    max_num = 1
    fields = [
        "plan",
        "status",
        "current_period_start",
        "current_period_end",
        "cancel_at_period_end",
        "stripe_subscription_id",
    ]
    readonly_fields = ["stripe_subscription_id"]
    can_delete = False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("plan")


def _change_plan(modeladmin, request, queryset, slug):
    """Bulk-change plan for selected users via the Subscription table."""
    plan = SubscriptionPlan.objects.filter(slug=slug).first()
    if not plan:
        modeladmin.message_user(request, f'Plan "{slug}" not found.', level="error")
        return
    updated = 0
    for user in queryset:
        sub = Subscription.objects.filter(user=user).first()
        if sub:
            if sub.plan_id != plan.pk:
                sub.plan = plan
                sub.status = "active"
                sub.save(update_fields=["plan", "status"])
                updated += 1
        else:
            Subscription.objects.create(user=user, plan=plan, status="active")
            updated += 1
    modeladmin.message_user(request, f"{updated} user(s) changed to {plan.name}.")


@admin.action(description="Set plan → Free")
def set_plan_free(modeladmin, request, queryset):
    _change_plan(modeladmin, request, queryset, "free")


@admin.action(description="Set plan → Premium")
def set_plan_premium(modeladmin, request, queryset):
    _change_plan(modeladmin, request, queryset, "premium")


@admin.action(description="Set plan → Pro")
def set_plan_pro(modeladmin, request, queryset):
    _change_plan(modeladmin, request, queryset, "pro")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model."""

    list_display = [
        "email",
        "display_name",
        "subscription",
        "level",
        "xp",
        "streak_days",
        "is_staff",
        "created_at",
    ]
    list_filter = ["subscription", "is_staff", "is_active", "created_at"]
    search_fields = ["email", "display_name"]
    ordering = ["-created_at"]
    actions = [set_plan_free, set_plan_premium, set_plan_pro]
    inlines = [SubscriptionInline]

    fieldsets = (
        (None, {"fields": ("email", "display_name", "avatar_url")}),
        (
            "Subscription (read-only — edit via inline below)",
            {
                "fields": ("subscription", "subscription_ends"),
                "description": "This field is auto-synced from the Subscription table below. "
                "To change a user's plan, edit the Subscription inline or use the bulk action.",
            },
        ),
        (
            "Preferences",
            {
                "fields": (
                    "timezone",
                    "work_schedule",
                    "notification_prefs",
                    "app_prefs",
                )
            },
        ),
        ("Gamification", {"fields": ("xp", "level", "streak_days", "last_activity")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("created_at", "updated_at")}),
    )

    readonly_fields = [
        "created_at",
        "updated_at",
        "last_activity",
        "subscription",
        "subscription_ends",
    ]

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "display_name"),
            },
        ),
    )


@admin.register(EmailChangeRequest)
class EmailChangeRequestAdmin(admin.ModelAdmin):
    """Admin interface for email change requests."""

    list_display = ["user", "new_email", "is_verified", "expires_at", "created_at"]
    list_filter = ["is_verified", "created_at"]
    search_fields = ["user__email", "new_email"]
    readonly_fields = ["created_at", "token"]
    raw_id_fields = ["user"]



# Gamification admin classes moved to apps.gamification.admin
