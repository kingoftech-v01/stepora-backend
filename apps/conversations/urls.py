"""
URLs for Conversations app.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import ConversationViewSet, MessageViewSet, ConversationTemplateViewSet, CallViewSet

router = SimpleRouter()
router.register(r'calls', CallViewSet, basename='call')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'conversation-templates', ConversationTemplateViewSet, basename='conversation-template')
router.register(r'', ConversationViewSet, basename='conversation')

urlpatterns = [
    path('', include(router.urls)),
]
