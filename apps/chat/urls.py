"""
URLs for Chat app (friend/buddy chat and calls only).
"""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .agora_views import agora_config, agora_rtc_token, agora_rtm_token
from .views import (
    CallViewSet,
    ChatConversationViewSet,
)

router = SimpleRouter()
router.register(r"calls", CallViewSet, basename="call")
router.register(r"", ChatConversationViewSet, basename="chat-conversation")

urlpatterns = [
    # Agora.io token endpoints
    path("agora/config/", agora_config, name="agora-config"),
    path("agora/rtm-token/", agora_rtm_token, name="agora-rtm-token"),
    path("agora/rtc-token/", agora_rtc_token, name="agora-rtc-token"),
    path("", include(router.urls)),
]
