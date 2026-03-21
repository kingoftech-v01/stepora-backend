"""
Serializers for the Plans system.
"""

from rest_framework import serializers

from .models import (
    CalibrationResponse,
    DreamMilestone,
    DreamProgressSnapshot,
    FocusSession,
    Goal,
    Obstacle,
    PlanCheckIn,
    Task,
)


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for Task model."""

    chain_position = serializers.SerializerMethodField(
        help_text="Position of this task within its chain."
    )
    xp = serializers.SerializerMethodField(
        help_text="XP reward for completing this task."
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
            "xp",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "completed_at",
            "chain_position",
            "xp",
        ]

    def get_chain_position(self, obj):
        pos, total = obj.get_chain_position()
        if pos is None:
            return None
        return {"position": pos, "total": total}

    def get_xp(self, obj):
        return max(10, (obj.duration_mins or 30) // 3)


class TaskCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating tasks."""

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
        ]


class GoalSerializer(serializers.ModelSerializer):
    """Serializer for Goal model."""

    tasks = TaskSerializer(many=True, read_only=True)

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
            "reminder_enabled",
            "reminder_time",
            "progress_percentage",
            "tasks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "completed_at",
            "progress_percentage",
        ]


class GoalCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating goals."""

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


class DreamMilestoneSerializer(serializers.ModelSerializer):
    """Serializer for DreamMilestone model."""

    goals = GoalSerializer(many=True, read_only=True)

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
            "has_tasks",
            "goals",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "completed_at",
            "progress_percentage",
        ]


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
        read_only_fields = ["id", "created_at"]


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
        help_text="Map of question_id to answer value",
    )


class DreamProgressSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for DreamProgressSnapshot model."""

    class Meta:
        model = DreamProgressSnapshot
        fields = [
            "id",
            "dream",
            "date",
            "progress_percentage",
            "created_at",
        ]
        read_only_fields = fields


class FocusSessionSerializer(serializers.ModelSerializer):
    """Serializer for FocusSession model."""

    class Meta:
        model = FocusSession
        fields = [
            "id",
            "user",
            "task",
            "duration_minutes",
            "actual_minutes",
            "session_type",
            "completed",
            "started_at",
            "ended_at",
        ]
        read_only_fields = ["id", "user", "started_at"]


class FocusSessionStartSerializer(serializers.Serializer):
    """Serializer for starting a focus session."""

    task_id = serializers.UUIDField(required=False, allow_null=True)
    duration_minutes = serializers.IntegerField(min_value=1, max_value=120)
    session_type = serializers.ChoiceField(
        choices=["work", "break"], default="work"
    )


class FocusSessionCompleteSerializer(serializers.Serializer):
    """Serializer for completing a focus session."""

    session_id = serializers.UUIDField()
    actual_minutes = serializers.IntegerField(min_value=0)
