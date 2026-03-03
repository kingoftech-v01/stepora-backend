"""
Views for Dreams app.
"""
import logging
import uuid
import requests as http_requests

logger = logging.getLogger(__name__)

from rest_framework import viewsets, status, generics, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse

from core.openapi_examples import (
    DREAM_CREATE_REQUEST, DREAM_LIST_RESPONSE, DREAM_ANALYZE_RESPONSE,
    GOAL_CREATE_REQUEST,
)
from .models import Dream, Goal, Task, Obstacle, DreamMilestone, CalibrationResponse, DreamTag, DreamTagging, SharedDream, DreamTemplate, DreamCollaborator, VisionBoardImage, DreamProgressSnapshot
from .serializers import (
    DreamSerializer, DreamDetailSerializer, DreamCreateSerializer, DreamUpdateSerializer,
    GoalSerializer, GoalCreateSerializer,
    TaskSerializer, TaskCreateSerializer,
    ObstacleSerializer, CalibrationResponseSerializer,
    DreamMilestoneSerializer,
    DreamTagSerializer, SharedDreamSerializer, ShareDreamRequestSerializer, AddTagSerializer,
    DreamTemplateSerializer, DreamCollaboratorSerializer, AddCollaboratorSerializer,
    VisionBoardImageSerializer,
)
from core.permissions import IsOwner, CanCreateDream, CanUseAI, CanUseVisionBoard
from integrations.openai_service import OpenAIService
from core.exceptions import OpenAIError
from core.ai_validators import (
    validate_plan_response,
    validate_analysis_response,
    validate_calibration_questions,
    validate_calibration_summary,
    check_plan_calibration_coherence,
    AIValidationError,
)
from core.throttles import AIPlanRateThrottle, AIPlanDailyThrottle, AICalibrationRateThrottle, AICalibrationDailyThrottle, AIImageDailyThrottle
from core.ai_usage import AIUsageTracker


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
            400: OpenApiResponse(description='Validation error.'),
        },
        examples=[DREAM_CREATE_REQUEST],
    ),
    retrieve=extend_schema(
        summary="Get dream",
        description="Get a specific dream with details",
        tags=["Dreams"],
        responses={
            200: DreamDetailSerializer,
            404: OpenApiResponse(description='Dream not found.'),
        },
    ),
    update=extend_schema(
        summary="Update dream",
        description="Update a dream",
        tags=["Dreams"],
        responses={
            200: DreamUpdateSerializer,
            400: OpenApiResponse(description='Validation error.'),
            404: OpenApiResponse(description='Dream not found.'),
        },
    ),
    partial_update=extend_schema(
        summary="Partial update dream",
        description="Partially update a dream",
        tags=["Dreams"],
        responses={
            200: DreamUpdateSerializer,
            400: OpenApiResponse(description='Validation error.'),
            404: OpenApiResponse(description='Dream not found.'),
        },
    ),
    destroy=extend_schema(
        summary="Delete dream",
        description="Delete a dream",
        tags=["Dreams"],
        responses={
            204: OpenApiResponse(description='Dream deleted.'),
            404: OpenApiResponse(description='Dream not found.'),
        },
    ),
)
class DreamViewSet(viewsets.ModelViewSet):
    """CRUD operations for dreams."""

    permission_classes = [IsAuthenticated, IsOwner]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'category']
    ordering_fields = ['created_at', 'target_date', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        """Get dreams for current user, including those they collaborate on.
        For retrieve action, also include public dreams from other users."""
        if getattr(self, 'swagger_fake_view', False):
            return Dream.objects.none()
        from django.db.models import Q
        collab_dream_ids = DreamCollaborator.objects.filter(
            user=self.request.user
        ).values_list('dream_id', flat=True)
        from .models import SharedDream
        shared_dream_ids = SharedDream.objects.filter(
            shared_with=self.request.user
        ).values_list('dream_id', flat=True)
        from django.db.models import Count, Q as DQ

        # Base filter: own dreams + collaborations + shared
        base_q = Q(user=self.request.user) | Q(id__in=collab_dream_ids) | Q(id__in=shared_dream_ids)

        # For retrieve, also allow viewing public dreams from anyone
        if self.action == 'retrieve':
            base_q = base_q | Q(is_public=True)

        qs = Dream.objects.filter(base_q).prefetch_related(
            'milestones__goals__tasks', 'milestones__obstacles',
            'goals__tasks', 'taggings__tag'
        ).annotate(
            _milestones_count=Count('milestones', distinct=True),
            _completed_milestones_count=Count('milestones', filter=DQ(milestones__status='completed'), distinct=True),
            _goals_count=Count('goals', distinct=True),
            _completed_goals_count=Count('goals', filter=DQ(goals__status='completed'), distinct=True),
            _total_tasks=Count('goals__tasks', distinct=True),
            _completed_tasks=Count('goals__tasks', filter=DQ(goals__tasks__status='completed'), distinct=True),
        ).distinct()

        # Elasticsearch-backed search (encrypted fields can't use DB icontains)
        search_query = self.request.query_params.get('search', '').strip()
        if search_query:
            from apps.search.services import SearchService
            dream_ids = SearchService.search_dreams(self.request.user, search_query)
            qs = qs.filter(id__in=dream_ids)

        return qs

    def get_serializer_class(self):
        """Return appropriate serializer based on action.
        For retrieve, use PublicDreamDetailSerializer if viewer is not the owner."""
        if self.action == 'create':
            return DreamCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DreamUpdateSerializer
        elif self.action == 'retrieve':
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
                return Dream.objects.filter(pk=pk).only('user_id').first()
        except Exception as e:
            logger.warning('get_object_for_serializer_check failed: %s', e)
        return None

    def get_permissions(self):
        """Get permissions based on action — AI and vision features require paid subscriptions.
        For retrieve, allow viewing public dreams without IsOwner check."""
        ai_actions = [
            'analyze', 'start_calibration', 'answer_calibration',
            'generate_plan', 'generate_two_minute_start',
        ]
        vision_ai_actions = ['generate_vision']
        vision_free_actions = [
            'vision_board_list', 'vision_board_add', 'vision_board_remove',
        ]
        if self.action in ai_actions:
            return [IsAuthenticated(), IsOwner(), CanUseAI()]
        if self.action in vision_ai_actions:
            return [IsAuthenticated(), IsOwner(), CanUseVisionBoard()]
        if self.action in vision_free_actions:
            return [IsAuthenticated(), IsOwner()]
        if self.action == 'create':
            return [IsAuthenticated(), CanCreateDream()]
        if self.action == 'retrieve':
            # Allow any authenticated user to retrieve — queryset handles access
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
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Dream not found.'),
            429: OpenApiResponse(description='Rate limit exceeded.'),
            500: OpenApiResponse(description='Internal server error.'),
            502: OpenApiResponse(description='AI service error.'),
        },
        examples=[DREAM_ANALYZE_RESPONSE],
    )
    @action(detail=True, methods=['post'], throttle_classes=[AIPlanRateThrottle, AIPlanDailyThrottle])
    def analyze(self, request, pk=None):
        """Analyze dream with AI."""
        dream = self.get_object()
        ai_service = OpenAIService()

        try:
            raw_analysis = ai_service.analyze_dream(
                dream.title,
                dream.description
            )

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, 'ai_plan')

            # Validate AI output before saving
            analysis = validate_analysis_response(raw_analysis)
            analysis_dict = analysis.model_dump()

            # Save validated analysis
            dream.ai_analysis = analysis_dict
            dream.save(update_fields=['ai_analysis'])

            return Response(analysis_dict)

        except AIValidationError as e:
            return Response(
                {'error': _('AI produced an invalid analysis: %(msg)s') % {'msg': e.message}},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except OpenAIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Start calibration",
        description="Generate initial calibration questions for a dream",
        tags=["Dreams"],
        responses={
            200: dict,
            400: OpenApiResponse(description='Calibration already completed.'),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Dream not found.'),
            429: OpenApiResponse(description='Rate limit exceeded.'),
            500: OpenApiResponse(description='Internal server error.'),
            502: OpenApiResponse(description='AI service error.'),
        },
    )
    @action(detail=True, methods=['post'], throttle_classes=[AICalibrationRateThrottle, AICalibrationDailyThrottle])
    def start_calibration(self, request, pk=None):
        """Generate initial calibration questions (7 questions) for the dream."""
        dream = self.get_object()
        ai_service = OpenAIService()

        # Check if calibration already completed
        if dream.calibration_status == 'completed':
            return Response(
                {'message': _('Calibration already completed for this dream')},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Generate initial batch of 7 questions
            raw_result = ai_service.generate_calibration_questions(
                dream.title,
                dream.description,
                batch_size=7,
                target_date=str(dream.target_date) if dream.target_date else None,
                category=dream.category,
            )

            # Validate AI output
            result = validate_calibration_questions(raw_result)

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, 'ai_plan')

            # Save validated questions to database
            questions_created = []
            for i, q in enumerate(result.questions, start=1):
                cr = CalibrationResponse.objects.create(
                    dream=dream,
                    question=q.question,
                    question_number=i,
                    category=q.category,
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

        except AIValidationError as e:
            return Response(
                {'error': _('AI produced invalid calibration questions: %(msg)s') % {'msg': e.message}},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except OpenAIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Answer calibration",
        description="Submit answers to calibration questions and get follow-ups if needed",
        tags=["Dreams"],
        responses={
            200: dict,
            400: OpenApiResponse(description='Validation error or content moderation flag.'),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Dream not found.'),
            429: OpenApiResponse(description='Rate limit exceeded.'),
            500: OpenApiResponse(description='Internal server error.'),
            502: OpenApiResponse(description='AI service error.'),
        },
    )
    @action(detail=True, methods=['post'], throttle_classes=[AICalibrationRateThrottle, AICalibrationDailyThrottle])
    def answer_calibration(self, request, pk=None):
        """
        Submit answers to calibration questions.

        Expects: { "answers": [{ "question_id": "uuid", "answer": "text" }, ...] }

        Returns either more questions or marks calibration as complete.
        """
        dream = self.get_object()
        answers_data = request.data.get('answers', [])

        # Support single-answer format from frontend:
        # { question: "...", answer: "...", question_number: N }
        if not answers_data:
            single_answer = request.data.get('answer')
            single_question = request.data.get('question')
            question_number = request.data.get('question_number')
            if single_answer and single_question:
                answers_data = [{'question': single_question, 'answer': single_answer, 'question_number': question_number}]

        if not answers_data:
            return Response(
                {'error': _('No answers provided')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Moderate and save answers
        from core.moderation import ContentModerationService
        moderation = ContentModerationService()

        for ans in answers_data:
            try:
                answer_text = ans.get('answer', '')
                if not answer_text:
                    continue

                # Moderate each answer
                mod_result = moderation.moderate_text(answer_text, context='calibration_answer')
                if mod_result.is_flagged:
                    return Response(
                        {'error': mod_result.user_message, 'moderation': True},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Try by question_id first, then by question_number, then by question text
                question_id = ans.get('question_id')
                question_number = ans.get('question_number')
                question_text = ans.get('question')

                cr = None
                if question_id:
                    cr = CalibrationResponse.objects.filter(id=question_id, dream=dream).first()
                if not cr and question_number:
                    cr = CalibrationResponse.objects.filter(dream=dream, question_number=question_number).first()
                if not cr and question_text:
                    cr = CalibrationResponse.objects.filter(dream=dream, question=question_text).first()
                if not cr:
                    # Create a new calibration response
                    next_num = CalibrationResponse.objects.filter(dream=dream).count() + 1
                    cr = CalibrationResponse.objects.create(
                        dream=dream,
                        question=question_text or f'Question {next_num}',
                        question_number=question_number or next_num,
                    )

                cr.answer = answer_text
                cr.save(update_fields=['answer'])
            except (KeyError, ValueError):
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

        # If we've reached 25 questions, force complete (increased from 15 for deeper understanding)
        if total_questions >= 25:
            dream.calibration_status = 'completed'
            dream.save(update_fields=['calibration_status'])

            return Response({
                'status': 'completed',
                'total_questions': total_questions,
                'answered': answered_count,
                'message': _('Calibration complete. Ready to generate your personalized plan.'),
            })

        # Ask AI if we have enough info or need more questions
        ai_service = OpenAIService()

        try:
            remaining_capacity = 25 - total_questions
            batch_size = min(remaining_capacity, 5)  # Follow-up batches of up to 5

            raw_result = ai_service.generate_calibration_questions(
                dream.title,
                dream.description,
                existing_qa=all_qa,
                batch_size=batch_size
            )

            # Validate AI output
            result = validate_calibration_questions(raw_result)

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, 'ai_plan')

            if result.sufficient or not result.questions:
                # AI says we have enough info
                dream.calibration_status = 'completed'
                dream.save(update_fields=['calibration_status'])

                return Response({
                    'status': 'completed',
                    'total_questions': total_questions,
                    'answered': answered_count,
                    'confidence_score': result.confidence_score,
                    'message': _('Calibration complete. Ready to generate your personalized plan.'),
                })
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

                return Response({
                    'status': 'in_progress',
                    'questions': CalibrationResponseSerializer(new_questions, many=True).data,
                    'total_questions': new_total,
                    'answered': answered_count,
                    'confidence_score': result.confidence_score,
                    'missing_areas': result.missing_areas,
                })

        except AIValidationError as e:
            return Response(
                {'error': _('AI produced invalid follow-up questions: %(msg)s') % {'msg': e.message}},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except OpenAIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Skip calibration",
        description="Skip the calibration step and use basic info for plan generation",
        tags=["Dreams"],
        responses={
            200: dict,
            404: OpenApiResponse(description='Dream not found.'),
        },
    )
    @action(detail=True, methods=['post'])
    def skip_calibration(self, request, pk=None):
        """Allow user to skip calibration and proceed with basic info."""
        dream = self.get_object()
        dream.calibration_status = 'skipped'
        dream.save(update_fields=['calibration_status'])

        return Response({
            'status': 'skipped',
            'message': _('Calibration skipped. You can generate a plan with basic info.'),
        })

    @extend_schema(
        summary="Generate plan",
        description="Dispatch AI plan generation as a background task. Returns 202 with status URL to poll.",
        tags=["Dreams"],
        responses={
            202: OpenApiResponse(description='Plan generation started.'),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Dream not found.'),
            429: OpenApiResponse(description='Rate limit exceeded.'),
        },
    )
    @action(detail=True, methods=['post'], throttle_classes=[AIPlanRateThrottle, AIPlanDailyThrottle])
    def generate_plan(self, request, pk=None):
        """Dispatch plan generation as a Celery background task."""
        from .tasks import generate_dream_plan_task, set_plan_status

        dream = self.get_object()

        # Check if already generating
        from .tasks import get_plan_status
        current = get_plan_status(str(dream.id))
        if current and current.get('status') == 'generating':
            return Response({
                'status': 'generating',
                'message': current.get('message', _('Plan is being generated...')),
            }, status=status.HTTP_202_ACCEPTED)

        # Dispatch Celery task
        set_plan_status(str(dream.id), 'generating', message='Starting plan generation...')
        generate_dream_plan_task.delay(str(dream.id), str(request.user.id))

        logger.info(f"generate_plan: dispatched Celery task for dream={dream.id}")
        return Response({
            'status': 'generating',
            'message': _('Plan generation started. This may take a few minutes.'),
        }, status=status.HTTP_202_ACCEPTED)

    @extend_schema(
        summary="Plan generation status",
        description="Poll for the status of a background plan generation task.",
        tags=["Dreams"],
        responses={200: dict},
    )
    @action(detail=True, methods=['get'])
    def plan_status(self, request, pk=None):
        """Check the status of plan generation for a dream."""
        from .tasks import get_plan_status

        dream = self.get_object()
        status_data = get_plan_status(str(dream.id))

        if not status_data:
            # No generation in progress — check if dream already has milestones
            has_plan = DreamMilestone.objects.filter(dream=dream).exists() or Goal.objects.filter(dream=dream).exists()
            if has_plan:
                return Response({'status': 'completed', 'message': _('Plan already exists.')})
            return Response({'status': 'idle', 'message': _('No plan generation in progress.')})

        return Response(status_data)

    @extend_schema(
        summary="Generate 2-minute start",
        description="Generate a micro-action to start working on the dream in 2 minutes",
        tags=["Dreams"],
        responses={
            200: DreamDetailSerializer,
            400: OpenApiResponse(description='2-minute start already generated.'),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Dream not found.'),
            429: OpenApiResponse(description='Rate limit exceeded.'),
            500: OpenApiResponse(description='Internal server error.'),
        },
    )
    @action(detail=True, methods=['post'], throttle_classes=[AIPlanDailyThrottle])
    def generate_two_minute_start(self, request, pk=None):
        """Generate 2-minute start task for dream."""
        dream = self.get_object()

        if dream.has_two_minute_start:
            return Response(
                {'message': _('2-minute start already generated')},
                status=status.HTTP_400_BAD_REQUEST
            )

        ai_service = OpenAIService()

        try:
            micro_action = ai_service.generate_two_minute_start(
                dream.title,
                dream.description
            )

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, 'ai_plan')

            # Get first goal or create one
            first_goal = dream.goals.order_by('order').first()
            if not first_goal:
                first_goal = Goal.objects.create(
                    dream=dream,
                    title=_("Getting Started"),
                    description=_("Initial steps to begin your journey"),
                    order=0
                )

            # Create 2-minute task
            Task.objects.create(
                goal=first_goal,
                title=_("Start now: %(action)s") % {'action': micro_action},
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

    @extend_schema(
        summary="Generate vision board",
        description="Generate a vision board image using DALL-E",
        tags=["Dreams"],
        responses={
            200: dict,
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Dream not found.'),
            429: OpenApiResponse(description='Rate limit exceeded.'),
            500: OpenApiResponse(description='Internal server error.'),
        },
    )
    @action(detail=True, methods=['post'], throttle_classes=[AIImageDailyThrottle])
    def generate_vision(self, request, pk=None):
        """Generate vision board image for dream."""
        dream = self.get_object()
        ai_service = OpenAIService()

        try:
            # Gather rich context for a more realistic, personalized image
            milestone_titles = list(
                dream.milestones.order_by('order').values_list('title', flat=True)
            )
            calibration_profile = None
            if dream.ai_analysis and isinstance(dream.ai_analysis, dict):
                cal_summary = dream.ai_analysis.get('calibration_summary', {})
                calibration_profile = cal_summary.get('user_profile') if isinstance(cal_summary, dict) else None

            image_url = ai_service.generate_vision_image(
                dream.title,
                dream.description,
                category=dream.category,
                milestones=milestone_titles,
                calibration_profile=calibration_profile,
            )

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, 'ai_image')

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
                logger.warning(f"Failed to download vision image for dream {dream.id}: {dl_err}")

            # Create vision board image entry with the local file
            vbi = VisionBoardImage(
                dream=dream,
                caption=_('AI-generated vision for "%(title)s"') % {'title': dream.title},
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
                permanent_url = request.build_absolute_uri(vbi.image_file.url)
            else:
                permanent_url = image_url

            dream.vision_image_url = permanent_url
            dream.save(update_fields=['vision_image_url'])

            return Response({'image_url': permanent_url})

        except OpenAIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Vision board list",
        description="List vision board images for a dream",
        tags=["Dreams"],
        responses={
            200: VisionBoardImageSerializer(many=True),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Dream not found.'),
        },
    )
    @action(detail=True, methods=['get'], url_path='vision-board')
    def vision_board_list(self, request, pk=None):
        """List all vision board images for a dream."""
        dream = self.get_object()
        images = dream.vision_images.all()
        return Response({'images': VisionBoardImageSerializer(images, many=True).data})

    @extend_schema(
        summary="Add vision board image",
        description="Add an image to the vision board",
        tags=["Dreams"],
        responses={
            201: VisionBoardImageSerializer,
            400: OpenApiResponse(description='Validation error — image file or URL required.'),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Dream not found.'),
        },
    )
    @action(detail=True, methods=['post'], url_path='vision-board/add', parser_classes=[MultiPartParser, FormParser])
    def vision_board_add(self, request, pk=None):
        """Add an image to the dream's vision board."""
        dream = self.get_object()

        image_file = request.FILES.get('image')
        image_url = request.data.get('image_url', '')
        caption = request.data.get('caption', '')

        if not image_file and not image_url:
            return Response({'error': _('Provide image file or image_url.')}, status=status.HTTP_400_BAD_REQUEST)

        # Validate uploaded image file type and size
        if image_file:
            ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
            content_type = getattr(image_file, 'content_type', '')
            if content_type not in ALLOWED_IMAGE_TYPES:
                return Response(
                    {'error': _('Unsupported image format. Allowed: JPEG, PNG, WebP, GIF.')},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if image_file.size > 10 * 1024 * 1024:
                return Response(
                    {'error': _('Image file too large. Max 10MB.')},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Validate magic bytes
            header = image_file.read(12)
            image_file.seek(0)
            valid_magic = (
                header[:3] == b'\xff\xd8\xff' or  # JPEG
                header[:8] == b'\x89PNG\r\n\x1a\n' or  # PNG
                header[:4] == b'RIFF' and header[8:12] == b'WEBP' or  # WebP
                header[:6] in (b'GIF87a', b'GIF89a')  # GIF
            )
            if not valid_magic:
                return Response(
                    {'error': _('Invalid image file.')},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Validate URL to prevent SSRF
        if image_url:
            from core.validators import validate_url_no_ssrf
            try:
                validate_url_no_ssrf(image_url)  # returns (url, resolved_ip); raises on unsafe
            except Exception:
                return Response(
                    {'error': _('Invalid or unsafe image URL.')},
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
                dream.vision_image_url = request.build_absolute_uri(vbi.image_file.url)
            elif vbi.image_url:
                dream.vision_image_url = vbi.image_url
            dream.save(update_fields=['vision_image_url'])

        return Response(VisionBoardImageSerializer(vbi).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Remove vision board image",
        description="Remove an image from the vision board",
        tags=["Dreams"],
        responses={
            200: dict,
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Image not found.'),
        },
    )
    @action(detail=True, methods=['delete'], url_path=r'vision-board/(?P<image_id>[0-9a-f-]+)')
    def vision_board_remove(self, request, pk=None, image_id=None):
        """Remove an image from the dream's vision board."""
        dream = self.get_object()
        deleted, _ = VisionBoardImage.objects.filter(dream=dream, id=image_id).delete()
        if deleted == 0:
            return Response({'error': _('Image not found.')}, status=status.HTTP_404_NOT_FOUND)
        return Response({'message': _('Image removed.')})

    @extend_schema(
        summary="Progress history",
        description="Get progress snapshot history for sparkline charts",
        tags=["Dreams"],
        responses={
            200: dict,
            404: OpenApiResponse(description='Dream not found.'),
        },
    )
    @action(detail=True, methods=['get'], url_path='progress-history')
    def progress_history(self, request, pk=None):
        """Get progress snapshots for a dream."""
        dream = self.get_object()
        days = int(request.query_params.get('days', 30))
        snapshots = DreamProgressSnapshot.objects.filter(
            dream=dream
        ).order_by('-date')[:days]
        data = list(reversed([
            {'date': str(s.date), 'progress': s.progress_percentage}
            for s in snapshots
        ]))
        return Response({'snapshots': data, 'current_progress': dream.progress_percentage})

    @extend_schema(
        summary="Complete dream",
        description="Mark a dream as completed",
        tags=["Dreams"],
        responses={
            200: DreamSerializer,
            404: OpenApiResponse(description='Dream not found.'),
        },
    )
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark dream as completed."""
        dream = self.get_object()
        if dream.status == 'completed':
            return Response(
                {'error': _('Dream is already completed.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        dream.complete()

        return Response(DreamSerializer(dream).data)

    @extend_schema(
        summary="Toggle dream favorite",
        description="Toggle the is_favorited flag on a dream (for vision board likes).",
        tags=["Dreams"],
        responses={
            200: DreamSerializer,
            404: OpenApiResponse(description='Dream not found.'),
        },
    )
    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        """Toggle the favorited status of a dream."""
        dream = self.get_object()
        dream.is_favorited = not dream.is_favorited
        dream.save(update_fields=['is_favorited', 'updated_at'])
        return Response(DreamSerializer(dream).data)

    @extend_schema(
        summary="Duplicate dream",
        description="Create a deep copy of a dream with all goals and tasks",
        tags=["Dreams"],
        responses={
            201: DreamDetailSerializer,
            404: OpenApiResponse(description='Dream not found.'),
        },
    )
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Deep-copy a dream including goals and tasks."""
        original = self.get_object()

        # Create the dream copy
        new_dream = Dream.objects.create(
            user=request.user,
            title=_("%(title)s (Copy)") % {'title': original.title},
            description=original.description,
            category=original.category,
            target_date=original.target_date,
            priority=original.priority,
            status='active',
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
            DreamDetailSerializer(new_dream).data,
            status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Share dream",
        description="Share a dream with another user",
        tags=["Dreams"],
        request=ShareDreamRequestSerializer,
        responses={
            201: SharedDreamSerializer,
            400: OpenApiResponse(description='Validation error.'),
            404: OpenApiResponse(description='Dream or target user not found.'),
        },
    )
    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Share a dream with another user."""
        dream = self.get_object()
        serializer = ShareDreamRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shared_with_id = serializer.validated_data['shared_with_id']
        permission = serializer.validated_data.get('permission', 'view')

        if shared_with_id == request.user.id:
            return Response(
                {'error': _('You cannot share a dream with yourself.')},
                status=status.HTTP_400_BAD_REQUEST
            )

        from apps.users.models import User
        try:
            target_user = User.objects.get(id=shared_with_id)
        except User.DoesNotExist:
            return Response(
                {'error': _('User not found.')},
                status=status.HTTP_404_NOT_FOUND
            )

        if SharedDream.objects.filter(dream=dream, shared_with=target_user).exists():
            return Response(
                {'error': _('Dream already shared with this user.')},
                status=status.HTTP_400_BAD_REQUEST
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
                notification_type='progress',
                title=_('%(name)s shared a dream with you!') % {'name': request.user.display_name or _("Someone")},
                body=_('You now have access to view this dream.'),
                scheduled_for=timezone.now(),
                data={
                    'type': 'dream_shared',
                    'dream_id': str(dream.id),
                    'shared_by_id': str(request.user.id),
                },
            )
        except Exception:
            pass  # Don't fail the share if notification fails

        return Response(
            SharedDreamSerializer(shared).data,
            status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Unshare dream",
        description="Remove sharing of a dream with a user",
        tags=["Dreams"],
        responses={
            200: dict,
            404: OpenApiResponse(description='Share not found.'),
        },
    )
    @action(detail=True, methods=['delete'], url_path=r'unshare/(?P<user_id>[0-9a-f-]+)')
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
                {'error': _('Share not found.')},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({'message': _('Dream unshared.')})

    @extend_schema(
        summary="Add tag to dream",
        description="Add a tag to a dream",
        tags=["Dreams"],
        request=AddTagSerializer,
        responses={
            200: DreamSerializer,
            400: OpenApiResponse(description='Validation error.'),
            404: OpenApiResponse(description='Dream not found.'),
        },
    )
    @action(detail=True, methods=['post'], url_path='tags')
    def add_tag(self, request, pk=None):
        """Add a tag to a dream. Creates the tag if it doesn't exist."""
        dream = self.get_object()
        serializer = AddTagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tag_name = serializer.validated_data['tag_name'].strip().lower()
        tag, _ = DreamTag.objects.get_or_create(name=tag_name)

        DreamTagging.objects.get_or_create(dream=dream, tag=tag)

        return Response(DreamSerializer(dream).data)

    @extend_schema(
        summary="Remove tag from dream",
        description="Remove a tag from a dream",
        tags=["Dreams"],
        responses={
            200: dict,
            404: OpenApiResponse(description='Tag not found on this dream.'),
        },
    )
    @action(detail=True, methods=['delete'], url_path=r'tags/(?P<tag_name>[^/]+)')
    def remove_tag(self, request, pk=None, tag_name=None):
        """Remove a tag from a dream."""
        dream = self.get_object()
        deleted_count, _ = DreamTagging.objects.filter(
            dream=dream,
            tag__name=tag_name.lower(),
        ).delete()

        if deleted_count == 0:
            return Response(
                {'error': _('Tag not found on this dream.')},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({'message': _('Tag removed.')})

    @extend_schema(
        summary="Add collaborator",
        description="Add a collaborator to a dream. Only the dream owner can add collaborators.",
        request=AddCollaboratorSerializer,
        responses={
            201: DreamCollaboratorSerializer,
            400: OpenApiResponse(description='Validation error.'),
            403: OpenApiResponse(description='Only the dream owner can add collaborators.'),
            404: OpenApiResponse(description='Dream or target user not found.'),
        },
        tags=["Dreams"],
    )
    @action(detail=True, methods=['post'], url_path='collaborators')
    def add_collaborator(self, request, pk=None):
        """Add a collaborator to a dream."""
        dream = self.get_object()

        if dream.user != request.user:
            return Response(
                {'error': _('Only the dream owner can add collaborators.')},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AddCollaboratorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user_id = serializer.validated_data['user_id']
        role = serializer.validated_data.get('role', 'viewer')

        if target_user_id == request.user.id:
            return Response(
                {'error': _('You cannot add yourself as a collaborator.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.users.models import User
        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response({'error': _('User not found.')}, status=status.HTTP_404_NOT_FOUND)

        if DreamCollaborator.objects.filter(dream=dream, user=target_user).exists():
            return Response(
                {'error': _('User is already a collaborator on this dream.')},
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
            404: OpenApiResponse(description='Dream not found.'),
        },
        tags=["Dreams"],
    )
    @action(detail=True, methods=['get'], url_path='collaborators/list')
    def list_collaborators(self, request, pk=None):
        """List collaborators on a dream."""
        dream = self.get_object()
        collabs = DreamCollaborator.objects.filter(
            dream=dream,
        ).select_related('user')
        serializer = DreamCollaboratorSerializer(collabs, many=True)
        return Response({'collaborators': serializer.data})

    @extend_schema(
        summary="Remove collaborator",
        description="Remove a collaborator from a dream. Only the owner can remove.",
        responses={
            200: dict,
            403: OpenApiResponse(description='Only the dream owner can remove collaborators.'),
            404: OpenApiResponse(description='Collaborator not found.'),
        },
        tags=["Dreams"],
    )
    @action(detail=True, methods=['delete'], url_path=r'collaborators/(?P<user_id>[0-9a-f-]+)')
    def remove_collaborator(self, request, pk=None, user_id=None):
        """Remove a collaborator from a dream."""
        dream = self.get_object()

        if dream.user != request.user:
            return Response(
                {'error': _('Only the dream owner can remove collaborators.')},
                status=status.HTTP_403_FORBIDDEN,
            )

        deleted_count, _ = DreamCollaborator.objects.filter(
            dream=dream,
            user_id=user_id,
        ).delete()

        if deleted_count == 0:
            return Response(
                {'error': _('Collaborator not found.')},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({'message': _('Collaborator removed.')})


class SharedWithMeView(generics.ListAPIView):
    """List dreams shared with the current user."""

    permission_classes = [IsAuthenticated]
    serializer_class = SharedDreamSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SharedDream.objects.none()
        return SharedDream.objects.filter(
            shared_with=self.request.user
        ).select_related('dream', 'shared_by', 'shared_with')

    @extend_schema(
        summary="Dreams shared with me",
        description="Get all dreams that other users have shared with the current user.",
        tags=["Dreams"],
        responses={200: SharedDreamSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({'shared_dreams': serializer.data})


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
            404: OpenApiResponse(description='Template not found.'),
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
        if getattr(self, 'swagger_fake_view', False):
            return DreamTemplate.objects.none()
        qs = DreamTemplate.objects.filter(is_active=True)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs

    @extend_schema(
        summary="Use dream template",
        description="Create a new dream from a template with pre-built goals and tasks.",
        tags=["Dream Templates"],
        responses={
            201: DreamDetailSerializer,
            404: OpenApiResponse(description='Template not found.'),
        },
    )
    @action(detail=True, methods=['post'])
    def use(self, request, pk=None):
        """Create a new dream from a template."""
        template = self.get_object()

        # Create dream from template
        dream = Dream.objects.create(
            user=request.user,
            title=template.title,
            description=template.description,
            category=template.category,
            status='active',
        )

        # Create goals and tasks from template
        for goal_data in template.template_goals:
            goal = Goal.objects.create(
                dream=dream,
                title=goal_data.get('title', ''),
                description=goal_data.get('description', ''),
                order=goal_data.get('order', 0),
                estimated_minutes=goal_data.get('estimated_minutes'),
            )

            for task_data in goal_data.get('tasks', []):
                Task.objects.create(
                    goal=goal,
                    title=task_data.get('title', ''),
                    description=task_data.get('description', ''),
                    order=task_data.get('order', 0),
                    duration_mins=task_data.get('duration_mins', 30),
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
    @action(detail=False, methods=['get'])
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
            200: OpenApiResponse(description='PDF file download.'),
            404: OpenApiResponse(description='Dream not found.'),
            501: OpenApiResponse(description='PDF generation not available (reportlab not installed).'),
        },
    )
    def get(self, request, dream_id):
        """Generate PDF for a dream."""
        from django.http import HttpResponse

        try:
            dream = Dream.objects.prefetch_related(
                'goals__tasks', 'obstacles'
            ).get(id=dream_id, user=request.user)
        except Dream.DoesNotExist:
            return Response(
                {'error': _('Dream not found.')},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            import io

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []

            # Title
            title_style = ParagraphStyle(
                'DreamTitle',
                parent=styles['Title'],
                fontSize=24,
                spaceAfter=12,
            )
            elements.append(Paragraph(dream.title, title_style))
            elements.append(Spacer(1, 12))

            # Description
            elements.append(Paragraph(dream.description, styles['Normal']))
            elements.append(Spacer(1, 12))

            # Progress
            elements.append(Paragraph(
                f"<b>Progress:</b> {dream.progress_percentage:.0f}%",
                styles['Normal'],
            ))
            elements.append(Paragraph(
                f"<b>Status:</b> {dream.get_status_display()}",
                styles['Normal'],
            ))
            if dream.target_date:
                elements.append(Paragraph(
                    f"<b>Target Date:</b> {dream.target_date.strftime('%B %d, %Y')}",
                    styles['Normal'],
                ))
            elements.append(Spacer(1, 24))

            # Goals and Tasks
            for goal in dream.goals.all().order_by('order'):
                goal_status = 'Completed' if goal.status == 'completed' else goal.get_status_display()
                elements.append(Paragraph(
                    f"<b>Goal {goal.order}:</b> {goal.title} [{goal_status}]",
                    styles['Heading2'],
                ))
                if goal.description:
                    elements.append(Paragraph(goal.description, styles['Normal']))

                for task in goal.tasks.all().order_by('order'):
                    check = '[x]' if task.status == 'completed' else '[ ]'
                    duration = f" ({task.duration_mins}min)" if task.duration_mins else ""
                    elements.append(Paragraph(
                        f"&nbsp;&nbsp;&nbsp;&nbsp;{check} {task.title}{duration}",
                        styles['Normal'],
                    ))

                elements.append(Spacer(1, 12))

            # Obstacles
            obstacles = dream.obstacles.all()
            if obstacles:
                elements.append(Paragraph("Obstacles", styles['Heading2']))
                for obs in obstacles:
                    elements.append(Paragraph(
                        f"<b>{obs.title}</b> ({obs.get_status_display()})",
                        styles['Normal'],
                    ))
                    if obs.solution:
                        elements.append(Paragraph(
                            f"<i>Solution:</i> {obs.solution}",
                            styles['Normal'],
                        ))
                    elements.append(Spacer(1, 6))

            doc.build(elements)
            buffer.seek(0)

            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="dream-{dream.id}.pdf"'
            return response

        except ImportError:
            return Response(
                {'error': _('PDF generation requires the reportlab package.')},
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
            400: OpenApiResponse(description='Validation error.'),
        },
        examples=[GOAL_CREATE_REQUEST],
    ),
    retrieve=extend_schema(
        summary="Get goal",
        description="Get a specific goal",
        tags=["Goals"],
        responses={
            200: GoalSerializer,
            404: OpenApiResponse(description='Goal not found.'),
        },
    ),
    update=extend_schema(
        summary="Update goal",
        description="Update a goal",
        tags=["Goals"],
        responses={
            200: GoalSerializer,
            400: OpenApiResponse(description='Validation error.'),
            404: OpenApiResponse(description='Goal not found.'),
        },
    ),
    partial_update=extend_schema(
        summary="Partial update goal",
        description="Partially update a goal",
        tags=["Goals"],
        responses={
            200: GoalSerializer,
            400: OpenApiResponse(description='Validation error.'),
            404: OpenApiResponse(description='Goal not found.'),
        },
    ),
    destroy=extend_schema(
        summary="Delete goal",
        description="Delete a goal",
        tags=["Goals"],
        responses={
            204: OpenApiResponse(description='Goal deleted.'),
            404: OpenApiResponse(description='Goal not found.'),
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
            404: OpenApiResponse(description='Dream milestone not found.'),
        },
    ),
    destroy=extend_schema(
        summary="Delete dream milestone",
        description="Delete a dream milestone",
        tags=["Dream Milestones"],
        responses={
            204: OpenApiResponse(description='Dream milestone deleted.'),
            404: OpenApiResponse(description='Dream milestone not found.'),
        },
    ),
)
class DreamMilestoneViewSet(viewsets.ModelViewSet):
    """CRUD operations for dream milestones (plan structure, not streak milestones)."""

    permission_classes = [IsAuthenticated]
    serializer_class = DreamMilestoneSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['order', 'created_at']
    ordering = ['order']

    def get_queryset(self):
        """Get dream milestones for current user's dreams."""
        if getattr(self, 'swagger_fake_view', False):
            return DreamMilestone.objects.none()
        dream_id = self.request.query_params.get('dream')
        queryset = DreamMilestone.objects.filter(
            dream__user=self.request.user
        ).prefetch_related('goals__tasks', 'obstacles')

        if dream_id:
            queryset = queryset.filter(dream_id=dream_id)

        return queryset

    @extend_schema(
        summary="Complete dream milestone",
        description="Mark a dream milestone as completed",
        tags=["Dream Milestones"],
        responses={
            200: DreamMilestoneSerializer,
            404: OpenApiResponse(description='Dream milestone not found.'),
        },
    )
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark dream milestone as completed."""
        milestone = self.get_object()
        if milestone.status == 'completed':
            return Response(
                {'error': _('Dream milestone is already completed.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        milestone.complete()
        return Response(DreamMilestoneSerializer(milestone).data)


class GoalViewSet(viewsets.ModelViewSet):
    """CRUD operations for goals."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['order', 'created_at']
    ordering = ['order']

    def get_queryset(self):
        """Get goals for current user's dreams."""
        if getattr(self, 'swagger_fake_view', False):
            return Goal.objects.none()
        dream_id = self.request.query_params.get('dream')
        milestone_id = self.request.query_params.get('milestone')
        queryset = Goal.objects.filter(dream__user=self.request.user).prefetch_related('tasks')

        if dream_id:
            queryset = queryset.filter(dream_id=dream_id)
        if milestone_id:
            queryset = queryset.filter(milestone_id=milestone_id)

        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action == 'create':
            return GoalCreateSerializer
        return GoalSerializer

    @extend_schema(
        summary="Complete goal",
        description="Mark a goal as completed",
        tags=["Goals"],
        responses={
            200: GoalSerializer,
            404: OpenApiResponse(description='Goal not found.'),
        },
    )
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark goal as completed."""
        goal = self.get_object()
        if goal.status == 'completed':
            return Response(
                {'error': _('Goal is already completed.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        goal.complete()

        return Response(GoalSerializer(goal).data)


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
            400: OpenApiResponse(description='Validation error.'),
        },
    ),
    retrieve=extend_schema(
        summary="Get task",
        description="Get a specific task",
        tags=["Tasks"],
        responses={
            200: TaskSerializer,
            404: OpenApiResponse(description='Task not found.'),
        },
    ),
    update=extend_schema(
        summary="Update task",
        description="Update a task",
        tags=["Tasks"],
        responses={
            200: TaskSerializer,
            400: OpenApiResponse(description='Validation error.'),
            404: OpenApiResponse(description='Task not found.'),
        },
    ),
    partial_update=extend_schema(
        summary="Partial update task",
        description="Partially update a task",
        tags=["Tasks"],
        responses={
            200: TaskSerializer,
            400: OpenApiResponse(description='Validation error.'),
            404: OpenApiResponse(description='Task not found.'),
        },
    ),
    destroy=extend_schema(
        summary="Delete task",
        description="Delete a task",
        tags=["Tasks"],
        responses={
            204: OpenApiResponse(description='Task deleted.'),
            404: OpenApiResponse(description='Task not found.'),
        },
    ),
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
        if getattr(self, 'swagger_fake_view', False):
            return Task.objects.none()
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

    @extend_schema(
        summary="Complete task",
        description="Mark a task as completed and earn XP",
        tags=["Tasks"],
        responses={
            200: TaskSerializer,
            404: OpenApiResponse(description='Task not found.'),
        },
    )
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark task as completed."""
        task = self.get_object()
        if task.status == 'completed':
            return Response(
                {'error': _('Task is already completed.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        task.complete()

        return Response(TaskSerializer(task).data)

    @extend_schema(
        summary="Skip task",
        description="Skip a task without completing it",
        tags=["Tasks"],
        responses={
            200: TaskSerializer,
            404: OpenApiResponse(description='Task not found.'),
        },
    )
    @action(detail=True, methods=['post'])
    def skip(self, request, pk=None):
        """Skip a task."""
        task = self.get_object()
        task.status = 'skipped'
        task.save()

        return Response(TaskSerializer(task).data)


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
            400: OpenApiResponse(description='Validation error.'),
        },
    ),
    retrieve=extend_schema(
        summary="Get obstacle",
        description="Get a specific obstacle",
        tags=["Obstacles"],
        responses={
            200: ObstacleSerializer,
            404: OpenApiResponse(description='Obstacle not found.'),
        },
    ),
    update=extend_schema(
        summary="Update obstacle",
        description="Update an obstacle",
        tags=["Obstacles"],
        responses={
            200: ObstacleSerializer,
            400: OpenApiResponse(description='Validation error.'),
            404: OpenApiResponse(description='Obstacle not found.'),
        },
    ),
    partial_update=extend_schema(
        summary="Partial update obstacle",
        description="Partially update an obstacle",
        tags=["Obstacles"],
        responses={
            200: ObstacleSerializer,
            400: OpenApiResponse(description='Validation error.'),
            404: OpenApiResponse(description='Obstacle not found.'),
        },
    ),
    destroy=extend_schema(
        summary="Delete obstacle",
        description="Delete an obstacle",
        tags=["Obstacles"],
        responses={
            204: OpenApiResponse(description='Obstacle deleted.'),
            404: OpenApiResponse(description='Obstacle not found.'),
        },
    ),
)
class ObstacleViewSet(viewsets.ModelViewSet):
    """CRUD operations for obstacles."""

    permission_classes = [IsAuthenticated]
    serializer_class = ObstacleSerializer

    def get_queryset(self):
        """Get obstacles for current user's dreams."""
        if getattr(self, 'swagger_fake_view', False):
            return Obstacle.objects.none()
        dream_id = self.request.query_params.get('dream')
        queryset = Obstacle.objects.filter(dream__user=self.request.user)

        if dream_id:
            queryset = queryset.filter(dream_id=dream_id)

        return queryset

    @extend_schema(
        summary="Resolve obstacle",
        description="Mark an obstacle as resolved",
        tags=["Obstacles"],
        responses={
            200: ObstacleSerializer,
            404: OpenApiResponse(description='Obstacle not found.'),
        },
    )
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Mark obstacle as resolved."""
        obstacle = self.get_object()
        obstacle.status = 'resolved'
        obstacle.save()

        return Response(ObstacleSerializer(obstacle).data)
