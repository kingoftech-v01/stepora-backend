"""
Serializers for Dreams app.
"""

from rest_framework import serializers
from core.sanitizers import sanitize_text
from .models import Dream, Goal, Task, Obstacle, CalibrationResponse, DreamTag, DreamTagging, SharedDream, DreamTemplate, DreamCollaborator, VisionBoardImage


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
    tags = serializers.SerializerMethodField()
    sparkline_data = serializers.SerializerMethodField()

    class Meta:
        model = Dream
        fields = [
            'id', 'user', 'title', 'description', 'category',
            'target_date', 'priority', 'status',
            'progress_percentage', 'completed_at',
            'has_two_minute_start', 'vision_image_url',
            'calibration_status',
            'goals_count', 'tasks_count', 'tags',
            'sparkline_data',
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

    def get_tags(self, obj):
        return list(obj.taggings.values_list('tag__name', flat=True))

    def get_sparkline_data(self, obj):
        """Return last 7 progress snapshots for sparkline chart."""
        from .models import DreamProgressSnapshot
        snapshots = DreamProgressSnapshot.objects.filter(
            dream=obj
        ).order_by('-date')[:7]
        return list(reversed([
            {'date': str(s.date), 'progress': s.progress_percentage}
            for s in snapshots
        ]))


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
        """Validate, sanitize, and moderate dream title."""
        value = sanitize_text(value)
        if len(value) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters long")

        from core.moderation import ContentModerationService
        result = ContentModerationService().moderate_text(value, context='dream_title')
        if result.is_flagged:
            raise serializers.ValidationError(result.user_message)

        return value

    def validate_description(self, value):
        """Sanitize and moderate dream description."""
        value = sanitize_text(value)

        if value:
            from core.moderation import ContentModerationService
            result = ContentModerationService().moderate_text(value, context='dream_description')
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
            'title', 'description', 'category',
            'target_date', 'priority', 'status'
        ]

    def validate_title(self, value):
        """Sanitize and moderate title."""
        value = sanitize_text(value)

        if value:
            from core.moderation import ContentModerationService
            result = ContentModerationService().moderate_text(value, context='dream_title')
            if result.is_flagged:
                raise serializers.ValidationError(result.user_message)

        return value

    def validate_description(self, value):
        """Sanitize and moderate description."""
        value = sanitize_text(value)

        if value:
            from core.moderation import ContentModerationService
            result = ContentModerationService().moderate_text(value, context='dream_description')
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
            'goal', 'title', 'description', 'order',
            'scheduled_date', 'scheduled_time', 'duration_mins',
            'recurrence', 'is_two_minute_start'
        ]

    def validate_title(self, value):
        """Sanitize title."""
        return sanitize_text(value)

    def validate_description(self, value):
        """Sanitize description."""
        return sanitize_text(value)


class DreamTagSerializer(serializers.ModelSerializer):
    """Serializer for DreamTag model."""

    class Meta:
        model = DreamTag
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']


class SharedDreamSerializer(serializers.ModelSerializer):
    """Serializer for SharedDream model."""

    dream_title = serializers.CharField(source='dream.title', read_only=True)
    shared_by_name = serializers.CharField(source='shared_by.display_name', read_only=True)
    shared_with_name = serializers.CharField(source='shared_with.display_name', read_only=True)

    class Meta:
        model = SharedDream
        fields = [
            'id', 'dream', 'dream_title',
            'shared_by', 'shared_by_name',
            'shared_with', 'shared_with_name',
            'permission', 'created_at'
        ]
        read_only_fields = ['id', 'shared_by', 'created_at']


class ShareDreamRequestSerializer(serializers.Serializer):
    """Serializer for sharing a dream."""

    shared_with_id = serializers.UUIDField(
        help_text='UUID of the user to share the dream with.'
    )
    permission = serializers.ChoiceField(
        choices=['view', 'comment'],
        default='view',
    )


class AddTagSerializer(serializers.Serializer):
    """Serializer for adding a tag to a dream."""

    tag_name = serializers.CharField(
        max_length=50,
        help_text='Name of the tag to add.'
    )

    def validate_tag_name(self, value):
        """Sanitize and validate tag name."""
        from core.validators import validate_tag_name
        return validate_tag_name(value)


class DreamTemplateSerializer(serializers.ModelSerializer):
    """Serializer for DreamTemplate model."""

    category_display = serializers.CharField(source='get_category_display', read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)

    class Meta:
        model = DreamTemplate
        fields = [
            'id', 'title', 'description', 'category', 'category_display',
            'template_goals', 'estimated_duration_days',
            'difficulty', 'difficulty_display',
            'icon', 'is_featured', 'usage_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'usage_count', 'created_at', 'updated_at']


class DreamCollaboratorSerializer(serializers.ModelSerializer):
    """Serializer for DreamCollaborator model."""

    user_display_name = serializers.CharField(source='user.display_name', read_only=True)
    user_avatar = serializers.CharField(source='user.avatar_url', read_only=True)
    dream_title = serializers.CharField(source='dream.title', read_only=True)

    class Meta:
        model = DreamCollaborator
        fields = [
            'id', 'dream', 'dream_title',
            'user', 'user_display_name', 'user_avatar',
            'role', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class AddCollaboratorSerializer(serializers.Serializer):
    """Serializer for adding a collaborator to a dream."""

    user_id = serializers.UUIDField(help_text='UUID of the user to add as collaborator.')
    role = serializers.ChoiceField(
        choices=['collaborator', 'viewer'],
        default='viewer',
        help_text='Role for the collaborator.',
    )


class VisionBoardImageSerializer(serializers.ModelSerializer):
    """Serializer for VisionBoardImage model."""

    class Meta:
        model = VisionBoardImage
        fields = [
            'id', 'dream', 'image_url', 'image_file',
            'caption', 'is_ai_generated', 'order',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class GoalCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating goals with sanitization."""

    class Meta:
        model = Goal
        fields = [
            'dream', 'title', 'description', 'order',
            'estimated_minutes', 'scheduled_start', 'scheduled_end',
            'reminder_enabled', 'reminder_time'
        ]

    def validate_title(self, value):
        """Sanitize title."""
        return sanitize_text(value)

    def validate_description(self, value):
        """Sanitize description."""
        return sanitize_text(value)
