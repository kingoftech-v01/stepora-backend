"""
URLs for Conversations app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConversationViewSet, MessageViewSet, ConversationTemplateViewSet

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'conversation-templates', ConversationTemplateViewSet, basename='conversation-template')

urlpatterns = [
    path('', include(router.urls)),
]
