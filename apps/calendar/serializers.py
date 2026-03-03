"""
Serializers for Calendar app.
"""

from rest_framework import serializers
from django.utils.translation import gettext as _
from core.sanitizers import sanitize_text
from .models import CalendarEvent, TimeBlock


class CalendarEventSerializer(serializers.ModelSerializer):
    """Serializer for Calendar events."""

    task_title = serializers.CharField(source='task.title', read_only=True, allow_null=True, help_text='Title of the linked task.')
    goal_title = serializers.CharField(source='task.goal.title', read_only=True, allow_null=True, help_text='Title of the goal the task belongs to.')
    dream_title = serializers.CharField(source='task.goal.dream.title', read_only=True, allow_null=True, help_text='Title of the dream the task belongs to.')

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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the calendar event.'},
            'user': {'help_text': 'Owner of the calendar event.'},
            'task': {'help_text': 'Task linked to this calendar event.'},
            'title': {'help_text': 'Title of the calendar event.'},
            'description': {'help_text': 'Detailed description of the event.'},
            'start_time': {'help_text': 'Start date and time of the event.'},
            'end_time': {'help_text': 'End date and time of the event.'},
            'location': {'help_text': 'Location where the event takes place.'},
            'reminder_minutes_before': {'help_text': 'Minutes before the event to send a reminder.'},
            'status': {'help_text': 'Current status of the event.'},
            'is_recurring': {'help_text': 'Whether this event repeats on a schedule.'},
            'recurrence_rule': {'help_text': 'Recurrence rule defining the repeat pattern.'},
            'parent_event': {'help_text': 'Parent event if this is a recurring instance.'},
            'created_at': {'help_text': 'Timestamp when the event was created.'},
            'updated_at': {'help_text': 'Timestamp when the event was last updated.'},
        }


class CalendarEventCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating calendar events."""

    force = serializers.BooleanField(required=False, default=False, write_only=True, help_text='Force creation even if there is a scheduling conflict.')

    class Meta:
        model = CalendarEvent
        fields = [
            'task', 'title', 'description',
            'start_time', 'end_time', 'location',
            'reminder_minutes_before',
            'is_recurring', 'recurrence_rule',
            'force',
        ]
        extra_kwargs = {
            'task': {'help_text': 'Task to link to this event.'},
            'title': {'help_text': 'Title of the calendar event.'},
            'description': {'help_text': 'Detailed description of the event.'},
            'start_time': {'help_text': 'Start date and time of the event.'},
            'end_time': {'help_text': 'End date and time of the event.'},
            'location': {'help_text': 'Location where the event takes place.'},
            'reminder_minutes_before': {'help_text': 'Minutes before the event to send a reminder.'},
            'is_recurring': {'help_text': 'Whether this event repeats on a schedule.'},
            'recurrence_rule': {'help_text': 'Recurrence rule defining the repeat pattern.'},
        }

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
            raise serializers.ValidationError(_("End time must be after start time"))
        return data


class CalendarEventRescheduleSerializer(serializers.Serializer):
    """Serializer for rescheduling a calendar event."""

    start_time = serializers.DateTimeField(help_text='New start date and time for the event.')
    end_time = serializers.DateTimeField(help_text='New end date and time for the event.')
    force = serializers.BooleanField(required=False, default=False, help_text='Force reschedule even if there is a conflict.')

    def validate(self, data):
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError(_("End time must be after start time"))
        return data


class SuggestTimeSlotsSerializer(serializers.Serializer):
    """Serializer for time slot suggestion request."""

    date = serializers.DateField(help_text='Date to find available time slots for.')
    duration_mins = serializers.IntegerField(min_value=5, max_value=480, help_text='Desired duration in minutes (5-480).')


class TimeBlockSerializer(serializers.ModelSerializer):
    """Serializer for Time blocks."""

    day_name = serializers.SerializerMethodField(help_text='Human-readable name of the day of week.')

    class Meta:
        model = TimeBlock
        fields = [
            'id', 'user', 'block_type', 'day_of_week', 'day_name',
            'start_time', 'end_time', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the time block.'},
            'user': {'help_text': 'Owner of the time block.'},
            'block_type': {'help_text': 'Category of the time block (e.g., work, rest).'},
            'day_of_week': {'help_text': 'Day of week as integer (0=Monday, 6=Sunday).'},
            'start_time': {'help_text': 'Start time of the block.'},
            'end_time': {'help_text': 'End time of the block.'},
            'is_active': {'help_text': 'Whether this time block is currently active.'},
            'created_at': {'help_text': 'Timestamp when the time block was created.'},
            'updated_at': {'help_text': 'Timestamp when the time block was last updated.'},
        }

    def get_day_name(self, obj) -> str:
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return days[obj.day_of_week]

    def validate(self, data):
        """Validate time block."""
        if 'start_time' in data and 'end_time' in data:
            if data['start_time'] >= data['end_time']:
                raise serializers.ValidationError(_("End time must be after start time"))

        if 'day_of_week' in data:
            if not 0 <= data['day_of_week'] <= 6:
                raise serializers.ValidationError(_("Day of week must be between 0 (Monday) and 6 (Sunday)"))

        return data


class CalendarTaskSerializer(serializers.Serializer):
    """Serializer for tasks in calendar view."""

    task_id = serializers.UUIDField(help_text='Unique identifier of the task.')
    task_title = serializers.CharField(help_text='Title of the task.')
    goal_id = serializers.UUIDField(help_text='Unique identifier of the parent goal.')
    goal_title = serializers.CharField(help_text='Title of the parent goal.')
    dream_id = serializers.UUIDField(help_text='Unique identifier of the parent dream.')
    dream_title = serializers.CharField(help_text='Title of the parent dream.')
    scheduled_date = serializers.DateTimeField(help_text='Date the task is scheduled for.')
    scheduled_time = serializers.CharField(allow_blank=True, help_text='Time of day the task is scheduled.')
    duration_mins = serializers.IntegerField(help_text='Estimated duration of the task in minutes.')
    status = serializers.CharField(help_text='Current completion status of the task.')
    is_two_minute_start = serializers.BooleanField(help_text='Whether this task can be started in two minutes.')
