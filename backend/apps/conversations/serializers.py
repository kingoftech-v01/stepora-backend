"""
Serializers for Conversations app.
"""

from rest_framework import serializers
from .models import Conversation, Message, ConversationSummary


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model."""

    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'role', 'content',
            'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class MessageCreateSerializer(serializers.Serializer):
    """Serializer for creating/sending a message."""

    content = serializers.CharField(max_length=5000)

    def validate_content(self, value):
        """Validate message content."""
        if not value.strip():
            raise serializers.ValidationError("Message content cannot be empty")
        return value.strip()


class ConversationSerializer(serializers.ModelSerializer):
    """Basic serializer for Conversation model."""

    dream_title = serializers.CharField(source='dream.title', read_only=True, allow_null=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'user', 'dream', 'dream_title',
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
            'conversation_type', 'total_messages', 'total_tokens_used',
            'is_active', 'messages',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'total_messages', 'total_tokens_used', 'created_at', 'updated_at']


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


class ConversationSummarySerializer(serializers.ModelSerializer):
    """Serializer for Conversation summaries."""

    class Meta:
        model = ConversationSummary
        fields = [
            'id', 'conversation', 'summary', 'key_points',
            'start_message', 'end_message', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
