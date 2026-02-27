"""
Dreams, Goals, and Tasks models for DreamPlanner.
"""

import uuid
from django.db import models
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField
from apps.users.models import User


class Dream(models.Model):
    """Main dream/objective model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dreams')

    title = EncryptedCharField(max_length=255)
    description = EncryptedTextField()
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
        """Calculate and update progress percentage based on milestones or goals."""
        total_milestones = self.milestones.count()
        if total_milestones > 0:
            # New hierarchy: progress based on milestones
            completed_milestones = self.milestones.filter(status='completed').count()
            self.progress_percentage = (completed_milestones / total_milestones) * 100
        else:
            # Legacy path: progress based on goals directly
            total_goals = self.goals.count()
            if total_goals == 0:
                self.progress_percentage = 0.0
            else:
                completed_goals = self.goals.filter(status='completed').count()
                self.progress_percentage = (completed_goals / total_goals) * 100

        self.save(update_fields=['progress_percentage'])

        # Record progress snapshot for sparkline display
        DreamProgressSnapshot.record_snapshot(self)

    def complete(self):
        """Mark dream as completed."""
        if self.status == 'completed':
            return  # Already completed, idempotent no-op

        self.status = 'completed'
        self.completed_at = timezone.now()
        self.progress_percentage = 100.0
        self.save()

        # Award XP to user
        self.user.add_xp(500)  # Completing a dream gives 500 XP

        # Check achievements
        from apps.users.services import AchievementService
        AchievementService.check_achievements(self.user)


class DreamMilestone(models.Model):
    """
    Time-based milestone within a dream plan.

    DreamMilestones divide the dream's timeline into equal periods (e.g., 12 months = 12 milestones).
    Each milestone contains multiple goals, and goals contain tasks.

    Hierarchy: Dream -> DreamMilestone -> Goal -> Task

    NOTE: This is different from "streak milestones" (7/14/30/60/100/365-day streaks in notifications)
    and "progress milestones" (25%/50%/75% in dreams/tasks.py). DreamMilestone is specifically
    for the AI-generated plan structure.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name='milestones')

    title = EncryptedCharField(max_length=255)
    description = EncryptedTextField(blank=True, default='')
    order = models.IntegerField(help_text='Order within the dream (1 = first milestone)')

    # Timeline for this milestone
    target_date = models.DateTimeField(
        null=True, blank=True,
        help_text='Date by which this milestone should be achieved'
    )
    expected_date = models.DateField(
        null=True, blank=True,
        help_text='Ideal/soft date to complete this milestone (no penalty if missed)'
    )
    deadline_date = models.DateField(
        null=True, blank=True,
        help_text='Hard deadline — must be done by this date'
    )

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

    # Progress
    progress_percentage = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'milestones'
        ordering = ['dream', 'order']
        indexes = [
            models.Index(fields=['dream', 'order']),
            models.Index(fields=['status']),
            models.Index(fields=['target_date']),
            models.Index(fields=['expected_date']),
            models.Index(fields=['deadline_date']),
        ]

    def __str__(self):
        return f"{self.title} (Milestone #{self.order})"

    def update_progress(self):
        """Calculate and update progress based on completed goals."""
        total_goals = self.goals.count()
        if total_goals == 0:
            self.progress_percentage = 0.0
        else:
            completed_goals = self.goals.filter(status='completed').count()
            self.progress_percentage = (completed_goals / total_goals) * 100

        self.save(update_fields=['progress_percentage'])

        # Update parent dream progress
        self.dream.update_progress()

    def complete(self):
        """Mark milestone as completed."""
        if self.status == 'completed':
            return

        self.status = 'completed'
        self.completed_at = timezone.now()
        self.progress_percentage = 100.0
        self.save()

        # Update dream progress
        self.dream.update_progress()

        # Award XP
        self.dream.user.add_xp(200)  # Completing a milestone gives 200 XP

        # Check achievements
        from apps.users.services import AchievementService
        AchievementService.check_achievements(self.dream.user)


class Goal(models.Model):
    """Goal within a milestone."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name='goals')
    milestone = models.ForeignKey(
        DreamMilestone, on_delete=models.CASCADE, related_name='goals',
        null=True, blank=True,
        help_text='The milestone this goal belongs to (null for legacy goals without milestones)'
    )

    title = EncryptedCharField(max_length=255)
    description = EncryptedTextField(blank=True, default='')
    order = models.IntegerField()

    estimated_minutes = models.IntegerField(null=True, blank=True)
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    expected_date = models.DateField(
        null=True, blank=True,
        help_text='Ideal/soft date to complete this goal (no penalty if missed)'
    )
    deadline_date = models.DateField(
        null=True, blank=True,
        help_text='Hard deadline — must be done by this date'
    )

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
            models.Index(fields=['milestone', 'order']),
            models.Index(fields=['expected_date']),
            models.Index(fields=['deadline_date']),
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

        # Update parent milestone progress if linked
        if self.milestone:
            self.milestone.update_progress()
        else:
            # Legacy path: update dream directly
            self.dream.update_progress()

    def complete(self):
        """Mark goal as completed."""
        if self.status == 'completed':
            return  # Already completed, idempotent no-op

        self.status = 'completed'
        self.completed_at = timezone.now()
        self.progress_percentage = 100.0
        self.save()

        # Update parent milestone or dream progress
        if self.milestone:
            self.milestone.update_progress()
        else:
            self.dream.update_progress()

        # Award XP
        self.dream.user.add_xp(100)  # Completing a goal gives 100 XP

        # Check achievements
        from apps.users.services import AchievementService
        AchievementService.check_achievements(self.dream.user)


class Task(models.Model):
    """Individual task within a goal."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='tasks')

    title = EncryptedCharField(max_length=255)
    description = EncryptedTextField(blank=True, default='')
    order = models.IntegerField()

    scheduled_date = models.DateTimeField(null=True, blank=True, db_index=True)
    scheduled_time = models.CharField(max_length=5, blank=True, help_text='HH:MM format')
    duration_mins = models.IntegerField(null=True, blank=True)
    expected_date = models.DateField(
        null=True, blank=True,
        help_text='Ideal/soft date to do this task (no penalty if missed)'
    )
    deadline_date = models.DateField(
        null=True, blank=True,
        help_text='Hard deadline — must be done by this date'
    )

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
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['expected_date']),
            models.Index(fields=['deadline_date']),
        ]

    def __str__(self):
        return f"{self.title} (Task #{self.order})"

    def complete(self):
        """Mark task as completed."""
        if self.status == 'completed':
            return  # Already completed, idempotent no-op

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

        # Record daily activity for heatmap
        from apps.users.models import DailyActivity
        DailyActivity.record_task_completion(
            user=self.goal.dream.user,
            xp_earned=xp_amount,
            duration_mins=self.duration_mins or 0,
        )

        # Check achievements
        from apps.users.services import AchievementService
        AchievementService.check_achievements(self.goal.dream.user)

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
    """Predicted or actual obstacles for dreams, milestones, or goals."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name='obstacles')
    milestone = models.ForeignKey(
        DreamMilestone, on_delete=models.CASCADE, related_name='obstacles',
        null=True, blank=True,
        help_text='The milestone this obstacle is linked to (optional)'
    )
    goal = models.ForeignKey(
        Goal, on_delete=models.CASCADE, related_name='obstacles',
        null=True, blank=True,
        help_text='The goal this obstacle is linked to (optional)'
    )

    title = EncryptedCharField(max_length=255)
    description = EncryptedTextField()

    TYPE_CHOICES = [
        ('predicted', 'Predicted'),
        ('actual', 'Actual'),
    ]
    obstacle_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='predicted')

    # AI-generated solution
    solution = EncryptedTextField(blank=True, default='')

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
        indexes = [
            models.Index(fields=['milestone']),
            models.Index(fields=['goal']),
        ]

    def __str__(self):
        return f"Obstacle: {self.title}"


class CalibrationResponse(models.Model):
    """Stores a calibration Q&A pair for a dream."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name='calibration_responses')

    question = models.TextField(help_text='AI-generated calibration question')
    answer = EncryptedTextField(blank=True, default='', help_text='User response to the question (encrypted at rest)')
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


class DreamTag(models.Model):
    """Tag for categorizing and filtering dreams."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dream_tags'
        ordering = ['name']

    def __str__(self):
        return self.name


class DreamTagging(models.Model):
    """M2M through model for Dream-Tag relationship."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name='taggings')
    tag = models.ForeignKey(DreamTag, on_delete=models.CASCADE, related_name='taggings')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dream_taggings'
        constraints = [
            models.UniqueConstraint(fields=['dream', 'tag'], name='unique_dream_tag'),
        ]

    def __str__(self):
        return f"{self.dream.title} - {self.tag.name}"


class DreamTemplate(models.Model):
    """
    Pre-built dream template for quick dream creation.

    Templates provide a starting point with suggested goals and tasks
    so users can quickly set up common dream types.
    """

    CATEGORY_CHOICES = [
        ('health', 'Health & Fitness'),
        ('career', 'Career & Business'),
        ('education', 'Education & Learning'),
        ('finance', 'Finance & Savings'),
        ('creative', 'Creative & Arts'),
        ('personal', 'Personal Growth'),
        ('social', 'Social & Relationships'),
        ('travel', 'Travel & Adventure'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        db_index=True,
    )
    template_goals = models.JSONField(
        default=list,
        help_text='JSON array of goal templates: [{title, description, order, tasks: [{title, description, order, duration_mins}]}]',
    )
    estimated_duration_days = models.IntegerField(
        default=90,
        help_text='Estimated number of days to complete this dream.',
    )
    difficulty = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
        ],
        default='intermediate',
    )
    icon = models.CharField(max_length=100, blank=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True)
    usage_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dream_templates'
        ordering = ['-is_featured', '-usage_count']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['is_featured', 'is_active']),
        ]

    def __str__(self):
        return f"Template: {self.title} ({self.category})"


class DreamCollaborator(models.Model):
    """
    Tracks users who collaborate on a dream.

    Collaborators can have different roles:
    - owner: the dream creator (full control)
    - collaborator: can add/edit goals and tasks
    - viewer: read-only access
    """

    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('collaborator', 'Collaborator'),
        ('viewer', 'Viewer'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name='collaborators')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dream_collaborations')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dream_collaborators'
        constraints = [
            models.UniqueConstraint(fields=['dream', 'user'], name='unique_dream_collaborator'),
        ]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'role'], name='idx_collab_user_role'),
            models.Index(fields=['dream', 'user'], name='idx_collab_dream_user'),
        ]

    def __str__(self):
        return f"{self.user.display_name or self.user.email} - {self.dream.title} ({self.role})"


class SharedDream(models.Model):
    """Represents a dream shared with another user."""

    PERMISSION_CHOICES = [
        ('view', 'View Only'),
        ('comment', 'Can Comment'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name='shares')
    shared_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='dreams_shared',
        help_text='The user who shared the dream.'
    )
    shared_with = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='dreams_shared_with_me',
        help_text='The user the dream was shared with.'
    )
    permission = models.CharField(
        max_length=20,
        choices=PERMISSION_CHOICES,
        default='view',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'shared_dreams'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['dream', 'shared_with'], name='unique_shared_dream'),
        ]
        indexes = [
            models.Index(fields=['shared_with'], name='idx_shared_dream_recipient'),
        ]

    def __str__(self):
        return f"{self.dream.title} shared with {self.shared_with.display_name or self.shared_with.email}"


class DreamProgressSnapshot(models.Model):
    """Daily snapshot of dream progress for sparkline charts."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name='progress_snapshots')
    date = models.DateField()
    progress_percentage = models.FloatField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dream_progress_snapshots'
        constraints = [
            models.UniqueConstraint(fields=['dream', 'date'], name='unique_dream_progress_date'),
        ]
        ordering = ['-date']
        indexes = [
            models.Index(fields=['dream', '-date']),
        ]

    def __str__(self):
        return f"{self.dream.title} - {self.date}: {self.progress_percentage}%"

    @classmethod
    def record_snapshot(cls, dream):
        """Record or update today's progress snapshot for a dream."""
        today = timezone.now().date()
        cls.objects.update_or_create(
            dream=dream,
            date=today,
            defaults={'progress_percentage': dream.progress_percentage},
        )


class VisionBoardImage(models.Model):
    """Image in a dream's vision board gallery."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name='vision_images')

    image_url = models.URLField(max_length=500, blank=True)
    image_file = models.ImageField(upload_to='vision_boards/', blank=True)
    caption = models.CharField(max_length=500, blank=True)
    is_ai_generated = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vision_board_images'
        ordering = ['order', '-created_at']
        indexes = [
            models.Index(fields=['dream', 'order']),
        ]

    def __str__(self):
        return f"Vision: {self.dream.title} #{self.order}"
