"""
Celery tasks for the AI Coaching app.

Handles async operations like voice message transcription,
conversation summarization, and chat memory extraction.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def transcribe_voice_message(self, message_id):
    """
    Transcribe a voice message using OpenAI Whisper.

    Downloads the audio from the message's audio_url, transcribes it,
    and saves the transcription back to the message.
    """
    import os
    import tempfile

    import requests

    from core.exceptions import OpenAIError
    from integrations.openai_service import OpenAIService

    from .models import AIMessage

    try:
        message = AIMessage.objects.get(id=message_id)
        if not message.audio_url:
            logger.warning(f"Message {message_id} has no audio_url, skipping.")
            return

        if message.transcription:
            logger.info(f"Message {message_id} already transcribed, skipping.")
            return

        # Validate audio URL to prevent SSRF (returns resolved IP to pin connection)
        from core.validators import validate_url_no_ssrf

        try:
            _validated_url, resolved_ip = validate_url_no_ssrf(message.audio_url)
        except Exception as e:
            logger.error(f"Invalid audio URL for message {message_id}: {e}")
            return

        # Download the audio file to a temp location
        # Pin to the resolved IP to prevent DNS rebinding attacks
        from urllib.parse import urlparse

        _parsed = urlparse(message.audio_url)
        _parsed.port or (443 if _parsed.scheme == "https" else 80)
        _pinned_url = message.audio_url
        if resolved_ip and _parsed.hostname:
            _pinned_url = message.audio_url.replace(_parsed.hostname, resolved_ip, 1)
        response = requests.get(
            _pinned_url,
            timeout=60,
            headers={"Host": _parsed.hostname} if resolved_ip else {},
            verify=True,
        )
        response.raise_for_status()

        # Determine file extension from content type
        content_type = response.headers.get("Content-Type", "")
        ext_map = {
            "audio/mpeg": ".mp3",
            "audio/mp4": ".m4a",
            "audio/wav": ".wav",
            "audio/webm": ".webm",
            "audio/ogg": ".ogg",
        }
        ext = ext_map.get(content_type, ".mp3")

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        try:
            ai_service = OpenAIService()
            result = ai_service.transcribe_audio(tmp_path)

            message.transcription = result["text"]
            message.save(update_fields=["transcription"])

            # Also update the message content if it was empty (voice-only message)
            if not message.content or message.content == "[Voice message]":
                message.content = result["text"]
                message.save(update_fields=["content"])

            logger.info(
                f"Transcribed message {message_id}: {len(result['text'])} chars"
            )

            # Auto-summarize after transcription if transcript is long enough
            if len(result["text"]) >= 50:
                try:
                    # Build conversation context from recent messages
                    recent_msgs = list(
                        message.conversation.messages.exclude(id=message.id).order_by(
                            "-created_at"
                        )[:5]
                    )
                    recent_msgs.reverse()
                    context = "\n".join(
                        f"{m.role}: {m.content[:200]}"
                        for m in recent_msgs
                        if m.content and m.content != "[Voice message]"
                    )

                    summary_result = ai_service.summarize_voice_note(
                        result["text"],
                        conversation_context=context,
                    )

                    # Store summary in message metadata
                    metadata = message.metadata or {}
                    metadata["voice_summary"] = summary_result
                    message.metadata = metadata
                    message.save(update_fields=["metadata"])

                    logger.info(f"Auto-summarized voice message {message_id}")
                except Exception as e:
                    logger.error(
                        f"Auto-summarization failed for {message_id}: {e}",
                        exc_info=True,
                    )

        finally:
            os.unlink(tmp_path)

    except AIMessage.DoesNotExist:
        logger.error(f"AIMessage {message_id} not found.")
    except OpenAIError as e:
        logger.error(f"OpenAI transcription error for {message_id}: {e}")
        raise self.retry(exc=e, countdown=30)
    except requests.RequestException as e:
        logger.error(f"Failed to download audio for {message_id}: {e}")
        raise self.retry(exc=e, countdown=30)
    except Exception as e:
        logger.error(f"Unexpected error transcribing {message_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=2)
def summarize_conversation(self, conversation_id):
    """
    Summarize an AI conversation after it reaches a message threshold.

    Triggered after every 20th message. Creates a ConversationSummary
    that is prepended to the API context window.
    """
    from core.exceptions import OpenAIError
    from integrations.openai_service import OpenAIService

    from .models import AIConversation, ConversationSummary

    try:
        conversation = AIConversation.objects.get(id=conversation_id)

        # Check AI background quota for the conversation owner
        from core.ai_usage import AIUsageTracker

        tracker = AIUsageTracker()
        allowed, _ = tracker.check_quota(conversation.user, "ai_background")
        if not allowed:
            logger.info(
                f"Skipping summarization for conversation {conversation_id}: background quota reached"
            )
            return

        messages = conversation.messages.order_by("created_at")

        # Find last summary end point
        last_summary = conversation.summaries.order_by("-created_at").first()
        if last_summary:
            messages = messages.filter(
                created_at__gt=last_summary.end_message.created_at
            )

        message_list = list(messages)
        if len(message_list) < 15:
            return  # Not enough messages to summarize

        # Build text for summarization
        text = "\n".join([f"{m.role}: {m.content}" for m in message_list])

        ai_service = OpenAIService()
        result = ai_service.chat(
            messages=[
                {
                    "role": "user",
                    "content": f"Summarize this conversation concisely, capturing key decisions, action items, and emotional context:\n\n{text}",
                }
            ],
            conversation_type="general",
            temperature=0.3,
            max_tokens=500,
        )

        ConversationSummary.objects.create(
            conversation=conversation,
            summary=result["content"],
            key_points=[],
            start_message=message_list[0],
            end_message=message_list[-1],
        )

        # Increment usage counter
        tracker.increment(conversation.user, "ai_background")

        logger.info(f"Summarized AI conversation {conversation_id}")

    except AIConversation.DoesNotExist:
        logger.error(f"AIConversation {conversation_id} not found.")
    except OpenAIError as e:
        logger.error(f"Summarization error for {conversation_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=2)
def extract_chat_memories(self, conversation_id):
    """
    Extract memorable facts and preferences from recent AI messages.

    Triggered after every 5th user message. Uses the AI to identify
    key information worth remembering across conversations.
    """
    from core.exceptions import OpenAIError
    from integrations.openai_service import OpenAIService

    from .models import AIConversation, ChatMemory

    try:
        conversation = AIConversation.objects.select_related("user").get(
            id=conversation_id
        )
        user = conversation.user

        # Check AI background quota
        from core.ai_usage import AIUsageTracker

        tracker = AIUsageTracker()
        allowed, _ = tracker.check_quota(user, "ai_background")
        if not allowed:
            logger.info(
                f"Skipping memory extraction for {conversation_id}: background quota reached"
            )
            return

        # Get last 10 messages for extraction
        recent_messages = list(conversation.messages.order_by("-created_at")[:10])
        if len(recent_messages) < 3:
            return  # Not enough messages to extract from

        recent_messages.reverse()  # Chronological order
        messages_for_api = [
            {"role": m.role, "content": m.content} for m in recent_messages
        ]

        # Get existing memories to avoid duplicates
        existing_memories = list(
            ChatMemory.objects.filter(user=user, is_active=True).values(
                "key", "content"
            )
        )

        ai_service = OpenAIService()
        new_memories = ai_service.extract_memories(messages_for_api, existing_memories)

        if not new_memories:
            logger.info(
                f"No new memories extracted from AI conversation {conversation_id}"
            )
            return

        # Cap total memories per user at 50
        current_count = ChatMemory.objects.filter(user=user, is_active=True).count()
        max_memories = 50
        if current_count >= max_memories:
            # Deactivate oldest low-importance memories to make room
            excess = current_count + len(new_memories) - max_memories
            if excess > 0:
                old_memories = ChatMemory.objects.filter(
                    user=user, is_active=True
                ).order_by("importance", "updated_at")[:excess]
                ChatMemory.objects.filter(id__in=[m.id for m in old_memories]).update(
                    is_active=False
                )

        # Create new memories
        created = 0
        for mem in new_memories:
            ChatMemory.objects.create(
                user=user,
                key=mem["key"],
                content=mem["content"],
                importance=mem["importance"],
                source_conversation=conversation,
            )
            created += 1

        # Increment background usage counter
        tracker.increment(user, "ai_background")

        logger.info(
            f"Extracted {created} memories from AI conversation {conversation_id}"
        )

    except AIConversation.DoesNotExist:
        logger.error(
            f"AIConversation {conversation_id} not found for memory extraction."
        )
    except OpenAIError as e:
        logger.error(f"Memory extraction error for {conversation_id}: {e}")
        raise self.retry(exc=e, countdown=60)
    except Exception as e:
        logger.error(f"Unexpected error extracting memories for {conversation_id}: {e}")
        raise self.retry(exc=e, countdown=60)
