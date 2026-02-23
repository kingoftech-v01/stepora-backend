"""
Serializers for Conversations app.
"""

from rest_framework import serializers
from core.sanitizers import sanitize_text
from .models import Conversation, Message, ConversationSummary, ConversationTemplate


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model."""

    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'role', 'content',
            'audio_url', 'transcription', 'image_url',
            'is_pinned', 'is_liked', 'reactions',
            'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class MessageCreateSerializer(serializers.Serializer):
    """Serializer for creating/sending a message."""

    content = serializers.CharField(max_length=5000)

    def validate_content(self, value):
        """Validate and sanitize message content."""
        if not value.strip():
            raise serializers.ValidationError("Message content cannot be empty")
        return sanitize_text(value.strip())


class ConversationSerializer(serializers.ModelSerializer):
    """Basic serializer for Conversation model."""

    dream_title = serializers.CharField(source='dream.title', read_only=True, allow_null=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'user', 'dream', 'dream_title',
            'title', 'is_pinned',
            'conversation_type', 'total_messages', 'total_tokens_used',
            'is_active', 'last_message',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'total_messages', 'total_tokens_used', 'created_at', 'updated_at']

    def get_last_message(self, obj):
        """Get the last message in the conversation."""
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return {
                'role': last_msg.role,
                'content': last_msg.content[:100] + '...' if len(last_msg.content) > 100 else last_msg.content,
                'created_at': last_msg.created_at
            }
        return None


class ConversationDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Conversation with messages."""

    messages = MessageSerializer(many=True, read_only=True)
    dream_title = serializers.CharField(source='dream.title', read_only=True, allow_null=True)

    class Meta:
        model = Conversation
        fields = [
            'id', 'user', 'dream', 'dream_title',
            'title', 'is_pinned',
            'conversation_type', 'total_messages', 'total_tokens_used',
            'is_active', 'messages',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'total_messages', 'total_tokens_used', 'created_at', 'updated_at']


    def validate_title(self, value):
        """Sanitize conversation title."""
        if value:
            return sanitize_text(value)
        return value


class ConversationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating conversations."""

    class Meta:
        model = Conversation
        fields = ['conversation_type', 'dream']

    def validate_conversation_type(self, value):
        """Validate conversation type."""
        valid_types = [choice[0] for choice in Conversation.TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid conversation type. Must be one of: {', '.join(valid_types)}")
        return value

    def validate(self, attrs):
        """Ensure dream-related conversations have a dream linked."""
        dream_required_types = {'dream_creation', 'planning', 'check_in', 'adjustment'}
        conv_type = attrs.get('conversation_type', 'general')
        dream = attrs.get('dream')

        if conv_type in dream_required_types and not dream:
            raise serializers.ValidationError(
                f"Conversations of type '{conv_type}' must be linked to a dream. "
                f"Please provide a dream ID."
            )
        return attrs


class ConversationSummarySerializer(serializers.ModelSerializer):
    """Serializer for Conversation summaries."""

    class Meta:
        model = ConversationSummary
        fields = [
            'id', 'conversation', 'summary', 'key_points',
            'start_message', 'end_message', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ConversationTemplateSerializer(serializers.ModelSerializer):
    """Serializer for ConversationTemplate model."""

    class Meta:
        model = ConversationTemplate
        fields = [
            'id', 'name', 'conversation_type', 'description',
            'icon', 'starter_messages', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
