"""
Backward-compatibility shim. All tasks now live in apps.chat.tasks.
"""

from apps.chat.tasks import (  # noqa: F401
    extract_chat_memories,
    summarize_conversation,
    transcribe_voice_message,
)
