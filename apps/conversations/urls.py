"""
URLs for Conversations app.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import ConversationViewSet, MessageViewSet, ConversationTemplateViewSet, CallViewSet
from .agora_views import agora_config, agora_rtm_token, agora_rtc_token

router = SimpleRouter()
router.register(r'calls', CallViewSet, basename='call')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'conversation-templates', ConversationTemplateViewSet, basename='conversation-template')
router.register(r'', ConversationViewSet, basename='conversation')

urlpatterns = [
    # Agora.io token endpoints
    path('agora/config/', agora_config, name='agora-config'),
    path('agora/rtm-token/', agora_rtm_token, name='agora-rtm-token'),
    path('agora/rtc-token/', agora_rtc_token, name='agora-rtc-token'),

    path('', include(router.urls)),
]
