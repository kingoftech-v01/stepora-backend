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


# ── Backward-compatible imports ──
# Plan models moved to apps.plans.models. Re-exported here so that
# existing ``from apps.dreams.models import DreamMilestone`` etc.
# continue to work throughout the codebase.
from apps.plans.models import (  # noqa: F401, E402
    CalibrationResponse,
    DreamMilestone,
    DreamProgressSnapshot,
    FocusSession,
    Goal,
    Obstacle,
    PlanCheckIn,
    Task,
)


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
