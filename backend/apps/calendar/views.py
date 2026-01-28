"""
Views for Calendar app.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import datetime, timedelta

from .models import CalendarEvent, TimeBlock
from .serializers import (
    CalendarEventSerializer, CalendarEventCreateSerializer,
    TimeBlockSerializer, CalendarTaskSerializer
)
from apps.dreams.models import Task


class CalendarEventViewSet(viewsets.ModelViewSet):
    """CRUD operations for calendar events."""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get calendar events for current user."""
        return CalendarEvent.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action == 'create':
            return CalendarEventCreateSerializer
        return CalendarEventSerializer

    def perform_create(self, serializer):
        """Create event for current user."""
        serializer.save(user=self.request.user)


class TimeBlockViewSet(viewsets.ModelViewSet):
    """CRUD operations for time blocks."""

    permission_classes = [IsAuthenticated]
    serializer_class = TimeBlockSerializer

    def get_queryset(self):
        """Get time blocks for current user."""
        return TimeBlock.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Create time block for current user."""
        serializer.save(user=self.request.user)


class CalendarViewSet(viewsets.ViewSet):
    """Calendar views and operations."""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def view(self, request):
        """Get calendar view for date range."""
        start_date = request.query_params.get('start')
        end_date = request.query_params.get('end')

        if not start_date or not end_date:
            return Response(
                {'error': 'start and end dates required (ISO format)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'},
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

    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get tasks for today."""
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)

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

    @action(detail=False, methods=['post'])
    def reschedule(self, request):
        """Reschedule a task."""
        task_id = request.data.get('task_id')
        new_date = request.data.get('new_date')

        if not task_id or not new_date:
            return Response(
                {'error': 'task_id and new_date required'},
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
                'message': 'Task rescheduled successfully',
                'task_id': task.id,
                'new_date': task.scheduled_date
            })

        except Task.DoesNotExist:
            return Response(
                {'error': 'Task not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError:
            return Response(
                {'error': 'Invalid date format'},
                status=status.HTTP_400_BAD_REQUEST
            )
