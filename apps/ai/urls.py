"""
URLs for AI Coaching app.
"""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AIConversationViewSet,
    AIMessageViewSet,
    ChatMemoryViewSet,
    ConversationTemplateViewSet,
)

router = SimpleRouter()
router.register(r"conversations", AIConversationViewSet, basename="ai-conversation")
router.register(r"messages", AIMessageViewSet, basename="ai-message")
router.register(r"memories", ChatMemoryViewSet, basename="ai-chat-memory")
router.register(
    r"templates",
    ConversationTemplateViewSet,
    basename="ai-conversation-template",
)

urlpatterns = [
    path("", include(router.urls)),
]
