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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the task.'},
            'goal': {'help_text': 'The goal this task belongs to.'},
            'title': {'help_text': 'Short title of the task.'},
            'description': {'help_text': 'Detailed description of the task.'},
            'order': {'help_text': 'Display order of the task within its goal.'},
            'scheduled_date': {'help_text': 'Date when the task is scheduled.'},
            'scheduled_time': {'help_text': 'Time when the task is scheduled.'},
            'duration_mins': {'help_text': 'Estimated duration in minutes.'},
            'recurrence': {'help_text': 'Recurrence pattern for the task.'},
            'status': {'help_text': 'Current status of the task.'},
            'completed_at': {'help_text': 'Timestamp when the task was completed.'},
            'is_two_minute_start': {'help_text': 'Whether this is a two-minute quick-start task.'},
            'created_at': {'help_text': 'Timestamp when the task was created.'},
            'updated_at': {'help_text': 'Timestamp when the task was last updated.'},
        }


class GoalSerializer(serializers.ModelSerializer):
    """Serializer for Goal model."""

    tasks = TaskSerializer(many=True, read_only=True, help_text='List of tasks under this goal.')
    tasks_count = serializers.SerializerMethodField(help_text='Total number of tasks in this goal.')
    completed_tasks_count = serializers.SerializerMethodField(help_text='Number of completed tasks in this goal.')

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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the goal.'},
            'dream': {'help_text': 'The dream this goal belongs to.'},
            'title': {'help_text': 'Short title of the goal.'},
            'description': {'help_text': 'Detailed description of the goal.'},
            'order': {'help_text': 'Display order of the goal within its dream.'},
            'estimated_minutes': {'help_text': 'Estimated time to complete in minutes.'},
            'scheduled_start': {'help_text': 'Scheduled start date for the goal.'},
            'scheduled_end': {'help_text': 'Scheduled end date for the goal.'},
            'status': {'help_text': 'Current status of the goal.'},
            'completed_at': {'help_text': 'Timestamp when the goal was completed.'},
            'progress_percentage': {'help_text': 'Percentage of goal completion.'},
            'reminder_enabled': {'help_text': 'Whether reminders are enabled for this goal.'},
            'reminder_time': {'help_text': 'Time of day to send the reminder.'},
            'created_at': {'help_text': 'Timestamp when the goal was created.'},
            'updated_at': {'help_text': 'Timestamp when the goal was last updated.'},
        }

    def get_tasks_count(self, obj) -> int:
        # Use len() to leverage prefetched data instead of .count() which hits DB
        return len(obj.tasks.all())

    def get_completed_tasks_count(self, obj) -> int:
        return len([t for t in obj.tasks.all() if t.status == 'completed'])


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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the obstacle.'},
            'dream': {'help_text': 'The dream this obstacle is associated with.'},
            'title': {'help_text': 'Short title of the obstacle.'},
            'description': {'help_text': 'Detailed description of the obstacle.'},
            'obstacle_type': {'help_text': 'Category or type of the obstacle.'},
            'solution': {'help_text': 'Proposed solution to overcome the obstacle.'},
            'status': {'help_text': 'Current status of the obstacle.'},
            'created_at': {'help_text': 'Timestamp when the obstacle was created.'},
            'updated_at': {'help_text': 'Timestamp when the obstacle was last updated.'},
        }


class DreamSerializer(serializers.ModelSerializer):
    """Basic serializer for Dream model."""

    goals_count = serializers.SerializerMethodField(help_text='Total number of goals for this dream.')
    tasks_count = serializers.SerializerMethodField(help_text='Total number of tasks across all goals.')
    tags = serializers.SerializerMethodField(help_text='List of tag names associated with this dream.')
    sparkline_data = serializers.SerializerMethodField(help_text='Last 7 progress snapshots for sparkline charts.')

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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the dream.'},
            'user': {'help_text': 'The user who owns this dream.'},
            'title': {'help_text': 'Short title of the dream.'},
            'description': {'help_text': 'Detailed description of the dream.'},
            'category': {'help_text': 'Category the dream belongs to.'},
            'target_date': {'help_text': 'Target date for achieving the dream.'},
            'priority': {'help_text': 'Priority level of the dream.'},
            'status': {'help_text': 'Current status of the dream.'},
            'progress_percentage': {'help_text': 'Overall completion percentage of the dream.'},
            'completed_at': {'help_text': 'Timestamp when the dream was completed.'},
            'has_two_minute_start': {'help_text': 'Whether a two-minute quick-start task exists.'},
            'vision_image_url': {'help_text': 'URL of the vision board image.'},
            'calibration_status': {'help_text': 'Status of the dream calibration process.'},
            'created_at': {'help_text': 'Timestamp when the dream was created.'},
            'updated_at': {'help_text': 'Timestamp when the dream was last updated.'},
        }

    def get_goals_count(self, obj) -> int:
        if hasattr(obj, '_goals_count'):
            return obj._goals_count
        return obj.goals.count()

    def get_tasks_count(self, obj) -> int:
        if hasattr(obj, '_tasks_count'):
            return obj._tasks_count
        return sum(len(goal.tasks.all()) for goal in obj.goals.all())

    def get_tags(self, obj) -> list:
        if hasattr(obj, '_prefetched_tags'):
            return obj._prefetched_tags
        return list(obj.taggings.values_list('tag__name', flat=True))

    def get_sparkline_data(self, obj) -> list:
        """Return last 7 progress snapshots for sparkline chart."""
        if hasattr(obj, '_prefetched_sparkline'):
            return obj._prefetched_sparkline
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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the calibration response.'},
            'dream': {'help_text': 'The dream this calibration response belongs to.'},
            'question': {'help_text': 'The calibration question text.'},
            'answer': {'help_text': 'The user answer to the calibration question.'},
            'question_number': {'help_text': 'Order number of the question in the sequence.'},
            'category': {'help_text': 'Category of the calibration question.'},
            'created_at': {'help_text': 'Timestamp when the response was created.'},
        }


class DreamDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Dream with nested goals and tasks."""

    goals = GoalSerializer(many=True, read_only=True, help_text='List of goals for this dream.')
    obstacles = ObstacleSerializer(many=True, read_only=True, help_text='List of obstacles for this dream.')
    calibration_responses = CalibrationResponseSerializer(many=True, read_only=True, help_text='List of calibration responses for this dream.')
    goals_count = serializers.SerializerMethodField()
    completed_goal_count = serializers.SerializerMethodField()
    total_tasks = serializers.SerializerMethodField()
    completed_tasks = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

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
            'goals_count', 'completed_goal_count',
            'total_tasks', 'completed_tasks',
            'days_left', 'tags',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'progress_percentage', 'ai_analysis', 'created_at', 'updated_at']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the dream.'},
            'user': {'help_text': 'The user who owns this dream.'},
            'title': {'help_text': 'Short title of the dream.'},
            'description': {'help_text': 'Detailed description of the dream.'},
            'category': {'help_text': 'Category the dream belongs to.'},
            'target_date': {'help_text': 'Target date for achieving the dream.'},
            'priority': {'help_text': 'Priority level of the dream.'},
            'status': {'help_text': 'Current status of the dream.'},
            'ai_analysis': {'help_text': 'AI-generated analysis of the dream.'},
            'vision_image_url': {'help_text': 'URL of the vision board image.'},
            'progress_percentage': {'help_text': 'Overall completion percentage of the dream.'},
            'completed_at': {'help_text': 'Timestamp when the dream was completed.'},
            'has_two_minute_start': {'help_text': 'Whether a two-minute quick-start task exists.'},
            'calibration_status': {'help_text': 'Status of the dream calibration process.'},
            'created_at': {'help_text': 'Timestamp when the dream was created.'},
            'updated_at': {'help_text': 'Timestamp when the dream was last updated.'},
        }

    def get_goals_count(self, obj) -> int:
        if hasattr(obj, '_goals_count'):
            return obj._goals_count
        return obj.goals.count()

    def get_completed_goal_count(self, obj) -> int:
        if hasattr(obj, '_completed_goals_count'):
            return obj._completed_goals_count
        return obj.goals.filter(status='completed').count()

    def get_total_tasks(self, obj) -> int:
        if hasattr(obj, '_total_tasks'):
            return obj._total_tasks
        return sum(len(goal.tasks.all()) for goal in obj.goals.all())

    def get_completed_tasks(self, obj) -> int:
        if hasattr(obj, '_completed_tasks'):
            return obj._completed_tasks
        return sum(
            len([t for t in goal.tasks.all() if t.status == 'completed'])
            for goal in obj.goals.all()
        )

    def get_days_left(self, obj):
        if not obj.target_date:
            return None
        from django.utils import timezone
        delta = obj.target_date - timezone.now()
        return max(0, delta.days)

    def get_tags(self, obj) -> list:
        if hasattr(obj, '_prefetched_tags'):
            return obj._prefetched_tags
        return list(obj.taggings.values_list('tag__name', flat=True))


class DreamCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating dreams."""

    class Meta:
        model = Dream
        fields = [
            'id', 'title', 'description', 'category',
            'target_date', 'priority'
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'title': {'help_text': 'Short title for the new dream.'},
            'description': {'help_text': 'Detailed description of the dream.'},
            'category': {'help_text': 'Category the dream belongs to.'},
            'target_date': {'help_text': 'Target date for achieving the dream.', 'required': False},
            'priority': {'help_text': 'Priority level of the dream.', 'required': False},
        }

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
        """Validate, sanitize, and moderate dream description."""
        value = sanitize_text(value)
        if len(value) < 10:
            raise serializers.ValidationError("Description must be at least 10 characters long")

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
        extra_kwargs = {
            'title': {'help_text': 'Updated title for the dream.'},
            'description': {'help_text': 'Updated description of the dream.'},
            'category': {'help_text': 'Updated category for the dream.'},
            'target_date': {'help_text': 'Updated target date for achieving the dream.'},
            'priority': {'help_text': 'Updated priority level of the dream.'},
            'status': {'help_text': 'Updated status of the dream.'},
        }

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
        extra_kwargs = {
            'goal': {'help_text': 'The goal this task belongs to.'},
            'title': {'help_text': 'Short title for the new task.'},
            'description': {'help_text': 'Detailed description of the task.'},
            'order': {'help_text': 'Display order of the task within its goal.'},
            'scheduled_date': {'help_text': 'Date when the task is scheduled.'},
            'scheduled_time': {'help_text': 'Time when the task is scheduled.'},
            'duration_mins': {'help_text': 'Estimated duration in minutes.'},
            'recurrence': {'help_text': 'Recurrence pattern for the task.'},
            'is_two_minute_start': {'help_text': 'Whether this is a two-minute quick-start task.'},
        }

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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the tag.'},
            'name': {'help_text': 'Name of the tag.'},
            'created_at': {'help_text': 'Timestamp when the tag was created.'},
        }


class SharedDreamSerializer(serializers.ModelSerializer):
    """Serializer for SharedDream model."""

    dream_title = serializers.CharField(source='dream.title', read_only=True, help_text='Title of the shared dream.')
    shared_by_name = serializers.CharField(source='shared_by.display_name', read_only=True, help_text='Display name of the user who shared the dream.')
    shared_with_name = serializers.CharField(source='shared_with.display_name', read_only=True, help_text='Display name of the user the dream was shared with.')

    class Meta:
        model = SharedDream
        fields = [
            'id', 'dream', 'dream_title',
            'shared_by', 'shared_by_name',
            'shared_with', 'shared_with_name',
            'permission', 'created_at'
        ]
        read_only_fields = ['id', 'shared_by', 'created_at']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the shared dream record.'},
            'dream': {'help_text': 'The dream being shared.'},
            'shared_by': {'help_text': 'The user who shared the dream.'},
            'shared_with': {'help_text': 'The user the dream was shared with.'},
            'permission': {'help_text': 'Permission level granted to the shared user.'},
            'created_at': {'help_text': 'Timestamp when the dream was shared.'},
        }


class ShareDreamRequestSerializer(serializers.Serializer):
    """Serializer for sharing a dream."""

    shared_with_id = serializers.UUIDField(
        help_text='UUID of the user to share the dream with.'
    )
    permission = serializers.ChoiceField(
        choices=['view', 'comment'],
        default='view',
        help_text='Permission level to grant (view or comment).',
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

    category_display = serializers.CharField(source='get_category_display', read_only=True, help_text='Human-readable category name.')
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True, help_text='Human-readable difficulty level.')

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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the template.'},
            'title': {'help_text': 'Title of the dream template.'},
            'description': {'help_text': 'Description of what the template provides.'},
            'category': {'help_text': 'Category of the template.'},
            'template_goals': {'help_text': 'Predefined goals included in the template.'},
            'estimated_duration_days': {'help_text': 'Estimated number of days to complete.'},
            'difficulty': {'help_text': 'Difficulty level of the template.'},
            'icon': {'help_text': 'Icon identifier for the template.'},
            'is_featured': {'help_text': 'Whether the template is featured.'},
            'usage_count': {'help_text': 'Number of times this template has been used.'},
            'created_at': {'help_text': 'Timestamp when the template was created.'},
            'updated_at': {'help_text': 'Timestamp when the template was last updated.'},
        }


class DreamCollaboratorSerializer(serializers.ModelSerializer):
    """Serializer for DreamCollaborator model."""

    user_display_name = serializers.CharField(source='user.display_name', read_only=True, help_text='Display name of the collaborator.')
    user_avatar = serializers.CharField(source='user.avatar_url', read_only=True, help_text='Avatar URL of the collaborator.')
    dream_title = serializers.CharField(source='dream.title', read_only=True, help_text='Title of the associated dream.')

    class Meta:
        model = DreamCollaborator
        fields = [
            'id', 'dream', 'dream_title',
            'user', 'user_display_name', 'user_avatar',
            'role', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the collaborator record.'},
            'dream': {'help_text': 'The dream being collaborated on.'},
            'user': {'help_text': 'The collaborating user.'},
            'role': {'help_text': 'Role of the collaborator on this dream.'},
            'created_at': {'help_text': 'Timestamp when the collaborator was added.'},
        }


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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the vision board image.'},
            'dream': {'help_text': 'The dream this image belongs to.'},
            'image_url': {'help_text': 'URL of the vision board image.'},
            'image_file': {'help_text': 'Uploaded image file for the vision board.'},
            'caption': {'help_text': 'Caption describing the image.'},
            'is_ai_generated': {'help_text': 'Whether the image was generated by AI.'},
            'order': {'help_text': 'Display order of the image on the vision board.'},
            'created_at': {'help_text': 'Timestamp when the image was added.'},
        }


class GoalCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating goals with sanitization."""

    class Meta:
        model = Goal
        fields = [
            'dream', 'title', 'description', 'order',
            'estimated_minutes', 'scheduled_start', 'scheduled_end',
            'reminder_enabled', 'reminder_time'
        ]
        extra_kwargs = {
            'dream': {'help_text': 'The dream this goal belongs to.'},
            'title': {'help_text': 'Short title for the new goal.'},
            'description': {'help_text': 'Detailed description of the goal.'},
            'order': {'help_text': 'Display order of the goal within its dream.'},
            'estimated_minutes': {'help_text': 'Estimated time to complete in minutes.'},
            'scheduled_start': {'help_text': 'Scheduled start date for the goal.'},
            'scheduled_end': {'help_text': 'Scheduled end date for the goal.'},
            'reminder_enabled': {'help_text': 'Whether reminders are enabled for this goal.'},
            'reminder_time': {'help_text': 'Time of day to send the reminder.'},
        }

    def validate_title(self, value):
        """Sanitize title."""
        return sanitize_text(value)

    def validate_description(self, value):
        """Sanitize description."""
        return sanitize_text(value)
