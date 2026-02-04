"""
Dreams, Goals, and Tasks models for DreamPlanner.
"""

import uuid
from django.db import models
from django.utils import timezone
from apps.users.models import User


class Dream(models.Model):
    """Main dream/objective model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dreams')

    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=50, blank=True, db_index=True)
    target_date = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(default=1)

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
        ('archived', 'Archived'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True
    )

    # AI analysis
    ai_analysis = models.JSONField(
        null=True,
        blank=True,
        help_text='AI-generated analysis and insights'
    )

    # Vision board
    vision_image_url = models.URLField(max_length=500, blank=True)

    # Tracking
    progress_percentage = models.FloatField(default=0.0)
    completed_at = models.DateTimeField(null=True, blank=True)

    # 2-minute start
    has_two_minute_start = models.BooleanField(default=False)

    # Calibration status
    calibration_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('skipped', 'Skipped'),
        ],
        default='pending',
        help_text='Status of the calibration questionnaire'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dreams'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['category']),
            models.Index(fields=['target_date']),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.email}"

    def update_progress(self):
        """Calculate and update progress percentage based on completed goals."""
        total_goals = self.goals.count()
        if total_goals == 0:
            self.progress_percentage = 0.0
        else:
            completed_goals = self.goals.filter(status='completed').count()
            self.progress_percentage = (completed_goals / total_goals) * 100

        self.save(update_fields=['progress_percentage'])

    def complete(self):
        """Mark dream as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.progress_percentage = 100.0
        self.save()

        # Award XP to user
        self.user.add_xp(500)  # Completing a dream gives 500 XP


class Goal(models.Model):
    """Goal/milestone within a dream."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name='goals')

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.IntegerField()

    estimated_minutes = models.IntegerField(null=True, blank=True)
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    # Reminders
    reminder_enabled = models.BooleanField(default=True)
    reminder_time = models.DateTimeField(null=True, blank=True)

    # Progress
    progress_percentage = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'goals'
        ordering = ['dream', 'order']
        indexes = [
            models.Index(fields=['dream', 'order']),
            models.Index(fields=['status']),
            models.Index(fields=['scheduled_start']),
        ]

    def __str__(self):
        return f"{self.title} (Goal #{self.order})"

    def update_progress(self):
        """Calculate and update progress percentage based on completed tasks."""
        total_tasks = self.tasks.count()
        if total_tasks == 0:
            self.progress_percentage = 0.0
        else:
            completed_tasks = self.tasks.filter(status='completed').count()
            self.progress_percentage = (completed_tasks / total_tasks) * 100

        self.save(update_fields=['progress_percentage'])

        # Update parent dream progress
        self.dream.update_progress()

    def complete(self):
        """Mark goal as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.progress_percentage = 100.0
        self.save()

        # Update dream progress
        self.dream.update_progress()

        # Award XP
        self.dream.user.add_xp(100)  # Completing a goal gives 100 XP


class Task(models.Model):
    """Individual task within a goal."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='tasks')

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.IntegerField()

    scheduled_date = models.DateTimeField(null=True, blank=True, db_index=True)
    scheduled_time = models.CharField(max_length=5, blank=True, help_text='HH:MM format')
    duration_mins = models.IntegerField(null=True, blank=True)

    # Recurrence
    recurrence = models.JSONField(
        null=True,
        blank=True,
        help_text='Recurrence pattern: {type: "daily|weekly|monthly", interval: 1, ...}'
    )

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    # 2-minute start flag
    is_two_minute_start = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tasks'
        ordering = ['goal', 'scheduled_date', 'order']
        indexes = [
            models.Index(fields=['goal', 'scheduled_date']),
            models.Index(fields=['status']),
            models.Index(fields=['scheduled_date']),
        ]

    def __str__(self):
        return f"{self.title} (Task #{self.order})"

    def complete(self):
        """Mark task as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

        # Update goal progress
        self.goal.update_progress()

        # Award XP based on duration
        xp_amount = max(10, (self.duration_mins or 30) // 3)  # Minimum 10 XP
        self.goal.dream.user.add_xp(xp_amount)

        # Update user activity
        self.goal.dream.user.update_activity()

        # Update streak
        self._update_streak()

    def _update_streak(self):
        """Update user's streak based on consecutive day completions."""
        user = self.goal.dream.user
        today = timezone.now().date()
        last_activity_date = user.last_activity.date()

        if last_activity_date == today:
            # Already counted today
            return
        elif last_activity_date == today - timezone.timedelta(days=1):
            # Consecutive day
            user.streak_days += 1
        else:
            # Streak broken
            user.streak_days = 1

        user.save(update_fields=['streak_days'])


class Obstacle(models.Model):
    """Predicted or actual obstacles for dreams."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name='obstacles')

    title = models.CharField(max_length=255)
    description = models.TextField()

    TYPE_CHOICES = [
        ('predicted', 'Predicted'),
        ('actual', 'Actual'),
    ]
    obstacle_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='predicted')

    # AI-generated solution
    solution = models.TextField(blank=True)

    # Status
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('resolved', 'Resolved'),
        ('ignored', 'Ignored'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'obstacles'
        ordering = ['-created_at']

    def __str__(self):
        return f"Obstacle: {self.title}"


class CalibrationResponse(models.Model):
    """Stores a calibration Q&A pair for a dream."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name='calibration_responses')

    question = models.TextField(help_text='AI-generated calibration question')
    answer = models.TextField(blank=True, help_text='User response to the question')
    question_number = models.IntegerField(help_text='Order of question in the calibration flow')

    # Metadata about the question
    category = models.CharField(
        max_length=30,
        blank=True,
        help_text='Question category: experience, timeline, resources, motivation, constraints, specifics, lifestyle, preferences'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'calibration_responses'
        ordering = ['dream', 'question_number']
        indexes = [
            models.Index(fields=['dream', 'question_number']),
        ]

    def __str__(self):
        return f"Q{self.question_number}: {self.question[:50]}"
