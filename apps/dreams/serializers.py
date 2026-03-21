"""
Serializers for Dreams app.
"""

from django.conf import settings
from django.utils.translation import gettext as _
from rest_framework import serializers

from core.sanitizers import sanitize_text

from .models import (
    CalibrationResponse,
    Dream,
    DreamCollaborator,
    DreamJournal,
    DreamMilestone,
    DreamTag,
    DreamTemplate,
    FocusSession,
    Goal,
    Obstacle,
    PlanCheckIn,
    ProgressPhoto,
    SharedDream,
    Task,
    VisionBoardImage,
)


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for Task model."""

    chain_position = serializers.SerializerMethodField(
        help_text="Position of this task within its chain (e.g. {position: 3, total: 5})."
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "goal",
            "title",
            "description",
            "order",
            "scheduled_date",
            "scheduled_time",
            "duration_mins",
            "expected_date",
            "deadline_date",
            "recurrence",
            "status",
            "completed_at",
            "is_two_minute_start",
            "chain_next_delay_days",
            "chain_template_title",
            "chain_parent",
            "is_chain",
            "chain_position",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "completed_at",
            "chain_position",
        ]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the task."},
            "goal": {"help_text": "The goal this task belongs to."},
            "title": {"help_text": "Short title of the task."},
            "description": {"help_text": "Detailed description of the task."},
            "order": {"help_text": "Display order of the task within its goal."},
            "scheduled_date": {"help_text": "Date when the task is scheduled."},
            "scheduled_time": {"help_text": "Time when the task is scheduled."},
            "duration_mins": {"help_text": "Estimated duration in minutes."},
            "expected_date": {
                "help_text": "Ideal/soft date to do this task (calendar event)."
            },
            "deadline_date": {
                "help_text": "Hard deadline for this task (calendar deadline)."
            },
            "recurrence": {"help_text": "Recurrence pattern for the task."},
            "status": {"help_text": "Current status of the task."},
            "completed_at": {"help_text": "Timestamp when the task was completed."},
            "is_two_minute_start": {
                "help_text": "Whether this is a two-minute quick-start task."
            },
            "chain_next_delay_days": {
                "help_text": "Days after completion to auto-create next task."
            },
            "chain_template_title": {
                "help_text": "Custom title for the next chained task."
            },
            "chain_parent": {"help_text": "Previous task in this chain."},
            "is_chain": {
                "help_text": "Whether this task is part of a recurring chain."
            },
            "created_at": {"help_text": "Timestamp when the task was created."},
            "updated_at": {"help_text": "Timestamp when the task was last updated."},
        }

    def get_chain_position(self, obj):
        if not obj.is_chain and obj.chain_next_delay_days is None:
            return None
        position, total = obj.get_chain_position()
        if position is None:
            return None
        return {"position": position, "total": total}


class GoalSerializer(serializers.ModelSerializer):
    """Serializer for Goal model."""

    tasks = TaskSerializer(
        many=True, read_only=True, help_text="List of tasks under this goal."
    )
    tasks_count = serializers.SerializerMethodField(
        help_text="Total number of tasks in this goal."
    )
    completed_tasks_count = serializers.SerializerMethodField(
        help_text="Number of completed tasks in this goal."
    )

    class Meta:
        model = Goal
        fields = [
            "id",
            "dream",
            "milestone",
            "title",
            "description",
            "order",
            "estimated_minutes",
            "scheduled_start",
            "scheduled_end",
            "expected_date",
            "deadline_date",
            "status",
            "completed_at",
            "progress_percentage",
            "reminder_enabled",
            "reminder_time",
            "tasks",
            "tasks_count",
            "completed_tasks_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "progress_percentage",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the goal."},
            "dream": {"help_text": "The dream this goal belongs to."},
            "milestone": {"help_text": "The milestone this goal belongs to."},
            "title": {"help_text": "Short title of the goal."},
            "description": {"help_text": "Detailed description of the goal."},
            "order": {"help_text": "Display order of the goal within its milestone."},
            "estimated_minutes": {
                "help_text": "Estimated time to complete in minutes."
            },
            "scheduled_start": {"help_text": "Scheduled start date for the goal."},
            "scheduled_end": {"help_text": "Scheduled end date for the goal."},
            "expected_date": {
                "help_text": "Ideal/soft date to complete this goal (calendar event)."
            },
            "deadline_date": {
                "help_text": "Hard deadline for this goal (calendar deadline)."
            },
            "status": {"help_text": "Current status of the goal."},
            "completed_at": {"help_text": "Timestamp when the goal was completed."},
            "progress_percentage": {"help_text": "Percentage of goal completion."},
            "reminder_enabled": {
                "help_text": "Whether reminders are enabled for this goal."
            },
            "reminder_time": {"help_text": "Time of day to send the reminder."},
            "created_at": {"help_text": "Timestamp when the goal was created."},
            "updated_at": {"help_text": "Timestamp when the goal was last updated."},
        }

    def get_tasks_count(self, obj) -> int:
        # Use len() to leverage prefetched data instead of .count() which hits DB
        return len(obj.tasks.all())

    def get_completed_tasks_count(self, obj) -> int:
        return len([t for t in obj.tasks.all() if t.status == "completed"])


class ObstacleSerializer(serializers.ModelSerializer):
    """Serializer for Obstacle model."""

    class Meta:
        model = Obstacle
        fields = [
            "id",
            "dream",
            "milestone",
            "goal",
            "title",
            "description",
            "obstacle_type",
            "solution",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the obstacle."},
            "dream": {"help_text": "The dream this obstacle is associated with."},
            "milestone": {
                "help_text": "The dream milestone this obstacle is linked to (optional)."
            },
            "goal": {"help_text": "The goal this obstacle is linked to (optional)."},
            "title": {"help_text": "Short title of the obstacle."},
            "description": {"help_text": "Detailed description of the obstacle."},
            "obstacle_type": {"help_text": "Category or type of the obstacle."},
            "solution": {"help_text": "Proposed solution to overcome the obstacle."},
            "status": {"help_text": "Current status of the obstacle."},
            "created_at": {"help_text": "Timestamp when the obstacle was created."},
            "updated_at": {
                "help_text": "Timestamp when the obstacle was last updated."
            },
        }


class DreamMilestoneSerializer(serializers.ModelSerializer):
    """Serializer for DreamMilestone model with nested goals."""

    goals = GoalSerializer(
        many=True, read_only=True, help_text="List of goals under this milestone."
    )
    obstacles = ObstacleSerializer(
        many=True, read_only=True, help_text="List of obstacles for this milestone."
    )
    goals_count = serializers.SerializerMethodField(
        help_text="Total number of goals in this milestone."
    )
    completed_goals_count = serializers.SerializerMethodField(
        help_text="Number of completed goals."
    )

    class Meta:
        model = DreamMilestone
        fields = [
            "id",
            "dream",
            "title",
            "description",
            "order",
            "target_date",
            "expected_date",
            "deadline_date",
            "status",
            "completed_at",
            "progress_percentage",
            "goals",
            "obstacles",
            "goals_count",
            "completed_goals_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "progress_percentage",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the dream milestone."},
            "dream": {"help_text": "The dream this milestone belongs to."},
            "title": {"help_text": "Short title of the milestone."},
            "description": {
                "help_text": "Detailed description of what this milestone achieves."
            },
            "order": {"help_text": "Order within the dream timeline."},
            "target_date": {"help_text": "Target date for this milestone."},
            "expected_date": {
                "help_text": "Ideal/soft date to complete this milestone (calendar event)."
            },
            "deadline_date": {
                "help_text": "Hard deadline for this milestone (calendar deadline)."
            },
            "status": {"help_text": "Current status of the milestone."},
            "completed_at": {
                "help_text": "Timestamp when the milestone was completed."
            },
            "progress_percentage": {"help_text": "Percentage of milestone completion."},
            "created_at": {"help_text": "Timestamp when the milestone was created."},
            "updated_at": {
                "help_text": "Timestamp when the milestone was last updated."
            },
        }

    def get_goals_count(self, obj) -> int:
        return len(obj.goals.all())

    def get_completed_goals_count(self, obj) -> int:
        return len([g for g in obj.goals.all() if g.status == "completed"])


class DreamSerializer(serializers.ModelSerializer):
    """Basic serializer for Dream model."""

    goals_count = serializers.SerializerMethodField(
        help_text="Total number of goals for this dream."
    )
    tasks_count = serializers.SerializerMethodField(
        help_text="Total number of tasks across all goals."
    )
    tags = serializers.SerializerMethodField(
        help_text="List of tag names associated with this dream."
    )
    sparkline_data = serializers.SerializerMethodField(
        help_text="Last 7 progress snapshots for sparkline charts."
    )
    signed_vision_image_url = serializers.SerializerMethodField(
        help_text="Pre-signed URL for the vision board image."
    )
    completed_goals_count = serializers.IntegerField(
        source="_completed_goals_count", read_only=True, default=0
    )

    class Meta:
        model = Dream
        fields = [
            "id",
            "user",
            "title",
            "description",
            "category",
            "target_date",
            "priority",
            "status",
            "color",
            "progress_percentage",
            "completed_at",
            "has_two_minute_start",
            "is_public",
            "is_favorited",
            "vision_image_url",
            "signed_vision_image_url",
            "calibration_status",
            "goals_count",
            "completed_goals_count",
            "tasks_count",
            "tags",
            "sparkline_data",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "progress_percentage",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the dream."},
            "user": {"help_text": "The user who owns this dream."},
            "title": {"help_text": "Short title of the dream."},
            "description": {"help_text": "Detailed description of the dream."},
            "category": {"help_text": "Category the dream belongs to."},
            "target_date": {"help_text": "Target date for achieving the dream."},
            "priority": {"help_text": "Priority level of the dream."},
            "status": {"help_text": "Current status of the dream."},
            "color": {"help_text": "Hex color for calendar display."},
            "progress_percentage": {
                "help_text": "Overall completion percentage of the dream."
            },
            "completed_at": {"help_text": "Timestamp when the dream was completed."},
            "has_two_minute_start": {
                "help_text": "Whether a two-minute quick-start task exists."
            },
            "vision_image_url": {"help_text": "URL of the vision board image."},
            "calibration_status": {
                "help_text": "Status of the dream calibration process."
            },
            "created_at": {"help_text": "Timestamp when the dream was created."},
            "updated_at": {"help_text": "Timestamp when the dream was last updated."},
        }

    def get_goals_count(self, obj) -> int:
        if hasattr(obj, "_goals_count"):
            return obj._goals_count
        return obj.goals.count()

    def get_tasks_count(self, obj) -> int:
        if hasattr(obj, "_tasks_count"):
            return obj._tasks_count
        return sum(len(goal.tasks.all()) for goal in obj.goals.all())

    def get_tags(self, obj) -> list:
        if hasattr(obj, "_prefetched_tags"):
            return obj._prefetched_tags
        return list(obj.taggings.values_list("tag__name", flat=True))

    def get_sparkline_data(self, obj) -> list:
        """Return last 7 progress snapshots for sparkline chart."""
        if hasattr(obj, "_prefetched_sparkline"):
            return obj._prefetched_sparkline
        from .models import DreamProgressSnapshot

        snapshots = DreamProgressSnapshot.objects.filter(dream=obj).order_by("-date")[
            :7
        ]
        return list(
            reversed(
                [
                    {"date": str(s.date), "progress": s.progress_percentage}
                    for s in snapshots
                ]
            )
        )

    def get_signed_vision_image_url(self, obj) -> str:
        """Return a pre-signed URL for the vision image stored on S3."""
        from core.storage import presigned_url

        if not obj.vision_image_url:
            return ""
        # If it's an S3 URL from our bucket, generate a signed URL from the key
        bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
        if bucket and bucket in (obj.vision_image_url or ""):
            import boto3
            from botocore.config import Config

            key = obj.vision_image_url.split(bucket + ".s3.amazonaws.com/")[-1]
            if "/" in key:
                client = boto3.client(
                    "s3",
                    region_name=getattr(settings, "AWS_S3_REGION_NAME", "eu-west-3"),
                    config=Config(signature_version="s3v4"),
                )
                return client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": key},
                    ExpiresIn=3600,
                )
        # External URL or local dev — return as-is
        return obj.vision_image_url


class CalibrationResponseSerializer(serializers.ModelSerializer):
    """Serializer for CalibrationResponse model."""

    class Meta:
        model = CalibrationResponse
        fields = [
            "id",
            "dream",
            "question",
            "answer",
            "question_number",
            "category",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "dream",
            "question",
            "question_number",
            "category",
            "created_at",
        ]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the calibration response."},
            "dream": {"help_text": "The dream this calibration response belongs to."},
            "question": {"help_text": "The calibration question text."},
            "answer": {"help_text": "The user answer to the calibration question."},
            "question_number": {
                "help_text": "Order number of the question in the sequence."
            },
            "category": {"help_text": "Category of the calibration question."},
            "created_at": {"help_text": "Timestamp when the response was created."},
        }


class DreamDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Dream with nested milestones, goals and tasks."""

    milestones = DreamMilestoneSerializer(
        many=True, read_only=True, help_text="List of milestones for this dream."
    )
    goals = GoalSerializer(
        many=True, read_only=True, help_text="List of goals for this dream."
    )
    obstacles = ObstacleSerializer(
        many=True, read_only=True, help_text="List of obstacles for this dream."
    )
    calibration_responses = CalibrationResponseSerializer(
        many=True,
        read_only=True,
        help_text="List of calibration responses for this dream.",
    )
    milestones_count = serializers.SerializerMethodField(
        help_text="Total number of milestones."
    )
    completed_milestones_count = serializers.SerializerMethodField(
        help_text="Number of completed milestones."
    )
    goals_count = serializers.SerializerMethodField()
    completed_goal_count = serializers.SerializerMethodField()
    total_tasks = serializers.SerializerMethodField()
    completed_tasks = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    signed_vision_image_url = serializers.SerializerMethodField(
        help_text="Pre-signed URL for the vision board image."
    )

    class Meta:
        model = Dream
        fields = [
            "id",
            "user",
            "title",
            "description",
            "category",
            "target_date",
            "priority",
            "status",
            "color",
            "ai_analysis",
            "vision_image_url",
            "signed_vision_image_url",
            "progress_percentage",
            "completed_at",
            "has_two_minute_start",
            "is_public",
            "is_favorited",
            "calibration_status",
            "calibration_responses",
            "milestones",
            "goals",
            "obstacles",
            "milestones_count",
            "completed_milestones_count",
            "goals_count",
            "completed_goal_count",
            "total_tasks",
            "completed_tasks",
            "days_left",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "progress_percentage",
            "ai_analysis",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the dream."},
            "user": {"help_text": "The user who owns this dream."},
            "title": {"help_text": "Short title of the dream."},
            "description": {"help_text": "Detailed description of the dream."},
            "category": {"help_text": "Category the dream belongs to."},
            "target_date": {"help_text": "Target date for achieving the dream."},
            "priority": {"help_text": "Priority level of the dream."},
            "status": {"help_text": "Current status of the dream."},
            "color": {"help_text": "Hex color for calendar display."},
            "ai_analysis": {"help_text": "AI-generated analysis of the dream."},
            "vision_image_url": {"help_text": "URL of the vision board image."},
            "progress_percentage": {
                "help_text": "Overall completion percentage of the dream."
            },
            "completed_at": {"help_text": "Timestamp when the dream was completed."},
            "has_two_minute_start": {
                "help_text": "Whether a two-minute quick-start task exists."
            },
            "calibration_status": {
                "help_text": "Status of the dream calibration process."
            },
            "created_at": {"help_text": "Timestamp when the dream was created."},
            "updated_at": {"help_text": "Timestamp when the dream was last updated."},
        }

    def get_milestones_count(self, obj) -> int:
        if hasattr(obj, "_milestones_count"):
            return obj._milestones_count
        return obj.milestones.count()

    def get_completed_milestones_count(self, obj) -> int:
        if hasattr(obj, "_completed_milestones_count"):
            return obj._completed_milestones_count
        return obj.milestones.filter(status="completed").count()

    def get_goals_count(self, obj) -> int:
        if hasattr(obj, "_goals_count"):
            return obj._goals_count
        return obj.goals.count()

    def get_completed_goal_count(self, obj) -> int:
        if hasattr(obj, "_completed_goals_count"):
            return obj._completed_goals_count
        return obj.goals.filter(status="completed").count()

    def get_total_tasks(self, obj) -> int:
        if hasattr(obj, "_total_tasks"):
            return obj._total_tasks
        return sum(len(goal.tasks.all()) for goal in obj.goals.all())

    def get_completed_tasks(self, obj) -> int:
        if hasattr(obj, "_completed_tasks"):
            return obj._completed_tasks
        return sum(
            len([t for t in goal.tasks.all() if t.status == "completed"])
            for goal in obj.goals.all()
        )

    def get_days_left(self, obj):
        if not obj.target_date:
            return None
        from django.utils import timezone

        delta = obj.target_date - timezone.now()
        return max(0, delta.days)

    def get_tags(self, obj) -> list:
        if hasattr(obj, "_prefetched_tags"):
            return obj._prefetched_tags
        return list(obj.taggings.values_list("tag__name", flat=True))

    def get_signed_vision_image_url(self, obj) -> str:
        # Reuse logic from DreamSerializer
        return DreamSerializer.get_signed_vision_image_url(self, obj)


class PublicGoalSerializer(serializers.ModelSerializer):
    """Goal serializer for public dream viewing — NO tasks exposed."""

    tasks_count = serializers.SerializerMethodField()
    completed_tasks_count = serializers.SerializerMethodField()

    class Meta:
        model = Goal
        fields = [
            "id",
            "title",
            "description",
            "order",
            "status",
            "progress_percentage",
            "tasks_count",
            "completed_tasks_count",
        ]

    def get_tasks_count(self, obj) -> int:
        return len(obj.tasks.all())

    def get_completed_tasks_count(self, obj) -> int:
        return len([t for t in obj.tasks.all() if t.status == "completed"])


class PublicMilestoneSerializer(serializers.ModelSerializer):
    """Milestone serializer for public dream viewing — goals without tasks."""

    goals = PublicGoalSerializer(many=True, read_only=True)
    goals_count = serializers.SerializerMethodField()
    completed_goals_count = serializers.SerializerMethodField()

    class Meta:
        model = DreamMilestone
        fields = [
            "id",
            "title",
            "description",
            "order",
            "status",
            "progress_percentage",
            "goals",
            "goals_count",
            "completed_goals_count",
        ]

    def get_goals_count(self, obj) -> int:
        return len(obj.goals.all())

    def get_completed_goals_count(self, obj) -> int:
        return len([g for g in obj.goals.all() if g.status == "completed"])


class PublicDreamDetailSerializer(serializers.ModelSerializer):
    """Read-only serializer for viewing another user's public dream.
    Exposes milestones and goals but NOT tasks, obstacles, AI analysis,
    calibration data, or collaborators."""

    milestones = PublicMilestoneSerializer(many=True, read_only=True)
    goals = PublicGoalSerializer(many=True, read_only=True)
    milestones_count = serializers.SerializerMethodField()
    completed_milestones_count = serializers.SerializerMethodField()
    goals_count = serializers.SerializerMethodField()
    completed_goal_count = serializers.SerializerMethodField()
    total_tasks = serializers.SerializerMethodField()
    completed_tasks = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = Dream
        fields = [
            "id",
            "user",
            "title",
            "description",
            "category",
            "target_date",
            "priority",
            "status",
            "progress_percentage",
            "is_public",
            "milestones",
            "goals",
            "milestones_count",
            "completed_milestones_count",
            "goals_count",
            "completed_goal_count",
            "total_tasks",
            "completed_tasks",
            "days_left",
            "tags",
            "owner_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_milestones_count(self, obj) -> int:
        if hasattr(obj, "_milestones_count"):
            return obj._milestones_count
        return obj.milestones.count()

    def get_completed_milestones_count(self, obj) -> int:
        if hasattr(obj, "_completed_milestones_count"):
            return obj._completed_milestones_count
        return obj.milestones.filter(status="completed").count()

    def get_goals_count(self, obj) -> int:
        if hasattr(obj, "_goals_count"):
            return obj._goals_count
        return obj.goals.count()

    def get_completed_goal_count(self, obj) -> int:
        if hasattr(obj, "_completed_goals_count"):
            return obj._completed_goals_count
        return obj.goals.filter(status="completed").count()

    def get_total_tasks(self, obj) -> int:
        if hasattr(obj, "_total_tasks"):
            return obj._total_tasks
        return sum(len(g.tasks.all()) for g in obj.goals.all())

    def get_completed_tasks(self, obj) -> int:
        if hasattr(obj, "_completed_tasks"):
            return obj._completed_tasks
        return sum(
            len([t for t in g.tasks.all() if t.status == "completed"])
            for g in obj.goals.all()
        )

    def get_days_left(self, obj):
        if not obj.target_date:
            return None
        from django.utils import timezone

        delta = obj.target_date - timezone.now()
        return max(0, delta.days)

    def get_tags(self, obj) -> list:
        return list(obj.taggings.values_list("tag__name", flat=True))

    def get_owner_name(self, obj) -> str:
        return obj.user.display_name or ""


class ExploreDreamSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the Explore Dreams feed.
    Returns public dreams from other users with owner info."""

    owner_name = serializers.SerializerMethodField()
    owner_avatar = serializers.SerializerMethodField()
    goals_count = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    class Meta:
        model = Dream
        fields = [
            "id",
            "user",
            "title",
            "description",
            "category",
            "target_date",
            "priority",
            "status",
            "progress_percentage",
            "is_public",
            "owner_name",
            "owner_avatar",
            "goals_count",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_owner_name(self, obj) -> str:
        return obj.user.display_name or ""

    def get_owner_avatar(self, obj) -> str:
        return obj.user.get_effective_avatar_url()

    def get_goals_count(self, obj) -> int:
        if hasattr(obj, "_goals_count"):
            return obj._goals_count
        return obj.goals.count()

    def get_tags(self, obj) -> list:
        return list(obj.taggings.values_list("tag__name", flat=True))


class DreamCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating dreams."""

    class Meta:
        model = Dream
        fields = [
            "id",
            "title",
            "description",
            "category",
            "target_date",
            "priority",
            "color",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "title": {"help_text": "Short title for the new dream."},
            "description": {"help_text": "Detailed description of the dream."},
            "category": {"help_text": "Category the dream belongs to."},
            "target_date": {
                "help_text": "Target date for achieving the dream (min 1 month, max 3 years from now).",
                "required": False,
            },
            "priority": {
                "help_text": "Priority level of the dream.",
                "required": False,
            },
        }

    def validate_target_date(self, value):
        """Validate target_date is between 1 month and 3 years from now."""
        if value is None:
            return value
        from datetime import timedelta

        from django.utils import timezone as tz

        now = tz.now()
        min_date = now + timedelta(days=30)
        max_date = now + timedelta(days=1095)  # ~3 years
        if value < min_date:
            raise serializers.ValidationError(
                _("Target date must be at least 1 month from now.")
            )
        if value > max_date:
            raise serializers.ValidationError(
                _("Target date must be within 3 years from now.")
            )
        return value

    def validate_title(self, value):
        """Validate, sanitize, and moderate dream title."""
        value = sanitize_text(value)
        if len(value) < 3:
            raise serializers.ValidationError(
                _("Title must be at least 3 characters long")
            )

        from core.moderation import ContentModerationService

        result = ContentModerationService().moderate_text(value, context="dream_title")
        if result.is_flagged:
            raise serializers.ValidationError(result.user_message)

        return value

    def validate_description(self, value):
        """Validate, sanitize, and moderate dream description."""
        value = sanitize_text(value)
        if len(value) < 10:
            raise serializers.ValidationError(
                _("Description must be at least 10 characters long")
            )

        from core.moderation import ContentModerationService

        result = ContentModerationService().moderate_text(
            value, context="dream_description"
        )
        if result.is_flagged:
            raise serializers.ValidationError(result.user_message)

        return value

    def validate_category(self, value):
        """Sanitize category."""
        return sanitize_text(value)


class DreamUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating dreams."""

    class Meta:
        model = Dream
        fields = [
            "title",
            "description",
            "category",
            "target_date",
            "priority",
            "status",
            "is_public",
            "color",
        ]
        extra_kwargs = {
            "title": {"help_text": "Updated title for the dream."},
            "description": {"help_text": "Updated description of the dream."},
            "category": {"help_text": "Updated category for the dream."},
            "target_date": {
                "help_text": "Updated target date (min 1 month, max 3 years from now)."
            },
            "priority": {"help_text": "Updated priority level of the dream."},
            "status": {"help_text": "Updated status of the dream."},
        }

    def validate_target_date(self, value):
        """Validate target_date is between 1 month and 3 years from now."""
        if value is None:
            return value
        from datetime import timedelta

        from django.utils import timezone as tz

        now = tz.now()
        min_date = now + timedelta(days=30)
        max_date = now + timedelta(days=1095)  # ~3 years
        if value < min_date:
            raise serializers.ValidationError(
                _("Target date must be at least 1 month from now.")
            )
        if value > max_date:
            raise serializers.ValidationError(
                _("Target date must be within 3 years from now.")
            )
        return value

    def validate_title(self, value):
        """Sanitize and moderate title."""
        value = sanitize_text(value)

        if value:
            from core.moderation import ContentModerationService

            result = ContentModerationService().moderate_text(
                value, context="dream_title"
            )
            if result.is_flagged:
                raise serializers.ValidationError(result.user_message)

        return value

    def validate_description(self, value):
        """Sanitize and moderate description."""
        value = sanitize_text(value)

        if value:
            from core.moderation import ContentModerationService

            result = ContentModerationService().moderate_text(
                value, context="dream_description"
            )
            if result.is_flagged:
                raise serializers.ValidationError(result.user_message)

        return value

    def validate_category(self, value):
        """Sanitize category."""
        return sanitize_text(value)


class TaskCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating tasks with sanitization."""

    class Meta:
        model = Task
        fields = [
            "goal",
            "title",
            "description",
            "order",
            "scheduled_date",
            "scheduled_time",
            "duration_mins",
            "expected_date",
            "deadline_date",
            "recurrence",
            "is_two_minute_start",
            "chain_next_delay_days",
            "chain_template_title",
            "is_chain",
        ]
        extra_kwargs = {
            "goal": {"help_text": "The goal this task belongs to."},
            "title": {"help_text": "Short title for the new task."},
            "description": {"help_text": "Detailed description of the task."},
            "order": {"help_text": "Display order of the task within its goal.", "required": False},
            "scheduled_date": {"help_text": "Date when the task is scheduled."},
            "scheduled_time": {"help_text": "Time when the task is scheduled."},
            "duration_mins": {"help_text": "Estimated duration in minutes."},
            "expected_date": {"help_text": "Ideal/soft date to do this task."},
            "deadline_date": {"help_text": "Hard deadline for this task."},
            "recurrence": {"help_text": "Recurrence pattern for the task."},
            "is_two_minute_start": {
                "help_text": "Whether this is a two-minute quick-start task."
            },
            "chain_next_delay_days": {
                "help_text": "Days after completion to auto-create next task.",
                "required": False,
            },
            "chain_template_title": {
                "help_text": "Custom title for the next chained task.",
                "required": False,
            },
            "is_chain": {
                "help_text": "Whether this task is part of a recurring chain.",
                "required": False,
            },
        }

    def validate_title(self, value):
        """Sanitize title."""
        return sanitize_text(value)

    def validate_description(self, value):
        """Sanitize description."""
        return sanitize_text(value)

    def validate_chain_next_delay_days(self, value):
        """Validate chain delay is a positive number."""
        if value is not None and value < 1:
            raise serializers.ValidationError("Chain delay must be at least 1 day.")
        return value


class DreamTagSerializer(serializers.ModelSerializer):
    """Serializer for DreamTag model."""

    class Meta:
        model = DreamTag
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the tag."},
            "name": {"help_text": "Name of the tag."},
            "created_at": {"help_text": "Timestamp when the tag was created."},
        }


class SharedDreamSerializer(serializers.ModelSerializer):
    """Serializer for SharedDream model."""

    dream_title = serializers.CharField(
        source="dream.title", read_only=True, help_text="Title of the shared dream."
    )
    shared_by_name = serializers.CharField(
        source="shared_by.display_name",
        read_only=True,
        help_text="Display name of the user who shared the dream.",
    )
    shared_with_name = serializers.CharField(
        source="shared_with.display_name",
        read_only=True,
        help_text="Display name of the user the dream was shared with.",
    )

    class Meta:
        model = SharedDream
        fields = [
            "id",
            "dream",
            "dream_title",
            "shared_by",
            "shared_by_name",
            "shared_with",
            "shared_with_name",
            "permission",
            "created_at",
        ]
        read_only_fields = ["id", "shared_by", "created_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the shared dream record."},
            "dream": {"help_text": "The dream being shared."},
            "shared_by": {"help_text": "The user who shared the dream."},
            "shared_with": {"help_text": "The user the dream was shared with."},
            "permission": {"help_text": "Permission level granted to the shared user."},
            "created_at": {"help_text": "Timestamp when the dream was shared."},
        }


class ShareDreamRequestSerializer(serializers.Serializer):
    """Serializer for sharing a dream."""

    shared_with_id = serializers.UUIDField(
        help_text="UUID of the user to share the dream with."
    )
    permission = serializers.ChoiceField(
        choices=["view", "comment"],
        default="view",
        help_text="Permission level to grant (view or comment).",
    )


class AddTagSerializer(serializers.Serializer):
    """Serializer for adding a tag to a dream."""

    tag_name = serializers.CharField(max_length=50, help_text="Name of the tag to add.")

    def validate_tag_name(self, value):
        """Sanitize and validate tag name."""
        from core.validators import validate_tag_name

        return validate_tag_name(value)


class DreamTemplateSerializer(serializers.ModelSerializer):
    """Serializer for DreamTemplate model."""

    category_display = serializers.CharField(
        source="get_category_display",
        read_only=True,
        help_text="Human-readable category name.",
    )
    difficulty_display = serializers.CharField(
        source="get_difficulty_display",
        read_only=True,
        help_text="Human-readable difficulty level.",
    )
    goals_count = serializers.SerializerMethodField(
        help_text="Number of goals in the template."
    )

    class Meta:
        model = DreamTemplate
        fields = [
            "id",
            "title",
            "description",
            "category",
            "category_display",
            "template_goals",
            "estimated_duration_days",
            "suggested_timeline",
            "difficulty",
            "difficulty_display",
            "icon",
            "color",
            "is_featured",
            "usage_count",
            "goals_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "usage_count", "created_at", "updated_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the template."},
            "title": {"help_text": "Title of the dream template."},
            "description": {"help_text": "Description of what the template provides."},
            "category": {"help_text": "Category of the template."},
            "template_goals": {
                "help_text": "Predefined goals included in the template."
            },
            "estimated_duration_days": {
                "help_text": "Estimated number of days to complete."
            },
            "suggested_timeline": {"help_text": "Human-readable suggested timeline."},
            "difficulty": {"help_text": "Difficulty level of the template."},
            "icon": {"help_text": "Icon identifier for the template."},
            "color": {"help_text": "Accent color for template display."},
            "is_featured": {"help_text": "Whether the template is featured."},
            "usage_count": {
                "help_text": "Number of times this template has been used."
            },
            "created_at": {"help_text": "Timestamp when the template was created."},
            "updated_at": {
                "help_text": "Timestamp when the template was last updated."
            },
        }

    def get_goals_count(self, obj) -> int:
        return len(obj.template_goals) if obj.template_goals else 0


class DreamCollaboratorSerializer(serializers.ModelSerializer):
    """Serializer for DreamCollaborator model."""

    user_display_name = serializers.CharField(
        source="user.display_name",
        read_only=True,
        help_text="Display name of the collaborator.",
    )
    user_avatar = serializers.SerializerMethodField(
        help_text="Avatar URL of the collaborator.",
    )
    dream_title = serializers.CharField(
        source="dream.title", read_only=True, help_text="Title of the associated dream."
    )

    class Meta:
        model = DreamCollaborator
        fields = [
            "id",
            "dream",
            "dream_title",
            "user",
            "user_display_name",
            "user_avatar",
            "role",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the collaborator record."},
            "dream": {"help_text": "The dream being collaborated on."},
            "user": {"help_text": "The collaborating user."},
            "role": {"help_text": "Role of the collaborator on this dream."},
            "created_at": {"help_text": "Timestamp when the collaborator was added."},
        }

    def get_user_avatar(self, obj) -> str:
        return obj.user.get_effective_avatar_url()


class AddCollaboratorSerializer(serializers.Serializer):
    """Serializer for adding a collaborator to a dream."""

    user_id = serializers.UUIDField(
        help_text="UUID of the user to add as collaborator."
    )
    role = serializers.ChoiceField(
        choices=["collaborator", "viewer"],
        default="viewer",
        help_text="Role for the collaborator.",
    )


class VisionBoardImageSerializer(serializers.ModelSerializer):
    """Serializer for VisionBoardImage model."""

    signed_image_url = serializers.SerializerMethodField()

    class Meta:
        model = VisionBoardImage
        fields = [
            "id",
            "dream",
            "image_url",
            "image_file",
            "signed_image_url",
            "caption",
            "is_ai_generated",
            "order",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "signed_image_url"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the vision board image."},
            "dream": {"help_text": "The dream this image belongs to."},
            "image_url": {"help_text": "URL of the vision board image."},
            "image_file": {"help_text": "Uploaded image file for the vision board."},
            "caption": {"help_text": "Caption describing the image."},
            "is_ai_generated": {"help_text": "Whether the image was generated by AI."},
            "order": {"help_text": "Display order of the image on the vision board."},
            "created_at": {"help_text": "Timestamp when the image was added."},
        }

    def get_signed_image_url(self, obj):
        from core.storage import presigned_url

        if obj.image_url:
            return obj.image_url
        return presigned_url(obj.image_file)


class ProgressPhotoSerializer(serializers.ModelSerializer):
    """Serializer for ProgressPhoto model."""

    ai_analysis_data = serializers.SerializerMethodField(
        help_text="Parsed AI analysis data (JSON object or null)."
    )
    signed_image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProgressPhoto
        fields = [
            "id",
            "dream",
            "image",
            "signed_image_url",
            "caption",
            "ai_analysis",
            "ai_analysis_data",
            "taken_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "ai_analysis", "created_at", "updated_at", "signed_image_url"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the progress photo."},
            "dream": {"help_text": "The dream this progress photo belongs to."},
            "image": {"help_text": "Uploaded progress photo file."},
            "caption": {"help_text": "User caption for the progress photo."},
            "ai_analysis": {"help_text": "Raw AI analysis text."},
            "taken_at": {"help_text": "When the progress photo was taken."},
            "created_at": {"help_text": "Timestamp when the photo was uploaded."},
            "updated_at": {"help_text": "Timestamp when the photo was last updated."},
        }

    def get_signed_image_url(self, obj):
        from core.storage import presigned_url

        return presigned_url(obj.image)

    def get_ai_analysis_data(self, obj):
        """Parse the AI analysis JSON if available."""
        if not obj.ai_analysis:
            return None
        try:
            import json

            return json.loads(obj.ai_analysis)
        except (json.JSONDecodeError, TypeError):
            return {"analysis": obj.ai_analysis}


class GoalCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating goals with sanitization."""

    class Meta:
        model = Goal
        fields = [
            "dream",
            "milestone",
            "title",
            "description",
            "order",
            "estimated_minutes",
            "scheduled_start",
            "scheduled_end",
            "expected_date",
            "deadline_date",
            "reminder_enabled",
            "reminder_time",
        ]
        extra_kwargs = {
            "dream": {"help_text": "The dream this goal belongs to."},
            "milestone": {
                "help_text": "The milestone this goal belongs to.",
                "required": False,
            },
            "title": {"help_text": "Short title for the new goal."},
            "description": {"help_text": "Detailed description of the goal."},
            "order": {"help_text": "Display order of the goal within its milestone.", "required": False},
            "estimated_minutes": {
                "help_text": "Estimated time to complete in minutes."
            },
            "scheduled_start": {"help_text": "Scheduled start date for the goal."},
            "scheduled_end": {"help_text": "Scheduled end date for the goal."},
            "expected_date": {"help_text": "Ideal/soft date to complete this goal."},
            "deadline_date": {"help_text": "Hard deadline for this goal."},
            "reminder_enabled": {
                "help_text": "Whether reminders are enabled for this goal."
            },
            "reminder_time": {"help_text": "Time of day to send the reminder."},
        }

    def validate_title(self, value):
        """Sanitize title."""
        return sanitize_text(value)

    def validate_description(self, value):
        """Sanitize description."""
        return sanitize_text(value)


class FocusSessionSerializer(serializers.ModelSerializer):
    """Serializer for FocusSession model."""

    task_title = serializers.CharField(
        source="task.title", read_only=True, default=None
    )

    class Meta:
        model = FocusSession
        fields = [
            "id",
            "user",
            "task",
            "task_title",
            "duration_minutes",
            "actual_minutes",
            "session_type",
            "completed",
            "started_at",
            "ended_at",
        ]
        read_only_fields = ["id", "user", "started_at", "ended_at", "task_title"]


class FocusSessionStartSerializer(serializers.Serializer):
    """Serializer for starting a focus session."""

    task_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional task to associate with the session.",
    )
    duration_minutes = serializers.IntegerField(
        min_value=1, max_value=120, help_text="Planned duration in minutes."
    )
    session_type = serializers.ChoiceField(choices=["work", "break"], default="work")


class FocusSessionCompleteSerializer(serializers.Serializer):
    """Serializer for completing a focus session."""

    session_id = serializers.UUIDField(help_text="ID of the session to complete.")
    actual_minutes = serializers.IntegerField(
        min_value=0, help_text="Actual minutes focused."
    )


class DreamJournalSerializer(serializers.ModelSerializer):
    """Serializer for DreamJournal model."""

    class Meta:
        model = DreamJournal
        fields = [
            "id",
            "dream",
            "title",
            "content",
            "mood",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the journal entry."},
            "dream": {"help_text": "The dream this journal entry belongs to."},
            "title": {"help_text": "Optional title for the journal entry."},
            "content": {"help_text": "Journal entry content (HTML or markdown)."},
            "mood": {"help_text": "Mood tag for the entry."},
            "created_at": {"help_text": "Timestamp when the entry was created."},
            "updated_at": {"help_text": "Timestamp when the entry was last updated."},
        }

    def validate_title(self, value):
        """Sanitize title."""
        return sanitize_text(value)

    def validate_content(self, value):
        """Sanitize content."""
        return sanitize_text(value)


class PlanCheckInSerializer(serializers.ModelSerializer):
    """Serializer for PlanCheckIn list view."""

    class Meta:
        model = PlanCheckIn
        fields = [
            "id",
            "dream",
            "status",
            "pace_status",
            "triggered_by",
            "progress_at_checkin",
            "tasks_completed_since_last",
            "tasks_overdue_at_checkin",
            "coaching_message",
            "adjustment_summary",
            "tasks_created",
            "milestones_adjusted",
            "months_generated_through",
            "scheduled_for",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields


class PlanCheckInDetailSerializer(PlanCheckInSerializer):
    """Detailed serializer with questionnaire and responses."""

    class Meta(PlanCheckInSerializer.Meta):
        fields = PlanCheckInSerializer.Meta.fields + [
            "questionnaire",
            "user_responses",
            "ai_actions",
            "error_message",
        ]
        read_only_fields = fields


class CheckInResponseSubmitSerializer(serializers.Serializer):
    """Serializer for submitting questionnaire responses."""

    responses = serializers.DictField(
        child=serializers.JSONField(),
        help_text="Map of question_id to answer value (int for slider, str for text/choice)",
    )
