"""
Views for the Plans system.

Provides API endpoints for milestones, goals, tasks, obstacles,
check-ins, and focus sessions.
"""

import logging

from django.db.models import Max
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsOwner

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
from .serializers import (
    CalibrationResponseSerializer,
    CheckInResponseSubmitSerializer,
    DreamMilestoneSerializer,
    FocusSessionCompleteSerializer,
    FocusSessionSerializer,
    FocusSessionStartSerializer,
    GoalCreateSerializer,
    GoalSerializer,
    ObstacleSerializer,
    PlanCheckInDetailSerializer,
    PlanCheckInSerializer,
    TaskCreateSerializer,
    TaskSerializer,
)

logger = logging.getLogger(__name__)


class DreamMilestoneViewSet(viewsets.ModelViewSet):
    """CRUD for dream milestones."""

    serializer_class = DreamMilestoneSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = DreamMilestone.objects.filter(dream__user=self.request.user)
        dream_id = self.request.query_params.get("dream")
        if dream_id:
            qs = qs.filter(dream_id=dream_id)
        return qs.select_related("dream").prefetch_related("goals__tasks")

    def perform_create(self, serializer):
        dream = serializer.validated_data.get("dream")
        if dream.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not own this dream.")
        serializer.save()


class GoalViewSet(viewsets.ModelViewSet):
    """CRUD for goals."""

    serializer_class = GoalSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return GoalCreateSerializer
        return GoalSerializer

    def get_queryset(self):
        qs = Goal.objects.filter(dream__user=self.request.user)
        dream_id = self.request.query_params.get("dream")
        milestone_id = self.request.query_params.get("milestone")
        if dream_id:
            qs = qs.filter(dream_id=dream_id)
        if milestone_id:
            qs = qs.filter(milestone_id=milestone_id)
        return qs.select_related("dream", "milestone").prefetch_related("tasks")

    def perform_create(self, serializer):
        dream = serializer.validated_data.get("dream")
        if dream.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not own this dream.")
        # Auto-compute order
        if "order" not in serializer.validated_data or serializer.validated_data["order"] is None:
            max_order = Goal.objects.filter(dream=dream).aggregate(Max("order"))[
                "order__max"
            ]
            serializer.validated_data["order"] = (max_order or 0) + 1
        serializer.save()

    @extend_schema(
        summary="Complete a goal",
        tags=["Plans"],
        responses={200: GoalSerializer},
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        goal = self.get_object()
        goal.complete()
        return Response(GoalSerializer(goal).data)


class TaskViewSet(viewsets.ModelViewSet):
    """CRUD for tasks."""

    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return TaskCreateSerializer
        return TaskSerializer

    def get_queryset(self):
        qs = Task.objects.filter(goal__dream__user=self.request.user)
        goal_id = self.request.query_params.get("goal")
        if goal_id:
            qs = qs.filter(goal_id=goal_id)
        return qs.select_related("goal__dream")

    def perform_create(self, serializer):
        goal = serializer.validated_data.get("goal")
        if goal.dream.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not own this dream.")
        # Auto-compute order
        if "order" not in serializer.validated_data or serializer.validated_data["order"] is None:
            max_order = Task.objects.filter(goal=goal).aggregate(Max("order"))[
                "order__max"
            ]
            serializer.validated_data["order"] = (max_order or 0) + 1
        serializer.save()

    @extend_schema(
        summary="Complete a task",
        tags=["Plans"],
        responses={200: TaskSerializer},
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = self.get_object()
        task.complete()
        return Response(TaskSerializer(task).data)


class ObstacleViewSet(viewsets.ModelViewSet):
    """CRUD for obstacles."""

    serializer_class = ObstacleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Obstacle.objects.filter(dream__user=self.request.user)
        dream_id = self.request.query_params.get("dream")
        if dream_id:
            qs = qs.filter(dream_id=dream_id)
        return qs

    def perform_create(self, serializer):
        dream = serializer.validated_data.get("dream")
        if dream.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not own this dream.")
        serializer.save()


class CheckInViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for plan check-ins."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PlanCheckInDetailSerializer
        return PlanCheckInSerializer

    def get_queryset(self):
        qs = PlanCheckIn.objects.filter(dream__user=self.request.user)
        dream_id = self.request.query_params.get("dream")
        status_filter = self.request.query_params.get("status")
        if dream_id:
            qs = qs.filter(dream_id=dream_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    @extend_schema(
        summary="Submit check-in responses",
        tags=["Plans"],
        request=CheckInResponseSubmitSerializer,
        responses={200: PlanCheckInDetailSerializer},
    )
    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        checkin = self.get_object()
        serializer = CheckInResponseSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        checkin.user_responses = serializer.validated_data["responses"]
        checkin.status = "ai_processing"
        checkin.save(update_fields=["user_responses", "status"])

        # Trigger async processing
        from .tasks import process_checkin_responses

        process_checkin_responses.delay(str(checkin.id))

        return Response(PlanCheckInDetailSerializer(checkin).data)

    @extend_schema(
        summary="Poll check-in status",
        tags=["Plans"],
        responses={200: PlanCheckInDetailSerializer},
    )
    @action(detail=True, methods=["get"])
    def status_poll(self, request, pk=None):
        checkin = self.get_object()
        return Response(PlanCheckInDetailSerializer(checkin).data)


class FocusSessionStartView(APIView):
    """Start a Pomodoro focus session."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Start focus session",
        tags=["Plans"],
        request=FocusSessionStartSerializer,
        responses={201: FocusSessionSerializer},
    )
    def post(self, request):
        serializer = FocusSessionStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = FocusSession.objects.create(
            user=request.user,
            task_id=serializer.validated_data.get("task_id"),
            duration_minutes=serializer.validated_data["duration_minutes"],
            session_type=serializer.validated_data.get("session_type", "work"),
        )
        return Response(
            FocusSessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )


class FocusSessionCompleteView(APIView):
    """Complete a focus session."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Complete focus session",
        tags=["Plans"],
        request=FocusSessionCompleteSerializer,
        responses={200: FocusSessionSerializer},
    )
    def post(self, request):
        serializer = FocusSessionCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            session = FocusSession.objects.get(
                id=serializer.validated_data["session_id"],
                user=request.user,
            )
        except FocusSession.DoesNotExist:
            return Response(
                {"error": "Session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        session.actual_minutes = serializer.validated_data["actual_minutes"]
        session.completed = True
        session.ended_at = timezone.now()
        session.save()

        # Award XP for focus session
        xp_amount = max(5, session.actual_minutes // 5)
        request.user.add_xp(xp_amount)

        from apps.gamification.models import DailyActivity

        DailyActivity.record_task_completion(
            user=request.user,
            xp_earned=xp_amount,
            duration_mins=session.actual_minutes,
        )

        return Response(FocusSessionSerializer(session).data)


class FocusSessionHistoryView(APIView):
    """List recent focus sessions."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Focus session history",
        tags=["Plans"],
        responses={200: FocusSessionSerializer(many=True)},
    )
    def get(self, request):
        sessions = FocusSession.objects.filter(user=request.user)[:20]
        return Response(FocusSessionSerializer(sessions, many=True).data)


class FocusSessionStatsView(APIView):
    """Weekly focus statistics."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Focus session stats",
        tags=["Plans"],
        responses={200: dict},
    )
    def get(self, request):
        from datetime import date, timedelta

        today = date.today()
        week_start = today - timedelta(days=6)

        sessions = FocusSession.objects.filter(
            user=request.user,
            completed=True,
            started_at__date__gte=week_start,
        )

        total_minutes = sum(s.actual_minutes for s in sessions)
        total_sessions = sessions.count()

        return Response(
            {
                "total_sessions": total_sessions,
                "total_minutes": total_minutes,
                "average_minutes": round(total_minutes / total_sessions, 1)
                if total_sessions
                else 0,
            }
        )
