"""
Notification models for push notifications and reminders.
"""

import uuid
from django.db import models
from django.utils import timezone
from apps.users.models import User


class Notification(models.Model):
    """Push notification model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')

    TYPE_CHOICES = [
        ('reminder', 'Reminder'),
        ('motivation', 'Motivation'),
        ('progress', 'Progress'),
        ('achievement', 'Achievement'),
        ('check_in', 'Check In'),
        ('rescue', 'Rescue'),
        ('buddy', 'Buddy'),
        ('system', 'System'),
    ]
    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        db_index=True
    )

    title = models.CharField(max_length=255)
    body = models.TextField()

    # Additional data for deep linking
    data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional data: {screen: "", dreamId: "", goalId: "", taskId: ""}'
    )

    # Scheduling
    scheduled_for = models.DateTimeField(db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )

    # Retry logic
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-scheduled_for']
        indexes = [
            models.Index(fields=['user', '-scheduled_for']),
            models.Index(fields=['status', 'scheduled_for']),
            models.Index(fields=['notification_type']),
        ]

    def __str__(self):
        return f"{self.notification_type}: {self.title} ({self.status})"

    def mark_sent(self):
        """Mark notification as sent."""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])

    def mark_read(self):
        """Mark notification as read by user."""
        self.read_at = timezone.now()
        self.save(update_fields=['read_at'])

    def mark_failed(self, error_message=''):
        """Mark notification as failed."""
        self.status = 'failed'
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count'])

    def should_send(self):
        """Check if notification should be sent now."""
        if self.status != 'pending':
            return False

        now = timezone.now()
        if self.scheduled_for > now:
            return False

        # Check DND (do not disturb)
        if self.user.notification_prefs:
            dnd_enabled = self.user.notification_prefs.get('dndEnabled', False)
            if dnd_enabled:
                user_tz = timezone.pytz.timezone(self.user.timezone)
                user_time = now.astimezone(user_tz)
                hour = user_time.hour

                dnd_start = self.user.notification_prefs.get('dndStart', 22)
                dnd_end = self.user.notification_prefs.get('dndEnd', 7)

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
        help_text='List of variables that can be used: ["user_name", "dream_title", etc.]'
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_templates'

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
        ('scheduled', 'Scheduled'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notification_batches'
        ordering = ['-created_at']

    def __str__(self):
        return f"Batch: {self.name} ({self.total_sent}/{self.total_scheduled} sent)"
