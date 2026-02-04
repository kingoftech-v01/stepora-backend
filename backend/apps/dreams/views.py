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
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse

from .models import Dream, Goal, Task, Obstacle, CalibrationResponse
from .serializers import (
    DreamSerializer, DreamDetailSerializer, DreamCreateSerializer, DreamUpdateSerializer,
    GoalSerializer, GoalCreateSerializer,
    TaskSerializer, TaskCreateSerializer,
    ObstacleSerializer, CalibrationResponseSerializer
)
from core.permissions import IsOwner, CanCreateDream
from integrations.openai_service import OpenAIService
from core.exceptions import OpenAIError


@extend_schema_view(
    list=extend_schema(summary="List dreams", description="Get all dreams for the current user", tags=["Dreams"]),
    create=extend_schema(summary="Create dream", description="Create a new dream", tags=["Dreams"]),
    retrieve=extend_schema(summary="Get dream", description="Get a specific dream with details", tags=["Dreams"]),
    update=extend_schema(summary="Update dream", description="Update a dream", tags=["Dreams"]),
    partial_update=extend_schema(summary="Partial update dream", description="Partially update a dream", tags=["Dreams"]),
    destroy=extend_schema(summary="Delete dream", description="Delete a dream", tags=["Dreams"]),
)
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

    @extend_schema(summary="Analyze dream", description="Analyze a dream using AI to get insights", tags=["Dreams"], responses={200: dict})
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

    @extend_schema(summary="Start calibration", description="Generate initial calibration questions for a dream", tags=["Dreams"], responses={200: dict})
    @action(detail=True, methods=['post'])
    def start_calibration(self, request, pk=None):
        """Generate initial calibration questions (7 questions) for the dream."""
        dream = self.get_object()
        ai_service = OpenAIService()

        # Check if calibration already completed
        if dream.calibration_status == 'completed':
            return Response(
                {'message': 'Calibration already completed for this dream'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Generate initial batch of 7 questions
            result = ai_service.generate_calibration_questions(
                dream.title,
                dream.description,
                batch_size=7
            )

            # Save questions to database
            questions_created = []
            for i, q_data in enumerate(result.get('questions', []), start=1):
                cr = CalibrationResponse.objects.create(
                    dream=dream,
                    question=q_data['question'],
                    question_number=i,
                    category=q_data.get('category', '')
                )
                questions_created.append(cr)

            # Update dream calibration status
            dream.calibration_status = 'in_progress'
            dream.save(update_fields=['calibration_status'])

            return Response({
                'status': 'in_progress',
                'questions': CalibrationResponseSerializer(questions_created, many=True).data,
                'total_questions': len(questions_created),
                'answered': 0,
            })

        except OpenAIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(summary="Answer calibration", description="Submit answers to calibration questions and get follow-ups if needed", tags=["Dreams"], responses={200: dict})
    @action(detail=True, methods=['post'])
    def answer_calibration(self, request, pk=None):
        """
        Submit answers to calibration questions.

        Expects: { "answers": [{ "question_id": "uuid", "answer": "text" }, ...] }

        Returns either more questions or marks calibration as complete.
        """
        dream = self.get_object()
        answers_data = request.data.get('answers', [])

        if not answers_data:
            return Response(
                {'error': 'No answers provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save answers
        for ans in answers_data:
            try:
                cr = CalibrationResponse.objects.get(
                    id=ans['question_id'],
                    dream=dream
                )
                cr.answer = ans['answer']
                cr.save(update_fields=['answer'])
            except CalibrationResponse.DoesNotExist:
                continue

        # Get all Q&A pairs so far
        all_qa = list(
            CalibrationResponse.objects.filter(
                dream=dream,
                answer__gt=''
            ).order_by('question_number').values('question', 'answer')
        )

        total_questions = CalibrationResponse.objects.filter(dream=dream).count()
        answered_count = len(all_qa)

        # If we've reached 15 questions, force complete
        if total_questions >= 15:
            dream.calibration_status = 'completed'
            dream.save(update_fields=['calibration_status'])

            return Response({
                'status': 'completed',
                'total_questions': total_questions,
                'answered': answered_count,
                'message': 'Calibration complete. Ready to generate your personalized plan.',
            })

        # Ask AI if we have enough info or need more questions
        ai_service = OpenAIService()

        try:
            remaining_capacity = 15 - total_questions
            batch_size = min(remaining_capacity, 4)  # Follow-up batches of up to 4

            result = ai_service.generate_calibration_questions(
                dream.title,
                dream.description,
                existing_qa=all_qa,
                batch_size=batch_size
            )

            if result.get('sufficient', False) or not result.get('questions'):
                # AI says we have enough info
                dream.calibration_status = 'completed'
                dream.save(update_fields=['calibration_status'])

                return Response({
                    'status': 'completed',
                    'total_questions': total_questions,
                    'answered': answered_count,
                    'confidence_score': result.get('confidence_score', 1.0),
                    'message': 'Calibration complete. Ready to generate your personalized plan.',
                })
            else:
                # Save new follow-up questions
                new_questions = []
                start_number = total_questions + 1
                for i, q_data in enumerate(result.get('questions', [])):
                    cr = CalibrationResponse.objects.create(
                        dream=dream,
                        question=q_data['question'],
                        question_number=start_number + i,
                        category=q_data.get('category', '')
                    )
                    new_questions.append(cr)

                new_total = total_questions + len(new_questions)

                return Response({
                    'status': 'in_progress',
                    'questions': CalibrationResponseSerializer(new_questions, many=True).data,
                    'total_questions': new_total,
                    'answered': answered_count,
                    'confidence_score': result.get('confidence_score', 0.5),
                    'missing_areas': result.get('missing_areas', []),
                })

        except OpenAIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(summary="Skip calibration", description="Skip the calibration step and use basic info for plan generation", tags=["Dreams"], responses={200: dict})
    @action(detail=True, methods=['post'])
    def skip_calibration(self, request, pk=None):
        """Allow user to skip calibration and proceed with basic info."""
        dream = self.get_object()
        dream.calibration_status = 'skipped'
        dream.save(update_fields=['calibration_status'])

        return Response({
            'status': 'skipped',
            'message': 'Calibration skipped. You can generate a plan with basic info.',
        })

    @extend_schema(summary="Generate plan", description="Generate a complete AI-powered plan with goals and tasks, using calibration data if available", tags=["Dreams"], responses={200: DreamDetailSerializer})
    @action(detail=True, methods=['post'])
    def generate_plan(self, request, pk=None):
        """Generate complete plan for dream with AI, enriched by calibration data."""
        dream = self.get_object()
        ai_service = OpenAIService()

        user_context = {
            'timezone': dream.user.timezone,
            'work_schedule': dream.user.work_schedule or {},
        }

        # If calibration was completed, build rich context from Q&A
        calibration_context = None
        if dream.calibration_status == 'completed':
            qa_pairs = list(
                CalibrationResponse.objects.filter(
                    dream=dream,
                    answer__gt=''
                ).order_by('question_number').values('question', 'answer')
            )

            if qa_pairs:
                try:
                    calibration_context = ai_service.generate_calibration_summary(
                        dream.title,
                        dream.description,
                        qa_pairs
                    )
                    # Store the calibration summary in ai_analysis
                    user_context['calibration_profile'] = calibration_context.get('user_profile', {})
                    user_context['plan_recommendations'] = calibration_context.get('plan_recommendations', {})
                    # Use enriched description if available
                    enriched = calibration_context.get('enriched_description', '')
                    if enriched:
                        user_context['enriched_description'] = enriched
                except OpenAIError:
                    pass  # Fall back to basic plan generation

        try:
            # Generate plan with AI (now with calibration context)
            plan = ai_service.generate_plan(
                dream.title,
                dream.description,
                user_context
            )

            # Save AI analysis (include calibration summary)
            analysis_data = plan
            if calibration_context:
                analysis_data['calibration_summary'] = calibration_context
            dream.ai_analysis = analysis_data
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

    @extend_schema(summary="Generate 2-minute start", description="Generate a micro-action to start working on the dream in 2 minutes", tags=["Dreams"], responses={200: DreamDetailSerializer})
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

    @extend_schema(summary="Generate vision board", description="Generate a vision board image using DALL-E", tags=["Dreams"], responses={200: dict})
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

    @extend_schema(summary="Complete dream", description="Mark a dream as completed", tags=["Dreams"], responses={200: DreamSerializer})
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark dream as completed."""
        dream = self.get_object()
        dream.complete()

        return Response(DreamSerializer(dream).data)


@extend_schema_view(
    list=extend_schema(summary="List goals", description="Get all goals for the current user", tags=["Goals"]),
    create=extend_schema(summary="Create goal", description="Create a new goal", tags=["Goals"]),
    retrieve=extend_schema(summary="Get goal", description="Get a specific goal", tags=["Goals"]),
    update=extend_schema(summary="Update goal", description="Update a goal", tags=["Goals"]),
    partial_update=extend_schema(summary="Partial update goal", description="Partially update a goal", tags=["Goals"]),
    destroy=extend_schema(summary="Delete goal", description="Delete a goal", tags=["Goals"]),
)
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

    @extend_schema(summary="Complete goal", description="Mark a goal as completed", tags=["Goals"], responses={200: GoalSerializer})
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark goal as completed."""
        goal = self.get_object()
        goal.complete()

        return Response(GoalSerializer(goal).data)


@extend_schema_view(
    list=extend_schema(summary="List tasks", description="Get all tasks for the current user", tags=["Tasks"]),
    create=extend_schema(summary="Create task", description="Create a new task", tags=["Tasks"]),
    retrieve=extend_schema(summary="Get task", description="Get a specific task", tags=["Tasks"]),
    update=extend_schema(summary="Update task", description="Update a task", tags=["Tasks"]),
    partial_update=extend_schema(summary="Partial update task", description="Partially update a task", tags=["Tasks"]),
    destroy=extend_schema(summary="Delete task", description="Delete a task", tags=["Tasks"]),
)
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

    @extend_schema(summary="Complete task", description="Mark a task as completed and earn XP", tags=["Tasks"], responses={200: TaskSerializer})
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark task as completed."""
        task = self.get_object()
        task.complete()

        return Response(TaskSerializer(task).data)

    @extend_schema(summary="Skip task", description="Skip a task without completing it", tags=["Tasks"], responses={200: TaskSerializer})
    @action(detail=True, methods=['post'])
    def skip(self, request, pk=None):
        """Skip a task."""
        task = self.get_object()
        task.status = 'skipped'
        task.save()

        return Response(TaskSerializer(task).data)


@extend_schema_view(
    list=extend_schema(summary="List obstacles", description="Get all obstacles for the current user", tags=["Obstacles"]),
    create=extend_schema(summary="Create obstacle", description="Create a new obstacle", tags=["Obstacles"]),
    retrieve=extend_schema(summary="Get obstacle", description="Get a specific obstacle", tags=["Obstacles"]),
    update=extend_schema(summary="Update obstacle", description="Update an obstacle", tags=["Obstacles"]),
    partial_update=extend_schema(summary="Partial update obstacle", description="Partially update an obstacle", tags=["Obstacles"]),
    destroy=extend_schema(summary="Delete obstacle", description="Delete an obstacle", tags=["Obstacles"]),
)
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

    @extend_schema(summary="Resolve obstacle", description="Mark an obstacle as resolved", tags=["Obstacles"], responses={200: ObstacleSerializer})
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Mark obstacle as resolved."""
        obstacle = self.get_object()
        obstacle.status = 'resolved'
        obstacle.save()

        return Response(ObstacleSerializer(obstacle).data)
