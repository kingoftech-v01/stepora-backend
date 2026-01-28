"""
Views for Conversations app.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Conversation, Message
from .serializers import (
    ConversationSerializer, ConversationDetailSerializer, ConversationCreateSerializer,
    MessageSerializer, MessageCreateSerializer
)
from integrations.openai_service import OpenAIService
from core.exceptions import OpenAIError


class ConversationViewSet(viewsets.ModelViewSet):
    """CRUD operations for conversations."""

    permission_classes = [IsAuthenticated]
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

    @action(detail=True, methods=['post'])
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

        # Save user message
        conversation.add_message('user', user_message)

        # Get AI response
        ai_service = OpenAIService()

        try:
            # Get recent messages for context
            messages = conversation.get_messages_for_api(limit=20)

            # Get AI response
            response = ai_service.chat(
                messages=messages,
                conversation_type=conversation.conversation_type
            )

            # Save assistant message
            assistant_message = conversation.add_message(
                'assistant',
                response['content'],
                metadata={'tokens_used': response['tokens_used']}
            )

            return Response({
                'user_message': {
                    'role': 'user',
                    'content': user_message
                },
                'assistant_message': MessageSerializer(assistant_message).data,
                'conversation': ConversationSerializer(conversation).data
            })

        except OpenAIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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


class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to messages."""

    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer

    def get_queryset(self):
        """Get messages for current user's conversations."""
        return Message.objects.filter(conversation__user=self.request.user)
