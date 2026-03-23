"""
Views for the Buddies system.

Provides API endpoints for Dream Buddy pairing, including finding matches,
creating pairings, tracking progress, sending encouragement, and ending
partnerships. All endpoints require authentication.
"""

import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils import timezone as django_timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.models import User
from core.permissions import CanUseAI, CanUseBuddy
from core.sanitizers import sanitize_text

from .models import (
    AccountabilityContract,
    BuddyEncouragement,
    BuddyPairing,
    ContractCheckIn,
)
from .serializers import (
    AccountabilityContractSerializer,
    AIBuddyMatchSerializer,
    BuddyEncourageSerializer,
    BuddyHistorySerializer,
    BuddyMatchSerializer,
    BuddyPairingSerializer,
    BuddyPairRequestSerializer,
    BuddyProgressSerializer,
    ContractCheckInCreateSerializer,
    ContractCheckInSerializer,
    ContractProgressSerializer,
)

logger = logging.getLogger(__name__)


class BuddyViewSet(viewsets.GenericViewSet):
    """
    ViewSet for Dream Buddy management.

    Supports finding matches, creating pairings, viewing progress,
    sending encouragement, and ending pairings.
    All buddy features require a premium+ subscription.
    """

    permission_classes = [IsAuthenticated, CanUseBuddy]
    queryset = BuddyPairing.objects.all()
    serializer_class = BuddyPairingSerializer

    def _get_partner_data(self, user):
        """Build partner data dict from a User object."""
        level = user.level
        if level >= 50:
            title = "Legend"
        elif level >= 30:
            title = "Master"
        elif level >= 20:
            title = "Expert"
        elif level >= 10:
            title = "Achiever"
        elif level >= 5:
            title = "Explorer"
        else:
            title = "Dreamer"

        return {
            "id": user.id,
            "username": user.display_name or "Anonymous",
            "avatar": user.get_effective_avatar_url(),
            "title": title,
            "current_level": user.level,
            "influence_score": user.xp,
            "current_streak": user.streak_days,
        }

    def _get_active_pairing(self, user):
        """Find the user's current active buddy pairing."""
        return (
            BuddyPairing.objects.filter(Q(user1=user) | Q(user2=user), status="active")
            .select_related("user1", "user2")
            .first()
        )

    def _get_partner_user(self, pairing, user):
        """Get the partner user from a pairing."""
        return pairing.user2 if pairing.user1_id == user.id else pairing.user1

    @extend_schema(
        summary="Get current buddy",
        description=(
            "Retrieve the current user's active buddy pairing. "
            "Returns null buddy if no active pairing exists."
        ),
        responses={
            200: BuddyPairingSerializer,
            403: OpenApiResponse(description="Subscription required."),
        },
        tags=["Buddies"],
    )
    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        """Get the current active buddy pairing."""
        pairing = self._get_active_pairing(request.user)

        if not pairing:
            return Response({"buddy": None})

        partner = self._get_partner_user(pairing, request.user)

        # Calculate recent activity (tasks in last 7 days)
        week_ago = django_timezone.now() - timedelta(days=7)
        recent_tasks = 0
        try:
            from apps.dreams.models import Task

            recent_tasks = Task.objects.filter(
                dream__user=partner,
                dream__is_public=True,
                completed_at__gte=week_ago,
                status="completed",
            ).count()
        except (ImportError, Exception):
            logger.debug("Failed to compute shared interests", exc_info=True)
            recent_tasks = 0

        buddy_data = {
            "id": pairing.id,
            "partner": self._get_partner_data(partner),
            "compatibility_score": pairing.compatibility_score,
            "status": pairing.status,
            "recent_activity": recent_tasks,
            "encouragement_streak": pairing.encouragement_streak,
            "best_encouragement_streak": pairing.best_encouragement_streak,
            "created_at": pairing.created_at,
        }

        serializer = BuddyPairingSerializer(buddy_data)
        return Response({"buddy": serializer.data})

    @extend_schema(
        summary="Find or create buddy chat",
        description="Find or create a buddy_chat conversation with a specific user.",
        responses={
            200: OpenApiResponse(description="Conversation found or created."),
            404: OpenApiResponse(
                description="User not found or no active buddy pairing."
            ),
        },
        tags=["Buddies"],
    )
    @action(detail=False, methods=["post"], url_path="chat")
    def chat(self, request):
        """Find or create a buddy_chat conversation for the given user."""
        from apps.chat.models import ChatConversation as Conversation

        target_user_id = (
            request.data.get("user_id")
            or request.data.get("user_id")
            or request.data.get("target_user_id")
            or request.data.get("target_user_id")
        )

        if not target_user_id or target_user_id == "undefined":
            return Response(
                {"error": _("user_id is required.")}, status=status.HTTP_400_BAD_REQUEST
            )

        target_user = None
        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            pass

        # If not a user ID, maybe it's a conversation ID (from ConversationList)
        if not target_user:
            try:
                conv = Conversation.objects.get(id=target_user_id)
                # Find the buddy (the other user in the pairing)
                buddy_user = None
                if conv.buddy_pairing:
                    bp = conv.buddy_pairing
                    buddy_user = (
                        bp.user2 if bp.user1_id == request.user.id else bp.user1
                    )
                if not buddy_user and conv.user_id != request.user.id:
                    buddy_user = conv.user
                return Response(
                    {
                        "conversation_id": str(conv.id),
                        "buddy": {
                            "id": str(buddy_user.id) if buddy_user else "",
                            "display_name": (
                                buddy_user.display_name if buddy_user else ""
                            )
                            or "Buddy",
                            "is_online": buddy_user.is_online if buddy_user else False,
                            "level": buddy_user.level if buddy_user else 0,
                            "streak": buddy_user.streak_days if buddy_user else 0,
                        },
                    }
                )
            except Conversation.DoesNotExist:
                return Response(
                    {"error": _("User not found.")}, status=status.HTTP_404_NOT_FOUND
                )

        # Find active buddy pairing between the two users
        pairing = BuddyPairing.objects.filter(
            Q(user1=request.user, user2=target_user)
            | Q(user1=target_user, user2=request.user),
            status="active",
        ).first()

        # Look for existing buddy_chat conversation
        existing = None
        if pairing:
            existing = (
                Conversation.objects.filter(
                    buddy_pairing=pairing,
                )
                .filter(Q(user=request.user) | Q(user=target_user))
                .first()
            )

        if not existing:
            # Also try to find by user + type (no pairing link)
            existing = (
                Conversation.objects.filter(
                    user=request.user,
                )
                .filter(
                    Q(buddy_pairing__user1=target_user)
                    | Q(buddy_pairing__user2=target_user)
                )
                .first()
            )

        if existing:
            conv = existing
        else:
            # Create new buddy_chat conversation
            conv = Conversation.objects.create(
                user=request.user,
                title=target_user.display_name or "Buddy",
                buddy_pairing=pairing,
                total_messages=0,
            )
            # Store target user as a system message so send_message can resolve recipient
            from apps.chat.models import ChatMessage as Message

            Message.objects.create(
                conversation=conv,
                role="system",
                content="",
                metadata={"target_user_id": str(target_user.id)},
            )

        return Response(
            {
                "conversation_id": str(conv.id),
                "buddy": {
                    "id": str(target_user.id),
                    "display_name": target_user.display_name or "Buddy",
                    "is_online": target_user.is_online,
                    "level": target_user.level,
                    "streak": target_user.streak_days,
                },
            }
        )

    @extend_schema(
        summary="Send buddy chat message",
        description="Send a message in a buddy chat conversation (no AI).",
        responses={
            200: OpenApiResponse(description="Message sent."),
            404: OpenApiResponse(description="Conversation not found."),
        },
        tags=["Buddies"],
    )
    @action(detail=False, methods=["post"], url_path="send-message")
    def send_message(self, request):
        """Send a buddy chat message (REST fallback when WebSocket unavailable)."""
        from django.db.models import F

        from apps.chat.models import ChatConversation as Conversation
        from apps.chat.models import ChatMessage as Message

        conv_id = request.data.get("conversation_id") or request.data.get(
            "conversation_id"
        )
        content = sanitize_text((request.data.get("content") or "").strip())

        if not conv_id or conv_id == "undefined" or not content:
            return Response(
                {"error": _("conversation_id and content are required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Limit message length to prevent storage abuse
        if len(content) > 5000:
            return Response(
                {"error": _("Message too long. Maximum 5000 characters.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import uuid

        try:
            uuid.UUID(str(conv_id))
        except (ValueError, AttributeError):
            return Response(
                {"error": _("Invalid conversation_id.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            conv = Conversation.objects.get(id=conv_id)
        except Conversation.DoesNotExist:
            return Response(
                {"error": _("Conversation not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify user has access (is part of the buddy pairing or owns the conversation)
        has_access = conv.user_id == request.user.id
        if not has_access and conv.buddy_pairing:
            bp = conv.buddy_pairing
            has_access = request.user.id in (bp.user1_id, bp.user2_id)
        if not has_access:
            return Response(
                {"error": _("Access denied.")}, status=status.HTTP_403_FORBIDDEN
            )

        # Block enforcement: determine the other user and check
        other_user = None
        if conv.buddy_pairing:
            bp = conv.buddy_pairing
            other_user = bp.user2 if bp.user1_id == request.user.id else bp.user1
        elif conv.user_id != request.user.id:
            other_user = conv.user

        # Fallback: check the system message metadata for target_user_id
        if not other_user:
            from apps.chat.models import ChatMessage as ConvMessage

            sys_msg = (
                ConvMessage.objects.filter(
                    conversation=conv,
                    role="system",
                )
                .exclude(metadata={})
                .first()
            )
            if sys_msg and sys_msg.metadata and sys_msg.metadata.get("target_user_id"):
                try:
                    other_user = User.objects.get(id=sys_msg.metadata["target_user_id"])
                except User.DoesNotExist:
                    pass

        if not other_user:
            return Response(
                {
                    "error": _(
                        "Cannot determine recipient. The other user may no longer exist."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.social.models import BlockedUser

        if BlockedUser.is_blocked(request.user, other_user):
            return Response(
                {"detail": _("Cannot send message")}, status=status.HTTP_403_FORBIDDEN
            )

        msg = Message.objects.create(
            conversation=conv,
            role="user",
            content=content,
            metadata={"sender_id": str(request.user.id)},
        )
        Conversation.objects.filter(id=conv.id).update(
            total_messages=F("total_messages") + 1,
            updated_at=django_timezone.now(),
        )

        # Send push notification to the other user
        try:
            from apps.notifications.services import NotificationService

            NotificationService.create(
                user=other_user,
                notification_type="buddy",
                title=_("Message from %(name)s")
                % {"name": request.user.display_name or _("Your buddy")},
                body=content[:100],
                scheduled_for=django_timezone.now(),
                data={
                    "conversation_id": str(conv.id),
                    "sender_id": str(request.user.id),
                    "screen": "BuddyChat",
                },
            )
        except Exception:
            logger.warning("Failed to send buddy notification", exc_info=True)

        return Response(
            {
                "id": str(msg.id),
                "content": msg.content,
                "sender_id": str(request.user.id),
                "created_at": msg.created_at.isoformat(),
            }
        )

    @extend_schema(
        summary="Send buddy voice message",
        description="Upload a voice message in buddy chat. Audio is stored and the message is created.",
        responses={
            201: OpenApiResponse(description="Voice message sent."),
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Conversation not found."),
        },
        tags=["Buddies"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="send-voice",
        parser_classes=[MultiPartParser, FormParser],
    )
    def send_voice(self, request):
        """Send a voice message in buddy chat (file upload via multipart form data)."""
        import re
        import uuid as uuid_mod

        from django.core.files.storage import default_storage
        from django.db.models import F

        from apps.chat.models import ChatConversation as Conversation
        from apps.chat.models import ChatMessage as Message

        conv_id = request.data.get("conversation_id") or request.data.get(
            "conversation_id"
        )
        audio_file = request.FILES.get("audio")

        if not conv_id or conv_id == "undefined":
            return Response(
                {"error": _("conversation_id is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not audio_file:
            return Response(
                {"error": _("No audio file provided.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            uuid_mod.UUID(str(conv_id))
        except (ValueError, AttributeError):
            return Response(
                {"error": _("Invalid conversation_id.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate file size (max 25MB)
        if audio_file.size > 25 * 1024 * 1024:
            return Response(
                {"error": _("Audio file too large. Max 25MB.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate audio MIME type
        ALLOWED_AUDIO_TYPES = {
            "audio/mpeg",
            "audio/mp3",
            "audio/mp4",
            "audio/m4a",
            "audio/wav",
            "audio/x-wav",
            "audio/webm",
            "audio/ogg",
            "audio/flac",
            "audio/aac",
        }
        content_type = getattr(audio_file, "content_type", "")
        if content_type not in ALLOWED_AUDIO_TYPES:
            return Response(
                {
                    "error": _(
                        "Unsupported audio format. Allowed: mp3, m4a, wav, webm, ogg, flac, aac."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            conv = Conversation.objects.get(id=conv_id)
        except Conversation.DoesNotExist:
            return Response(
                {"error": _("Conversation not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify user has access
        has_access = conv.user_id == request.user.id
        if not has_access and conv.buddy_pairing:
            bp = conv.buddy_pairing
            has_access = request.user.id in (bp.user1_id, bp.user2_id)
        if not has_access:
            return Response(
                {"error": _("Access denied.")}, status=status.HTTP_403_FORBIDDEN
            )

        # Determine the other user and check blocks
        other_user = None
        if conv.buddy_pairing:
            bp = conv.buddy_pairing
            other_user = bp.user2 if bp.user1_id == request.user.id else bp.user1
        elif conv.user_id != request.user.id:
            other_user = conv.user
        if not other_user:
            from apps.chat.models import ChatMessage as ConvMessage

            sys_msg = (
                ConvMessage.objects.filter(
                    conversation=conv,
                    role="system",
                )
                .exclude(metadata={})
                .first()
            )
            if sys_msg and sys_msg.metadata and sys_msg.metadata.get("target_user_id"):
                try:
                    other_user = User.objects.get(id=sys_msg.metadata["target_user_id"])
                except User.DoesNotExist:
                    pass
        if not other_user:
            return Response(
                {"error": _("Cannot determine recipient.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.social.models import BlockedUser

        if BlockedUser.is_blocked(request.user, other_user):
            return Response(
                {"detail": _("Cannot send message")}, status=status.HTTP_403_FORBIDDEN
            )

        # Save audio file
        safe_name = re.sub(r"[^\w\-.]", "_", audio_file.name)[:100]
        file_path = f"voice_messages/{conv.id}/{safe_name}"
        saved_path = default_storage.save(file_path, audio_file)
        audio_url = default_storage.url(saved_path)

        # Parse optional duration
        audio_duration = None
        raw_duration = request.data.get("duration")
        if raw_duration is not None:
            try:
                audio_duration = int(raw_duration)
            except (ValueError, TypeError):
                pass

        # Create the message
        msg = Message.objects.create(
            conversation=conv,
            role="user",
            content="[Voice message]",
            audio_url=audio_url,
            audio_duration=audio_duration,
            metadata={"sender_id": str(request.user.id), "type": "voice"},
        )
        Conversation.objects.filter(id=conv.id).update(
            total_messages=F("total_messages") + 1,
            updated_at=django_timezone.now(),
        )

        # Send push notification
        try:
            from apps.notifications.services import NotificationService

            NotificationService.create(
                user=other_user,
                notification_type="buddy",
                title=_("Voice message from %(name)s")
                % {"name": request.user.display_name or _("Your buddy")},
                body=_("Sent a voice message"),
                scheduled_for=django_timezone.now(),
                data={
                    "conversation_id": str(conv.id),
                    "sender_id": str(request.user.id),
                    "screen": "BuddyChat",
                },
            )
        except Exception:
            logger.warning("Failed to send buddy voice notification", exc_info=True)

        return Response(
            {
                "id": str(msg.id),
                "content": msg.content,
                "audio_url": audio_url,
                "audio_duration": audio_duration,
                "sender_id": str(request.user.id),
                "created_at": msg.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Get buddy progress",
        description="Retrieve progress comparison between the current user and their buddy.",
        responses={
            200: BuddyProgressSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Buddies"],
    )
    @action(detail=True, methods=["get"], url_path="progress")
    def progress(self, request, pk=None):
        """Get progress comparison for a buddy pairing."""
        try:
            pairing = BuddyPairing.objects.select_related("user1", "user2").get(
                id=pk, status="active"
            )
        except BuddyPairing.DoesNotExist:
            return Response(
                {"error": _("Active buddy pairing not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        if pairing.user1_id != request.user.id and pairing.user2_id != request.user.id:
            return Response(
                {"error": _("You are not part of this pairing.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        partner = self._get_partner_user(pairing, request.user)

        week_ago = django_timezone.now() - timedelta(days=7)

        user_tasks_week = 0
        partner_tasks_week = 0
        try:
            from apps.dreams.models import Task

            user_tasks_week = Task.objects.filter(
                dream__user=request.user, completed_at__gte=week_ago, status="completed"
            ).count()
            partner_tasks_week = Task.objects.filter(
                dream__user=partner,
                dream__is_public=True,
                completed_at__gte=week_ago,
                status="completed",
            ).count()
        except (ImportError, Exception):
            logger.debug("Failed to compute shared interests", exc_info=True)

        progress_data = {
            "user": {
                "current_streak": request.user.streak_days,
                "tasks_this_week": user_tasks_week,
                "influence_score": request.user.xp,
            },
            "partner": {
                "current_streak": partner.streak_days,
                "tasks_this_week": partner_tasks_week,
                "influence_score": partner.xp,
            },
        }

        serializer = BuddyProgressSerializer(progress_data)
        return Response({"progress": serializer.data})

    @extend_schema(
        summary="Find a buddy match",
        description=(
            "Find a compatible buddy match based on shared interests and activity level."
        ),
        responses={
            200: BuddyMatchSerializer,
            400: OpenApiResponse(description="Already have an active buddy."),
            403: OpenApiResponse(description="Subscription required."),
        },
        tags=["Buddies"],
    )
    @action(detail=False, methods=["post"], url_path="find-match")
    def find_match(self, request):
        """Find a compatible buddy match."""
        existing = self._get_active_pairing(request.user)
        if existing:
            return Response(
                {"error": _("You already have an active buddy pairing.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find users without active pairings
        active_pairing_user_ids = set()
        active_pairings = BuddyPairing.objects.filter(status="active")
        for p in active_pairings:
            active_pairing_user_ids.add(p.user1_id)
            active_pairing_user_ids.add(p.user2_id)

        candidates = (
            User.objects.filter(is_active=True)
            .exclude(id__in=active_pairing_user_ids)
            .exclude(id=request.user.id)
            .order_by("-last_activity")[:50]
        )

        if not candidates.exists():
            return Response({"match": None})

        best_match = None
        best_score = 0.0
        user_level = request.user.level
        user_xp = request.user.xp

        for candidate in candidates:
            level_diff = abs(candidate.level - user_level)
            level_score = max(0.0, 1.0 - (level_diff / 50.0))
            xp_diff = abs(candidate.xp - user_xp)
            xp_score = max(0.0, 1.0 - (xp_diff / 10000.0))
            days_since_activity = (django_timezone.now() - candidate.last_activity).days
            activity_score = max(0.0, 1.0 - (days_since_activity / 30.0))
            score = (level_score * 0.3) + (xp_score * 0.3) + (activity_score * 0.4)

            if score > best_score:
                best_score = score
                best_match = candidate

        if not best_match:
            return Response({"match": None})

        shared_interests = []
        try:
            user_gam = request.user.gamification
            match_gam = best_match.gamification
            categories = [
                "health",
                "career",
                "relationships",
                "personal_growth",
                "finance",
                "hobbies",
            ]
            for cat in categories:
                user_xp_attr = getattr(user_gam, f"{cat}_xp", 0)
                match_xp_attr = getattr(match_gam, f"{cat}_xp", 0)
                if user_xp_attr > 0 and match_xp_attr > 0:
                    shared_interests.append(cat)
        except Exception:
            logger.debug("Failed to compute shared interests", exc_info=True)
            shared_interests = []

        match_data = {
            "user_id": best_match.id,
            "username": best_match.display_name or "Anonymous",
            "avatar": best_match.get_effective_avatar_url(),
            "compatibility_score": round(best_score, 2),
            "shared_interests": shared_interests,
        }

        serializer = BuddyMatchSerializer(match_data)
        return Response({"match": serializer.data})

    def _build_user_profile_for_ai(self, user):
        """Build a profile dict for AI compatibility scoring."""
        # Fetch user's active dream titles and categories
        dream_titles = []
        dream_categories = []
        try:
            from apps.dreams.models import Dream

            dreams = Dream.objects.filter(user=user, status="active").values_list(
                "title", "category"
            )
            for title, category in dreams:
                if title:
                    dream_titles.append(title)
                if category and category not in dream_categories:
                    dream_categories.append(category)
        except Exception:
            logger.debug("Failed to fetch dreams for AI profile", exc_info=True)

        # Determine activity level from streak and last activity
        days_since_activity = (django_timezone.now() - user.last_activity).days
        if days_since_activity <= 1 and user.streak_days >= 7:
            activity_level = "very active"
        elif days_since_activity <= 3 and user.streak_days >= 3:
            activity_level = "active"
        elif days_since_activity <= 7:
            activity_level = "moderate"
        else:
            activity_level = "low"

        return {
            "name": user.display_name or "Anonymous",
            "dreams": dream_titles[:10],
            "categories": dream_categories[:10],
            "activity_level": activity_level,
            "personality": user.dreamer_type or "unknown",
            "level": user.level,
            "streak": user.streak_days,
            "bio": user.bio or "",
        }

    @extend_schema(
        summary="AI-powered buddy matches",
        description=(
            "Find compatible buddies using AI scoring. Returns the top candidates "
            "scored by an AI model that considers dream alignment, activity levels, "
            "and personality compatibility. Requires premium+ subscription and AI access."
        ),
        responses={
            200: AIBuddyMatchSerializer(many=True),
            400: OpenApiResponse(description="Already have an active buddy."),
            403: OpenApiResponse(description="Subscription or AI access required."),
        },
        tags=["Buddies"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="ai-matches",
        permission_classes=[IsAuthenticated, CanUseBuddy, CanUseAI],
    )
    def ai_matches(self, request):
        """Find compatible buddies with AI-powered compatibility scoring."""
        existing = self._get_active_pairing(request.user)
        if existing:
            return Response(
                {"error": _("You already have an active buddy pairing.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find candidate users (same logic as find_match but get top 50)
        active_pairing_user_ids = set()
        active_pairings = BuddyPairing.objects.filter(status="active")
        for p in active_pairings:
            active_pairing_user_ids.add(p.user1_id)
            active_pairing_user_ids.add(p.user2_id)

        candidates = (
            User.objects.filter(is_active=True)
            .exclude(id__in=active_pairing_user_ids)
            .exclude(id=request.user.id)
            .order_by("-last_activity")[:50]
        )

        if not candidates.exists():
            return Response({"results": []})

        # Basic scoring to pick top 10 for AI scoring
        user_level = request.user.level
        user_xp = request.user.xp
        scored_candidates = []

        for candidate in candidates:
            level_diff = abs(candidate.level - user_level)
            level_score = max(0.0, 1.0 - (level_diff / 50.0))
            xp_diff = abs(candidate.xp - user_xp)
            xp_score = max(0.0, 1.0 - (xp_diff / 10000.0))
            days_since_activity = (django_timezone.now() - candidate.last_activity).days
            activity_score = max(0.0, 1.0 - (days_since_activity / 30.0))
            score = (level_score * 0.3) + (xp_score * 0.3) + (activity_score * 0.4)
            scored_candidates.append((candidate, score))

        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        top_candidates = scored_candidates[:10]

        # Build requesting user's profile once
        user_profile = self._build_user_profile_for_ai(request.user)

        # Score each candidate with AI
        from core.exceptions import OpenAIError
        from integrations.openai_service import OpenAIService

        ai_service = OpenAIService()
        ai_results = []

        for candidate, base_score in top_candidates:
            candidate_profile = self._build_user_profile_for_ai(candidate)
            try:
                ai_result = ai_service.score_buddy_compatibility(
                    user_profile, candidate_profile
                )
            except OpenAIError:
                logger.warning(
                    "AI scoring failed for candidate %s, using base score",
                    candidate.id,
                    exc_info=True,
                )
                ai_result = {
                    "compatibility_score": round(base_score, 2),
                    "reasons": [],
                    "shared_interests": [],
                    "potential_challenges": [],
                    "suggested_icebreaker": "Hey! Want to be accountability buddies?",
                }

            ai_results.append(
                {
                    "user_id": candidate.id,
                    "username": candidate.display_name or "Anonymous",
                    "avatar": candidate.get_effective_avatar_url(),
                    "bio": candidate.bio or "",
                    "level": candidate.level,
                    "streak": candidate.streak_days,
                    "xp": candidate.xp,
                    "dreamer_type": candidate.dreamer_type or "",
                    "compatibility_score": ai_result["compatibility_score"],
                    "reasons": ai_result["reasons"],
                    "shared_interests": ai_result["shared_interests"],
                    "potential_challenges": ai_result["potential_challenges"],
                    "suggested_icebreaker": ai_result["suggested_icebreaker"],
                    "dreams": candidate_profile["dreams"],
                    "categories": candidate_profile["categories"],
                }
            )

        # Sort by AI compatibility score descending
        ai_results.sort(key=lambda x: x["compatibility_score"], reverse=True)

        serializer = AIBuddyMatchSerializer(ai_results, many=True)
        return Response({"results": serializer.data})

    @extend_schema(
        summary="Create a buddy pairing",
        description="Pair with a specific user to become accountability buddies.",
        request=BuddyPairRequestSerializer,
        responses={
            201: OpenApiResponse(description="Buddy pairing created."),
            400: OpenApiResponse(
                description="Already have a buddy or invalid partner."
            ),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Buddies"],
    )
    @action(detail=False, methods=["post"], url_path="pair")
    def pair(self, request):
        """Create a buddy pairing with a specific user."""
        serializer = BuddyPairRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        partner_id = serializer.validated_data["partner_id"]

        if partner_id == request.user.id:
            return Response(
                {"error": _("You cannot pair with yourself.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = self._get_active_pairing(request.user)
        if existing:
            return Response(
                {"error": _("You already have an active buddy pairing.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            partner = User.objects.get(id=partner_id)
        except User.DoesNotExist:
            return Response(
                {"error": _("Partner user not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        partner_pairing = BuddyPairing.objects.filter(
            Q(user1=partner) | Q(user2=partner), status="active"
        ).exists()

        if partner_pairing:
            return Response(
                {"error": _("This user already has an active buddy pairing.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        level_diff = abs(partner.level - request.user.level)
        level_score = max(0.0, 1.0 - (level_diff / 50.0))
        xp_diff = abs(partner.xp - request.user.xp)
        xp_score = max(0.0, 1.0 - (xp_diff / 10000.0))
        compatibility = round((level_score + xp_score) / 2, 2)

        pairing = BuddyPairing.objects.create(
            user1=request.user,
            user2=partner,
            status="pending",
            compatibility_score=compatibility,
            expires_at=timezone.now() + timedelta(days=7),
        )

        return Response(
            {
                "message": _("Buddy pairing created with %(name)s.")
                % {"name": partner.display_name or _("user")},
                "pairing_id": str(pairing.id),
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Accept buddy pairing",
        description="Accept a pending buddy pairing request.",
        responses={
            200: OpenApiResponse(description="Pairing accepted."),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Pairing not found."),
        },
        tags=["Buddies"],
    )
    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, pk=None):
        """Accept a pending buddy pairing."""
        try:
            pairing = BuddyPairing.objects.get(
                id=pk, user2=request.user, status="pending"
            )
        except BuddyPairing.DoesNotExist:
            return Response(
                {"error": _("Pending buddy pairing not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        pairing.status = "active"
        pairing.save(update_fields=["status", "updated_at"])

        return Response({"message": _("Buddy pairing accepted.")})

    @extend_schema(
        summary="Reject buddy pairing",
        description="Reject a pending buddy pairing request.",
        responses={
            200: OpenApiResponse(description="Pairing rejected."),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Pairing not found."),
        },
        tags=["Buddies"],
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        """Reject a pending buddy pairing."""
        try:
            pairing = BuddyPairing.objects.get(
                id=pk, user2=request.user, status="pending"
            )
        except BuddyPairing.DoesNotExist:
            return Response(
                {"error": _("Pending buddy pairing not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        pairing.status = "cancelled"
        pairing.ended_at = django_timezone.now()
        pairing.save(update_fields=["status", "ended_at", "updated_at"])

        return Response({"message": _("Buddy pairing rejected.")})

    @extend_schema(
        summary="Send encouragement",
        description="Send an encouragement message to your buddy partner.",
        request=BuddyEncourageSerializer,
        responses={
            200: OpenApiResponse(description="Encouragement sent."),
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Pairing not found."),
        },
        tags=["Buddies"],
    )
    @action(detail=True, methods=["post"], url_path="encourage")
    def encourage(self, request, pk=None):
        """Send encouragement to a buddy with streak tracking."""
        try:
            pairing = BuddyPairing.objects.get(id=pk, status="active")
        except BuddyPairing.DoesNotExist:
            return Response(
                {"error": _("Active buddy pairing not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        if pairing.user1_id != request.user.id and pairing.user2_id != request.user.id:
            return Response(
                {"error": _("You are not part of this pairing.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BuddyEncourageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        BuddyEncouragement.objects.create(
            pairing=pairing,
            sender=request.user,
            message=serializer.validated_data.get("message", ""),
        )

        # Update encouragement streak
        now = django_timezone.now()
        if pairing.last_encouragement_at:
            days_since = (now.date() - pairing.last_encouragement_at.date()).days
            if days_since <= 1:
                if days_since == 1:
                    pairing.encouragement_streak += 1
            else:
                pairing.encouragement_streak = 1
        else:
            pairing.encouragement_streak = 1

        pairing.last_encouragement_at = now
        if pairing.encouragement_streak > pairing.best_encouragement_streak:
            pairing.best_encouragement_streak = pairing.encouragement_streak

        pairing.save(
            update_fields=[
                "encouragement_streak",
                "best_encouragement_streak",
                "last_encouragement_at",
                "updated_at",
            ]
        )

        # Determine the partner
        partner = (
            pairing.user2 if pairing.user1_id == request.user.id else pairing.user1
        )

        # Try to send a notification (best-effort)
        try:
            from apps.notifications.services import NotificationService

            NotificationService.create(
                user=partner,
                title=_("Buddy Encouragement"),
                body=serializer.validated_data.get("message", "")
                or _("%(name)s sent you encouragement!")
                % {"name": request.user.display_name or _("Your buddy")},
                notification_type="buddy",
                scheduled_for=now,
                status="sent",
                data={"pairing_id": str(pairing.id)},
            )
        except (ImportError, Exception):
            logger.warning("Failed to send buddy notification", exc_info=True)

        return Response(
            {
                "message": _("Encouragement sent to %(name)s.")
                % {"name": partner.display_name or _("your buddy")},
                "encouragement_streak": pairing.encouragement_streak,
                "best_encouragement_streak": pairing.best_encouragement_streak,
            }
        )

    @extend_schema(
        summary="End buddy pairing",
        description="End an active buddy pairing. Sets status to cancelled.",
        responses={
            200: OpenApiResponse(description="Pairing ended."),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Pairing not found."),
        },
        tags=["Buddies"],
    )
    def destroy(self, request, pk=None):
        """End a buddy pairing."""
        try:
            pairing = BuddyPairing.objects.get(id=pk, status="active")
        except BuddyPairing.DoesNotExist:
            return Response(
                {"error": _("Active buddy pairing not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        if pairing.user1_id != request.user.id and pairing.user2_id != request.user.id:
            return Response(
                {"error": _("You are not part of this pairing.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        pairing.status = "cancelled"
        pairing.ended_at = django_timezone.now()
        pairing.save(update_fields=["status", "ended_at", "updated_at"])

        return Response({"message": _("Buddy pairing ended.")})

    @extend_schema(
        summary="Buddy pairing history",
        description="Get the user's past buddy pairings with stats.",
        responses={
            200: BuddyHistorySerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
        },
        tags=["Buddies"],
    )
    @action(detail=False, methods=["get"], url_path="history")
    def history(self, request):
        """Get past buddy pairings with stats."""
        pairings = (
            BuddyPairing.objects.filter(
                Q(user1=request.user) | Q(user2=request.user),
            )
            .select_related("user1", "user2")
            .order_by("-created_at")
        )

        results = []
        for pairing in pairings:
            partner = self._get_partner_user(pairing, request.user)
            encouragement_count = pairing.encouragements.count()
            duration_days = None
            if pairing.ended_at:
                duration_days = (pairing.ended_at - pairing.created_at).days

            results.append(
                {
                    "id": pairing.id,
                    "partner": self._get_partner_data(partner),
                    "status": pairing.status,
                    "compatibility_score": pairing.compatibility_score,
                    "encouragement_count": encouragement_count,
                    "encouragement_streak": pairing.encouragement_streak,
                    "best_encouragement_streak": pairing.best_encouragement_streak,
                    "duration_days": duration_days,
                    "created_at": pairing.created_at,
                    "ended_at": pairing.ended_at,
                }
            )

        serializer = BuddyHistorySerializer(results, many=True)
        return Response({"pairings": serializer.data})


class ContractViewSet(viewsets.GenericViewSet):
    """
    ViewSet for Buddy Accountability Contracts.

    Supports creating contracts, accepting them, submitting check-ins,
    and viewing progress comparisons between both partners.
    """

    permission_classes = [IsAuthenticated, CanUseBuddy]
    queryset = AccountabilityContract.objects.all()
    serializer_class = AccountabilityContractSerializer

    def _get_user_pairings(self, user):
        """Get all active buddy pairing IDs for a user."""
        return BuddyPairing.objects.filter(
            Q(user1=user) | Q(user2=user), status="active"
        )

    def _get_partner_user(self, pairing, user):
        """Get the partner user from a pairing."""
        return pairing.user2 if pairing.user1_id == user.id else pairing.user1

    @extend_schema(
        summary="List accountability contracts",
        description=(
            "Retrieve all active accountability contracts for the current user's "
            "buddy pairings."
        ),
        responses={
            200: AccountabilityContractSerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
        },
        tags=["Buddies"],
    )
    def list(self, request):
        """List active contracts for the current user's buddy pairings."""
        pairing_ids = self._get_user_pairings(request.user).values_list("id", flat=True)

        contracts = (
            AccountabilityContract.objects.filter(
                pairing_id__in=pairing_ids,
            )
            .select_related("pairing", "created_by")
            .order_by("-created_at")
        )

        # Allow filtering by status (default: show active only)
        status_filter = request.query_params.get("status", "active")
        if status_filter != "all":
            contracts = contracts.filter(status=status_filter)

        results = []
        for contract in contracts:
            results.append(
                {
                    "id": contract.id,
                    "pairing_id": contract.pairing_id,
                    "title": contract.title,
                    "description": contract.description,
                    "goals": contract.goals,
                    "check_in_frequency": contract.check_in_frequency,
                    "start_date": contract.start_date,
                    "end_date": contract.end_date,
                    "status": contract.status,
                    "created_by_id": contract.created_by_id,
                    "accepted_by_partner": contract.accepted_by_partner,
                    "created_at": contract.created_at,
                }
            )

        serializer = AccountabilityContractSerializer(results, many=True)
        return Response({"contracts": serializer.data})

    @extend_schema(
        summary="Create accountability contract",
        description="Create a new accountability contract within a buddy pairing.",
        request=AccountabilityContractSerializer,
        responses={
            201: AccountabilityContractSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Pairing not found."),
        },
        tags=["Buddies"],
    )
    def create(self, request):
        """Create a new accountability contract."""
        serializer = AccountabilityContractSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pairing_id = serializer.validated_data.get("pairing_id")

        # Verify the pairing exists and is active
        try:
            pairing = BuddyPairing.objects.get(id=pairing_id, status="active")
        except BuddyPairing.DoesNotExist:
            return Response(
                {"error": _("Active buddy pairing not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify user is part of this pairing
        if pairing.user1_id != request.user.id and pairing.user2_id != request.user.id:
            return Response(
                {"error": _("You are not part of this pairing.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        contract = AccountabilityContract.objects.create(
            pairing=pairing,
            title=serializer.validated_data["title"],
            description=serializer.validated_data.get("description", ""),
            goals=serializer.validated_data["goals"],
            check_in_frequency=serializer.validated_data.get(
                "check_in_frequency", "weekly"
            ),
            start_date=serializer.validated_data["start_date"],
            end_date=serializer.validated_data["end_date"],
            created_by=request.user,
        )

        # Notify the partner
        partner = self._get_partner_user(pairing, request.user)
        try:
            from apps.notifications.services import NotificationService

            NotificationService.create(
                user=partner,
                notification_type="buddy",
                title=_("New Accountability Contract"),
                body=_("%(name)s created a contract: %(title)s")
                % {
                    "name": request.user.display_name or _("Your buddy"),
                    "title": contract.title,
                },
                scheduled_for=django_timezone.now(),
                data={
                    "contract_id": str(contract.id),
                    "pairing_id": str(pairing.id),
                    "screen": "AccountabilityContract",
                },
            )
        except Exception:
            logger.warning("Failed to send contract notification", exc_info=True)

        result = {
            "id": contract.id,
            "pairing_id": contract.pairing_id,
            "title": contract.title,
            "description": contract.description,
            "goals": contract.goals,
            "check_in_frequency": contract.check_in_frequency,
            "start_date": contract.start_date,
            "end_date": contract.end_date,
            "status": contract.status,
            "created_by_id": contract.created_by_id,
            "accepted_by_partner": contract.accepted_by_partner,
            "created_at": contract.created_at,
        }

        return Response(
            {"contract": AccountabilityContractSerializer(result).data},
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Accept accountability contract",
        description="Partner accepts an accountability contract.",
        responses={
            200: OpenApiResponse(description="Contract accepted."),
            400: OpenApiResponse(description="Already accepted."),
            403: OpenApiResponse(
                description="Not the partner or subscription required."
            ),
            404: OpenApiResponse(description="Contract not found."),
        },
        tags=["Buddies"],
    )
    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, pk=None):
        """Accept an accountability contract (partner only)."""
        try:
            contract = AccountabilityContract.objects.select_related("pairing").get(
                id=pk, status="active"
            )
        except AccountabilityContract.DoesNotExist:
            return Response(
                {"error": _("Active contract not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        pairing = contract.pairing

        # Verify user is part of this pairing
        if pairing.user1_id != request.user.id and pairing.user2_id != request.user.id:
            return Response(
                {"error": _("You are not part of this pairing.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Only the partner (not the creator) can accept
        if contract.created_by_id == request.user.id:
            return Response(
                {
                    "error": _(
                        "You created this contract. Only your partner can accept it."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if contract.accepted_by_partner:
            return Response(
                {"error": _("Contract already accepted.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contract.accepted_by_partner = True
        contract.save(update_fields=["accepted_by_partner"])

        # Notify the creator
        try:
            from apps.notifications.services import NotificationService

            NotificationService.create(
                user=contract.created_by,
                notification_type="buddy",
                title=_("Contract Accepted"),
                body=_("%(name)s accepted your contract: %(title)s")
                % {
                    "name": request.user.display_name or _("Your buddy"),
                    "title": contract.title,
                },
                scheduled_for=django_timezone.now(),
                data={
                    "contract_id": str(contract.id),
                    "screen": "AccountabilityContract",
                },
            )
        except Exception:
            logger.warning(
                "Failed to send contract acceptance notification", exc_info=True
            )

        return Response({"message": _("Contract accepted.")})

    @extend_schema(
        summary="Submit contract check-in",
        description="Submit a progress check-in for an accountability contract.",
        request=ContractCheckInCreateSerializer,
        responses={
            201: ContractCheckInSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(
                description="Not part of the pairing or subscription required."
            ),
            404: OpenApiResponse(description="Contract not found."),
        },
        tags=["Buddies"],
    )
    @action(detail=True, methods=["post"], url_path="check-in")
    def check_in(self, request, pk=None):
        """Submit a check-in for a contract."""
        try:
            contract = AccountabilityContract.objects.select_related("pairing").get(
                id=pk, status="active"
            )
        except AccountabilityContract.DoesNotExist:
            return Response(
                {"error": _("Active contract not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        pairing = contract.pairing

        # Verify user is part of this pairing
        if pairing.user1_id != request.user.id and pairing.user2_id != request.user.id:
            return Response(
                {"error": _("You are not part of this pairing.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ContractCheckInCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        check_in = ContractCheckIn.objects.create(
            contract=contract,
            user=request.user,
            progress=serializer.validated_data.get("progress", {}),
            note=serializer.validated_data.get("note", ""),
            mood=serializer.validated_data.get("mood", ""),
        )

        # Notify the partner
        partner = self._get_partner_user(pairing, request.user)
        try:
            from apps.notifications.services import NotificationService

            NotificationService.create(
                user=partner,
                notification_type="buddy",
                title=_("Buddy Check-In"),
                body=_('%(name)s checked in on "%(title)s"')
                % {
                    "name": request.user.display_name or _("Your buddy"),
                    "title": contract.title,
                },
                scheduled_for=django_timezone.now(),
                data={
                    "contract_id": str(contract.id),
                    "screen": "AccountabilityContract",
                },
            )
        except Exception:
            logger.warning("Failed to send check-in notification", exc_info=True)

        result = {
            "id": check_in.id,
            "user_id": check_in.user_id,
            "username": request.user.display_name or request.user.email,
            "progress": check_in.progress,
            "note": check_in.note,
            "mood": check_in.mood,
            "created_at": check_in.created_at,
        }

        return Response(
            {"check_in": ContractCheckInSerializer(result).data},
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="View contract progress",
        description="View both partners' progress for an accountability contract.",
        responses={
            200: ContractProgressSerializer,
            403: OpenApiResponse(
                description="Not part of the pairing or subscription required."
            ),
            404: OpenApiResponse(description="Contract not found."),
        },
        tags=["Buddies"],
    )
    @action(detail=True, methods=["get"], url_path="progress")
    def progress(self, request, pk=None):
        """View progress for both partners on a contract."""
        try:
            contract = AccountabilityContract.objects.select_related(
                "pairing", "pairing__user1", "pairing__user2", "created_by"
            ).get(id=pk)
        except AccountabilityContract.DoesNotExist:
            return Response(
                {"error": _("Contract not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        pairing = contract.pairing

        # Verify user is part of this pairing
        if pairing.user1_id != request.user.id and pairing.user2_id != request.user.id:
            return Response(
                {"error": _("You are not part of this pairing.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Fetch check-ins for both users
        all_check_ins = (
            ContractCheckIn.objects.filter(contract=contract)
            .select_related("user")
            .order_by("-created_at")
        )

        user_check_ins = []
        partner_check_ins = []

        for ci in all_check_ins:
            entry = {
                "id": ci.id,
                "user_id": ci.user_id,
                "username": ci.user.display_name or ci.user.email,
                "progress": ci.progress,
                "note": ci.note,
                "mood": ci.mood,
                "created_at": ci.created_at,
            }
            if ci.user_id == request.user.id:
                user_check_ins.append(entry)
            else:
                partner_check_ins.append(entry)

        # Aggregate totals per goal
        goals = contract.goals or []
        user_totals = {}
        partner_totals = {}

        for i in range(len(goals)):
            idx = str(i)
            user_totals[idx] = 0
            partner_totals[idx] = 0

        for ci in all_check_ins:
            progress = ci.progress or {}
            totals = user_totals if ci.user_id == request.user.id else partner_totals
            for key, value in progress.items():
                if key in totals:
                    try:
                        totals[key] += float(value)
                    except (ValueError, TypeError):
                        pass

        contract_data = {
            "id": contract.id,
            "pairing_id": contract.pairing_id,
            "title": contract.title,
            "description": contract.description,
            "goals": contract.goals,
            "check_in_frequency": contract.check_in_frequency,
            "start_date": contract.start_date,
            "end_date": contract.end_date,
            "status": contract.status,
            "created_by_id": contract.created_by_id,
            "accepted_by_partner": contract.accepted_by_partner,
            "created_at": contract.created_at,
        }

        result = {
            "contract": contract_data,
            "user_check_ins": user_check_ins,
            "partner_check_ins": partner_check_ins,
            "user_totals": user_totals,
            "partner_totals": partner_totals,
        }

        serializer = ContractProgressSerializer(result)
        return Response(serializer.data)
