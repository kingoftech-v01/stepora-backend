"""
Views for Conversations app.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from django.conf import settings
from django.http import JsonResponse

from .models import Conversation, Message, ConversationTemplate
from .serializers import (
    ConversationSerializer, ConversationDetailSerializer, ConversationCreateSerializer,
    MessageSerializer, MessageCreateSerializer, ConversationTemplateSerializer
)
from .tasks import transcribe_voice_message, summarize_conversation
from integrations.openai_service import OpenAIService
from core.exceptions import OpenAIError
from core.permissions import CanUseAI
from core.ai_validators import validate_chat_response, validate_function_call, AIValidationError, validate_ai_output_safety
from core.moderation import ContentModerationService
from core.throttles import AIRateThrottle, AIChatDailyThrottle, AIVoiceDailyThrottle
from core.ai_usage import AIUsageTracker


@extend_schema_view(
    list=extend_schema(summary="List conversations", description="Get all conversations for the current user", tags=["Conversations"]),
    create=extend_schema(summary="Create conversation", description="Create a new AI conversation", tags=["Conversations"]),
    retrieve=extend_schema(summary="Get conversation", description="Get a specific conversation with messages", tags=["Conversations"]),
    update=extend_schema(summary="Update conversation", description="Update a conversation", tags=["Conversations"]),
    partial_update=extend_schema(summary="Partial update conversation", description="Partially update a conversation", tags=["Conversations"]),
    destroy=extend_schema(summary="Delete conversation", description="Delete a conversation", tags=["Conversations"]),
)
class ConversationViewSet(viewsets.ModelViewSet):
    """CRUD operations for conversations. All AI conversation features require premium+."""

    permission_classes = [IsAuthenticated, CanUseAI]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['conversation_type', 'is_active']
    ordering = ['-updated_at']

    def get_queryset(self):
        """Get conversations for current user."""
        return Conversation.objects.filter(user=self.request.user).prefetch_related('messages')

    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action == 'create':
            return ConversationCreateSerializer
        elif self.action == 'retrieve':
            return ConversationDetailSerializer
        return ConversationSerializer

    def perform_create(self, serializer):
        """Create conversation with current user."""
        serializer.save(user=self.request.user)

    @extend_schema(summary="Send message", description="Send a message and get AI response", tags=["Conversations"], request=MessageCreateSerializer, responses={200: dict})
    @action(detail=True, methods=['post'], throttle_classes=[AIRateThrottle, AIChatDailyThrottle])
    def send_message(self, request, pk=None):
        """Send a message in the conversation."""
        conversation = self.get_object()

        # Validate message
        message_serializer = MessageCreateSerializer(data=request.data)
        if not message_serializer.is_valid():
            return Response(
                message_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        user_message = message_serializer.validated_data['content']

        # Content moderation check BEFORE saving or calling AI
        mod_result = ContentModerationService().moderate_text(user_message, context='chat')
        if mod_result.is_flagged:
            return Response(
                {'error': mod_result.user_message, 'moderation': True},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save user message
        conversation.add_message('user', user_message)

        # Get AI response
        ai_service = OpenAIService()

        try:
            # Get recent messages for context
            messages = conversation.get_messages_for_api(limit=20)

            # Get AI response
            raw_response = ai_service.chat(
                messages=messages,
                conversation_type=conversation.conversation_type
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
            AIUsageTracker().increment(request.user, 'ai_chat')

            # Save validated assistant message
            assistant_message = conversation.add_message(
                'assistant',
                validated.content,
                metadata={'tokens_used': validated.tokens_used}
            )

            # Handle function calls from AI (validate before executing)
            if raw_response.get('function_call'):
                try:
                    fc = validate_function_call(raw_response['function_call'])
                    assistant_message.metadata['function_call'] = fc.model_dump()
                    assistant_message.save(update_fields=['metadata'])
                except AIValidationError:
                    pass  # Ignore invalid function calls silently

            # Trigger summarization if threshold reached
            if conversation.total_messages % 20 == 0 and conversation.total_messages > 0:
                summarize_conversation.delay(str(conversation.id))

            return Response({
                'user_message': {
                    'role': 'user',
                    'content': user_message
                },
                'assistant_message': MessageSerializer(assistant_message).data,
                'conversation': ConversationSerializer(conversation).data
            })

        except AIValidationError as e:
            return Response(
                {'error': f'AI produced an invalid response: {e.message}'},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except OpenAIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(summary="Send voice message", description="Upload audio for transcription and AI response", tags=["Conversations"])
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser], url_path='send-voice', throttle_classes=[AIVoiceDailyThrottle])
    def send_voice(self, request, pk=None):
        """Send a voice message. Audio is transcribed via Whisper and AI responds."""
        import os
        from django.core.files.storage import default_storage

        conversation = self.get_object()
        audio_file = request.FILES.get('audio')
        if not audio_file:
            return Response({'error': 'No audio file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate file size (max 25MB — Whisper limit)
        if audio_file.size > 25 * 1024 * 1024:
            return Response({'error': 'Audio file too large. Max 25MB.'}, status=status.HTTP_400_BAD_REQUEST)

        # Save audio file
        file_path = f'voice_messages/{conversation.id}/{audio_file.name}'
        saved_path = default_storage.save(file_path, audio_file)
        audio_url = default_storage.url(saved_path)

        # Create message with audio_url
        message = conversation.add_message(
            'user',
            '[Voice message]',
            metadata={'type': 'voice'},
        )
        Message.objects.filter(id=message.id).update(audio_url=audio_url)

        # Increment voice usage counter
        AIUsageTracker().increment(request.user, 'ai_voice')

        # Queue async transcription
        transcribe_voice_message.delay(str(message.id))

        # Trigger summarization if threshold reached
        if conversation.total_messages % 20 == 0 and conversation.total_messages > 0:
            summarize_conversation.delay(str(conversation.id))

        return Response({
            'message': MessageSerializer(Message.objects.get(id=message.id)).data,
            'status': 'transcription_queued',
        }, status=status.HTTP_201_CREATED)

    @extend_schema(summary="Send image message", description="Upload image for GPT-4 Vision analysis", tags=["Conversations"])
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser], url_path='send-image', throttle_classes=[AIRateThrottle, AIChatDailyThrottle])
    def send_image(self, request, pk=None):
        """Send an image for GPT-4 Vision analysis in the conversation context."""
        from django.core.files.storage import default_storage

        conversation = self.get_object()
        image_file = request.FILES.get('image')
        user_prompt = request.data.get('prompt', '')

        if not image_file:
            return Response({'error': 'No image file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate file size (max 20MB)
        if image_file.size > 20 * 1024 * 1024:
            return Response({'error': 'Image too large. Max 20MB.'}, status=status.HTTP_400_BAD_REQUEST)

        # Moderate user prompt text if provided
        if user_prompt:
            mod_result = ContentModerationService().moderate_text(user_prompt, context='chat')
            if mod_result.is_flagged:
                return Response(
                    {'error': mod_result.user_message, 'moderation': True},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Save image
        file_path = f'chat_images/{conversation.id}/{image_file.name}'
        saved_path = default_storage.save(file_path, image_file)
        image_url = default_storage.url(saved_path)

        # Save user message with image
        user_content = user_prompt if user_prompt else '[Image shared]'
        user_message = conversation.add_message(
            'user', user_content,
            metadata={'type': 'image'},
        )
        Message.objects.filter(id=user_message.id).update(image_url=image_url)

        # Analyze image with GPT-4 Vision
        ai_service = OpenAIService()
        try:
            result = ai_service.analyze_image(image_url, user_prompt)

            # Increment AI usage counter
            AIUsageTracker().increment(request.user, 'ai_chat')

            assistant_message = conversation.add_message(
                'assistant',
                result['content'],
                metadata={'tokens_used': result['tokens_used'], 'type': 'image_analysis'},
            )

            return Response({
                'user_message': MessageSerializer(Message.objects.get(id=user_message.id)).data,
                'assistant_message': MessageSerializer(assistant_message).data,
            })

        except OpenAIError as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(summary="Get messages", description="Get all messages for a conversation", tags=["Conversations"], responses={200: MessageSerializer(many=True)})
    @action(detail=True, methods=['get'])
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

    @extend_schema(summary="Pin conversation", description="Pin/unpin a conversation", tags=["Conversations"], responses={200: ConversationSerializer})
    @action(detail=True, methods=['post'])
    def pin(self, request, pk=None):
        """Toggle pin status on a conversation."""
        conversation = self.get_object()
        conversation.is_pinned = not conversation.is_pinned
        conversation.save(update_fields=['is_pinned'])
        return Response(ConversationSerializer(conversation).data)

    @extend_schema(summary="Pin message", description="Pin/unpin a message in a conversation", tags=["Conversations"], responses={200: MessageSerializer})
    @action(detail=True, methods=['post'], url_path=r'pin-message/(?P<message_id>[0-9a-f-]+)')
    def pin_message(self, request, pk=None, message_id=None):
        """Toggle pin on a message."""
        conversation = self.get_object()
        try:
            message = conversation.messages.get(id=message_id)
        except Message.DoesNotExist:
            return Response({'error': 'Message not found.'}, status=status.HTTP_404_NOT_FOUND)
        message.is_pinned = not message.is_pinned
        message.save(update_fields=['is_pinned'])
        return Response(MessageSerializer(message).data)

    @extend_schema(summary="Like message", description="Toggle like on a message", tags=["Conversations"], responses={200: MessageSerializer})
    @action(detail=True, methods=['post'], url_path=r'like-message/(?P<message_id>[0-9a-f-]+)')
    def like_message(self, request, pk=None, message_id=None):
        """Toggle like on a message."""
        conversation = self.get_object()
        try:
            message = conversation.messages.get(id=message_id)
        except Message.DoesNotExist:
            return Response({'error': 'Message not found.'}, status=status.HTTP_404_NOT_FOUND)
        message.is_liked = not message.is_liked
        message.save(update_fields=['is_liked'])
        return Response(MessageSerializer(message).data)

    @extend_schema(summary="React to message", description="Add a reaction emoji to a message", tags=["Conversations"], responses={200: MessageSerializer})
    @action(detail=True, methods=['post'], url_path=r'react-message/(?P<message_id>[0-9a-f-]+)')
    def react_message(self, request, pk=None, message_id=None):
        """Add or remove a reaction on a message."""
        conversation = self.get_object()
        try:
            message = conversation.messages.get(id=message_id)
        except Message.DoesNotExist:
            return Response({'error': 'Message not found.'}, status=status.HTTP_404_NOT_FOUND)

        emoji = request.data.get('emoji', '')
        if not emoji:
            return Response({'error': 'emoji is required.'}, status=status.HTTP_400_BAD_REQUEST)

        reactions = message.reactions or []
        if emoji in reactions:
            reactions.remove(emoji)
        else:
            reactions.append(emoji)
        message.reactions = reactions
        message.save(update_fields=['reactions'])
        return Response(MessageSerializer(message).data)

    @extend_schema(summary="Search messages", description="Search messages within a conversation", tags=["Conversations"], responses={200: MessageSerializer(many=True)})
    @action(detail=True, methods=['get'])
    def search(self, request, pk=None):
        """Search messages within a conversation."""
        conversation = self.get_object()
        query = request.query_params.get('q', '').strip()
        if len(query) < 2:
            return Response({'messages': []})

        messages = conversation.messages.filter(
            content__icontains=query
        ).order_by('-created_at')[:50]
        return Response({'messages': MessageSerializer(messages, many=True).data})

    @extend_schema(summary="Export conversation", description="Export a conversation as JSON or PDF", tags=["Conversations"], responses={200: dict})
    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """Export conversation in JSON or PDF format."""
        conversation = self.get_object()
        export_format = request.query_params.get('format', 'json')

        messages = conversation.messages.order_by('created_at')

        if export_format == 'pdf':
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet
                import io
                from django.http import HttpResponse

                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter)
                styles = getSampleStyleSheet()
                story = []

                # Title
                story.append(Paragraph(
                    f"Conversation: {conversation.conversation_type}",
                    styles['Title']
                ))
                story.append(Spacer(1, 12))

                # Messages
                for msg in messages:
                    role_label = "You" if msg.role == 'user' else "DreamPlanner"
                    story.append(Paragraph(
                        f"<b>{role_label}</b> ({msg.created_at.strftime('%Y-%m-%d %H:%M')})",
                        styles['Heading4']
                    ))
                    # Escape special chars for reportlab
                    content = msg.content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(content, styles['Normal']))
                    story.append(Spacer(1, 8))

                doc.build(story)
                buffer.seek(0)

                response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="conversation_{conversation.id}.pdf"'
                return response

            except ImportError:
                return Response(
                    {'error': 'PDF export is not available. Install reportlab.'},
                    status=status.HTTP_501_NOT_IMPLEMENTED
                )

        # Default: JSON export
        data = {
            'conversation': {
                'id': str(conversation.id),
                'type': conversation.conversation_type,
                'created_at': conversation.created_at.isoformat(),
                'total_messages': conversation.total_messages,
            },
            'messages': [
                {
                    'role': msg.role,
                    'content': msg.content,
                    'created_at': msg.created_at.isoformat(),
                }
                for msg in messages
            ],
        }

        return Response(data)


@extend_schema_view(
    list=extend_schema(summary="List messages", description="Get all messages for the current user", tags=["Messages"]),
    retrieve=extend_schema(summary="Get message", description="Get a specific message", tags=["Messages"]),
)
class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to messages."""

    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer

    def get_queryset(self):
        """Get messages for current user's conversations."""
        return Message.objects.filter(conversation__user=self.request.user)


@extend_schema_view(
    list=extend_schema(summary="List conversation templates", description="Get all available conversation templates", tags=["Conversations"]),
    retrieve=extend_schema(summary="Get template", description="Get a specific conversation template", tags=["Conversations"]),
)
class ConversationTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to conversation templates."""

    permission_classes = [IsAuthenticated]
    serializer_class = ConversationTemplateSerializer
    queryset = ConversationTemplate.objects.filter(is_active=True)
