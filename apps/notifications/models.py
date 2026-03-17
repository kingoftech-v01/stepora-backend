"""
Notification models for push notifications and reminders.
"""

import uuid
import zoneinfo

from django.db import models
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField

from apps.users.models import User


class Notification(models.Model):
    """Push notification model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )

    TYPE_CHOICES = [
        ("reminder", "Reminder"),
        ("motivation", "Motivation"),
        ("progress", "Progress"),
        ("achievement", "Achievement"),
        ("check_in", "Check In"),
        ("rescue", "Rescue"),
        ("buddy", "Buddy"),
        ("missed_call", "Missed Call"),
        ("system", "System"),
        ("dream_completed", "Dream Completed"),
        ("weekly_report", "Weekly Report"),
        ("daily_summary", "Daily Summary"),
        ("task_due", "Task Due"),
        ("task_call", "Task Call"),
    ]
    notification_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, db_index=True
    )

    title = EncryptedCharField(
        max_length=255, help_text="Notification title (encrypted at rest)."
    )
    body = EncryptedTextField(help_text="Notification body (encrypted at rest).")

    # Additional data for deep linking
    data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional data: {screen: "", dreamId: "", goalId: "", taskId: ""}',
    )

    # Scheduling
    scheduled_for = models.DateTimeField(db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the user opened/interacted with this notification.",
    )
    image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Optional image URL for rich notifications.",
    )
    action_url = models.CharField(
        max_length=500,
        blank=True,
        help_text="Deep link URL for the notification action.",
    )

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )

    # Retry logic
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-scheduled_for"]
        indexes = [
            models.Index(fields=["user", "-scheduled_for"]),
            models.Index(fields=["status", "scheduled_for"]),
            models.Index(fields=["notification_type"]),
        ]

    def __str__(self):
        return f"{self.notification_type}: {self.title} ({self.status})"

    def mark_sent(self):
        """Mark notification as sent."""
        self.status = "sent"
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at"])

    def mark_read(self):
        """Mark notification as read by user."""
        self.read_at = timezone.now()
        self.save(update_fields=["read_at"])

    def mark_opened(self):
        """Mark notification as opened/interacted with."""
        self.opened_at = timezone.now()
        if not self.read_at:
            self.read_at = self.opened_at
        self.save(update_fields=["opened_at", "read_at"])

    def mark_failed(self, error_message=""):
        """Mark notification as failed."""
        self.status = "failed"
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=["status", "error_message", "retry_count"])

    def should_send(self):
        """Check if notification should be sent now."""
        if self.status != "pending":
            return False

        now = timezone.now()
        if self.scheduled_for > now:
            return False

        # Check DND (do not disturb)
        if self.user.notification_prefs:
            dnd_enabled = self.user.notification_prefs.get("dndEnabled", False)
            if dnd_enabled:
                user_tz = zoneinfo.ZoneInfo(self.user.timezone)
                user_time = now.astimezone(user_tz)
                hour = user_time.hour

                dnd_start = self.user.notification_prefs.get("dndStart", 22)
                dnd_end = self.user.notification_prefs.get("dndEnd", 7)

                # Check if in DND period
                if dnd_start > dnd_end:  # DND crosses midnight
                    if hour >= dnd_start or hour < dnd_end:
                        return False
                else:
                    if dnd_start <= hour < dnd_end:
                        return False

        return True


class NotificationTemplate(models.Model):
    """Template for notification messages."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=100, unique=True)
    notification_type = models.CharField(max_length=20)

    title_template = models.CharField(max_length=255)
    body_template = models.TextField()

    # Variables that can be used in templates
    available_variables = models.JSONField(
        default=list,
        help_text='List of variables that can be used: ["user_name", "dream_title", etc.]',
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_templates"

    def __str__(self):
        return f"Template: {self.name}"

    def render(self, **variables):
        """Render template with provided variables."""
        title = self.title_template
        body = self.body_template

        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            title = title.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))

        return title, body


class WebPushSubscription(models.Model):
    """Browser Web Push subscription (VAPID)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="webpush_subscriptions"
    )
    subscription_info = models.JSONField(
        help_text="Web Push subscription: {endpoint, keys: {p256dh, auth}}"
    )
    browser = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "webpush_subscriptions"
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"WebPush - {self.user.email} ({self.browser or 'unknown'})"


class UserDevice(models.Model):
    """FCM device registration for push notifications."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")

    fcm_token = models.TextField(
        unique=True,
        help_text="Firebase Cloud Messaging registration token for this device.",
    )

    PLATFORM_CHOICES = [
        ("android", "Android"),
        ("ios", "iOS"),
        ("web", "Web"),
    ]
    platform = models.CharField(
        max_length=10,
        choices=PLATFORM_CHOICES,
        help_text="Device platform (android, ios, web).",
    )

    device_name = EncryptedCharField(
        max_length=255,
        blank=True,
        help_text="Human-readable device name (encrypted at rest).",
    )
    app_version = models.CharField(
        max_length=50,
        blank=True,
        help_text="App version string at time of registration.",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Set to False when token is known invalid or user logs out.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_devices"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["platform"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.platform} ({'active' if self.is_active else 'inactive'})"


class ReminderPreference(models.Model):
    """User's preferred reminder times for task notifications."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="reminder_preferences"
    )
    dream = models.ForeignKey(
        "dreams.Dream",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reminder_preferences",
        help_text="If null, this is a global preference (applies to all dreams).",
    )

    REMINDER_TYPE_CHOICES = [
        ("morning", "Morning"),
        ("afternoon", "Afternoon"),
        ("evening", "Evening"),
        ("custom", "Custom"),
    ]
    reminder_type = models.CharField(
        max_length=20, choices=REMINDER_TYPE_CHOICES, default="morning"
    )
    time = models.TimeField(help_text="The actual time to send the reminder (user local time).")

    # Days of week (stored as comma-separated: "mon,tue,wed,thu,fri,sat,sun")
    days = models.CharField(
        max_length=50,
        default="mon,tue,wed,thu,fri,sat,sun",
        help_text="Comma-separated day abbreviations: mon,tue,wed,thu,fri,sat,sun",
    )

    is_active = models.BooleanField(default=True)

    # Notification method
    NOTIFY_CHOICES = [
        ("push", "Push Notification"),
        ("task_call", "Task Call (in-app call screen)"),
        ("both", "Both"),
    ]
    notify_method = models.CharField(
        max_length=20,
        choices=NOTIFY_CHOICES,
        default="push",
        help_text="How to deliver the reminder: push, task_call, or both.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reminder_preferences"
        ordering = ["time"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "dream", "time"],
                name="unique_user_dream_time",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["is_active", "time"]),
        ]

    def __str__(self):
        dream_label = f" (dream: {self.dream_id})" if self.dream_id else " (global)"
        return f"{self.user.email} - {self.time}{dream_label}"

    def get_days_list(self):
        """Return days as a list: ['mon', 'tue', ...]."""
        return [d.strip().lower() for d in self.days.split(",") if d.strip()]

    def matches_day(self, day_abbr):
        """Check if reminder is active for the given day abbreviation."""
        return day_abbr.lower() in self.get_days_list()


class NotificationBatch(models.Model):
    """Batch of notifications sent together."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)
    notification_type = models.CharField(max_length=20)

    # Stats
    total_scheduled = models.IntegerField(default=0)
    total_sent = models.IntegerField(default=0)
    total_failed = models.IntegerField(default=0)

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="scheduled"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notification_batches"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Batch: {self.name} ({self.total_sent}/{self.total_scheduled} sent)"
