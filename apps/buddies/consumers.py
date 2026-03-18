"""
Backward-compatibility shim. BuddyChatConsumer now lives in apps.chat.consumers.
"""

from apps.chat.consumers import BuddyChatConsumer  # noqa: F401

__all__ = ["BuddyChatConsumer"]
