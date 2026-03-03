"""
Views for Calendar app.
"""

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from django.http import HttpResponse
from datetime import datetime, timedelta, timezone as dt_timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse, inline_serializer
from rest_framework import serializers as drf_serializers

from .models import CalendarEvent, TimeBlock, GoogleCalendarIntegration
from .serializers import (
    CalendarEventSerializer, CalendarEventCreateSerializer,
    TimeBlockSerializer, CalendarTaskSerializer,
    CalendarEventRescheduleSerializer, SuggestTimeSlotsSerializer,
)
from apps.dreams.models import Task


def _check_conflicts(user, start_time, end_time, exclude_event_id=None):
    """Check for overlapping events for a user."""
    qs = CalendarEvent.objects.filter(
        user=user,
        status='scheduled',
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_event_id:
        qs = qs.exclude(id=exclude_event_id)
    return qs


@extend_schema_view(
    list=extend_schema(summary="List events", description="Get all calendar events for the current user", tags=["Calendar Events"]),
    create=extend_schema(summary="Create event", description="Create a new calendar event", tags=["Calendar Events"]),
    retrieve=extend_schema(summary="Get event", description="Get a specific calendar event", tags=["Calendar Events"]),
    update=extend_schema(summary="Update event", description="Update a calendar event", tags=["Calendar Events"]),
    partial_update=extend_schema(summary="Partial update event", description="Partially update a calendar event", tags=["Calendar Events"]),
    destroy=extend_schema(summary="Delete event", description="Delete a calendar event", tags=["Calendar Events"]),
)
class CalendarEventViewSet(viewsets.ModelViewSet):
    """CRUD operations for calendar events."""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get calendar events for current user."""
        if getattr(self, 'swagger_fake_view', False):
            return CalendarEvent.objects.none()
        return CalendarEvent.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action in ('create', 'update', 'partial_update'):
            return CalendarEventCreateSerializer
        return CalendarEventSerializer

    def perform_create(self, serializer):
        """Create event for current user with conflict detection."""
        data = serializer.validated_data
        force = data.pop('force', False)

        conflicts = _check_conflicts(
            self.request.user, data['start_time'], data['end_time']
        )

        if conflicts.exists() and not force:
            conflict_data = CalendarEventSerializer(conflicts, many=True).data
            raise ConflictException(conflict_data)

        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        """Update event with conflict detection."""
        data = serializer.validated_data
        force = data.pop('force', False)

        start = data.get('start_time', serializer.instance.start_time)
        end = data.get('end_time', serializer.instance.end_time)

        conflicts = _check_conflicts(
            self.request.user, start, end,
            exclude_event_id=serializer.instance.id
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
                    'detail': _('This event conflicts with existing events.'),
                    'conflicts': e.conflicts,
                    'hint': _('Set force=true to save anyway.'),
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
                    'detail': _('This event conflicts with existing events.'),
                    'conflicts': e.conflicts,
                    'hint': _('Set force=true to save anyway.'),
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
    @action(detail=True, methods=['patch'], url_path='reschedule')
    def reschedule(self, request, pk=None):
        """Reschedule a calendar event to new start/end times."""
        event = self.get_object()
        serializer = CalendarEventRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_start = serializer.validated_data['start_time']
        new_end = serializer.validated_data['end_time']
        force = serializer.validated_data.get('force', False)

        conflicts = _check_conflicts(
            request.user, new_start, new_end, exclude_event_id=event.id
        )

        if conflicts.exists() and not force:
            return Response(
                {
                    'detail': _('This time conflicts with existing events.'),
                    'conflicts': CalendarEventSerializer(conflicts, many=True).data,
                    'hint': _('Set force=true to save anyway.'),
                },
                status=status.HTTP_409_CONFLICT,
            )

        event.start_time = new_start
        event.end_time = new_end
        event.status = 'scheduled'
        event.save(update_fields=['start_time', 'end_time', 'status', 'updated_at'])

        # Update linked task scheduled_date if present
        if event.task:
            event.task.scheduled_date = new_start
            event.task.save(update_fields=['scheduled_date'])

        return Response(CalendarEventSerializer(event).data)


class ConflictException(Exception):
    """Raised when an event conflicts with existing events."""
    def __init__(self, conflicts):
        self.conflicts = conflicts


@extend_schema_view(
    list=extend_schema(summary="List time blocks", description="Get all time blocks for the current user", tags=["Time Blocks"]),
    create=extend_schema(summary="Create time block", description="Create a new time block", tags=["Time Blocks"]),
    retrieve=extend_schema(summary="Get time block", description="Get a specific time block", tags=["Time Blocks"]),
    update=extend_schema(summary="Update time block", description="Update a time block", tags=["Time Blocks"]),
    partial_update=extend_schema(summary="Partial update time block", description="Partially update a time block", tags=["Time Blocks"]),
    destroy=extend_schema(summary="Delete time block", description="Delete a time block", tags=["Time Blocks"]),
)
class TimeBlockViewSet(viewsets.ModelViewSet):
    """CRUD operations for time blocks."""

    permission_classes = [IsAuthenticated]
    serializer_class = TimeBlockSerializer

    def get_queryset(self):
        """Get time blocks for current user."""
        if getattr(self, 'swagger_fake_view', False):
            return TimeBlock.objects.none()
        return TimeBlock.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Create time block for current user."""
        serializer.save(user=self.request.user)


class CalendarViewSet(viewsets.ViewSet):
    """Calendar views and operations."""

    permission_classes = [IsAuthenticated]
    serializer_class = CalendarTaskSerializer

    @extend_schema(
        summary="Get calendar view",
        description="Get tasks for a date range",
        tags=["Calendar"],
        parameters=[
            OpenApiParameter(name='start', description='Start date (ISO format)', required=True, type=str),
            OpenApiParameter(name='end', description='End date (ISO format)', required=True, type=str),
        ],
        responses={200: CalendarTaskSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def view(self, request):
        """Get calendar view for date range."""
        start_date = request.query_params.get('start')
        end_date = request.query_params.get('end')

        if not start_date or not end_date:
            return Response(
                {'error': _('start and end dates required (ISO format)')},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            return Response(
                {'error': _('Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get tasks in date range
        tasks = Task.objects.filter(
            goal__dream__user=request.user,
            scheduled_date__gte=start,
            scheduled_date__lte=end
        ).select_related('goal__dream').order_by('scheduled_date')

        # Format tasks for calendar
        calendar_tasks = []
        for task in tasks:
            calendar_tasks.append({
                'task_id': task.id,
                'task_title': task.title,
                'goal_id': task.goal.id,
                'goal_title': task.goal.title,
                'dream_id': task.goal.dream.id,
                'dream_title': task.goal.dream.title,
                'scheduled_date': task.scheduled_date,
                'scheduled_time': task.scheduled_time,
                'duration_mins': task.duration_mins,
                'status': task.status,
                'is_two_minute_start': task.is_two_minute_start,
            })

        return Response(calendar_tasks)

    @extend_schema(summary="Today's tasks", description="Get all tasks scheduled for today", tags=["Calendar"], responses={200: CalendarTaskSerializer(many=True)})
    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get tasks for today."""
        today = timezone.now().date()

        tasks = Task.objects.filter(
            goal__dream__user=request.user,
            scheduled_date__date=today
        ).select_related('goal__dream').order_by('scheduled_time', 'order')

        calendar_tasks = []
        for task in tasks:
            calendar_tasks.append({
                'task_id': task.id,
                'task_title': task.title,
                'goal_id': task.goal.id,
                'goal_title': task.goal.title,
                'dream_id': task.goal.dream.id,
                'dream_title': task.goal.dream.title,
                'scheduled_date': task.scheduled_date,
                'scheduled_time': task.scheduled_time,
                'duration_mins': task.duration_mins,
                'status': task.status,
                'is_two_minute_start': task.is_two_minute_start,
            })

        return Response(calendar_tasks)

    @extend_schema(summary="Reschedule task", description="Reschedule a task to a new date", tags=["Calendar"], responses={200: dict})
    @action(detail=False, methods=['post'])
    def reschedule(self, request):
        """Reschedule a task."""
        task_id = request.data.get('task_id')
        new_date = request.data.get('new_date')

        if not task_id or not new_date:
            return Response(
                {'error': _('task_id and new_date required')},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            task = Task.objects.get(
                id=task_id,
                goal__dream__user=request.user
            )

            task.scheduled_date = datetime.fromisoformat(new_date.replace('Z', '+00:00'))
            task.save(update_fields=['scheduled_date'])

            return Response({
                'message': _('Task rescheduled successfully'),
                'task_id': task.id,
                'new_date': task.scheduled_date
            })

        except Task.DoesNotExist:
            return Response(
                {'error': _('Task not found')},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError:
            return Response(
                {'error': _('Invalid date format')},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        summary="Suggest time slots",
        description="Find optimal open time slots for a given date and duration.",
        tags=["Calendar"],
        parameters=[
            OpenApiParameter(name='date', description='Date (YYYY-MM-DD)', required=True, type=str),
            OpenApiParameter(name='duration_mins', description='Duration in minutes', required=True, type=int),
        ],
        responses={200: dict},
    )
    @action(detail=False, methods=['get'], url_path='suggest-time-slots')
    def suggest_time_slots(self, request):
        """Find optimal open time slots on a given date."""
        date_str = request.query_params.get('date')
        duration_str = request.query_params.get('duration_mins')

        if not date_str or not duration_str:
            return Response(
                {'error': _('date and duration_mins are required')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            duration = int(duration_str)
        except ValueError:
            return Response(
                {'error': _('Invalid date or duration format')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if duration < 5 or duration > 480:
            return Response(
                {'error': _('Duration must be between 5 and 480 minutes')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get user's buffer preference (default 15 minutes)
        buffer_mins = 15
        if hasattr(request.user, 'notification_prefs') and request.user.notification_prefs:
            buffer_mins = request.user.notification_prefs.get('buffer_minutes', 15)

        # Get existing events for the day
        day_start = datetime.combine(target_date, datetime.min.time()).replace(
            tzinfo=dt_timezone.utc
        )
        day_end = day_start + timedelta(days=1)

        events = CalendarEvent.objects.filter(
            user=request.user,
            status='scheduled',
            start_time__lt=day_end,
            end_time__gt=day_start,
        ).order_by('start_time')

        # Get time blocks for this day of week
        day_of_week = target_date.weekday()
        blocked_times = TimeBlock.objects.filter(
            user=request.user,
            day_of_week=day_of_week,
            is_active=True,
            block_type='blocked',
        )

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

        # Sort busy intervals
        busy.sort(key=lambda x: x[0])

        # Find free slots between 8 AM and 10 PM
        work_start = day_start + timedelta(hours=8)
        work_end = day_start + timedelta(hours=22)
        needed = timedelta(minutes=duration)
        buffer = timedelta(minutes=buffer_mins)

        slots = []
        current = work_start

        for busy_start, busy_end in busy:
            if busy_start < work_start:
                current = max(current, busy_end + buffer)
                continue
            if current + needed <= busy_start - buffer:
                slots.append({
                    'start': current.isoformat(),
                    'end': (current + needed).isoformat(),
                })
            current = max(current, busy_end + buffer)

        # Check slot after last busy interval
        if current + needed <= work_end:
            slots.append({
                'start': current.isoformat(),
                'end': (current + needed).isoformat(),
            })

        return Response({
            'date': date_str,
            'duration_mins': duration,
            'buffer_mins': buffer_mins,
            'slots': slots[:10],  # Return max 10 suggestions
        })


class GoogleCalendarStatusView(APIView):
    """Check Google Calendar connection status for the current user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Google Calendar connection status",
        tags=["Calendar Integration"],
        request=None,
        responses={
            200: inline_serializer(
                name='GoogleCalendarStatusResponse',
                fields={
                    'connected': drf_serializers.BooleanField(),
                    'last_sync_at': drf_serializers.DateTimeField(allow_null=True),
                },
            ),
        },
    )
    def get(self, request):
        try:
            integration = GoogleCalendarIntegration.objects.get(
                user=request.user, sync_enabled=True
            )
            return Response({
                'connected': True,
                'last_sync_at': integration.last_sync_at,
            })
        except GoogleCalendarIntegration.DoesNotExist:
            return Response({
                'connected': False,
                'last_sync_at': None,
            })


class GoogleCalendarAuthView(APIView):
    """Initiate Google Calendar OAuth2 flow."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Google OAuth URL",
        tags=["Calendar Integration"],
        request=None,
        responses={
            200: inline_serializer(
                name='GoogleCalendarAuthResponse',
                fields={'auth_url': drf_serializers.URLField()},
            ),
            501: OpenApiResponse(description='Google Calendar integration not configured'),
        },
    )
    def get(self, request):
        from integrations.google_calendar import GoogleCalendarService
        from django.conf import settings

        # Allow frontend to override redirect_uri for native OAuth flow
        redirect_uri = request.query_params.get(
            'redirect_uri',
            getattr(settings, 'GOOGLE_CALENDAR_REDIRECT_URI', ''),
        )
        if not redirect_uri:
            return Response(
                {'error': _('Google Calendar integration is not configured.')},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        service = GoogleCalendarService()
        auth_url = service.get_auth_url(redirect_uri)
        return Response({'auth_url': auth_url})


class GoogleCalendarCallbackView(APIView):
    """Handle Google Calendar OAuth2 callback."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Google OAuth callback",
        tags=["Calendar Integration"],
        request=inline_serializer(
            name='GoogleCalendarCallbackRequest',
            fields={'code': drf_serializers.CharField()},
        ),
        responses={
            200: inline_serializer(
                name='GoogleCalendarCallbackResponse',
                fields={
                    'status': drf_serializers.CharField(),
                    'calendar_id': drf_serializers.CharField(),
                    'ical_feed_token': drf_serializers.CharField(),
                },
            ),
            400: OpenApiResponse(description='Invalid or missing authorization code'),
        },
    )
    def post(self, request):
        from integrations.google_calendar import GoogleCalendarService
        from django.conf import settings

        code = request.data.get('code')
        if not code:
            return Response({'error': _('Authorization code is required.')}, status=status.HTTP_400_BAD_REQUEST)

        redirect_uri = request.data.get(
            'redirect_uri',
            getattr(settings, 'GOOGLE_CALENDAR_REDIRECT_URI', ''),
        )
        service = GoogleCalendarService()

        try:
            tokens = service.exchange_code(code, redirect_uri)
        except Exception as e:
            return Response({'error': _('Token exchange failed: %(error)s') % {'error': str(e)}}, status=status.HTTP_400_BAD_REQUEST)

        integration, _ = GoogleCalendarIntegration.objects.update_or_create(
            user=request.user,
            defaults={
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token'],
                'token_expiry': tokens['token_expiry'],
                'sync_enabled': True,
            },
        )

        return Response({
            'status': 'connected',
            'calendar_id': integration.calendar_id,
            'ical_feed_token': integration.ical_feed_token,
        })


class GoogleCalendarSyncView(APIView):
    """Trigger a manual Google Calendar sync."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Trigger Google Calendar sync",
        tags=["Calendar Integration"],
        request=None,
        responses={
            200: inline_serializer(
                name='GoogleCalendarSyncResponse',
                fields={
                    'status': drf_serializers.CharField(),
                    'last_sync': drf_serializers.DateTimeField(),
                },
            ),
            404: OpenApiResponse(description='Google Calendar not connected'),
        },
    )
    def post(self, request):
        from .tasks import sync_google_calendar
        try:
            integration = GoogleCalendarIntegration.objects.get(user=request.user, sync_enabled=True)
        except GoogleCalendarIntegration.DoesNotExist:
            return Response({'error': _('Google Calendar not connected.')}, status=status.HTTP_404_NOT_FOUND)

        sync_google_calendar.delay(str(integration.id))
        return Response({'status': 'sync_queued', 'last_sync': integration.last_sync_at})


class GoogleCalendarDisconnectView(APIView):
    """Disconnect Google Calendar integration."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Disconnect Google Calendar",
        tags=["Calendar Integration"],
        request=None,
        responses={
            200: inline_serializer(
                name='GoogleCalendarDisconnectResponse',
                fields={'status': drf_serializers.CharField()},
            ),
            404: OpenApiResponse(description='No integration found'),
        },
    )
    def post(self, request):
        deleted, _ = GoogleCalendarIntegration.objects.filter(user=request.user).delete()
        if deleted:
            return Response({'status': 'disconnected'})
        return Response({'error': _('No integration found.')}, status=status.HTTP_404_NOT_FOUND)


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
            200: OpenApiResponse(description='iCal feed content'),
            404: OpenApiResponse(description='Feed not found'),
        },
    )
    def get(self, request, feed_token):
        try:
            integration = GoogleCalendarIntegration.objects.select_related('user').get(
                ical_feed_token=feed_token
            )
        except GoogleCalendarIntegration.DoesNotExist:
            return HttpResponse(_('Feed not found.'), status=404, content_type='text/plain')

        user = integration.user
        now = timezone.now()
        events = CalendarEvent.objects.filter(
            user=user,
            status='scheduled',
            start_time__gte=now - timedelta(days=30),
            start_time__lte=now + timedelta(days=90),
        ).order_by('start_time')

        # Build iCalendar format
        lines = [
            'BEGIN:VCALENDAR',
            'VERSION:2.0',
            'PRODID:-//DreamPlanner//Calendar//EN',
            'CALSCALE:GREGORIAN',
            'METHOD:PUBLISH',
            f'X-WR-CALNAME:DreamPlanner - {_ical_escape(user.display_name or user.email)}',
        ]

        for event in events:
            lines.extend([
                'BEGIN:VEVENT',
                f'UID:{event.id}@dreamplanner',
                f'DTSTART:{event.start_time.strftime("%Y%m%dT%H%M%SZ")}',
                f'DTEND:{event.end_time.strftime("%Y%m%dT%H%M%SZ")}',
                f'SUMMARY:{_ical_escape(event.title)}',
                f'DESCRIPTION:{_ical_escape(event.description)}',
            ])
            if event.location:
                lines.append(f'LOCATION:{_ical_escape(event.location)}')
            lines.append('END:VEVENT')

        lines.append('END:VCALENDAR')

        ical_content = '\r\n'.join(lines)
        response = HttpResponse(ical_content, content_type='text/calendar; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="dreamplanner.ics"'
        return response


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
        responses={200: OpenApiResponse(description='HTML redirect page')},
    )
    def get(self, request):
        import html
        import json as json_mod
        code = request.query_params.get('code', '')
        error = request.query_params.get('error', '')

        if error:
            deep_link = f"com.dreamplanner.app://calendar/callback?error={html.escape(error)}"
        elif code:
            deep_link = f"com.dreamplanner.app://calendar/callback?code={html.escape(code)}"
        else:
            return HttpResponse(_('Missing authorization code.'), status=400)

        # Use json.dumps for safe JS string embedding (prevents injection)
        deep_link_js = json_mod.dumps(deep_link)
        deep_link_html = html.escape(deep_link)
        page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Redirecting...</title></head>
<body>
<p>Redirecting to DreamPlanner...</p>
<script>window.location.href = {deep_link_js};</script>
<noscript><a href="{deep_link_html}">Click here to return to the app</a></noscript>
</body></html>"""
        return HttpResponse(page, content_type='text/html')


def _ical_escape(text):
    """Escape special characters for iCal format (RFC 5545)."""
    if not text:
        return ''
    return (
        text
        .replace('\\', '\\\\')
        .replace(',', '\\,')
        .replace(';', '\\;')
        .replace('\r\n', '\\n')
        .replace('\r', '\\n')
        .replace('\n', '\\n')
    )
