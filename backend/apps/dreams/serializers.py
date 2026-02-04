"""
Serializers for Dreams app.
"""

from rest_framework import serializers
from core.sanitizers import sanitize_text
from .models import Dream, Goal, Task, Obstacle, CalibrationResponse


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for Task model."""

    class Meta:
        model = Task
        fields = [
            'id', 'goal', 'title', 'description', 'order',
            'scheduled_date', 'scheduled_time', 'duration_mins',
            'recurrence', 'status', 'completed_at',
            'is_two_minute_start',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at']


class GoalSerializer(serializers.ModelSerializer):
    """Serializer for Goal model."""

    tasks = TaskSerializer(many=True, read_only=True)
    tasks_count = serializers.SerializerMethodField()
    completed_tasks_count = serializers.SerializerMethodField()

    class Meta:
        model = Goal
        fields = [
            'id', 'dream', 'title', 'description', 'order',
            'estimated_minutes', 'scheduled_start', 'scheduled_end',
            'status', 'completed_at', 'progress_percentage',
            'reminder_enabled', 'reminder_time',
            'tasks', 'tasks_count', 'completed_tasks_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'progress_percentage', 'created_at', 'updated_at', 'completed_at']

    def get_tasks_count(self, obj):
        return obj.tasks.count()

    def get_completed_tasks_count(self, obj):
        return obj.tasks.filter(status='completed').count()


class ObstacleSerializer(serializers.ModelSerializer):
    """Serializer for Obstacle model."""

    class Meta:
        model = Obstacle
        fields = [
            'id', 'dream', 'title', 'description',
            'obstacle_type', 'solution', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DreamSerializer(serializers.ModelSerializer):
    """Basic serializer for Dream model."""

    goals_count = serializers.SerializerMethodField()
    tasks_count = serializers.SerializerMethodField()

    class Meta:
        model = Dream
        fields = [
            'id', 'user', 'title', 'description', 'category',
            'target_date', 'priority', 'status',
            'progress_percentage', 'completed_at',
            'has_two_minute_start', 'vision_image_url',
            'calibration_status',
            'goals_count', 'tasks_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'progress_percentage', 'created_at', 'updated_at', 'completed_at']

    def get_goals_count(self, obj):
        return obj.goals.count()

    def get_tasks_count(self, obj):
        total = 0
        for goal in obj.goals.all():
            total += goal.tasks.count()
        return total


class CalibrationResponseSerializer(serializers.ModelSerializer):
    """Serializer for CalibrationResponse model."""

    class Meta:
        model = CalibrationResponse
        fields = [
            'id', 'dream', 'question', 'answer', 'question_number',
            'category', 'created_at'
        ]
        read_only_fields = ['id', 'dream', 'question', 'question_number', 'category', 'created_at']


class DreamDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Dream with nested goals and tasks."""

    goals = GoalSerializer(many=True, read_only=True)
    obstacles = ObstacleSerializer(many=True, read_only=True)
    calibration_responses = CalibrationResponseSerializer(many=True, read_only=True)

    class Meta:
        model = Dream
        fields = [
            'id', 'user', 'title', 'description', 'category',
            'target_date', 'priority', 'status',
            'ai_analysis', 'vision_image_url',
            'progress_percentage', 'completed_at',
            'has_two_minute_start',
            'calibration_status', 'calibration_responses',
            'goals', 'obstacles',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'progress_percentage', 'ai_analysis', 'created_at', 'updated_at']


class DreamCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating dreams."""

    class Meta:
        model = Dream
        fields = [
            'title', 'description', 'category',
            'target_date', 'priority'
        ]

    def validate_title(self, value):
        """Validate and sanitize dream title."""
        value = sanitize_text(value)
        if len(value) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters long")
        return value

    def validate_description(self, value):
        """Sanitize dream description."""
        return sanitize_text(value)

    def validate_category(self, value):
        """Sanitize category."""
        return sanitize_text(value)


class DreamUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating dreams."""

    class Meta:
        model = Dream
        fields = [
            'title', 'description', 'category',
            'target_date', 'priority', 'status'
        ]

    def validate_title(self, value):
        """Sanitize title."""
        return sanitize_text(value)

    def validate_description(self, value):
        """Sanitize description."""
        return sanitize_text(value)

    def validate_category(self, value):
        """Sanitize category."""
        return sanitize_text(value)


class TaskCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating tasks with sanitization."""

    class Meta:
        model = Task
        fields = [
            'title', 'description', 'order',
            'scheduled_date', 'scheduled_time', 'duration_mins',
            'recurrence', 'is_two_minute_start'
        ]

    def validate_title(self, value):
        """Sanitize title."""
        return sanitize_text(value)

    def validate_description(self, value):
        """Sanitize description."""
        return sanitize_text(value)


class GoalCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating goals with sanitization."""

    class Meta:
        model = Goal
        fields = [
            'title', 'description', 'order',
            'estimated_minutes', 'scheduled_start', 'scheduled_end',
            'reminder_enabled', 'reminder_time'
        ]

    def validate_title(self, value):
        """Sanitize title."""
        return sanitize_text(value)

    def validate_description(self, value):
        """Sanitize description."""
        return sanitize_text(value)
