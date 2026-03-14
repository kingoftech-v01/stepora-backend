"""
Views for Dreams app.
"""

import logging
import uuid

import requests as http_requests
from django.db.models import Max

logger = logging.getLogger(__name__)

from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, status, views, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.ai_usage import AIUsageTracker
from core.ai_validators import (
    AIValidationError,
    validate_analysis_response,
    validate_calibration_questions,
    validate_smart_analysis_response,
)
from core.exceptions import OpenAIError
from core.openapi_examples import (
    DREAM_ANALYZE_RESPONSE,
    DREAM_CREATE_REQUEST,
    DREAM_LIST_RESPONSE,
    GOAL_CREATE_REQUEST,
)
from core.permissions import CanCreateDream, CanUseAI, CanUseVisionBoard, IsOwner
from core.throttles import (
    AICalibrationDailyThrottle,
    AICalibrationRateThrottle,
    AIImageDailyThrottle,
    AIPlanDailyThrottle,
    AIPlanRateThrottle,
)
from integrations.openai_service import OpenAIService

from .models import (
    CalibrationResponse,
    Dream,
    DreamCollaborator,
    DreamJournal,
    DreamMilestone,
    DreamProgressSnapshot,
    DreamTag,
    DreamTagging,
    DreamTemplate,
    FocusSession,
    Goal,
    Obstacle,
    PlanCheckIn,
    ProgressPhoto,
    SharedDream,
    Task,
    VisionBoardImage,
)
from .serializers import (
    AddCollaboratorSerializer,
    AddTagSerializer,
    CalibrationResponseSerializer,
    DreamCollaboratorSerializer,
    DreamCreateSerializer,
    DreamDetailSerializer,
    DreamJournalSerializer,
    DreamMilestoneSerializer,
    DreamSerializer,
    DreamTagSerializer,
    DreamTemplateSerializer,
    DreamUpdateSerializer,
    FocusSessionCompleteSerializer,
    FocusSessionSerializer,
    FocusSessionStartSerializer,
    GoalCreateSerializer,
    GoalSerializer,
    ObstacleSerializer,
    ProgressPhotoSerializer,
    SharedDreamSerializer,
    ShareDreamRequestSerializer,
    TaskCreateSerializer,
    TaskSerializer,
    VisionBoardImageSerializer,
    PlanCheckInSerializer,
    PlanCheckInDetailSerializer,
    CheckInResponseSubmitSerializer,
)
from integrations.plan_processors import detect_category_with_ambiguity


@extend_schema_view(
    list=extend_schema(
        summary="List dreams",
        description="Get all dreams for the current user",
        tags=["Dreams"],
        responses={200: DreamSerializer(many=True)},
        examples=[DREAM_LIST_RESPONSE],
    ),
    create=extend_schema(
        summary="Create dream",
        description="Create a new dream",
        tags=["Dreams"],
        responses={
            201: DreamSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
        examples=[DREAM_CREATE_REQUEST],
    ),
    retrieve=extend_schema(
        summary="Get dream",
        description="Get a specific dream with details",
        tags=["Dreams"],
        responses={
            200: DreamDetailSerializer,
            404: OpenApiResponse(description="Dream not found."),
        },
    ),
    update=extend_schema(
        summary="Update dream",
        description="Update a dream",
        tags=["Dreams"],
        responses={
            200: DreamUpdateSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Dream not found."),
        },
    ),
    partial_update=extend_schema(
        summary="Partial update dream",
        description="Partially update a dream",
        tags=["Dreams"],
        responses={
            200: DreamUpdateSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Dream not found."),
        },
    ),
    destroy=extend_schema(
        summary="Delete dream",
        description="Delete a dream",
        tags=["Dreams"],
        responses={
            204: OpenApiResponse(description="Dream deleted."),
            404: OpenApiResponse(description="Dream not found."),
        },
    ),
)
class DreamViewSet(viewsets.ModelViewSet):
    """CRUD operations for dreams."""

    permission_classes = [IsAuthenticated, IsOwner]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["status", "category"]
    ordering_fields = ["created_at", "target_date", "priority"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Get dreams for current user, including those they collaborate on.
        For retrieve action, also include public dreams from other users."""
        if getattr(self, "swagger_fake_view", False):
            return Dream.objects.none()
        from django.db.models import Q

        collab_dream_ids = DreamCollaborator.objects.filter(
            user=self.request.user
        ).values_list("dream_id", flat=True)
        from .models import SharedDream

        shared_dream_ids = SharedDream.objects.filter(
            shared_with=self.request.user
        ).values_list("dream_id", flat=True)
        from django.db.models import Count
        from django.db.models import Q as DQ

        # Base filter: own dreams + collaborations + shared
        base_q = (
            Q(user=self.request.user)
            | Q(id__in=collab_dream_ids)
            | Q(id__in=shared_dream_ids)
        )

        # For retrieve, also allow viewing public dreams from anyone
        if self.action == "retrieve":
            base_q = base_q | Q(is_public=True)

        qs = (
            Dream.objects.filter(base_q)
            .prefetch_related(
                "milestones__goals__tasks",
                "milestones__obstacles",
                "goals__tasks",
                "taggings__tag",
            )
            .annotate(
                _milestones_count=Count("milestones", distinct=True),
                _completed_milestones_count=Count(
                    "milestones",
                    filter=DQ(milestones__status="completed"),
                    distinct=True,
                ),
                _goals_count=Count("goals", distinct=True),
                _completed_goals_count=Count(
                    "goals", filter=DQ(goals__status="completed"), distinct=True
                ),
                _total_tasks=Count("goals__tasks", distinct=True),
                _completed_tasks=Count(
                    "goals__tasks",
                    filter=DQ(goals__tasks__status="completed"),
                    distinct=True,
                ),
            )
            .distinct()
        )

        # Elasticsearch-backed search (encrypted fields can't use DB icontains)
        search_query = self.request.query_params.get("search", "").strip()
        if search_query:
            from apps.search.services import SearchService

            dream_ids = SearchService.search_dreams(self.request.user, search_query)
            qs = qs.filter(id__in=dream_ids)

        return qs

    def get_serializer_class(self):
        """Return appropriate serializer based on action.
        For retrieve, use PublicDreamDetailSerializer if viewer is not the owner."""
        if self.action == "create":
            return DreamCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return DreamUpdateSerializer
        elif self.action == "retrieve":
            # Check if the dream belongs to someone else — use public serializer
            obj = self.get_object_for_serializer_check()
            if obj and obj.user != self.request.user:
                from .serializers import PublicDreamDetailSerializer

                return PublicDreamDetailSerializer
            return DreamDetailSerializer
        return DreamSerializer

    def get_object_for_serializer_check(self):
        """Get the object without triggering permission checks (used by get_serializer_class)."""
        try:
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            pk = self.kwargs.get(lookup_url_kwarg)
            if pk:
                return Dream.objects.filter(pk=pk).only("user_id").first()
        except Exception as e:
            logger.warning("get_object_for_serializer_check failed: %s", e)
        return None

    def get_permissions(self):
        """Get permissions based on action — AI and vision features require paid subscriptions.
        For retrieve, allow viewing public dreams without IsOwner check."""
        ai_actions = [
            "analyze",
            "start_calibration",
            "answer_calibration",
            "generate_plan",
            "generate_two_minute_start",
            "predict_obstacles",
            "similar",
            "conversation_starters",
        ]
        vision_ai_actions = ["generate_vision"]
        vision_free_actions = [
            "vision_board_list",
            "vision_board_add",
            "vision_board_remove",
        ]
        if self.action in ai_actions:
            return [IsAuthenticated(), IsOwner(), CanUseAI()]
        if self.action in vision_ai_actions:
            return [IsAuthenticated(), IsOwner(), CanUseVisionBoard()]
        if self.action in vision_free_actions:
            return [IsAuthenticated(), IsOwner()]
        if self.action == "create":
            return [IsAuthenticated(), CanCreateDream()]
        if self.action == "retrieve":
            # Allow any authenticated user to retrieve — queryset handles access
            return [IsAuthenticated()]
        if self.action == "explore":
            return [IsAuthenticated()]
        return super().get_permissions()

    def perform_create(self, serializer):
        """Create dream with current user."""
        serializer.save(user=self.request.user)

    @extend_schema(
        summary="Analyze dream",
        description="Analyze a dream using AI to get insights",
        tags=["Dreams"],
        responses={
            200: dict,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Dream not found."),
            429: OpenApiResponse(description="Rate limit exceeded."),
            500: OpenApiResponse(description="Internal server error."),
            502: OpenApiResponse(description="AI service error."),
        },
        examples=[DREAM_ANALYZE_RESPONSE],
    )
    @action(
        detail=True,
        methods=["post"],
        throttle_classes=[AIPlanRateThrottle, AIPlanDailyThrottle],
    )
    def analyze(self, request, pk=None):
        """Analyze dream with AI."""
        dream = self.get_object()
        ai_service = OpenAIService()

        try:
            raw_analysis = ai_service.analyze_dream(dream.title, dream.description)

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, "ai_plan")

            # Validate AI output before saving
            analysis = validate_analysis_response(raw_analysis)
            analysis_dict = analysis.model_dump()

            # Save validated analysis and update category from AI
            dream.ai_analysis = analysis_dict
            update_fields = ["ai_analysis"]
            if analysis_dict.get("category") and not dream.category:
                dream.category = analysis_dict["category"]
                update_fields.append("category")
            # Store AI-detected language
            if not dream.language and analysis_dict.get("detected_language"):
                dream.language = analysis_dict["detected_language"]
                update_fields.append("language")
            dream.save(update_fields=update_fields)

            return Response(analysis_dict)

        except AIValidationError as e:
            return Response(
                {
                    "error": _("AI produced an invalid analysis: %(msg)s")
                    % {"msg": e.message}
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except OpenAIError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Predict obstacles",
        description="Use AI to predict potential obstacles for a dream and suggest preventive measures",
        tags=["Dreams"],
        responses={
            200: dict,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Dream not found."),
            429: OpenApiResponse(description="Rate limit exceeded."),
            500: OpenApiResponse(description="Internal server error."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="predict-obstacles",
        throttle_classes=[AIPlanRateThrottle, AIPlanDailyThrottle],
    )
    def predict_obstacles(self, request, pk=None):
        """Predict potential obstacles for a dream using AI."""
        dream = self.get_object()
        ai_service = OpenAIService()

        try:
            # Build dream info
            dream_info = {
                "title": dream.title,
                "description": dream.description,
                "category": dream.category,
                "target_date": str(dream.target_date) if dream.target_date else None,
                "progress": dream.progress_percentage,
            }

            # Gather goals data
            goals_data = [
                {
                    "title": g.title,
                    "description": g.description,
                    "status": g.status,
                    "progress": g.progress_percentage,
                }
                for g in dream.goals.all()
            ]

            # Gather tasks data
            tasks_data = [
                {
                    "title": t.title,
                    "status": t.status,
                    "duration_mins": t.duration_mins,
                }
                for g in dream.goals.all()
                for t in g.tasks.all()
            ]

            # Gather existing obstacles
            existing_obstacles = [
                {
                    "title": ob.title,
                    "description": ob.description,
                    "status": ob.status,
                    "type": ob.obstacle_type,
                }
                for ob in dream.obstacles.all()
            ]

            # Gather past obstacle patterns from user's other dreams
            other_obstacles = (
                Obstacle.objects.filter(
                    dream__user=request.user,
                )
                .exclude(dream=dream)
                .select_related("dream")[:30]
            )
            past_patterns = [
                {
                    "obstacle": ob.title,
                    "dream_category": ob.dream.category,
                    "was_resolved": ob.status == "resolved",
                }
                for ob in other_obstacles
            ]

            # Call AI prediction
            result = ai_service.predict_obstacles(
                dream_info=dream_info,
                goals_data=goals_data,
                tasks_data=tasks_data,
                existing_obstacles=existing_obstacles,
                past_patterns=past_patterns,
            )

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, "ai_plan")

            return Response(result)

        except OpenAIError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Get conversation starters",
        description="Generate contextual conversation starters tailored to a dream's current status using AI",
        tags=["Dreams"],
        responses={
            200: dict,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Dream not found."),
            429: OpenApiResponse(description="Rate limit exceeded."),
            500: OpenApiResponse(description="Internal server error."),
            502: OpenApiResponse(description="AI service error."),
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="conversation-starters",
        throttle_classes=[AIPlanRateThrottle, AIPlanDailyThrottle],
    )
    def conversation_starters(self, request, pk=None):
        """Generate contextual conversation starters for a dream."""
        dream = self.get_object()
        ai_service = OpenAIService()

        try:
            # Gather recent tasks (last 5 completed or in-progress)
            recent_tasks = []
            for goal in dream.goals.all()[:5]:
                for task in goal.tasks.order_by("-updated_at")[:3]:
                    recent_tasks.append(
                        {
                            "title": task.title,
                            "status": task.status,
                        }
                    )
            recent_tasks = recent_tasks[:5]

            # Gather active obstacles
            obstacle_data = [
                {
                    "title": ob.title,
                    "status": ob.status,
                }
                for ob in dream.obstacles.filter(status="active")[:5]
            ]

            dream_info = {
                "title": dream.title,
                "description": dream.description,
                "category": dream.category,
                "status": dream.status,
                "progress": dream.progress_percentage,
                "recent_tasks": recent_tasks,
                "obstacles": obstacle_data,
            }

            result = ai_service.generate_starters(dream_info)

            # Track AI usage
            AIUsageTracker().increment(request.user, "ai_chat")

            return Response(result)

        except OpenAIError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Find similar dreams and inspiration",
        description="Find similar public dreams from other users and related templates using AI",
        tags=["Dreams"],
        responses={
            200: dict,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Dream not found."),
            429: OpenApiResponse(description="Rate limit exceeded."),
            500: OpenApiResponse(description="Internal server error."),
            502: OpenApiResponse(description="AI service error."),
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="similar",
        throttle_classes=[AIPlanRateThrottle, AIPlanDailyThrottle],
    )
    def similar(self, request, pk=None):
        """Find similar public dreams and related templates for inspiration."""
        dream = self.get_object()
        ai_service = OpenAIService()

        try:
            # Build source dream info
            source_dream = {
                "title": dream.title,
                "description": dream.description,
                "category": dream.category,
                "progress": dream.progress_percentage,
            }

            # Fetch public dreams from other users (limit 50 most recent)
            public_dreams_qs = (
                Dream.objects.filter(
                    is_public=True,
                )
                .exclude(
                    user=request.user,
                )
                .order_by("-created_at")[:50]
            )

            public_dreams = [
                {
                    "id": str(d.id),
                    "title": d.title,
                    "category": d.category,
                    "progress": d.progress_percentage,
                }
                for d in public_dreams_qs
            ]

            # Fetch available templates
            templates_qs = DreamTemplate.objects.filter(
                is_active=True,
            ).order_by(
                "-is_featured", "-usage_count"
            )[:30]

            templates = [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "description": t.description,
                    "category": t.category,
                    "difficulty": t.difficulty,
                }
                for t in templates_qs
            ]

            # Call AI for similarity matching
            result = ai_service.find_similar_dreams(
                source_dream=source_dream,
                public_dreams=public_dreams,
                templates=templates,
            )

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, "ai_plan")

            return Response(result)

        except OpenAIError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Smart cross-dream analysis",
        description="Analyze all active dreams to find patterns, synergies, insights, and risks using AI",
        tags=["Dreams"],
        responses={
            200: dict,
            400: OpenApiResponse(description="No active dreams to analyze."),
            403: OpenApiResponse(description="Subscription required."),
            429: OpenApiResponse(description="Rate limit exceeded."),
            500: OpenApiResponse(description="Internal server error."),
            502: OpenApiResponse(description="AI service error."),
        },
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="smart-analysis",
        throttle_classes=[AIPlanRateThrottle, AIPlanDailyThrottle],
    )
    def smart_analysis(self, request):
        """Perform AI-powered cross-dream pattern recognition across all user's active dreams."""
        # Fetch all active dreams with related goals and tasks
        dreams = Dream.objects.filter(
            user=request.user,
            status="active",
        ).prefetch_related("goals", "goals__tasks")

        if not dreams.exists():
            return Response(
                {"error": _("You need at least one active dream for smart analysis.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build dreams data payload for AI
        dreams_data = []
        for dream in dreams:
            goals_data = []
            for goal in dream.goals.all():
                tasks_data = []
                for task in goal.tasks.all():
                    tasks_data.append(
                        {
                            "title": task.title,
                            "status": task.status,
                            "order": task.order,
                        }
                    )
                goals_data.append(
                    {
                        "title": goal.title,
                        "description": goal.description,
                        "status": goal.status,
                        "progress": goal.progress_percentage,
                        "tasks": tasks_data,
                    }
                )
            dreams_data.append(
                {
                    "title": dream.title,
                    "description": dream.description,
                    "category": dream.category,
                    "progress": dream.progress_percentage,
                    "status": dream.status,
                    "goals": goals_data,
                }
            )

        ai_service = OpenAIService()

        try:
            raw_result = ai_service.smart_analysis(dreams_data)

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, "ai_plan")

            # Validate AI output
            analysis = validate_smart_analysis_response(raw_result)
            return Response(analysis.model_dump())

        except AIValidationError as e:
            return Response(
                {
                    "error": _("AI produced an invalid smart analysis: %(msg)s")
                    % {"msg": e.message}
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except OpenAIError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Auto-categorize dream",
        description="Use AI to suggest the best category and relevant tags for a dream based on title and description",
        tags=["Dreams"],
        responses={
            200: dict,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Subscription required."),
            429: OpenApiResponse(description="Rate limit exceeded."),
            500: OpenApiResponse(description="Internal server error."),
            502: OpenApiResponse(description="AI service error."),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="auto-categorize",
        permission_classes=[IsAuthenticated, CanUseAI],
        throttle_classes=[AIPlanRateThrottle, AIPlanDailyThrottle],
    )
    def auto_categorize(self, request):
        """Use AI to suggest category and tags for a dream."""
        title = request.data.get("title", "").strip()
        description = request.data.get("description", "").strip()

        if not title or not description:
            return Response(
                {"error": _("Both title and description are required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(description) < 10:
            return Response(
                {"error": _("Description must be at least 10 characters.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ai_service = OpenAIService()

        try:
            result = ai_service.auto_categorize(title, description)

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, "ai_plan")

            return Response(result)

        except OpenAIError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Start calibration",
        description="Generate initial calibration questions for a dream",
        tags=["Dreams"],
        responses={
            200: dict,
            400: OpenApiResponse(description="Calibration already completed."),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Dream not found."),
            429: OpenApiResponse(description="Rate limit exceeded."),
            500: OpenApiResponse(description="Internal server error."),
            502: OpenApiResponse(description="AI service error."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        throttle_classes=[AICalibrationRateThrottle, AICalibrationDailyThrottle],
    )
    def start_calibration(self, request, pk=None):
        """Generate initial calibration questions (7 questions) for the dream."""
        dream = self.get_object()
        ai_service = OpenAIService()

        # Check if calibration already completed
        if dream.calibration_status == "completed":
            return Response(
                {"message": _("Calibration already completed for this dream")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Generate initial batch of 7 questions
            # Get category from dream field or AI analysis
            cat = dream.category
            if not cat and dream.ai_analysis and isinstance(dream.ai_analysis, dict):
                cat = dream.ai_analysis.get("category", "")

            # Check for category ambiguity and generate disambiguation question
            disambiguation_q = None
            if not cat or cat == "other":
                ambiguity = detect_category_with_ambiguity(
                    dream.title, dream.description
                )
                cat = ambiguity["category"]
                if ambiguity["is_ambiguous"]:
                    disambiguation_q = (
                        ai_service.generate_disambiguation_question(
                            dream.title,
                            dream.description,
                            ambiguity["candidates"],
                        )
                    )

            persona = dream.user.persona or {}
            raw_result = ai_service.generate_calibration_questions(
                dream.title,
                dream.description,
                batch_size=7 if not disambiguation_q else 6,
                target_date=str(dream.target_date) if dream.target_date else None,
                category=cat,
                persona=persona,
            )

            # Validate AI output
            result = validate_calibration_questions(raw_result)

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, "ai_plan")

            # Save validated questions to database
            questions_created = []
            q_number = 1

            # Insert disambiguation question first if needed
            if disambiguation_q:
                cr = CalibrationResponse.objects.create(
                    dream=dream,
                    question=disambiguation_q,
                    question_number=q_number,
                    category="specifics",
                )
                questions_created.append(cr)
                q_number += 1

            for q in result.questions:
                cr = CalibrationResponse.objects.create(
                    dream=dream,
                    question=q.question,
                    question_number=q_number,
                    category=q.category,
                )
                questions_created.append(cr)
                q_number += 1

            # Update dream calibration status
            dream.calibration_status = "in_progress"
            dream.save(update_fields=["calibration_status"])

            return Response(
                {
                    "status": "in_progress",
                    "questions": CalibrationResponseSerializer(
                        questions_created, many=True
                    ).data,
                    "total_questions": len(questions_created),
                    "answered": 0,
                }
            )

        except AIValidationError as e:
            return Response(
                {
                    "error": _("AI produced invalid calibration questions: %(msg)s")
                    % {"msg": e.message}
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except OpenAIError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Answer calibration",
        description="Submit answers to calibration questions and get follow-ups if needed",
        tags=["Dreams"],
        responses={
            200: dict,
            400: OpenApiResponse(
                description="Validation error or content moderation flag."
            ),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Dream not found."),
            429: OpenApiResponse(description="Rate limit exceeded."),
            500: OpenApiResponse(description="Internal server error."),
            502: OpenApiResponse(description="AI service error."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        throttle_classes=[AICalibrationRateThrottle, AICalibrationDailyThrottle],
    )
    def answer_calibration(self, request, pk=None):
        """
        Submit answers to calibration questions.

        Expects: { "answers": [{ "question_id": "uuid", "answer": "text" }, ...] }

        Returns either more questions or marks calibration as complete.
        """
        dream = self.get_object()
        answers_data = request.data.get("answers", [])

        # Support single-answer format from frontend:
        # { question: "...", answer: "...", question_number: N }
        if not answers_data:
            single_answer = request.data.get("answer")
            single_question = request.data.get("question")
            question_number = request.data.get("question_number")
            if single_answer and single_question:
                answers_data = [
                    {
                        "question": single_question,
                        "answer": single_answer,
                        "question_number": question_number,
                    }
                ]

        if not answers_data:
            return Response(
                {"error": _("No answers provided")}, status=status.HTTP_400_BAD_REQUEST
            )

        # Moderate and save answers
        from core.moderation import ContentModerationService

        moderation = ContentModerationService()

        for ans in answers_data:
            try:
                answer_text = ans.get("answer", "")
                if not answer_text:
                    continue

                # Moderate each answer
                mod_result = moderation.moderate_text(
                    answer_text, context="calibration_answer"
                )
                if mod_result.is_flagged:
                    return Response(
                        {"error": mod_result.user_message, "moderation": True},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Try by question_id first, then by question_number, then by question text
                question_id = ans.get("question_id")
                question_number = ans.get("question_number")
                question_text = ans.get("question")

                cr = None
                if question_id:
                    cr = CalibrationResponse.objects.filter(
                        id=question_id, dream=dream
                    ).first()
                if not cr and question_number:
                    cr = CalibrationResponse.objects.filter(
                        dream=dream, question_number=question_number
                    ).first()
                if not cr and question_text:
                    cr = CalibrationResponse.objects.filter(
                        dream=dream, question=question_text
                    ).first()
                if not cr:
                    # Create a new calibration response
                    next_num = (
                        CalibrationResponse.objects.filter(dream=dream).count() + 1
                    )
                    cr = CalibrationResponse.objects.create(
                        dream=dream,
                        question=question_text or f"Question {next_num}",
                        question_number=question_number or next_num,
                    )

                cr.answer = answer_text
                cr.save(update_fields=["answer"])
            except (KeyError, ValueError):
                continue

        # Get all Q&A pairs so far
        all_qa = list(
            CalibrationResponse.objects.filter(dream=dream, answer__gt="")
            .order_by("question_number")
            .values("question", "answer")
        )

        total_questions = CalibrationResponse.objects.filter(dream=dream).count()
        answered_count = len(all_qa)

        # If we've reached 25 questions, force complete (increased from 15 for deeper understanding)
        if total_questions >= 25:
            dream.calibration_status = "completed"
            dream.save(update_fields=["calibration_status"])

            return Response(
                {
                    "status": "completed",
                    "total_questions": total_questions,
                    "answered": answered_count,
                    "message": _(
                        "Calibration complete. Ready to generate your personalized plan."
                    ),
                }
            )

        # Server-side guard: force completion after 10+ answered questions
        if answered_count >= 10:
            dream.calibration_status = "completed"
            dream.save(update_fields=["calibration_status"])
            return Response(
                {
                    "status": "completed",
                    "total_questions": total_questions,
                    "answered": answered_count,
                    "confidence_score": min(1.0, answered_count / 10),
                    "message": _(
                        "Calibration complete. Ready to generate your personalized plan."
                    ),
                }
            )

        # Ask AI if we have enough info or need more questions
        ai_service = OpenAIService()

        try:
            remaining_capacity = 25 - total_questions
            batch_size = min(remaining_capacity, 5)  # Follow-up batches of up to 5

            raw_result = ai_service.generate_calibration_questions(
                dream.title,
                dream.description,
                existing_qa=all_qa,
                batch_size=batch_size,
            )

            # Validate AI output
            result = validate_calibration_questions(raw_result)

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, "ai_plan")

            if result.sufficient or not result.questions:
                # AI says we have enough info
                dream.calibration_status = "completed"
                dream.save(update_fields=["calibration_status"])

                return Response(
                    {
                        "status": "completed",
                        "total_questions": total_questions,
                        "answered": answered_count,
                        "confidence_score": result.confidence_score,
                        "message": _(
                            "Calibration complete. Ready to generate your personalized plan."
                        ),
                    }
                )
            else:
                # Save validated follow-up questions
                new_questions = []
                start_number = total_questions + 1
                for i, q in enumerate(result.questions):
                    cr = CalibrationResponse.objects.create(
                        dream=dream,
                        question=q.question,
                        question_number=start_number + i,
                        category=q.category,
                    )
                    new_questions.append(cr)

                new_total = total_questions + len(new_questions)

                return Response(
                    {
                        "status": "in_progress",
                        "questions": CalibrationResponseSerializer(
                            new_questions, many=True
                        ).data,
                        "total_questions": new_total,
                        "answered": answered_count,
                        "confidence_score": result.confidence_score,
                        "missing_areas": result.missing_areas,
                    }
                )

        except AIValidationError as e:
            return Response(
                {
                    "error": _("AI produced invalid follow-up questions: %(msg)s")
                    % {"msg": e.message}
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except OpenAIError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Skip calibration",
        description="Skip the calibration step and use basic info for plan generation",
        tags=["Dreams"],
        responses={
            200: dict,
            404: OpenApiResponse(description="Dream not found."),
        },
    )
    @action(detail=True, methods=["post"])
    def skip_calibration(self, request, pk=None):
        """Allow user to skip calibration and proceed with basic info."""
        dream = self.get_object()
        dream.calibration_status = "skipped"
        dream.save(update_fields=["calibration_status"])

        return Response(
            {
                "status": "skipped",
                "message": _(
                    "Calibration skipped. You can generate a plan with basic info."
                ),
            }
        )

    @extend_schema(
        summary="Generate plan",
        description="Dispatch AI plan generation as a background task. Returns 202 with status URL to poll.",
        tags=["Dreams"],
        responses={
            202: OpenApiResponse(description="Plan generation started."),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Dream not found."),
            429: OpenApiResponse(description="Rate limit exceeded."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        throttle_classes=[AIPlanRateThrottle, AIPlanDailyThrottle],
    )
    def generate_plan(self, request, pk=None):
        """Dispatch adaptive plan generation (skeleton + initial tasks) as Celery background tasks."""
        from .tasks import generate_dream_skeleton_task, set_plan_status

        dream = self.get_object()

        # Check if already generating
        from .tasks import get_plan_status

        current = get_plan_status(str(dream.id))
        if current and current.get("status") == "generating":
            return Response(
                {
                    "status": "generating",
                    "message": current.get("message", _("Plan is being generated...")),
                },
                status=status.HTTP_202_ACCEPTED,
            )

        # Dispatch skeleton generation (chains to initial tasks automatically)
        set_plan_status(
            str(dream.id), "generating", message="Starting plan generation..."
        )
        generate_dream_skeleton_task.apply_async(
            args=[str(dream.id), str(request.user.id)], queue="dreams"
        )

        logger.info(f"generate_plan: dispatched skeleton task for dream={dream.id}")
        return Response(
            {
                "status": "generating",
                "message": _("Plan generation started. This may take a few minutes."),
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        summary="Plan generation status",
        description="Poll for the status of a background plan generation task.",
        tags=["Dreams"],
        responses={200: dict},
    )
    @action(detail=True, methods=["get"])
    def plan_status(self, request, pk=None):
        """Check the status of plan generation for a dream."""
        from .tasks import get_plan_status

        dream = self.get_object()
        status_data = get_plan_status(str(dream.id))

        if not status_data:
            # No generation in progress — check if dream already has milestones
            has_plan = (
                DreamMilestone.objects.filter(dream=dream).exists()
                or Goal.objects.filter(dream=dream).exists()
            )
            if has_plan:
                return Response(
                    {"status": "completed", "message": _("Plan already exists.")}
                )
            return Response(
                {"status": "idle", "message": _("No plan generation in progress.")}
            )

        return Response(status_data)

    @extend_schema(
        summary="Generate 2-minute start",
        description="Generate a micro-action to start working on the dream in 2 minutes",
        tags=["Dreams"],
        responses={
            200: DreamDetailSerializer,
            400: OpenApiResponse(description="2-minute start already generated."),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Dream not found."),
            429: OpenApiResponse(description="Rate limit exceeded."),
            500: OpenApiResponse(description="Internal server error."),
        },
    )
    @action(detail=True, methods=["post"], throttle_classes=[AIPlanDailyThrottle])
    def generate_two_minute_start(self, request, pk=None):
        """Generate 2-minute start task for dream."""
        dream = self.get_object()

        if dream.has_two_minute_start:
            return Response(
                {"message": _("2-minute start already generated")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ai_service = OpenAIService()

        try:
            micro_action = ai_service.generate_two_minute_start(
                dream.title, dream.description
            )

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, "ai_plan")

            # Get first goal or create one
            first_goal = dream.goals.order_by("order").first()
            if not first_goal:
                first_goal = Goal.objects.create(
                    dream=dream,
                    title=_("Getting Started"),
                    description=_("Initial steps to begin your journey"),
                    order=0,
                )

            # Create 2-minute task
            Task.objects.create(
                goal=first_goal,
                title=_("Start now: %(action)s") % {"action": micro_action},
                duration_mins=2,
                order=0,
                is_two_minute_start=True,
            )

            dream.has_two_minute_start = True
            dream.save(update_fields=["has_two_minute_start"])

            return Response(DreamDetailSerializer(dream).data)

        except OpenAIError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Generate vision board",
        description="Generate a vision board image using DALL-E",
        tags=["Dreams"],
        responses={
            200: dict,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Dream not found."),
            429: OpenApiResponse(description="Rate limit exceeded."),
            500: OpenApiResponse(description="Internal server error."),
        },
    )
    @action(detail=True, methods=["post"], throttle_classes=[AIImageDailyThrottle])
    def generate_vision(self, request, pk=None):
        """Generate vision board image for dream."""
        dream = self.get_object()
        ai_service = OpenAIService()

        try:
            # Gather rich context for a more realistic, personalized image
            milestone_titles = list(
                dream.milestones.order_by("order").values_list("title", flat=True)
            )
            calibration_profile = None
            if dream.ai_analysis and isinstance(dream.ai_analysis, dict):
                cal_summary = dream.ai_analysis.get("calibration_summary", {})
                calibration_profile = (
                    cal_summary.get("user_profile")
                    if isinstance(cal_summary, dict)
                    else None
                )

            image_url = ai_service.generate_vision_image(
                dream.title,
                dream.description,
                category=dream.category,
                milestones=milestone_titles,
                calibration_profile=calibration_profile,
            )

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, "ai_image")

            # Download the image from OpenAI (temporary URL, expires in ~1 hour)
            # and save it as a local file so it persists permanently.
            saved_image_file = None
            try:
                resp = http_requests.get(image_url, timeout=60)
                resp.raise_for_status()
                from django.core.files.base import ContentFile

                filename = f"vision_{dream.id}_{uuid.uuid4().hex[:8]}.png"
                saved_image_file = ContentFile(resp.content, name=filename)
            except Exception as dl_err:
                logger.warning(
                    f"Failed to download vision image for dream {dream.id}: {dl_err}"
                )

            # Create vision board image entry with the local file
            vbi = VisionBoardImage(
                dream=dream,
                caption=_('AI-generated vision for "%(title)s"')
                % {"title": dream.title},
                is_ai_generated=True,
                order=dream.vision_images.count(),
            )
            if saved_image_file:
                vbi.image_file.save(saved_image_file.name, saved_image_file, save=False)
            else:
                # Fallback: store the temporary URL (will expire)
                vbi.image_url = image_url
            vbi.save()

            # Build the permanent URL for the saved image
            if vbi.image_file:
                url = vbi.image_file.url
                # S3 URLs are already absolute; local dev needs host prefix
                permanent_url = url if url.startswith(("http://", "https://")) else request.build_absolute_uri(url)
            else:
                permanent_url = image_url

            dream.vision_image_url = permanent_url
            dream.save(update_fields=["vision_image_url"])

            return Response({"image_url": permanent_url})

        except OpenAIError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Vision board list",
        description="List vision board images for a dream",
        tags=["Dreams"],
        responses={
            200: VisionBoardImageSerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Dream not found."),
        },
    )
    @action(detail=True, methods=["get"], url_path="vision-board")
    def vision_board_list(self, request, pk=None):
        """List all vision board images for a dream."""
        dream = self.get_object()
        images = dream.vision_images.all()
        return Response({"images": VisionBoardImageSerializer(images, many=True).data})

    @extend_schema(
        summary="Add vision board image",
        description="Add an image to the vision board",
        tags=["Dreams"],
        responses={
            201: VisionBoardImageSerializer,
            400: OpenApiResponse(
                description="Validation error — image file or URL required."
            ),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Dream not found."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="vision-board/add",
        parser_classes=[MultiPartParser, FormParser],
    )
    def vision_board_add(self, request, pk=None):
        """Add an image to the dream's vision board."""
        dream = self.get_object()

        image_file = request.FILES.get("image")
        image_url = request.data.get("image_url", "")
        caption = request.data.get("caption", "")

        if not image_file and not image_url:
            return Response(
                {"error": _("Provide image file or image_url.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate uploaded image file type and size
        if image_file:
            ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
            content_type = getattr(image_file, "content_type", "")
            if content_type not in ALLOWED_IMAGE_TYPES:
                return Response(
                    {
                        "error": _(
                            "Unsupported image format. Allowed: JPEG, PNG, WebP, GIF."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if image_file.size > 10 * 1024 * 1024:
                return Response(
                    {"error": _("Image file too large. Max 10MB.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Validate magic bytes
            header = image_file.read(12)
            image_file.seek(0)
            valid_magic = (
                header[:3] == b"\xff\xd8\xff"  # JPEG
                or header[:8] == b"\x89PNG\r\n\x1a\n"  # PNG
                or (header[:4] == b"RIFF" and header[8:12] == b"WEBP")  # WebP
                or header[:6] in (b"GIF87a", b"GIF89a")  # GIF
            )
            if not valid_magic:
                return Response(
                    {"error": _("Invalid image file.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Validate URL to prevent SSRF
        if image_url:
            from core.validators import validate_url_no_ssrf

            try:
                validate_url_no_ssrf(
                    image_url
                )  # returns (url, resolved_ip); raises on unsafe
            except Exception:
                return Response(
                    {"error": _("Invalid or unsafe image URL.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        vbi = VisionBoardImage(
            dream=dream,
            caption=caption,
            order=dream.vision_images.count(),
        )
        if image_file:
            vbi.image_file = image_file
        if image_url:
            vbi.image_url = image_url
        vbi.save()

        # Update dream's primary vision image if it doesn't have one yet
        if not dream.vision_image_url:
            if vbi.image_file:
                url = vbi.image_file.url
                dream.vision_image_url = url if url.startswith(("http://", "https://")) else request.build_absolute_uri(url)
            elif vbi.image_url:
                dream.vision_image_url = vbi.image_url
            dream.save(update_fields=["vision_image_url"])

        return Response(
            VisionBoardImageSerializer(vbi).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Remove vision board image",
        description="Remove an image from the vision board",
        tags=["Dreams"],
        responses={
            200: dict,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Image not found."),
        },
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path=r"vision-board/(?P<image_id>[0-9a-f-]+)",
    )
    def vision_board_remove(self, request, pk=None, image_id=None):
        """Remove an image from the dream's vision board."""
        dream = self.get_object()
        deleted, _ = VisionBoardImage.objects.filter(dream=dream, id=image_id).delete()
        if deleted == 0:
            return Response(
                {"error": _("Image not found.")}, status=status.HTTP_404_NOT_FOUND
            )
        return Response({"message": _("Image removed.")})

    # -- Progress Photos ---------------------------------------------------

    @extend_schema(
        summary="List progress photos",
        description="List all progress photos for a dream with AI analyses",
        tags=["Dreams"],
        responses={
            200: ProgressPhotoSerializer(many=True),
            404: OpenApiResponse(description="Dream not found."),
        },
    )
    @action(detail=True, methods=["get"], url_path="progress-photos")
    def progress_photos_list(self, request, pk=None):
        """List all progress photos for a dream."""
        dream = self.get_object()
        photos = dream.progress_photos.all()
        return Response(
            {
                "photos": ProgressPhotoSerializer(
                    photos, many=True, context={"request": request}
                ).data,
            }
        )

    @extend_schema(
        summary="Upload progress photo",
        description="Upload a progress photo for visual tracking",
        tags=["Dreams"],
        responses={
            201: ProgressPhotoSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Dream not found."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="progress-photos/upload",
        parser_classes=[MultiPartParser, FormParser],
    )
    def progress_photos_upload(self, request, pk=None):
        """Upload a progress photo for a dream."""
        dream = self.get_object()

        image_file = request.FILES.get("image")
        if not image_file:
            return Response(
                {"error": _("Image file is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate image file type and size
        ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
        content_type = getattr(image_file, "content_type", "")
        if content_type not in ALLOWED_IMAGE_TYPES:
            return Response(
                {
                    "error": _(
                        "Unsupported image format. Allowed: JPEG, PNG, WebP, GIF."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if image_file.size > 10 * 1024 * 1024:
            return Response(
                {"error": _("Image file too large. Max 10MB.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate magic bytes
        header = image_file.read(12)
        image_file.seek(0)
        valid_magic = (
            header[:2] == b"\xff\xd8"  # JPEG
            or header[:8] == b"\x89PNG\r\n\x1a\n"  # PNG
            or (header[:4] == b"RIFF" and header[8:12] == b"WEBP")  # WebP
            or header[:6] in (b"GIF87a", b"GIF89a")  # GIF
        )
        if not valid_magic:
            return Response(
                {"error": _("Invalid image file.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        caption = request.data.get("caption", "")
        taken_at = request.data.get("taken_at", timezone.now())

        photo = ProgressPhoto.objects.create(
            dream=dream,
            image=image_file,
            caption=caption,
            taken_at=taken_at,
        )

        return Response(
            ProgressPhotoSerializer(photo, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Analyze progress photo",
        description="Trigger AI vision analysis on a progress photo",
        tags=["Dreams"],
        responses={
            200: dict,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Photo not found."),
            429: OpenApiResponse(description="Rate limit exceeded."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path=r"progress-photos/(?P<photo_id>[0-9a-f-]+)/analyze",
        throttle_classes=[AIImageDailyThrottle],
    )
    def progress_photos_analyze(self, request, pk=None, photo_id=None):
        """Analyze a progress photo with AI vision."""
        dream = self.get_object()

        try:
            photo = ProgressPhoto.objects.get(id=photo_id, dream=dream)
        except ProgressPhoto.DoesNotExist:
            return Response(
                {"error": _("Progress photo not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Build the image URL for the AI service
        if photo.image:
            url = photo.image.url
            image_url = url if url.startswith(("http://", "https://")) else request.build_absolute_uri(url)
        else:
            return Response(
                {"error": _("Photo has no image file.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Gather previous analyses for comparison context
        import json as json_module

        previous_photos = (
            dream.progress_photos.filter(
                ai_analysis__isnull=False,
                taken_at__lt=photo.taken_at,
            )
            .exclude(ai_analysis="")
            .order_by("-taken_at")[:3]
        )

        previous_analyses = []
        for prev in previous_photos:
            try:
                parsed = json_module.loads(prev.ai_analysis)
                previous_analyses.append(parsed.get("analysis", prev.ai_analysis))
            except (json_module.JSONDecodeError, TypeError):
                previous_analyses.append(prev.ai_analysis)
        previous_analyses.reverse()  # Chronological order

        ai_service = OpenAIService()

        try:
            result = ai_service.analyze_progress_image(
                image_url=image_url,
                dream_title=dream.title,
                dream_description=dream.description,
                previous_analyses=previous_analyses if previous_analyses else None,
            )

            # Store the analysis as JSON string
            photo.ai_analysis = json_module.dumps(result)
            photo.save(update_fields=["ai_analysis", "updated_at"])

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, "ai_image")

            return Response(
                {
                    "analysis": result,
                    "photo": ProgressPhotoSerializer(
                        photo, context={"request": request}
                    ).data,
                }
            )

        except OpenAIError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Progress history",
        description="Get progress snapshot history for sparkline charts",
        tags=["Dreams"],
        responses={
            200: dict,
            404: OpenApiResponse(description="Dream not found."),
        },
    )
    @action(detail=True, methods=["get"], url_path="progress-history")
    def progress_history(self, request, pk=None):
        """Get progress snapshots for a dream."""
        dream = self.get_object()
        days = int(request.query_params.get("days", 30))
        snapshots = DreamProgressSnapshot.objects.filter(dream=dream).order_by("-date")[
            :days
        ]
        data = list(
            reversed(
                [
                    {"date": str(s.date), "progress": s.progress_percentage}
                    for s in snapshots
                ]
            )
        )
        return Response(
            {"snapshots": data, "current_progress": dream.progress_percentage}
        )

    @extend_schema(
        summary="Dream analytics",
        description="Get comprehensive analytics for a dream including progress history, task stats, weekly activity, category breakdown, and milestones.",
        tags=["Dreams"],
        parameters=[
            OpenApiParameter(
                name="range",
                description="Time range filter: 1w, 1m, 3m, or all",
                required=False,
                type=str,
            ),
        ],
        responses={
            200: dict,
            404: OpenApiResponse(description="Dream not found."),
        },
    )
    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """Get comprehensive analytics for a dream."""
        import datetime

        from django.db.models import Count
        from django.db.models.functions import TruncWeek

        dream = self.get_object()

        # Determine date range filter
        range_param = request.query_params.get("range", "all")
        now = timezone.now()
        range_start = None
        if range_param == "1w":
            range_start = now - datetime.timedelta(weeks=1)
        elif range_param == "1m":
            range_start = now - datetime.timedelta(days=30)
        elif range_param == "3m":
            range_start = now - datetime.timedelta(days=90)
        # 'all' means no filter

        # 1. Progress history from snapshots
        snapshot_qs = DreamProgressSnapshot.objects.filter(dream=dream)
        if range_start:
            snapshot_qs = snapshot_qs.filter(date__gte=range_start.date())
        snapshots = snapshot_qs.order_by("date")
        progress_history = [
            {"date": str(s.date), "progress": round(s.progress_percentage, 1)}
            for s in snapshots
        ]

        # 2. Task stats (across all goals in this dream)
        all_tasks = Task.objects.filter(goal__dream=dream)
        task_stats = {
            "completed": all_tasks.filter(status="completed").count(),
            "in_progress": all_tasks.filter(
                status="pending", goal__status="in_progress"
            ).count(),
            "pending": all_tasks.filter(status="pending")
            .exclude(goal__status="in_progress")
            .count(),
            "skipped": all_tasks.filter(status="skipped").count(),
        }

        # 3. Weekly activity (tasks completed per week)
        completed_tasks_qs = all_tasks.filter(
            status="completed", completed_at__isnull=False
        )
        if range_start:
            completed_tasks_qs = completed_tasks_qs.filter(
                completed_at__gte=range_start
            )
        weekly_data = (
            completed_tasks_qs.annotate(week=TruncWeek("completed_at"))
            .values("week")
            .annotate(tasks_completed=Count("id"))
            .order_by("week")
        )
        weekly_activity = [
            {
                "week": entry["week"].strftime("%Y-W%W"),
                "tasks_completed": entry["tasks_completed"],
            }
            for entry in weekly_data
        ]

        # 4. Category breakdown (percentage of dreams by category for this user)
        user_dreams = Dream.objects.filter(
            user=request.user, status__in=["active", "completed"]
        )
        total_user_dreams = user_dreams.count()
        category_breakdown = {}
        if total_user_dreams > 0:
            cat_counts = (
                user_dreams.values("category")
                .annotate(count=Count("id"))
                .order_by("-count")
            )
            for entry in cat_counts:
                cat_name = entry["category"] or "uncategorized"
                category_breakdown[cat_name] = round(
                    (entry["count"] / total_user_dreams) * 100, 1
                )

        # 5. Milestones (progress milestones — when 25%, 50%, 75% were first reached)
        milestones = []
        thresholds = [25, 50, 75, 100]
        for threshold in thresholds:
            milestone_snapshot = (
                DreamProgressSnapshot.objects.filter(
                    dream=dream, progress_percentage__gte=threshold
                )
                .order_by("date")
                .first()
            )
            if milestone_snapshot:
                milestones.append(
                    {
                        "label": str(threshold) + "%",
                        "date": str(milestone_snapshot.date),
                    }
                )

        return Response(
            {
                "progress_history": progress_history,
                "task_stats": task_stats,
                "weekly_activity": weekly_activity,
                "category_breakdown": category_breakdown,
                "milestones": milestones,
            }
        )

    @extend_schema(
        summary="Complete dream",
        description="Mark a dream as completed",
        tags=["Dreams"],
        responses={
            200: DreamSerializer,
            404: OpenApiResponse(description="Dream not found."),
        },
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Mark dream as completed."""
        dream = self.get_object()
        if dream.status == "completed":
            return Response(
                {"error": _("Dream is already completed.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dream.complete()

        return Response(DreamSerializer(dream).data)

    @extend_schema(
        summary="Toggle dream favorite",
        description="Toggle the is_favorited flag on a dream (for vision board likes).",
        tags=["Dreams"],
        responses={
            200: DreamSerializer,
            404: OpenApiResponse(description="Dream not found."),
        },
    )
    @action(detail=True, methods=["post"])
    def like(self, request, pk=None):
        """Toggle the favorited status of a dream."""
        dream = self.get_object()
        dream.is_favorited = not dream.is_favorited
        dream.save(update_fields=["is_favorited", "updated_at"])
        return Response(DreamSerializer(dream).data)

    @extend_schema(
        summary="Duplicate dream",
        description="Create a deep copy of a dream with all goals and tasks",
        tags=["Dreams"],
        responses={
            201: DreamDetailSerializer,
            404: OpenApiResponse(description="Dream not found."),
        },
    )
    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Deep-copy a dream including goals and tasks."""
        original = self.get_object()

        # Create the dream copy
        new_dream = Dream.objects.create(
            user=request.user,
            title=_("%(title)s (Copy)") % {"title": original.title},
            description=original.description,
            category=original.category,
            target_date=original.target_date,
            priority=original.priority,
            status="active",
        )

        # Copy goals and tasks
        for goal in original.goals.all():
            new_goal = Goal.objects.create(
                dream=new_dream,
                title=goal.title,
                description=goal.description,
                order=goal.order,
                estimated_minutes=goal.estimated_minutes,
                reminder_enabled=goal.reminder_enabled,
            )
            for task in goal.tasks.all():
                Task.objects.create(
                    goal=new_goal,
                    title=task.title,
                    description=task.description,
                    order=task.order,
                    duration_mins=task.duration_mins,
                    recurrence=task.recurrence,
                )

        # Copy tags
        for tagging in original.taggings.all():
            DreamTagging.objects.create(dream=new_dream, tag=tagging.tag)

        return Response(
            DreamDetailSerializer(new_dream).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Share dream",
        description="Share a dream with another user",
        tags=["Dreams"],
        request=ShareDreamRequestSerializer,
        responses={
            201: SharedDreamSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Dream or target user not found."),
        },
    )
    @action(detail=True, methods=["post"])
    def share(self, request, pk=None):
        """Share a dream with another user."""
        dream = self.get_object()
        serializer = ShareDreamRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shared_with_id = serializer.validated_data["shared_with_id"]
        permission = serializer.validated_data.get("permission", "view")

        if shared_with_id == request.user.id:
            return Response(
                {"error": _("You cannot share a dream with yourself.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.users.models import User

        try:
            target_user = User.objects.get(id=shared_with_id)
        except User.DoesNotExist:
            return Response(
                {"error": _("User not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        if SharedDream.objects.filter(dream=dream, shared_with=target_user).exists():
            return Response(
                {"error": _("Dream already shared with this user.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shared = SharedDream.objects.create(
            dream=dream,
            shared_by=request.user,
            shared_with=target_user,
            permission=permission,
        )

        # Notify the recipient
        try:
            from apps.notifications.models import Notification

            Notification.objects.create(
                user=target_user,
                notification_type="progress",
                title=_("%(name)s shared a dream with you!")
                % {"name": request.user.display_name or _("Someone")},
                body=_("You now have access to view this dream."),
                scheduled_for=timezone.now(),
                data={
                    "type": "dream_shared",
                    "dream_id": str(dream.id),
                    "shared_by_id": str(request.user.id),
                },
            )
        except Exception:
            pass  # Don't fail the share if notification fails

        return Response(
            SharedDreamSerializer(shared).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Unshare dream",
        description="Remove sharing of a dream with a user",
        tags=["Dreams"],
        responses={
            200: dict,
            404: OpenApiResponse(description="Share not found."),
        },
    )
    @action(
        detail=True, methods=["delete"], url_path=r"unshare/(?P<user_id>[0-9a-f-]+)"
    )
    def unshare(self, request, pk=None, user_id=None):
        """Remove a dream share."""
        dream = self.get_object()
        deleted_count, _ = SharedDream.objects.filter(
            dream=dream,
            shared_by=request.user,
            shared_with_id=user_id,
        ).delete()

        if deleted_count == 0:
            return Response(
                {"error": _("Share not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        return Response({"message": _("Dream unshared.")})

    @extend_schema(
        summary="Add tag to dream",
        description="Add a tag to a dream",
        tags=["Dreams"],
        request=AddTagSerializer,
        responses={
            200: DreamSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Dream not found."),
        },
    )
    @action(detail=True, methods=["post"], url_path="tags")
    def add_tag(self, request, pk=None):
        """Add a tag to a dream. Creates the tag if it doesn't exist."""
        dream = self.get_object()
        serializer = AddTagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tag_name = serializer.validated_data["tag_name"].strip().lower()
        tag, _ = DreamTag.objects.get_or_create(name=tag_name)

        DreamTagging.objects.get_or_create(dream=dream, tag=tag)

        return Response(DreamSerializer(dream).data)

    @extend_schema(
        summary="Remove tag from dream",
        description="Remove a tag from a dream",
        tags=["Dreams"],
        responses={
            200: dict,
            404: OpenApiResponse(description="Tag not found on this dream."),
        },
    )
    @action(detail=True, methods=["delete"], url_path=r"tags/(?P<tag_name>[^/]+)")
    def remove_tag(self, request, pk=None, tag_name=None):
        """Remove a tag from a dream."""
        dream = self.get_object()
        deleted_count, _ = DreamTagging.objects.filter(
            dream=dream,
            tag__name=tag_name.lower(),
        ).delete()

        if deleted_count == 0:
            return Response(
                {"error": _("Tag not found on this dream.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"message": _("Tag removed.")})

    @extend_schema(
        summary="Add collaborator",
        description="Add a collaborator to a dream. Only the dream owner can add collaborators.",
        request=AddCollaboratorSerializer,
        responses={
            201: DreamCollaboratorSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(
                description="Only the dream owner can add collaborators."
            ),
            404: OpenApiResponse(description="Dream or target user not found."),
        },
        tags=["Dreams"],
    )
    @action(detail=True, methods=["post"], url_path="collaborators")
    def add_collaborator(self, request, pk=None):
        """Add a collaborator to a dream."""
        dream = self.get_object()

        if dream.user != request.user:
            return Response(
                {"error": _("Only the dream owner can add collaborators.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AddCollaboratorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user_id = serializer.validated_data["user_id"]
        role = serializer.validated_data.get("role", "viewer")

        if target_user_id == request.user.id:
            return Response(
                {"error": _("You cannot add yourself as a collaborator.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.users.models import User

        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {"error": _("User not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        if DreamCollaborator.objects.filter(dream=dream, user=target_user).exists():
            return Response(
                {"error": _("User is already a collaborator on this dream.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        collab = DreamCollaborator.objects.create(
            dream=dream,
            user=target_user,
            role=role,
        )

        return Response(
            DreamCollaboratorSerializer(collab).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="List collaborators",
        description="List all collaborators on a dream.",
        responses={
            200: DreamCollaboratorSerializer(many=True),
            404: OpenApiResponse(description="Dream not found."),
        },
        tags=["Dreams"],
    )
    @action(detail=True, methods=["get"], url_path="collaborators/list")
    def list_collaborators(self, request, pk=None):
        """List collaborators on a dream."""
        dream = self.get_object()
        collabs = DreamCollaborator.objects.filter(
            dream=dream,
        ).select_related("user")
        serializer = DreamCollaboratorSerializer(collabs, many=True)
        return Response({"collaborators": serializer.data})

    @extend_schema(
        summary="Remove collaborator",
        description="Remove a collaborator from a dream. Only the owner can remove.",
        responses={
            200: dict,
            403: OpenApiResponse(
                description="Only the dream owner can remove collaborators."
            ),
            404: OpenApiResponse(description="Collaborator not found."),
        },
        tags=["Dreams"],
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path=r"collaborators/(?P<user_id>[0-9a-f-]+)",
    )
    def remove_collaborator(self, request, pk=None, user_id=None):
        """Remove a collaborator from a dream."""
        dream = self.get_object()

        if dream.user != request.user:
            return Response(
                {"error": _("Only the dream owner can remove collaborators.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        deleted_count, _detail = DreamCollaborator.objects.filter(
            dream=dream,
            user_id=user_id,
        ).delete()

        if deleted_count == 0:
            return Response(
                {"error": _("Collaborator not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"message": _("Collaborator removed.")})

    @extend_schema(
        summary="Explore public dreams",
        description="Browse public dreams from other users, with optional category filtering. "
        "Uses standard LimitOffset pagination.",
        tags=["Dreams"],
        parameters=[
            OpenApiParameter(
                name="category",
                description="Filter by dream category",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="ordering",
                description="Order results (e.g. -created_at, -progress_percentage)",
                required=False,
                type=str,
            ),
        ],
        responses={200: DreamSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def explore(self, request):
        """Return public dreams from other users for the Explore feed."""
        from django.db.models import Count

        from .serializers import ExploreDreamSerializer

        qs = (
            Dream.objects.filter(
                is_public=True,
                status="active",
            )
            .exclude(
                user=request.user,
            )
            .select_related("user")
            .prefetch_related(
                "goals",
                "taggings__tag",
            )
            .annotate(
                _goals_count=Count("goals", distinct=True),
            )
        )

        # Optional category filter
        category = request.query_params.get("category", "").strip()
        if category:
            qs = qs.filter(category=category)

        # Ordering: allow client to choose, default to most recent
        ordering = request.query_params.get("ordering", "-created_at")
        allowed_orderings = {
            "-created_at",
            "created_at",
            "-progress_percentage",
            "progress_percentage",
            "-updated_at",
            "updated_at",
        }
        if ordering not in allowed_orderings:
            ordering = "-created_at"
        qs = qs.order_by(ordering)

        # Use standard pagination
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ExploreDreamSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ExploreDreamSerializer(qs, many=True)
        return Response(serializer.data)

    # --- Check-in actions ---

    @extend_schema(
        summary="List check-ins",
        description="Get check-in history for a dream.",
        tags=["Check-ins"],
        responses={200: PlanCheckInSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="checkins")
    def list_checkins(self, request, pk=None):
        """List past check-ins for this dream."""
        dream = self.get_object()
        qs = PlanCheckIn.objects.filter(dream=dream).order_by("-scheduled_for")[:20]
        return Response(PlanCheckInSerializer(qs, many=True).data)

    @extend_schema(
        summary="Trigger check-in",
        description="Manually trigger an interactive check-in for a dream.",
        tags=["Check-ins"],
        responses={202: dict},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="trigger-checkin",
        throttle_classes=[AIPlanRateThrottle, AIPlanDailyThrottle],
    )
    def trigger_checkin(self, request, pk=None):
        """Manually trigger an interactive check-in."""
        from .tasks import generate_checkin_questionnaire_task

        dream = self.get_object()

        if dream.plan_phase not in ("partial", "full"):
            return Response(
                {
                    "error": _(
                        "Dream must have a plan before check-ins can be triggered."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Guard: no active check-in already in progress
        active = PlanCheckIn.objects.filter(
            dream=dream,
            status__in=[
                "pending",
                "questionnaire_generating",
                "awaiting_user",
                "ai_processing",
            ],
        ).first()
        if active:
            return Response(
                {
                    "status": active.status,
                    "checkin_id": str(active.id),
                },
                status=status.HTTP_202_ACCEPTED,
            )

        checkin = PlanCheckIn.objects.create(
            dream=dream,
            status="pending",
            scheduled_for=timezone.now(),
            triggered_by="manual",
        )
        generate_checkin_questionnaire_task.apply_async(
            args=[str(checkin.id)], queue="dreams"
        )

        return Response(
            {
                "status": "pending",
                "checkin_id": str(checkin.id),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class CheckInViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for check-in detail, response submission, and status polling."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["dream", "status"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PlanCheckIn.objects.none()
        return (
            PlanCheckIn.objects.filter(dream__user=self.request.user)
            .select_related("dream")
            .order_by("-scheduled_for")
        )

    def get_serializer_class(self):
        if self.action in ("retrieve", "status"):
            return PlanCheckInDetailSerializer
        return PlanCheckInSerializer

    @extend_schema(
        summary="Submit check-in responses",
        description="Submit questionnaire responses for a check-in awaiting user input.",
        tags=["Check-ins"],
        request=CheckInResponseSubmitSerializer,
        responses={202: dict},
    )
    @action(
        detail=True,
        methods=["post"],
        throttle_classes=[AIPlanRateThrottle, AIPlanDailyThrottle],
    )
    def respond(self, request, pk=None):
        """Submit questionnaire responses."""
        checkin = self.get_object()

        if checkin.status != "awaiting_user":
            return Response(
                {
                    "error": _("Check-in is not awaiting response."),
                    "status": checkin.status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CheckInResponseSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        responses = serializer.validated_data["responses"]

        # Validate required questions
        if checkin.questionnaire:
            required_ids = {
                q["id"]
                for q in checkin.questionnaire
                if q.get("is_required", True)
            }
            missing = required_ids - set(responses.keys())
            if missing:
                return Response(
                    {"error": f"Missing answers for: {sorted(missing)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        checkin.user_responses = responses
        checkin.status = "ai_processing"
        checkin.save(update_fields=["user_responses", "status"])

        from apps.dreams.tasks import process_checkin_responses_task

        process_checkin_responses_task.apply_async(
            args=[str(checkin.id)], queue="dreams"
        )

        return Response(
            {
                "status": "processing",
                "checkin_id": str(checkin.id),
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        summary="Check-in processing status",
        description="Poll for the status of a check-in being processed.",
        tags=["Check-ins"],
        responses={200: PlanCheckInDetailSerializer},
    )
    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        """Poll check-in processing status."""
        checkin = self.get_object()
        return Response(PlanCheckInDetailSerializer(checkin).data)


class SharedWithMeView(generics.ListAPIView):
    """List dreams shared with the current user."""

    permission_classes = [IsAuthenticated]
    serializer_class = SharedDreamSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SharedDream.objects.none()
        return SharedDream.objects.filter(shared_with=self.request.user).select_related(
            "dream", "shared_by", "shared_with"
        )

    @extend_schema(
        summary="Dreams shared with me",
        description="Get all dreams that other users have shared with the current user.",
        tags=["Dreams"],
        responses={200: SharedDreamSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"shared_dreams": serializer.data})


class DreamTagListView(generics.ListAPIView):
    """List all available dream tags."""

    permission_classes = [IsAuthenticated]
    serializer_class = DreamTagSerializer
    pagination_class = None  # tags are a small finite set
    queryset = DreamTag.objects.all()


@extend_schema_view(
    list=extend_schema(
        summary="List dream templates",
        description="Get all active dream templates",
        tags=["Dream Templates"],
        responses={200: DreamTemplateSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Get dream template",
        description="Get a specific dream template",
        tags=["Dream Templates"],
        responses={
            200: DreamTemplateSerializer,
            404: OpenApiResponse(description="Template not found."),
        },
    ),
)
class DreamTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for browsing and using dream templates."""

    permission_classes = [IsAuthenticated]
    serializer_class = DreamTemplateSerializer

    @method_decorator(cache_page(300))  # Cache for 5 minutes
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        """Return active templates, optionally filtered by category."""
        if getattr(self, "swagger_fake_view", False):
            return DreamTemplate.objects.none()
        qs = DreamTemplate.objects.filter(is_active=True)
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        return qs

    @extend_schema(
        summary="Use dream template",
        description="Create a new dream from a template with pre-built goals and tasks.",
        tags=["Dream Templates"],
        responses={
            201: DreamDetailSerializer,
            404: OpenApiResponse(description="Template not found."),
        },
    )
    @action(detail=True, methods=["post"])
    def use(self, request, pk=None):
        """Create a new dream from a template."""
        template = self.get_object()

        # Create dream from template
        dream = Dream.objects.create(
            user=request.user,
            title=template.title,
            description=template.description,
            category=template.category,
            status="active",
        )

        # Create goals and tasks from template
        for goal_data in template.template_goals:
            goal = Goal.objects.create(
                dream=dream,
                title=goal_data.get("title", ""),
                description=goal_data.get("description", ""),
                order=goal_data.get("order", 0),
                estimated_minutes=goal_data.get("estimated_minutes"),
            )

            for task_data in goal_data.get("tasks", []):
                Task.objects.create(
                    goal=goal,
                    title=task_data.get("title", ""),
                    description=task_data.get("description", ""),
                    order=task_data.get("order", 0),
                    duration_mins=task_data.get("duration_mins", 30),
                )

        # Increment usage count
        DreamTemplate.objects.filter(pk=template.pk).update(
            usage_count=template.usage_count + 1
        )

        return Response(
            DreamDetailSerializer(dream).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Featured templates",
        description="Get featured dream templates.",
        tags=["Dream Templates"],
        responses={
            200: DreamTemplateSerializer(many=True),
        },
    )
    @action(detail=False, methods=["get"])
    def featured(self, request):
        """Return featured templates."""
        templates = DreamTemplate.objects.filter(
            is_active=True,
            is_featured=True,
        )[:10]
        serializer = DreamTemplateSerializer(templates, many=True)
        return Response(serializer.data)


class DreamPDFExportView(views.APIView):
    """Export a dream as PDF."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Export dream as PDF",
        description="Generate and download a PDF of the dream with goals and tasks.",
        tags=["Dreams"],
        responses={
            200: OpenApiResponse(description="PDF file download."),
            404: OpenApiResponse(description="Dream not found."),
            501: OpenApiResponse(
                description="PDF generation not available (reportlab not installed)."
            ),
        },
    )
    def get(self, request, dream_id):
        """Generate PDF for a dream."""
        from django.http import HttpResponse

        try:
            dream = Dream.objects.prefetch_related("goals__tasks", "obstacles").get(
                id=dream_id, user=request.user
            )
        except Dream.DoesNotExist:
            return Response(
                {"error": _("Dream not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            import io

            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
            )

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []

            # Title
            title_style = ParagraphStyle(
                "DreamTitle",
                parent=styles["Title"],
                fontSize=24,
                spaceAfter=12,
            )
            elements.append(Paragraph(dream.title, title_style))
            elements.append(Spacer(1, 12))

            # Description
            elements.append(Paragraph(dream.description, styles["Normal"]))
            elements.append(Spacer(1, 12))

            # Progress
            elements.append(
                Paragraph(
                    f"<b>Progress:</b> {dream.progress_percentage:.0f}%",
                    styles["Normal"],
                )
            )
            elements.append(
                Paragraph(
                    f"<b>Status:</b> {dream.get_status_display()}",
                    styles["Normal"],
                )
            )
            if dream.target_date:
                elements.append(
                    Paragraph(
                        f"<b>Target Date:</b> {dream.target_date.strftime('%B %d, %Y')}",
                        styles["Normal"],
                    )
                )
            elements.append(Spacer(1, 24))

            # Goals and Tasks
            for goal in dream.goals.all().order_by("order"):
                goal_status = (
                    "Completed"
                    if goal.status == "completed"
                    else goal.get_status_display()
                )
                elements.append(
                    Paragraph(
                        f"<b>Goal {goal.order}:</b> {goal.title} [{goal_status}]",
                        styles["Heading2"],
                    )
                )
                if goal.description:
                    elements.append(Paragraph(goal.description, styles["Normal"]))

                for task in goal.tasks.all().order_by("order"):
                    check = "[x]" if task.status == "completed" else "[ ]"
                    duration = (
                        f" ({task.duration_mins}min)" if task.duration_mins else ""
                    )
                    elements.append(
                        Paragraph(
                            f"&nbsp;&nbsp;&nbsp;&nbsp;{check} {task.title}{duration}",
                            styles["Normal"],
                        )
                    )

                elements.append(Spacer(1, 12))

            # Obstacles
            obstacles = dream.obstacles.all()
            if obstacles:
                elements.append(Paragraph("Obstacles", styles["Heading2"]))
                for obs in obstacles:
                    elements.append(
                        Paragraph(
                            f"<b>{obs.title}</b> ({obs.get_status_display()})",
                            styles["Normal"],
                        )
                    )
                    if obs.solution:
                        elements.append(
                            Paragraph(
                                f"<i>Solution:</i> {obs.solution}",
                                styles["Normal"],
                            )
                        )
                    elements.append(Spacer(1, 6))

            doc.build(elements)
            buffer.seek(0)

            response = HttpResponse(buffer, content_type="application/pdf")
            response["Content-Disposition"] = (
                f'attachment; filename="dream-{dream.id}.pdf"'
            )
            return response

        except ImportError:
            return Response(
                {"error": _("PDF generation requires the reportlab package.")},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )


@extend_schema_view(
    list=extend_schema(
        summary="List goals",
        description="Get all goals for the current user",
        tags=["Goals"],
        responses={200: GoalSerializer(many=True)},
    ),
    create=extend_schema(
        summary="Create goal",
        description="Create a new goal",
        tags=["Goals"],
        responses={
            201: GoalSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
        examples=[GOAL_CREATE_REQUEST],
    ),
    retrieve=extend_schema(
        summary="Get goal",
        description="Get a specific goal",
        tags=["Goals"],
        responses={
            200: GoalSerializer,
            404: OpenApiResponse(description="Goal not found."),
        },
    ),
    update=extend_schema(
        summary="Update goal",
        description="Update a goal",
        tags=["Goals"],
        responses={
            200: GoalSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Goal not found."),
        },
    ),
    partial_update=extend_schema(
        summary="Partial update goal",
        description="Partially update a goal",
        tags=["Goals"],
        responses={
            200: GoalSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Goal not found."),
        },
    ),
    destroy=extend_schema(
        summary="Delete goal",
        description="Delete a goal",
        tags=["Goals"],
        responses={
            204: OpenApiResponse(description="Goal deleted."),
            404: OpenApiResponse(description="Goal not found."),
        },
    ),
)
@extend_schema_view(
    list=extend_schema(
        summary="List dream milestones",
        description="Get all dream milestones for the current user's dreams",
        tags=["Dream Milestones"],
        responses={200: DreamMilestoneSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Get dream milestone",
        description="Get a specific dream milestone with its goals and tasks",
        tags=["Dream Milestones"],
        responses={
            200: DreamMilestoneSerializer,
            404: OpenApiResponse(description="Dream milestone not found."),
        },
    ),
    destroy=extend_schema(
        summary="Delete dream milestone",
        description="Delete a dream milestone",
        tags=["Dream Milestones"],
        responses={
            204: OpenApiResponse(description="Dream milestone deleted."),
            404: OpenApiResponse(description="Dream milestone not found."),
        },
    ),
)
class DreamMilestoneViewSet(viewsets.ModelViewSet):
    """CRUD operations for dream milestones (plan structure, not streak milestones)."""

    permission_classes = [IsAuthenticated]
    serializer_class = DreamMilestoneSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["status"]
    ordering_fields = ["order", "created_at"]
    ordering = ["order"]

    def get_queryset(self):
        """Get dream milestones for current user's dreams."""
        if getattr(self, "swagger_fake_view", False):
            return DreamMilestone.objects.none()
        dream_id = self.request.query_params.get("dream")
        queryset = DreamMilestone.objects.filter(
            dream__user=self.request.user
        ).prefetch_related("goals__tasks", "obstacles")

        if dream_id:
            queryset = queryset.filter(dream_id=dream_id)

        return queryset

    def perform_create(self, serializer):
        """Validate that the dream belongs to the current user."""
        dream = serializer.validated_data.get("dream")
        if dream and dream.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                _("You can only create milestones for your own dreams.")
            )
        serializer.save()

    @extend_schema(
        summary="Complete dream milestone",
        description="Mark a dream milestone as completed",
        tags=["Dream Milestones"],
        responses={
            200: DreamMilestoneSerializer,
            404: OpenApiResponse(description="Dream milestone not found."),
        },
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Mark dream milestone as completed."""
        milestone = self.get_object()
        if milestone.status == "completed":
            return Response(
                {"error": _("Dream milestone is already completed.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        milestone.complete()
        return Response(DreamMilestoneSerializer(milestone).data)


class GoalViewSet(viewsets.ModelViewSet):
    """CRUD operations for goals."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["status"]
    ordering_fields = ["order", "created_at"]
    ordering = ["order"]

    def get_queryset(self):
        """Get goals for current user's dreams."""
        if getattr(self, "swagger_fake_view", False):
            return Goal.objects.none()
        dream_id = self.request.query_params.get("dream")
        milestone_id = self.request.query_params.get("milestone")
        queryset = Goal.objects.filter(dream__user=self.request.user).prefetch_related(
            "tasks"
        )

        if dream_id:
            queryset = queryset.filter(dream_id=dream_id)
        if milestone_id:
            queryset = queryset.filter(milestone_id=milestone_id)

        return queryset

    def perform_create(self, serializer):
        """Validate that the dream belongs to the current user before creating."""
        dream = serializer.validated_data.get("dream")
        if dream and dream.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(_("You can only create goals for your own dreams."))
        serializer.save()

    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action == "create":
            return GoalCreateSerializer
        return GoalSerializer

    @extend_schema(
        summary="Complete goal",
        description="Mark a goal as completed",
        tags=["Goals"],
        responses={
            200: GoalSerializer,
            404: OpenApiResponse(description="Goal not found."),
        },
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Mark goal as completed."""
        goal = self.get_object()
        if goal.status == "completed":
            return Response(
                {"error": _("Goal is already completed.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        goal.complete()

        return Response(GoalSerializer(goal).data)

    @extend_schema(
        summary="Refine goal with AI",
        description="Interactive SMART goal refinement wizard powered by AI. Supports multi-turn conversation.",
        tags=["Goals"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "goal_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "UUID of the goal to refine",
                    },
                    "message": {
                        "type": "string",
                        "description": "User message in the refinement conversation",
                    },
                    "history": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {
                                    "type": "string",
                                    "enum": ["user", "assistant"],
                                },
                                "content": {"type": "string"},
                            },
                        },
                        "description": "Conversation history for multi-turn refinement",
                    },
                },
                "required": ["goal_id", "message"],
            },
        },
        responses={
            200: OpenApiResponse(
                description="AI refinement response with optional refined goal and milestones."
            ),
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Goal not found."),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated, CanUseAI],
        url_path="refine",
        url_name="goal-refine",
    )
    def refine(self, request):
        """Refine a goal into a SMART goal through AI conversation."""
        goal_id = request.data.get("goal_id")
        message = request.data.get("message", "")
        history = request.data.get("history", [])

        if not goal_id:
            return Response(
                {"error": _("goal_id is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not message.strip():
            return Response(
                {"error": _("message is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch the goal (must belong to current user)
        try:
            goal = Goal.objects.select_related("dream").get(
                id=goal_id,
                dream__user=request.user,
            )
        except Goal.DoesNotExist:
            return Response(
                {"error": _("Goal not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check AI usage quota
        tracker = AIUsageTracker()
        allowed, info = tracker.check_quota(request.user, "ai_chat")
        if not allowed:
            return Response(
                {
                    "error": _(
                        "Daily AI usage limit reached. Please try again tomorrow."
                    ),
                    "quota": info,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Build dream context
        dream = goal.dream
        dream_context = {
            "title": dream.title,
            "description": dream.description,
            "category": dream.category,
        }

        # Append the new user message to history
        full_history = list(history) + [{"role": "user", "content": message}]

        # Call AI service
        try:
            ai_service = OpenAIService()
            result = ai_service.refine_goal(
                goal_title=goal.title,
                goal_description=goal.description,
                dream_context=dream_context,
                conversation_history=full_history,
            )
        except OpenAIError as e:
            logger.error(f"Goal refinement AI error: {e}")
            return Response(
                {
                    "error": _(
                        "AI service is temporarily unavailable. Please try again."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Track AI usage
        tracker.increment(request.user, "ai_chat")

        return Response(
            {
                "message": result.get("message", ""),
                "refined_goal": result.get("refined_goal"),
                "milestones": result.get("milestones"),
                "is_complete": result.get("is_complete", False),
            }
        )


@extend_schema_view(
    list=extend_schema(
        summary="List tasks",
        description="Get all tasks for the current user",
        tags=["Tasks"],
        responses={200: TaskSerializer(many=True)},
    ),
    create=extend_schema(
        summary="Create task",
        description="Create a new task",
        tags=["Tasks"],
        responses={
            201: TaskSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    ),
    retrieve=extend_schema(
        summary="Get task",
        description="Get a specific task",
        tags=["Tasks"],
        responses={
            200: TaskSerializer,
            404: OpenApiResponse(description="Task not found."),
        },
    ),
    update=extend_schema(
        summary="Update task",
        description="Update a task",
        tags=["Tasks"],
        responses={
            200: TaskSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Task not found."),
        },
    ),
    partial_update=extend_schema(
        summary="Partial update task",
        description="Partially update a task",
        tags=["Tasks"],
        responses={
            200: TaskSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Task not found."),
        },
    ),
    destroy=extend_schema(
        summary="Delete task",
        description="Delete a task",
        tags=["Tasks"],
        responses={
            204: OpenApiResponse(description="Task deleted."),
            404: OpenApiResponse(description="Task not found."),
        },
    ),
)
class TaskViewSet(viewsets.ModelViewSet):
    """CRUD operations for tasks."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["status"]
    ordering_fields = ["order", "scheduled_date", "created_at"]
    ordering = ["scheduled_date", "order"]

    def get_queryset(self):
        """Get tasks for current user."""
        if getattr(self, "swagger_fake_view", False):
            return Task.objects.none()
        goal_id = self.request.query_params.get("goal")
        queryset = Task.objects.filter(goal__dream__user=self.request.user)

        if goal_id:
            queryset = queryset.filter(goal_id=goal_id)

        return queryset

    def perform_create(self, serializer):
        """Validate that the goal's dream belongs to the current user."""
        goal = serializer.validated_data.get("goal")
        if goal and goal.dream.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(_("You can only create tasks for your own dreams."))
        serializer.save()

    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action == "create":
            return TaskCreateSerializer
        return TaskSerializer

    @extend_schema(
        summary="Complete task",
        description="Mark a task as completed and earn XP. If the task has chain_next_delay_days set, a new task is auto-created.",
        tags=["Tasks"],
        responses={
            200: TaskSerializer,
            404: OpenApiResponse(description="Task not found."),
        },
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Mark task as completed."""
        task = self.get_object()
        if task.status == "completed":
            return Response(
                {"error": _("Task is already completed.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        task.complete()

        data = TaskSerializer(task).data
        # Include the newly created chain task in the response if one was created
        chain_child = task.chain_children.first()
        if chain_child:
            data["chain_next_task"] = TaskSerializer(chain_child).data

        return Response(data)

    @extend_schema(
        summary="Get task chain",
        description="Get all tasks in a chain, ordered from root to latest.",
        tags=["Tasks"],
        responses={
            200: TaskSerializer(many=True),
            404: OpenApiResponse(description="Task not found."),
        },
    )
    @action(detail=True, methods=["get"])
    def chain(self, request, pk=None):
        """Get all tasks in this task's chain."""
        task = self.get_object()

        # Walk back to the chain root
        root = task
        while root.chain_parent_id:
            root = root.chain_parent

        # Walk forward collecting all chain tasks
        chain_tasks = [root]
        current = root
        while True:
            child = current.chain_children.first()
            if not child:
                break
            chain_tasks.append(child)
            current = child

        return Response(TaskSerializer(chain_tasks, many=True).data)

    @extend_schema(
        summary="Skip task",
        description="Skip a task without completing it",
        tags=["Tasks"],
        responses={
            200: TaskSerializer,
            404: OpenApiResponse(description="Task not found."),
        },
    )
    @action(detail=True, methods=["post"])
    def skip(self, request, pk=None):
        """Skip a task."""
        task = self.get_object()
        task.status = "skipped"
        task.save()

        return Response(TaskSerializer(task).data)

    @extend_schema(
        summary="Quick create task",
        description=(
            "Create a task with minimal input. Optionally specify a dream_id; "
            "if omitted the task is added to the first active dream's first goal."
        ),
        tags=["Tasks"],
        responses={
            201: TaskSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    @action(detail=False, methods=["post"])
    def quick_create(self, request):
        """Quick-add a task with intelligent dream/goal assignment."""
        title = (request.data.get("title") or "").strip()
        if not title:
            return Response(
                {"error": _("Title is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dream_id = request.data.get("dream_id")
        user = request.user

        # Resolve dream
        dream = None
        if dream_id:
            try:
                dream = Dream.objects.get(id=dream_id, user=user, status="active")
            except Dream.DoesNotExist:
                return Response(
                    {"error": _("Dream not found or not active.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            dream = (
                Dream.objects.filter(user=user, status="active")
                .order_by("-updated_at")
                .first()
            )

        if not dream:
            return Response(
                {"error": _("No active dreams found. Please create a dream first.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve goal — pick the first non-completed goal, or create one
        goal = dream.goals.exclude(status="completed").order_by("order").first()
        if not goal:
            goal = Goal.objects.create(
                dream=dream,
                title=_("Quick Tasks"),
                description=_("Auto-created goal for quick-add tasks."),
                order=dream.goals.count() + 1,
            )

        # Determine next order
        max_order = goal.tasks.aggregate(Max("order"))["order__max"] or 0

        task = Task.objects.create(
            goal=goal,
            title=title,
            order=max_order + 1,
        )

        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Reorder tasks",
        description="Reorder tasks within a goal. Body: { goal_id: uuid, task_ids: [ordered list of task UUIDs] }",
        tags=["Tasks"],
        responses={
            200: OpenApiResponse(description="Tasks reordered."),
            400: OpenApiResponse(description="Missing goal_id or task_ids."),
        },
    )
    @action(detail=False, methods=["post"])
    def reorder(self, request):
        """Reorder tasks within a goal. Body: { goal_id: str, task_ids: [ordered list] }"""
        goal_id = request.data.get("goal_id")
        task_ids = request.data.get("task_ids", [])
        if not goal_id or not task_ids:
            return Response(
                {"error": _("goal_id and task_ids are required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Update order field for each task
        for i, task_id in enumerate(task_ids):
            Task.objects.filter(
                id=task_id,
                goal_id=goal_id,
                goal__dream__user=request.user,
            ).update(order=i)
        return Response({"status": "ok"})

    @extend_schema(
        summary="AI daily task priorities",
        description=(
            "Uses AI to analyze the user's pending tasks and suggest an optimal "
            "order based on energy levels, deadlines, and the Eisenhower matrix."
        ),
        tags=["Tasks"],
        responses={
            200: OpenApiResponse(
                description="Prioritized task list with focus task and quick wins."
            ),
            403: OpenApiResponse(
                description="AI features require a Premium or Pro subscription."
            ),
        },
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="daily-priorities",
        permission_classes=[IsAuthenticated, CanUseAI],
    )
    def daily_priorities(self, request):
        """Return AI-prioritized task list for today."""
        user = request.user
        today = timezone.now().date()

        # Gather pending tasks for this user
        pending_tasks = Task.objects.filter(
            goal__dream__user=user,
            status="pending",
        ).select_related("goal", "goal__dream")

        # Filter to tasks relevant for today:
        # - scheduled today, or overdue, or no date set (backlog)
        from django.db.models import Q

        today_tasks = pending_tasks.filter(
            Q(scheduled_date__date=today)
            | Q(scheduled_date__date__lt=today)
            | Q(scheduled_date__isnull=True, expected_date__lte=today)
            | Q(scheduled_date__isnull=True, deadline_date__lte=today)
            | Q(
                scheduled_date__isnull=True,
                expected_date__isnull=True,
                deadline_date__isnull=True,
            )
        )[
            :30
        ]  # cap to avoid massive prompts

        if not today_tasks:
            return Response(
                {
                    "prioritized_tasks": [],
                    "focus_task": None,
                    "quick_wins": [],
                    "message": "No pending tasks found for today.",
                }
            )

        # Build task payload for AI
        task_payload = []
        for t in today_tasks:
            task_payload.append(
                {
                    "task_id": str(t.id),
                    "title": t.title,
                    "dream": t.goal.dream.title,
                    "deadline": (
                        t.deadline_date.isoformat() if t.deadline_date else None
                    ),
                    "estimated_duration": t.duration_mins,
                    "priority": t.goal.dream.priority,
                }
            )

        energy_profile = user.energy_profile or {}
        current_hour = timezone.now().hour

        # Call AI
        try:
            ai = OpenAIService()
            result = ai.prioritize_tasks(task_payload, energy_profile, current_hour)
        except OpenAIError as e:
            logger.error("AI daily priorities failed: %s", e)
            return Response(
                {"error": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Track AI usage
        tracker = AIUsageTracker()
        tracker.increment(user, "ai_plan")

        # Enrich response with full task data so the frontend doesn't need extra calls
        task_map = {str(t.id): t for t in today_tasks}
        for pt in result.get("prioritized_tasks", []):
            task_obj = task_map.get(pt.get("task_id"))
            if task_obj:
                pt["task_title"] = task_obj.title
                pt["dream_title"] = task_obj.goal.dream.title
                pt["dream_color"] = task_obj.goal.dream.color
                pt["duration_mins"] = task_obj.duration_mins

        focus = result.get("focus_task")
        if focus and focus.get("task_id"):
            fobj = task_map.get(focus["task_id"])
            if fobj:
                focus["task_title"] = fobj.title
                focus["dream_title"] = fobj.goal.dream.title
                focus["dream_color"] = fobj.goal.dream.color
                focus["duration_mins"] = fobj.duration_mins

        for qw in result.get("quick_wins", []):
            qobj = task_map.get(qw.get("task_id"))
            if qobj:
                qw["task_title"] = qobj.title
                qw["dream_title"] = qobj.goal.dream.title
                qw["duration_mins"] = qobj.duration_mins

        return Response(result)

    @extend_schema(
        summary="Estimate task durations",
        description=(
            "Uses AI to estimate how long each task will take based on context "
            "and the user's historical focus session data. "
            "Body: { task_ids: [uuid], apply: false, skill_hints: '' }"
        ),
        tags=["Tasks"],
        responses={
            200: OpenApiResponse(description="Duration estimates for each task."),
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(
                description="AI features require a Premium or Pro subscription."
            ),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="estimate-durations",
        permission_classes=[IsAuthenticated, CanUseAI],
    )
    def estimate_durations(self, request):
        """Estimate durations for a list of tasks using AI."""
        from django.db.models import Avg

        task_ids = request.data.get("task_ids", [])
        apply_estimates = request.data.get("apply", False)
        skill_hints = request.data.get("skill_hints", "")

        if not task_ids or not isinstance(task_ids, list):
            return Response(
                {"error": _("task_ids is required and must be a non-empty list.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(task_ids) > 50:
            return Response(
                {"error": _("Maximum 50 tasks per request.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user

        # Fetch tasks belonging to this user
        tasks = Task.objects.filter(
            id__in=task_ids,
            goal__dream__user=user,
        ).select_related("goal", "goal__dream")

        if not tasks.exists():
            return Response(
                {"error": _("No tasks found for the given IDs.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build task payload for AI
        task_payload = []
        for t in tasks:
            task_payload.append(
                {
                    "task_id": str(t.id),
                    "title": t.title,
                    "description": t.description or "",
                    "dream_title": t.goal.dream.title,
                    "dream_category": t.goal.dream.category or "",
                    "goal_title": t.goal.title,
                    "current_duration_mins": t.duration_mins,
                }
            )

        # Gather historical focus session data for this user
        historical_data = {}
        completed_sessions = FocusSession.objects.filter(
            user=user,
            completed=True,
            session_type="work",
        )

        total_sessions = completed_sessions.count()
        if total_sessions > 0:
            agg = completed_sessions.aggregate(
                avg_actual=Avg("actual_minutes"),
                avg_planned=Avg("duration_minutes"),
            )
            avg_actual = round(agg["avg_actual"] or 0, 1)
            avg_planned = agg["avg_planned"] or 1

            # Total completed tasks for user
            total_user_tasks = Task.objects.filter(
                goal__dream__user=user,
            ).count()
            completed_user_tasks = Task.objects.filter(
                goal__dream__user=user,
                status="completed",
            ).count()
            completion_rate = round(
                (
                    (completed_user_tasks / total_user_tasks * 100)
                    if total_user_tasks > 0
                    else 0
                ),
                1,
            )

            # Planned vs actual ratio
            ratio = round(avg_actual / avg_planned, 2) if avg_planned > 0 else 1.0

            # Category averages: avg actual_minutes by dream category
            cat_sessions = (
                completed_sessions.filter(
                    task__isnull=False,
                )
                .values(
                    "task__goal__dream__category",
                )
                .annotate(
                    avg_mins=Avg("actual_minutes"),
                )
            )
            category_averages = {}
            for cs in cat_sessions:
                cat = cs["task__goal__dream__category"] or "uncategorized"
                category_averages[cat] = round(cs["avg_mins"] or 0, 1)

            historical_data = {
                "avg_actual_minutes": avg_actual,
                "completion_rate": completion_rate,
                "avg_planned_vs_actual_ratio": ratio,
                "total_sessions": total_sessions,
                "category_averages": category_averages,
            }

        # Call AI estimation
        try:
            ai = OpenAIService()
            result = ai.estimate_durations(
                tasks=task_payload,
                historical_data=historical_data if historical_data else None,
                skill_hints=skill_hints or None,
            )
        except OpenAIError as e:
            logger.error("AI duration estimation failed: %s", e)
            return Response(
                {"error": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Track AI usage
        tracker = AIUsageTracker()
        tracker.increment(user, "ai_plan")

        estimates = result.get("estimates", [])

        # Optionally apply realistic estimates to tasks
        if apply_estimates:
            task_map = {str(t.id): t for t in tasks}
            for est in estimates:
                task_obj = task_map.get(est.get("task_id"))
                if task_obj and est.get("realistic_minutes"):
                    task_obj.duration_mins = est["realistic_minutes"]
                    task_obj.save(update_fields=["duration_mins"])

        # Compute total estimated time
        total_optimistic = sum(e.get("optimistic_minutes", 0) for e in estimates)
        total_realistic = sum(e.get("realistic_minutes", 0) for e in estimates)
        total_pessimistic = sum(e.get("pessimistic_minutes", 0) for e in estimates)

        return Response(
            {
                "estimates": estimates,
                "total_optimistic_minutes": total_optimistic,
                "total_realistic_minutes": total_realistic,
                "total_pessimistic_minutes": total_pessimistic,
                "tasks_count": len(estimates),
                "applied": apply_estimates,
            }
        )

    @extend_schema(
        summary="Parse natural language into tasks",
        description=(
            "Uses AI to parse free-form natural language text into structured "
            "task objects. Returns parsed tasks for user confirmation before creation."
        ),
        tags=["Tasks"],
        responses={
            200: OpenApiResponse(
                description="Parsed tasks from natural language input."
            ),
            400: OpenApiResponse(description="Validation error — text is required."),
            403: OpenApiResponse(
                description="AI features require a Premium or Pro subscription."
            ),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="parse-natural",
        permission_classes=[IsAuthenticated, CanUseAI],
    )
    def parse_natural(self, request):
        """Parse natural language text into structured tasks using AI."""
        text = (request.data.get("text") or "").strip()
        if not text:
            return Response(
                {"error": _("Text is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(text) > 5000:
            return Response(
                {"error": _("Text must be 5000 characters or less.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user

        # Build dreams/goals context for AI matching
        active_dreams = Dream.objects.filter(
            user=user, status="active"
        ).prefetch_related("goals")

        dreams_context = []
        for dream in active_dreams:
            goals_list = []
            for goal in dream.goals.exclude(status="completed").order_by("order")[:10]:
                goals_list.append(
                    {
                        "id": str(goal.id),
                        "title": goal.title,
                    }
                )
            dreams_context.append(
                {
                    "id": str(dream.id),
                    "title": dream.title,
                    "category": dream.category,
                    "goals": goals_list,
                }
            )

        # Call AI
        try:
            ai = OpenAIService()
            result = ai.parse_natural_language_tasks(
                text=text,
                dreams_context=dreams_context if dreams_context else None,
            )
        except OpenAIError as e:
            logger.error("AI natural language task parsing failed: %s", e)
            return Response(
                {"error": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Track AI usage
        tracker = AIUsageTracker()
        tracker.increment(user, "ai_plan")

        # Enrich parsed tasks with dream/goal titles for display
        dream_map = {str(d.id): d for d in active_dreams}
        goal_map = {}
        for d in active_dreams:
            for g in d.goals.all():
                goal_map[str(g.id)] = g

        parsed_tasks = result.get("tasks", [])
        for task in parsed_tasks:
            dream_id = task.get("matched_dream_id")
            goal_id = task.get("matched_goal_id")
            if dream_id and dream_id in dream_map:
                task["matched_dream_title"] = dream_map[dream_id].title
            else:
                task["matched_dream_id"] = None
                task["matched_dream_title"] = None
            if goal_id and goal_id in goal_map:
                task["matched_goal_title"] = goal_map[goal_id].title
            else:
                task["matched_goal_id"] = None
                task["matched_goal_title"] = None

        return Response(
            {
                "tasks": parsed_tasks,
                "dreams": [
                    {
                        "id": str(d.id),
                        "title": d.title,
                        "category": d.category,
                        "goals": [
                            {"id": str(g.id), "title": g.title}
                            for g in d.goals.exclude(status="completed").order_by(
                                "order"
                            )[:10]
                        ],
                    }
                    for d in active_dreams
                ],
            }
        )

    @extend_schema(
        summary="Create tasks from parsed natural language",
        description=(
            "Creates tasks from the AI-parsed results after user confirmation. "
            "Accepts a list of task objects with optional dream/goal assignments."
        ),
        tags=["Tasks"],
        responses={
            201: TaskSerializer(many=True),
            400: OpenApiResponse(description="Validation error."),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="create-from-parsed",
        permission_classes=[IsAuthenticated],
    )
    def create_from_parsed(self, request):
        """Create tasks from parsed natural language results."""
        tasks_data = request.data.get("tasks", [])
        if not tasks_data or not isinstance(tasks_data, list):
            return Response(
                {"error": _("A list of tasks is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        created_tasks = []

        for task_data in tasks_data:
            title = (task_data.get("title") or "").strip()
            if not title:
                continue

            # Resolve dream and goal
            dream = None
            goal = None
            dream_id = task_data.get("matched_dream_id") or task_data.get("dream_id")
            goal_id = task_data.get("matched_goal_id") or task_data.get("goal_id")

            if goal_id:
                try:
                    goal = Goal.objects.get(id=goal_id, dream__user=user)
                    dream = goal.dream
                except Goal.DoesNotExist:
                    goal = None

            if not goal and dream_id:
                try:
                    dream = Dream.objects.get(id=dream_id, user=user, status="active")
                    goal = (
                        dream.goals.exclude(status="completed")
                        .order_by("order")
                        .first()
                    )
                except Dream.DoesNotExist:
                    dream = None

            # Fallback: first active dream's first goal
            if not goal:
                dream = (
                    Dream.objects.filter(user=user, status="active")
                    .order_by("-updated_at")
                    .first()
                )
                if dream:
                    goal = (
                        dream.goals.exclude(status="completed")
                        .order_by("order")
                        .first()
                    )

            if not dream:
                continue  # Skip tasks if no dream exists

            # Auto-create a goal if needed
            if not goal:
                goal = Goal.objects.create(
                    dream=dream,
                    title=_("Quick Tasks"),
                    description=_("Auto-created goal for quick-add tasks."),
                    order=dream.goals.count() + 1,
                )

            # Determine next order
            max_order = goal.tasks.aggregate(Max("order"))["order__max"] or 0

            # Parse deadline
            deadline = None
            deadline_hint = task_data.get("deadline_hint")
            if deadline_hint:
                try:
                    from datetime import date

                    deadline = date.fromisoformat(str(deadline_hint)[:10])
                except (ValueError, TypeError):
                    deadline = None

            task = Task.objects.create(
                goal=goal,
                title=title[:255],
                description=(task_data.get("description") or "")[:5000],
                order=max_order + 1,
                duration_mins=task_data.get("duration_mins"),
                deadline_date=deadline,
            )

            created_tasks.append(task)

        if not created_tasks:
            return Response(
                {"error": _("No valid tasks could be created.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            TaskSerializer(created_tasks, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Calibrate task difficulty",
        description=(
            "Uses AI to analyze the user's task completion patterns over the last "
            "30 days and suggests difficulty adjustments, a daily target, and "
            "a stretch challenge."
        ),
        tags=["Tasks"],
        responses={
            200: OpenApiResponse(
                description="Difficulty calibration with suggestions."
            ),
            403: OpenApiResponse(
                description="AI features require a Premium or Pro subscription."
            ),
            503: OpenApiResponse(description="AI service error."),
        },
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="calibrate-difficulty",
        permission_classes=[IsAuthenticated, CanUseAI],
    )
    def calibrate_difficulty(self, request):
        """Return AI difficulty calibration based on user's recent performance."""
        from datetime import timedelta

        from django.db.models import Avg

        user = request.user
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)

        # --- Gather completion patterns over the last 30 days ---
        all_tasks_30d = Task.objects.filter(
            goal__dream__user=user,
            created_at__date__gte=thirty_days_ago,
        )
        total_tasks_30d = all_tasks_30d.count()
        completed_tasks_30d = all_tasks_30d.filter(status="completed").count()
        skipped_tasks_30d = all_tasks_30d.filter(status="skipped").count()

        completion_rate = (
            (completed_tasks_30d / total_tasks_30d) if total_tasks_30d > 0 else 0.0
        )

        # Average completion time from tasks with duration_mins
        avg_completion_time = (
            all_tasks_30d.filter(
                status="completed", duration_mins__isnull=False
            ).aggregate(avg=Avg("duration_mins"))["avg"]
        ) or 0.0

        # Streak data
        streak_data = {
            "current_streak": user.streak_days,
            "days_active_last_30": (
                user.daily_activities.filter(date__gte=thirty_days_ago)
                .values("date")
                .distinct()
                .count()
            ),
            "total_completed_30d": completed_tasks_30d,
            "total_skipped_30d": skipped_tasks_30d,
            "total_tasks_30d": total_tasks_30d,
        }

        # Current pending tasks (max 30)
        pending_tasks = Task.objects.filter(
            goal__dream__user=user,
            status="pending",
        ).select_related("goal", "goal__dream")[:30]

        current_tasks = []
        for t in pending_tasks:
            current_tasks.append(
                {
                    "task_id": str(t.id),
                    "title": t.title,
                    "description": (t.description or "")[:200],
                    "duration_mins": t.duration_mins,
                    "dream_title": t.goal.dream.title,
                    "deadline": (
                        t.deadline_date.isoformat() if t.deadline_date else None
                    ),
                }
            )

        if not current_tasks and total_tasks_30d == 0:
            return Response(
                {
                    "difficulty_level": "moderate",
                    "calibration_score": 0.5,
                    "analysis": "Not enough data to calibrate. Complete some tasks first!",
                    "suggestions": [],
                    "daily_target": {
                        "tasks": 3,
                        "focus_minutes": 60,
                        "reason": "Default target for new users.",
                    },
                    "challenge": None,
                }
            )

        # Call AI
        try:
            ai = OpenAIService()
            result = ai.calibrate_difficulty(
                completion_rate=completion_rate,
                avg_completion_time=avg_completion_time,
                streak_data=streak_data,
                current_tasks=current_tasks,
            )
        except OpenAIError as e:
            logger.error("AI difficulty calibration failed: %s", e)
            return Response(
                {"error": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Track AI usage
        AIUsageTracker().increment(user, "ai_plan")

        # Enrich suggestions with full task data
        task_map = {str(t.id): t for t in pending_tasks}
        for s in result.get("suggestions", []):
            task_obj = task_map.get(s.get("task_id"))
            if task_obj:
                s["task_title"] = task_obj.title
                s["dream_title"] = task_obj.goal.dream.title
                s["current_duration_mins"] = task_obj.duration_mins

        return Response(result)

    @extend_schema(
        summary="Apply difficulty calibration",
        description=(
            "Applies AI-suggested difficulty modifications to tasks. "
            "Body: { suggestions: [{task_id, modified_task: {title, description, duration_mins}}] }"
        ),
        tags=["Tasks"],
        responses={
            200: OpenApiResponse(description="Applied calibration results."),
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(
                description="AI features require a Premium or Pro subscription."
            ),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="apply-calibration",
        permission_classes=[IsAuthenticated, CanUseAI],
    )
    def apply_calibration(self, request):
        """Apply AI-suggested difficulty modifications to tasks."""
        suggestions = request.data.get("suggestions", [])
        if not suggestions or not isinstance(suggestions, list):
            return Response(
                {"error": _("suggestions list is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        applied = []
        errors = []

        for s in suggestions[:20]:
            task_id = s.get("task_id")
            modified = s.get("modified_task", {})
            if not task_id or not modified:
                continue

            try:
                task = Task.objects.get(
                    id=task_id,
                    goal__dream__user=user,
                )
            except Task.DoesNotExist:
                errors.append({"task_id": task_id, "error": "Task not found."})
                continue

            # Apply modifications
            if modified.get("title"):
                task.title = str(modified["title"])[:255]
            if modified.get("description"):
                task.description = str(modified["description"])[:5000]
            if modified.get("duration_mins") is not None:
                try:
                    task.duration_mins = int(modified["duration_mins"])
                except (ValueError, TypeError):
                    pass

            task.save()
            applied.append(TaskSerializer(task).data)

        return Response(
            {
                "applied": applied,
                "applied_count": len(applied),
                "errors": errors,
            }
        )


@extend_schema_view(
    list=extend_schema(
        summary="List obstacles",
        description="Get all obstacles for the current user",
        tags=["Obstacles"],
        responses={200: ObstacleSerializer(many=True)},
    ),
    create=extend_schema(
        summary="Create obstacle",
        description="Create a new obstacle",
        tags=["Obstacles"],
        responses={
            201: ObstacleSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    ),
    retrieve=extend_schema(
        summary="Get obstacle",
        description="Get a specific obstacle",
        tags=["Obstacles"],
        responses={
            200: ObstacleSerializer,
            404: OpenApiResponse(description="Obstacle not found."),
        },
    ),
    update=extend_schema(
        summary="Update obstacle",
        description="Update an obstacle",
        tags=["Obstacles"],
        responses={
            200: ObstacleSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Obstacle not found."),
        },
    ),
    partial_update=extend_schema(
        summary="Partial update obstacle",
        description="Partially update an obstacle",
        tags=["Obstacles"],
        responses={
            200: ObstacleSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Obstacle not found."),
        },
    ),
    destroy=extend_schema(
        summary="Delete obstacle",
        description="Delete an obstacle",
        tags=["Obstacles"],
        responses={
            204: OpenApiResponse(description="Obstacle deleted."),
            404: OpenApiResponse(description="Obstacle not found."),
        },
    ),
)
class ObstacleViewSet(viewsets.ModelViewSet):
    """CRUD operations for obstacles."""

    permission_classes = [IsAuthenticated]
    serializer_class = ObstacleSerializer

    def get_queryset(self):
        """Get obstacles for current user's dreams."""
        if getattr(self, "swagger_fake_view", False):
            return Obstacle.objects.none()
        dream_id = self.request.query_params.get("dream")
        queryset = Obstacle.objects.filter(dream__user=self.request.user)

        if dream_id:
            queryset = queryset.filter(dream_id=dream_id)

        return queryset

    def perform_create(self, serializer):
        """Validate that the dream belongs to the current user."""
        dream = serializer.validated_data.get("dream")
        if dream and dream.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                _("You can only create obstacles for your own dreams.")
            )
        serializer.save()

    @extend_schema(
        summary="Resolve obstacle",
        description="Mark an obstacle as resolved",
        tags=["Obstacles"],
        responses={
            200: ObstacleSerializer,
            404: OpenApiResponse(description="Obstacle not found."),
        },
    )
    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        """Mark obstacle as resolved."""
        obstacle = self.get_object()
        obstacle.status = "resolved"
        obstacle.save()

        return Response(ObstacleSerializer(obstacle).data)


@extend_schema_view(
    list=extend_schema(
        summary="List journal entries",
        description="Get all journal entries for a dream. Filter by dream using ?dream=<uuid>.",
        tags=["Dream Journal"],
        responses={200: DreamJournalSerializer(many=True)},
    ),
    create=extend_schema(
        summary="Create journal entry",
        description="Create a new journal entry for a dream",
        tags=["Dream Journal"],
        responses={201: DreamJournalSerializer},
    ),
    retrieve=extend_schema(
        summary="Get journal entry",
        description="Get a specific journal entry",
        tags=["Dream Journal"],
        responses={200: DreamJournalSerializer},
    ),
    update=extend_schema(
        summary="Update journal entry",
        description="Update a journal entry",
        tags=["Dream Journal"],
        responses={200: DreamJournalSerializer},
    ),
    partial_update=extend_schema(
        summary="Partial update journal entry",
        description="Partially update a journal entry",
        tags=["Dream Journal"],
        responses={200: DreamJournalSerializer},
    ),
    destroy=extend_schema(
        summary="Delete journal entry",
        description="Delete a journal entry",
        tags=["Dream Journal"],
        responses={204: OpenApiResponse(description="Journal entry deleted.")},
    ),
)
class DreamJournalViewSet(viewsets.ModelViewSet):
    """CRUD operations for dream journal entries."""

    serializer_class = DreamJournalSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["dream", "mood"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Return journal entries for dreams owned by the current user."""
        if getattr(self, "swagger_fake_view", False):
            return DreamJournal.objects.none()
        return DreamJournal.objects.filter(
            dream__user=self.request.user
        ).select_related("dream")

    def perform_create(self, serializer):
        """Ensure the dream belongs to the current user before creating."""
        dream = serializer.validated_data.get("dream")
        if dream.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                _("You can only add journal entries to your own dreams.")
            )
        serializer.save()


# ─── Focus Session Views ──────────────────────────────────────────────


class FocusSessionStartView(views.APIView):
    """Start a new Pomodoro focus session."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Start focus session",
        description="Start a new Pomodoro focus session, optionally linked to a task.",
        tags=["Focus"],
        request=FocusSessionStartSerializer,
        responses={
            201: FocusSessionSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request):
        serializer = FocusSessionStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task = None
        task_id = serializer.validated_data.get("task_id")
        if task_id:
            try:
                task = Task.objects.get(id=task_id, goal__dream__user=request.user)
            except Task.DoesNotExist:
                return Response(
                    {"error": _("Task not found.")},
                    status=status.HTTP_404_NOT_FOUND,
                )

        session = FocusSession.objects.create(
            user=request.user,
            task=task,
            duration_minutes=serializer.validated_data["duration_minutes"],
            session_type=serializer.validated_data.get("session_type", "work"),
        )

        return Response(
            FocusSessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )


class FocusSessionCompleteView(views.APIView):
    """Complete (or stop) an active focus session."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Complete focus session",
        description="Mark a focus session as completed and record actual minutes.",
        tags=["Focus"],
        request=FocusSessionCompleteSerializer,
        responses={
            200: FocusSessionSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Session not found."),
        },
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
                {"error": _("Session not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        session.actual_minutes = serializer.validated_data["actual_minutes"]
        session.completed = session.actual_minutes >= session.duration_minutes
        session.ended_at = timezone.now()
        session.save(update_fields=["actual_minutes", "completed", "ended_at"])

        # Award XP for completed work sessions
        if session.completed and session.session_type == "work":
            xp_amount = max(5, session.actual_minutes // 5)
            request.user.add_xp(xp_amount)

            # Record daily activity
            from apps.users.models import DailyActivity

            DailyActivity.record_task_completion(
                user=request.user,
                xp_earned=xp_amount,
                duration_mins=session.actual_minutes,
            )

        return Response(FocusSessionSerializer(session).data)


class FocusSessionHistoryView(generics.ListAPIView):
    """List recent focus sessions for the current user."""

    permission_classes = [IsAuthenticated]
    serializer_class = FocusSessionSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return FocusSession.objects.none()
        return FocusSession.objects.filter(
            user=self.request.user,
        ).select_related(
            "task"
        )[:50]

    @extend_schema(
        summary="Focus session history",
        description="Get recent focus sessions for the current user.",
        tags=["Focus"],
        responses={200: FocusSessionSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class FocusSessionStatsView(views.APIView):
    """Weekly focus stats: total minutes, sessions completed."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Focus stats",
        description="Get weekly focus statistics: total minutes and sessions completed.",
        tags=["Focus"],
        responses={
            200: OpenApiResponse(description="Focus statistics."),
        },
    )
    def get(self, request):
        from datetime import timedelta

        from django.db.models import Count, Q, Sum

        now = timezone.now()
        week_ago = now - timedelta(days=7)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Weekly stats
        weekly = FocusSession.objects.filter(
            user=request.user,
            started_at__gte=week_ago,
            session_type="work",
        ).aggregate(
            total_minutes=Sum("actual_minutes"),
            sessions_completed=Count("id", filter=Q(completed=True)),
            total_sessions=Count("id"),
        )

        # Today stats
        today = FocusSession.objects.filter(
            user=request.user,
            started_at__gte=today_start,
            session_type="work",
        ).aggregate(
            total_minutes=Sum("actual_minutes"),
            sessions_completed=Count("id", filter=Q(completed=True)),
        )

        return Response(
            {
                "weekly": {
                    "total_minutes": weekly["total_minutes"] or 0,
                    "sessions_completed": weekly["sessions_completed"] or 0,
                    "total_sessions": weekly["total_sessions"] or 0,
                },
                "today": {
                    "total_minutes": today["total_minutes"] or 0,
                    "sessions_completed": today["sessions_completed"] or 0,
                },
            }
        )
