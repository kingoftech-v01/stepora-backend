"""
Backward-compatibility shim. All models now live in apps.chat.models.
"""

from apps.chat.models import (  # noqa: F401
    Call,
    ChatMemory,
    Conversation,
    ConversationBranch,
    ConversationSummary,
    ConversationTemplate,
    Message,
    MessageReadStatus,
)
