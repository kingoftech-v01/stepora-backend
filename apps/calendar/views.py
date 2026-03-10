"""
Views for Calendar app.
"""

import calendar as cal_module
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.buddies.models import BuddyPairing
from apps.dreams.models import Dream, FocusSession, Task
from apps.users.models import DailyActivity

from .models import (
    CalendarEvent,
    CalendarShare,
    GoogleCalendarIntegration,
    Habit,
    HabitCompletion,
    RecurrenceException,
    TimeBlock,
    TimeBlockTemplate,
)
from .serializers import (
    AcceptScheduleSerializer,
    BatchScheduleSerializer,
    CalendarEventCreateSerializer,
    CalendarEventRescheduleSerializer,
    CalendarEventSerializer,
    CalendarPreferencesSerializer,
    CalendarShareCreateSerializer,
    CalendarShareLinkSerializer,
    CalendarShareSerializer,
    CalendarTaskSerializer,
    CheckConflictsResponseSerializer,
    CheckConflictsSerializer,
    HabitCompleteSerializer,
    HabitCompletionSerializer,
    HabitSerializer,
    HabitUncompleteSerializer,
    HeatmapDaySerializer,
    ModifyOccurrenceSerializer,
    RecurrenceExceptionSerializer,
    SaveCurrentTemplateSerializer,
    SkipOccurrenceSerializer,
    SmartScheduleRequestSerializer,
    TimeBlockSerializer,
    TimeBlockTemplateSerializer,
    TimeSuggestionSerializer,
)


def expand_recurring_events(event, range_start, range_end):
    """Expand a recurring CalendarEvent into virtual instances within a date range."""
    rule = event.recurrence_rule
    if not rule or not event.is_recurring:
        return []
    frequency = rule.get("frequency", "daily")
    interval = rule.get("interval", 1)
    days_of_week = rule.get("days_of_week")
    day_of_month = rule.get("day_of_month")
    week_of_month = rule.get("week_of_month")
    rule_day_of_week = rule.get("day_of_week")
    end_date_str = rule.get("end_date")
    end_after_count = rule.get("end_after_count")
    weekdays_only = rule.get("weekdays_only", False)
    recurrence_end = None
    if end_date_str:
        try:
            parsed = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt_timezone.utc)
            recurrence_end = parsed
        except (ValueError, AttributeError):
            pass
    event_duration = event.end_time - event.start_time
    base_start = event.start_time
    occurrences = []
    count = 0
    current = base_start
    iteration = 0
    while iteration < 1500:
        iteration += 1
        if current > range_end:
            break
        if recurrence_end and current > recurrence_end:
            break
        if end_after_count and count >= end_after_count:
            break
        if current != base_start:
            if weekdays_only and current.weekday() >= 5:
                current = _advance_date(
                    current,
                    frequency,
                    interval,
                    base_start,
                    days_of_week,
                    day_of_month,
                    week_of_month,
                    rule_day_of_week,
                )
                continue
            if frequency == "weekly" and days_of_week is not None:
                if current.weekday() not in days_of_week:
                    current = _advance_date(
                        current,
                        frequency,
                        interval,
                        base_start,
                        days_of_week,
                        day_of_month,
                        week_of_month,
                        rule_day_of_week,
                    )
                    continue
            occ_end = current + event_duration
            if occ_end >= range_start and current <= range_end:
                virtual = _make_virtual_event(event, current, occ_end)
                occurrences.append(virtual)
                count += 1
            elif current < range_start:
                count += 1
        else:
            count += 1
        current = _advance_date(
            current,
            frequency,
            interval,
            base_start,
            days_of_week,
            day_of_month,
            week_of_month,
            rule_day_of_week,
        )
    return occurrences


def _advance_date(
    current,
    frequency,
    interval,
    base_start,
    days_of_week,
    day_of_month,
    week_of_month,
    rule_day_of_week,
):
    """Advance the current date by one step according to the recurrence rule."""
    if frequency == "daily":
        return current + timedelta(days=interval)
    elif frequency == "weekly":
        if days_of_week and len(days_of_week) > 1:
            sorted_days = sorted(days_of_week)
            current_dow = current.weekday()
            next_days = [d for d in sorted_days if d > current_dow]
            if next_days:
                return current + timedelta(days=next_days[0] - current_dow)
            else:
                days_to_first = (7 - current_dow) + sorted_days[0]
                extra_weeks = (interval - 1) * 7
                return current + timedelta(days=days_to_first + extra_weeks)
        else:
            return current + timedelta(weeks=interval)
    elif frequency == "monthly":
        if week_of_month is not None and rule_day_of_week is not None:
            next_date = _next_nth_weekday(
                current, interval, week_of_month, rule_day_of_week
            )
            return next_date.replace(
                hour=base_start.hour,
                minute=base_start.minute,
                second=base_start.second,
                tzinfo=base_start.tzinfo,
            )
        else:
            target_day = day_of_month or base_start.day
            month = current.month + interval
            year = current.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            max_day = cal_module.monthrange(year, month)[1]
            actual_day = min(target_day, max_day)
            return current.replace(year=year, month=month, day=actual_day)
    elif frequency == "yearly":
        try:
            return current.replace(year=current.year + interval)
        except ValueError:
            return current.replace(year=current.year + interval, day=28)
    elif frequency == "custom":
        return current + timedelta(days=interval)
    return current + timedelta(days=1)


def _next_nth_weekday(current, interval, week_of_month, day_of_week):
    """Find the next Nth weekday of a future month (skipping interval months)."""
    month = current.month + interval
    year = current.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    first_day_dow = datetime(year, month, 1).weekday()
    days_until = (day_of_week - first_day_dow) % 7
    target_day = 1 + days_until + (week_of_month - 1) * 7
    max_day = cal_module.monthrange(year, month)[1]
    if target_day > max_day:
        target_day = 1 + days_until + (week_of_month - 2) * 7
        target_day = min(max(target_day, 1), max_day)
    return datetime(year, month, target_day)


def _make_virtual_event(parent_event, new_start, new_end):
    """Create a virtual (unsaved) CalendarEvent copy for a recurrence occurrence."""
    virtual = CalendarEvent()
    virtual.id = parent_event.id
    virtual.user_id = parent_event.user_id
    virtual.task_id = parent_event.task_id
    virtual.title = parent_event.title
    virtual.description = parent_event.description
    virtual.start_time = new_start
    virtual.end_time = new_end
    virtual.all_day = parent_event.all_day
    virtual.location = parent_event.location
    virtual.reminder_minutes_before = parent_event.reminder_minutes_before
    virtual.status = parent_event.status
    virtual.category = parent_event.category
    virtual.is_recurring = True
    virtual.recurrence_rule = parent_event.recurrence_rule
    virtual.parent_event_id = parent_event.id
    virtual.google_event_id = parent_event.google_event_id
    virtual.created_at = parent_event.created_at
    virtual.updated_at = parent_event.updated_at
    virtual._virtual_occurrence = True
    return virtual


def _get_user_buffer_minutes(user):
    """Get the user's configured buffer minutes between events."""
    prefs = getattr(user, "calendar_preferences", None) or {}
    buffer = prefs.get("buffer_minutes", 15)
    # Clamp to 0-60
    return max(0, min(60, int(buffer)))


def _get_user_min_event_duration(user):
    """Get the user's configured minimum event duration in minutes."""
    prefs = getattr(user, "calendar_preferences", None) or {}
    duration = prefs.get("min_event_duration", 30)
    # Clamp to 15-120
    return max(15, min(120, int(duration)))


def _check_conflicts(user, start_time, end_time, exclude_event_id=None):
    """Check for overlapping events for a user, considering buffer time."""
    buffer_mins = _get_user_buffer_minutes(user)
    buffered_start = start_time - timedelta(minutes=buffer_mins)
    buffered_end = end_time + timedelta(minutes=buffer_mins)
    qs = CalendarEvent.objects.filter(
        user=user,
        status="scheduled",
        start_time__lt=buffered_end,
        end_time__gt=buffered_start,
    )
    if exclude_event_id:
        qs = qs.exclude(id=exclude_event_id)
    return qs


def _check_timeblock_conflicts(user, start_time, end_time):
    """Check if an event would overlap with 'blocked' time blocks.

    TimeBlocks are recurring weekly schedules (day_of_week + start_time/end_time).
    We check each day the event spans and see if any active 'blocked' time block
    on that day of week overlaps the event's time range on that day.
    """
    from datetime import time as time_type

    conflicts = []
    current_date = start_time.date()
    end_date = end_time.date()

    while current_date <= end_date:
        # Python weekday(): Monday=0, Sunday=6 — matches our model
        dow = current_date.weekday()

        # Determine the time window on this particular day
        if current_date == start_time.date():
            day_start_time = start_time.time()
        else:
            day_start_time = time_type(0, 0)

        if current_date == end_time.date():
            day_end_time = end_time.time()
        else:
            day_end_time = time_type(23, 59, 59)

        blocked = TimeBlock.objects.filter(
            user=user,
            is_active=True,
            block_type="blocked",
            day_of_week=dow,
            start_time__lt=day_end_time,
            end_time__gt=day_start_time,
        )

        for tb in blocked:
            days_map = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
            conflicts.append(
                {
                    "id": str(tb.id),
                    "title": "Blocked: "
                    + days_map[tb.day_of_week]
                    + " "
                    + tb.start_time.strftime("%H:%M")
                    + "-"
                    + tb.end_time.strftime("%H:%M"),
                    "start_time": str(current_date)
                    + "T"
                    + tb.start_time.strftime("%H:%M:%S"),
                    "end_time": str(current_date)
                    + "T"
                    + tb.end_time.strftime("%H:%M:%S"),
                    "type": "timeblock",
                }
            )

        current_date += timedelta(days=1)

    return conflicts


@extend_schema_view(
    list=extend_schema(
        summary="List events",
        description="Get all calendar events for the current user",
        tags=["Calendar Events"],
    ),
    create=extend_schema(
        summary="Create event",
        description="Create a new calendar event",
        tags=["Calendar Events"],
    ),
    retrieve=extend_schema(
        summary="Get event",
        description="Get a specific calendar event",
        tags=["Calendar Events"],
    ),
    update=extend_schema(
        summary="Update event",
        description="Update a calendar event",
        tags=["Calendar Events"],
    ),
    partial_update=extend_schema(
        summary="Partial update event",
        description="Partially update a calendar event",
        tags=["Calendar Events"],
    ),
    destroy=extend_schema(
        summary="Delete event",
        description="Delete a calendar event",
        tags=["Calendar Events"],
    ),
)
class CalendarEventViewSet(viewsets.ModelViewSet):
    """CRUD operations for calendar events."""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get calendar events for current user."""
        if getattr(self, "swagger_fake_view", False):
            return CalendarEvent.objects.none()
        return CalendarEvent.objects.filter(user=self.request.user).prefetch_related(
            "exceptions"
        )

    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action in ("create", "update", "partial_update"):
            return CalendarEventCreateSerializer
        return CalendarEventSerializer

    def list(self, request, *args, **kwargs):
        """List events with recurring event expansion within date range."""
        queryset = self.filter_queryset(self.get_queryset())

        # Check for date range filters to expand recurring events
        start_gte = request.query_params.get("start_time__gte")
        start_lte = request.query_params.get("start_time__lte")

        if start_gte and start_lte:
            try:
                range_start = datetime.fromisoformat(start_gte.replace("Z", "+00:00"))
                range_end = datetime.fromisoformat(start_lte.replace("Z", "+00:00"))
                if range_start.tzinfo is None:
                    range_start = range_start.replace(tzinfo=dt_timezone.utc)
                if range_end.tzinfo is None:
                    range_end = range_end.replace(tzinfo=dt_timezone.utc)
            except (ValueError, AttributeError):
                range_start = None
                range_end = None

            if range_start and range_end:
                # Filter non-recurring events normally
                non_recurring = queryset.filter(
                    is_recurring=False,
                    start_time__gte=range_start,
                    start_time__lte=range_end,
                )
                # Get all recurring events (parent events) for this user
                recurring = queryset.filter(
                    is_recurring=True,
                    recurrence_rule__isnull=False,
                    parent_event__isnull=True,
                )
                # Expand recurring events into virtual instances
                expanded = []
                for evt in recurring:
                    # Include the parent if it falls within range
                    if evt.start_time >= range_start and evt.start_time <= range_end:
                        expanded.append(evt)
                    # Expand virtual occurrences
                    expanded.extend(
                        expand_recurring_events(evt, range_start, range_end)
                    )

                # Combine and serialize
                all_events = list(non_recurring) + expanded
                all_events.sort(key=lambda e: e.start_time)
                serializer = self.get_serializer(all_events, many=True)
                return Response(serializer.data)

        # Default: standard queryset list (no expansion)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        """Create event for current user with conflict detection."""
        data = serializer.validated_data
        force = data.pop("force", False)

        conflicts = _check_conflicts(
            self.request.user, data["start_time"], data["end_time"]
        )

        if conflicts.exists() and not force:
            conflict_data = CalendarEventSerializer(conflicts, many=True).data
            raise ConflictException(conflict_data)

        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        """Update event with conflict detection."""
        data = serializer.validated_data
        force = data.pop("force", False)

        start = data.get("start_time", serializer.instance.start_time)
        end = data.get("end_time", serializer.instance.end_time)

        conflicts = _check_conflicts(
            self.request.user, start, end, exclude_event_id=serializer.instance.id
        )

        if conflicts.exists() and not force:
            conflict_data = CalendarEventSerializer(conflicts, many=True).data
            raise ConflictException(conflict_data)

        serializer.save()

    def create(self, request, *args, **kwargs):
        """Override create to handle conflict responses."""
        try:
            return super().create(request, *args, **kwargs)
        except ConflictException as e:
            return Response(
                {
                    "detail": _("This event conflicts with existing events."),
                    "conflicts": e.conflicts,
                    "hint": _("Set force=true to save anyway."),
                },
                status=status.HTTP_409_CONFLICT,
            )

    def update(self, request, *args, **kwargs):
        """Override update to handle conflict responses."""
        try:
            return super().update(request, *args, **kwargs)
        except ConflictException as e:
            return Response(
                {
                    "detail": _("This event conflicts with existing events."),
                    "conflicts": e.conflicts,
                    "hint": _("Set force=true to save anyway."),
                },
                status=status.HTTP_409_CONFLICT,
            )

    @extend_schema(
        summary="Reschedule event",
        description="Reschedule a calendar event to a new time. Also updates linked task.",
        request=CalendarEventRescheduleSerializer,
        tags=["Calendar Events"],
        responses={
            200: CalendarEventSerializer,
            409: OpenApiResponse(description="Time conflict"),
        },
    )
    @action(detail=True, methods=["patch"], url_path="reschedule")
    def reschedule(self, request, pk=None):
        """Reschedule a calendar event to new start/end times."""
        event = self.get_object()
        serializer = CalendarEventRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_start = serializer.validated_data["start_time"]
        new_end = serializer.validated_data["end_time"]
        force = serializer.validated_data.get("force", False)

        conflicts = _check_conflicts(
            request.user, new_start, new_end, exclude_event_id=event.id
        )

        if conflicts.exists() and not force:
            return Response(
                {
                    "detail": _("This time conflicts with existing events."),
                    "conflicts": CalendarEventSerializer(conflicts, many=True).data,
                    "hint": _("Set force=true to save anyway."),
                },
                status=status.HTTP_409_CONFLICT,
            )

        event.start_time = new_start
        event.end_time = new_end
        event.status = "scheduled"
        event.save(update_fields=["start_time", "end_time", "status", "updated_at"])

        # Update linked task scheduled_date if present
        if event.task:
            event.task.scheduled_date = new_start
            event.task.save(update_fields=["scheduled_date"])

        return Response(CalendarEventSerializer(event).data)

    @extend_schema(
        summary="Check conflicts",
        description="Pre-flight conflict check. Returns overlapping events and blocked time blocks without creating anything.",
        request=CheckConflictsSerializer,
        tags=["Calendar Events"],
        responses={200: CheckConflictsResponseSerializer},
    )
    @action(detail=False, methods=["post"], url_path="check-conflicts")
    def check_conflicts(self, request):
        """Check for scheduling conflicts without creating an event."""
        serializer = CheckConflictsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        start_time = serializer.validated_data["start_time"]
        end_time = serializer.validated_data["end_time"]
        exclude_event_id = serializer.validated_data.get("exclude_event_id")

        # Check overlapping calendar events
        event_conflicts = _check_conflicts(
            request.user,
            start_time,
            end_time,
            exclude_event_id=exclude_event_id,
        )
        event_conflict_data = []
        for evt in event_conflicts:
            event_conflict_data.append(
                {
                    "id": str(evt.id),
                    "title": evt.title,
                    "start_time": evt.start_time.isoformat(),
                    "end_time": evt.end_time.isoformat(),
                    "type": "event",
                }
            )

        # Check overlapping blocked time blocks
        timeblock_conflicts = _check_timeblock_conflicts(
            request.user,
            start_time,
            end_time,
        )

        all_conflicts = event_conflict_data + timeblock_conflicts

        return Response(
            {
                "has_conflicts": len(all_conflicts) > 0,
                "conflicts": all_conflicts,
            }
        )

    @extend_schema(
        summary="Skip occurrence",
        description="Skip a single occurrence of a recurring event by date.",
        request=SkipOccurrenceSerializer,
        responses={201: RecurrenceExceptionSerializer},
        tags=["Calendar Events"],
    )
    @action(detail=True, methods=["post"], url_path="skip-occurrence")
    def skip_occurrence(self, request, pk=None):
        """Skip a single occurrence of a recurring event."""
        event = self.get_object()

        if not event.is_recurring:
            return Response(
                {"detail": _("This event is not recurring.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SkipOccurrenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        original_date = serializer.validated_data["original_date"]

        # Upsert: update existing exception or create new one
        exception, created = RecurrenceException.objects.update_or_create(
            parent_event=event,
            original_date=original_date,
            defaults={
                "skip_occurrence": True,
                "modified_title": "",
                "modified_start_time": None,
                "modified_end_time": None,
            },
        )

        return Response(
            RecurrenceExceptionSerializer(exception).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Modify occurrence",
        description="Modify a single occurrence of a recurring event (title, start_time, end_time).",
        request=ModifyOccurrenceSerializer,
        responses={201: RecurrenceExceptionSerializer},
        tags=["Calendar Events"],
    )
    @action(detail=True, methods=["post"], url_path="modify-occurrence")
    def modify_occurrence(self, request, pk=None):
        """Modify a single occurrence of a recurring event."""
        event = self.get_object()

        if not event.is_recurring:
            return Response(
                {"detail": _("This event is not recurring.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ModifyOccurrenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        original_date = data["original_date"]

        exception, created = RecurrenceException.objects.update_or_create(
            parent_event=event,
            original_date=original_date,
            defaults={
                "skip_occurrence": False,
                "modified_title": data.get("title", ""),
                "modified_start_time": data.get("start_time"),
                "modified_end_time": data.get("end_time"),
            },
        )

        return Response(
            RecurrenceExceptionSerializer(exception).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="List exceptions",
        description="List all recurrence exceptions (skips and modifications) for a recurring event.",
        responses={200: RecurrenceExceptionSerializer(many=True)},
        tags=["Calendar Events"],
    )
    @action(detail=True, methods=["get"], url_path="exceptions")
    def exceptions(self, request, pk=None):
        """List all recurrence exceptions for a recurring event."""
        event = self.get_object()
        exceptions = RecurrenceException.objects.filter(parent_event=event)
        return Response(
            RecurrenceExceptionSerializer(exceptions, many=True).data,
        )

    @extend_schema(
        summary="List event categories",
        description="Returns the list of available event categories with their labels and suggested icons.",
        tags=["Calendar Events"],
        responses={
            200: inline_serializer(
                name="CategoryListResponse",
                fields={
                    "categories": drf_serializers.ListField(
                        help_text="List of available event categories.",
                    ),
                },
            ),
        },
    )
    @action(detail=False, methods=["get"], url_path="categories")
    def categories(self, request):
        """Return available event categories with labels and icon hints."""
        category_list = [
            {"key": "meeting", "label": "Meeting", "icon": "Users"},
            {"key": "deadline", "label": "Deadline", "icon": "AlertTriangle"},
            {"key": "milestone", "label": "Milestone", "icon": "Flag"},
            {"key": "habit", "label": "Habit", "icon": "Repeat"},
            {"key": "social", "label": "Social", "icon": "Heart"},
            {"key": "health", "label": "Health", "icon": "Activity"},
            {"key": "learning", "label": "Learning", "icon": "BookOpen"},
            {"key": "custom", "label": "Custom", "icon": "Star"},
        ]
        return Response({"categories": category_list})

    @extend_schema(
        summary="Search calendar events and tasks",
        description=(
            "Search events and tasks by title, description, or location. "
            "Since these fields are encrypted, all user events are fetched "
            "and filtered in Python. Returns up to 50 combined results."
        ),
        parameters=[
            OpenApiParameter(
                name="q", type=str, required=True, description="Search query term"
            ),
        ],
        responses={200: CalendarEventSerializer(many=True)},
        tags=["Calendar Events"],
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        """Search calendar events and tasks by title, description, or location."""
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response(
                {"detail": _('Search query parameter "q" is required.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        query_lower = query.lower()
        results = []

        # --- Search CalendarEvents (encrypted fields, filter in Python) ---
        all_events = (
            CalendarEvent.objects.filter(
                user=request.user,
            )
            .select_related("task", "task__goal", "task__goal__dream")
            .prefetch_related("exceptions")
        )

        for event in all_events:
            match_context = None
            title_str = event.title or ""
            desc_str = event.description or ""
            loc_str = event.location or ""

            if query_lower in title_str.lower():
                match_context = "title"
            elif query_lower in desc_str.lower():
                match_context = "description"
            elif query_lower in loc_str.lower():
                match_context = "location"

            if match_context:
                event_data = CalendarEventSerializer(event).data
                event_data["match_context"] = match_context
                event_data["result_type"] = "event"
                results.append(event_data)

        # --- Search Tasks (encrypted title, filter in Python) ---
        all_tasks = Task.objects.filter(
            goal__dream__user=request.user,
            scheduled_date__isnull=False,
        ).select_related("goal", "goal__dream")

        for task in all_tasks:
            title_str = task.title or ""
            if query_lower in title_str.lower():
                results.append(
                    {
                        "id": str(task.id),
                        "title": task.title,
                        "description": task.description or "",
                        "start_time": (
                            task.scheduled_date.isoformat()
                            if task.scheduled_date
                            else None
                        ),
                        "end_time": (
                            task.scheduled_date.isoformat()
                            if task.scheduled_date
                            else None
                        ),
                        "all_day": False,
                        "location": "",
                        "status": task.status,
                        "is_recurring": False,
                        "recurrence_rule": None,
                        "task": str(task.id),
                        "task_title": task.title,
                        "goal_title": task.goal.title if task.goal else "",
                        "dream_id": (
                            str(task.goal.dream.id)
                            if task.goal and task.goal.dream
                            else None
                        ),
                        "dream_title": (
                            task.goal.dream.title
                            if task.goal and task.goal.dream
                            else ""
                        ),
                        "match_context": "title",
                        "result_type": "task",
                    }
                )

        # Sort by start_time, then limit to 50
        def sort_key(item):
            st = item.get("start_time")
            if st:
                try:
                    return datetime.fromisoformat(str(st).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            return datetime.min.replace(tzinfo=dt_timezone.utc)

        results.sort(key=sort_key)
        results = results[:50]

        return Response(results)

    @extend_schema(
        summary="Snooze event notification",
        description="Snooze the in-app notification for this event by the given number of minutes.",
        request=inline_serializer(
            name="SnoozeRequest",
            fields={
                "minutes": drf_serializers.IntegerField(
                    help_text="Minutes to snooze (5, 10, 15, 30, or 60)"
                )
            },
        ),
        responses={
            200: inline_serializer(
                name="SnoozeResponse",
                fields={
                    "detail": drf_serializers.CharField(),
                    "snoozed_until": drf_serializers.DateTimeField(),
                },
            )
        },
        tags=["Calendar Events"],
    )
    @action(detail=True, methods=["post"], url_path="snooze")
    def snooze(self, request, pk=None):
        """Snooze in-app notification for this event by N minutes."""
        event = self.get_object()
        allowed_minutes = (5, 10, 15, 30, 60)
        minutes = request.data.get("minutes")
        if minutes is None or int(minutes) not in allowed_minutes:
            return Response(
                {"detail": _("minutes must be one of: 5, 10, 15, 30, 60")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        minutes = int(minutes)
        event.snoozed_until = timezone.now() + timedelta(minutes=minutes)
        event.save(update_fields=["snoozed_until", "updated_at"])
        return Response(
            {
                "detail": _("Notification snoozed for %(minutes)d minutes.")
                % {"minutes": minutes},
                "snoozed_until": event.snoozed_until.isoformat(),
            }
        )

    @extend_schema(
        summary="Dismiss event notification",
        description=(
            "Dismiss the current in-app notification for this event. "
            "Marks all pending reminders as sent so they will not fire again."
        ),
        request=None,
        responses={
            200: inline_serializer(
                name="DismissResponse",
                fields={"detail": drf_serializers.CharField()},
            )
        },
        tags=["Calendar Events"],
    )
    @action(detail=True, methods=["post"], url_path="dismiss")
    def dismiss(self, request, pk=None):
        """Dismiss current reminders for this event (marks them as sent)."""
        event = self.get_object()
        reminders_list = event.reminders or []
        if not reminders_list and event.reminder_minutes_before:
            reminders_list = [
                {"minutes_before": event.reminder_minutes_before, "type": "push"}
            ]
        already_sent = list(event.reminders_sent or [])
        for reminder in reminders_list:
            minutes_before = reminder.get("minutes_before", 0)
            reminder_key = "%d_%s" % (minutes_before, event.start_time.isoformat())
            if reminder_key not in already_sent:
                already_sent.append(reminder_key)
        event.reminders_sent = already_sent
        # Also clear any active snooze
        event.snoozed_until = None
        event.save(update_fields=["reminders_sent", "snoozed_until", "updated_at"])
        return Response({"detail": _("Notification dismissed.")})


class ConflictException(Exception):
    """Raised when an event conflicts with existing events."""

    def __init__(self, conflicts):
        self.conflicts = conflicts


@extend_schema_view(
    list=extend_schema(
        summary="List time blocks",
        description="Get all time blocks for the current user",
        tags=["Time Blocks"],
    ),
    create=extend_schema(
        summary="Create time block",
        description="Create a new time block",
        tags=["Time Blocks"],
    ),
    retrieve=extend_schema(
        summary="Get time block",
        description="Get a specific time block",
        tags=["Time Blocks"],
    ),
    update=extend_schema(
        summary="Update time block",
        description="Update a time block",
        tags=["Time Blocks"],
    ),
    partial_update=extend_schema(
        summary="Partial update time block",
        description="Partially update a time block",
        tags=["Time Blocks"],
    ),
    destroy=extend_schema(
        summary="Delete time block",
        description="Delete a time block",
        tags=["Time Blocks"],
    ),
)
class TimeBlockViewSet(viewsets.ModelViewSet):
    """CRUD operations for time blocks."""

    permission_classes = [IsAuthenticated]
    serializer_class = TimeBlockSerializer

    def get_queryset(self):
        """Get time blocks for current user."""
        if getattr(self, "swagger_fake_view", False):
            return TimeBlock.objects.none()
        return TimeBlock.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Create time block for current user."""
        serializer.save(user=self.request.user)


@extend_schema_view(
    list=extend_schema(
        summary="List templates",
        description="Get all time block templates for the current user plus presets",
        tags=["Time Block Templates"],
    ),
    create=extend_schema(
        summary="Create template",
        description="Create a new time block template",
        tags=["Time Block Templates"],
    ),
    retrieve=extend_schema(
        summary="Get template",
        description="Get a specific time block template",
        tags=["Time Block Templates"],
    ),
    update=extend_schema(
        summary="Update template",
        description="Update a time block template",
        tags=["Time Block Templates"],
    ),
    partial_update=extend_schema(
        summary="Partial update template",
        description="Partially update a time block template",
        tags=["Time Block Templates"],
    ),
    destroy=extend_schema(
        summary="Delete template",
        description="Delete a time block template",
        tags=["Time Block Templates"],
    ),
)
class TimeBlockTemplateViewSet(viewsets.ModelViewSet):
    """CRUD operations for time block templates, plus apply/save_current/presets actions."""

    permission_classes = [IsAuthenticated]
    serializer_class = TimeBlockTemplateSerializer

    def get_queryset(self):
        """Get templates: user's own + system presets."""
        if getattr(self, "swagger_fake_view", False):
            return TimeBlockTemplate.objects.none()
        return TimeBlockTemplate.objects.filter(
            Q(user=self.request.user) | Q(is_preset=True)
        )

    def perform_create(self, serializer):
        """Create template for current user."""
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        """Prevent editing system presets."""
        if (
            serializer.instance.is_preset
            and serializer.instance.user != self.request.user
        ):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(_("Cannot edit system preset templates."))
        serializer.save()

    def perform_destroy(self, instance):
        """Prevent deleting system presets."""
        if instance.is_preset and instance.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(_("Cannot delete system preset templates."))
        instance.delete()

    @extend_schema(
        summary="Apply template",
        description="Apply a template -- deletes existing time blocks and creates new ones from the template.",
        tags=["Time Block Templates"],
        request=None,
        responses={200: TimeBlockSerializer(many=True)},
    )
    @action(detail=True, methods=["post"], url_path="apply")
    def apply(self, request, pk=None):
        """Apply a template: delete existing time blocks, create new ones from template blocks."""
        template = self.get_object()

        # Delete all existing time blocks for this user
        TimeBlock.objects.filter(user=request.user).delete()

        # Create new time blocks from template
        created_blocks = []
        for block_data in template.blocks:
            tb = TimeBlock.objects.create(
                user=request.user,
                block_type=block_data["block_type"],
                day_of_week=block_data["day_of_week"],
                start_time=block_data["start_time"],
                end_time=block_data["end_time"],
                is_active=True,
            )
            created_blocks.append(tb)

        serializer = TimeBlockSerializer(created_blocks, many=True)
        return Response(
            {
                "detail": _('Template "%(name)s" applied successfully.')
                % {"name": template.name},
                "blocks": serializer.data,
                "count": len(created_blocks),
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Save current blocks as template",
        description="Save the user's current time blocks as a new reusable template.",
        tags=["Time Block Templates"],
        request=SaveCurrentTemplateSerializer,
        responses={201: TimeBlockTemplateSerializer},
    )
    @action(detail=False, methods=["post"], url_path="save-current")
    def save_current(self, request):
        """Save current time blocks as a new template."""
        serializer = SaveCurrentTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        current_blocks = TimeBlock.objects.filter(user=request.user, is_active=True)
        if not current_blocks.exists():
            return Response(
                {"detail": _("No active time blocks to save.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        blocks_data = []
        for block in current_blocks:
            blocks_data.append(
                {
                    "block_type": block.block_type,
                    "day_of_week": block.day_of_week,
                    "start_time": block.start_time.strftime("%H:%M"),
                    "end_time": block.end_time.strftime("%H:%M"),
                }
            )

        template = TimeBlockTemplate.objects.create(
            user=request.user,
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description", ""),
            blocks=blocks_data,
        )

        return Response(
            TimeBlockTemplateSerializer(template).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="List preset templates",
        description="List system-provided preset templates.",
        tags=["Time Block Templates"],
        responses={200: TimeBlockTemplateSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="presets")
    def presets(self, request):
        """List system preset templates (is_preset=True)."""
        presets_qs = TimeBlockTemplate.objects.filter(is_preset=True)
        serializer = TimeBlockTemplateSerializer(presets_qs, many=True)
        return Response(serializer.data)


class CalendarViewSet(viewsets.ViewSet):
    """Calendar views and operations."""

    permission_classes = [IsAuthenticated]
    serializer_class = CalendarTaskSerializer

    @extend_schema(
        summary="Get or update calendar preferences",
        description=(
            "GET returns current calendar preferences (buffer_minutes, min_event_duration). "
            "POST updates them. These preferences control buffer zones between events and "
            "minimum event duration for smart scheduling."
        ),
        tags=["Calendar"],
        request=CalendarPreferencesSerializer,
        responses={200: CalendarPreferencesSerializer},
    )
    @action(detail=False, methods=["get", "post"], url_path="preferences")
    def preferences(self, request):
        """Get or update calendar preferences (buffer time, min event duration)."""
        user = request.user
        current_prefs = user.calendar_preferences or {}

        if request.method == "GET":
            data = {
                "buffer_minutes": current_prefs.get("buffer_minutes", 15),
                "min_event_duration": current_prefs.get("min_event_duration", 30),
            }
            return Response(data)

        # POST -- update preferences
        serializer = CalendarPreferencesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_prefs = dict(current_prefs)
        new_prefs["buffer_minutes"] = serializer.validated_data["buffer_minutes"]
        new_prefs["min_event_duration"] = serializer.validated_data[
            "min_event_duration"
        ]

        user.calendar_preferences = new_prefs
        user.save(update_fields=["calendar_preferences"])

        return Response(
            {
                "buffer_minutes": new_prefs["buffer_minutes"],
                "min_event_duration": new_prefs["min_event_duration"],
            }
        )

    @extend_schema(
        summary="Get upcoming event alerts",
        description=(
            "Returns events with reminders due in the next 5 minutes. "
            "Used by the frontend to poll for in-app notification popups. "
            "Events that are snoozed (snoozed_until > now) or whose "
            "reminders have already been sent are excluded."
        ),
        tags=["Calendar"],
        responses={200: CalendarEventSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="upcoming-alerts")
    def upcoming_alerts(self, request):
        """Return events with reminders due in the next 5 minutes for in-app popups."""
        now = timezone.now()
        alert_window = now + timedelta(minutes=5)

        # Get scheduled events starting within the next 24 hours (covers all
        # reasonable reminder offsets that would fire in the next 5 minutes).
        max_lookahead = now + timedelta(hours=24)

        events = (
            CalendarEvent.objects.filter(
                user=request.user,
                status="scheduled",
                start_time__gt=now,
                start_time__lte=max_lookahead,
            )
            .filter(Q(snoozed_until__isnull=True) | Q(snoozed_until__lte=now))
            .select_related(
                "task",
                "task__goal",
                "task__goal__dream",
            )
            .prefetch_related("exceptions")
        )

        alertable = []
        for event in events:
            reminders_list = event.reminders or []
            if not reminders_list and event.reminder_minutes_before:
                reminders_list = [
                    {"minutes_before": event.reminder_minutes_before, "type": "push"}
                ]
            if not reminders_list:
                continue

            already_sent = list(event.reminders_sent or [])

            for reminder in reminders_list:
                minutes_before = reminder.get("minutes_before", 0)
                reminder_time = event.start_time - timedelta(minutes=minutes_before)
                reminder_key = "%d_%s" % (minutes_before, event.start_time.isoformat())

                # Reminder fires within [now, alert_window) and hasn't been sent
                if (
                    now <= reminder_time < alert_window
                    and reminder_key not in already_sent
                ):
                    alertable.append(event)
                    break  # Only need one matching reminder per event

        serializer = CalendarEventSerializer(alertable, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Get or update user timezone",
        description=(
            "GET returns the user's home timezone. "
            "PUT updates it. The timezone is used for display purposes; "
            "all times are stored in UTC."
        ),
        tags=["Calendar"],
        request=inline_serializer(
            name="TimezoneUpdateRequest",
            fields={
                "timezone": drf_serializers.CharField(
                    max_length=50,
                    help_text="IANA timezone identifier (e.g. America/New_York)",
                )
            },
        ),
        responses={
            200: inline_serializer(
                name="TimezoneResponse",
                fields={
                    "timezone": drf_serializers.CharField(
                        help_text="User home timezone"
                    )
                },
            )
        },
    )
    @action(detail=False, methods=["get", "put"], url_path="timezone")
    def timezone_view(self, request):
        """Get or update the user's home timezone."""
        import zoneinfo

        if request.method == "GET":
            return Response({"timezone": request.user.timezone or "UTC"})

        # PUT -- update timezone
        tz_value = request.data.get("timezone", "").strip()
        if not tz_value:
            return Response(
                {"error": _("timezone is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate it is a real IANA timezone
        try:
            zoneinfo.ZoneInfo(tz_value)
        except (KeyError, Exception):
            return Response(
                {"error": _("Invalid timezone identifier")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.timezone = tz_value
        request.user.save(update_fields=["timezone"])

        return Response({"timezone": tz_value})

    @extend_schema(
        summary="Get calendar view",
        description="Get tasks for a date range",
        tags=["Calendar"],
        parameters=[
            OpenApiParameter(
                name="start",
                description="Start date (ISO format)",
                required=True,
                type=str,
            ),
            OpenApiParameter(
                name="end", description="End date (ISO format)", required=True, type=str
            ),
        ],
        responses={200: CalendarTaskSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def view(self, request):
        """Get calendar view for date range."""
        start_date = request.query_params.get("start")
        end_date = request.query_params.get("end")

        if not start_date or not end_date:
            return Response(
                {"error": _("start and end dates required (ISO format)")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            return Response(
                {
                    "error": _(
                        "Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get tasks in date range
        tasks = (
            Task.objects.filter(
                goal__dream__user=request.user,
                scheduled_date__gte=start,
                scheduled_date__lte=end,
            )
            .select_related("goal__dream")
            .order_by("scheduled_date")
        )

        # Format tasks for calendar
        calendar_tasks = []
        for task in tasks:
            calendar_tasks.append(
                {
                    "task_id": task.id,
                    "task_title": task.title,
                    "goal_id": task.goal.id,
                    "goal_title": task.goal.title,
                    "dream_id": task.goal.dream.id,
                    "dream_title": task.goal.dream.title,
                    "scheduled_date": task.scheduled_date,
                    "scheduled_time": task.scheduled_time,
                    "duration_mins": task.duration_mins,
                    "status": task.status,
                    "is_two_minute_start": task.is_two_minute_start,
                }
            )

        return Response(calendar_tasks)

    @extend_schema(
        summary="Today's tasks",
        description="Get all tasks scheduled for today",
        tags=["Calendar"],
        responses={200: CalendarTaskSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def today(self, request):
        """Get tasks for today."""
        today = timezone.now().date()

        tasks = (
            Task.objects.filter(
                goal__dream__user=request.user, scheduled_date__date=today
            )
            .select_related("goal__dream")
            .order_by("scheduled_time", "order")
        )

        calendar_tasks = []
        for task in tasks:
            calendar_tasks.append(
                {
                    "task_id": task.id,
                    "task_title": task.title,
                    "goal_id": task.goal.id,
                    "goal_title": task.goal.title,
                    "dream_id": task.goal.dream.id,
                    "dream_title": task.goal.dream.title,
                    "scheduled_date": task.scheduled_date,
                    "scheduled_time": task.scheduled_time,
                    "duration_mins": task.duration_mins,
                    "status": task.status,
                    "is_two_minute_start": task.is_two_minute_start,
                }
            )

        return Response(calendar_tasks)

    @extend_schema(
        summary="Reschedule task",
        description="Reschedule a task to a new date",
        tags=["Calendar"],
        responses={200: dict},
    )
    @action(detail=False, methods=["post"])
    def reschedule(self, request):
        """Reschedule a task."""
        task_id = request.data.get("task_id")
        new_date = request.data.get("new_date")

        if not task_id or not new_date:
            return Response(
                {"error": _("task_id and new_date required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task = Task.objects.get(id=task_id, goal__dream__user=request.user)

            task.scheduled_date = datetime.fromisoformat(
                new_date.replace("Z", "+00:00")
            )
            task.save(update_fields=["scheduled_date"])

            return Response(
                {
                    "message": _("Task rescheduled successfully"),
                    "task_id": task.id,
                    "new_date": task.scheduled_date,
                }
            )

        except Task.DoesNotExist:
            return Response(
                {"error": _("Task not found")}, status=status.HTTP_404_NOT_FOUND
            )
        except ValueError:
            return Response(
                {"error": _("Invalid date format")}, status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        summary="Productivity heatmap data",
        description="Get per-day productivity data for a date range, suitable for heatmap display.",
        tags=["Calendar"],
        parameters=[
            OpenApiParameter(
                name="start",
                description="Start date (YYYY-MM-DD)",
                required=True,
                type=str,
            ),
            OpenApiParameter(
                name="end", description="End date (YYYY-MM-DD)", required=True, type=str
            ),
        ],
        responses={200: HeatmapDaySerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def heatmap(self, request):
        """Get per-day productivity data for a date range."""
        start_str = request.query_params.get("start")
        end_str = request.query_params.get("end")

        if not start_str or not end_str:
            return Response(
                {"error": _("start and end query params required (YYYY-MM-DD)")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": _("Invalid date format. Use YYYY-MM-DD.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cap range at 365 days to prevent abuse
        if (end_date - start_date).days > 365:
            return Response(
                {"error": _("Date range cannot exceed 365 days.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user

        # --- Gather per-day data ---
        # 1) Tasks scheduled in range (all statuses) grouped by date
        tasks_in_range = (
            Task.objects.filter(
                goal__dream__user=user,
                scheduled_date__date__gte=start_date,
                scheduled_date__date__lte=end_date,
            )
            .values("scheduled_date__date")
            .annotate(
                total=Count("id"),
                completed=Count("id", filter=Q(status="completed")),
            )
        )
        tasks_by_date = {}
        for row in tasks_in_range:
            d = row["scheduled_date__date"]
            tasks_by_date[d] = {"total": row["total"], "completed": row["completed"]}

        # 2) Calendar events in range grouped by date
        events_in_range = (
            CalendarEvent.objects.filter(
                user=user,
                start_time__date__gte=start_date,
                start_time__date__lte=end_date,
            )
            .exclude(status="cancelled")
            .values("start_time__date")
            .annotate(
                count=Count("id"),
            )
        )
        events_by_date = {}
        for row in events_in_range:
            events_by_date[row["start_time__date"]] = row["count"]

        # 3) Focus sessions in range grouped by date
        focus_in_range = (
            FocusSession.objects.filter(
                user=user,
                completed=True,
                started_at__date__gte=start_date,
                started_at__date__lte=end_date,
            )
            .values("started_at__date")
            .annotate(
                total_minutes=Sum("actual_minutes"),
            )
        )
        focus_by_date = {}
        for row in focus_in_range:
            focus_by_date[row["started_at__date"]] = row["total_minutes"] or 0

        # --- Build per-day response ---
        result = []
        current = start_date
        one_day = timedelta(days=1)

        while current <= end_date:
            task_data = tasks_by_date.get(current, {"total": 0, "completed": 0})
            tasks_completed = task_data["completed"]
            tasks_total = task_data["total"]
            events_count = events_by_date.get(current, 0)
            focus_minutes = focus_by_date.get(current, 0)

            # Productivity score = weighted combination (0.0-1.0)
            # Tasks weight: 0.4, Focus weight: 0.3, Events weight: 0.3
            task_score = 0.0
            if tasks_total > 0:
                task_score = min(tasks_completed / tasks_total, 1.0)
            elif tasks_completed > 0:
                task_score = 1.0

            # Focus score: 60 minutes = full score
            focus_score = min(focus_minutes / 60.0, 1.0) if focus_minutes > 0 else 0.0

            # Events score: 3+ events = full score
            events_score = min(events_count / 3.0, 1.0) if events_count > 0 else 0.0

            productivity_score = round(
                task_score * 0.4 + focus_score * 0.3 + events_score * 0.3,
                3,
            )

            result.append(
                {
                    "date": current.isoformat(),
                    "tasks_completed": tasks_completed,
                    "tasks_total": tasks_total,
                    "events_count": events_count,
                    "focus_minutes": focus_minutes,
                    "productivity_score": productivity_score,
                }
            )

            current += one_day

        return Response(result)

    @extend_schema(
        summary="Weekly schedule score",
        description="Calculate weekly schedule adherence score with detailed breakdown.",
        tags=["Calendar"],
        parameters=[
            OpenApiParameter(
                name="week",
                description="ISO week start date (YYYY-MM-DD, Monday). Defaults to current week.",
                required=False,
                type=str,
            ),
        ],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="schedule-score")
    def schedule_score(self, request):
        """Calculate weekly schedule adherence score."""
        week_param = request.query_params.get("week")
        today = timezone.now().date()

        if week_param:
            try:
                week_start = datetime.strptime(week_param, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {
                        "error": _(
                            "Invalid week format. Use YYYY-MM-DD (Monday of the week)."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # Default to current week (Monday)
            week_start = today - timedelta(days=today.weekday())

        week_end = week_start + timedelta(days=6)
        user = request.user

        # --- Tasks ---
        tasks_qs = Task.objects.filter(
            goal__dream__user=user,
            scheduled_date__date__gte=week_start,
            scheduled_date__date__lte=week_end,
        )
        tasks_scheduled = tasks_qs.count()
        tasks_completed = tasks_qs.filter(status="completed").count()
        task_completion_rate = round(
            (tasks_completed / tasks_scheduled * 100) if tasks_scheduled > 0 else 0, 1
        )

        # --- Events (not cancelled) ---
        events_total = CalendarEvent.objects.filter(
            user=user,
            start_time__date__gte=week_start,
            start_time__date__lte=week_end,
        ).count()
        events_attended = (
            CalendarEvent.objects.filter(
                user=user,
                start_time__date__gte=week_start,
                start_time__date__lte=week_end,
            )
            .exclude(status="cancelled")
            .count()
        )

        # --- Focus blocks (planned from TimeBlock with focus_block=True) ---
        focus_time_blocks = TimeBlock.objects.filter(
            user=user,
            is_active=True,
            focus_block=True,
        )
        focus_minutes_planned = 0
        for fb in focus_time_blocks:
            start_dt = datetime.combine(week_start, fb.start_time)
            end_dt = datetime.combine(week_start, fb.end_time)
            block_mins = max(0, int((end_dt - start_dt).total_seconds() / 60))
            focus_minutes_planned += block_mins

        # --- Focus sessions (actual) ---
        focus_agg = FocusSession.objects.filter(
            user=user,
            completed=True,
            started_at__date__gte=week_start,
            started_at__date__lte=week_end,
        ).aggregate(total=Sum("actual_minutes"))
        focus_minutes_actual = focus_agg["total"] or 0

        # --- Time block adherence ---
        all_blocks = TimeBlock.objects.filter(user=user, is_active=True)
        total_block_slots = all_blocks.count()

        used_block_slots = 0
        for block in all_blocks:
            block_day = week_start + timedelta(days=block.day_of_week)
            if block_day > week_end:
                continue
            block_start_dt = timezone.make_aware(
                datetime.combine(block_day, block.start_time),
                timezone.get_current_timezone(),
            )
            block_end_dt = timezone.make_aware(
                datetime.combine(block_day, block.end_time),
                timezone.get_current_timezone(),
            )
            has_activity = (
                CalendarEvent.objects.filter(
                    user=user,
                    start_time__lt=block_end_dt,
                    end_time__gt=block_start_dt,
                )
                .exclude(status="cancelled")
                .exists()
            )
            if not has_activity:
                has_activity = Task.objects.filter(
                    goal__dream__user=user,
                    scheduled_date__date=block_day,
                    status="completed",
                ).exists()
            if has_activity:
                used_block_slots += 1

        time_block_adherence = round(
            (
                (used_block_slots / total_block_slots * 100)
                if total_block_slots > 0
                else 0
            ),
            1,
        )

        # --- Overall score (weighted composite 0-100) ---
        task_score = (task_completion_rate / 100) * 40
        focus_score_val = (
            min(
                (
                    (focus_minutes_actual / focus_minutes_planned)
                    if focus_minutes_planned > 0
                    else (1.0 if focus_minutes_actual > 0 else 0)
                ),
                1.0,
            )
            * 30
        )
        block_score = (time_block_adherence / 100) * 20
        event_score = (
            min(events_attended / max(events_total, 1), 1.0) if events_total > 0 else 0
        ) * 10
        overall_score = round(
            task_score + focus_score_val + block_score + event_score, 1
        )
        overall_score = max(0, min(100, overall_score))

        # --- Streak (consecutive days with >50% adherence) ---
        streak_days = 0
        check_date = today
        while True:
            day_tasks = Task.objects.filter(
                goal__dream__user=user,
                scheduled_date__date=check_date,
            )
            day_total = day_tasks.count()
            day_completed = day_tasks.filter(status="completed").count()
            day_events = (
                CalendarEvent.objects.filter(
                    user=user,
                    start_time__date=check_date,
                )
                .exclude(status="cancelled")
                .count()
            )
            day_focus = (
                FocusSession.objects.filter(
                    user=user,
                    completed=True,
                    started_at__date=check_date,
                ).aggregate(total=Sum("actual_minutes"))["total"]
                or 0
            )

            day_task_score = (day_completed / day_total) if day_total > 0 else 0
            day_focus_score = min(day_focus / 30.0, 1.0) if day_focus > 0 else 0
            day_event_score = 1.0 if day_events > 0 else 0
            day_adherence = (
                day_task_score * 0.5 + day_focus_score * 0.3 + day_event_score * 0.2
            )

            if day_adherence > 0.5 or (
                day_total == 0
                and day_events == 0
                and day_focus == 0
                and check_date == today
            ):
                streak_days += 1
                check_date -= timedelta(days=1)
                if streak_days >= 365:
                    break
            else:
                break

        # --- Grade ---
        if overall_score >= 97:
            grade = "A+"
        elif overall_score >= 90:
            grade = "A"
        elif overall_score >= 85:
            grade = "B+"
        elif overall_score >= 75:
            grade = "B"
        elif overall_score >= 65:
            grade = "C+"
        elif overall_score >= 55:
            grade = "C"
        elif overall_score >= 40:
            grade = "D"
        else:
            grade = "F"

        # --- Week comparison (vs previous week) ---
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = prev_week_start + timedelta(days=6)
        prev_tasks_total = Task.objects.filter(
            goal__dream__user=user,
            scheduled_date__date__gte=prev_week_start,
            scheduled_date__date__lte=prev_week_end,
        ).count()
        prev_tasks_completed = Task.objects.filter(
            goal__dream__user=user,
            scheduled_date__date__gte=prev_week_start,
            scheduled_date__date__lte=prev_week_end,
            status="completed",
        ).count()
        prev_focus_agg = FocusSession.objects.filter(
            user=user,
            completed=True,
            started_at__date__gte=prev_week_start,
            started_at__date__lte=prev_week_end,
        ).aggregate(total=Sum("actual_minutes"))
        prev_focus_actual = prev_focus_agg["total"] or 0
        prev_task_rate = (
            (prev_tasks_completed / prev_tasks_total * 100)
            if prev_tasks_total > 0
            else 0
        )
        prev_focus_rate = (
            min(
                (
                    (prev_focus_actual / focus_minutes_planned)
                    if focus_minutes_planned > 0
                    else (1.0 if prev_focus_actual > 0 else 0)
                ),
                1.0,
            )
            * 100
        )
        prev_overall = round(prev_task_rate * 0.4 + prev_focus_rate * 0.3, 1)
        week_comparison = round(overall_score - prev_overall, 1)

        # --- Tips ---
        tips = []
        if task_completion_rate < 50 and tasks_scheduled > 0:
            tips.append(
                "Try breaking larger tasks into smaller steps to boost completion rate."
            )
        if (
            focus_minutes_actual < focus_minutes_planned * 0.5
            and focus_minutes_planned > 0
        ):
            tips.append(
                "Schedule focus blocks during your peak energy hours for better adherence."
            )
        if time_block_adherence < 50 and total_block_slots > 0:
            tips.append(
                "Review your time blocks \u2014 consider adjusting them to match your actual routine."
            )
        if streak_days < 3:
            tips.append(
                "Aim for at least one completed task each day to build momentum."
            )
        if events_attended < events_total and events_total > 0:
            tips.append(
                "Some events were cancelled this week. Protect your calendar commitments."
            )
        if not tips:
            if overall_score >= 80:
                tips.append("Great work this week! Keep the momentum going.")
            else:
                tips.append(
                    "Consistency is key \u2014 small daily wins add up to big results."
                )

        return Response(
            {
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "tasks_scheduled": tasks_scheduled,
                "tasks_completed": tasks_completed,
                "task_completion_rate": task_completion_rate,
                "events_attended": events_attended,
                "events_total": events_total,
                "focus_minutes_planned": focus_minutes_planned,
                "focus_minutes_actual": focus_minutes_actual,
                "time_block_adherence": time_block_adherence,
                "overall_score": overall_score,
                "streak_days": streak_days,
                "grade": grade,
                "week_comparison": week_comparison,
                "tips": tips,
            }
        )

    @extend_schema(
        summary="Daily summary preview",
        description=(
            "Returns a preview of today's schedule: tasks, events, focus blocks, "
            "overdue items, and a motivational message. Can be called on-demand."
        ),
        tags=["Calendar"],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="daily-summary")
    def daily_summary(self, request):
        """Return today's schedule summary for the authenticated user."""
        import random
        import zoneinfo

        user = request.user

        # Determine user's local "today"
        try:
            user_tz = zoneinfo.ZoneInfo(user.timezone)
        except Exception:
            user_tz = zoneinfo.ZoneInfo("UTC")

        now = timezone.now()
        user_now = now.astimezone(user_tz)
        user_today = user_now.date()
        day_of_week = user_today.weekday()
        hour = user_now.hour

        # Greeting based on time of day
        if hour < 12:
            greeting = _("Good morning")
        elif hour < 17:
            greeting = _("Good afternoon")
        else:
            greeting = _("Good evening")

        display_name = user.display_name or user.email.split("@")[0]

        # --- Today's tasks ---
        today_tasks = (
            Task.objects.filter(
                goal__dream__user=user,
                goal__dream__status="active",
                scheduled_date__date=user_today,
            )
            .select_related("goal__dream")
            .order_by("scheduled_time", "order")
        )

        task_list = []
        for t in today_tasks[:10]:
            task_list.append(
                {
                    "id": str(t.id),
                    "title": t.title,
                    "status": t.status,
                    "scheduled_time": t.scheduled_time or "",
                    "duration_mins": t.duration_mins,
                    "dream_title": t.goal.dream.title,
                    "goal_title": t.goal.title,
                }
            )

        task_count = today_tasks.count()
        pending_count = today_tasks.filter(status="pending").count()
        completed_count = today_tasks.filter(status="completed").count()

        # --- Today's calendar events ---
        today_events = CalendarEvent.objects.filter(
            user=user,
            status="scheduled",
            start_time__date=user_today,
        ).order_by("start_time")

        event_list = []
        for ev in today_events[:10]:
            event_list.append(
                {
                    "id": str(ev.id),
                    "title": ev.title,
                    "start_time": ev.start_time.isoformat(),
                    "end_time": ev.end_time.isoformat(),
                    "all_day": ev.all_day,
                    "location": ev.location or "",
                }
            )

        event_count = today_events.count()

        # --- Focus blocks for today ---
        focus_blocks = TimeBlock.objects.filter(
            user=user,
            day_of_week=day_of_week,
            is_active=True,
            focus_block=True,
        ).order_by("start_time")

        focus_list = []
        for fb in focus_blocks:
            focus_list.append(
                {
                    "id": str(fb.id),
                    "block_type": fb.block_type,
                    "start_time": fb.start_time.isoformat(),
                    "end_time": fb.end_time.isoformat(),
                }
            )

        focus_block_count = focus_blocks.count()

        # --- Overdue tasks ---
        overdue_tasks = (
            Task.objects.filter(
                goal__dream__user=user,
                goal__dream__status="active",
                status="pending",
                scheduled_date__date__lt=user_today,
            )
            .select_related("goal__dream")
            .order_by("scheduled_date")
        )

        overdue_list = []
        for ot in overdue_tasks[:5]:
            overdue_list.append(
                {
                    "id": str(ot.id),
                    "title": ot.title,
                    "scheduled_date": (
                        ot.scheduled_date.date().isoformat()
                        if ot.scheduled_date
                        else ""
                    ),
                    "dream_title": ot.goal.dream.title,
                }
            )

        overdue_count = overdue_tasks.count()

        # --- Motivational message ---
        messages = [
            _("Make today count -- you are building something amazing!"),
            _("Small steps every day lead to big results."),
            _("Today is a new opportunity to move closer to your dreams."),
            _("Stay focused, stay determined. You've got this!"),
            _("Every task you complete is a step towards your dream life."),
            _("Your future self will thank you for today's effort."),
            _("Progress happens one day at a time. Let's make this one great!"),
            _("Believe in the power of a productive day."),
        ]
        motivational_message = random.choice(messages)

        return Response(
            {
                "greeting": "%s, %s!" % (greeting, display_name),
                "date": user_today.isoformat(),
                "task_count": task_count,
                "pending_count": pending_count,
                "completed_count": completed_count,
                "event_count": event_count,
                "focus_block_count": focus_block_count,
                "overdue_count": overdue_count,
                "tasks": task_list,
                "events": event_list,
                "focus_blocks": focus_list,
                "overdue_tasks": overdue_list,
                "motivational_message": motivational_message,
            }
        )

    @extend_schema(
        summary="Suggest time slots",
        description="Find optimal open time slots for a given date and duration. "
        "Returns both best-match slots for the requested duration and "
        "all free slots for the entire day with quality scores.",
        tags=["Calendar"],
        parameters=[
            OpenApiParameter(
                name="date", description="Date (YYYY-MM-DD)", required=True, type=str
            ),
            OpenApiParameter(
                name="duration_mins",
                description="Duration in minutes",
                required=True,
                type=int,
            ),
        ],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="suggest-time-slots")
    def suggest_time_slots(self, request):
        """Find optimal open time slots on a given date.

        Returns:
          - slots: best-match slots that fit the requested duration
          - free_slots: all free time windows for the day with quality scores
          - total_free_mins: total free minutes in the day
        """
        date_str = request.query_params.get("date")
        duration_str = request.query_params.get("duration_mins")

        if not date_str or not duration_str:
            return Response(
                {"error": _("date and duration_mins are required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            duration = int(duration_str)
        except ValueError:
            return Response(
                {"error": _("Invalid date or duration format")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if duration < 5 or duration > 480:
            return Response(
                {"error": _("Duration must be between 5 and 480 minutes")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get user's buffer preference from calendar_preferences
        buffer_mins = _get_user_buffer_minutes(request.user)

        # Get existing events for the day
        day_start = datetime.combine(target_date, datetime.min.time()).replace(
            tzinfo=dt_timezone.utc
        )
        day_end = day_start + timedelta(days=1)

        events = CalendarEvent.objects.filter(
            user=request.user,
            status="scheduled",
            start_time__lt=day_end,
            end_time__gt=day_start,
        ).order_by("start_time")

        # Get ALL time blocks for this day of week (not just blocked)
        day_of_week = target_date.weekday()
        all_time_blocks = TimeBlock.objects.filter(
            user=request.user,
            day_of_week=day_of_week,
            is_active=True,
        )
        blocked_times = all_time_blocks.filter(block_type="blocked")
        work_blocks = all_time_blocks.filter(block_type="work")

        # Build list of busy intervals
        busy = []
        for event in events:
            busy.append((event.start_time, event.end_time))
        for block in blocked_times:
            block_start = datetime.combine(target_date, block.start_time).replace(
                tzinfo=dt_timezone.utc
            )
            block_end = datetime.combine(target_date, block.end_time).replace(
                tzinfo=dt_timezone.utc
            )
            busy.append((block_start, block_end))

        # Sort busy intervals and merge overlaps
        busy.sort(key=lambda x: x[0])
        merged_busy = []
        for start, end in busy:
            if merged_busy and start <= merged_busy[-1][1]:
                merged_busy[-1] = (merged_busy[-1][0], max(merged_busy[-1][1], end))
            else:
                merged_busy.append((start, end))
        busy = merged_busy

        # Build work block intervals for quality scoring
        work_intervals = []
        for wb in work_blocks:
            wb_start = datetime.combine(target_date, wb.start_time).replace(
                tzinfo=dt_timezone.utc
            )
            wb_end = datetime.combine(target_date, wb.end_time).replace(
                tzinfo=dt_timezone.utc
            )
            work_intervals.append((wb_start, wb_end))

        # Define peak productivity hours (9-12 AM and 2-5 PM)
        peak_hours = [
            (day_start + timedelta(hours=9), day_start + timedelta(hours=12)),
            (day_start + timedelta(hours=14), day_start + timedelta(hours=17)),
        ]

        # Working window: 6 AM to 11 PM (matches HOURS 6-23 in frontend)
        work_start = day_start + timedelta(hours=6)
        work_end = day_start + timedelta(hours=23)
        needed = timedelta(minutes=duration)
        buffer = timedelta(minutes=buffer_mins)

        def compute_quality_score(slot_start, slot_end):
            """Compute a quality score (0.0-1.0) for a free slot."""
            score = 0.5  # Base score

            # Factor 1: Alignment with work blocks (+0.2 max)
            slot_mid = slot_start + (slot_end - slot_start) / 2
            in_work_block = any(
                wb_start <= slot_mid <= wb_end for wb_start, wb_end in work_intervals
            )
            if in_work_block:
                score += 0.2

            # Factor 2: Peak hours alignment (+0.2 max)
            in_peak = any(
                pk_start <= slot_mid <= pk_end for pk_start, pk_end in peak_hours
            )
            if in_peak:
                score += 0.2

            # Factor 3: Distance from other events (+0.1 max)
            min_dist_mins = float("inf")
            for ev_start, ev_end in busy:
                dist_before = (slot_start - ev_end).total_seconds() / 60
                dist_after = (ev_start - slot_end).total_seconds() / 60
                if dist_before > 0:
                    min_dist_mins = min(min_dist_mins, dist_before)
                if dist_after > 0:
                    min_dist_mins = min(min_dist_mins, dist_after)
            if min_dist_mins == float("inf"):
                score += 0.1
            elif min_dist_mins >= 30:
                score += 0.08
            elif min_dist_mins >= 15:
                score += 0.04

            return round(min(score, 1.0), 2)

        # ── Find ALL free slots (entire day) ──
        free_slots = []
        total_free_mins = 0
        current = work_start

        for busy_start, busy_end in busy:
            if busy_end <= work_start:
                continue
            if busy_start >= work_end:
                break
            effective_busy_start = max(busy_start, work_start)
            if current < effective_busy_start:
                gap_start = current
                gap_end = effective_busy_start
                gap_mins = int((gap_end - gap_start).total_seconds() / 60)
                if gap_mins >= 5:
                    free_slots.append(
                        {
                            "start_time": gap_start.isoformat(),
                            "end_time": gap_end.isoformat(),
                            "duration_mins": gap_mins,
                            "quality_score": compute_quality_score(gap_start, gap_end),
                        }
                    )
                    total_free_mins += gap_mins
            current = max(current, min(busy_end, work_end))

        # Free slot after the last busy interval
        if current < work_end:
            gap_mins = int((work_end - current).total_seconds() / 60)
            if gap_mins >= 5:
                free_slots.append(
                    {
                        "start_time": current.isoformat(),
                        "end_time": work_end.isoformat(),
                        "duration_mins": gap_mins,
                        "quality_score": compute_quality_score(current, work_end),
                    }
                )
                total_free_mins += gap_mins

        # ── Find best-match slots (fit requested duration with buffer) ──
        slots = []
        current = work_start

        for busy_start, busy_end in busy:
            if busy_start < work_start:
                current = max(current, busy_end + buffer)
                continue
            if current + needed <= busy_start - buffer:
                slot_start = current
                slot_end = current + needed
                slots.append(
                    {
                        "start": slot_start.isoformat(),
                        "end": slot_end.isoformat(),
                        "quality_score": compute_quality_score(slot_start, slot_end),
                    }
                )
            current = max(current, busy_end + buffer)

        # Check slot after last busy interval
        if current + needed <= work_end:
            slot_start = current
            slot_end = current + needed
            slots.append(
                {
                    "start": slot_start.isoformat(),
                    "end": slot_end.isoformat(),
                    "quality_score": compute_quality_score(slot_start, slot_end),
                }
            )

        # Sort best-match slots by quality score descending
        slots.sort(key=lambda s: s["quality_score"], reverse=True)

        return Response(
            {
                "date": date_str,
                "duration_mins": duration,
                "buffer_mins": buffer_mins,
                "slots": slots[:10],
                "free_slots": free_slots,
                "total_free_mins": total_free_mins,
            }
        )

    # ── Overdue tasks ────────────────────────────────────────────────
    @extend_schema(
        summary="Get overdue tasks",
        description="Returns tasks where scheduled_date < today and status != completed.",
        tags=["Calendar"],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"])
    def overdue(self, request):
        """Get all overdue (past-due, incomplete) tasks for the current user."""
        today = timezone.now().date()

        overdue_tasks = (
            Task.objects.filter(
                goal__dream__user=request.user,
                scheduled_date__date__lt=today,
            )
            .exclude(
                status="completed",
            )
            .exclude(
                status="skipped",
            )
            .select_related("goal__dream")
            .order_by("scheduled_date")
        )

        results = []
        for task in overdue_tasks:
            original_date = task.scheduled_date.date() if task.scheduled_date else None
            days_overdue = (today - original_date).days if original_date else 0
            results.append(
                {
                    "task_id": str(task.id),
                    "task_title": task.title,
                    "dream_id": str(task.goal.dream.id),
                    "dream_title": task.goal.dream.title,
                    "goal_id": str(task.goal.id),
                    "goal_title": task.goal.title,
                    "original_date": (
                        original_date.isoformat() if original_date else None
                    ),
                    "days_overdue": days_overdue,
                    "status": task.status,
                    "duration_mins": task.duration_mins,
                }
            )

        return Response(
            {
                "count": len(results),
                "tasks": results,
            }
        )

    # ── Rescue overdue tasks ─────────────────────────────────────────
    @extend_schema(
        summary="Rescue overdue tasks",
        description=(
            "Bulk-reschedule overdue tasks using a chosen strategy. "
            "Strategies: 'today' (all to today), 'spread' (across next 7 days), "
            "'smart' (priority-aware spread with weekday preference)."
        ),
        tags=["Calendar"],
        request=inline_serializer(
            name="RescueRequest",
            fields={
                "task_ids": drf_serializers.ListField(
                    child=drf_serializers.UUIDField(),
                    help_text="List of overdue task IDs to rescue.",
                ),
                "strategy": drf_serializers.ChoiceField(
                    choices=["today", "spread", "smart"],
                    help_text="Rescue strategy: today, spread, or smart.",
                ),
            },
        ),
        responses={200: dict},
    )
    @action(detail=False, methods=["post"])
    def rescue(self, request):
        """Bulk-reschedule overdue tasks with a chosen strategy."""
        task_ids = request.data.get("task_ids", [])
        strategy = request.data.get("strategy", "today")

        if not task_ids:
            return Response(
                {"error": _("task_ids is required and must be a non-empty list")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if strategy not in ("today", "spread", "smart"):
            return Response(
                {"error": _("strategy must be one of: today, spread, smart")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tasks = (
            Task.objects.filter(
                id__in=task_ids,
                goal__dream__user=request.user,
            )
            .exclude(
                status="completed",
            )
            .select_related("goal__dream")
            .order_by("scheduled_date")
        )

        if not tasks.exists():
            return Response(
                {"error": _("No matching overdue tasks found")},
                status=status.HTTP_404_NOT_FOUND,
            )

        today = timezone.now()
        today_date = today.date()
        schedule = []

        if strategy == "today":
            # Reschedule all tasks to today, preserving original time
            for task in tasks:
                new_date = datetime.combine(
                    today_date,
                    task.scheduled_date.time() if task.scheduled_date else today.time(),
                ).replace(tzinfo=dt_timezone.utc)
                task.scheduled_date = new_date
                task.save(update_fields=["scheduled_date"])
                schedule.append(
                    {
                        "task_id": str(task.id),
                        "task_title": task.title,
                        "new_date": new_date.isoformat(),
                        "dream_title": task.goal.dream.title,
                    }
                )

        elif strategy == "spread":
            # Spread tasks evenly across the next 7 days
            task_list = list(tasks)
            count = len(task_list)
            for i, task in enumerate(task_list):
                day_offset = (i * 7) // count if count > 0 else 0
                target_date = today_date + timedelta(days=day_offset)
                new_date = datetime.combine(
                    target_date,
                    task.scheduled_date.time() if task.scheduled_date else today.time(),
                ).replace(tzinfo=dt_timezone.utc)
                task.scheduled_date = new_date
                task.save(update_fields=["scheduled_date"])
                schedule.append(
                    {
                        "task_id": str(task.id),
                        "task_title": task.title,
                        "new_date": new_date.isoformat(),
                        "dream_title": task.goal.dream.title,
                    }
                )

        elif strategy == "smart":
            # Smart: priority-aware spread with weekday preference
            # Group by dream priority, spread high-priority first, prefer weekdays
            task_list = list(tasks)
            # Sort by dream priority (ascending = higher priority first), then by original date
            task_list.sort(
                key=lambda t: (t.goal.dream.priority, t.scheduled_date or today)
            )

            count = len(task_list)
            # Spread across next 14 days, preferring weekdays
            available_days = []
            for offset in range(14):
                candidate = today_date + timedelta(days=offset)
                # Weekdays first (0=Mon ... 4=Fri)
                available_days.append((candidate, candidate.weekday() < 5))

            # Sort: weekdays first, then weekends
            weekdays = [d for d, is_wd in available_days if is_wd]
            weekends = [d for d, is_wd in available_days if not is_wd]
            ordered_days = weekdays + weekends

            # Distribute tasks across ordered days, max ~3 per day
            max_per_day = (
                max(1, (count // len(ordered_days)) + 1) if ordered_days else count
            )
            max_per_day = min(max_per_day, 3)
            day_index = 0
            day_count = 0

            for task in task_list:
                if day_index >= len(ordered_days):
                    day_index = 0  # wrap around
                target_date = ordered_days[day_index]
                new_date = datetime.combine(
                    target_date,
                    task.scheduled_date.time() if task.scheduled_date else today.time(),
                ).replace(tzinfo=dt_timezone.utc)
                task.scheduled_date = new_date
                task.save(update_fields=["scheduled_date"])
                schedule.append(
                    {
                        "task_id": str(task.id),
                        "task_title": task.title,
                        "new_date": new_date.isoformat(),
                        "dream_title": task.goal.dream.title,
                    }
                )
                day_count += 1
                if day_count >= max_per_day:
                    day_count = 0
                    day_index += 1

        return Response(
            {
                "strategy": strategy,
                "rescued_count": len(schedule),
                "schedule": schedule,
            }
        )

    @extend_schema(
        summary="Batch schedule tasks",
        description="Schedule multiple tasks at once by creating calendar events for each.",
        tags=["Calendar"],
        request=BatchScheduleSerializer,
        responses={
            201: OpenApiResponse(
                description="Calendar events created for batch-scheduled tasks"
            ),
            400: OpenApiResponse(description="Invalid request"),
        },
    )
    @action(detail=False, methods=["post"], url_path="batch-schedule")
    def batch_schedule(self, request):
        """Batch-create calendar events for multiple tasks with specified dates and times."""
        serializer = BatchScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tasks_data = serializer.validated_data["tasks"]
        create_events = serializer.validated_data.get("create_events", True)

        created_events = []
        errors = []

        for item in tasks_data:
            task_id = item["task_id"]
            date_val = item["date"]
            time_str = item["time"]

            try:
                task = Task.objects.get(
                    id=task_id,
                    goal__dream__user=request.user,
                )
            except Task.DoesNotExist:
                errors.append(
                    {
                        "task_id": str(task_id),
                        "error": _("Task not found."),
                    }
                )
                continue

            duration = task.duration_mins or 30
            start_dt = datetime.combine(
                date_val,
                datetime.strptime(time_str, "%H:%M").time(),
            ).replace(tzinfo=dt_timezone.utc)
            end_dt = start_dt + timedelta(minutes=duration)

            if create_events:
                event = CalendarEvent.objects.create(
                    user=request.user,
                    task=task,
                    title=task.title,
                    description=task.description or "",
                    start_time=start_dt,
                    end_time=end_dt,
                    status="scheduled",
                )
                created_events.append(CalendarEventSerializer(event).data)

            # Update task scheduled_date and scheduled_time
            task.scheduled_date = start_dt
            task.scheduled_time = time_str
            task.save(update_fields=["scheduled_date", "scheduled_time"])

        return Response(
            {
                "created": created_events,
                "errors": errors,
                "count": len(created_events),
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Export calendar events",
        description=(
            "Export calendar events for a date range in CSV, iCal (.ics), or JSON format. "
            "Query params: start_date (required), end_date (required), format (csv|ical|json, default json)."
        ),
        tags=["Calendar"],
        parameters=[
            OpenApiParameter(
                name="start_date",
                description="Start date (YYYY-MM-DD)",
                required=True,
                type=str,
            ),
            OpenApiParameter(
                name="end_date",
                description="End date (YYYY-MM-DD)",
                required=True,
                type=str,
            ),
            OpenApiParameter(
                name="format",
                description="Export format: csv, ical, or json (default json)",
                required=False,
                type=str,
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Exported calendar data in the requested format"
            ),
            400: OpenApiResponse(description="Invalid parameters"),
        },
    )
    @action(detail=False, methods=["get"], url_path="export")
    def export_events(self, request):
        """Export calendar events for a date range as CSV, iCal, or JSON."""
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        export_format = request.query_params.get("format", "json").lower()

        if not start_date_str or not end_date_str:
            return Response(
                {"error": _("start_date and end_date are required (YYYY-MM-DD)")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if export_format not in ("csv", "ical", "json"):
            return Response(
                {"error": _("format must be one of: csv, ical, json")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").replace(
                hour=0, minute=0, second=0, tzinfo=dt_timezone.utc
            )
            end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=dt_timezone.utc
            )
        except ValueError:
            return Response(
                {"error": _("Invalid date format. Use YYYY-MM-DD.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch events in range
        events = CalendarEvent.objects.filter(
            user=request.user,
            start_time__lte=end_dt,
            end_time__gte=start_dt,
        ).order_by("start_time")

        # Also expand recurring events into the range
        recurring_parents = CalendarEvent.objects.filter(
            user=request.user,
            is_recurring=True,
            start_time__lte=end_dt,
        )
        virtual_events = []
        for parent in recurring_parents:
            occurrences = expand_recurring_events(parent, start_dt, end_dt)
            for occ in occurrences:
                virtual_events.append(occ)

        # Combine real + virtual, deduplicate by checking existing event ids
        real_ids = set(str(e.id) for e in events)
        all_events = list(events)
        for v in virtual_events:
            if str(v.id) not in real_ids:
                all_events.append(v)
                real_ids.add(str(v.id))

        # Sort by start_time
        all_events.sort(key=lambda e: e.start_time)

        if export_format == "csv":
            return self._export_csv(all_events, start_date_str, end_date_str)
        elif export_format == "ical":
            return self._export_ical(all_events, request.user)
        else:
            return self._export_json(all_events)

    def _export_csv(self, events, start_date, end_date):
        """Return events as a downloadable CSV file."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "title",
                "start_time",
                "end_time",
                "location",
                "status",
                "category",
                "description",
            ]
        )

        for event in events:
            writer.writerow(
                [
                    event.title or "",
                    (
                        event.start_time.strftime("%Y-%m-%d %H:%M")
                        if event.start_time
                        else ""
                    ),
                    event.end_time.strftime("%Y-%m-%d %H:%M") if event.end_time else "",
                    event.location or "",
                    event.status or "",
                    getattr(event, "category", "custom") or "custom",
                    event.description or "",
                ]
            )

        response = HttpResponse(
            output.getvalue(), content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="stepora-calendar-{start_date}-to-{end_date}.csv"'
        )
        return response

    def _export_ical(self, events, user):
        """Return events as a downloadable .ics (iCal) file."""
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Stepora//Calendar Export//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:Stepora - {_ical_escape(user.display_name or user.email)}",
        ]

        for event in events:
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{event.id}@stepora",
                    f'DTSTART:{event.start_time.strftime("%Y%m%dT%H%M%SZ")}',
                    f'DTEND:{event.end_time.strftime("%Y%m%dT%H%M%SZ")}',
                    f"SUMMARY:{_ical_escape(event.title)}",
                    f"DESCRIPTION:{_ical_escape(event.description)}",
                    f'STATUS:{event.status.upper() if event.status else "CONFIRMED"}',
                ]
            )
            if event.location:
                lines.append(f"LOCATION:{_ical_escape(event.location)}")
            category = getattr(event, "category", "")
            if category:
                lines.append(f"CATEGORIES:{_ical_escape(category)}")
            lines.append("END:VEVENT")

        lines.append("END:VCALENDAR")

        ical_content = "\r\n".join(lines)
        response = HttpResponse(
            ical_content, content_type="text/calendar; charset=utf-8"
        )
        response["Content-Disposition"] = 'attachment; filename="stepora-calendar.ics"'
        return response

    def _export_json(self, events):
        """Return events as JSON (same format as the regular view)."""
        serializer = CalendarEventSerializer(events, many=True)
        return Response(serializer.data)


class FocusModeActiveView(APIView):
    """Check if the user is currently in a focus block."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Check focus mode status",
        description="Returns whether the user is currently in a focus block.",
        tags=["Calendar", "Focus"],
        responses={
            200: inline_serializer(
                name="FocusModeActiveResponse",
                fields={
                    "focus_active": drf_serializers.BooleanField(),
                    "source": drf_serializers.CharField(allow_null=True),
                    "block_id": drf_serializers.UUIDField(allow_null=True),
                    "session_id": drf_serializers.UUIDField(allow_null=True),
                    "start_time": drf_serializers.TimeField(allow_null=True),
                    "end_time": drf_serializers.TimeField(allow_null=True),
                    "remaining_minutes": drf_serializers.IntegerField(allow_null=True),
                },
            )
        },
    )
    def get(self, request):
        now = timezone.now()
        current_time = now.time()
        current_dow = now.weekday()
        fb = TimeBlock.objects.filter(
            user=request.user,
            is_active=True,
            focus_block=True,
            day_of_week=current_dow,
            start_time__lte=current_time,
            end_time__gt=current_time,
        )
        if fb.exists():
            block = fb.first()
            end_dt = datetime.combine(now.date(), block.end_time).replace(
                tzinfo=dt_timezone.utc
            )
            remaining = max(0, int((end_dt - now).total_seconds() / 60))
            return Response(
                {
                    "focus_active": True,
                    "source": "time_block",
                    "block_id": block.id,
                    "session_id": None,
                    "start_time": str(block.start_time),
                    "end_time": str(block.end_time),
                    "remaining_minutes": remaining,
                }
            )
        active_session = (
            FocusSession.objects.filter(
                user=request.user,
                ended_at__isnull=True,
                session_type="work",
            )
            .order_by("-started_at")
            .first()
        )
        if active_session:
            session_end = active_session.started_at + timedelta(
                minutes=active_session.duration_minutes
            )
            if session_end > now:
                remaining = max(0, int((session_end - now).total_seconds() / 60))
                return Response(
                    {
                        "focus_active": True,
                        "source": "focus_session",
                        "block_id": None,
                        "session_id": active_session.id,
                        "start_time": str(active_session.started_at.time()),
                        "end_time": str(session_end.time()),
                        "remaining_minutes": remaining,
                    }
                )
        return Response(
            {
                "focus_active": False,
                "source": None,
                "block_id": None,
                "session_id": None,
                "start_time": None,
                "end_time": None,
                "remaining_minutes": None,
            }
        )


class FocusBlockEventsView(APIView):
    """Return upcoming focus blocks for the current week."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Upcoming focus blocks",
        description="Get all focus time blocks for the current week.",
        tags=["Calendar", "Focus"],
        responses={
            200: inline_serializer(
                name="FocusBlockEventsResponse",
                fields={
                    "focus_blocks": drf_serializers.ListField(
                        child=drf_serializers.DictField()
                    )
                },
            )
        },
    )
    def get(self, request):
        now = timezone.now()
        current_dow = now.weekday()
        blocks = TimeBlock.objects.filter(
            user=request.user,
            is_active=True,
            focus_block=True,
        ).order_by("day_of_week", "start_time")
        day_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        result = []
        for block in blocks:
            days_ahead = block.day_of_week - current_dow
            if days_ahead < 0:
                days_ahead += 7
            block_date = (now + timedelta(days=days_ahead)).date()
            result.append(
                {
                    "id": block.id,
                    "block_type": block.block_type,
                    "day_of_week": block.day_of_week,
                    "day_name": day_names[block.day_of_week],
                    "date": str(block_date),
                    "start_time": str(block.start_time),
                    "end_time": str(block.end_time),
                    "focus_block": True,
                }
            )
        return Response({"focus_blocks": result})


class GoogleCalendarStatusView(APIView):
    """Check Google Calendar connection status for the current user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Google Calendar connection status",
        tags=["Calendar Integration"],
        request=None,
        responses={
            200: inline_serializer(
                name="GoogleCalendarStatusResponse",
                fields={
                    "connected": drf_serializers.BooleanField(),
                    "sync_enabled": drf_serializers.BooleanField(),
                    "last_sync_at": drf_serializers.DateTimeField(allow_null=True),
                    "events_pending": drf_serializers.IntegerField(),
                },
            ),
        },
    )
    def get(self, request):
        try:
            integration = GoogleCalendarIntegration.objects.get(
                user=request.user, sync_enabled=True
            )
            events_pending = CalendarEvent.objects.filter(
                user=request.user,
                sync_status="pending",
            ).count()
            return Response(
                {
                    "connected": True,
                    "sync_enabled": integration.sync_enabled,
                    "last_sync_at": integration.last_sync_at,
                    "events_pending": events_pending,
                }
            )
        except GoogleCalendarIntegration.DoesNotExist:
            return Response(
                {
                    "connected": False,
                    "sync_enabled": False,
                    "last_sync_at": None,
                    "events_pending": 0,
                }
            )


class GoogleCalendarAuthView(APIView):
    """Initiate Google Calendar OAuth2 flow."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Google OAuth URL",
        tags=["Calendar Integration"],
        request=None,
        responses={
            200: inline_serializer(
                name="GoogleCalendarAuthResponse",
                fields={"auth_url": drf_serializers.URLField()},
            ),
            501: OpenApiResponse(
                description="Google Calendar integration not configured"
            ),
        },
    )
    def get(self, request):
        from django.conf import settings

        from integrations.google_calendar import GoogleCalendarService

        # Allow frontend to override redirect_uri for native OAuth flow
        redirect_uri = request.query_params.get(
            "redirect_uri",
            getattr(settings, "GOOGLE_CALENDAR_REDIRECT_URI", ""),
        )
        if not redirect_uri:
            return Response(
                {"error": _("Google Calendar integration is not configured.")},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        service = GoogleCalendarService()
        auth_url = service.get_auth_url(redirect_uri)
        return Response({"auth_url": auth_url})


class GoogleCalendarCallbackView(APIView):
    """Handle Google Calendar OAuth2 callback."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Google OAuth callback",
        tags=["Calendar Integration"],
        request=inline_serializer(
            name="GoogleCalendarCallbackRequest",
            fields={"code": drf_serializers.CharField()},
        ),
        responses={
            200: inline_serializer(
                name="GoogleCalendarCallbackResponse",
                fields={
                    "status": drf_serializers.CharField(),
                    "calendar_id": drf_serializers.CharField(),
                    "ical_feed_token": drf_serializers.CharField(),
                },
            ),
            400: OpenApiResponse(description="Invalid or missing authorization code"),
        },
    )
    def post(self, request):
        from django.conf import settings

        from integrations.google_calendar import GoogleCalendarService

        code = request.data.get("code")
        if not code:
            return Response(
                {"error": _("Authorization code is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        redirect_uri = request.data.get(
            "redirect_uri",
            getattr(settings, "GOOGLE_CALENDAR_REDIRECT_URI", ""),
        )
        service = GoogleCalendarService()

        try:
            tokens = service.exchange_code(code, redirect_uri)
        except Exception as e:
            return Response(
                {"error": _("Token exchange failed: %(error)s") % {"error": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        integration, _created = GoogleCalendarIntegration.objects.update_or_create(
            user=request.user,
            defaults={
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "token_expiry": tokens["token_expiry"],
                "sync_enabled": True,
            },
        )

        return Response(
            {
                "status": "connected",
                "calendar_id": integration.calendar_id,
                "ical_feed_token": integration.ical_feed_token,
            }
        )


class GoogleCalendarSyncView(APIView):
    """Trigger a manual Google Calendar sync."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Trigger Google Calendar sync",
        tags=["Calendar Integration"],
        request=None,
        responses={
            200: inline_serializer(
                name="GoogleCalendarSyncResponse",
                fields={
                    "status": drf_serializers.CharField(),
                    "last_sync": drf_serializers.DateTimeField(),
                },
            ),
            404: OpenApiResponse(description="Google Calendar not connected"),
        },
    )
    def post(self, request):
        from .tasks import sync_google_calendar

        try:
            integration = GoogleCalendarIntegration.objects.get(
                user=request.user, sync_enabled=True
            )
        except GoogleCalendarIntegration.DoesNotExist:
            return Response(
                {"error": _("Google Calendar not connected.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        sync_google_calendar.delay(str(integration.id))
        return Response(
            {"status": "sync_queued", "last_sync": integration.last_sync_at}
        )


class GoogleCalendarDisconnectView(APIView):
    """Disconnect Google Calendar integration."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Disconnect Google Calendar",
        tags=["Calendar Integration"],
        request=None,
        responses={
            200: inline_serializer(
                name="GoogleCalendarDisconnectResponse",
                fields={"status": drf_serializers.CharField()},
            ),
            404: OpenApiResponse(description="No integration found"),
        },
    )
    def post(self, request):
        deleted, _ = GoogleCalendarIntegration.objects.filter(
            user=request.user
        ).delete()
        if deleted:
            return Response({"status": "disconnected"})
        return Response(
            {"error": _("No integration found.")}, status=status.HTTP_404_NOT_FOUND
        )


class GoogleCalendarSyncSettingsView(APIView):
    """Get or update selective sync settings for Google Calendar."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get sync settings",
        description="Return current sync settings and user's dreams list.",
        tags=["Calendar Integration"],
        request=None,
        responses={200: dict},
    )
    def get(self, request):
        try:
            integration = GoogleCalendarIntegration.objects.get(
                user=request.user,
                sync_enabled=True,
            )
        except GoogleCalendarIntegration.DoesNotExist:
            return Response(
                {"connected": False},
                status=status.HTTP_200_OK,
            )

        dreams = (
            Dream.objects.filter(
                user=request.user,
                status="active",
            )
            .values("id", "title", "color")
            .order_by("title")
        )

        return Response(
            {
                "connected": True,
                "synced_dream_ids": integration.synced_dream_ids or [],
                "sync_direction": integration.sync_direction,
                "sync_tasks": integration.sync_tasks,
                "sync_events": integration.sync_events,
                "last_sync_at": integration.last_sync_at,
                "dreams": [
                    {
                        "id": str(d["id"]),
                        "title": d["title"],
                        "color": d["color"] or "#8B5CF6",
                    }
                    for d in dreams
                ],
            }
        )

    @extend_schema(
        summary="Update sync settings",
        description="Update selective sync settings for Google Calendar.",
        tags=["Calendar Integration"],
        request=inline_serializer(
            name="GoogleCalendarSyncSettingsRequest",
            fields={
                "synced_dream_ids": drf_serializers.ListField(
                    child=drf_serializers.CharField(),
                    required=False,
                ),
                "sync_direction": drf_serializers.ChoiceField(
                    choices=["both", "push_only", "pull_only"],
                    required=False,
                ),
                "sync_tasks": drf_serializers.BooleanField(required=False),
                "sync_events": drf_serializers.BooleanField(required=False),
            },
        ),
        responses={
            200: dict,
            404: OpenApiResponse(description="Google Calendar not connected"),
        },
    )
    def post(self, request):
        try:
            integration = GoogleCalendarIntegration.objects.get(
                user=request.user,
                sync_enabled=True,
            )
        except GoogleCalendarIntegration.DoesNotExist:
            return Response(
                {"error": _("Google Calendar not connected.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        update_fields = ["updated_at"]

        if "synced_dream_ids" in request.data:
            dream_ids = request.data["synced_dream_ids"]
            if not isinstance(dream_ids, list):
                return Response(
                    {"error": _("synced_dream_ids must be a list.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            integration.synced_dream_ids = dream_ids
            update_fields.append("synced_dream_ids")

        if "sync_direction" in request.data:
            direction = request.data["sync_direction"]
            if direction not in ("both", "push_only", "pull_only"):
                return Response(
                    {"error": _("Invalid sync_direction.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            integration.sync_direction = direction
            update_fields.append("sync_direction")

        if "sync_tasks" in request.data:
            integration.sync_tasks = bool(request.data["sync_tasks"])
            update_fields.append("sync_tasks")

        if "sync_events" in request.data:
            integration.sync_events = bool(request.data["sync_events"])
            update_fields.append("sync_events")

        integration.save(update_fields=update_fields)

        return Response(
            {
                "status": "updated",
                "synced_dream_ids": integration.synced_dream_ids,
                "sync_direction": integration.sync_direction,
                "sync_tasks": integration.sync_tasks,
                "sync_events": integration.sync_events,
            }
        )


class ICalFeedView(APIView):
    """
    Public iCal feed endpoint (authenticated by secret token, not user session).

    Subscribe to this URL in any calendar app (Apple Calendar, Outlook, etc.)
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="iCal feed export",
        tags=["Calendar Integration"],
        request=None,
        responses={
            200: OpenApiResponse(description="iCal feed content"),
            404: OpenApiResponse(description="Feed not found"),
        },
    )
    def get(self, request, feed_token):
        try:
            integration = GoogleCalendarIntegration.objects.select_related("user").get(
                ical_feed_token=feed_token
            )
        except GoogleCalendarIntegration.DoesNotExist:
            return HttpResponse(
                _("Feed not found."), status=404, content_type="text/plain"
            )

        user = integration.user
        now = timezone.now()
        events = CalendarEvent.objects.filter(
            user=user,
            status="scheduled",
            start_time__gte=now - timedelta(days=30),
            start_time__lte=now + timedelta(days=90),
        ).order_by("start_time")

        # Build iCalendar format
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Stepora//Calendar//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:Stepora - {_ical_escape(user.display_name or user.email)}",
        ]

        for event in events:
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{event.id}@stepora",
                    f'DTSTART:{event.start_time.strftime("%Y%m%dT%H%M%SZ")}',
                    f'DTEND:{event.end_time.strftime("%Y%m%dT%H%M%SZ")}',
                    f"SUMMARY:{_ical_escape(event.title)}",
                    f"DESCRIPTION:{_ical_escape(event.description)}",
                ]
            )
            if event.location:
                lines.append(f"LOCATION:{_ical_escape(event.location)}")
            lines.append("END:VEVENT")

        lines.append("END:VCALENDAR")

        ical_content = "\r\n".join(lines)
        response = HttpResponse(
            ical_content, content_type="text/calendar; charset=utf-8"
        )
        response["Content-Disposition"] = 'attachment; filename="stepora.ics"'
        return response


class ICalImportView(APIView):
    """Import events from an uploaded .ics (iCal) file."""

    permission_classes = [IsAuthenticated]
    MAX_EVENTS = 500

    _FREQ_MAP = {
        "DAILY": "daily",
        "WEEKLY": "weekly",
        "MONTHLY": "monthly",
        "YEARLY": "yearly",
    }
    _ICAL_WEEKDAY_MAP = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}

    @extend_schema(
        summary="Import iCal (.ics) file",
        tags=["Calendar Integration"],
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
                "required": ["file"],
            }
        },
        responses={
            200: OpenApiResponse(
                description="Import results",
                response=inline_serializer(
                    name="ICalImportResponse",
                    fields={
                        "imported": drf_serializers.IntegerField(),
                        "skipped": drf_serializers.IntegerField(),
                        "errors": drf_serializers.ListField(
                            child=drf_serializers.CharField()
                        ),
                    },
                ),
            ),
            400: OpenApiResponse(description="Invalid file or too many events"),
        },
    )
    def post(self, request):
        import icalendar

        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response(
                {"error": _("No file uploaded.")}, status=status.HTTP_400_BAD_REQUEST
            )
        name = (uploaded.name or "").lower()
        if not name.endswith(".ics"):
            return Response(
                {"error": _("Only .ics files are accepted.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            raw = uploaded.read()
            cal = icalendar.Calendar.from_ical(raw)
        except Exception:
            return Response(
                {"error": _("Failed to parse .ics file.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        vevents = [c for c in cal.walk() if c.name == "VEVENT"]
        if len(vevents) > self.MAX_EVENTS:
            return Response(
                {
                    "error": _(
                        "Too many events (%(count)d). Maximum is %(max)d per import."
                    )
                    % {"count": len(vevents), "max": self.MAX_EVENTS}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        imported = 0
        skipped = 0
        errors = []
        for idx, vevent in enumerate(vevents):
            try:
                event = self._create_event(request.user, vevent, idx)
                if event:
                    imported += 1
                else:
                    skipped += 1
            except Exception as exc:
                skipped += 1
                summary = str(vevent.get("SUMMARY", f"Event #{idx + 1}"))
                errors.append(f"{summary}: {exc}")
                if len(errors) >= 50:
                    errors.append("(additional errors truncated)")
                    break
        return Response({"imported": imported, "skipped": skipped, "errors": errors})

    def _create_event(self, user, vevent, idx):
        """Parse a single VEVENT and create a CalendarEvent."""
        summary = str(vevent.get("SUMMARY", "")).strip()
        if not summary:
            summary = f"Imported Event #{idx + 1}"
        description = str(vevent.get("DESCRIPTION", "") or "")
        location = str(vevent.get("LOCATION", "") or "")
        dtstart = vevent.get("DTSTART")
        dtend = vevent.get("DTEND")
        if not dtstart:
            return None
        start_dt = dtstart.dt
        all_day = False
        if isinstance(start_dt, datetime):
            start_time = self._ensure_utc(start_dt)
        else:
            all_day = True
            start_time = datetime(
                start_dt.year,
                start_dt.month,
                start_dt.day,
                0,
                0,
                0,
                tzinfo=dt_timezone.utc,
            )
        if dtend:
            end_dt = dtend.dt
            if isinstance(end_dt, datetime):
                end_time = self._ensure_utc(end_dt)
            else:
                end_time = datetime(
                    end_dt.year,
                    end_dt.month,
                    end_dt.day,
                    23,
                    59,
                    59,
                    tzinfo=dt_timezone.utc,
                )
        elif all_day:
            end_time = start_time.replace(hour=23, minute=59, second=59)
        else:
            end_time = start_time + timedelta(hours=1)
        is_recurring = False
        recurrence_rule = None
        rrule = vevent.get("RRULE")
        if rrule:
            recurrence_rule = self._parse_rrule(rrule)
            if recurrence_rule:
                is_recurring = True
        return CalendarEvent.objects.create(
            user=user,
            title=summary[:255],
            description=description,
            start_time=start_time,
            end_time=end_time,
            all_day=all_day,
            location=location[:255],
            is_recurring=is_recurring,
            recurrence_rule=recurrence_rule,
            status="scheduled",
        )

    @staticmethod
    def _ensure_utc(dt_val):
        """Ensure a datetime is UTC-aware."""
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=dt_timezone.utc)
        return dt_val.astimezone(dt_timezone.utc)

    def _parse_rrule(self, rrule):
        """Convert an iCal RRULE to Stepora recurrence_rule dict."""
        freq_list = rrule.get("FREQ", [])
        if not freq_list:
            return None
        freq_str = str(freq_list[0]).upper()
        frequency = self._FREQ_MAP.get(freq_str)
        if not frequency:
            return None
        rule = {"frequency": frequency}
        interval = rrule.get("INTERVAL")
        if interval:
            rule["interval"] = int(interval[0])
        byday = rrule.get("BYDAY")
        if byday:
            days = []
            for d in byday:
                day_str = str(d)[-2:]
                if day_str in self._ICAL_WEEKDAY_MAP:
                    days.append(self._ICAL_WEEKDAY_MAP[day_str])
            if days:
                rule["days_of_week"] = sorted(set(days))
        bymonthday = rrule.get("BYMONTHDAY")
        if bymonthday:
            rule["day_of_month"] = int(bymonthday[0])
        count = rrule.get("COUNT")
        if count:
            rule["end_after_count"] = int(count[0])
        until = rrule.get("UNTIL")
        if until:
            until_dt = until[0]
            if isinstance(until_dt, datetime):
                rule["end_date"] = until_dt.isoformat()
            elif hasattr(until_dt, "isoformat"):
                rule["end_date"] = datetime(
                    until_dt.year,
                    until_dt.month,
                    until_dt.day,
                    23,
                    59,
                    59,
                    tzinfo=dt_timezone.utc,
                ).isoformat()
        return rule


class GoogleCalendarNativeRedirectView(APIView):
    """
    Intermediate redirect for native OAuth flow.

    Google OAuth redirects here with ?code=..., and this view redirects
    the user back to the native app via the custom URL scheme.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Native OAuth redirect",
        tags=["Calendar Integration"],
        responses={200: OpenApiResponse(description="HTML redirect page")},
    )
    def get(self, request):
        import html
        import json as json_mod

        code = request.query_params.get("code", "")
        error = request.query_params.get("error", "")

        if error:
            deep_link = (
                f"com.stepora.app://calendar/callback?error={html.escape(error)}"
            )
        elif code:
            deep_link = f"com.stepora.app://calendar/callback?code={html.escape(code)}"
        else:
            return HttpResponse(_("Missing authorization code."), status=400)

        # Use json.dumps for safe JS string embedding (prevents injection)
        deep_link_js = json_mod.dumps(deep_link)
        deep_link_html = html.escape(deep_link)
        page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Redirecting...</title></head>
<body>
<p>Redirecting to Stepora...</p>
<script>window.location.href = {deep_link_js};</script>
<noscript><a href="{deep_link_html}">Click here to return to the app</a></noscript>
</body></html>"""
        return HttpResponse(page, content_type="text/html")


class SmartScheduleView(APIView):
    """
    AI-powered smart task scheduling.

    Analyzes task priorities, due dates, existing calendar events,
    user activity patterns, and task durations to suggest optimal
    time slots for unscheduled tasks.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Smart schedule tasks",
        description=(
            "Analyze tasks and suggest optimal time slots based on priority, "
            "due dates, existing events, user activity patterns, and durations."
        ),
        tags=["Calendar"],
        request=SmartScheduleRequestSerializer,
        responses={
            200: OpenApiResponse(description="Smart schedule suggestions"),
            400: OpenApiResponse(description="Invalid request"),
        },
    )
    def post(self, request):
        serializer = SmartScheduleRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task_ids = serializer.validated_data["task_ids"]

        # Fetch requested tasks owned by the current user
        tasks = (
            Task.objects.filter(
                id__in=task_ids,
                goal__dream__user=request.user,
            )
            .select_related("goal__dream")
            .order_by("deadline_date", "expected_date", "-goal__dream__priority")
        )

        if not tasks.exists():
            return Response(
                {"error": _("No matching tasks found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Gather scheduling context ──────────────────────────────────

        now = timezone.now()
        schedule_start = now + timedelta(hours=1)  # Start scheduling from next hour
        schedule_horizon = now + timedelta(days=14)  # Look ahead 14 days

        # 1) Existing calendar events in the scheduling window
        existing_events = CalendarEvent.objects.filter(
            user=request.user,
            status="scheduled",
            start_time__lt=schedule_horizon,
            end_time__gt=schedule_start,
        ).order_by("start_time")

        # Build busy intervals per date
        busy_by_date = {}
        for event in existing_events:
            date_key = event.start_time.date()
            if date_key not in busy_by_date:
                busy_by_date[date_key] = []
            busy_by_date[date_key].append((event.start_time, event.end_time))

        # 2) Time blocks (blocked periods per day of week)
        blocked_times = TimeBlock.objects.filter(
            user=request.user,
            is_active=True,
            block_type="blocked",
        )
        blocked_by_dow = {}
        for block in blocked_times:
            if block.day_of_week not in blocked_by_dow:
                blocked_by_dow[block.day_of_week] = []
            blocked_by_dow[block.day_of_week].append((block.start_time, block.end_time))

        # 3) User activity patterns — find their most productive hours
        recent_activities = DailyActivity.objects.filter(
            user=request.user,
            date__gte=(now - timedelta(days=60)).date(),
        ).order_by("-date")[:60]

        # Analyze focus sessions for time-of-day patterns
        from apps.dreams.models import FocusSession

        recent_sessions = FocusSession.objects.filter(
            user=request.user,
            completed=True,
            started_at__gte=now - timedelta(days=60),
        ).order_by("-started_at")[:100]

        # Build productivity score per hour (0-23)
        hour_scores = [0.0] * 24
        hour_counts = [0] * 24
        for session in recent_sessions:
            h = session.started_at.hour
            # Weight by actual minutes focused
            hour_scores[h] += float(session.actual_minutes or session.duration_minutes)
            hour_counts[h] += 1

        # Normalize to 0-1 scale
        max_score = max(hour_scores) if max(hour_scores) > 0 else 1.0
        productivity_by_hour = [s / max_score for s in hour_scores]

        # If no data, use sensible defaults (morning peak, afternoon dip, evening OK)
        if max(hour_scores) == 0:
            productivity_by_hour = [
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,  # 0-5 AM
                0.3,
                0.5,
                0.8,
                0.95,
                0.9,
                0.85,  # 6-11 AM
                0.6,
                0.55,
                0.65,
                0.75,
                0.8,
                0.7,  # 12-5 PM
                0.5,
                0.4,
                0.3,
                0.2,
                0.1,
                0.0,  # 6-11 PM
            ]

        # 4) Load user energy profile for peak/low energy hour awareness
        energy_profile = request.user.energy_profile or {}
        peak_hours_ranges = energy_profile.get("peak_hours", [])
        low_energy_ranges = energy_profile.get("low_energy_hours", [])

        # Build a per-hour energy multiplier (0-23) from the profile
        energy_by_hour = [0.0] * 24  # 0 = neutral, positive = peak, negative = low
        for r in peak_hours_ranges:
            for h in range(r.get("start", 0), r.get("end", 0)):
                if 0 <= h < 24:
                    energy_by_hour[h] = 1.0  # peak
        for r in low_energy_ranges:
            for h in range(r.get("start", 0), r.get("end", 0)):
                if 0 <= h < 24:
                    energy_by_hour[h] = -1.0  # low energy

        has_energy_profile = bool(peak_hours_ranges or low_energy_ranges)

        # Determine user's average daily active minutes
        if recent_activities:
            avg_daily_mins = sum(a.minutes_active for a in recent_activities) / len(
                recent_activities
            )
        else:
            avg_daily_mins = 120  # Default 2 hours

        # ── Scheduling algorithm ───────────────────────────────────────

        # Sort tasks by priority: urgent/high-priority first
        def task_sort_key(task):
            # Lower = higher priority
            urgency = 0
            if task.deadline_date:
                days_until = (task.deadline_date - now.date()).days
                if days_until <= 1:
                    urgency = -100
                elif days_until <= 3:
                    urgency = -50
                elif days_until <= 7:
                    urgency = -20
            dream_priority = task.goal.dream.priority or 1
            return (urgency, -dream_priority, task.order)

        sorted_tasks = sorted(tasks, key=task_sort_key)

        suggestions = []
        # Track cumulative scheduled minutes per day to avoid overloading
        daily_scheduled_mins = {}

        for task in sorted_tasks:
            duration = task.duration_mins or 30  # Default 30 min
            dream_priority = task.goal.dream.priority or 1

            best_slot = None
            best_score = -1.0
            best_reason = ""

            # Scan days in the scheduling window
            current_date = schedule_start.date()
            while current_date <= schedule_horizon.date():
                dow = current_date.weekday()

                # Skip if we've already scheduled too much for this day
                day_mins = daily_scheduled_mins.get(current_date, 0)
                daily_capacity = max(
                    avg_daily_mins * 1.2, 60
                )  # Don't exceed ~120% of avg
                if day_mins + duration > daily_capacity:
                    current_date += timedelta(days=1)
                    continue

                # Build busy intervals for this date
                busy = list(busy_by_date.get(current_date, []))

                # Add blocked time blocks for this day of week
                for bt_start, bt_end in blocked_by_dow.get(dow, []):
                    block_start = datetime.combine(current_date, bt_start).replace(
                        tzinfo=dt_timezone.utc
                    )
                    block_end = datetime.combine(current_date, bt_end).replace(
                        tzinfo=dt_timezone.utc
                    )
                    busy.append((block_start, block_end))

                busy.sort(key=lambda x: x[0])

                # Find free slots between 7 AM and 9 PM
                day_start = datetime.combine(current_date, datetime.min.time()).replace(
                    tzinfo=dt_timezone.utc
                ) + timedelta(hours=7)
                day_end = datetime.combine(current_date, datetime.min.time()).replace(
                    tzinfo=dt_timezone.utc
                ) + timedelta(hours=21)

                # Don't schedule in the past
                if day_start < schedule_start:
                    day_start = schedule_start
                    # Round up to next 15-min boundary
                    mins = day_start.minute
                    if mins % 15 != 0:
                        day_start = day_start.replace(
                            minute=(mins // 15 + 1) * 15 % 60, second=0, microsecond=0
                        )
                        if (mins // 15 + 1) * 15 >= 60:
                            day_start += timedelta(hours=1)
                            day_start = day_start.replace(minute=0)

                needed = timedelta(minutes=duration)
                buffer = timedelta(minutes=_get_user_buffer_minutes(request.user))
                current_time = day_start

                for busy_start, busy_end in busy:
                    if busy_start < day_start:
                        current_time = max(current_time, busy_end + buffer)
                        continue
                    if current_time + needed <= busy_start - buffer:
                        # Found a free slot — score it
                        slot_hour = current_time.hour
                        score = _compute_slot_score(
                            current_time,
                            current_date,
                            slot_hour,
                            dream_priority,
                            task,
                            productivity_by_hour,
                            day_mins,
                            now,
                            energy_by_hour,
                            has_energy_profile,
                        )
                        if score > best_score:
                            best_score = score
                            best_slot = current_time
                            best_reason = _build_reason(
                                slot_hour,
                                productivity_by_hour,
                                dream_priority,
                                task,
                                current_date,
                                now,
                                energy_by_hour,
                                has_energy_profile,
                            )
                    current_time = max(current_time, busy_end + buffer)

                # Check slot after last busy interval
                if current_time + needed <= day_end:
                    slot_hour = current_time.hour
                    score = _compute_slot_score(
                        current_time,
                        current_date,
                        slot_hour,
                        dream_priority,
                        task,
                        productivity_by_hour,
                        day_mins,
                        now,
                        energy_by_hour,
                        has_energy_profile,
                    )
                    if score > best_score:
                        best_score = score
                        best_slot = current_time
                        best_reason = _build_reason(
                            slot_hour,
                            productivity_by_hour,
                            dream_priority,
                            task,
                            current_date,
                            now,
                            energy_by_hour,
                            has_energy_profile,
                        )

                # If we found a decent slot on this day, don't keep searching
                # unless the score is very low
                if best_score > 0.6:
                    break

                current_date += timedelta(days=1)

            if best_slot:
                # Record this slot as busy for future iterations
                slot_date = best_slot.date()
                slot_end = best_slot + timedelta(minutes=duration)
                if slot_date not in busy_by_date:
                    busy_by_date[slot_date] = []
                busy_by_date[slot_date].append((best_slot, slot_end))
                busy_by_date[slot_date].sort(key=lambda x: x[0])
                daily_scheduled_mins[slot_date] = (
                    daily_scheduled_mins.get(slot_date, 0) + duration
                )

                suggestions.append(
                    {
                        "task_id": str(task.id),
                        "task_title": task.title,
                        "suggested_date": best_slot.strftime("%Y-%m-%d"),
                        "suggested_time": best_slot.strftime("%H:%M"),
                        "duration_mins": duration,
                        "reason": best_reason,
                        "confidence": round(min(best_score, 1.0), 2),
                    }
                )
            else:
                suggestions.append(
                    {
                        "task_id": str(task.id),
                        "task_title": task.title,
                        "suggested_date": None,
                        "suggested_time": None,
                        "duration_mins": duration,
                        "reason": _(
                            "No available time slots found in the next 14 days."
                        ),
                        "confidence": 0.0,
                    }
                )

        return Response({"suggestions": suggestions})


class AcceptScheduleView(APIView):
    """
    Batch-create calendar events from accepted smart schedule suggestions.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Accept smart schedule",
        description="Batch-create calendar events from accepted schedule suggestions.",
        tags=["Calendar"],
        request=AcceptScheduleSerializer,
        responses={
            201: OpenApiResponse(description="Calendar events created"),
            400: OpenApiResponse(description="Invalid request"),
        },
    )
    def post(self, request):
        serializer = AcceptScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        accepted = serializer.validated_data["suggestions"]
        created_events = []
        errors = []

        for item in accepted:
            task_id = item["task_id"]
            date_str = item["suggested_date"]
            time_str = item["suggested_time"]

            try:
                task = Task.objects.get(
                    id=task_id,
                    goal__dream__user=request.user,
                )
            except Task.DoesNotExist:
                errors.append(
                    {
                        "task_id": str(task_id),
                        "error": _("Task not found."),
                    }
                )
                continue

            duration = task.duration_mins or 30
            start_dt = datetime.combine(
                date_str,
                datetime.strptime(time_str, "%H:%M").time(),
            ).replace(tzinfo=dt_timezone.utc)
            end_dt = start_dt + timedelta(minutes=duration)

            # Create calendar event
            event = CalendarEvent.objects.create(
                user=request.user,
                task=task,
                title=task.title,
                description=task.description or "",
                start_time=start_dt,
                end_time=end_dt,
                status="scheduled",
            )

            # Update task scheduled_date and scheduled_time
            task.scheduled_date = start_dt
            task.scheduled_time = time_str
            task.save(update_fields=["scheduled_date", "scheduled_time"])

            created_events.append(CalendarEventSerializer(event).data)

        return Response(
            {
                "created": created_events,
                "errors": errors,
                "count": len(created_events),
            },
            status=status.HTTP_201_CREATED,
        )


def _compute_slot_score(
    slot_time,
    slot_date,
    slot_hour,
    dream_priority,
    task,
    productivity_by_hour,
    day_mins_so_far,
    now,
    energy_by_hour=None,
    has_energy_profile=False,
):
    """Compute a 0-1 score for a candidate time slot.

    When the user has an energy profile, high-priority / hard tasks get a
    strong bonus for peak-energy hours and a penalty for low-energy hours.
    """
    score = 0.0

    # 1) Productivity alignment (0-0.30)
    prod = productivity_by_hour[slot_hour] if 0 <= slot_hour < 24 else 0.5
    if dream_priority >= 3:
        score += prod * 0.30
    else:
        score += prod * 0.20

    # 2) Energy profile alignment (0-0.20) — peak hours preference
    if has_energy_profile and energy_by_hour:
        energy = energy_by_hour[slot_hour] if 0 <= slot_hour < 24 else 0.0
        if energy > 0:
            # Peak hour — big bonus for hard / high-priority tasks
            if dream_priority >= 3:
                score += 0.20
            else:
                score += 0.12
        elif energy < 0:
            # Low energy hour — penalty for hard tasks, small bonus for easy ones
            if dream_priority >= 3:
                score -= 0.10  # discourage hard tasks during low-energy
            else:
                score += 0.05  # easy tasks are fine here
        else:
            # Neutral hours
            score += 0.06

    # 3) Deadline proximity bonus (0-0.20)
    if task.deadline_date:
        days_until = (task.deadline_date - slot_date).days
        if days_until <= 0:
            score += 0.20  # Overdue — schedule ASAP
        elif days_until <= 2:
            score += 0.18
        elif days_until <= 5:
            score += 0.12
        elif days_until <= 14:
            score += 0.06
    elif task.expected_date:
        days_until = (task.expected_date - slot_date).days
        if days_until <= 0:
            score += 0.15
        elif days_until <= 3:
            score += 0.10
        elif days_until <= 7:
            score += 0.06

    # 4) Sooner is better (0-0.12) — mild preference for earlier dates
    days_from_now = (slot_date - now.date()).days
    if days_from_now <= 1:
        score += 0.12
    elif days_from_now <= 3:
        score += 0.10
    elif days_from_now <= 7:
        score += 0.06
    else:
        score += 0.02

    # 5) Day load balancing (0-0.10) — prefer less loaded days
    if day_mins_so_far == 0:
        score += 0.10
    elif day_mins_so_far < 60:
        score += 0.07
    elif day_mins_so_far < 120:
        score += 0.03

    # 6) Spacing bonus (0-0.08) — prefer mid-morning, early afternoon
    if 8 <= slot_hour <= 10:
        score += 0.08  # Prime morning
    elif 13 <= slot_hour <= 15:
        score += 0.06  # Early afternoon
    elif 7 <= slot_hour <= 11:
        score += 0.05
    elif 15 <= slot_hour <= 17:
        score += 0.03

    return score


def _build_reason(
    slot_hour,
    productivity_by_hour,
    dream_priority,
    task,
    slot_date,
    now,
    energy_by_hour=None,
    has_energy_profile=False,
):
    """Build a human-readable reason for the scheduling suggestion."""
    reasons = []

    # Energy-profile-based reason (takes priority when present)
    if has_energy_profile and energy_by_hour:
        energy = energy_by_hour[slot_hour] if 0 <= slot_hour < 24 else 0.0
        if energy > 0:
            reasons.append(_("Placed in your peak energy hours"))
        elif energy < 0 and dream_priority < 3:
            reasons.append(_("Low-energy slot suited for lighter tasks"))

    # Productivity-based reason
    prod = productivity_by_hour[slot_hour] if 0 <= slot_hour < 24 else 0.5
    if prod >= 0.8:
        if slot_hour < 12:
            reasons.append(_("You're most productive in the morning"))
        elif slot_hour < 17:
            reasons.append(_("This is one of your peak productivity hours"))
        else:
            reasons.append(_("You tend to be focused at this time"))
    elif prod >= 0.6:
        reasons.append(_("Good productivity window based on your history"))

    # Priority-based reason
    if dream_priority >= 3:
        reasons.append(_("high-priority task scheduled at an optimal time"))
    elif dream_priority >= 2:
        reasons.append(_("prioritized based on dream importance"))

    # Deadline-based reason
    if task.deadline_date:
        days_until = (task.deadline_date - slot_date).days
        if days_until <= 0:
            reasons.append(_("deadline has passed — urgent"))
        elif days_until <= 2:
            reasons.append(_("deadline is approaching soon"))
        elif days_until <= 7:
            reasons.append(_("scheduled well before the deadline"))
    elif task.expected_date:
        days_until = (task.expected_date - slot_date).days
        if days_until <= 3:
            reasons.append(_("expected completion date is near"))

    if not reasons:
        if slot_hour < 12:
            reasons.append(_("Morning slot with no conflicts"))
        elif slot_hour < 17:
            reasons.append(_("Afternoon slot with no conflicts"))
        else:
            reasons.append(_("Available time slot with no conflicts"))

    return "; ".join(str(r) for r in reasons[:2])


def _ical_escape(text):
    """Escape special characters for iCal format (RFC 5545)."""
    if not text:
        return ""
    return (
        text.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\r\n", "\\n")
        .replace("\r", "\\n")
        .replace("\n", "\\n")
    )


# ═══════════════════════════════════════════════════════════════════
# Calendar Sharing Views
# ═══════════════════════════════════════════════════════════════════


def _get_active_buddies(user):
    """Return list of user IDs that are active buddies of the given user."""
    pairings = BuddyPairing.objects.filter(
        Q(user1=user) | Q(user2=user),
        status="active",
    )
    buddy_ids = []
    for p in pairings:
        if p.user1_id == user.id:
            buddy_ids.append(p.user2_id)
        else:
            buddy_ids.append(p.user1_id)
    return buddy_ids


class CalendarShareView(APIView):
    """
    Share calendar with a buddy.

    POST /api/calendar/share/
    Creates a calendar share with a specific buddy user.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Share calendar with a buddy",
        tags=["Calendar Sharing"],
        request=CalendarShareCreateSerializer,
        responses={
            201: CalendarShareSerializer,
            400: OpenApiResponse(description="Invalid request or not a buddy"),
            409: OpenApiResponse(description="Already shared with this user"),
        },
    )
    def post(self, request):
        serializer = CalendarShareCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        permission = serializer.validated_data["permission"]

        # Verify the target user is an active buddy
        buddy_ids = _get_active_buddies(request.user)
        if user_id not in buddy_ids:
            return Response(
                {"error": _("You can only share your calendar with active buddies.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for existing share
        existing = CalendarShare.objects.filter(
            owner=request.user,
            shared_with_id=user_id,
        ).first()

        if existing:
            if existing.is_active:
                return Response(
                    {"error": _("Calendar is already shared with this user.")},
                    status=status.HTTP_409_CONFLICT,
                )
            # Reactivate an inactive share
            existing.is_active = True
            existing.permission = permission
            existing.save(update_fields=["is_active", "permission"])
            return Response(
                CalendarShareSerializer(existing).data,
                status=status.HTTP_201_CREATED,
            )

        share = CalendarShare.objects.create(
            owner=request.user,
            shared_with_id=user_id,
            permission=permission,
        )
        return Response(
            CalendarShareSerializer(share).data,
            status=status.HTTP_201_CREATED,
        )


class CalendarSharedWithMeView(APIView):
    """
    List calendars shared with the current user.

    GET /api/calendar/shared-with-me/
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Calendars shared with me",
        tags=["Calendar Sharing"],
        responses={200: CalendarShareSerializer(many=True)},
    )
    def get(self, request):
        shares = CalendarShare.objects.filter(
            shared_with=request.user,
            is_active=True,
        ).select_related("owner", "shared_with")
        return Response(CalendarShareSerializer(shares, many=True).data)


class CalendarMySharesView(APIView):
    """
    List calendars the current user has shared with others.

    GET /api/calendar/my-shares/
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="My shared calendars",
        tags=["Calendar Sharing"],
        responses={200: CalendarShareSerializer(many=True)},
    )
    def get(self, request):
        shares = CalendarShare.objects.filter(
            owner=request.user,
            is_active=True,
        ).select_related("owner", "shared_with")
        return Response(CalendarShareSerializer(shares, many=True).data)


class CalendarShareRevokeView(APIView):
    """
    Revoke a calendar share.

    DELETE /api/calendar/share/<id>/
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Revoke calendar share",
        tags=["Calendar Sharing"],
        responses={
            204: OpenApiResponse(description="Share revoked"),
            404: OpenApiResponse(description="Share not found"),
        },
    )
    def delete(self, request, share_id):
        try:
            share = CalendarShare.objects.get(
                id=share_id,
                owner=request.user,
            )
        except CalendarShare.DoesNotExist:
            return Response(
                {"error": _("Calendar share not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        share.is_active = False
        share.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CalendarShareLinkView(APIView):
    """
    Generate a shareable calendar link.

    POST /api/calendar/share-link/
    Creates a link-only share (no specific user) with a unique token.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Generate shareable calendar link",
        tags=["Calendar Sharing"],
        request=CalendarShareLinkSerializer,
        responses={
            201: CalendarShareSerializer,
        },
    )
    def post(self, request):
        serializer = CalendarShareLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        permission = serializer.validated_data["permission"]

        share = CalendarShare.objects.create(
            owner=request.user,
            shared_with=None,
            permission=permission,
        )
        return Response(
            CalendarShareSerializer(share).data,
            status=status.HTTP_201_CREATED,
        )


class SharedCalendarView(APIView):
    """
    View a shared calendar by token (read-only).

    GET /api/calendar/shared/<token>/
    Public endpoint (no auth required for link shares).
    Authenticated users with direct shares can also view via token.
    Returns calendar events for the shared calendar owner.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="View shared calendar",
        tags=["Calendar Sharing"],
        responses={
            200: OpenApiResponse(description="Shared calendar events and metadata"),
            404: OpenApiResponse(description="Shared calendar not found"),
        },
    )
    def get(self, request, token):
        try:
            share = CalendarShare.objects.select_related("owner").get(
                share_token=token,
                is_active=True,
            )
        except CalendarShare.DoesNotExist:
            return Response(
                {"error": _("Shared calendar not found or link has been revoked.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        owner = share.owner
        now = timezone.now()

        # Return events for the next 30 days and past 7 days
        events = CalendarEvent.objects.filter(
            user=owner,
            status="scheduled",
            start_time__gte=now - timedelta(days=7),
            start_time__lte=now + timedelta(days=30),
        ).order_by("start_time")

        events_data = CalendarEventSerializer(events, many=True).data

        return Response(
            {
                "owner": {
                    "id": str(owner.id),
                    "displayName": owner.display_name or "",
                    "avatar": (
                        owner.avatar.url
                        if hasattr(owner, "avatar")
                        and owner.avatar
                        and hasattr(owner.avatar, "url")
                        else ""
                    ),
                },
                "permission": share.permission,
                "events": events_data,
            }
        )


class SharedCalendarSuggestView(APIView):
    """
    Suggest a time on a shared calendar.

    POST /api/calendar/shared/<token>/suggest/
    Only works for shares with 'suggest' permission.
    Creates a notification for the calendar owner.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Suggest time on shared calendar",
        tags=["Calendar Sharing"],
        request=TimeSuggestionSerializer,
        responses={
            201: OpenApiResponse(description="Suggestion sent"),
            403: OpenApiResponse(description="Suggest permission not granted"),
            404: OpenApiResponse(description="Shared calendar not found"),
        },
    )
    def post(self, request, token):
        try:
            share = CalendarShare.objects.select_related("owner").get(
                share_token=token,
                is_active=True,
            )
        except CalendarShare.DoesNotExist:
            return Response(
                {"error": _("Shared calendar not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        if share.permission != "suggest":
            return Response(
                {
                    "error": _(
                        "You do not have permission to suggest times on this calendar."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = TimeSuggestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create a notification for the calendar owner
        try:
            from apps.notifications.models import Notification

            note = serializer.validated_data.get("note", "")
            Notification.objects.create(
                user=share.owner,
                title=_("Time Suggestion"),
                body=_("%(name)s suggested a time: %(start)s - %(end)s%(note)s")
                % {
                    "name": request.user.display_name or request.user.email,
                    "start": serializer.validated_data["suggested_start"].strftime(
                        "%b %d, %H:%M"
                    ),
                    "end": serializer.validated_data["suggested_end"].strftime("%H:%M"),
                    "note": f" — {note}" if note else "",
                },
                notification_type="calendar_suggestion",
                data={
                    "suggested_start": serializer.validated_data[
                        "suggested_start"
                    ].isoformat(),
                    "suggested_end": serializer.validated_data[
                        "suggested_end"
                    ].isoformat(),
                    "from_user_id": str(request.user.id),
                    "from_user_name": request.user.display_name or request.user.email,
                    "note": note,
                    "share_token": token,
                },
            )
        except Exception:
            pass  # Notifications are best-effort

        return Response(
            {"message": _("Time suggestion sent successfully.")},
            status=status.HTTP_201_CREATED,
        )


# ─── Habit Tracker ──────────────────────────────────────────────


def _compute_habit_streak(habit):
    """Recompute current and best streak for a habit from completion history."""

    today = timezone.now().date()
    completions = set(habit.completions.values_list("date", flat=True))

    if not completions:
        habit.streak_current = 0
        habit.save(update_fields=["streak_current", "streak_best"])
        return

    # Determine which days are "expected" based on frequency
    def is_expected_day(d):
        dow = d.weekday()  # 0=Mon, 6=Sun
        if habit.frequency == "daily":
            return True
        elif habit.frequency == "weekdays":
            return dow < 5
        elif habit.frequency == "weekly":
            return dow == habit.created_at.weekday()
        elif habit.frequency == "custom":
            return dow in (habit.custom_days or [])
        return True

    # Calculate current streak (counting backwards from today)
    current_streak = 0
    check_date = today
    # Allow today to not yet be completed without breaking streak
    if check_date not in completions and is_expected_day(check_date):
        check_date = check_date - timedelta(days=1)

    while True:
        if is_expected_day(check_date):
            if check_date in completions:
                current_streak += 1
            else:
                break
        check_date = check_date - timedelta(days=1)
        if check_date < habit.created_at.date():
            break

    # Calculate best streak from all completions
    sorted_dates = sorted(completions)
    best_streak = 0
    running = 0
    prev = None

    for d in sorted_dates:
        if prev is None:
            running = 1
        else:
            gap_date = prev + timedelta(days=1)
            gap_ok = True
            while gap_date < d:
                if is_expected_day(gap_date):
                    gap_ok = False
                    break
                gap_date += timedelta(days=1)

            if gap_ok:
                running += 1
            else:
                running = 1
        best_streak = max(best_streak, running)
        prev = d

    habit.streak_current = current_streak
    habit.streak_best = max(habit.streak_best, best_streak, current_streak)
    habit.save(update_fields=["streak_current", "streak_best"])


class HabitViewSet(viewsets.ModelViewSet):
    """ViewSet for managing habits and habit completions."""

    permission_classes = [IsAuthenticated]
    serializer_class = HabitSerializer

    def get_queryset(self):
        return Habit.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        """Mark a habit as completed for a given date."""
        habit = self.get_object()
        serializer = HabitCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        date_val = serializer.validated_data["date"]
        note = serializer.validated_data.get("note", "")

        completion, created = HabitCompletion.objects.get_or_create(
            habit=habit,
            date=date_val,
            defaults={"note": note, "count": 1},
        )

        if not created:
            completion.count = min(completion.count + 1, habit.target_per_day)
            if note:
                completion.note = note
            completion.save(update_fields=["count", "note"])

        _compute_habit_streak(habit)
        habit.refresh_from_db()

        streak_continued = habit.streak_current > 1

        return Response(
            {
                "completion": HabitCompletionSerializer(completion).data,
                "streak_current": habit.streak_current,
                "streak_best": habit.streak_best,
                "streak_continued": streak_continued,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="uncomplete")
    def uncomplete(self, request, pk=None):
        """Remove completion of a habit for a given date."""
        habit = self.get_object()
        serializer = HabitUncompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        date_val = serializer.validated_data["date"]

        deleted_count, _ = HabitCompletion.objects.filter(
            habit=habit,
            date=date_val,
        ).delete()

        _compute_habit_streak(habit)
        habit.refresh_from_db()

        return Response(
            {
                "removed": deleted_count > 0,
                "streak_current": habit.streak_current,
                "streak_best": habit.streak_best,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="stats")
    def stats(self, request, pk=None):
        """Get habit completion statistics."""
        habit = self.get_object()
        today = timezone.now().date()

        total_completions = habit.completions.count()

        month_start = today.replace(day=1)
        month_completions = habit.completions.filter(
            date__gte=month_start,
            date__lte=today,
        ).count()

        days_since_creation = max((today - habit.created_at.date()).days, 1)

        expected = 0
        check = habit.created_at.date()
        while check <= today:
            dow = check.weekday()
            if habit.frequency == "daily":
                expected += 1
            elif habit.frequency == "weekdays" and dow < 5:
                expected += 1
            elif habit.frequency == "weekly" and dow == habit.created_at.weekday():
                expected += 1
            elif habit.frequency == "custom" and dow in (habit.custom_days or []):
                expected += 1
            check += timedelta(days=1)

        completion_rate = round((total_completions / max(expected, 1)) * 100, 1)

        monthly_stats = []
        for i in range(5, -1, -1):
            m_start = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
            if i > 0:
                m_end = (m_start.replace(day=28) + timedelta(days=4)).replace(
                    day=1
                ) - timedelta(days=1)
            else:
                m_end = today
            m_count = habit.completions.filter(
                date__gte=m_start,
                date__lte=m_end,
            ).count()
            monthly_stats.append(
                {
                    "month": m_start.strftime("%Y-%m"),
                    "label": m_start.strftime("%b"),
                    "count": m_count,
                }
            )

        return Response(
            {
                "habit_id": str(habit.id),
                "name": habit.name,
                "total_completions": total_completions,
                "month_completions": month_completions,
                "completion_rate": completion_rate,
                "streak_current": habit.streak_current,
                "streak_best": habit.streak_best,
                "days_tracked": days_since_creation,
                "monthly_stats": monthly_stats,
            }
        )

    @action(detail=False, methods=["get"], url_path="calendar-data")
    def calendar_data(self, request):
        """Get habit completion data for calendar display."""
        month = request.query_params.get("month")
        year = request.query_params.get("year")

        if not month or not year:
            today = timezone.now().date()
            month = today.month
            year = today.year
        else:
            month = int(month)
            year = int(year)

        first_day = datetime(year, month, 1).date()
        last_day_num = cal_module.monthrange(year, month)[1]
        last_day = datetime(year, month, last_day_num).date()

        habits = Habit.objects.filter(
            user=request.user,
            is_active=True,
        )

        completions = HabitCompletion.objects.filter(
            habit__user=request.user,
            habit__is_active=True,
            date__gte=first_day,
            date__lte=last_day,
        ).select_related("habit")

        completion_map = {}
        for comp in completions:
            date_str = comp.date.isoformat()
            if date_str not in completion_map:
                completion_map[date_str] = []
            completion_map[date_str].append(
                {
                    "habit_id": str(comp.habit_id),
                    "habit_name": comp.habit.name,
                    "color": comp.habit.color,
                    "icon": comp.habit.icon,
                    "count": comp.count,
                    "target": comp.habit.target_per_day,
                }
            )

        return Response(
            {
                "month": month,
                "year": year,
                "habits": HabitSerializer(habits, many=True).data,
                "completions": completion_map,
            }
        )
