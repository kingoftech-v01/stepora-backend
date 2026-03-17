"""
Backward-compatibility shim. All serializers now live in apps.chat.serializers.
"""

from apps.chat.serializers import (  # noqa: F401
    CallHistorySerializer,
    ChatMemorySerializer,
    ConversationBranchSerializer,
    ConversationCreateSerializer,
    ConversationDetailSerializer,
    ConversationSerializer,
    ConversationSummarySerializer,
    ConversationTemplateSerializer,
    MessageCreateSerializer,
    MessageSearchSerializer,
    MessageSerializer,
)
