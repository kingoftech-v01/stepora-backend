"""
Backward-compatibility shim. All agora views now live in apps.chat.agora_views.
"""

from apps.chat.agora_views import (  # noqa: F401
    agora_config,
    agora_rtc_token,
    agora_rtm_token,
)
