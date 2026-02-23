"""
Celery tasks for the Conversations app.

Handles async operations like voice message transcription
and conversation summarization.
"""

import logging
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def transcribe_voice_message(self, message_id):
    """
    Transcribe a voice message using OpenAI Whisper.

    Downloads the audio from the message's audio_url, transcribes it,
    and saves the transcription back to the message.
    """
    from .models import Message
    from integrations.openai_service import OpenAIService
    from core.exceptions import OpenAIError
    import tempfile
    import requests
    import os

    try:
        message = Message.objects.get(id=message_id)
        if not message.audio_url:
            logger.warning(f"Message {message_id} has no audio_url, skipping.")
            return

        if message.transcription:
            logger.info(f"Message {message_id} already transcribed, skipping.")
            return

        # Download the audio file to a temp location
        response = requests.get(message.audio_url, timeout=60)
        response.raise_for_status()

        # Determine file extension from content type
        content_type = response.headers.get('Content-Type', '')
        ext_map = {
            'audio/mpeg': '.mp3',
            'audio/mp4': '.m4a',
            'audio/wav': '.wav',
            'audio/webm': '.webm',
            'audio/ogg': '.ogg',
        }
        ext = ext_map.get(content_type, '.mp3')

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        try:
            ai_service = OpenAIService()
            result = ai_service.transcribe_audio(tmp_path)

            message.transcription = result['text']
            message.save(update_fields=['transcription'])

            # Also update the message content if it was empty (voice-only message)
            if not message.content or message.content == '[Voice message]':
                message.content = result['text']
                message.save(update_fields=['content'])

            logger.info(f"Transcribed message {message_id}: {len(result['text'])} chars")

        finally:
            os.unlink(tmp_path)

    except Message.DoesNotExist:
        logger.error(f"Message {message_id} not found.")
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
    Summarize a conversation after it reaches a message threshold.

    Triggered after every 20th message. Creates a ConversationSummary
    that is prepended to the API context window.
    """
    from .models import Conversation, ConversationSummary
    from integrations.openai_service import OpenAIService
    from core.exceptions import OpenAIError

    try:
        conversation = Conversation.objects.get(id=conversation_id)

        # Check AI background quota for the conversation owner
        from core.ai_usage import AIUsageTracker
        tracker = AIUsageTracker()
        allowed, _ = tracker.check_quota(conversation.user, 'ai_background')
        if not allowed:
            logger.info(f"Skipping summarization for conversation {conversation_id}: background quota reached")
            return

        messages = conversation.messages.order_by('created_at')

        # Find last summary end point
        last_summary = conversation.summaries.order_by('-created_at').first()
        if last_summary:
            messages = messages.filter(created_at__gt=last_summary.end_message.created_at)

        message_list = list(messages)
        if len(message_list) < 15:
            return  # Not enough messages to summarize

        # Build text for summarization
        text = "\n".join([
            f"{m.role}: {m.content}" for m in message_list
        ])

        ai_service = OpenAIService()
        result = ai_service.chat(
            messages=[{
                'role': 'user',
                'content': f"Summarize this conversation concisely, capturing key decisions, action items, and emotional context:\n\n{text}",
            }],
            conversation_type='general',
            temperature=0.3,
            max_tokens=500,
        )

        ConversationSummary.objects.create(
            conversation=conversation,
            summary=result['content'],
            key_points=[],
            start_message=message_list[0],
            end_message=message_list[-1],
        )

        # Increment usage counter
        tracker.increment(conversation.user, 'ai_background')

        logger.info(f"Summarized conversation {conversation_id}")

    except Conversation.DoesNotExist:
        logger.error(f"Conversation {conversation_id} not found.")
    except OpenAIError as e:
        logger.error(f"Summarization error for {conversation_id}: {e}")
        raise self.retry(exc=e, countdown=60)
