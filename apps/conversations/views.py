"""
Backward-compatibility shim. All views now live in apps.chat.views.
"""

from apps.chat.views import (  # noqa: F401
    CallViewSet,
    ChatMemoryViewSet,
    ConversationTemplateViewSet,
    ConversationViewSet,
    MessageViewSet,
)
