"""
Dreams, Goals, and Tasks models for Stepora.
"""

import uuid

from django.db import models
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField

from apps.users.models import User


class Dream(models.Model):
    """Main dream/objective model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="dreams")

    title = EncryptedCharField(max_length=255)
    description = EncryptedTextField()
    category = models.CharField(max_length=50, blank=True, db_index=True)
    language = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="Detected language code (fr, en, es, etc.) from dream title/description",
    )
    target_date = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(default=1)

    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("paused", "Paused"),
        ("archived", "Archived"),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active", db_index=True
    )

    # AI analysis
    ai_analysis = models.JSONField(
        null=True, blank=True, help_text="AI-generated analysis and insights"
    )

    # Vision board
    vision_image_url = models.URLField(max_length=500, blank=True)

    # Color for calendar/UI identification
    color = models.CharField(
        max_length=7,
        blank=True,
        default="",
        help_text="Hex color for calendar display (e.g. #8B5CF6). Auto-assigned if blank.",
    )

    # Tracking
    progress_percentage = models.FloatField(default=0.0)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Privacy
    is_public = models.BooleanField(
        default=False, help_text="Whether this dream is publicly visible to other users"
    )

    # Favorites
    is_favorited = models.BooleanField(
        default=False,
        help_text="Whether the user has favorited this dream on the vision board",
    )

    # 2-minute start
    has_two_minute_start = models.BooleanField(default=False)

    # Calibration status
    calibration_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("skipped", "Skipped"),
        ],
        default="pending",
        help_text="Status of the calibration questionnaire",
    )

    # Adaptive plan generation fields
    plan_phase = models.CharField(
        max_length=20,
        choices=[
            ("none", "No Plan"),
            ("skeleton", "Skeleton Only"),
            ("partial", "Partial Tasks"),
            ("full", "Full Plan"),
        ],
        default="none",
        db_index=True,
    )
    plan_skeleton = models.JSONField(null=True, blank=True)
    tasks_generated_through_month = models.IntegerField(default=0)
    last_checkin_at = models.DateTimeField(null=True, blank=True)
    next_checkin_at = models.DateTimeField(null=True, blank=True, db_index=True)
    checkin_count = models.IntegerField(default=0)
    checkin_interval_days = models.IntegerField(
        default=14,
        help_text="Days between check-ins (7 if behind, 14 normal, 21 if ahead)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dreams"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["category"]),
            models.Index(fields=["target_date"]),
            models.Index(fields=["is_public", "status"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.email}"

    def update_progress(self):
        """Calculate and update progress percentage based on milestones or goals."""
        total_milestones = self.milestones.count()
        if total_milestones > 0:
            # New hierarchy: progress based on milestones
            completed_milestones = self.milestones.filter(status="completed").count()
            self.progress_percentage = (completed_milestones / total_milestones) * 100
        else:
            # Legacy path: progress based on goals directly
            total_goals = self.goals.count()
            if total_goals == 0:
                self.progress_percentage = 0.0
            else:
                completed_goals = self.goals.filter(status="completed").count()
                self.progress_percentage = (completed_goals / total_goals) * 100

        self.save(update_fields=["progress_percentage"])

        # Record progress snapshot for sparkline display
        DreamProgressSnapshot.record_snapshot(self)

    # Map dream category to gamification attribute
    CATEGORY_TO_ATTRIBUTE = {
        "health": "health",
        "career": "career",
        "relationships": "relationships",
        "personal": "personal_growth",
        "finance": "finance",
        "hobbies": "hobbies",
    }

    def _award_category_xp(self, amount):
        """Award XP to the matching skill radar category."""
        attr = self.CATEGORY_TO_ATTRIBUTE.get(self.category)
        if not attr:
            return
        from apps.users.models import GamificationProfile

        profile, _ = GamificationProfile.objects.get_or_create(user=self.user)
        profile.add_attribute_xp(attr, amount)

    def complete(self):
        """Mark dream as completed."""
        if self.status == "completed":
            return  # Already completed, idempotent no-op

        self.status = "completed"
        self.completed_at = timezone.now()
        self.progress_percentage = 100.0
        self.save()

        # Award XP to user
        self.user.add_xp(500)  # Completing a dream gives 500 XP

        # Award category XP to skill radar
        self._award_category_xp(500)

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
    dream = models.ForeignKey(
        Dream, on_delete=models.CASCADE, related_name="milestones"
    )

    title = EncryptedCharField(max_length=255)
    description = EncryptedTextField(blank=True, default="")
    order = models.IntegerField(
        help_text="Order within the dream (1 = first milestone)"
    )

    # Timeline for this milestone
    target_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date by which this milestone should be achieved",
    )
    expected_date = models.DateField(
        null=True,
        blank=True,
        help_text="Ideal/soft date to complete this milestone (no penalty if missed)",
    )
    deadline_date = models.DateField(
        null=True, blank=True, help_text="Hard deadline — must be done by this date"
    )

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("skipped", "Skipped"),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    # Progress
    progress_percentage = models.FloatField(default=0.0)

    has_tasks = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "milestones"
        ordering = ["dream", "order"]
        indexes = [
            models.Index(fields=["dream", "order"]),
            models.Index(fields=["status"]),
            models.Index(fields=["target_date"]),
            models.Index(fields=["expected_date"]),
            models.Index(fields=["deadline_date"]),
        ]

    def __str__(self):
        return f"{self.title} (Milestone #{self.order})"

    def update_progress(self):
        """Calculate and update progress based on completed goals."""
        total_goals = self.goals.count()
        if total_goals == 0:
            self.progress_percentage = 0.0
        else:
            completed_goals = self.goals.filter(status="completed").count()
            self.progress_percentage = (completed_goals / total_goals) * 100

        self.save(update_fields=["progress_percentage"])

        # Update parent dream progress
        self.dream.update_progress()

    def complete(self):
        """Mark milestone as completed."""
        if self.status == "completed":
            return

        self.status = "completed"
        self.completed_at = timezone.now()
        self.progress_percentage = 100.0
        self.save()

        # Update dream progress
        self.dream.update_progress()

        # Award XP
        self.dream.user.add_xp(200)  # Completing a milestone gives 200 XP
        self.dream._award_category_xp(200)

        # Check achievements
        from apps.users.services import AchievementService

        AchievementService.check_achievements(self.dream.user)


class Goal(models.Model):
    """Goal within a milestone."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name="goals")
    milestone = models.ForeignKey(
        DreamMilestone,
        on_delete=models.CASCADE,
        related_name="goals",
        null=True,
        blank=True,
        help_text="The milestone this goal belongs to (null for legacy goals without milestones)",
    )

    title = EncryptedCharField(max_length=255)
    description = EncryptedTextField(blank=True, default="")
    order = models.IntegerField()

    estimated_minutes = models.IntegerField(null=True, blank=True)
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    expected_date = models.DateField(
        null=True,
        blank=True,
        help_text="Ideal/soft date to complete this goal (no penalty if missed)",
    )
    deadline_date = models.DateField(
        null=True, blank=True, help_text="Hard deadline — must be done by this date"
    )

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("skipped", "Skipped"),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
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
        db_table = "goals"
        ordering = ["dream", "milestone__order", "order"]
        indexes = [
            models.Index(fields=["dream", "order"]),
            models.Index(fields=["status"]),
            models.Index(fields=["scheduled_start"]),
            models.Index(fields=["milestone", "order"]),
            models.Index(fields=["expected_date"]),
            models.Index(fields=["deadline_date"]),
        ]

    def __str__(self):
        return f"{self.title} (Goal #{self.order})"

    def update_progress(self):
        """Calculate and update progress percentage based on completed tasks."""
        total_tasks = self.tasks.count()
        if total_tasks == 0:
            self.progress_percentage = 0.0
        else:
            completed_tasks = self.tasks.filter(status="completed").count()
            self.progress_percentage = (completed_tasks / total_tasks) * 100

        self.save(update_fields=["progress_percentage"])

        # Update parent milestone progress if linked
        if self.milestone:
            self.milestone.update_progress()
        else:
            # Legacy path: update dream directly
            self.dream.update_progress()

    def complete(self):
        """Mark goal as completed."""
        if self.status == "completed":
            return  # Already completed, idempotent no-op

        self.status = "completed"
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
        self.dream._award_category_xp(100)

        # Check achievements
        from apps.users.services import AchievementService

        AchievementService.check_achievements(self.dream.user)


class Task(models.Model):
    """Individual task within a goal."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="tasks")

    title = EncryptedCharField(max_length=255)
    description = EncryptedTextField(blank=True, default="")
    order = models.IntegerField()

    scheduled_date = models.DateTimeField(null=True, blank=True, db_index=True)
    scheduled_time = models.CharField(
        max_length=5, blank=True, help_text="HH:MM format"
    )
    duration_mins = models.IntegerField(null=True, blank=True)
    expected_date = models.DateField(
        null=True,
        blank=True,
        help_text="Ideal/soft date to do this task (no penalty if missed)",
    )
    deadline_date = models.DateField(
        null=True, blank=True, help_text="Hard deadline — must be done by this date"
    )

    # Recurrence
    recurrence = models.JSONField(
        null=True,
        blank=True,
        help_text='Recurrence pattern: {type: "daily|weekly|monthly", interval: 1, ...}',
    )

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("skipped", "Skipped"),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    # 2-minute start flag
    is_two_minute_start = models.BooleanField(default=False)

    # ── Chain (recurring task chains) ──
    chain_next_delay_days = models.IntegerField(
        null=True,
        blank=True,
        help_text="Days after completion to schedule the next task in the chain",
    )
    chain_template_title = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Custom title for the next task in the chain (uses current title if blank)",
    )
    chain_parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chain_children",
        help_text="The previous task in this chain",
    )
    is_chain = models.BooleanField(
        default=False, help_text="Whether this task is part of a recurring chain"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tasks"
        ordering = ["goal", "scheduled_date", "order"]
        indexes = [
            models.Index(fields=["goal", "scheduled_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["scheduled_date"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["expected_date"]),
            models.Index(fields=["deadline_date"]),
            models.Index(fields=["chain_parent"]),
        ]

    def __str__(self):
        return f"{self.title} (Task #{self.order})"

    def complete(self):
        """Mark task as completed."""
        if self.status == "completed":
            return  # Already completed, idempotent no-op

        self.status = "completed"
        self.completed_at = timezone.now()
        self.save()

        # Update goal progress
        self.goal.update_progress()

        # Award XP based on duration
        xp_amount = max(10, (self.duration_mins or 30) // 3)  # Minimum 10 XP
        self.goal.dream.user.add_xp(xp_amount)
        self.goal.dream._award_category_xp(xp_amount)

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

        # ── Chain: auto-create next task if this is a chain task ──
        if self.chain_next_delay_days is not None:
            self._create_chain_next()

    def _update_streak(self):
        """Update user's streak based on consecutive day completions (atomic)."""
        from django.contrib.auth import get_user_model
        from django.db.models import F

        User = get_user_model()

        user = self.goal.dream.user
        today = timezone.now().date()
        last_activity_date = user.last_activity.date()

        if last_activity_date == today:
            # Already counted today
            return
        elif last_activity_date == today - timezone.timedelta(days=1):
            # Consecutive day — atomic increment
            User.objects.filter(id=user.id).update(streak_days=F("streak_days") + 1)
        else:
            # Streak broken — reset
            User.objects.filter(id=user.id).update(streak_days=1)

        user.refresh_from_db(fields=["streak_days"])

    def _create_chain_next(self):
        """Auto-create the next task in a recurring chain."""
        from datetime import timedelta

        next_title = (
            self.chain_template_title.strip()
            if self.chain_template_title
            else self.title
        )
        next_date = self.completed_at + timedelta(days=self.chain_next_delay_days)

        # Determine next order
        max_order = Task.objects.filter(goal=self.goal).count()

        next_task = Task.objects.create(
            goal=self.goal,
            title=next_title,
            description=self.description,
            order=max_order + 1,
            scheduled_date=next_date,
            scheduled_time=self.scheduled_time,
            duration_mins=self.duration_mins,
            chain_next_delay_days=self.chain_next_delay_days,
            chain_template_title=self.chain_template_title,
            chain_parent=self,
            is_chain=True,
        )

        # Create notification for the user
        from apps.notifications.models import Notification

        Notification.objects.create(
            user=self.goal.dream.user,
            notification_type="system",
            title="Next task in chain created",
            body='"{}" has been scheduled for {}.'.format(
                next_task.title, next_date.strftime("%b %d, %Y")
            ),
            scheduled_for=timezone.now(),
            data={
                "screen": "dream",
                "dreamId": str(self.goal.dream.id),
                "goalId": str(self.goal.id),
                "taskId": str(next_task.id),
            },
        )

        return next_task

    def get_chain_position(self):
        """Return (position, total) for this task in its chain."""
        if not self.is_chain and self.chain_next_delay_days is None:
            return None, None

        # Walk back to the chain root
        root = self
        position = 1
        while root.chain_parent_id:
            root = root.chain_parent
            position += 1

        # Count all tasks in the chain from root forward
        total = position
        current = self
        while Task.objects.filter(chain_parent=current).exists():
            current = Task.objects.filter(chain_parent=current).first()
            total += 1

        return position, total


class Obstacle(models.Model):
    """Predicted or actual obstacles for dreams, milestones, or goals."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name="obstacles")
    milestone = models.ForeignKey(
        DreamMilestone,
        on_delete=models.CASCADE,
        related_name="obstacles",
        null=True,
        blank=True,
        help_text="The milestone this obstacle is linked to (optional)",
    )
    goal = models.ForeignKey(
        Goal,
        on_delete=models.CASCADE,
        related_name="obstacles",
        null=True,
        blank=True,
        help_text="The goal this obstacle is linked to (optional)",
    )

    title = EncryptedCharField(max_length=255)
    description = EncryptedTextField()

    TYPE_CHOICES = [
        ("predicted", "Predicted"),
        ("actual", "Actual"),
    ]
    obstacle_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default="predicted"
    )

    # AI-generated solution
    solution = EncryptedTextField(blank=True, default="")

    # Status
    STATUS_CHOICES = [
        ("active", "Active"),
        ("resolved", "Resolved"),
        ("ignored", "Ignored"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "obstacles"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["milestone"]),
            models.Index(fields=["goal"]),
        ]

    def __str__(self):
        return f"Obstacle: {self.title}"


class CalibrationResponse(models.Model):
    """Stores a calibration Q&A pair for a dream."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(
        Dream, on_delete=models.CASCADE, related_name="calibration_responses"
    )

    question = models.TextField(help_text="AI-generated calibration question")
    answer = EncryptedTextField(
        blank=True,
        default="",
        help_text="User response to the question (encrypted at rest)",
    )
    question_number = models.IntegerField(
        help_text="Order of question in the calibration flow"
    )

    # Metadata about the question
    category = models.CharField(
        max_length=30,
        blank=True,
        help_text="Question category: experience, timeline, resources, motivation, constraints, specifics, lifestyle, preferences",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "calibration_responses"
        ordering = ["dream", "question_number"]
        indexes = [
            models.Index(fields=["dream", "question_number"]),
        ]

    def __str__(self):
        return f"Q{self.question_number}: {self.question[:50]}"


class DreamTag(models.Model):
    """Tag for categorizing and filtering dreams."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dream_tags"
        ordering = ["name"]

    def __str__(self):
        return self.name


class DreamTagging(models.Model):
    """M2M through model for Dream-Tag relationship."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name="taggings")
    tag = models.ForeignKey(DreamTag, on_delete=models.CASCADE, related_name="taggings")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dream_taggings"
        constraints = [
            models.UniqueConstraint(fields=["dream", "tag"], name="unique_dream_tag"),
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
        ("health", "Health & Fitness"),
        ("career", "Career & Business"),
        ("education", "Education & Learning"),
        ("finance", "Finance & Savings"),
        ("creative", "Creative & Arts"),
        ("personal", "Personal Growth"),
        ("hobbies", "Hobbies & Skills"),
        ("social", "Social & Relationships"),
        ("relationships", "Relationships"),
        ("travel", "Travel & Adventure"),
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
        help_text="JSON array of goal templates: [{title, description, order, tasks: [{title, description, order, duration_mins}]}]",
    )
    estimated_duration_days = models.IntegerField(
        default=90,
        help_text="Estimated number of days to complete this dream.",
    )
    suggested_timeline = models.CharField(
        max_length=50,
        blank=True,
        help_text='Human-readable timeline, e.g. "3 months", "1 year"',
    )
    difficulty = models.CharField(
        max_length=20,
        choices=[
            ("beginner", "Beginner"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
        ],
        default="intermediate",
    )
    icon = models.CharField(max_length=100, blank=True)
    color = models.CharField(
        max_length=20,
        default="#8B5CF6",
        help_text="Accent color for template card display",
    )
    is_featured = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True)
    usage_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dream_templates"
        ordering = ["-is_featured", "-usage_count"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["is_featured", "is_active"]),
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
        ("owner", "Owner"),
        ("collaborator", "Collaborator"),
        ("viewer", "Viewer"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(
        Dream, on_delete=models.CASCADE, related_name="collaborators"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="dream_collaborations"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="viewer")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dream_collaborators"
        constraints = [
            models.UniqueConstraint(
                fields=["dream", "user"], name="unique_dream_collaborator"
            ),
        ]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "role"], name="idx_collab_user_role"),
            models.Index(fields=["dream", "user"], name="idx_collab_dream_user"),
        ]

    def __str__(self):
        return f"{self.user.display_name or self.user.email} - {self.dream.title} ({self.role})"


class SharedDream(models.Model):
    """Represents a dream shared with another user."""

    PERMISSION_CHOICES = [
        ("view", "View Only"),
        ("comment", "Can Comment"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name="shares")
    shared_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="dreams_shared",
        help_text="The user who shared the dream.",
    )
    shared_with = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="dreams_shared_with_me",
        help_text="The user the dream was shared with.",
    )
    permission = models.CharField(
        max_length=20,
        choices=PERMISSION_CHOICES,
        default="view",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "shared_dreams"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["dream", "shared_with"], name="unique_shared_dream"
            ),
        ]
        indexes = [
            models.Index(fields=["shared_with"], name="idx_shared_dream_recipient"),
        ]

    def __str__(self):
        return f"{self.dream.title} shared with {self.shared_with.display_name or self.shared_with.email}"


class DreamProgressSnapshot(models.Model):
    """Daily snapshot of dream progress for sparkline charts."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(
        Dream, on_delete=models.CASCADE, related_name="progress_snapshots"
    )
    date = models.DateField()
    progress_percentage = models.FloatField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dream_progress_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["dream", "date"], name="unique_dream_progress_date"
            ),
        ]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["dream", "-date"]),
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
            defaults={"progress_percentage": dream.progress_percentage},
        )


class FocusSession(models.Model):
    """Pomodoro-style focus session linked to a user and optionally a task."""

    SESSION_TYPE_CHOICES = [
        ("work", "Work"),
        ("break", "Break"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="focus_sessions"
    )
    task = models.ForeignKey(
        "Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="focus_sessions",
    )
    duration_minutes = models.PositiveIntegerField(
        help_text="Planned duration in minutes"
    )
    actual_minutes = models.PositiveIntegerField(
        default=0, help_text="Actual time focused in minutes"
    )
    session_type = models.CharField(
        max_length=20, choices=SESSION_TYPE_CHOICES, default="work"
    )
    completed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "focus_sessions"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "-started_at"]),
            models.Index(fields=["user", "completed"]),
        ]

    def __str__(self):
        return f"FocusSession {self.session_type} ({self.duration_minutes}min) - {self.user.email}"


class DreamJournal(models.Model):
    """Journal/notes entry associated with a dream."""

    MOOD_CHOICES = [
        ("excited", "Excited"),
        ("happy", "Happy"),
        ("neutral", "Neutral"),
        ("frustrated", "Frustrated"),
        ("motivated", "Motivated"),
        ("reflective", "Reflective"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(
        Dream, on_delete=models.CASCADE, related_name="journal_entries"
    )
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField(
        help_text="Journal entry content stored as HTML or markdown"
    )
    mood = models.CharField(max_length=20, blank=True, choices=MOOD_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dream_journal_entries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["dream", "-created_at"]),
        ]

    def __str__(self):
        label = self.title or self.content[:50]
        return f"Journal: {label} ({self.dream.title})"


class ProgressPhoto(models.Model):
    """Progress photo for visual tracking of dream progress via AI analysis."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(
        Dream, on_delete=models.CASCADE, related_name="progress_photos"
    )

    image = models.ImageField(upload_to="progress_photos/")
    caption = EncryptedTextField(blank=True, default="")
    ai_analysis = EncryptedTextField(blank=True, default="")

    taken_at = models.DateTimeField(help_text="When the progress photo was taken")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "progress_photos"
        ordering = ["-taken_at"]
        indexes = [
            models.Index(fields=["dream", "-taken_at"]),
        ]

    def __str__(self):
        return f"Progress photo for {self.dream.title} ({self.taken_at.strftime('%Y-%m-%d')})"


class VisionBoardImage(models.Model):
    """Image in a dream's vision board gallery."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(
        Dream, on_delete=models.CASCADE, related_name="vision_images"
    )

    image_url = models.URLField(max_length=500, blank=True)
    image_file = models.ImageField(upload_to="vision_boards/", blank=True)
    caption = models.CharField(max_length=500, blank=True)
    is_ai_generated = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "vision_board_images"
        ordering = ["order", "-created_at"]
        indexes = [
            models.Index(fields=["dream", "order"]),
        ]

    def __str__(self):
        return f"Vision: {self.dream.title} #{self.order}"


class PlanCheckIn(models.Model):
    """Record of each AI check-in session for a dream (interactive or autonomous)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name="checkins")
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkin_records",
    )
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("questionnaire_generating", "Generating Questionnaire"),
        ("awaiting_user", "Awaiting User Response"),
        ("ai_processing", "AI Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),
    ]
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="pending", db_index=True
    )

    TRIGGERED_BY_CHOICES = [
        ("schedule", "Scheduled"),
        ("manual", "Manual"),
        ("auto_expire", "Auto Expired"),
    ]
    triggered_by = models.CharField(
        max_length=20, choices=TRIGGERED_BY_CHOICES, default="schedule"
    )

    # Interactive questionnaire
    questionnaire = models.JSONField(
        null=True,
        blank=True,
        help_text="AI-generated questions: [{id, question_type, question, options, ...}]",
    )
    user_responses = models.JSONField(
        null=True, blank=True, help_text="User answers: {question_id: answer_value}"
    )
    questionnaire_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="After this time, check-in runs autonomously if user has not responded",
    )

    # Pace analysis
    PACE_CHOICES = [
        ("significantly_behind", "Significantly Behind"),
        ("behind", "Behind"),
        ("on_track", "On Track"),
        ("ahead", "Ahead"),
        ("significantly_ahead", "Significantly Ahead"),
    ]
    pace_status = models.CharField(
        max_length=25, choices=PACE_CHOICES, blank=True, default=""
    )
    next_checkin_interval_days = models.IntegerField(default=14)

    # Progress snapshot
    progress_at_checkin = models.FloatField(default=0.0)
    tasks_completed_since_last = models.IntegerField(default=0)
    tasks_overdue_at_checkin = models.IntegerField(default=0)

    # AI results
    ai_actions = models.JSONField(default=list)
    tasks_created = models.IntegerField(default=0)
    milestones_adjusted = models.IntegerField(default=0)
    months_generated_through = models.IntegerField(default=0)
    coaching_message = models.TextField(blank=True)
    adjustment_summary = models.TextField(blank=True)

    # Timestamps
    scheduled_for = models.DateTimeField(db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "plan_checkins"
        ordering = ["-scheduled_for"]

    def __str__(self):
        return f"CheckIn for {self.dream_id} ({self.status})"
