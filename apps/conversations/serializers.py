"""
Serializers for Conversations app.
"""

from typing import Optional

from rest_framework import serializers
from django.utils.translation import gettext as _
from core.sanitizers import sanitize_text
from .models import Conversation, Message, MessageReadStatus, ConversationSummary, ConversationTemplate, Call, ConversationBranch, ChatMemory


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model."""

    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'role', 'content',
            'audio_url', 'audio_duration', 'transcription', 'image_url',
            'is_pinned', 'is_liked', 'reactions',
            'branch', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the message.'},
            'conversation': {'help_text': 'Conversation this message belongs to.'},
            'role': {'help_text': 'Role of the message sender (user or assistant).'},
            'content': {'help_text': 'Text content of the message.'},
            'audio_url': {'help_text': 'URL to an attached audio recording.'},
            'audio_duration': {'help_text': 'Duration of the audio recording in seconds.'},
            'transcription': {'help_text': 'Transcription of the audio content.'},
            'image_url': {'help_text': 'URL to an attached image.'},
            'is_pinned': {'help_text': 'Whether this message is pinned.'},
            'is_liked': {'help_text': 'Whether the user liked this message.'},
            'reactions': {'help_text': 'Emoji reactions on this message.'},
            'branch': {'help_text': 'Branch this message belongs to (null = main).'},
            'metadata': {'help_text': 'Additional metadata for the message.'},
            'created_at': {'help_text': 'Timestamp when the message was created.'},
        }


class MessageCreateSerializer(serializers.Serializer):
    """Serializer for creating/sending a message."""

    content = serializers.CharField(max_length=5000, help_text='Text content of the message to send.')

    def validate_content(self, value):
        """Validate and sanitize message content."""
        if not value.strip():
            raise serializers.ValidationError(_("Message content cannot be empty"))
        return sanitize_text(value.strip())


class ConversationSerializer(serializers.ModelSerializer):
    """Basic serializer for Conversation model."""

    dream_title = serializers.CharField(source='dream.title', read_only=True, allow_null=True, help_text='Title of the linked dream.')
    last_message = serializers.SerializerMethodField(help_text='Preview of the most recent message.')
    unread_count = serializers.SerializerMethodField(help_text='Number of unread messages for the current user.')

    class Meta:
        model = Conversation
        fields = [
            'id', 'user', 'dream', 'dream_title',
            'title', 'is_pinned',
            'conversation_type', 'total_messages', 'total_tokens_used',
            'is_active', 'last_message', 'unread_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'total_messages', 'total_tokens_used', 'created_at', 'updated_at']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the conversation.'},
            'user': {'help_text': 'Owner of the conversation.'},
            'dream': {'help_text': 'Dream linked to this conversation.'},
            'title': {'help_text': 'Title of the conversation.'},
            'is_pinned': {'help_text': 'Whether the conversation is pinned.'},
            'conversation_type': {'help_text': 'Type of conversation (e.g., general, planning).'},
            'total_messages': {'help_text': 'Total number of messages in the conversation.'},
            'total_tokens_used': {'help_text': 'Total AI tokens consumed in this conversation.'},
            'is_active': {'help_text': 'Whether the conversation is still active.'},
            'created_at': {'help_text': 'Timestamp when the conversation was created.'},
            'updated_at': {'help_text': 'Timestamp when the conversation was last updated.'},
        }

    def get_last_message(self, obj) -> Optional[dict]:
        """Get the last message in the conversation."""
        # Use prefetched _last_message_list if available to avoid N+1
        if hasattr(obj, '_last_message_list'):
            last_msg = obj._last_message_list[0] if obj._last_message_list else None
        else:
            last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return {
                'role': last_msg.role,
                'content': last_msg.content[:100] + '...' if len(last_msg.content) > 100 else last_msg.content,
                'created_at': last_msg.created_at
            }
        return None

    def get_unread_count(self, obj) -> int:
        """Count messages after the user's last-read high-water mark."""
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return 0

        user_id_str = str(request.user.id)

        # Use prefetched read_statuses if available to avoid N+1
        read_status = None
        if hasattr(obj, '_prefetched_objects_cache') and 'read_statuses' in obj._prefetched_objects_cache:
            for rs in obj.read_statuses.all():
                if rs.user_id == request.user.id:
                    read_status = rs
                    break
        else:
            read_status = obj.read_statuses.filter(user=request.user).first()

        if read_status and read_status.last_read_message:
            return obj.messages.filter(
                created_at__gt=read_status.last_read_message.created_at
            ).exclude(
                metadata__sender_id=user_id_str
            ).exclude(role='system').count()

        # No read status or no last_read_message: count all non-own user messages
        return obj.messages.exclude(
            metadata__sender_id=user_id_str
        ).exclude(role='system').filter(role='user').count()


class ConversationDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Conversation with messages (latest 50)."""

    messages = serializers.SerializerMethodField(help_text='Latest messages in the conversation (max 50).')
    dream_title = serializers.CharField(source='dream.title', read_only=True, allow_null=True, help_text='Title of the linked dream.')

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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the conversation.'},
            'user': {'help_text': 'Owner of the conversation.'},
            'dream': {'help_text': 'Dream linked to this conversation.'},
            'title': {'help_text': 'Title of the conversation.'},
            'is_pinned': {'help_text': 'Whether the conversation is pinned.'},
            'conversation_type': {'help_text': 'Type of conversation (e.g., general, planning).'},
            'total_messages': {'help_text': 'Total number of messages in the conversation.'},
            'total_tokens_used': {'help_text': 'Total AI tokens consumed in this conversation.'},
            'is_active': {'help_text': 'Whether the conversation is still active.'},
            'created_at': {'help_text': 'Timestamp when the conversation was created.'},
            'updated_at': {'help_text': 'Timestamp when the conversation was last updated.'},
        }


    def get_messages(self, obj):
        """Return the latest 50 messages to prevent response bloat."""
        msgs = obj.messages.order_by('-created_at')[:50]
        return MessageSerializer(reversed(list(msgs)), many=True).data

    def validate_title(self, value):
        """Sanitize conversation title."""
        if value:
            return sanitize_text(value)
        return value


class ConversationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating conversations."""

    class Meta:
        model = Conversation
        fields = ['conversation_type', 'dream', 'title']
        extra_kwargs = {
            'conversation_type': {'help_text': 'Type of conversation to create.'},
            'dream': {'help_text': 'Dream to link to this conversation.'},
            'title': {'help_text': 'Optional title for the conversation.', 'required': False},
        }

    def validate_conversation_type(self, value):
        """Validate conversation type."""
        valid_types = [choice[0] for choice in Conversation.TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError(_("Invalid conversation type. Must be one of: %(types)s") % {'types': ', '.join(valid_types)})
        return value

    def validate(self, attrs):
        """Ensure dream-related conversations have a dream linked."""
        dream_required_types = {'dream_creation', 'planning', 'check_in', 'adjustment'}
        conv_type = attrs.get('conversation_type', 'general')
        dream = attrs.get('dream')

        if conv_type in dream_required_types and not dream:
            raise serializers.ValidationError(
                _("Conversations of type '%(type)s' must be linked to a dream. "
                  "Please provide a dream ID.") % {'type': conv_type}
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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the summary.'},
            'conversation': {'help_text': 'Conversation this summary belongs to.'},
            'summary': {'help_text': 'AI-generated summary of the conversation segment.'},
            'key_points': {'help_text': 'Key points extracted from the conversation.'},
            'start_message': {'help_text': 'First message covered by this summary.'},
            'end_message': {'help_text': 'Last message covered by this summary.'},
            'created_at': {'help_text': 'Timestamp when the summary was created.'},
        }


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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the template.'},
            'name': {'help_text': 'Display name of the template.'},
            'conversation_type': {'help_text': 'Type of conversation this template starts.'},
            'description': {'help_text': 'Brief description of the template purpose.'},
            'icon': {'help_text': 'Icon identifier for the template.'},
            'starter_messages': {'help_text': 'Pre-defined starter messages for the template.'},
            'is_active': {'help_text': 'Whether this template is currently available.'},
            'created_at': {'help_text': 'Timestamp when the template was created.'},
            'updated_at': {'help_text': 'Timestamp when the template was last updated.'},
        }


class MessageSearchSerializer(serializers.ModelSerializer):
    """Serializer for message search results with highlighted content excerpt."""

    excerpt = serializers.SerializerMethodField(help_text='Content excerpt with search term highlighted in <mark> tags.')

    class Meta:
        model = Message
        fields = ['id', 'role', 'content', 'excerpt', 'created_at']
        read_only_fields = ['id', 'role', 'content', 'excerpt', 'created_at']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the message.'},
            'role': {'help_text': 'Role of the message sender (user or assistant).'},
            'content': {'help_text': 'Full text content of the message.'},
            'created_at': {'help_text': 'Timestamp when the message was created.'},
        }

    def get_excerpt(self, obj):
        """Return a short excerpt of the content with the search query highlighted."""
        import re
        query = self.context.get('search_query', '')
        if not query:
            return obj.content[:120]

        content = obj.content
        # Find the position of the match (case-insensitive)
        match = re.search(re.escape(query), content, re.IGNORECASE)
        if not match:
            return content[:120]

        start = match.start()
        # Build excerpt window around the match
        excerpt_start = max(0, start - 40)
        excerpt_end = min(len(content), start + len(query) + 80)
        excerpt = content[excerpt_start:excerpt_end]

        if excerpt_start > 0:
            excerpt = '...' + excerpt
        if excerpt_end < len(content):
            excerpt = excerpt + '...'

        # Wrap matched text in <mark> tags (case-insensitive replace, first occurrence)
        highlighted = re.sub(
            '(' + re.escape(query) + ')',
            r'<mark>\1</mark>',
            excerpt,
            count=0,
            flags=re.IGNORECASE,
        )
        return highlighted


class ConversationBranchSerializer(serializers.ModelSerializer):
    """Serializer for ConversationBranch model."""

    message_count = serializers.SerializerMethodField(help_text='Number of messages in this branch.')

    class Meta:
        model = ConversationBranch
        fields = [
            'id', 'conversation', 'parent_message', 'name',
            'message_count', 'created_at'
        ]
        read_only_fields = ['id', 'conversation', 'created_at']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the branch.'},
            'conversation': {'help_text': 'Conversation this branch belongs to.'},
            'parent_message': {'help_text': 'Message from which this branch diverges.'},
            'name': {'help_text': 'Optional label for this branch.'},
            'created_at': {'help_text': 'Timestamp when the branch was created.'},
        }

    def get_message_count(self, obj) -> int:
        return obj.messages.count()


class CallHistorySerializer(serializers.ModelSerializer):
    """Serializer for call history entries."""

    caller_name = serializers.CharField(source='caller.display_name', read_only=True)
    callee_name = serializers.CharField(source='callee.display_name', read_only=True)
    caller_id = serializers.UUIDField(source='caller.id', read_only=True)
    callee_id = serializers.UUIDField(source='callee.id', read_only=True)

    class Meta:
        model = Call
        fields = [
            'id', 'caller_id', 'callee_id', 'caller_name', 'callee_name',
            'call_type', 'status', 'started_at', 'ended_at',
            'duration_seconds', 'created_at',
        ]
        read_only_fields = fields


class ChatMemorySerializer(serializers.ModelSerializer):
    """Serializer for ChatMemory model."""

    class Meta:
        model = ChatMemory
        fields = [
            'id', 'key', 'content', 'importance',
            'source_conversation', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'source_conversation', 'created_at', 'updated_at']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the memory.'},
            'key': {'help_text': 'Memory category (preference, fact, goal_context, style).'},
            'content': {'help_text': 'The remembered information.'},
            'importance': {'help_text': 'Importance level from 1 (low) to 5 (critical).'},
            'source_conversation': {'help_text': 'Conversation this memory was extracted from.'},
            'is_active': {'help_text': 'Whether this memory is currently active.'},
            'created_at': {'help_text': 'Timestamp when the memory was created.'},
            'updated_at': {'help_text': 'Timestamp when the memory was last updated.'},
        }
