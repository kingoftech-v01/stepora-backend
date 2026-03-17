"""
Serializers for Notifications app.
"""

from django.utils.translation import gettext as _
from rest_framework import serializers

from core.sanitizers import sanitize_text

from .models import (
    Notification,
    NotificationBatch,
    NotificationTemplate,
    ReminderPreference,
    UserDevice,
    WebPushSubscription,
)


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model."""

    is_read = serializers.SerializerMethodField(
        help_text="Whether the notification has been read."
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "user",
            "notification_type",
            "title",
            "body",
            "data",
            "scheduled_for",
            "sent_at",
            "read_at",
            "status",
            "is_read",
            "created_at",
        ]
        read_only_fields = ["id", "user", "sent_at", "read_at", "status", "created_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the notification."},
            "user": {"help_text": "User who receives this notification."},
            "notification_type": {"help_text": "Category of the notification."},
            "title": {"help_text": "Title displayed in the notification."},
            "body": {"help_text": "Body text of the notification."},
            "data": {"help_text": "Additional payload data for the notification."},
            "scheduled_for": {
                "help_text": "Scheduled delivery time for the notification."
            },
            "sent_at": {"help_text": "Timestamp when the notification was sent."},
            "read_at": {"help_text": "Timestamp when the notification was read."},
            "status": {"help_text": "Current delivery status of the notification."},
            "created_at": {"help_text": "Timestamp when the notification was created."},
        }

    def get_is_read(self, obj) -> bool:
        return obj.read_at is not None


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notifications."""

    class Meta:
        model = Notification
        fields = ["notification_type", "title", "body", "data", "scheduled_for"]
        extra_kwargs = {
            "notification_type": {
                "help_text": "Category of the notification to create."
            },
            "title": {"help_text": "Title to display in the notification."},
            "body": {"help_text": "Body text of the notification."},
            "data": {"help_text": "Additional payload data for the notification."},
            "scheduled_for": {
                "help_text": "Optional future time to deliver the notification."
            },
        }

    def validate_title(self, value):
        """Sanitize title to prevent XSS."""
        return sanitize_text(value)

    def validate_body(self, value):
        """Sanitize body to prevent XSS."""
        return sanitize_text(value)


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """Serializer for Notification templates."""

    class Meta:
        model = NotificationTemplate
        fields = [
            "id",
            "name",
            "notification_type",
            "title_template",
            "body_template",
            "available_variables",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the template."},
            "name": {"help_text": "Internal name of the notification template."},
            "notification_type": {
                "help_text": "Type of notification this template generates."
            },
            "title_template": {
                "help_text": "Template string for the notification title."
            },
            "body_template": {
                "help_text": "Template string for the notification body."
            },
            "available_variables": {
                "help_text": "Variables that can be used in the template."
            },
            "is_active": {"help_text": "Whether this template is currently in use."},
            "created_at": {"help_text": "Timestamp when the template was created."},
            "updated_at": {
                "help_text": "Timestamp when the template was last updated."
            },
        }


class NotificationBatchSerializer(serializers.ModelSerializer):
    """Serializer for Notification batches."""

    success_rate = serializers.SerializerMethodField(
        help_text="Percentage of notifications successfully sent."
    )

    class Meta:
        model = NotificationBatch
        fields = [
            "id",
            "name",
            "notification_type",
            "total_scheduled",
            "total_sent",
            "total_failed",
            "status",
            "success_rate",
            "created_at",
            "completed_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the batch."},
            "name": {"help_text": "Name of the notification batch."},
            "notification_type": {"help_text": "Type of notifications in this batch."},
            "total_scheduled": {
                "help_text": "Total notifications scheduled in the batch."
            },
            "total_sent": {"help_text": "Total notifications successfully sent."},
            "total_failed": {"help_text": "Total notifications that failed to send."},
            "status": {"help_text": "Current processing status of the batch."},
            "created_at": {"help_text": "Timestamp when the batch was created."},
            "completed_at": {
                "help_text": "Timestamp when the batch finished processing."
            },
        }

    def get_success_rate(self, obj) -> float:
        if obj.total_scheduled == 0:
            return 0.0
        return round((obj.total_sent / obj.total_scheduled) * 100, 2)


class WebPushSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Web Push subscriptions."""

    class Meta:
        model = WebPushSubscription
        fields = ["id", "subscription_info", "browser", "is_active", "created_at"]
        read_only_fields = ["id", "is_active", "created_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the subscription."},
            "subscription_info": {
                "help_text": "Web Push subscription endpoint and keys."
            },
            "browser": {"help_text": "Browser used for this push subscription."},
            "is_active": {
                "help_text": "Whether this subscription is currently active."
            },
            "created_at": {"help_text": "Timestamp when the subscription was created."},
        }


class UserDeviceSerializer(serializers.ModelSerializer):
    """Serializer for FCM device registration."""

    class Meta:
        model = UserDevice
        fields = [
            "id",
            "fcm_token",
            "platform",
            "device_name",
            "app_version",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_active", "created_at", "updated_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for this device registration."},
            "fcm_token": {
                "help_text": "Firebase Cloud Messaging token for this device."
            },
            "platform": {"help_text": "Device platform: android, ios, or web."},
            "device_name": {"help_text": "Optional human-readable device name."},
            "app_version": {"help_text": "App version at time of registration."},
            "is_active": {"help_text": "Whether this device registration is active."},
            "created_at": {"help_text": "When this device was first registered."},
            "updated_at": {
                "help_text": "When this device registration was last updated."
            },
        }

    def validate_fcm_token(self, value):
        """Validate FCM token is not empty and has reasonable length."""
        if not value or len(value) < 20:
            raise serializers.ValidationError(_("Invalid FCM token."))
        if len(value) > 4096:
            raise serializers.ValidationError(_("FCM token exceeds maximum length."))
        return value


class ReminderPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for ReminderPreference model."""

    dream_title = serializers.SerializerMethodField(
        help_text="Title of the associated dream (if any)."
    )

    class Meta:
        model = ReminderPreference
        fields = [
            "id",
            "user",
            "dream",
            "dream_title",
            "reminder_type",
            "time",
            "days",
            "is_active",
            "notify_method",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "dream_title", "created_at", "updated_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the reminder preference."},
            "user": {"help_text": "Owner of this reminder preference."},
            "dream": {
                "help_text": "Associated dream (null for global reminder).",
                "required": False,
                "allow_null": True,
            },
            "reminder_type": {
                "help_text": "Preset type: morning, afternoon, evening, or custom."
            },
            "time": {"help_text": "Time of day to send the reminder (HH:MM format)."},
            "days": {
                "help_text": "Comma-separated day abbreviations: mon,tue,wed,thu,fri,sat,sun"
            },
            "is_active": {"help_text": "Whether this reminder is currently active."},
            "notify_method": {
                "help_text": "Delivery method: push, task_call, or both."
            },
        }

    def get_dream_title(self, obj) -> str:
        if obj.dream:
            try:
                return obj.dream.title
            except Exception:
                return ""
        return ""

    def validate_days(self, value):
        """Validate days string contains only valid day abbreviations."""
        valid_days = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        days = [d.strip().lower() for d in value.split(",") if d.strip()]
        if not days:
            raise serializers.ValidationError(
                _("At least one day must be selected.")
            )
        invalid = set(days) - valid_days
        if invalid:
            raise serializers.ValidationError(
                _("Invalid day abbreviations: %(days)s") % {"days": ", ".join(invalid)}
            )
        return ",".join(days)

    def validate_dream(self, value):
        """Ensure the dream belongs to the requesting user."""
        if value is not None:
            request = self.context.get("request")
            if request and value.user != request.user:
                raise serializers.ValidationError(
                    _("You can only set reminders for your own dreams.")
                )
        return value

    def validate(self, attrs):
        """Check uniqueness of user + dream + time."""
        request = self.context.get("request")
        user = request.user if request else None
        dream = attrs.get("dream")
        time = attrs.get("time")

        if user and time:
            qs = ReminderPreference.objects.filter(
                user=user, dream=dream, time=time
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    _("A reminder at this time already exists for this dream.")
                )
        return attrs


class ReminderQuickSetupSerializer(serializers.Serializer):
    """Serializer for quick-setup endpoint (preset-based creation)."""

    PRESET_CHOICES = [
        ("morning", "Morning"),
        ("afternoon", "Afternoon"),
        ("evening", "Evening"),
    ]
    preset = serializers.ChoiceField(
        choices=PRESET_CHOICES,
        help_text="Preset to apply: morning (08:00), afternoon (13:00), evening (19:00).",
    )
    dream = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional dream ID to associate the reminder with.",
    )
    notify_method = serializers.ChoiceField(
        choices=ReminderPreference.NOTIFY_CHOICES,
        default="push",
        help_text="Delivery method: push, task_call, or both.",
    )
    days = serializers.CharField(
        default="mon,tue,wed,thu,fri,sat,sun",
        help_text="Comma-separated day abbreviations.",
    )
