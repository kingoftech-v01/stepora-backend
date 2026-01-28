"""
Views for Dreams app.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Dream, Goal, Task, Obstacle
from .serializers import (
    DreamSerializer, DreamDetailSerializer, DreamCreateSerializer, DreamUpdateSerializer,
    GoalSerializer, GoalCreateSerializer,
    TaskSerializer, TaskCreateSerializer,
    ObstacleSerializer
)
from core.permissions import IsOwner, CanCreateDream
from integrations.openai_service import OpenAIService
from core.exceptions import OpenAIError


class DreamViewSet(viewsets.ModelViewSet):
    """CRUD operations for dreams."""

    permission_classes = [IsAuthenticated, IsOwner]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'category']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'target_date', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        """Get dreams for current user."""
        return Dream.objects.filter(user=self.request.user).prefetch_related(
            'goals__tasks'
        )

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return DreamCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DreamUpdateSerializer
        elif self.action == 'retrieve':
            return DreamDetailSerializer
        return DreamSerializer

    def get_permissions(self):
        """Get permissions based on action."""
        if self.action == 'create':
            return [IsAuthenticated(), CanCreateDream()]
        return super().get_permissions()

    def perform_create(self, serializer):
        """Create dream with current user."""
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def analyze(self, request, pk=None):
        """Analyze dream with AI."""
        dream = self.get_object()
        ai_service = OpenAIService()

        try:
            analysis = ai_service.analyze_dream(
                dream.title,
                dream.description
            )

            # Save analysis
            dream.ai_analysis = analysis
            dream.save(update_fields=['ai_analysis'])

            return Response(analysis)

        except OpenAIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def generate_plan(self, request, pk=None):
        """Generate complete plan for dream with AI."""
        dream = self.get_object()
        ai_service = OpenAIService()

        user_context = {
            'timezone': dream.user.timezone,
            'work_schedule': dream.user.work_schedule or {},
        }

        try:
            # Generate plan with AI
            plan = ai_service.generate_plan(
                dream.title,
                dream.description,
                user_context
            )

            # Save AI analysis
            dream.ai_analysis = plan
            dream.save(update_fields=['ai_analysis'])

            # Create Goals and Tasks from plan
            for goal_data in plan.get('goals', []):
                goal = Goal.objects.create(
                    dream=dream,
                    title=goal_data['title'],
                    description=goal_data.get('description', ''),
                    order=goal_data['order'],
                    estimated_minutes=goal_data.get('estimated_minutes')
                )

                # Create tasks for this goal
                for task_data in goal_data.get('tasks', []):
                    Task.objects.create(
                        goal=goal,
                        title=task_data['title'],
                        description=task_data.get('description', ''),
                        order=task_data['order'],
                        duration_mins=task_data.get('duration_mins', 30)
                    )

            # Create obstacles
            for obstacle_data in plan.get('potential_obstacles', []):
                Obstacle.objects.create(
                    dream=dream,
                    title=obstacle_data['title'],
                    description=obstacle_data.get('title', ''),
                    solution=obstacle_data.get('solution', ''),
                    obstacle_type='predicted'
                )

            return Response(DreamDetailSerializer(dream).data)

        except OpenAIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def generate_two_minute_start(self, request, pk=None):
        """Generate 2-minute start task for dream."""
        dream = self.get_object()

        if dream.has_two_minute_start:
            return Response(
                {'message': '2-minute start already generated'},
                status=status.HTTP_400_BAD_REQUEST
            )

        ai_service = OpenAIService()

        try:
            micro_action = ai_service.generate_two_minute_start(
                dream.title,
                dream.description
            )

            # Get first goal or create one
            first_goal = dream.goals.order_by('order').first()
            if not first_goal:
                first_goal = Goal.objects.create(
                    dream=dream,
                    title="Getting Started",
                    description="Initial steps to begin your journey",
                    order=0
                )

            # Create 2-minute task
            Task.objects.create(
                goal=first_goal,
                title=f"🚀 Start: {micro_action}",
                duration_mins=2,
                order=0,
                is_two_minute_start=True
            )

            dream.has_two_minute_start = True
            dream.save(update_fields=['has_two_minute_start'])

            return Response(DreamDetailSerializer(dream).data)

        except OpenAIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def generate_vision(self, request, pk=None):
        """Generate vision board image for dream."""
        dream = self.get_object()
        ai_service = OpenAIService()

        try:
            image_url = ai_service.generate_vision_image(
                dream.title,
                dream.description
            )

            dream.vision_image_url = image_url
            dream.save(update_fields=['vision_image_url'])

            return Response({'image_url': image_url})

        except OpenAIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark dream as completed."""
        dream = self.get_object()
        dream.complete()

        return Response(DreamSerializer(dream).data)


class GoalViewSet(viewsets.ModelViewSet):
    """CRUD operations for goals."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['order', 'created_at']
    ordering = ['order']

    def get_queryset(self):
        """Get goals for current user's dreams."""
        dream_id = self.request.query_params.get('dream')
        queryset = Goal.objects.filter(dream__user=self.request.user).prefetch_related('tasks')

        if dream_id:
            queryset = queryset.filter(dream_id=dream_id)

        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action == 'create':
            return GoalCreateSerializer
        return GoalSerializer

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark goal as completed."""
        goal = self.get_object()
        goal.complete()

        return Response(GoalSerializer(goal).data)


class TaskViewSet(viewsets.ModelViewSet):
    """CRUD operations for tasks."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['order', 'scheduled_date', 'created_at']
    ordering = ['scheduled_date', 'order']

    def get_queryset(self):
        """Get tasks for current user."""
        goal_id = self.request.query_params.get('goal')
        queryset = Task.objects.filter(goal__dream__user=self.request.user)

        if goal_id:
            queryset = queryset.filter(goal_id=goal_id)

        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action == 'create':
            return TaskCreateSerializer
        return TaskSerializer

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark task as completed."""
        task = self.get_object()
        task.complete()

        return Response(TaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def skip(self, request, pk=None):
        """Skip a task."""
        task = self.get_object()
        task.status = 'skipped'
        task.save()

        return Response(TaskSerializer(task).data)


class ObstacleViewSet(viewsets.ModelViewSet):
    """CRUD operations for obstacles."""

    permission_classes = [IsAuthenticated]
    serializer_class = ObstacleSerializer

    def get_queryset(self):
        """Get obstacles for current user's dreams."""
        dream_id = self.request.query_params.get('dream')
        queryset = Obstacle.objects.filter(dream__user=self.request.user)

        if dream_id:
            queryset = queryset.filter(dream_id=dream_id)

        return queryset

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Mark obstacle as resolved."""
        obstacle = self.get_object()
        obstacle.status = 'resolved'
        obstacle.save()

        return Response(ObstacleSerializer(obstacle).data)
