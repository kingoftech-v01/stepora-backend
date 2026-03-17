"""
Backward-compatibility shim. All consumers now live in apps.chat.consumers.
"""

from apps.chat.consumers import (  # noqa: F401
    AIChatConsumer,
    BuddyChatConsumer,
    ChatConsumer,
)
