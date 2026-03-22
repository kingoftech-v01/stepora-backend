"""
Calendar models for scheduling and time management.
"""

import uuid

from django.db import models
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField

from django.conf import settings


class CalendarEvent(models.Model):
    """Calendar event for task scheduling."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calendar_events"
    )
    task = models.ForeignKey(
        "plans.Task",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="calendar_events",
    )

    title = EncryptedCharField(max_length=255)
    description = EncryptedTextField(blank=True, default="")

    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField()

    # All-day / multi-day events
    all_day = models.BooleanField(
        default=False, help_text="Whether this is an all-day event."
    )

    # Per-event timezone override (display only; times stored in UTC)
    event_timezone = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Optional timezone override for this event (e.g. America/New_York). Empty = use user home timezone.",
    )

    # Location/context
    location = EncryptedCharField(max_length=255, blank=True)

    # Reminder (legacy single-value field kept for backward compatibility)
    reminder_minutes_before = models.IntegerField(default=15)

    # Multiple reminders: [{minutes_before: 15, type: "push"}, {minutes_before: 60, type: "push"}]
    reminders = models.JSONField(
        default=list,
        blank=True,
        help_text='List of reminders: [{minutes_before: int, type: "push"|"email"}]',
    )

    # Tracks which reminders have already been sent to avoid duplicates
    # Stored as list of strings: ["<minutes_before>_<scheduled_iso>"]
    reminders_sent = models.JSONField(
        default=list,
        blank=True,
        help_text='List of reminder keys already sent, e.g. ["15_2026-03-04T10:00:00"]',
    )

    # Snooze support: when set, in-app notifications are suppressed until this time
    snoozed_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="If set, suppress in-app notification popups until this datetime.",
    )

    # Category
    CATEGORY_CHOICES = [
        ("meeting", "Meeting"),
        ("deadline", "Deadline"),
        ("milestone", "Milestone"),
        ("habit", "Habit"),
        ("social", "Social"),
        ("health", "Health"),
        ("learning", "Learning"),
        ("custom", "Custom"),
    ]
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="custom",
        db_index=True,
        help_text="Event category for visual grouping and filtering.",
    )

    # Status
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("rescheduled", "Rescheduled"),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="scheduled"
    )

    # Recurring events
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            'Recurrence rule: {frequency: "daily|weekly|monthly|yearly|custom", '
            "interval: int, days_of_week: [0-6], day_of_month: int, "
            'week_of_month: int, day_of_week: int, end_date: "ISO"|null, '
            "end_after_count: int|null, weekdays_only: bool}"
        ),
    )
    parent_event = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="recurring_instances",
        help_text="Parent event if this is a recurring instance.",
    )

    # Google Calendar sync
    google_event_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="Google Calendar event ID for bidirectional sync.",
    )

    SYNC_STATUS_CHOICES = [
        ("local", "Local only"),
        ("synced", "Synced"),
        ("pending", "Pending sync"),
        ("error", "Sync error"),
    ]
    sync_status = models.CharField(
        max_length=10,
        choices=SYNC_STATUS_CHOICES,
        default="local",
        db_index=True,
        help_text="Google Calendar sync status for this event.",
    )
    last_sync_error = models.TextField(
        blank=True,
        default="",
        help_text="Last sync error message, if any.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "calendar_events"
        ordering = ["start_time"]
        indexes = [
            models.Index(fields=["user", "start_time"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.title} at {self.start_time}"


class TimeBlock(models.Model):
    """User-defined time blocks for scheduling preferences."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="time_blocks")

    title = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Optional user-facing label for this time block.",
    )

    BLOCK_TYPE_CHOICES = [
        ("work", "Work"),
        ("personal", "Personal"),
        ("family", "Family"),
        ("exercise", "Exercise"),
        ("blocked", "Blocked"),
    ]
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPE_CHOICES, default="personal")

    # Recurring schedule
    day_of_week = models.IntegerField(help_text="0=Monday, 6=Sunday")
    start_time = models.TimeField()
    end_time = models.TimeField()

    color = models.CharField(
        max_length=7,
        blank=True,
        default="#8B5CF6",
        help_text="Hex color code for the time block.",
    )
    dream = models.ForeignKey(
        "dreams.Dream",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="time_blocks",
        help_text="Optional associated dream.",
    )

    is_active = models.BooleanField(default=True)

    # Focus/DND mode — marks this block as a focus block that suppresses notifications
    focus_block = models.BooleanField(
        default=False,
        help_text="Whether this time block is a focus/DND block that suppresses notifications.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "time_blocks"
        ordering = ["day_of_week", "start_time"]
        indexes = [
            models.Index(fields=["user", "day_of_week", "is_active"]),
            models.Index(fields=["user", "focus_block", "is_active"]),
        ]

    def __str__(self):
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        label = " [FOCUS]" if self.focus_block else ""
        return f"{days[self.day_of_week]} {self.start_time}-{self.end_time}: {self.block_type}{label}"


class TimeBlockTemplate(models.Model):
    """Saved weekly time block patterns that users can apply to their schedule."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="timeblock_templates"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    blocks = models.JSONField(
        help_text="Array of {block_type, day_of_week, start_time, end_time}"
    )
    is_preset = models.BooleanField(
        default=False, help_text="System-provided preset template"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "timeblock_templates"
        ordering = ["-is_preset", "-created_at"]

    def __str__(self):
        return f"{self.name} ({'preset' if self.is_preset else self.user.email})"


class GoogleCalendarIntegration(models.Model):
    """Stores Google Calendar OAuth2 credentials for bidirectional sync."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="google_calendar"
    )
    access_token = EncryptedTextField()
    refresh_token = EncryptedTextField()
    token_expiry = models.DateTimeField()
    calendar_id = models.CharField(
        max_length=255, default="primary", help_text="Google Calendar ID to sync with."
    )
    sync_enabled = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    sync_token = models.CharField(
        max_length=500, blank=True, help_text="Google incremental sync token."
    )

    # Selective sync settings
    synced_dream_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of dream UUIDs to sync. Empty = sync all.",
    )
    SYNC_DIRECTION_CHOICES = [
        ("both", "Both ways"),
        ("push_only", "Push only"),
        ("pull_only", "Pull only"),
    ]
    sync_direction = models.CharField(
        max_length=10,
        choices=SYNC_DIRECTION_CHOICES,
        default="both",
        help_text="Direction of sync with Google Calendar.",
    )
    sync_tasks = models.BooleanField(
        default=True,
        help_text="Whether to sync dream tasks as calendar events.",
    )
    sync_events = models.BooleanField(
        default=True,
        help_text="Whether to sync standalone calendar events.",
    )

    ical_feed_token = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        help_text="Secret token for iCal feed URL.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "google_calendar_integrations"

    def __str__(self):
        return f"Google Calendar: {self.user.email} ({self.calendar_id})"

    def save(self, *args, **kwargs):
        if not self.ical_feed_token:
            import secrets

            self.ical_feed_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)


class RecurrenceException(models.Model):
    """Exception (skip or modify) for a single occurrence of a recurring event."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent_event = models.ForeignKey(
        CalendarEvent,
        on_delete=models.CASCADE,
        related_name="exceptions",
        help_text="The recurring parent event this exception belongs to.",
    )
    original_date = models.DateField(
        help_text="The original occurrence date being modified or skipped."
    )
    # If skip_occurrence is True, this date is excluded from the recurrence
    skip_occurrence = models.BooleanField(
        default=False,
        help_text="If True, the occurrence on original_date is skipped entirely.",
    )
    # If not skipping, these fields hold the modified values
    modified_title = EncryptedCharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Modified title for this occurrence (blank = use parent title).",
    )
    modified_start_time = models.DateTimeField(
        null=True, blank=True, help_text="Modified start time for this occurrence."
    )
    modified_end_time = models.DateTimeField(
        null=True, blank=True, help_text="Modified end time for this occurrence."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recurrence_exceptions"
        ordering = ["original_date"]
        unique_together = [("parent_event", "original_date")]
        indexes = [
            models.Index(fields=["parent_event", "original_date"]),
        ]

    def __str__(self):
        action = "Skip" if self.skip_occurrence else "Modify"
        return f"{action} {self.parent_event.title} on {self.original_date}"


class CalendarShare(models.Model):
    """
    Represents a calendar sharing relationship between two users.

    Allows a user (owner) to share their calendar schedule with another user
    (shared_with). Supports view-only and suggest-times permission levels.
    A unique share_token enables link-based sharing without requiring the
    recipient to be a registered buddy.
    """

    PERMISSION_CHOICES = [
        ("view", "View Only"),
        ("suggest", "Can Suggest Times"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shared_calendars",
        help_text="The user who owns the calendar being shared.",
    )
    shared_with = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="calendars_shared_with_me",
        help_text="The user the calendar is shared with. Null for link-only shares.",
    )
    permission = models.CharField(
        max_length=10,
        choices=PERMISSION_CHOICES,
        default="view",
        help_text="Permission level: view only or can suggest times.",
    )
    share_token = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        help_text="Unique token for link-based calendar sharing.",
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this share is currently active."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "calendar_shares"
        ordering = ["-created_at"]
        verbose_name = "Calendar Share"
        verbose_name_plural = "Calendar Shares"
        unique_together = [("owner", "shared_with")]
        indexes = [
            models.Index(
                fields=["owner", "is_active"], name="idx_calshare_owner_active"
            ),
            models.Index(
                fields=["shared_with", "is_active"], name="idx_calshare_shared_active"
            ),
            models.Index(fields=["share_token"], name="idx_calshare_token"),
        ]

    def __str__(self):
        target = (
            self.shared_with.email
            if self.shared_with
            else f"link:{self.share_token[:8]}"
        )
        return f"Calendar share: {self.owner.email} -> {target} ({self.permission})"

    def save(self, *args, **kwargs):
        if not self.share_token:
            import secrets

            self.share_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)


class Habit(models.Model):
    """Trackable habit integrated with the calendar system."""

    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekdays", "Weekdays"),
        ("weekly", "Weekly"),
        ("custom", "Custom"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="habits")
    name = EncryptedCharField(max_length=100)
    description = EncryptedTextField(blank=True, default="")
    frequency = models.CharField(
        max_length=10, choices=FREQUENCY_CHOICES, default="daily"
    )
    custom_days = models.JSONField(
        default=list,
        blank=True,
        help_text="List of day numbers 0-6 (Mon-Sun) for custom frequency.",
    )
    target_per_day = models.IntegerField(
        default=1, help_text="How many times per day to complete the habit."
    )
    color = models.CharField(
        max_length=7, default="#8B5CF6", help_text="Hex color code for the habit."
    )
    icon = models.CharField(
        max_length=50, default="star", help_text="Lucide icon name for the habit."
    )
    is_active = models.BooleanField(default=True)
    streak_current = models.IntegerField(default=0)
    streak_best = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "habits"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.icon} {self.name} ({self.frequency})"


class HabitCompletion(models.Model):
    """Records a single completion of a habit on a specific date."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    habit = models.ForeignKey(
        Habit, on_delete=models.CASCADE, related_name="completions"
    )
    completed_at = models.DateTimeField(auto_now_add=True)
    date = models.DateField(db_index=True)
    count = models.IntegerField(
        default=1, help_text="Number of completions for this date."
    )
    note = EncryptedTextField(blank=True, default="")

    class Meta:
        db_table = "habit_completions"
        ordering = ["-date"]
        unique_together = [("habit", "date")]
        indexes = [
            models.Index(fields=["habit", "date"]),
        ]

    def __str__(self):
        return f"{self.habit.name} - {self.date} (x{self.count})"
