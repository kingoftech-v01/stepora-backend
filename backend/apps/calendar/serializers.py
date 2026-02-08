"""
Serializers for Calendar app.
"""

from rest_framework import serializers
from core.sanitizers import sanitize_text
from .models import CalendarEvent, TimeBlock


class CalendarEventSerializer(serializers.ModelSerializer):
    """Serializer for Calendar events."""

    task_title = serializers.CharField(source='task.title', read_only=True, allow_null=True)
    goal_title = serializers.CharField(source='task.goal.title', read_only=True, allow_null=True)
    dream_title = serializers.CharField(source='task.goal.dream.title', read_only=True, allow_null=True)

    class Meta:
        model = CalendarEvent
        fields = [
            'id', 'user', 'task', 'title', 'description',
            'start_time', 'end_time', 'location',
            'reminder_minutes_before', 'status',
            'is_recurring', 'recurrence_rule', 'parent_event',
            'task_title', 'goal_title', 'dream_title',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class CalendarEventCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating calendar events."""

    force = serializers.BooleanField(required=False, default=False, write_only=True)

    class Meta:
        model = CalendarEvent
        fields = [
            'task', 'title', 'description',
            'start_time', 'end_time', 'location',
            'reminder_minutes_before',
            'is_recurring', 'recurrence_rule',
            'force',
        ]

    def validate_title(self, value):
        """Sanitize title to prevent XSS."""
        return sanitize_text(value)

    def validate_description(self, value):
        """Sanitize description to prevent XSS."""
        if value:
            return sanitize_text(value)
        return value

    def validate_location(self, value):
        """Sanitize location to prevent XSS."""
        if value:
            return sanitize_text(value)
        return value

    def validate(self, data):
        """Validate that end_time is after start_time."""
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time")
        return data


class CalendarEventRescheduleSerializer(serializers.Serializer):
    """Serializer for rescheduling a calendar event."""

    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    force = serializers.BooleanField(required=False, default=False)

    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time")
        return data


class SuggestTimeSlotsSerializer(serializers.Serializer):
    """Serializer for time slot suggestion request."""

    date = serializers.DateField()
    duration_mins = serializers.IntegerField(min_value=5, max_value=480)


class TimeBlockSerializer(serializers.ModelSerializer):
    """Serializer for Time blocks."""

    day_name = serializers.SerializerMethodField()

    class Meta:
        model = TimeBlock
        fields = [
            'id', 'user', 'block_type', 'day_of_week', 'day_name',
            'start_time', 'end_time', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def get_day_name(self, obj):
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return days[obj.day_of_week]

    def validate(self, data):
        """Validate time block."""
        if 'start_time' in data and 'end_time' in data:
            if data['start_time'] >= data['end_time']:
                raise serializers.ValidationError("End time must be after start time")

        if 'day_of_week' in data:
            if not 0 <= data['day_of_week'] <= 6:
                raise serializers.ValidationError("Day of week must be between 0 (Monday) and 6 (Sunday)")

        return data


class CalendarTaskSerializer(serializers.Serializer):
    """Serializer for tasks in calendar view."""

    task_id = serializers.UUIDField()
    task_title = serializers.CharField()
    goal_id = serializers.UUIDField()
    goal_title = serializers.CharField()
    dream_id = serializers.UUIDField()
    dream_title = serializers.CharField()
    scheduled_date = serializers.DateTimeField()
    scheduled_time = serializers.CharField(allow_blank=True)
    duration_mins = serializers.IntegerField()
    status = serializers.CharField()
    is_two_minute_start = serializers.BooleanField()
