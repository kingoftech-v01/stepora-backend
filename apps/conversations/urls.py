"""
URLs for Conversations app.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import ConversationViewSet, MessageViewSet, ConversationTemplateViewSet

router = SimpleRouter()
router.register(r'', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'conversation-templates', ConversationTemplateViewSet, basename='conversation-template')

urlpatterns = [
    path('', include(router.urls)),
]
