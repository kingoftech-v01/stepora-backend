"""
Views for Conversations app.
"""

import logging

from django.db.models import Prefetch
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.ai_usage import AIUsageTracker
from core.ai_validators import (
    AIValidationError,
    validate_ai_output_safety,
    validate_chat_response,
    validate_function_call,
)
from core.exceptions import OpenAIError
from core.moderation import ContentModerationService
from core.openapi_examples import AI_SEND_MESSAGE_REQUEST, AI_SEND_MESSAGE_RESPONSE
from core.pagination import StandardResultsSetPagination
from core.permissions import CanUseAI
from core.throttles import AIChatDailyThrottle, AIRateThrottle, AIVoiceDailyThrottle
from core.validators import validate_url_no_ssrf
from integrations.openai_service import OpenAIService

from .models import (
    Call,
    ChatMemory,
    Conversation,
    ConversationBranch,
    ConversationTemplate,
    Message,
    MessageReadStatus,
)
from .serializers import (
    CallHistorySerializer,
    ChatMemorySerializer,
    ConversationBranchSerializer,
    ConversationCreateSerializer,
    ConversationDetailSerializer,
    ConversationSerializer,
    ConversationTemplateSerializer,
    MessageCreateSerializer,
    MessageSearchSerializer,
    MessageSerializer,
)
from .tasks import (
    extract_chat_memories,
    summarize_conversation,
    transcribe_voice_message,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List conversations",
        description="Get all conversations for the current user",
        tags=["Conversations"],
        responses={
            200: ConversationSerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
        },
    ),
    create=extend_schema(
        summary="Create conversation",
        description="Create a new AI conversation",
        tags=["Conversations"],
        responses={
            201: ConversationSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Subscription required."),
        },
    ),
    retrieve=extend_schema(
        summary="Get conversation",
        description="Get a specific conversation with messages",
        tags=["Conversations"],
        responses={
            200: ConversationDetailSerializer,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Not found."),
        },
    ),
    update=extend_schema(
        summary="Update conversation",
        description="Update a conversation",
        tags=["Conversations"],
        responses={
            200: ConversationSerializer,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Not found."),
        },
    ),
    partial_update=extend_schema(
        summary="Partial update conversation",
        description="Partially update a conversation",
        tags=["Conversations"],
        responses={
            200: ConversationSerializer,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Not found."),
        },
    ),
    destroy=extend_schema(
        summary="Delete conversation",
        description="Delete a conversation",
        tags=["Conversations"],
        responses={
            204: OpenApiResponse(description="Conversation deleted."),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Not found."),
        },
    ),
)
class ConversationViewSet(viewsets.ModelViewSet):
    """CRUD operations for conversations. All AI conversation features require premium+."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["conversation_type", "is_active"]
    ordering = ["-updated_at"]

    def get_permissions(self):
        """Only require CanUseAI for AI-specific write actions, not list/retrieve."""
        if self.action in (
            "create",
            "send_message",
            "send_voice",
            "send_image",
            "summarize",
            "summarize_voice",
            "generate_plan",
        ):
            return [IsAuthenticated(), CanUseAI()]
        return [IsAuthenticated()]

    def perform_update(self, serializer):
        """Only the conversation owner can update."""
        if serializer.instance.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You can only modify your own conversations.")
        serializer.save()

    def perform_destroy(self, instance):
        """Only the conversation owner can delete."""
        if instance.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You can only delete your own conversations.")
        instance.delete()

    def get_queryset(self):
        """Get conversations for current user, including buddy chats they participate in."""
        if getattr(self, "swagger_fake_view", False):
            return Conversation.objects.none()
        from django.db.models import Q

        user = self.request.user
        return (
            Conversation.objects.filter(
                Q(user=user)
                | Q(conversation_type="buddy_chat", buddy_pairing__user1=user)
                | Q(conversation_type="buddy_chat", buddy_pairing__user2=user)
            )
            .distinct()
            .prefetch_related(
                Prefetch(
                    "messages",
                    queryset=Message.objects.order_by("-created_at")[:1],
                    to_attr="_last_message_list",
                ),
                "read_statuses",
            )
        )

    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action == "create":
            return ConversationCreateSerializer
        elif self.action == "retrieve":
            return ConversationDetailSerializer
        return ConversationSerializer

    def create(self, request, *args, **kwargs):
        """Create conversation and return full serialized object."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = serializer.save(user=request.user)
        # Return full representation with id
        response_serializer = ConversationSerializer(
            conversation, context={"request": request}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Send message",
        description="Send a message and get AI response",
        tags=["Conversations"],
        request=MessageCreateSerializer,
        responses={
            200: dict,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Subscription required."),
            429: OpenApiResponse(description="Rate limit exceeded."),
            502: OpenApiResponse(description="AI service error."),
        },
        examples=[AI_SEND_MESSAGE_REQUEST, AI_SEND_MESSAGE_RESPONSE],
    )
    @action(
        detail=True,
        methods=["post"],
        throttle_classes=[AIRateThrottle, AIChatDailyThrottle],
    )
    def send_message(self, request, pk=None):
        """Send a message in the conversation."""
        conversation = self.get_object()

        # Validate message
        message_serializer = MessageCreateSerializer(data=request.data)
        if not message_serializer.is_valid():
            return Response(
                message_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        user_message = message_serializer.validated_data["content"]

        # Content moderation check BEFORE saving or calling AI
        mod_result = ContentModerationService().moderate_text(
            user_message, context="chat"
        )
        if mod_result.is_flagged:
            return Response(
                {"error": mod_result.user_message, "moderation": True},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Save user message
        conversation.add_message("user", user_message)

        # Get AI response
        ai_service = OpenAIService()

        try:
            # Get recent messages for context
            messages = conversation.get_messages_for_api(limit=20)

            # Get AI response
            raw_response = ai_service.chat(
                messages=messages, conversation_type=conversation.conversation_type
            )

            # Validate chat response
            validated = validate_chat_response(raw_response)

            # Validate AI output safety
            is_safe, safety_reason = validate_ai_output_safety(validated.content)
            if not is_safe:
                validated.content = (
                    "I apologize, but I need to rephrase my response. "
                    "Could you tell me more about what specific aspect of your dream you'd like help with?"
                )

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, "ai_chat")

            # Save validated assistant message
            assistant_message = conversation.add_message(
                "assistant",
                validated.content,
                metadata={"tokens_used": validated.tokens_used},
            )

            # Handle function calls from AI (validate before executing)
            if raw_response.get("function_call"):
                try:
                    fc = validate_function_call(raw_response["function_call"])
                    assistant_message.metadata["function_call"] = fc.model_dump()
                    assistant_message.save(update_fields=["metadata"])
                except AIValidationError:
                    pass  # Ignore invalid function calls silently

            # Trigger summarization if threshold reached
            if (
                conversation.total_messages % 20 == 0
                and conversation.total_messages > 0
            ):
                summarize_conversation.delay(str(conversation.id))

            # Trigger memory extraction every 5 user messages
            user_msg_count = conversation.messages.filter(role="user").count()
            if user_msg_count % 5 == 0 and user_msg_count > 0:
                extract_chat_memories.delay(str(conversation.id))

            # Broadcast to WebSocket clients so other connected tabs/users get real-time updates
            try:
                from asgiref.sync import async_to_sync
                from channels.layers import get_channel_layer

                channel_layer = get_channel_layer()
                room = f"conversation_{conversation.id}"
                async_to_sync(channel_layer.group_send)(
                    room,
                    {
                        "type": "chat_message",
                        "message": {
                            "id": str(assistant_message.id),
                            "role": "assistant",
                            "content": validated.content,
                            "created_at": assistant_message.created_at.isoformat(),
                        },
                    },
                )
            except Exception:
                logger.debug("WebSocket broadcast failed", exc_info=True)

            return Response(
                {
                    "user_message": {"role": "user", "content": user_message},
                    "assistant_message": MessageSerializer(assistant_message).data,
                    "conversation": ConversationSerializer(conversation).data,
                }
            )

        except AIValidationError as e:
            return Response(
                {
                    "error": _("AI produced an invalid response: %(message)s")
                    % {"message": e.message}
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except OpenAIError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Send voice message",
        description="Upload audio for transcription and AI response",
        tags=["Conversations"],
        responses={
            201: dict,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Subscription required."),
            429: OpenApiResponse(description="Rate limit exceeded."),
            502: OpenApiResponse(description="AI service error."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
        url_path="send-voice",
        throttle_classes=[AIVoiceDailyThrottle],
    )
    def send_voice(self, request, pk=None):
        """Send a voice message. Audio is transcribed via Whisper and AI responds."""

        from django.core.files.storage import default_storage

        conversation = self.get_object()
        audio_file = request.FILES.get("audio")
        if not audio_file:
            return Response(
                {"error": _("No audio file provided.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate file size (max 25MB — Whisper limit)
        if audio_file.size > 25 * 1024 * 1024:
            return Response(
                {"error": _("Audio file too large. Max 25MB.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate audio file type
        ALLOWED_AUDIO_TYPES = {
            "audio/mpeg",
            "audio/mp3",
            "audio/mp4",
            "audio/m4a",
            "audio/wav",
            "audio/x-wav",
            "audio/webm",
            "audio/ogg",
            "audio/flac",
            "audio/aac",
        }
        content_type = getattr(audio_file, "content_type", "")
        if content_type not in ALLOWED_AUDIO_TYPES:
            return Response(
                {
                    "error": _(
                        "Unsupported audio format: %(format)s. Allowed: mp3, m4a, wav, webm, ogg, flac, aac."
                    )
                    % {"format": content_type}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate magic bytes to prevent disguised file uploads
        header = audio_file.read(12)
        audio_file.seek(0)
        valid_audio = (
            header[:3] == b"ID3"  # MP3 with ID3 tag
            or header[:2] == b"\xff\xfb"
            or header[:2] == b"\xff\xf3"
            or header[:2] == b"\xff\xf2"  # MP3 sync
            or header[4:8] == b"ftyp"  # M4A/MP4 container
            or header[:4] == b"RIFF"  # WAV
            or header[:4] == b"OggS"  # Ogg
            or header[:4] == b"fLaC"  # FLAC
            or header[:4] == b"\x1aE\xdf\xa3"  # WebM/Matroska
            or len(header) >= 4  # Allow through if header too short to validate
        )
        if not valid_audio:
            return Response(
                {"error": _("Invalid audio file content.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Sanitize filename to prevent path traversal
        import re

        safe_name = re.sub(r"[^\w\-.]", "_", audio_file.name)[:100]

        # Save audio file
        file_path = f"voice_messages/{conversation.id}/{safe_name}"
        saved_path = default_storage.save(file_path, audio_file)
        audio_url = default_storage.url(saved_path)

        # Create message with audio_url
        message = conversation.add_message(
            "user",
            "[Voice message]",
            metadata={"type": "voice"},
        )
        audio_duration = request.data.get("duration")
        update_kwargs = {"audio_url": audio_url}
        if audio_duration is not None:
            try:
                update_kwargs["audio_duration"] = int(audio_duration)
            except (ValueError, TypeError):
                pass
        Message.objects.filter(id=message.id).update(**update_kwargs)

        # Increment voice usage counter
        AIUsageTracker().increment(request.user, "ai_voice")

        # Queue async transcription
        transcribe_voice_message.delay(str(message.id))

        # Trigger summarization if threshold reached
        if conversation.total_messages % 20 == 0 and conversation.total_messages > 0:
            summarize_conversation.delay(str(conversation.id))

        return Response(
            {
                "message": MessageSerializer(Message.objects.get(id=message.id)).data,
                "status": "transcription_queued",
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Summarize voice message",
        description="Generate an AI-powered summary of a voice message's transcription, "
        "extracting key points, action items, and mood.",
        tags=["Conversations"],
        responses={
            200: dict,
            400: OpenApiResponse(description="No transcription available."),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Message not found."),
            429: OpenApiResponse(description="Rate limit exceeded."),
            502: OpenApiResponse(description="AI service error."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path=r"summarize-voice/(?P<message_id>[0-9a-f-]+)",
        throttle_classes=[AIRateThrottle, AIChatDailyThrottle],
    )
    def summarize_voice(self, request, pk=None, message_id=None):
        """Summarize a specific voice message in the conversation."""
        conversation = self.get_object()

        try:
            message = conversation.messages.get(id=message_id)
        except Message.DoesNotExist:
            return Response(
                {"error": _("Message not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        # Check if the message has a transcription to summarize
        transcript = message.transcription or ""
        if not transcript and message.content and message.content != "[Voice message]":
            transcript = message.content

        if not transcript:
            return Response(
                {
                    "error": _(
                        "This message has no transcription yet. Please wait for transcription to complete."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if summary already exists in metadata
        metadata = message.metadata or {}
        existing_summary = metadata.get("voice_summary")
        if existing_summary and not request.data.get("force"):
            return Response(
                {
                    "summary": existing_summary,
                    "message_id": str(message.id),
                    "cached": True,
                }
            )

        # Build conversation context from recent messages
        recent_msgs = list(
            conversation.messages.exclude(id=message.id).order_by("-created_at")[:5]
        )
        recent_msgs.reverse()
        context = "\n".join(
            f"{m.role}: {m.content[:200]}"
            for m in recent_msgs
            if m.content and m.content != "[Voice message]"
        )

        ai_service = OpenAIService()
        try:
            summary_result = ai_service.summarize_voice_note(
                transcript,
                conversation_context=context,
            )

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, "ai_chat")

            # Store summary in message metadata
            metadata["voice_summary"] = summary_result
            message.metadata = metadata
            message.save(update_fields=["metadata"])

            return Response(
                {
                    "summary": summary_result,
                    "message_id": str(message.id),
                    "cached": False,
                }
            )

        except OpenAIError as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    @extend_schema(
        summary="Send image message",
        description="Upload image for GPT-4 Vision analysis",
        tags=["Conversations"],
        responses={
            200: dict,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Subscription required."),
            429: OpenApiResponse(description="Rate limit exceeded."),
            502: OpenApiResponse(description="AI service error."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
        url_path="send-image",
        throttle_classes=[AIRateThrottle, AIChatDailyThrottle],
    )
    def send_image(self, request, pk=None):
        """Send an image for GPT-4 Vision analysis in the conversation context."""
        from django.core.files.storage import default_storage

        conversation = self.get_object()
        image_file = request.FILES.get("image")
        user_prompt = request.data.get("prompt", "")

        if not image_file:
            return Response(
                {"error": _("No image file provided.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate file size (max 20MB)
        if image_file.size > 20 * 1024 * 1024:
            return Response(
                {"error": _("Image too large. Max 20MB.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Moderate user prompt text if provided
        if user_prompt:
            mod_result = ContentModerationService().moderate_text(
                user_prompt, context="chat"
            )
            if mod_result.is_flagged:
                return Response(
                    {"error": mod_result.user_message, "moderation": True},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Save image (sanitize filename to prevent path traversal)
        import re

        safe_name = re.sub(r"[^\w\-.]", "_", image_file.name)[:100]
        file_path = f"chat_images/{conversation.id}/{safe_name}"
        saved_path = default_storage.save(file_path, image_file)
        image_url = default_storage.url(saved_path)

        # Save user message with image
        user_content = user_prompt if user_prompt else "[Image shared]"
        user_message = conversation.add_message(
            "user",
            user_content,
            metadata={"type": "image"},
        )
        Message.objects.filter(id=user_message.id).update(image_url=image_url)

        # Validate image URL to prevent SSRF
        try:
            _validated_url, _resolved_ip = validate_url_no_ssrf(image_url)
        except Exception:
            return Response(
                {"error": _("Invalid image URL.")}, status=status.HTTP_400_BAD_REQUEST
            )

        # Analyze image with GPT-4 Vision
        ai_service = OpenAIService()
        try:
            result = ai_service.analyze_image(image_url, user_prompt)

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, "ai_chat")

            assistant_message = conversation.add_message(
                "assistant",
                result["content"],
                metadata={
                    "tokens_used": result["tokens_used"],
                    "type": "image_analysis",
                },
            )

            return Response(
                {
                    "user_message": MessageSerializer(
                        Message.objects.get(id=user_message.id)
                    ).data,
                    "assistant_message": MessageSerializer(assistant_message).data,
                }
            )

        except OpenAIError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Get messages",
        description="Get all messages for a conversation",
        tags=["Conversations"],
        responses={
            200: MessageSerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Not found."),
        },
    )
    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        """Get messages for a conversation."""
        conversation = self.get_object()
        messages = conversation.messages.all()

        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = MessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Pin conversation",
        description="Pin/unpin a conversation",
        tags=["Conversations"],
        responses={
            200: ConversationSerializer,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Not found."),
        },
    )
    @action(detail=True, methods=["post"])
    def pin(self, request, pk=None):
        """Toggle pin status on a conversation."""
        conversation = self.get_object()
        conversation.is_pinned = not conversation.is_pinned
        conversation.save(update_fields=["is_pinned"])
        return Response(ConversationSerializer(conversation).data)

    @extend_schema(
        summary="Pin message",
        description="Pin/unpin a message in a conversation",
        tags=["Conversations"],
        responses={
            200: MessageSerializer,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Not found."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path=r"pin-message/(?P<message_id>[0-9a-f-]+)",
    )
    def pin_message(self, request, pk=None, message_id=None):
        """Toggle pin on a message."""
        conversation = self.get_object()
        try:
            message = conversation.messages.get(id=message_id)
        except Message.DoesNotExist:
            return Response(
                {"error": _("Message not found.")}, status=status.HTTP_404_NOT_FOUND
            )
        message.is_pinned = not message.is_pinned
        message.save(update_fields=["is_pinned"])
        return Response(MessageSerializer(message).data)

    @extend_schema(
        summary="Like message",
        description="Toggle like on a message",
        tags=["Conversations"],
        responses={
            200: MessageSerializer,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Not found."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path=r"like-message/(?P<message_id>[0-9a-f-]+)",
    )
    def like_message(self, request, pk=None, message_id=None):
        """Toggle like on a message."""
        conversation = self.get_object()
        try:
            message = conversation.messages.get(id=message_id)
        except Message.DoesNotExist:
            return Response(
                {"error": _("Message not found.")}, status=status.HTTP_404_NOT_FOUND
            )
        message.is_liked = not message.is_liked
        message.save(update_fields=["is_liked"])
        return Response(MessageSerializer(message).data)

    @extend_schema(
        summary="React to message",
        description="Add a reaction emoji to a message",
        tags=["Conversations"],
        responses={
            200: MessageSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Not found."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path=r"react-message/(?P<message_id>[0-9a-f-]+)",
    )
    def react_message(self, request, pk=None, message_id=None):
        """Add or remove a reaction on a message."""
        conversation = self.get_object()
        try:
            message = conversation.messages.get(id=message_id)
        except Message.DoesNotExist:
            return Response(
                {"error": _("Message not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        emoji = request.data.get("emoji", "")
        if not emoji:
            return Response(
                {"error": _("emoji is required.")}, status=status.HTTP_400_BAD_REQUEST
            )

        reactions = message.reactions or []
        if emoji in reactions:
            reactions.remove(emoji)
        else:
            reactions.append(emoji)
        message.reactions = reactions
        message.save(update_fields=["reactions"])
        return Response(MessageSerializer(message).data)

    @extend_schema(
        summary="Search messages",
        description="Search messages within a conversation by keyword. Returns paginated results with highlighted excerpts.",
        tags=["Conversations"],
        responses={
            200: MessageSearchSerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Not found."),
        },
    )
    @action(detail=True, methods=["get"])
    def search(self, request, pk=None):
        """Search messages within a conversation by content keyword."""
        conversation = self.get_object()
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response([])

        matched = (
            conversation.messages.filter(content__icontains=query)
            .exclude(role="system")
            .order_by("-created_at")[:50]
        )

        serializer = MessageSearchSerializer(
            matched,
            many=True,
            context={"search_query": query, "request": request},
        )
        return Response(serializer.data)

    @extend_schema(
        summary="Export conversation",
        description="Export a conversation as JSON or PDF",
        tags=["Conversations"],
        responses={
            200: dict,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Not found."),
        },
    )
    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        """Export conversation in JSON or PDF format."""
        conversation = self.get_object()
        export_format = request.query_params.get("format", "json")

        # Cap exported messages to prevent DoS via memory-heavy PDF generation
        MAX_EXPORT_MESSAGES = 2000
        messages = conversation.messages.order_by("created_at")[:MAX_EXPORT_MESSAGES]

        if export_format == "pdf":
            try:
                import io

                from django.http import HttpResponse
                from reportlab.lib.pagesizes import letter
                from reportlab.lib.styles import getSampleStyleSheet
                from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter)
                styles = getSampleStyleSheet()
                story = []

                # Title
                story.append(
                    Paragraph(
                        f"Conversation: {conversation.conversation_type}",
                        styles["Title"],
                    )
                )
                story.append(Spacer(1, 12))

                # Messages
                for msg in messages:
                    role_label = "You" if msg.role == "user" else "Stepora"
                    story.append(
                        Paragraph(
                            f"<b>{role_label}</b> ({msg.created_at.strftime('%Y-%m-%d %H:%M')})",
                            styles["Heading4"],
                        )
                    )
                    # Escape special chars for reportlab
                    content = (
                        msg.content.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                    )
                    story.append(Paragraph(content, styles["Normal"]))
                    story.append(Spacer(1, 8))

                doc.build(story)
                buffer.seek(0)

                response = HttpResponse(
                    buffer.getvalue(), content_type="application/pdf"
                )
                response["Content-Disposition"] = (
                    f'attachment; filename="conversation_{conversation.id}.pdf"'
                )
                return response

            except ImportError:
                return Response(
                    {"error": _("PDF export is not available. Install reportlab.")},
                    status=status.HTTP_501_NOT_IMPLEMENTED,
                )

        # Default: JSON export
        data = {
            "conversation": {
                "id": str(conversation.id),
                "type": conversation.conversation_type,
                "created_at": conversation.created_at.isoformat(),
                "total_messages": conversation.total_messages,
            },
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                }
                for msg in messages
            ],
        }

        return Response(data)

    @extend_schema(
        summary="Archive conversation",
        description="Archive (deactivate) a conversation.",
        tags=["Conversations"],
        responses={200: ConversationSerializer},
    )
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        """Archive a conversation by setting is_active=False."""
        conversation = self.get_object()
        conversation.is_active = False
        conversation.save(update_fields=["is_active", "updated_at"])
        return Response(ConversationSerializer(conversation).data)

    @extend_schema(
        summary="Mark conversation as read",
        description="Mark all messages in this conversation as read for the current user.",
        tags=["Conversations"],
        responses={200: dict},
    )
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        """Mark conversation as read up to the latest message."""
        conversation = self.get_object()
        last_msg = conversation.messages.order_by("-created_at").first()

        read_status, _ = MessageReadStatus.objects.update_or_create(
            user=request.user,
            conversation=conversation,
            defaults={"last_read_message": last_msg},
        )

        return Response(
            {
                "status": "ok",
                "last_read_message_id": str(last_msg.id) if last_msg else None,
            }
        )

    # ─── Branch endpoints ─────────────────────────────────────────────

    @extend_schema(
        summary="Create branch",
        description="Create a new conversation branch from a specific message. "
        "All messages up to the parent message are copied as context.",
        tags=["Conversations"],
        responses={
            201: ConversationBranchSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Message not found."),
        },
    )
    @action(detail=True, methods=["post"], url_path="branch")
    def create_branch(self, request, pk=None):
        """Create a branch from a specific message in the conversation."""
        conversation = self.get_object()

        parent_message_id = request.data.get("parent_message_id")
        branch_name = request.data.get("name", "")

        if not parent_message_id:
            return Response(
                {"error": _("parent_message_id is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            parent_message = conversation.messages.get(id=parent_message_id)
        except Message.DoesNotExist:
            return Response(
                {"error": _("Message not found in this conversation.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Create the branch
        branch = ConversationBranch.objects.create(
            conversation=conversation,
            parent_message=parent_message,
            name=branch_name,
        )

        # Copy all messages up to and including parent_message as context
        context_messages = conversation.messages.filter(
            created_at__lte=parent_message.created_at,
            branch__isnull=True,
        ).order_by("created_at")

        for msg in context_messages:
            Message.objects.create(
                conversation=conversation,
                branch=branch,
                role=msg.role,
                content=msg.content,
                metadata={**msg.metadata, "copied_from": str(msg.id)},
            )

        return Response(
            ConversationBranchSerializer(branch).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="List branches",
        description="List all branches for a conversation.",
        tags=["Conversations"],
        responses={200: ConversationBranchSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="branches")
    def list_branches(self, request, pk=None):
        """List all branches for a conversation."""
        conversation = self.get_object()
        branches = conversation.branches.all()
        serializer = ConversationBranchSerializer(branches, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Send message in branch",
        description="Send a message in a specific branch and get AI response.",
        tags=["Conversations"],
        request=MessageCreateSerializer,
        responses={
            200: dict,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Branch not found."),
            502: OpenApiResponse(description="AI service error."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path=r"branch/(?P<branch_id>[0-9a-f-]+)/send",
        throttle_classes=[AIRateThrottle, AIChatDailyThrottle],
    )
    def branch_send(self, request, pk=None, branch_id=None):
        """Send a message in a branch and get AI response."""
        conversation = self.get_object()

        try:
            branch = conversation.branches.get(id=branch_id)
        except ConversationBranch.DoesNotExist:
            return Response(
                {"error": _("Branch not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        # Validate message
        message_serializer = MessageCreateSerializer(data=request.data)
        if not message_serializer.is_valid():
            return Response(
                message_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        user_message = message_serializer.validated_data["content"]

        # Content moderation
        mod_result = ContentModerationService().moderate_text(
            user_message, context="chat"
        )
        if mod_result.is_flagged:
            return Response(
                {"error": mod_result.user_message, "moderation": True},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Save user message in the branch
        user_msg = Message.objects.create(
            conversation=conversation,
            branch=branch,
            role="user",
            content=user_message,
        )

        # Get AI response using branch messages as context
        ai_service = OpenAIService()

        try:
            # Build context from branch messages
            branch_messages = branch.messages.order_by("created_at")
            api_messages = []

            # Inject dream context if available
            if conversation.dream:
                dream = conversation.dream
                dream_context = (
                    f"DREAM CONTEXT (always active):\n"
                    f"- Dream Title: {dream.title}\n"
                    f"- Dream Description: {dream.description}\n"
                    f"- Category: {dream.category}\n"
                    f"- Status: {dream.status}\n"
                    f"- Progress: {dream.progress_percentage:.0f}%\n"
                )
                api_messages.append({"role": "system", "content": dream_context})

            # Add branch messages (last 20)
            recent_branch_msgs = list(branch_messages.order_by("-created_at")[:20])
            recent_branch_msgs.reverse()
            api_messages.extend(
                [
                    {"role": msg.role, "content": msg.content}
                    for msg in recent_branch_msgs
                ]
            )

            raw_response = ai_service.chat(
                messages=api_messages, conversation_type=conversation.conversation_type
            )

            validated = validate_chat_response(raw_response)

            is_safe, safety_reason = validate_ai_output_safety(validated.content)
            if not is_safe:
                validated.content = (
                    "I apologize, but I need to rephrase my response. "
                    "Could you tell me more about what specific aspect of your dream you'd like help with?"
                )

            AIUsageTracker().increment(request.user, "ai_chat")

            assistant_message = Message.objects.create(
                conversation=conversation,
                branch=branch,
                role="assistant",
                content=validated.content,
                metadata={"tokens_used": validated.tokens_used},
            )

            return Response(
                {
                    "user_message": MessageSerializer(user_msg).data,
                    "assistant_message": MessageSerializer(assistant_message).data,
                    "branch": ConversationBranchSerializer(branch).data,
                }
            )

        except AIValidationError as e:
            return Response(
                {
                    "error": _("AI produced an invalid response: %(message)s")
                    % {"message": e.message}
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except OpenAIError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Get branch messages",
        description="Get all messages in a specific branch.",
        tags=["Conversations"],
        responses={
            200: MessageSerializer(many=True),
            404: OpenApiResponse(description="Branch not found."),
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path=r"branch/(?P<branch_id>[0-9a-f-]+)/messages",
    )
    def branch_messages(self, request, pk=None, branch_id=None):
        """Get messages for a specific branch."""
        conversation = self.get_object()

        try:
            branch = conversation.branches.get(id=branch_id)
        except ConversationBranch.DoesNotExist:
            return Response(
                {"error": _("Branch not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        messages = branch.messages.order_by("created_at")

        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = MessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List messages",
        description="Get all messages for the current user",
        tags=["Messages"],
    ),
    retrieve=extend_schema(
        summary="Get message", description="Get a specific message", tags=["Messages"]
    ),
)
class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to messages."""

    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """Get messages for current user's conversations."""
        if getattr(self, "swagger_fake_view", False):
            return Message.objects.none()
        return (
            Message.objects.filter(conversation__user=self.request.user)
            .select_related("conversation")
            .order_by("-created_at")
        )


@extend_schema_view(
    list=extend_schema(
        summary="List conversation templates",
        description="Get all available conversation templates",
        tags=["Conversations"],
    ),
    retrieve=extend_schema(
        summary="Get template",
        description="Get a specific conversation template",
        tags=["Conversations"],
    ),
)
class ConversationTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to conversation templates."""

    permission_classes = [IsAuthenticated]
    serializer_class = ConversationTemplateSerializer
    queryset = ConversationTemplate.objects.filter(is_active=True)


class CallViewSet(viewsets.GenericViewSet):
    """Manage voice/video calls between buddies."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Call.objects.none()
        from django.db.models import Q

        return Call.objects.filter(
            Q(caller=self.request.user) | Q(callee=self.request.user)
        )

    @extend_schema(
        summary="Initiate a call",
        description="Create a call and notify the callee via FCM.",
        tags=["Calls"],
        responses={201: dict, 400: OpenApiResponse(description="Validation error")},
    )
    @action(detail=False, methods=["post"])
    def initiate(self, request):
        """Initiate a voice or video call."""
        callee_id = request.data.get("callee_id")
        call_type = request.data.get("call_type", "voice")

        if not callee_id:
            return Response(
                {"detail": _("callee_id is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if call_type not in ("voice", "video"):
            return Response(
                {"detail": _("call_type must be voice or video.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.users.models import User

        try:
            callee = User.objects.get(id=callee_id)
        except User.DoesNotExist:
            return Response(
                {"detail": _("User not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        if callee == request.user:
            return Response(
                {"detail": _("Cannot call yourself.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Block enforcement
        from apps.social.models import BlockedUser

        if BlockedUser.is_blocked(request.user, callee):
            return Response(
                {"detail": _("Cannot call this user")}, status=status.HTTP_403_FORBIDDEN
            )

        # Find buddy pairing if one exists
        from django.db.models import Q as BQ

        from apps.buddies.models import BuddyPairing

        pairing = BuddyPairing.objects.filter(
            BQ(user1=request.user, user2=callee) | BQ(user1=callee, user2=request.user),
            status="active",
        ).first()

        call = Call.objects.create(
            caller=request.user,
            callee=callee,
            call_type=call_type,
            status="ringing",
            buddy_pairing=pairing,
        )

        # Send FCM push to callee
        self._notify_callee(call, request.user)

        # Broadcast to buddy_chat WebSocket group so partner sees it in real-time
        if pairing:
            try:
                from asgiref.sync import async_to_sync
                from channels.layers import get_channel_layer

                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"buddy_chat_{pairing.id}",
                    {
                        "type": "call_started",
                        "call": {
                            "id": str(call.id),
                            "type": call_type,
                            "caller": str(request.user.id),
                        },
                    },
                )
            except Exception:
                logger.debug("WebSocket call broadcast failed", exc_info=True)

        return Response(
            {
                "callId": str(call.id),
                "channelName": str(call.id),
                "callType": call.call_type,
                "status": call.status,
                "calleeId": str(callee.id),
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(summary="Accept a call", tags=["Calls"])
    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """Accept an incoming call."""
        call = self._get_call(pk)
        if not call:
            return Response(
                {"detail": _("Call not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        if call.callee != request.user:
            return Response(
                {"detail": _("Only the callee can accept.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        if call.status != "ringing":
            return Response(
                {
                    "detail": _("Call is %(status)s, cannot accept.")
                    % {"status": call.status}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone

        call.status = "accepted"
        call.started_at = timezone.now()
        call.save(update_fields=["status", "started_at", "updated_at"])

        return Response(
            {
                "callId": str(call.id),
                "status": call.status,
                "startedAt": call.started_at.isoformat(),
            }
        )

    @extend_schema(summary="Reject a call", tags=["Calls"])
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Reject an incoming call."""
        call = self._get_call(pk)
        if not call:
            return Response(
                {"detail": _("Call not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        if call.callee != request.user:
            return Response(
                {"detail": _("Only the callee can reject.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        call.status = "rejected"
        call.save(update_fields=["status", "updated_at"])

        # Notify the caller that the call was declined
        try:
            from django.utils import timezone as tz

            from apps.notifications.models import Notification

            callee_name = call.callee.display_name or _("Your buddy")
            Notification.objects.create(
                user=call.caller,
                notification_type="buddy",
                title=_("%(name)s declined your call") % {"name": callee_name},
                body="",
                scheduled_for=tz.now(),
                data={"call_id": str(call.id), "type": "call_rejected"},
            )
        except Exception:
            logger.warning("Failed to send notification", exc_info=True)

        # Send WebSocket event to caller
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"notifications_{call.caller.id}",
                {
                    "type": "notification.message",
                    "data": {
                        "type": "call_rejected",
                        "call_id": str(call.id),
                        "callee_name": callee_name,
                    },
                },
            )
        except Exception:
            logger.debug("WebSocket broadcast failed", exc_info=True)

        return Response({"callId": str(call.id), "status": call.status})

    @extend_schema(summary="End a call", tags=["Calls"])
    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        """End an active call."""
        call = self._get_call(pk)
        if not call:
            return Response(
                {"detail": _("Call not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        if request.user not in (call.caller, call.callee):
            return Response(
                {"detail": _("Not a participant.")}, status=status.HTTP_403_FORBIDDEN
            )

        from django.utils import timezone

        call.status = "completed"
        call.ended_at = timezone.now()
        if call.started_at:
            call.duration_seconds = int(
                (call.ended_at - call.started_at).total_seconds()
            )
        call.save(
            update_fields=["status", "ended_at", "duration_seconds", "updated_at"]
        )

        return Response(
            {
                "callId": str(call.id),
                "status": call.status,
                "durationSeconds": call.duration_seconds,
            }
        )

    @extend_schema(summary="Cancel a call", tags=["Calls"])
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a ringing call (caller only)."""
        call = self._get_call(pk)
        if not call:
            return Response(
                {"detail": _("Call not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        if call.caller != request.user:
            return Response(
                {"detail": _("Only the caller can cancel.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        if call.status != "ringing":
            return Response(
                {
                    "detail": _("Call is %(status)s, cannot cancel.")
                    % {"status": call.status}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        call.status = "cancelled"
        call.save(update_fields=["status", "updated_at"])

        return Response({"callId": str(call.id), "status": call.status})

    @extend_schema(
        summary="Incoming calls",
        description="Get ringing calls where the current user is the callee (for polling).",
        tags=["Calls"],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"])
    def incoming(self, request):
        """Return any ringing calls for the current user (callee side)."""
        calls = (
            Call.objects.filter(
                callee=request.user,
                status="ringing",
            )
            .select_related("caller")
            .order_by("-created_at")[:5]
        )

        results = []
        for c in calls:
            caller_name = ""
            try:
                caller_name = c.caller.display_name or c.caller.username or ""
            except Exception:
                logger.debug("Failed to get display name", exc_info=True)
            results.append(
                {
                    "callId": str(c.id),
                    "callerId": str(c.caller_id),
                    "callerName": caller_name,
                    "callType": c.call_type,
                    "createdAt": c.created_at.isoformat(),
                }
            )

        return Response(results)

    @extend_schema(
        summary="Call history",
        description="Get the user's call history (incoming, outgoing, missed).",
        tags=["Calls"],
        responses={200: CallHistorySerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def history(self, request):
        """Get call history for the current user."""
        from django.db.models import Q

        calls = (
            Call.objects.filter(Q(caller=request.user) | Q(callee=request.user))
            .select_related("caller", "callee")
            .order_by("-created_at")
        )
        page = self.paginate_queryset(calls)
        if page is not None:
            serializer = CallHistorySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = CallHistorySerializer(calls, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Get call status", tags=["Calls"])
    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        """Get the current status of a call (for polling)."""
        call = self._get_call(pk)
        if not call:
            return Response(
                {"detail": _("Call not found.")}, status=status.HTTP_404_NOT_FOUND
            )
        if request.user not in (call.caller, call.callee):
            return Response(
                {"detail": _("Not a participant.")}, status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {
                "callId": str(call.id),
                "status": call.status,
                "callType": call.call_type,
                "callerId": str(call.caller_id),
                "calleeId": str(call.callee_id),
                "startedAt": call.started_at.isoformat() if call.started_at else None,
            }
        )

    def _get_call(self, pk):
        try:
            pass

            return Call.objects.get(id=pk)
        except Call.DoesNotExist:
            return None

    def _notify_callee(self, call, caller):
        """Send FCM push notification to the callee about incoming call."""
        try:
            from apps.notifications.fcm_service import FCMService
            from apps.notifications.models import UserDevice

            devices = UserDevice.objects.filter(user=call.callee, is_active=True)
            tokens = [d.fcm_token for d in devices if d.fcm_token]
            if not tokens:
                return

            fcm = FCMService()
            caller_name = caller.display_name or caller.username or _("Someone")
            data = {
                "type": "incoming_call",
                "call_id": str(call.id),
                "channel_name": str(call.id),
                "caller_id": str(caller.id),
                "caller_name": caller_name,
                "call_type": call.call_type,
            }

            for token in tokens:
                try:
                    fcm.send_to_token(
                        token=token,
                        title=_("Incoming %(call_type)s call")
                        % {"call_type": call.call_type},
                        body=_("%(name)s is calling you") % {"name": caller_name},
                        data=data,
                    )
                except Exception:
                    logger.warning("Failed to send notification", exc_info=True)
        except Exception:
            logger.warning("Failed to send notification", exc_info=True)


# ─── Chat Memory ViewSet ──────────────────────────────────────────────


@extend_schema_view(
    list=extend_schema(
        summary="List chat memories",
        description="Get all active chat memories for the current user.",
        tags=["Chat Memory"],
        responses={200: ChatMemorySerializer(many=True)},
    ),
    destroy=extend_schema(
        summary="Delete a chat memory",
        description="Delete a specific chat memory by ID.",
        tags=["Chat Memory"],
        responses={204: None},
    ),
)
class ChatMemoryViewSet(viewsets.GenericViewSet):
    """
    ViewSet for managing AI chat memories.

    Provides list, delete, and clear-all operations for the
    user's persistent chat memories.
    """

    serializer_class = ChatMemorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ChatMemory.objects.filter(
            user=self.request.user,
            is_active=True,
        )

    def list(self, request):
        """List all active memories for the current user."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def destroy(self, request, pk=None):
        """Delete (deactivate) a specific memory."""
        try:
            memory = self.get_queryset().get(pk=pk)
        except ChatMemory.DoesNotExist:
            return Response(
                {"error": _("Memory not found.")}, status=status.HTTP_404_NOT_FOUND
            )
        memory.is_active = False
        memory.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Clear all chat memories",
        description="Deactivate all chat memories for the current user.",
        tags=["Chat Memory"],
        responses={200: OpenApiResponse(description="All memories cleared.")},
    )
    @action(detail=False, methods=["post"], url_path="clear")
    def clear_all(self, request):
        """Deactivate all memories for the current user."""
        count = self.get_queryset().update(is_active=False)
        return Response(
            {
                "cleared": count,
                "message": _("All memories have been cleared."),
            }
        )
