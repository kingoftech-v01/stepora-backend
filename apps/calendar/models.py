"""
Calendar models for scheduling and time management.
"""

import uuid
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField
from apps.users.models import User
from apps.dreams.models import Task


class CalendarEvent(models.Model):
    """Calendar event for task scheduling."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendar_events')
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='calendar_events'
    )

    title = EncryptedCharField(max_length=255)
    description = EncryptedTextField(blank=True, default='')

    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField()

    # Location/context
    location = EncryptedCharField(max_length=255, blank=True)

    # Reminder
    reminder_minutes_before = models.IntegerField(default=15)

    # Status
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

    # Recurring events
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.JSONField(
        null=True,
        blank=True,
        help_text='Recurrence rule: {frequency: "daily|weekly|monthly", interval: 1, end_date: "ISO"}'
    )
    parent_event = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='recurring_instances',
        help_text='Parent event if this is a recurring instance.'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'calendar_events'
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['user', 'start_time']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.title} at {self.start_time}"


class TimeBlock(models.Model):
    """User-defined time blocks for scheduling preferences."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_blocks')

    BLOCK_TYPE_CHOICES = [
        ('work', 'Work'),
        ('personal', 'Personal'),
        ('family', 'Family'),
        ('exercise', 'Exercise'),
        ('blocked', 'Blocked'),
    ]
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPE_CHOICES)

    # Recurring schedule
    day_of_week = models.IntegerField(help_text='0=Monday, 6=Sunday')
    start_time = models.TimeField()
    end_time = models.TimeField()

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'time_blocks'
        ordering = ['day_of_week', 'start_time']
        indexes = [
            models.Index(fields=['user', 'day_of_week', 'is_active']),
        ]

    def __str__(self):
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        return f"{days[self.day_of_week]} {self.start_time}-{self.end_time}: {self.block_type}"


class GoogleCalendarIntegration(models.Model):
    """Stores Google Calendar OAuth2 credentials for bidirectional sync."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='google_calendar')
    access_token = EncryptedTextField()
    refresh_token = EncryptedTextField()
    token_expiry = models.DateTimeField()
    calendar_id = models.CharField(
        max_length=255,
        default='primary',
        help_text='Google Calendar ID to sync with.'
    )
    sync_enabled = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    sync_token = models.CharField(
        max_length=500,
        blank=True,
        help_text='Google incremental sync token.'
    )
    ical_feed_token = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        help_text='Secret token for iCal feed URL.'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'google_calendar_integrations'

    def __str__(self):
        return f"Google Calendar: {self.user.email} ({self.calendar_id})"

    def save(self, *args, **kwargs):
        if not self.ical_feed_token:
            import secrets
            self.ical_feed_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)
