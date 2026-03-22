"""
Serializers for Calendar app.
"""

from django.utils.translation import gettext as _
from rest_framework import serializers

from core.sanitizers import sanitize_text

from apps.dreams.models import Dream
from .models import (
    CalendarEvent,
    CalendarShare,
    Habit,
    HabitCompletion,
    RecurrenceException,
    TimeBlock,
    TimeBlockTemplate,
)


class CalendarEventSerializer(serializers.ModelSerializer):
    """Serializer for Calendar events."""

    task_title = serializers.CharField(
        source="task.title",
        read_only=True,
        allow_null=True,
        help_text="Title of the linked task.",
    )
    goal_title = serializers.CharField(
        source="task.goal.title",
        read_only=True,
        allow_null=True,
        help_text="Title of the goal the task belongs to.",
    )
    dream_id = serializers.UUIDField(
        source="task.goal.dream.id",
        read_only=True,
        allow_null=True,
        help_text="UUID of the dream the task belongs to.",
    )
    dream_title = serializers.CharField(
        source="task.goal.dream.title",
        read_only=True,
        allow_null=True,
        help_text="Title of the dream the task belongs to.",
    )

    is_multi_day = serializers.SerializerMethodField(
        help_text="Whether the event spans multiple days."
    )
    duration_days = serializers.SerializerMethodField(
        help_text="Number of days the event spans."
    )
    recurrence_exceptions = serializers.SerializerMethodField(
        help_text="List of recurrence exceptions (skips/modifications) for recurring events."
    )
    display_timezone = serializers.SerializerMethodField(
        help_text="Effective timezone for display: event_timezone if set, otherwise user home timezone."
    )

    class Meta:
        model = CalendarEvent
        fields = [
            "id",
            "user",
            "task",
            "title",
            "description",
            "start_time",
            "end_time",
            "all_day",
            "location",
            "event_timezone",
            "display_timezone",
            "reminder_minutes_before",
            "reminders",
            "status",
            "category",
            "is_recurring",
            "recurrence_rule",
            "parent_event",
            "task_title",
            "goal_title",
            "dream_id",
            "dream_title",
            "is_multi_day",
            "duration_days",
            "recurrence_exceptions",
            "snoozed_until",
            "sync_status",
            "last_sync_error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "created_at",
            "updated_at",
            "is_multi_day",
            "duration_days",
            "display_timezone",
            "snoozed_until",
            "sync_status",
            "last_sync_error",
        ]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the calendar event."},
            "user": {"help_text": "Owner of the calendar event."},
            "task": {"help_text": "Task linked to this calendar event."},
            "title": {"help_text": "Title of the calendar event."},
            "description": {"help_text": "Detailed description of the event."},
            "start_time": {"help_text": "Start date and time of the event."},
            "end_time": {"help_text": "End date and time of the event."},
            "all_day": {"help_text": "Whether this is an all-day event."},
            "location": {"help_text": "Location where the event takes place."},
            "reminder_minutes_before": {
                "help_text": "Minutes before the event to send a reminder (legacy)."
            },
            "reminders": {
                "help_text": 'List of reminders: [{minutes_before: int, type: "push"|"email"}].'
            },
            "status": {"help_text": "Current status of the event."},
            "category": {
                "help_text": "Event category: meeting, deadline, milestone, habit, social, health, learning, custom."
            },
            "is_recurring": {"help_text": "Whether this event repeats on a schedule."},
            "recurrence_rule": {
                "help_text": "Recurrence rule defining the repeat pattern."
            },
            "parent_event": {
                "help_text": "Parent event if this is a recurring instance."
            },
            "created_at": {"help_text": "Timestamp when the event was created."},
            "updated_at": {"help_text": "Timestamp when the event was last updated."},
        }

    def get_is_multi_day(self, obj) -> bool:
        """True if start_time.date() != end_time.date()."""
        if obj.start_time and obj.end_time:
            return obj.start_time.date() != obj.end_time.date()
        return False

    def get_duration_days(self, obj) -> int:
        """Number of days the event spans (1 for single-day)."""
        if obj.start_time and obj.end_time:
            delta = (obj.end_time.date() - obj.start_time.date()).days
            return max(delta + 1, 1)
        return 1

    def get_display_timezone(self, obj) -> str:
        """Return effective display timezone: event_timezone if set, else user's home timezone."""
        if obj.event_timezone:
            return obj.event_timezone
        if obj.user and hasattr(obj.user, "timezone") and obj.user.timezone:
            return obj.user.timezone
        return "UTC"

    def get_recurrence_exceptions(self, obj):
        """Return exceptions only for recurring events, empty list otherwise."""
        if not obj.is_recurring:
            return []
        exceptions = obj.exceptions.all()
        return [
            {
                "id": str(exc.id),
                "original_date": str(exc.original_date),
                "skip_occurrence": exc.skip_occurrence,
                "modified_title": exc.modified_title,
                "modified_start_time": (
                    exc.modified_start_time.isoformat()
                    if exc.modified_start_time
                    else None
                ),
                "modified_end_time": (
                    exc.modified_end_time.isoformat() if exc.modified_end_time else None
                ),
            }
            for exc in exceptions
        ]


class CalendarEventCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating calendar events."""

    force = serializers.BooleanField(
        required=False,
        default=False,
        write_only=True,
        help_text="Force creation even if there is a scheduling conflict.",
    )

    class Meta:
        model = CalendarEvent
        fields = [
            "task",
            "title",
            "description",
            "start_time",
            "end_time",
            "all_day",
            "location",
            "event_timezone",
            "reminder_minutes_before",
            "reminders",
            "category",
            "is_recurring",
            "recurrence_rule",
            "force",
        ]
        extra_kwargs = {
            "task": {"help_text": "Task to link to this event."},
            "title": {"help_text": "Title of the calendar event."},
            "description": {"help_text": "Detailed description of the event."},
            "start_time": {"help_text": "Start date and time of the event."},
            "end_time": {"help_text": "End date and time of the event."},
            "all_day": {"help_text": "Whether this is an all-day event."},
            "location": {"help_text": "Location where the event takes place."},
            "event_timezone": {
                "help_text": "Optional timezone override for this event (e.g. America/New_York)."
            },
            "reminder_minutes_before": {
                "help_text": "Minutes before the event to send a reminder (legacy)."
            },
            "reminders": {
                "help_text": 'List of reminders: [{minutes_before: int, type: "push"|"email"}].'
            },
            "category": {
                "help_text": "Event category: meeting, deadline, milestone, habit, social, health, learning, custom."
            },
            "is_recurring": {"help_text": "Whether this event repeats on a schedule."},
            "recurrence_rule": {
                "help_text": "Recurrence rule defining the repeat pattern."
            },
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

    def validate_reminders(self, value):
        """Validate reminders JSON array."""
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError(_("reminders must be an array"))
        if len(value) > 10:
            raise serializers.ValidationError(_("Maximum 10 reminders allowed"))
        valid_types = ("push", "email")
        for i, reminder in enumerate(value):
            if not isinstance(reminder, dict):
                raise serializers.ValidationError(
                    _("Each reminder must be a JSON object (item %(index)d is not)")
                    % {"index": i}
                )
            minutes_before = reminder.get("minutes_before")
            if minutes_before is None:
                raise serializers.ValidationError(
                    _("Reminder %(index)d is missing 'minutes_before'") % {"index": i}
                )
            if (
                not isinstance(minutes_before, int)
                or minutes_before < 0
                or minutes_before > 40320
            ):
                raise serializers.ValidationError(
                    _("minutes_before must be an integer between 0 and 40320 (28 days)")
                )
            reminder_type = reminder.get("type", "push")
            if reminder_type not in valid_types:
                raise serializers.ValidationError(
                    _("Reminder type must be one of: push, email")
                )
        return value

    def validate_recurrence_rule(self, value):
        """Validate the enhanced recurrence_rule JSON schema."""
        if value is None:
            return value

        if not isinstance(value, dict):
            raise serializers.ValidationError(
                _("recurrence_rule must be a JSON object")
            )

        valid_frequencies = ("daily", "weekly", "monthly", "yearly", "custom")
        frequency = value.get("frequency")
        if not frequency:
            raise serializers.ValidationError(
                _("recurrence_rule requires a 'frequency' field")
            )
        if frequency not in valid_frequencies:
            raise serializers.ValidationError(
                _("frequency must be one of: daily, weekly, monthly, yearly, custom")
            )

        # interval (optional, defaults to 1)
        interval = value.get("interval", 1)
        if not isinstance(interval, int) or interval < 1:
            raise serializers.ValidationError(_("interval must be a positive integer"))

        # days_of_week (optional, for weekly)
        days_of_week = value.get("days_of_week")
        if days_of_week is not None:
            if not isinstance(days_of_week, list):
                raise serializers.ValidationError(_("days_of_week must be an array"))
            for dow in days_of_week:
                if not isinstance(dow, int) or dow < 0 or dow > 6:
                    raise serializers.ValidationError(
                        _("days_of_week values must be integers 0-6")
                    )

        # day_of_month (optional, for monthly)
        day_of_month = value.get("day_of_month")
        if day_of_month is not None:
            if (
                not isinstance(day_of_month, int)
                or day_of_month < 1
                or day_of_month > 31
            ):
                raise serializers.ValidationError(
                    _("day_of_month must be an integer 1-31")
                )

        # week_of_month + day_of_week (optional, for "first Monday" pattern)
        week_of_month = value.get("week_of_month")
        if week_of_month is not None:
            if (
                not isinstance(week_of_month, int)
                or week_of_month < 1
                or week_of_month > 5
            ):
                raise serializers.ValidationError(
                    _("week_of_month must be an integer 1-5")
                )
            day_of_week = value.get("day_of_week")
            if day_of_week is None:
                raise serializers.ValidationError(
                    _("day_of_week is required when week_of_month is specified")
                )
            if not isinstance(day_of_week, int) or day_of_week < 0 or day_of_week > 6:
                raise serializers.ValidationError(
                    _("day_of_week must be an integer 0-6")
                )

        # end_date (optional, ISO date string or null)
        end_date = value.get("end_date")
        if end_date is not None:
            if not isinstance(end_date, str):
                raise serializers.ValidationError(
                    _("end_date must be an ISO date string or null")
                )
            try:
                from datetime import datetime as _dt

                _dt.fromisoformat(end_date.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                raise serializers.ValidationError(
                    _("end_date must be a valid ISO date string")
                )

        # end_after_count (optional, positive int or null)
        end_after_count = value.get("end_after_count")
        if end_after_count is not None:
            if not isinstance(end_after_count, int) or end_after_count < 1:
                raise serializers.ValidationError(
                    _("end_after_count must be a positive integer or null")
                )

        # weekdays_only (optional, boolean)
        weekdays_only = value.get("weekdays_only")
        if weekdays_only is not None:
            if not isinstance(weekdays_only, bool):
                raise serializers.ValidationError(_("weekdays_only must be a boolean"))

        return value

    def validate(self, data):
        """Validate that end_time is after start_time."""
        if data["start_time"] >= data["end_time"]:
            raise serializers.ValidationError(_("End time must be after start time"))

        # If is_recurring is True, recurrence_rule must be provided
        if data.get("is_recurring") and not data.get("recurrence_rule"):
            raise serializers.ValidationError(
                _("recurrence_rule is required when is_recurring is True")
            )

        return data


class CalendarEventRescheduleSerializer(serializers.Serializer):
    """Serializer for rescheduling a calendar event."""

    start_time = serializers.DateTimeField(
        help_text="New start date and time for the event."
    )
    end_time = serializers.DateTimeField(
        help_text="New end date and time for the event."
    )
    force = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Force reschedule even if there is a conflict.",
    )

    def validate(self, data):
        if data["start_time"] >= data["end_time"]:
            raise serializers.ValidationError(_("End time must be after start time"))
        return data


class SuggestTimeSlotsSerializer(serializers.Serializer):
    """Serializer for time slot suggestion request."""

    date = serializers.DateField(help_text="Date to find available time slots for.")
    duration_mins = serializers.IntegerField(
        min_value=5, max_value=480, help_text="Desired duration in minutes (5-480)."
    )


class TimeBlockSerializer(serializers.ModelSerializer):
    """Serializer for Time blocks."""

    day_name = serializers.SerializerMethodField(
        help_text="Human-readable name of the day of week."
    )
    dream_id = serializers.PrimaryKeyRelatedField(
        source="dream",
        queryset=Dream.objects.all(),
        required=False,
        allow_null=True,
        help_text="UUID of the associated dream.",
    )

    class Meta:
        model = TimeBlock
        fields = [
            "id",
            "user",
            "title",
            "block_type",
            "day_of_week",
            "day_name",
            "start_time",
            "end_time",
            "color",
            "dream_id",
            "is_active",
            "focus_block",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the time block."},
            "user": {"help_text": "Owner of the time block."},
            "title": {"help_text": "User-facing label for the time block."},
            "block_type": {
                "help_text": "Category of the time block (e.g., work, personal).",
                "required": False,
            },
            "day_of_week": {
                "help_text": "Day of week as integer (0=Monday, 6=Sunday)."
            },
            "start_time": {"help_text": "Start time of the block."},
            "end_time": {"help_text": "End time of the block."},
            "color": {"help_text": "Hex color code for the time block."},
            "is_active": {"help_text": "Whether this time block is currently active."},
            "focus_block": {
                "help_text": "Whether this block is a focus/DND block that suppresses notifications."
            },
            "created_at": {"help_text": "Timestamp when the time block was created."},
            "updated_at": {
                "help_text": "Timestamp when the time block was last updated."
            },
        }

    def get_day_name(self, obj) -> str:
        days = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        return days[obj.day_of_week]

    def validate(self, data):
        """Validate time block."""
        if "start_time" in data and "end_time" in data:
            if data["start_time"] >= data["end_time"]:
                raise serializers.ValidationError(
                    _("End time must be after start time")
                )

        if "day_of_week" in data:
            if not 0 <= data["day_of_week"] <= 6:
                raise serializers.ValidationError(
                    _("Day of week must be between 0 (Monday) and 6 (Sunday)")
                )

        return data


class SmartScheduleRequestSerializer(serializers.Serializer):
    """Serializer for AI smart scheduling request."""

    task_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=20,
        help_text="List of task IDs to schedule (1-20 tasks).",
    )


class AcceptScheduleSerializer(serializers.Serializer):
    """Serializer for accepting smart schedule suggestions."""

    class SuggestionItem(serializers.Serializer):
        task_id = serializers.UUIDField(help_text="ID of the task to schedule.")
        suggested_date = serializers.DateField(help_text="Accepted date for the task.")
        suggested_time = serializers.CharField(
            max_length=5, help_text="Accepted time in HH:MM format."
        )

    suggestions = serializers.ListField(
        child=SuggestionItem(),
        min_length=1,
        max_length=20,
        help_text="List of accepted schedule suggestions.",
    )


class BatchScheduleItemSerializer(serializers.Serializer):
    """Single item in a batch schedule request."""

    task_id = serializers.UUIDField(help_text="ID of the task to schedule.")
    date = serializers.DateField(help_text="Date to schedule the task (YYYY-MM-DD).")
    time = serializers.CharField(
        max_length=5, help_text="Time to schedule the task (HH:MM)."
    )


class BatchScheduleSerializer(serializers.Serializer):
    """Serializer for batch scheduling multiple tasks at once."""

    tasks = serializers.ListField(
        child=BatchScheduleItemSerializer(),
        min_length=1,
        max_length=50,
        help_text="List of tasks to schedule with date and time.",
    )
    create_events = serializers.BooleanField(
        default=True,
        help_text="Whether to create CalendarEvent objects for each task.",
    )


class CheckConflictsSerializer(serializers.Serializer):
    """Serializer for the check_conflicts pre-flight endpoint."""

    start_time = serializers.DateTimeField(
        help_text="Start date and time to check for conflicts."
    )
    end_time = serializers.DateTimeField(
        help_text="End date and time to check for conflicts."
    )
    exclude_event_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Event ID to exclude from conflict check (for reschedule).",
    )

    def validate(self, data):
        if data["start_time"] >= data["end_time"]:
            raise serializers.ValidationError(_("End time must be after start time"))
        return data


class CheckConflictsResponseSerializer(serializers.Serializer):
    """Response serializer for the check_conflicts endpoint."""

    has_conflicts = serializers.BooleanField(
        help_text="Whether there are any conflicts."
    )
    conflicts = serializers.ListField(
        help_text="List of conflicting events and time blocks."
    )


class CalendarTaskSerializer(serializers.Serializer):
    """Serializer for tasks in calendar view."""

    task_id = serializers.UUIDField(help_text="Unique identifier of the task.")
    task_title = serializers.CharField(help_text="Title of the task.")
    goal_id = serializers.UUIDField(help_text="Unique identifier of the parent goal.")
    goal_title = serializers.CharField(help_text="Title of the parent goal.")
    dream_id = serializers.UUIDField(help_text="Unique identifier of the parent dream.")
    dream_title = serializers.CharField(help_text="Title of the parent dream.")
    scheduled_date = serializers.DateTimeField(
        help_text="Date the task is scheduled for."
    )
    scheduled_time = serializers.CharField(
        allow_blank=True, help_text="Time of day the task is scheduled."
    )
    duration_mins = serializers.IntegerField(
        help_text="Estimated duration of the task in minutes."
    )
    status = serializers.CharField(help_text="Current completion status of the task.")
    is_two_minute_start = serializers.BooleanField(
        help_text="Whether this task can be started in two minutes."
    )


class TimeBlockTemplateSerializer(serializers.ModelSerializer):
    """Serializer for time block templates."""

    block_count = serializers.SerializerMethodField(
        help_text="Number of blocks in this template."
    )

    class Meta:
        model = TimeBlockTemplate
        fields = [
            "id",
            "user",
            "name",
            "description",
            "blocks",
            "is_preset",
            "block_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "is_preset", "created_at", "updated_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the template."},
            "user": {"help_text": "Owner of the template."},
            "name": {"help_text": "Name of the template."},
            "description": {"help_text": "Description of the template."},
            "blocks": {
                "help_text": "Array of {block_type, day_of_week, start_time, end_time}."
            },
            "is_preset": {"help_text": "Whether this is a system preset template."},
            "created_at": {"help_text": "Timestamp when the template was created."},
            "updated_at": {
                "help_text": "Timestamp when the template was last updated."
            },
        }

    def get_block_count(self, obj) -> int:
        if isinstance(obj.blocks, list):
            return len(obj.blocks)
        return 0

    def validate_name(self, value):
        """Sanitize name to prevent XSS."""
        return sanitize_text(value)

    def validate_description(self, value):
        """Sanitize description to prevent XSS."""
        if value:
            return sanitize_text(value)
        return value

    def validate_blocks(self, value):
        """Validate that blocks is a list of valid block dicts."""
        if not isinstance(value, list):
            raise serializers.ValidationError(_("blocks must be an array"))
        if len(value) == 0:
            raise serializers.ValidationError(
                _("blocks must contain at least one block")
            )
        valid_types = ("work", "personal", "family", "exercise", "blocked")
        for i, block in enumerate(value):
            if not isinstance(block, dict):
                raise serializers.ValidationError(
                    _("Each block must be a JSON object (item %(index)d is not)")
                    % {"index": i}
                )
            for field in ("block_type", "day_of_week", "start_time", "end_time"):
                if field not in block:
                    raise serializers.ValidationError(
                        _("Block %(index)d is missing required field '%(field)s'")
                        % {"index": i, "field": field}
                    )
            if block["block_type"] not in valid_types:
                raise serializers.ValidationError(
                    _("Block %(index)d has invalid block_type '%(type)s'")
                    % {"index": i, "type": block["block_type"]}
                )
            dow = block["day_of_week"]
            if not isinstance(dow, int) or dow < 0 or dow > 6:
                raise serializers.ValidationError(
                    _("Block %(index)d day_of_week must be 0-6") % {"index": i}
                )
        return value


class SaveCurrentTemplateSerializer(serializers.Serializer):
    """Serializer for saving current time blocks as a template."""

    name = serializers.CharField(max_length=100, help_text="Name for the new template.")
    description = serializers.CharField(
        required=False, default="", help_text="Optional description."
    )

    def validate_name(self, value):
        return sanitize_text(value)

    def validate_description(self, value):
        if value:
            return sanitize_text(value)
        return value


class HeatmapDaySerializer(serializers.Serializer):
    """Serializer for a single day's productivity heatmap data."""

    date = serializers.DateField(help_text="The calendar date.")
    tasks_completed = serializers.IntegerField(
        help_text="Number of tasks completed on this day."
    )
    tasks_total = serializers.IntegerField(
        help_text="Total number of tasks scheduled for this day."
    )
    events_count = serializers.IntegerField(
        help_text="Number of calendar events on this day."
    )
    focus_minutes = serializers.IntegerField(
        help_text="Total focus session minutes on this day."
    )
    productivity_score = serializers.FloatField(
        help_text="Weighted productivity score (0.0-1.0)."
    )


class RecurrenceExceptionSerializer(serializers.ModelSerializer):
    """Serializer for RecurrenceException (read)."""

    class Meta:
        model = RecurrenceException
        fields = [
            "id",
            "parent_event",
            "original_date",
            "skip_occurrence",
            "modified_title",
            "modified_start_time",
            "modified_end_time",
            "created_at",
        ]
        read_only_fields = ["id", "parent_event", "created_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for this exception."},
            "parent_event": {
                "help_text": "The recurring event this exception applies to."
            },
            "original_date": {"help_text": "The original occurrence date."},
            "skip_occurrence": {
                "help_text": "Whether to skip this occurrence entirely."
            },
            "modified_title": {"help_text": "Modified title for this occurrence."},
            "modified_start_time": {"help_text": "Modified start time."},
            "modified_end_time": {"help_text": "Modified end time."},
            "created_at": {"help_text": "When this exception was created."},
        }


class SkipOccurrenceSerializer(serializers.Serializer):
    """Serializer for skipping a single occurrence of a recurring event."""

    original_date = serializers.DateField(
        help_text="The date of the occurrence to skip (YYYY-MM-DD)."
    )


class ModifyOccurrenceSerializer(serializers.Serializer):
    """Serializer for modifying a single occurrence of a recurring event."""

    original_date = serializers.DateField(
        help_text="The date of the occurrence to modify (YYYY-MM-DD)."
    )
    title = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="New title for this occurrence. Blank keeps parent title.",
    )
    start_time = serializers.DateTimeField(
        required=False, allow_null=True, help_text="New start time for this occurrence."
    )
    end_time = serializers.DateTimeField(
        required=False, allow_null=True, help_text="New end time for this occurrence."
    )

    def validate_title(self, value):
        if value:
            return sanitize_text(value)
        return value

    def validate(self, data):
        st = data.get("start_time")
        et = data.get("end_time")
        if st and et and st >= et:
            raise serializers.ValidationError(_("End time must be after start time"))
        return data


# ─── Calendar Sharing ──────────────────────────────────────────────


class CalendarShareCreateSerializer(serializers.Serializer):
    """Serializer for creating a calendar share with a buddy."""

    user_id = serializers.UUIDField(
        help_text="UUID of the buddy user to share the calendar with."
    )
    permission = serializers.ChoiceField(
        choices=["view", "suggest"],
        default="view",
        help_text='Permission level: "view" (read-only) or "suggest" (can suggest times).',
    )


class CalendarShareSerializer(serializers.ModelSerializer):
    """Serializer for calendar share records."""

    owner_name = serializers.CharField(
        source="owner.display_name", read_only=True, allow_blank=True
    )
    owner_avatar = serializers.SerializerMethodField()
    shared_with_name = serializers.CharField(
        source="shared_with.display_name",
        read_only=True,
        allow_blank=True,
        allow_null=True,
    )
    shared_with_avatar = serializers.SerializerMethodField()

    class Meta:
        model = CalendarShare
        fields = [
            "id",
            "owner",
            "shared_with",
            "permission",
            "share_token",
            "is_active",
            "created_at",
            "owner_name",
            "owner_avatar",
            "shared_with_name",
            "shared_with_avatar",
        ]
        read_only_fields = [
            "id",
            "owner",
            "shared_with",
            "share_token",
            "is_active",
            "created_at",
        ]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for this calendar share."},
            "owner": {"help_text": "User who owns the shared calendar."},
            "shared_with": {"help_text": "User the calendar is shared with."},
            "permission": {"help_text": "Permission level (view or suggest)."},
            "share_token": {"help_text": "Unique token for link-based sharing."},
            "is_active": {"help_text": "Whether this share is active."},
            "created_at": {"help_text": "When the share was created."},
        }

    def get_owner_avatar(self, obj):
        if obj.owner and hasattr(obj.owner, "avatar") and obj.owner.avatar:
            return (
                obj.owner.avatar.url
                if hasattr(obj.owner.avatar, "url")
                else str(obj.owner.avatar)
            )
        return ""

    def get_shared_with_avatar(self, obj):
        if (
            obj.shared_with
            and hasattr(obj.shared_with, "avatar")
            and obj.shared_with.avatar
        ):
            return (
                obj.shared_with.avatar.url
                if hasattr(obj.shared_with.avatar, "url")
                else str(obj.shared_with.avatar)
            )
        return ""


class CalendarShareLinkSerializer(serializers.Serializer):
    """Serializer for generating a shareable calendar link."""

    permission = serializers.ChoiceField(
        choices=["view", "suggest"],
        default="view",
        help_text="Permission level for anyone accessing the link.",
    )


class TimeSuggestionSerializer(serializers.Serializer):
    """Serializer for suggesting a time on a shared calendar."""

    suggested_start = serializers.DateTimeField(
        help_text="Suggested start time for the event."
    )
    suggested_end = serializers.DateTimeField(
        help_text="Suggested end time for the event."
    )
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=500,
        help_text="Optional note about the suggestion.",
    )

    def validate_note(self, value):
        return sanitize_text(value)

    def validate(self, data):
        if data["suggested_start"] >= data["suggested_end"]:
            raise serializers.ValidationError(_("End time must be after start time"))
        return data


class CalendarPreferencesSerializer(serializers.Serializer):
    """Serializer for calendar buffer/scheduling preferences."""

    buffer_minutes = serializers.IntegerField(
        min_value=0,
        max_value=60,
        default=15,
        help_text="Minimum gap in minutes between events (0-60).",
    )
    min_event_duration = serializers.IntegerField(
        min_value=15,
        max_value=120,
        default=30,
        help_text="Minimum event duration in minutes (15-120).",
    )


# ─── Habit Tracker ──────────────────────────────────────────────


class HabitSerializer(serializers.ModelSerializer):
    """Serializer for Habit model."""

    completions_today = serializers.SerializerMethodField(
        help_text="Number of completions for today."
    )

    class Meta:
        model = Habit
        fields = [
            "id",
            "user",
            "name",
            "description",
            "frequency",
            "custom_days",
            "target_per_day",
            "color",
            "icon",
            "is_active",
            "streak_current",
            "streak_best",
            "completions_today",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "streak_current",
            "streak_best",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the habit."},
            "user": {"help_text": "Owner of the habit."},
            "name": {"help_text": "Name of the habit."},
            "description": {"help_text": "Description of the habit."},
            "frequency": {"help_text": "How often the habit should be completed."},
            "custom_days": {
                "help_text": "Days of the week (0-6) for custom frequency."
            },
            "target_per_day": {"help_text": "Number of completions per day."},
            "color": {"help_text": "Hex color for the habit display."},
            "icon": {"help_text": "Lucide icon name for the habit."},
            "is_active": {"help_text": "Whether this habit is currently active."},
            "streak_current": {"help_text": "Current consecutive completion streak."},
            "streak_best": {"help_text": "Best consecutive completion streak."},
            "created_at": {"help_text": "When the habit was created."},
            "updated_at": {"help_text": "When the habit was last updated."},
        }

    def get_completions_today(self, obj) -> int:
        from django.utils import timezone

        today = timezone.now().date()
        completion = obj.completions.filter(date=today).first()
        return completion.count if completion else 0

    def validate_name(self, value):
        return sanitize_text(value)

    def validate_description(self, value):
        if value:
            return sanitize_text(value)
        return value

    def validate_custom_days(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(_("custom_days must be an array"))
        for day in value:
            if not isinstance(day, int) or day < 0 or day > 6:
                raise serializers.ValidationError(
                    _("custom_days values must be integers 0-6")
                )
        return value

    def validate_color(self, value):
        import re

        if value and not re.match(r"^#[0-9A-Fa-f]{6}$", value):
            raise serializers.ValidationError(
                _("color must be a valid hex color code (e.g. #8B5CF6)")
            )
        return value

    def validate_target_per_day(self, value):
        if value < 1 or value > 100:
            raise serializers.ValidationError(
                _("target_per_day must be between 1 and 100")
            )
        return value


class HabitCompletionSerializer(serializers.ModelSerializer):
    """Serializer for HabitCompletion model."""

    habit_name = serializers.CharField(source="habit.name", read_only=True)
    habit_color = serializers.CharField(source="habit.color", read_only=True)
    habit_icon = serializers.CharField(source="habit.icon", read_only=True)

    class Meta:
        model = HabitCompletion
        fields = [
            "id",
            "habit",
            "completed_at",
            "date",
            "count",
            "note",
            "habit_name",
            "habit_color",
            "habit_icon",
        ]
        read_only_fields = ["id", "completed_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for this completion record."},
            "habit": {"help_text": "The habit that was completed."},
            "completed_at": {"help_text": "Timestamp of the completion."},
            "date": {"help_text": "Date of the completion."},
            "count": {"help_text": "Number of completions for this date."},
            "note": {"help_text": "Optional note about the completion."},
        }

    def validate_note(self, value):
        if value:
            return sanitize_text(value)
        return value


class HabitCompleteSerializer(serializers.Serializer):
    """Serializer for the habit complete action."""

    date = serializers.DateField(help_text="Date of completion (YYYY-MM-DD).")
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=500,
        help_text="Optional note about the completion.",
    )

    def validate_note(self, value):
        if value:
            return sanitize_text(value)
        return value


class HabitUncompleteSerializer(serializers.Serializer):
    """Serializer for the habit uncomplete action."""

    date = serializers.DateField(help_text="Date to remove completion (YYYY-MM-DD).")
