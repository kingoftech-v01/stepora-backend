"""
Views for Chat app (friend/buddy chat and calls only).

AI conversation features are in apps.ai.views.
"""

import logging

from django.conf import settings as django_settings
from django.db.models import Prefetch, Q
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.pagination import StandardResultsSetPagination

from .models import (
    Call,
    ChatConversation,
    ChatMessage,
    MessageReadStatus,
)
from .serializers import (
    CallHistorySerializer,
    ChatConversationDetailSerializer,
    ChatConversationSerializer,
    ChatMessageCreateSerializer,
    ChatMessageSerializer,
)

logger = logging.getLogger(__name__)


class FeatureFlagMixin:
    """Return 501 when a feature flag is disabled."""

    feature_flag = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        flag_name = self.feature_flag
        if flag_name and not getattr(django_settings, flag_name, False):
            from rest_framework.exceptions import APIException

            class FeatureComingSoon(APIException):
                status_code = 501
                default_detail = _("This feature is coming soon.")
                default_code = "coming_soon"

            raise FeatureComingSoon()


@extend_schema_view(
    list=extend_schema(
        summary="List chat conversations",
        description="Get all friend/buddy chat conversations for the current user",
        tags=["Chat"],
        responses={200: ChatConversationSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Get chat conversation",
        description="Get a specific chat conversation with messages",
        tags=["Chat"],
        responses={
            200: ChatConversationDetailSerializer,
            404: OpenApiResponse(description="Not found."),
        },
    ),
)
class ChatConversationViewSet(FeatureFlagMixin, viewsets.ReadOnlyModelViewSet):
    """List and retrieve friend/buddy chat conversations."""

    feature_flag = "USE_MESSAGES"
    permission_classes = [IsAuthenticated]
    ordering = ["-updated_at"]

    def get_queryset(self):
        """Get chat conversations for current user, including ones where they are the target."""
        if getattr(self, "swagger_fake_view", False):
            return ChatConversation.objects.none()

        user = self.request.user
        return (
            ChatConversation.objects.filter(
                Q(user=user)
                | Q(target_user=user)
                | Q(buddy_pairing__user1=user)
                | Q(buddy_pairing__user2=user)
            )
            .distinct()
            .prefetch_related(
                Prefetch(
                    "messages",
                    queryset=ChatMessage.objects.order_by("-created_at")[:1],
                    to_attr="_last_message_list",
                ),
                "read_statuses",
            )
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ChatConversationDetailSerializer
        return ChatConversationSerializer

    @extend_schema(
        summary="Start or get conversation",
        description="Get or create a chat conversation with another user.",
        tags=["Chat"],
        request=None,
        responses={
            200: ChatConversationSerializer,
            201: ChatConversationSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    @action(detail=False, methods=["post"], url_path="start")
    def start(self, request):
        """Get or create a chat conversation with another user."""
        target_user_id = request.data.get("target_user_id") or request.data.get(
            "user_id"
        )
        if not target_user_id:
            return Response(
                {"error": _("target_user_id is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.users.models import User

        try:
            target = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {"error": _("User not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        if target == request.user:
            return Response(
                {"error": _("Cannot chat with yourself.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Block enforcement
        from apps.social.models import BlockedUser

        if BlockedUser.is_blocked(request.user, target):
            return Response(
                {"error": _("Cannot chat with this user.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get or create conversation (check both directions)
        conv = ChatConversation.objects.filter(
            Q(user=request.user, target_user=target)
            | Q(user=target, target_user=request.user)
        ).first()

        if conv:
            serializer = ChatConversationSerializer(conv, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        conv = ChatConversation.objects.create(
            user=request.user,
            target_user=target,
            is_active=True,
        )
        serializer = ChatConversationSerializer(conv, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Send friend message",
        description="Send a text message in a friend chat (no AI).",
        tags=["Chat"],
        request=ChatMessageCreateSerializer,
        responses={
            201: ChatMessageSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="send-message",
    )
    def send_message(self, request, pk=None):
        """Send a message in a friend/buddy chat conversation (no AI)."""
        conversation = self.get_object()

        serializer = ChatMessageCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        content = serializer.validated_data["content"]

        # Save message
        msg = ChatMessage.objects.create(
            conversation=conversation,
            role="user",
            content=content,
            metadata={"sender_id": str(request.user.id)},
        )
        conversation.total_messages = (conversation.total_messages or 0) + 1
        conversation.save(update_fields=["total_messages", "updated_at"])

        # Broadcast via WebSocket
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()
            room = (
                f"buddy_chat_{conversation.buddy_pairing_id}"
                if conversation.buddy_pairing_id
                else f"chat_{conversation.id}"
            )
            async_to_sync(channel_layer.group_send)(
                room,
                {
                    "type": "chat_message",
                    "message": {
                        "id": str(msg.id),
                        "role": "user",
                        "content": content,
                        "sender_id": str(request.user.id),
                        "created_at": msg.created_at.isoformat(),
                    },
                },
            )
        except Exception:
            logger.debug("WebSocket broadcast failed", exc_info=True)

        return Response(ChatMessageSerializer(msg).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Get messages",
        description="Get all messages for a chat conversation",
        tags=["Chat"],
        responses={200: ChatMessageSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        """Get messages for a chat conversation."""
        conversation = self.get_object()
        messages = conversation.messages.all()

        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = ChatMessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Pin message",
        description="Pin/unpin a message in a chat conversation",
        tags=["Chat"],
        responses={200: ChatMessageSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path=r"pin-message/(?P<message_id>[0-9a-f-]+)",
    )
    def pin_message(self, request, pk=None, message_id=None):
        """Toggle pin on a chat message."""
        conversation = self.get_object()
        try:
            message = conversation.messages.get(id=message_id)
        except ChatMessage.DoesNotExist:
            return Response(
                {"error": _("Message not found.")}, status=status.HTTP_404_NOT_FOUND
            )
        message.is_pinned = not message.is_pinned
        message.save(update_fields=["is_pinned"])
        return Response(ChatMessageSerializer(message).data)

    @extend_schema(
        summary="Like message",
        description="Toggle like on a chat message",
        tags=["Chat"],
        responses={200: ChatMessageSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path=r"like-message/(?P<message_id>[0-9a-f-]+)",
    )
    def like_message(self, request, pk=None, message_id=None):
        """Toggle like on a chat message."""
        conversation = self.get_object()
        try:
            message = conversation.messages.get(id=message_id)
        except ChatMessage.DoesNotExist:
            return Response(
                {"error": _("Message not found.")}, status=status.HTTP_404_NOT_FOUND
            )
        message.is_liked = not message.is_liked
        message.save(update_fields=["is_liked"])
        return Response(ChatMessageSerializer(message).data)

    @extend_schema(
        summary="Mark conversation as read",
        description="Mark all messages in this chat conversation as read.",
        tags=["Chat"],
        responses={200: dict},
    )
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        """Mark chat conversation as read up to the latest message."""
        conversation = self.get_object()
        last_msg = conversation.messages.order_by("-created_at").first()

        read_status, _ = MessageReadStatus.objects.update_or_create(
            user=request.user,
            conversation=conversation,
            defaults={"last_read_message": last_msg},
        )

        return Response(
            {
                "status": "ok",
                "last_read_message_id": str(last_msg.id) if last_msg else None,
            }
        )


class CallViewSet(FeatureFlagMixin, viewsets.GenericViewSet):
    """Manage voice/video calls between buddies."""

    feature_flag = "USE_MESSAGES"
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Call.objects.none()
        return Call.objects.filter(
            Q(caller=self.request.user) | Q(callee=self.request.user)
        )

    @extend_schema(
        summary="Initiate a call",
        description="Create a call and notify the callee via FCM.",
        tags=["Calls"],
        responses={201: dict, 400: OpenApiResponse(description="Validation error")},
    )
    @action(detail=False, methods=["post"])
    def initiate(self, request):
        """Initiate a voice or video call."""
        callee_id = request.data.get("callee_id") or request.data.get("user_id")
        call_type = request.data.get("call_type", "voice")

        if not callee_id:
            return Response(
                {"detail": _("callee_id is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if call_type not in ("voice", "video"):
            return Response(
                {"detail": _("call_type must be voice or video.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.users.models import User

        try:
            callee = User.objects.get(id=callee_id)
        except User.DoesNotExist:
            return Response(
                {"detail": _("User not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        if callee == request.user:
            return Response(
                {"detail": _("Cannot call yourself.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Block enforcement
        from apps.social.models import BlockedUser

        if BlockedUser.is_blocked(request.user, callee):
            return Response(
                {"detail": _("Cannot call this user")}, status=status.HTTP_403_FORBIDDEN
            )

        # Find buddy pairing if one exists
        from apps.buddies.models import BuddyPairing

        pairing = BuddyPairing.objects.filter(
            Q(user1=request.user, user2=callee) | Q(user1=callee, user2=request.user),
            status="active",
        ).first()

        call = Call.objects.create(
            caller=request.user,
            callee=callee,
            call_type=call_type,
            status="ringing",
            buddy_pairing=pairing,
        )

        # Send FCM push to callee
        self._notify_callee(call, request.user)

        # Broadcast to buddy_chat WebSocket group so partner sees it in real-time
        if pairing:
            try:
                from asgiref.sync import async_to_sync
                from channels.layers import get_channel_layer

                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"buddy_chat_{pairing.id}",
                    {
                        "type": "call_started",
                        "call": {
                            "id": str(call.id),
                            "type": call_type,
                            "caller": str(request.user.id),
                        },
                    },
                )
            except Exception:
                logger.debug("WebSocket call broadcast failed", exc_info=True)

        return Response(
            {
                "call_id": str(call.id),
                "channel_name": str(call.id),
                "call_type": call.call_type,
                "status": call.status,
                "callee_id": str(callee.id),
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(summary="Accept a call", tags=["Calls"])
    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """Accept an incoming call."""
        call = self._get_call(pk)
        if not call:
            return Response(
                {"detail": _("Call not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        if call.callee != request.user:
            return Response(
                {"detail": _("Only the callee can accept.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        if call.status != "ringing":
            return Response(
                {
                    "detail": _("Call is %(status)s, cannot accept.")
                    % {"status": call.status}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone

        call.status = "accepted"
        call.started_at = timezone.now()
        call.save(update_fields=["status", "started_at", "updated_at"])

        return Response(
            {
                "call_id": str(call.id),
                "status": call.status,
                "started_at": call.started_at.isoformat(),
            }
        )

    @extend_schema(summary="Reject a call", tags=["Calls"])
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Reject an incoming call."""
        call = self._get_call(pk)
        if not call:
            return Response(
                {"detail": _("Call not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        if call.callee != request.user:
            return Response(
                {"detail": _("Only the callee can reject.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        call.status = "rejected"
        call.save(update_fields=["status", "updated_at"])

        # Notify the caller
        try:
            from django.utils import timezone as tz

            from apps.notifications.services import NotificationService

            callee_name = call.callee.display_name or _("Your buddy")
            NotificationService.create(
                user=call.caller,
                notification_type="buddy",
                title=_("%(name)s declined your call") % {"name": callee_name},
                body="",
                scheduled_for=tz.now(),
                data={"call_id": str(call.id), "type": "call_rejected"},
            )
        except Exception:
            logger.warning("Failed to send notification", exc_info=True)

        # Send WebSocket event to caller
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"notifications_{call.caller.id}",
                {
                    "type": "notification.message",
                    "data": {
                        "type": "call_rejected",
                        "call_id": str(call.id),
                        "callee_name": callee_name,
                    },
                },
            )
        except Exception:
            logger.debug("WebSocket broadcast failed", exc_info=True)

        return Response({"call_id": str(call.id), "status": call.status})

    @extend_schema(summary="End a call", tags=["Calls"])
    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        """End an active call."""
        call = self._get_call(pk)
        if not call:
            return Response(
                {"detail": _("Call not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        if request.user not in (call.caller, call.callee):
            return Response(
                {"detail": _("Not a participant.")}, status=status.HTTP_403_FORBIDDEN
            )

        from django.utils import timezone

        call.status = "completed"
        call.ended_at = timezone.now()
        if call.started_at:
            call.duration_seconds = int(
                (call.ended_at - call.started_at).total_seconds()
            )
        call.save(
            update_fields=["status", "ended_at", "duration_seconds", "updated_at"]
        )

        return Response(
            {
                "call_id": str(call.id),
                "status": call.status,
                "duration_seconds": call.duration_seconds,
            }
        )

    @extend_schema(summary="Cancel a call", tags=["Calls"])
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a ringing call (caller only)."""
        call = self._get_call(pk)
        if not call:
            return Response(
                {"detail": _("Call not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        if call.caller != request.user:
            return Response(
                {"detail": _("Only the caller can cancel.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        if call.status != "ringing":
            return Response(
                {
                    "detail": _("Call is %(status)s, cannot cancel.")
                    % {"status": call.status}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        call.status = "cancelled"
        call.save(update_fields=["status", "updated_at"])

        return Response({"call_id": str(call.id), "status": call.status})

    @extend_schema(
        summary="Incoming calls",
        description="Get ringing calls where the current user is the callee.",
        tags=["Calls"],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"])
    def incoming(self, request):
        """Return any ringing calls for the current user (callee side)."""
        calls = (
            Call.objects.filter(
                callee=request.user,
                status="ringing",
            )
            .select_related("caller")
            .order_by("-created_at")[:5]
        )

        results = []
        for c in calls:
            caller_name = ""
            try:
                caller_name = c.caller.display_name or c.caller.username or ""
            except Exception:
                logger.debug("Failed to get display name", exc_info=True)
            results.append(
                {
                    "call_id": str(c.id),
                    "caller_id": str(c.caller_id),
                    "caller_name": caller_name,
                    "call_type": c.call_type,
                    "created_at": c.created_at.isoformat(),
                }
            )

        return Response(results)

    @extend_schema(
        summary="Call history",
        description="Get the user's call history.",
        tags=["Calls"],
        responses={200: CallHistorySerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def history(self, request):
        """Get call history for the current user."""
        calls = (
            Call.objects.filter(Q(caller=request.user) | Q(callee=request.user))
            .select_related("caller", "callee")
            .order_by("-created_at")
        )
        page = self.paginate_queryset(calls)
        if page is not None:
            serializer = CallHistorySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = CallHistorySerializer(calls, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Get call status", tags=["Calls"])
    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        """Get the current status of a call."""
        call = self._get_call(pk)
        if not call:
            return Response(
                {"detail": _("Call not found.")}, status=status.HTTP_404_NOT_FOUND
            )
        if request.user not in (call.caller, call.callee):
            return Response(
                {"detail": _("Not a participant.")}, status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {
                "call_id": str(call.id),
                "status": call.status,
                "call_type": call.call_type,
                "caller_id": str(call.caller_id),
                "callee_id": str(call.callee_id),
                "started_at": call.started_at.isoformat() if call.started_at else None,
            }
        )

    def _get_call(self, pk):
        try:
            return Call.objects.get(id=pk)
        except Call.DoesNotExist:
            return None

    def _notify_callee(self, call, caller):
        """Send FCM push notification to the callee about incoming call."""
        try:
            from apps.notifications.fcm_service import FCMService
            from apps.notifications.models import UserDevice

            devices = UserDevice.objects.filter(user=call.callee, is_active=True)
            tokens = [d.fcm_token for d in devices if d.fcm_token]
            if not tokens:
                return

            fcm = FCMService()
            caller_name = caller.display_name or caller.username or _("Someone")
            data = {
                "type": "incoming_call",
                "call_id": str(call.id),
                "channel_name": str(call.id),
                "caller_id": str(caller.id),
                "caller_name": caller_name,
                "call_type": call.call_type,
            }

            for token in tokens:
                try:
                    fcm.send_to_token(
                        token=token,
                        title=_("Incoming %(call_type)s call")
                        % {"call_type": call.call_type},
                        body=_("%(name)s is calling you") % {"name": caller_name},
                        data=data,
                    )
                except Exception:
                    logger.warning("Failed to send notification", exc_info=True)
        except Exception:
            logger.warning("Failed to send notification", exc_info=True)
