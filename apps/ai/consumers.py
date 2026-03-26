"""
WebSocket consumer for AI coach chat.

Uses shared mixins from core.consumers for rate limiting,
authentication, and moderation.
"""

import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import F
from django.utils import timezone

from core.ai_usage import AIUsageTracker
from core.consumers import (
    MAX_MSG_CONTENT_LEN,
    MAX_MSG_SIZE,
    AuthenticatedConsumerMixin,
    ConnectionLimitMixin,
    ModerationMixin,
    RateLimitMixin,
)
from core.exceptions import OpenAIError
from core.sanitizers import sanitize_text
from integrations.openai_service import OpenAIService

from .models import AIConversation, AIMessage
from .tasks import extract_chat_memories

logger = logging.getLogger(__name__)


class AIChatConsumer(
    RateLimitMixin,
    ConnectionLimitMixin,
    AuthenticatedConsumerMixin,
    ModerationMixin,
    AsyncWebsocketConsumer,
):
    """WebSocket consumer for AI coach conversations."""

    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"ai_chat_{self.conversation_id}"
        self._conversation_cache = None
        self._init_rate_limit()
        await self._init_auth()

        if self.user.is_authenticated:
            await self._setup_authenticated()
        elif self.scope.get("_allow_post_auth"):
            await self.accept()
        else:
            await self.close(code=4003)

    async def _setup_authenticated_inner(self):
        """Verify access, join room, send confirmation."""
        conversation = await self._load_and_verify_conversation()
        if not conversation:
            await self.close(code=4003)
            return

        self._conversation_cache = conversation

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection",
                    "status": "connected",
                    "conversation_id": self.conversation_id,
                }
            )
        )

    async def disconnect(self, close_code):
        await self._cancel_heartbeat()
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )

    async def receive(self, text_data):
        if len(text_data) > MAX_MSG_SIZE:
            await self.send_error("Message too large")
            return

        try:
            data = json.loads(text_data)
            message_type = data.get("type", "message")

            if message_type == "authenticate":
                await self._handle_authenticate_message(data)
                return

            if not self._authenticated:
                await self.send_error(
                    'Not authenticated. Send {"type": "authenticate", "token": "..."} first.'
                )
                return

            if self._is_rate_limited():
                await self.send_error("Rate limit exceeded. Please slow down.")
                return

            if message_type == "message":
                await self.handle_message(data)
            elif message_type == "function_call":
                await self.handle_explicit_function_call(data)
            elif message_type == "typing":
                await self.handle_typing(data)
            elif message_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))

        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception:
            logger.exception("AIChatConsumer.receive error")
            await self.send_error("An unexpected error occurred")

    async def handle_message(self, data):
        message_content = data.get("message", "").strip()

        if not message_content:
            await self.send_error("Message cannot be empty")
            return

        if len(message_content) > MAX_MSG_CONTENT_LEN:
            await self.send_error(
                f"Message exceeds {MAX_MSG_CONTENT_LEN} character limit"
            )
            return

        mod_result = await self._moderate_content(message_content)
        if mod_result.is_flagged:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "moderation",
                        "message": mod_result.user_message,
                    }
                )
            )
            return

        allowed, info = await self._check_ai_quota()
        if not allowed:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "quota_exceeded",
                        "message": f"Daily AI chat limit reached ({info['used']}/{info['limit']}). Resets at midnight.",
                        "usage": info,
                    }
                )
            )
            return

        user_message = await self.save_message("user", message_content)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": {
                    "id": str(user_message.id),
                    "role": "user",
                    "content": message_content,
                    "created_at": user_message.created_at.isoformat(),
                },
            },
        )

        await self.get_ai_response_stream(message_content)

    async def handle_typing(self, data):
        is_typing = data.get("is_typing", False)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_status",
                "user_id": str(self.user.id),
                "is_typing": is_typing,
            },
        )

    async def get_ai_response_stream(self, user_message):
        try:
            conversation = await self._get_conversation()
            messages = await self.get_messages_for_api(conversation)

            ai_service = OpenAIService()

            await self.send(text_data=json.dumps({"type": "stream_start"}))

            MAX_STREAM_LEN = 10000
            chunks = []
            total_len = 0
            async for chunk in ai_service.chat_stream_async(
                messages=messages,
                conversation_type=conversation.conversation_type,
            ):
                chunks.append(chunk)
                total_len += len(chunk)
                if total_len > MAX_STREAM_LEN:
                    break
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "stream_chunk",
                            "chunk": chunk,
                        }
                    )
                )

            full_response = "".join(chunks)[:MAX_STREAM_LEN]
            full_response = sanitize_text(full_response)

            output_safe = await self._check_ai_output_safety(full_response)
            if not output_safe:
                full_response = (
                    "I apologize, but I need to rephrase my response. "
                    "Could you tell me more about what specific aspect of your dream you'd like help with?"
                )

            await self.send(
                text_data=json.dumps(
                    {
                        "type": "stream_end",
                        "disclaimer": "AI-generated content may contain inaccuracies. Verify important information independently.",
                    }
                )
            )
            await self._increment_ai_quota()

            assistant_message = await self.save_message("assistant", full_response)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": {
                        "id": str(assistant_message.id),
                        "role": "assistant",
                        "content": full_response,
                        "created_at": assistant_message.created_at.isoformat(),
                    },
                },
            )

            # Trigger memory extraction every 5 user messages
            await self._maybe_extract_memories(conversation)

        except OpenAIError:
            logger.exception("AI service error in stream")
            await self.send_error("AI service is temporarily unavailable")
        except Exception:
            logger.exception("Unexpected error in AI stream")
            await self.send_error("An unexpected error occurred")

    async def handle_function_call(self, function_call, conversation):
        from apps.dreams.models import Dream, Goal, Task

        name = function_call["name"]
        args = function_call["arguments"]
        user = self.scope["user"]

        if name == "create_task":
            goal = await database_sync_to_async(
                lambda: Goal.objects.filter(dream__user=user, dream__status="active")
                .exclude(status="completed")
                .order_by("order")
                .first()
            )()
            if not goal:
                return {"success": False, "error": "No active goal found"}
            next_order = await database_sync_to_async(goal.tasks.count)()
            task = await database_sync_to_async(
                lambda: Task.objects.create(
                    goal=goal,
                    title=args["title"],
                    description=args.get("description", ""),
                    duration_mins=args.get("duration_mins", 30),
                    order=next_order,
                )
            )()
            return {"success": True, "task_id": str(task.id), "title": task.title}

        elif name == "complete_task":
            task = await database_sync_to_async(
                lambda: Task.objects.select_related("goal__dream__user")
                .filter(id=args["task_id"], goal__dream__user=user)
                .first()
            )()
            if not task:
                return {"success": False, "error": "Task not found"}
            await database_sync_to_async(task.complete)()
            return {"success": True, "task_id": str(task.id)}

        elif name == "create_goal":
            dream = await database_sync_to_async(
                lambda: Dream.objects.filter(id=args["dream_id"], user=user).first()
            )()
            if not dream:
                return {"success": False, "error": "Dream not found"}
            next_order = await database_sync_to_async(dream.goals.count)()
            goal = await database_sync_to_async(
                lambda: Goal.objects.create(
                    dream=dream,
                    title=args["title"],
                    description=args.get("description", ""),
                    order=args.get("order", next_order),
                )
            )()
            return {"success": True, "goal_id": str(goal.id), "title": goal.title}

        return {"success": False, "error": f"Unknown function: {name}"}

    async def handle_explicit_function_call(self, data):
        conversation = await self._get_conversation()
        messages = await self.get_messages_for_api(conversation)

        ai_service = OpenAIService()
        instruction = data.get(
            "instruction",
            "Based on our conversation, please take the appropriate action.",
        )

        # SECURITY: Moderate function_call instruction before sending to AI,
        # same as regular messages, to prevent moderation bypass.
        mod_result = await self._moderate_content(instruction)
        if mod_result.is_flagged:
            await self.send_error(
                mod_result.user_message or "Content flagged by moderation."
            )
            return

        messages.append({"role": "user", "content": instruction})

        try:
            result = await database_sync_to_async(ai_service.chat)(
                messages=messages,
                conversation_type=conversation.conversation_type,
                functions=OpenAIService.FUNCTION_DEFINITIONS,
            )

            if result.get("function_call"):
                fc_result = await self.handle_function_call(
                    result["function_call"], conversation
                )
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "function_result",
                            "function_name": result["function_call"]["name"],
                            "result": fc_result,
                            "ai_message": result.get("content", ""),
                        }
                    )
                )
                if result.get("content"):
                    await self.save_message("assistant", result["content"])
            else:
                if result.get("content"):
                    await self.save_message("assistant", result["content"])
                    await self.send(
                        text_data=json.dumps(
                            {
                                "type": "chat_message",
                                "message": {
                                    "role": "assistant",
                                    "content": result["content"],
                                },
                            }
                        )
                    )

        except Exception:
            logger.exception("Function call failed")
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "message": "Failed to process action request",
                    }
                )
            )

    # -- Channel layer handlers --

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message",
                    "message": event["message"],
                }
            )
        )

    async def typing_status(self, event):
        if str(event["user_id"]) != str(self.user.id):
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "typing",
                        "user_id": event["user_id"],
                        "is_typing": event["is_typing"],
                    }
                )
            )

    # -- Database methods --

    @database_sync_to_async
    def _load_and_verify_conversation(self):
        try:
            conversation = AIConversation.objects.select_related("user", "dream").get(
                id=self.conversation_id
            )
            if conversation.user_id != self.user.id:
                return None
            return conversation
        except AIConversation.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_conversation(self):
        if self._conversation_cache:
            return self._conversation_cache
        return AIConversation.objects.select_related("user", "dream").get(
            id=self.conversation_id
        )

    @database_sync_to_async
    def get_messages_for_api(self, conversation):
        return conversation.get_messages_for_api(limit=20)

    @database_sync_to_async
    def _check_ai_output_safety(self, content):
        from core.ai_validators import validate_ai_output_safety

        is_safe, _ = validate_ai_output_safety(content)
        return is_safe

    @database_sync_to_async
    def save_message(self, role, content):
        message = AIMessage.objects.create(
            conversation_id=self.conversation_id, role=role, content=content
        )
        AIConversation.objects.filter(id=self.conversation_id).update(
            total_messages=F("total_messages") + 1,
            updated_at=timezone.now(),
        )
        return message

    @database_sync_to_async
    def _maybe_extract_memories(self, conversation):
        """Trigger memory extraction every 5 user messages."""
        user_msg_count = conversation.messages.filter(role="user").count()
        if user_msg_count % 5 == 0 and user_msg_count > 0:
            extract_chat_memories.delay(str(conversation.id))

    @database_sync_to_async
    def _check_ai_quota(self):
        tracker = AIUsageTracker()
        return tracker.check_quota(self.user, "ai_chat")

    @database_sync_to_async
    def _increment_ai_quota(self):
        tracker = AIUsageTracker()
        return tracker.increment(self.user, "ai_chat")
