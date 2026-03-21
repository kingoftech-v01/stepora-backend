"""
Views for Users app.
Authentication is handled by core.auth at /api/auth/ endpoints.
"""

import csv
import io
import logging
import os
import secrets
import uuid as uuid_mod
from datetime import timedelta

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)

from core.ai_usage import AIUsageTracker
from core.audit import log_account_change, log_data_export
from core.permissions import CanUseAI
from core.throttles import (
    AICheckinRateThrottle,
    AIMotivationRateThrottle,
    AINotificationTimingRateThrottle,
    ExportRateThrottle,
    TwoFactorRateThrottle,
)

from .models import (
    Achievement,
    DailyActivity,
    EmailChangeRequest,
    GamificationProfile,
    User,
    UserAchievement,
)
from .serializers import (
    GamificationProfileSerializer,
    UserProfileSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from .two_factor import _hash_code as hash_backup_code


@extend_schema_view(
    list=extend_schema(
        summary="List users",
        description="Get user list (current user only)",
        tags=["Users"],
    ),
    retrieve=extend_schema(
        summary="Get user", description="Get a specific user", tags=["Users"]
    ),
    update=extend_schema(
        summary="Update user", description="Update a user", tags=["Users"]
    ),
    partial_update=extend_schema(
        summary="Partial update user",
        description="Partially update a user",
        tags=["Users"],
    ),
    destroy=extend_schema(
        summary="Delete user", description="Delete a user", tags=["Users"]
    ),
)
class UserViewSet(viewsets.ModelViewSet):
    """User management endpoints."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    queryset = User.objects.all()

    def get_queryset(self):
        """Filter to only allow users to see their own data."""
        if getattr(self, "swagger_fake_view", False):
            return User.objects.none()
        return User.objects.filter(id=self.request.user.id)

    def retrieve(self, request, *args, **kwargs):
        """Get a user's public profile by ID, respecting profile_visibility."""
        user_id = kwargs.get("pk")
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": _("User not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        # Enforce profile_visibility setting
        from apps.social.models import Friendship

        if target_user != request.user:
            visibility = target_user.profile_visibility or "public"
            if visibility == "private":
                return Response(
                    {"error": _("This profile is private.")},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if visibility == "friends":
                is_friend_check = Friendship.objects.filter(
                    Q(user1=request.user, user2=target_user)
                    | Q(user1=target_user, user2=request.user),
                    status="accepted",
                ).exists()
                if not is_friend_check:
                    return Response(
                        {"error": _("This profile is visible to friends only.")},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        # Return public profile data (no email, no private settings)
        from apps.dreams.models import Dream

        # Only return public dreams (with id + title + progress for clickable cards)
        public_dreams_qs = Dream.objects.filter(
            user=target_user, status="active", is_public=True
        ).values("id", "title", "category", "progress_percentage")[:10]
        dreams = [
            {
                "id": str(d["id"]),
                "title": d["title"],
                "category": d["category"],
                "progress": d["progress_percentage"],
            }
            for d in public_dreams_qs
        ]
        categories = list(
            Dream.objects.filter(user=target_user, status="active", is_public=True)
            .values_list("category", flat=True)
            .distinct()
        )
        friend_count = Friendship.objects.filter(
            Q(user1=target_user) | Q(user2=target_user), status="accepted"
        ).count()
        mutual = 0
        if request.user != target_user:
            my_friend_ids = set(
                Friendship.objects.filter(
                    Q(user1=request.user) | Q(user2=request.user), status="accepted"
                ).values_list("user1_id", "user2_id")
            )
            my_friends = set()
            for u1, u2 in my_friend_ids:
                my_friends.add(u1)
                my_friends.add(u2)
            my_friends.discard(request.user.id)
            their_friend_ids = set(
                Friendship.objects.filter(
                    Q(user1=target_user) | Q(user2=target_user), status="accepted"
                ).values_list("user1_id", "user2_id")
            )
            their_friends = set()
            for u1, u2 in their_friend_ids:
                their_friends.add(u1)
                their_friends.add(u2)
            their_friends.discard(target_user.id)
            mutual = len(my_friends & their_friends)

        is_friend = Friendship.objects.filter(
            Q(user1=request.user, user2=target_user)
            | Q(user1=target_user, user2=request.user),
            status="accepted",
        ).exists()

        return Response(
            {
                "id": str(target_user.id),
                "display_name": target_user.display_name,
                "name": target_user.display_name,
                "initial": (target_user.display_name or "U")[0].upper(),
                "bio": target_user.bio or "",
                "location": target_user.location or "",
                "avatar_url": target_user.get_effective_avatar_url(),
                "level": target_user.level,
                "xp": target_user.xp,
                "streak": target_user.streak_days,
                "is_online": target_user.is_online,
                "is_friend": is_friend,
                "mutual_friends": mutual,
                "friend_count": friend_count,
                "dreams": dreams,
                "categories": categories,
                "date_joined": (
                    target_user.created_at.strftime("%b %Y")
                    if target_user.created_at
                    else ""
                ),
            }
        )

    @extend_schema(
        summary="Get current user",
        description="Get the current authenticated user's profile",
        tags=["Users"],
        responses={
            200: UserProfileSerializer,
            404: OpenApiResponse(description="Resource not found."),
        },
    )
    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user profile."""
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    @extend_schema(
        summary="Update profile",
        description="Update the current user's profile",
        tags=["Users"],
        request=UserUpdateSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    @action(detail=False, methods=["put", "patch"])
    def update_profile(self, request):
        """Update current user profile."""
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(UserSerializer(request.user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Get gamification profile",
        description="Get the current user's gamification profile with XP and levels",
        tags=["Users"],
        responses={
            200: GamificationProfileSerializer,
            404: OpenApiResponse(description="Resource not found."),
        },
    )
    @action(detail=False, methods=["get"])
    def gamification(self, request):
        """Get gamification profile."""
        profile, created = GamificationProfile.objects.get_or_create(user=request.user)
        serializer = GamificationProfileSerializer(profile)
        return Response(serializer.data)

    @extend_schema(
        summary="Get AI usage",
        description="Get the current user's AI usage quotas for today",
        tags=["Users"],
        responses={200: dict, 404: OpenApiResponse(description="Resource not found.")},
    )
    @action(detail=False, methods=["get"], url_path="ai-usage")
    def ai_usage(self, request):
        """Get current user's AI usage and remaining quotas for today."""
        tracker = AIUsageTracker()
        usage = tracker.get_usage(request.user)
        reset_time = tracker.get_reset_time()

        return Response(
            {
                "date": timezone.now().date().isoformat(),
                "usage": usage,
                "plan": getattr(request.user, "subscription", "free"),
                "resets_at": reset_time.isoformat(),
            }
        )

    @extend_schema(
        summary="Upload avatar",
        description="Upload an avatar image for the current user.",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"avatar": {"type": "string", "format": "binary"}},
            }
        },
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
        tags=["Users"],
    )
    @action(
        detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser]
    )
    def upload_avatar(self, request):
        """Upload avatar image for the current user."""
        avatar_file = request.FILES.get("avatar")
        if not avatar_file:
            return Response(
                {"error": _("No avatar file provided.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate file type by content-type header
        allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
        if avatar_file.content_type not in allowed_types:
            return Response(
                {"error": _("Invalid file type. Allowed: JPEG, PNG, GIF, WebP.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate file size (5MB max)
        if avatar_file.size > 5 * 1024 * 1024:
            return Response(
                {"error": _("File too large. Maximum size is 5MB.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate file magic bytes (prevent content-type spoofing)
        magic_signatures = {
            b"\xff\xd8\xff": "image/jpeg",
            b"\x89PNG": "image/png",
            b"GIF87a": "image/gif",
            b"GIF89a": "image/gif",
            b"RIFF": "image/webp",  # WebP starts with RIFF
        }
        header = avatar_file.read(12)
        avatar_file.seek(0)
        valid_magic = any(header.startswith(sig) for sig in magic_signatures)
        if not valid_magic:
            return Response(
                {"error": _("File content does not match an allowed image format.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        # Delete old avatar image if exists
        if user.avatar_image:
            user.avatar_image.delete(save=False)

        # Sanitize filename: use UUID to prevent path traversal
        ext = os.path.splitext(avatar_file.name)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            ext = ".jpg"
        avatar_file.name = f"{uuid_mod.uuid4().hex}{ext}"

        user.avatar_image = avatar_file
        user.save(update_fields=["avatar_image"])

        # Sync avatar_url with the newly uploaded image URL so that all
        # serializers (social feed, stories, comments, etc.) that read
        # avatar_url return the correct value.
        try:
            user.avatar_url = user.avatar_image.url
            user.save(update_fields=["avatar_url"])
        except Exception:
            pass  # Non-blocking — avatar_image is already saved

        return Response(UserSerializer(user, context={"request": request}).data)

    @extend_schema(
        summary="Get user statistics",
        description="Get comprehensive statistics for the current user",
        tags=["Users"],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get user statistics."""
        from apps.dreams.models import Task

        user = request.user

        stats = {
            "level": user.level,
            "xp": user.xp,
            "xp_to_next_level": 100 - (user.xp % 100),
            "streak_days": user.streak_days,
            "total_dreams": user.dreams.count(),
            "active_dreams": user.dreams.filter(status="active").count(),
            "completed_dreams": user.dreams.filter(status="completed").count(),
            "total_tasks_completed": Task.objects.filter(
                goal__dream__user=user, status="completed"
            ).count(),
        }

        return Response(stats)

    @extend_schema(
        summary="Delete account",
        description="Soft-delete the current user's account. Requires password confirmation. "
        "Anonymizes personal data, deactivates the account, and schedules hard-delete after 30 days.",
        responses={
            200: OpenApiResponse(description="Account scheduled for deletion."),
            400: OpenApiResponse(description="Validation error."),
        },
        tags=["Users"],
    )
    @action(detail=False, methods=["post", "delete"], url_path="delete-account")
    def delete_account(self, request):
        """
        Soft-delete user account (GDPR compliant).
        Anonymizes personal data and deactivates the account.
        A background task will hard-delete after 30 days.
        """
        user = request.user

        # Verify password for security
        password = request.data.get("password")
        if not password or not user.check_password(password):
            return Response(
                {"error": _("Incorrect password")}, status=status.HTTP_400_BAD_REQUEST
            )

        log_account_change(user, "account_deletion")

        # Cancel Stripe subscription if active
        try:
            from apps.subscriptions.services import StripeService

            StripeService.cancel_subscription(user)
        except Exception:
            logger.exception(
                "Failed to cancel Stripe subscription for user %s during deletion",
                user.id,
            )

        # End active buddy pairings
        try:
            from apps.buddies.models import BuddyPairing

            BuddyPairing.objects.filter(
                Q(user1=user) | Q(user2=user), status__in=["pending", "active"]
            ).update(status="cancelled", ended_at=timezone.now())
        except Exception:
            logger.exception(
                "Failed to end buddy pairings for user %s during deletion", user.id
            )

        # Remove from circles
        try:
            from apps.circles.models import CircleMembership

            CircleMembership.objects.filter(user=user).delete()
        except Exception:
            logger.exception(
                "Failed to remove circle memberships for user %s during deletion",
                user.id,
            )

        # Soft-delete: deactivate and schedule hard delete after 30 days
        user.is_active = False
        user.deactivated_at = timezone.now()

        # Anonymize personal data
        user.display_name = "Deleted User"
        user.email = f"deleted_{user.id}@deleted.stepora.app"
        user.avatar_url = ""
        if user.avatar_image:
            user.avatar_image.delete(save=False)
        user.bio = ""
        user.location = ""
        user.social_links = None
        user.notification_prefs = None
        user.app_prefs = None
        user.work_schedule = None
        user.save()

        # Delete auth tokens (JWT outstanding + legacy DRF tokens)
        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

            OutstandingToken.objects.filter(user=user).delete()
        except ImportError:
            pass  # simplejwt token_blacklist not installed
        except Exception as e:
            logger.error("Failed to clean up JWT tokens for user %s: %s", user.id, e)
        try:
            from rest_framework.authtoken.models import Token

            Token.objects.filter(user=user).delete()
        except ImportError:
            pass  # DRF authtoken not installed
        except Exception as e:
            logger.error("Failed to clean up DRF tokens for user %s: %s", user.id, e)

        return Response(
            {
                "detail": _("Account scheduled for deletion in 30 days"),
                "message": _(
                    "Account scheduled for deletion. Your data has been anonymized. "
                    "The account will be permanently deleted in 30 days."
                ),
            }
        )

    @extend_schema(
        summary="Export user data",
        description="Export all user data as JSON or CSV (GDPR data portability). "
        "Pass ?format=csv to get a flattened CSV of dreams/goals/tasks.",
        responses={
            200: dict,
            429: OpenApiResponse(description="Rate limit exceeded."),
        },
        tags=["Users"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="export-data",
        throttle_classes=[ExportRateThrottle],
    )
    def export_data(self, request):
        """Export all user data as JSON or CSV for GDPR compliance."""
        user = request.user
        export_format = request.query_params.get("export_format", "json").lower()
        log_data_export(user)

        data = {
            "profile": {
                "email": user.email,
                "display_name": user.display_name,
                "bio": user.bio,
                "location": user.location,
                "timezone": user.timezone,
                "subscription": user.subscription,
                "level": user.level,
                "xp": user.xp,
                "streak_days": user.streak_days,
                "date_joined": str(user.created_at),
            },
            "dreams": [],
            "conversations": [],
            "achievements": [],
            "focus_sessions": [],
            "notifications": [],
        }

        # Export dreams with goals and tasks (optimized with prefetch)
        for dream in user.dreams.prefetch_related("goals__tasks").all():
            dream_data = {
                "title": dream.title,
                "description": dream.description,
                "category": dream.category,
                "status": dream.status,
                "progress_percentage": dream.progress_percentage,
                "target_date": str(dream.target_date) if dream.target_date else None,
                "created_at": str(dream.created_at),
                "goals": [],
            }
            for goal in dream.goals.all():
                goal_data = {
                    "title": goal.title,
                    "description": goal.description,
                    "status": goal.status,
                    "progress_percentage": goal.progress_percentage,
                    "tasks": [
                        {
                            "title": t.title,
                            "description": t.description,
                            "status": t.status,
                            "duration_mins": t.duration_mins,
                            "completed_at": (
                                str(t.completed_at) if t.completed_at else None
                            ),
                        }
                        for t in goal.tasks.all()
                    ],
                }
                dream_data["goals"].append(goal_data)
            data["dreams"].append(dream_data)

        # Export conversation summaries (not full messages for privacy)
        try:
            from apps.ai.models import AIConversation
            from apps.chat.models import ChatConversation

            for conv in AIConversation.objects.filter(user=user).order_by("-updated_at")[
                :100
            ]:
                data["conversations"].append(
                    {
                        "type": conv.conversation_type,
                        "title": conv.title or "",
                        "total_messages": conv.total_messages,
                        "created_at": str(conv.created_at),
                        "updated_at": str(conv.updated_at),
                    }
                )
            for conv in ChatConversation.objects.filter(user=user).order_by("-updated_at")[
                :100
            ]:
                data["conversations"].append(
                    {
                        "type": "buddy_chat",
                        "title": conv.title or "",
                        "total_messages": conv.total_messages,
                        "created_at": str(conv.created_at),
                        "updated_at": str(conv.updated_at),
                    }
                )
        except Exception:
            logger.exception("Failed to export conversations for user %s", user.id)

        # Export achievements
        try:
            user_achievements = UserAchievement.objects.filter(
                user=user
            ).select_related("achievement")
            for ua in user_achievements:
                data["achievements"].append(
                    {
                        "name": ua.achievement.name,
                        "description": ua.achievement.description,
                        "category": ua.achievement.category,
                        "rarity": getattr(ua.achievement, "rarity", "common"),
                        "unlocked_at": str(ua.unlocked_at),
                        "progress": ua.progress,
                    }
                )
        except Exception:
            logger.exception("Failed to export achievements for user %s", user.id)

        # Export focus sessions
        try:
            from apps.dreams.models import FocusSession

            for session in FocusSession.objects.filter(user=user).order_by(
                "-started_at"
            )[:200]:
                data["focus_sessions"].append(
                    {
                        "session_type": session.session_type,
                        "duration_minutes": session.duration_minutes,
                        "actual_minutes": session.actual_minutes,
                        "completed": session.completed,
                        "started_at": str(session.started_at),
                        "ended_at": str(session.ended_at) if session.ended_at else None,
                    }
                )
        except Exception:
            logger.exception("Failed to export focus sessions for user %s", user.id)

        # Export notifications
        try:
            from apps.notifications.models import Notification

            for notif in Notification.objects.filter(user=user).order_by("-created_at")[
                :200
            ]:
                data["notifications"].append(
                    {
                        "type": notif.notification_type,
                        "title": notif.title,
                        "body": notif.body,
                        "created_at": str(notif.created_at),
                    }
                )
        except Exception:
            logger.exception("Failed to export notifications for user %s", user.id)

        # ── CSV format: flatten dreams/goals/tasks into rows ───────────
        if export_format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "dream_title",
                    "dream_category",
                    "dream_status",
                    "dream_progress",
                    "goal_title",
                    "goal_status",
                    "goal_progress",
                    "task_title",
                    "task_status",
                    "task_duration_mins",
                    "task_completed_at",
                ]
            )
            for dream in data["dreams"]:
                if not dream["goals"]:
                    writer.writerow(
                        [
                            dream["title"],
                            dream["category"],
                            dream["status"],
                            dream["progress_percentage"],
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                        ]
                    )
                for goal in dream["goals"]:
                    if not goal["tasks"]:
                        writer.writerow(
                            [
                                dream["title"],
                                dream["category"],
                                dream["status"],
                                dream["progress_percentage"],
                                goal["title"],
                                goal["status"],
                                goal["progress_percentage"],
                                "",
                                "",
                                "",
                                "",
                            ]
                        )
                    for task in goal["tasks"]:
                        writer.writerow(
                            [
                                dream["title"],
                                dream["category"],
                                dream["status"],
                                dream["progress_percentage"],
                                goal["title"],
                                goal["status"],
                                goal["progress_percentage"],
                                task["title"],
                                task["status"],
                                task.get("duration_mins", ""),
                                task.get("completed_at", ""),
                            ]
                        )
            csv_content = output.getvalue()
            response = HttpResponse(csv_content, content_type="text/csv")
            response["Content-Disposition"] = (
                'attachment; filename="stepora-export.csv"'
            )
            return response

        # ── JSON format (default) ─────────────────────────────────────
        response = Response(data)
        response["Content-Disposition"] = 'attachment; filename="stepora-export.json"'
        return response

    @extend_schema(
        summary="Change email",
        description="Request to change the user's email address. Sends a verification email to the new address.",
        responses={
            200: OpenApiResponse(description="Verification email sent."),
            400: OpenApiResponse(description="Validation error."),
        },
        tags=["Users"],
    )
    @action(detail=False, methods=["post"], url_path="change-email")
    def change_email(self, request):
        """Request email change with verification."""
        new_email = request.data.get("new_email", "").strip()
        password = request.data.get("password", "")

        if not new_email:
            return Response(
                {"error": _("new_email is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password or not request.user.check_password(password):
            return Response(
                {"error": _("Invalid password.")}, status=status.HTTP_400_BAD_REQUEST
            )

        # If 2FA is enabled, require TOTP code
        if getattr(request.user, "totp_enabled", False):
            totp_code = request.data.get("totp_code", "").strip()
            if not totp_code:
                return Response(
                    {"error": _("2FA verification code is required.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            import pyotp

            totp = pyotp.TOTP(request.user.totp_secret)
            if not totp.verify(totp_code, valid_window=1):
                return Response(
                    {"error": _("Invalid 2FA code.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Check if email is already taken
        if User.objects.filter(email=new_email).exclude(id=request.user.id).exists():
            return Response(
                {"error": _("This email is already in use.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Invalidate previous requests
        EmailChangeRequest.objects.filter(user=request.user, is_verified=False).delete()

        # Create new request
        token = secrets.token_urlsafe(64)
        EmailChangeRequest.objects.create(
            user=request.user,
            new_email=new_email,
            token=token,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        # Send verification email via Celery task
        from .tasks import send_email_change_verification

        send_email_change_verification.delay(request.user.id, new_email, token)

        return Response(
            {
                "message": _(
                    "Verification email sent to the new address. Please check your inbox."
                ),
            }
        )

    @extend_schema(
        summary="Get dashboard",
        description="Aggregated dashboard data: heatmap, stats, upcoming tasks, top dreams",
        tags=["Users"],
        responses={200: dict, 404: OpenApiResponse(description="Resource not found.")},
    )
    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        """Get aggregated dashboard data for the home screen."""
        user = request.user

        # Heatmap: last 28 days of DailyActivity
        from datetime import date
        from datetime import timedelta as td

        today = date.today()
        start_date = today - td(days=27)
        activities = DailyActivity.objects.filter(
            user=user, date__gte=start_date
        ).order_by("date")
        activity_map = {a.date: a for a in activities}
        heatmap = []
        for i in range(28):
            d = start_date + td(days=i)
            a = activity_map.get(d)
            heatmap.append(
                {
                    "date": str(d),
                    "tasks_completed": a.tasks_completed if a else 0,
                    "xp_earned": a.xp_earned if a else 0,
                    "minutes_active": a.minutes_active if a else 0,
                }
            )

        # Stats
        from apps.dreams.models import Dream, Task

        week_start = today - td(days=6)
        completed_tasks_week = Task.objects.filter(
            goal__dream__user=user,
            status="completed",
            completed_at__date__gte=week_start,
        ).count()

        stats = {
            "active_dreams": Dream.objects.filter(user=user, status="active").count(),
            "completed_tasks_week": completed_tasks_week,
            "streak_days": user.streak_days,
            "xp": user.xp,
            "level": user.level,
            "xp_to_next_level": 100 - (user.xp % 100),
        }

        # Upcoming tasks: next 5 scheduled tasks
        upcoming_tasks = (
            Task.objects.filter(
                goal__dream__user=user,
                status="pending",
                scheduled_date__gte=timezone.now(),
            )
            .select_related("goal__dream")
            .order_by("scheduled_date")[:5]
        )
        upcoming_list = [
            {
                "id": str(t.id),
                "title": t.title,
                "scheduled_date": t.scheduled_date,
                "duration_mins": t.duration_mins,
                "dream_title": t.goal.dream.title,
                "dream_id": str(t.goal.dream.id),
            }
            for t in upcoming_tasks
        ]

        # Top 3 active dreams with sparkline
        from apps.dreams.models import DreamProgressSnapshot

        top_dreams = Dream.objects.filter(user=user, status="active").order_by(
            "-updated_at"
        )[:3]
        dreams_data = []
        for dream in top_dreams:
            snapshots = DreamProgressSnapshot.objects.filter(dream=dream).order_by(
                "-date"
            )[:7]
            sparkline = list(
                reversed(
                    [
                        {"date": str(s.date), "progress": s.progress_percentage}
                        for s in snapshots
                    ]
                )
            )
            dreams_data.append(
                {
                    "id": str(dream.id),
                    "title": dream.title,
                    "category": dream.category,
                    "progress_percentage": dream.progress_percentage,
                    "sparkline_data": sparkline,
                }
            )

        return Response(
            {
                "heatmap": heatmap,
                "stats": stats,
                "upcoming_tasks": upcoming_list,
                "top_dreams": dreams_data,
            }
        )

    @extend_schema(
        summary="Get streak details",
        description="Return current streak, longest streak, 14-day history, and streak-freeze status.",
        responses={200: dict},
        tags=["Users"],
    )
    @action(detail=False, methods=["get"], url_path="streak-details")
    def streak_details(self, request):
        """Return detailed streak data for the streak widget."""
        from datetime import date
        from datetime import timedelta as td

        user = request.user
        today = date.today()

        # Fetch last 14 days of DailyActivity
        start_date = today - td(days=13)
        activities = DailyActivity.objects.filter(
            user=user, date__gte=start_date
        ).order_by("date")
        activity_map = {a.date: a for a in activities}

        streak_history = []
        for i in range(14):
            d = start_date + td(days=i)
            a = activity_map.get(d)
            streak_history.append(1 if (a and a.tasks_completed > 0) else 0)

        # Calculate longest streak from all DailyActivity records
        all_activities = (
            DailyActivity.objects.filter(user=user, tasks_completed__gt=0)
            .order_by("date")
            .values_list("date", flat=True)
        )
        longest_streak = 0
        current_run = 0
        prev_date = None
        for d in all_activities:
            if prev_date is not None and (d - prev_date).days == 1:
                current_run += 1
            else:
                current_run = 1
            if current_run > longest_streak:
                longest_streak = current_run
            prev_date = d

        # Streak freeze from GamificationProfile (streak_jokers)
        profile, _ = GamificationProfile.objects.get_or_create(user=user)
        freeze_count = profile.streak_jokers
        streak_frozen = False
        # Check if yesterday was missed and a joker was implicitly protecting the streak
        yesterday = today - td(days=1)
        yesterday_activity = activity_map.get(yesterday)
        if user.streak_days > 0 and (
            not yesterday_activity or yesterday_activity.tasks_completed == 0
        ):
            streak_frozen = True

        return Response(
            {
                "current_streak": user.streak_days,
                "longest_streak": max(longest_streak, user.streak_days),
                "streak_history": streak_history,
                "streak_frozen": streak_frozen,
                "freeze_count": freeze_count,
                "freeze_available": freeze_count > 0,
            }
        )

    @extend_schema(
        summary="Get achievements",
        description="List all achievements with unlock status and progress",
        tags=["Users"],
        responses={200: dict, 404: OpenApiResponse(description="Resource not found.")},
    )
    @action(detail=False, methods=["get"])
    def achievements(self, request):
        """Get all achievements with user unlock status and progress."""
        user = request.user
        all_achievements = Achievement.objects.filter(is_active=True)

        # Build map of user achievements (keyed by achievement_id)
        user_achievement_map = {
            ua.achievement_id: ua for ua in UserAchievement.objects.filter(user=user)
        }

        # Compute live progress for each condition type
        progress_cache = self._compute_achievement_progress(user)

        results = []
        for ach in all_achievements:
            ua = user_achievement_map.get(ach.id)
            is_unlocked = ua is not None

            # Use stored progress from UserAchievement if unlocked,
            # otherwise compute live progress from the cache
            if is_unlocked:
                progress = ua.progress if ua.progress > 0 else ach.condition_value
            else:
                progress = progress_cache.get(ach.condition_type, 0)

            results.append(
                {
                    "id": str(ach.id),
                    "name": ach.name,
                    "description": ach.description,
                    "icon": ach.icon,
                    "category": ach.category,
                    "rarity": getattr(ach, "rarity", "common"),
                    "xp_reward": ach.xp_reward,
                    "condition_type": ach.condition_type,
                    "requirement_value": ach.condition_value,
                    "unlocked": is_unlocked,
                    "unlocked_at": ua.unlocked_at if ua else None,
                    "progress": min(progress, ach.condition_value),
                }
            )

        unlocked_count = len(user_achievement_map)

        return Response(
            {
                "achievements": results,
                "unlocked_count": unlocked_count,
                "total_count": all_achievements.count(),
            }
        )

    def _compute_achievement_progress(self, user):
        """Compute live progress values for each achievement condition type."""
        from apps.dreams.models import Dream, Task

        progress = {}

        # Streak days
        progress["streak_days"] = user.streak_days or 0

        # Dreams created
        dreams_qs = Dream.objects.filter(user=user)
        dreams_total = dreams_qs.count()
        progress["dreams_created"] = dreams_total
        progress["first_dream"] = min(dreams_total, 1)

        # Dreams completed
        progress["dreams_completed"] = dreams_qs.filter(status="completed").count()

        # Tasks completed
        progress["tasks_completed"] = Task.objects.filter(
            goal__dream__user=user, status="completed"
        ).count()

        # Friends count
        try:
            from apps.social.models import Friendship

            progress["friends_count"] = Friendship.objects.filter(
                Q(user1=user) | Q(user2=user), status="accepted"
            ).count()
        except Exception:
            progress["friends_count"] = 0

        # Circles joined
        try:
            from apps.circles.models import CircleMembership

            progress["circles_joined"] = CircleMembership.objects.filter(
                user=user
            ).count()
        except Exception:
            progress["circles_joined"] = 0

        # Level reached
        progress["level_reached"] = user.level or 1

        # XP earned
        progress["xp_earned"] = user.xp or 0

        # Posts created
        try:
            from apps.social.models import Post

            progress["posts_created"] = Post.objects.filter(author=user).count()
        except Exception:
            progress["posts_created"] = 0

        # Likes received
        try:
            from apps.social.models import PostLike

            progress["likes_received"] = PostLike.objects.filter(
                post__author=user
            ).count()
        except Exception:
            progress["likes_received"] = 0

        # Vision board created
        try:
            from apps.dreams.models import VisionBoardImage

            progress["vision_created"] = min(
                VisionBoardImage.objects.filter(dream__user=user).count(), 1
            )
        except Exception:
            progress["vision_created"] = 0

        # First buddy
        try:
            from apps.buddies.models import BuddyPairing

            progress["first_buddy"] = min(
                BuddyPairing.objects.filter(
                    Q(user1=user) | Q(user2=user), status="active"
                ).count(),
                1,
            )
        except Exception:
            progress["first_buddy"] = 0

        # Profile completed (check if all profile fields are filled)
        profile_fields_filled = all(
            [
                bool(user.display_name and user.display_name.strip()),
                bool(user.avatar_url or user.avatar_image),
                bool(user.bio and user.bio.strip()),
            ]
        )
        progress["profile_completed"] = 1 if profile_fields_filled else 0

        # Early/late tasks (count-based, default to 0 here)
        progress["early_task"] = 0
        progress["late_task"] = 0

        return progress

    @extend_schema(
        summary="Update notification preferences",
        description="Update per-type notification preferences (push/email toggles).",
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
        tags=["Users"],
    )
    @action(detail=False, methods=["put"], url_path="notification-preferences")
    def notification_preferences(self, request):
        """Update notification preferences."""
        prefs = request.data

        # Validate structure
        if not isinstance(prefs, dict):
            return Response(
                {"error": _("Expected a JSON object with notification preferences.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Whitelist allowed keys and enforce boolean values
        allowed_keys = {
            "push_enabled",
            "email_enabled",
            "sound_enabled",
            "dream_reminders",
            "goal_deadlines",
            "buddy_messages",
            "circle_updates",
            "league_updates",
            "social_activity",
            "ai_suggestions",
            "streak_reminders",
            "weekly_summary",
        }
        validated = {}
        for key, value in prefs.items():
            if key not in allowed_keys:
                continue
            if not isinstance(value, bool):
                return Response(
                    {
                        "error": _('Invalid value for "%(key)s": expected true/false.')
                        % {"key": key}
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            validated[key] = value

        user = request.user
        # Merge validated prefs with existing (preserve unset keys)
        existing = user.notification_prefs or {}
        existing.update(validated)
        user.notification_prefs = existing
        user.save(update_fields=["notification_prefs"])

        return Response(UserSerializer(user).data)

    # ── Persona ─────────────────────────────────────────────────────

    @extend_schema(
        summary="Get or update user persona",
        description="Get or update the user's persona profile used to personalize AI dream plans.",
        responses={200: UserSerializer},
        tags=["Users"],
    )
    @action(detail=False, methods=["get", "put"], url_path="persona")
    def persona(self, request):
        """Get or update user persona for AI personalization."""
        user = request.user

        if request.method == "GET":
            return Response({"persona": user.persona or {}})

        data = request.data
        if not isinstance(data, dict):
            return Response(
                {"error": _("Expected a JSON object.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_keys = {
            "available_hours_per_week",  # number
            "preferred_schedule",  # morning/afternoon/evening/flexible
            "budget_range",  # none/low/medium/high
            "fitness_level",  # beginner/intermediate/advanced
            "learning_style",  # visual/reading/hands-on/audio
            "typical_day",  # free text description
            "occupation",  # free text
            "astrological_sign",  # optional, zodiac sign
            "global_motivation",  # free text - why they use Stepora
            "global_constraints",  # free text - general life constraints
            "preferred_language",  # fr/en/es etc
        }

        validated = {}
        for key, value in data.items():
            if key not in allowed_keys:
                continue
            if key == "available_hours_per_week":
                try:
                    validated[key] = max(0, min(168, int(value)))
                except (ValueError, TypeError):
                    continue
            elif isinstance(value, str):
                validated[key] = value[:500]  # cap text length
            else:
                validated[key] = value

        existing = user.persona or {}
        existing.update(validated)
        user.persona = existing
        user.save(update_fields=["persona"])

        return Response({"persona": user.persona})

    # ── Energy Profile ───────────────────────────────────────────────

    @extend_schema(
        summary="Get or set energy profile",
        description=(
            "GET returns the current energy profile. "
            "PUT sets peak_hours, low_energy_hours, and energy_pattern for smart scheduling."
        ),
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
        tags=["Users"],
    )
    @action(detail=False, methods=["get", "put"], url_path="energy-profile")
    def energy_profile(self, request):
        """Get or update energy profile for smart scheduling."""
        user = request.user

        if request.method == "GET":
            return Response(
                {
                    "energy_profile": user.energy_profile
                    or {
                        "peak_hours": [],
                        "low_energy_hours": [],
                        "energy_pattern": "steady",
                    }
                }
            )

        # PUT — validate and save
        data = request.data
        if not isinstance(data, dict):
            return Response(
                {"error": _("Expected a JSON object.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate energy_pattern
        valid_patterns = ("morning_person", "night_owl", "steady")
        pattern = data.get("energy_pattern", "steady")
        if pattern not in valid_patterns:
            return Response(
                {
                    "error": _(
                        "energy_pattern must be one of: morning_person, night_owl, steady"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate hour ranges helper
        def validate_hour_ranges(ranges, field_name):
            if not isinstance(ranges, list):
                return _("%(field)s must be an array") % {"field": field_name}
            if len(ranges) > 10:
                return _("%(field)s can have at most 10 ranges") % {"field": field_name}
            for r in ranges:
                if not isinstance(r, dict):
                    return _("Each range in %(field)s must be a JSON object") % {
                        "field": field_name
                    }
                start = r.get("start")
                end = r.get("end")
                if not isinstance(start, int) or not isinstance(end, int):
                    return _("start and end must be integers in %(field)s") % {
                        "field": field_name
                    }
                if start < 0 or start > 23 or end < 0 or end > 23:
                    return _("Hours must be between 0 and 23 in %(field)s") % {
                        "field": field_name
                    }
                if start >= end:
                    return _("start must be less than end in %(field)s") % {
                        "field": field_name
                    }
            return None

        peak_hours = data.get("peak_hours", [])
        err = validate_hour_ranges(peak_hours, "peak_hours")
        if err:
            return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

        low_energy_hours = data.get("low_energy_hours", [])
        err = validate_hour_ranges(low_energy_hours, "low_energy_hours")
        if err:
            return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

        user.energy_profile = {
            "peak_hours": peak_hours,
            "low_energy_hours": low_energy_hours,
            "energy_pattern": pattern,
        }
        user.save(update_fields=["energy_profile"])

        return Response(
            {
                "energy_profile": user.energy_profile,
            }
        )

    # ── Notification Timing Optimization ─────────────────────────────

    @extend_schema(
        summary="Get or optimize notification timing",
        description=(
            "GET returns current AI-optimized notification timing (analyzes activity patterns and calls AI). "
            "PUT applies the suggested timing to the user's preferences."
        ),
        responses={200: dict, 400: OpenApiResponse(description="Validation error.")},
        tags=["Users"],
    )
    @action(
        detail=False,
        methods=["get", "put"],
        url_path="notification-timing",
        permission_classes=[IsAuthenticated, CanUseAI],
        throttle_classes=[AINotificationTimingRateThrottle],
    )
    def notification_timing(self, request):
        """GET: Analyze activity patterns and return AI timing suggestions. PUT: Apply timing."""
        from collections import Counter, defaultdict
        from datetime import timedelta as td

        from apps.notifications.models import Notification
        from core.exceptions import OpenAIError
        from integrations.openai_service import OpenAIService

        user = request.user

        if request.method == "PUT":
            # Apply notification timing
            data = request.data
            if not isinstance(data, dict):
                return Response(
                    {"error": _("Expected a JSON object.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate optimal_times
            optimal_times = data.get("optimal_times", [])
            if not isinstance(optimal_times, list):
                return Response(
                    {"error": _("optimal_times must be an array.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            valid_days = {
                "weekday",
                "weekend",
                "daily",
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            }
            validated_times = []
            for item in optimal_times[:20]:
                if not isinstance(item, dict):
                    continue
                ntype = str(item.get("notification_type", ""))[:30]
                best_hour = item.get("best_hour", 9)
                if not isinstance(best_hour, int) or best_hour < 0 or best_hour > 23:
                    return Response(
                        {"error": _("best_hour must be an integer 0-23.")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                best_day = str(item.get("best_day", "daily"))[:20]
                if best_day not in valid_days:
                    return Response(
                        {
                            "error": _("best_day must be one of: %(days)s")
                            % {"days": ", ".join(sorted(valid_days))}
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                validated_times.append(
                    {
                        "notification_type": ntype,
                        "best_hour": best_hour,
                        "best_day": best_day,
                        "reason": str(item.get("reason", ""))[:300],
                    }
                )

            # Validate quiet_hours
            quiet_hours = data.get("quiet_hours", {})
            if not isinstance(quiet_hours, dict):
                return Response(
                    {"error": _("quiet_hours must be an object with start and end.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qh_start = quiet_hours.get("start", 22)
            qh_end = quiet_hours.get("end", 7)
            if (
                not isinstance(qh_start, int)
                or qh_start < 0
                or qh_start > 23
                or not isinstance(qh_end, int)
                or qh_end < 0
                or qh_end > 23
            ):
                return Response(
                    {"error": _("quiet_hours start and end must be integers 0-23.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            engagement_score = data.get("engagement_score", 0.5)
            if not isinstance(engagement_score, (int, float)):
                engagement_score = 0.5
            engagement_score = max(0.0, min(1.0, float(engagement_score)))

            user.notification_timing = {
                "optimal_times": validated_times,
                "quiet_hours": {"start": qh_start, "end": qh_end},
                "engagement_score": round(engagement_score, 2),
                "last_optimized": timezone.now().isoformat(),
            }
            user.save(update_fields=["notification_timing"])

            return Response(
                {
                    "notification_timing": user.notification_timing,
                    "applied": True,
                }
            )

        # ── GET: Analyze patterns and call AI ────────────────────────
        now = timezone.now()
        thirty_days_ago = now - td(days=30)

        # 1) Gather DailyActivity patterns (last 30 days)
        activities = DailyActivity.objects.filter(
            user=user,
            date__gte=thirty_days_ago.date(),
        ).order_by("date")

        # Build activity summary by day of week
        day_activity = defaultdict(
            lambda: {"tasks": 0, "xp": 0, "minutes": 0, "count": 0}
        )
        for act in activities:
            dow = act.date.strftime("%A").lower()
            day_activity[dow]["tasks"] += act.tasks_completed
            day_activity[dow]["xp"] += act.xp_earned
            day_activity[dow]["minutes"] += act.minutes_active
            day_activity[dow]["count"] += 1

        # Average per day of week
        day_summary = {}
        for dow, stats in day_activity.items():
            cnt = stats["count"] or 1
            day_summary[dow] = {
                "avg_tasks": round(stats["tasks"] / cnt, 1),
                "avg_xp": round(stats["xp"] / cnt, 1),
                "avg_minutes": round(stats["minutes"] / cnt, 1),
                "sample_days": cnt,
            }

        # 2) Analyze notification engagement (sent vs read/opened)
        recent_notifs = Notification.objects.filter(
            user=user,
            created_at__gte=thirty_days_ago,
        ).order_by("-created_at")[:200]

        type_engagement = defaultdict(
            lambda: {"sent": 0, "read": 0, "opened": 0, "hours": []}
        )
        for notif in recent_notifs:
            te = type_engagement[notif.notification_type]
            te["sent"] += 1
            if notif.read_at:
                te["read"] += 1
            if notif.opened_at:
                te["opened"] += 1
                # Track hour of interaction for pattern analysis
                te["hours"].append(notif.opened_at.hour)

        engagement_summary = {}
        for ntype, stats in type_engagement.items():
            sent = stats["sent"] or 1
            hour_counts = Counter(stats["hours"])
            most_common_hours = [h for h, _ in hour_counts.most_common(3)]
            engagement_summary[ntype] = {
                "sent": stats["sent"],
                "read_rate": round(stats["read"] / sent, 2),
                "open_rate": round(stats["opened"] / sent, 2),
                "most_responsive_hours": most_common_hours,
            }

        # 3) Derive active hours from last_activity and notification opens
        active_hours_counter = Counter()
        for notif in recent_notifs:
            if notif.opened_at:
                active_hours_counter[notif.opened_at.hour] += 1
        # Add activity pattern from daily records
        total_activity_records = len(activities)
        if total_activity_records > 0:
            # If user has activity, weight their active periods
            for act in activities:
                # Approximate: users tend to be active during working hours
                if act.minutes_active > 0:
                    active_hours_counter[9] += 1
                    active_hours_counter[14] += 1
                    active_hours_counter[19] += 1

        top_active_hours = [h for h, _ in active_hours_counter.most_common(6)]

        # 4) Notification types the user receives
        notification_types = list(
            set(
                Notification.objects.filter(user=user)
                .values_list("notification_type", flat=True)
                .distinct()
            )
        )
        # If no notifications yet, use all defined types
        if not notification_types:
            notification_types = [
                "reminder",
                "motivation",
                "progress",
                "achievement",
                "check_in",
                "daily_summary",
                "weekly_report",
            ]

        # 5) Build patterns object for AI
        activity_patterns = {
            "active_hours": top_active_hours,
            "day_of_week_activity": day_summary,
            "notification_engagement": engagement_summary,
            "total_activity_days": total_activity_records,
            "streak_days": user.streak_days,
            "energy_profile": user.energy_profile or {},
        }

        current_prefs = user.notification_timing or {}

        # 6) Call AI
        try:
            service = OpenAIService()
            ai_result = service.optimize_notification_timing(
                activity_patterns=activity_patterns,
                notification_types=notification_types,
                current_preferences=current_prefs,
            )
        except OpenAIError as e:
            logger.error("Notification timing optimization failed: %s", str(e))
            return Response(
                {
                    "error": _(
                        "AI optimization temporarily unavailable. Please try again later."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Return both the AI suggestion and the currently applied timing
        return Response(
            {
                "suggestion": ai_result,
                "current_timing": user.notification_timing,
                "activity_summary": {
                    "total_days_analyzed": total_activity_records,
                    "notifications_analyzed": len(recent_notifs),
                    "active_hours": top_active_hours,
                },
            }
        )

    # ── Two-Factor Authentication ────────────────────────────────────

    @extend_schema(
        summary="Setup 2FA",
        description="Generate TOTP secret and return provisioning URI for authenticator apps.",
        responses={200: dict},
        tags=["Users"],
    )
    @action(detail=False, methods=["post"], url_path="2fa/setup")
    def setup_2fa(self, request):
        """Generate TOTP secret and return OTP auth URI."""
        import pyotp

        user = request.user
        if user.totp_enabled:
            return Response(
                {"error": _("2FA is already enabled.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.save(update_fields=["totp_secret"])
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=user.email, issuer_name="Stepora")
        return Response({"secret": secret, "otpauth_url": uri})

    @extend_schema(
        summary="Verify 2FA setup",
        description="Verify TOTP code to complete 2FA activation.",
        request={
            "application/json": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
            }
        },
        responses={200: dict},
        tags=["Users"],
    )
    @action(detail=False, methods=["post"], url_path="2fa/verify-setup")
    def verify_2fa_setup(self, request):
        """Verify TOTP code to complete 2FA setup."""
        import pyotp

        code = request.data.get("code", "")
        user = request.user
        if not user.totp_secret:
            return Response(
                {"error": _("Run 2FA setup first.")}, status=status.HTTP_400_BAD_REQUEST
            )
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(code):
            user.totp_enabled = True
            user.save(update_fields=["totp_enabled"])
            return Response({"message": _("2FA enabled successfully.")})
        return Response(
            {"error": _("Invalid code.")}, status=status.HTTP_400_BAD_REQUEST
        )

    @extend_schema(
        summary="Disable 2FA",
        description="Disable two-factor authentication. Requires password and current TOTP code.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "password": {"type": "string"},
                    "code": {"type": "string"},
                },
            }
        },
        responses={200: dict},
        tags=["Users"],
    )
    @action(detail=False, methods=["post"], url_path="2fa/disable")
    def disable_2fa(self, request):
        """Disable 2FA — requires password + TOTP code."""
        import pyotp

        user = request.user
        password = request.data.get("password", "")
        code = request.data.get("code", "")
        if not user.check_password(password):
            return Response(
                {"error": _("Invalid password.")}, status=status.HTTP_400_BAD_REQUEST
            )
        if not user.totp_enabled:
            return Response(
                {"error": _("2FA is not enabled.")}, status=status.HTTP_400_BAD_REQUEST
            )
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(code):
            return Response(
                {"error": _("Invalid 2FA code.")}, status=status.HTTP_400_BAD_REQUEST
            )
        user.totp_enabled = False
        user.totp_secret = ""
        user.backup_codes = None
        user.save(update_fields=["totp_enabled", "totp_secret", "backup_codes"])
        return Response({"message": _("2FA disabled.")})

    @extend_schema(
        summary="Generate backup codes",
        description="Generate 10 one-time backup codes for 2FA recovery. Requires 2FA to be enabled.",
        responses={200: dict},
        tags=["Users"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="2fa/backup-codes",
        throttle_classes=[TwoFactorRateThrottle],
    )
    def generate_backup_codes(self, request):
        """Generate 10 one-time backup codes."""
        user = request.user
        if not user.totp_enabled:
            return Response(
                {"error": _("2FA must be enabled first.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        codes = [secrets.token_hex(4).upper() for _ in range(10)]
        hashed = [hash_backup_code(c) for c in codes]
        user.backup_codes = hashed
        user.save(update_fields=["backup_codes"])
        return Response(
            {
                "backup_codes": codes,
                "message": _("Save these codes securely. They cannot be shown again."),
            }
        )

    # ── Onboarding ───────────────────────────────────────────────────

    @extend_schema(
        summary="Complete onboarding",
        description="Mark the onboarding flow as completed for the current user.",
        responses={200: dict},
        tags=["Users"],
    )
    @action(detail=False, methods=["post"], url_path="complete-onboarding")
    def complete_onboarding(self, request):
        """Mark onboarding as completed."""
        user = request.user
        user.onboarding_completed = True
        user.save(update_fields=["onboarding_completed"])
        return Response({"message": _("Onboarding completed.")})

    @extend_schema(
        summary="Submit personality quiz",
        description=(
            "Accept quiz answers (index-based choices for 8 questions), "
            "score across 5 dimensions, determine dreamer type, save to profile, "
            "and award 50 XP for first-time completion."
        ),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "answers": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 0, "maximum": 3},
                        "minItems": 8,
                        "maxItems": 8,
                    }
                },
                "required": ["answers"],
            }
        },
        responses={200: dict},
        tags=["Users"],
    )
    @action(detail=False, methods=["post"], url_path="personality-quiz")
    def personality_quiz(self, request):
        """Score personality quiz answers and determine dreamer type."""
        answers = request.data.get("answers")
        if not answers or not isinstance(answers, list) or len(answers) != 8:
            return Response(
                {"error": _("Exactly 8 answers are required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate each answer is 0-3
        for i, ans in enumerate(answers):
            if not isinstance(ans, int) or ans < 0 or ans > 3:
                return Response(
                    {"error": _("Each answer must be an integer between 0 and 3.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Scoring matrix: each question maps answer indices to dimension scores.
        # Dimensions: visionary, achiever, explorer, collaborator, strategist
        # Each row = one question, each column = one answer option.
        # Values are (dimension_index, points) tuples per answer.
        SCORING = [
            # Q1: "When you have a new idea, you first..."
            # Think it through / Share with friends / Start immediately / Research everything
            [(4, 3), (3, 3), (1, 3), (4, 2)],
            # Q2: "Your ideal weekend looks like..."
            # Learning something new / Hanging with friends / Achieving a goal / Exploring new places
            [(4, 2), (3, 3), (1, 3), (2, 3)],
            # Q3: "When facing a challenge..."
            # Create an innovative solution / Ask for help / Push through it / Analyze all options
            [(0, 3), (3, 3), (1, 3), (4, 3)],
            # Q4: "You feel most fulfilled when..."
            # Inspiring others / Working together / Completing a task / Discovering something new
            [(0, 3), (3, 3), (1, 3), (2, 3)],
            # Q5: "Your dream workspace is..."
            # Creative studio / Collaborative space / Productive office / Anywhere new
            [(0, 3), (3, 3), (1, 2), (2, 3)],
            # Q6: "You prefer goals that are..."
            # Bold and visionary / Shared with others / Concrete and measurable / Flexible and evolving
            [(0, 3), (3, 3), (1, 3), (2, 3)],
            # Q7: "When planning a trip..."
            # Go with the flow / Plan with friends / Have a packed itinerary / Find hidden gems
            [(0, 2), (3, 3), (4, 3), (2, 3)],
            # Q8: "Success to you means..."
            # Making an impact / Building connections / Reaching milestones / Growing as a person
            [(0, 3), (3, 3), (1, 3), (2, 3)],
        ]

        DIMENSION_NAMES = [
            "visionary",
            "achiever",
            "explorer",
            "collaborator",
            "strategist",
        ]
        scores = [0, 0, 0, 0, 0]

        for q_idx, answer in enumerate(answers):
            dim_idx, points = SCORING[q_idx][answer]
            scores[dim_idx] += points

        # Determine the winning dimension
        max_score = max(scores)
        winner_idx = scores.index(max_score)
        dreamer_type = DIMENSION_NAMES[winner_idx]

        DESCRIPTIONS = {
            "visionary": {
                "title": "The Visionary",
                "description": "You see the big picture and inspire others with bold ideas. "
                "Your creativity and imagination drive you to dream beyond limits.",
                "traits": [
                    "Creative",
                    "Innovative",
                    "Inspiring",
                    "Big-picture thinker",
                ],
                "icon": "sparkles",
            },
            "achiever": {
                "title": "The Achiever",
                "description": "You thrive on setting goals and crushing them. "
                "Discipline and determination are your superpowers.",
                "traits": ["Determined", "Disciplined", "Goal-oriented", "Productive"],
                "icon": "trophy",
            },
            "explorer": {
                "title": "The Explorer",
                "description": "Curiosity is your compass. You love discovering new ideas, "
                "places, and perspectives that expand your world.",
                "traits": ["Curious", "Adventurous", "Open-minded", "Growth-driven"],
                "icon": "compass",
            },
            "collaborator": {
                "title": "The Collaborator",
                "description": "You believe in the power of together. Building connections "
                "and lifting others up is what makes you shine.",
                "traits": ["Empathetic", "Team player", "Supportive", "Communicative"],
                "icon": "users",
            },
            "strategist": {
                "title": "The Strategist",
                "description": "You approach everything with a plan. Analytical thinking "
                "and careful preparation set you up for success.",
                "traits": ["Analytical", "Methodical", "Thoughtful", "Detail-oriented"],
                "icon": "brain",
            },
        }

        user = request.user
        first_time = not user.dreamer_type
        user.dreamer_type = dreamer_type
        user.save(update_fields=["dreamer_type"])

        # Award 50 XP on first completion
        leveled_up = False
        if first_time:
            leveled_up = user.add_xp(50)

        result_info = DESCRIPTIONS[dreamer_type]
        return Response(
            {
                "dreamer_type": dreamer_type,
                "title": result_info["title"],
                "description": result_info["description"],
                "traits": result_info["traits"],
                "icon": result_info["icon"],
                "scores": dict(zip(DIMENSION_NAMES, scores)),
                "xp_awarded": 50 if first_time else 0,
                "leveled_up": leveled_up,
            }
        )

    @extend_schema(
        summary="Profile completeness",
        description="Calculate profile completeness percentage based on filled fields and activity.",
        responses={200: dict},
        tags=["Users"],
    )
    @action(detail=False, methods=["get"], url_path="profile-completeness")
    def profile_completeness(self, request):
        """Calculate profile completeness and return progress data."""
        user = request.user

        # Define completeness criteria with weights
        criteria = [
            {
                "key": "display_name",
                "label": "Display name",
                "weight": 15,
                "filled": bool(user.display_name and user.display_name.strip()),
                "suggestion": "Set a display name so others can find you.",
                "action": "/edit-profile",
                "action_label": "Add name",
            },
            {
                "key": "avatar",
                "label": "Profile photo",
                "weight": 20,
                "filled": bool(user.avatar_url or user.avatar_image),
                "suggestion": "Add a profile photo to stand out!",
                "action": "/edit-profile",
                "action_label": "Add photo",
            },
            {
                "key": "bio",
                "label": "Bio",
                "weight": 15,
                "filled": bool(user.bio and user.bio.strip()),
                "suggestion": "Write a short bio to introduce yourself.",
                "action": "/edit-profile",
                "action_label": "Add bio",
            },
            {
                "key": "dob",
                "label": "Date of birth",
                "weight": 10,
                "filled": bool(getattr(user, "date_of_birth", None)),
                "suggestion": "Add your date of birth for a personalised experience.",
                "action": "/edit-profile",
                "action_label": "Add birthday",
            },
            {
                "key": "timezone",
                "label": "Timezone",
                "weight": 10,
                "filled": bool(user.timezone and user.timezone != "Europe/Paris"),
                "suggestion": "Set your timezone for accurate reminders.",
                "action": "/settings",
                "action_label": "Set timezone",
            },
        ]

        # Check dream and goal counts (imported here to keep lazy)
        from apps.dreams.models import Dream, Goal

        has_dream = Dream.objects.filter(user=user).exists()
        has_goal = Goal.objects.filter(dream__user=user).exists()

        criteria.append(
            {
                "key": "dream",
                "label": "First dream",
                "weight": 15,
                "filled": has_dream,
                "suggestion": "Create your first dream to start planning!",
                "action": "/new-dream",
                "action_label": "Create a dream",
            }
        )
        criteria.append(
            {
                "key": "goal",
                "label": "First goal",
                "weight": 15,
                "filled": has_goal,
                "suggestion": "Add a goal to one of your dreams to stay on track.",
                "action": "/dreams",
                "action_label": "Add a goal",
            }
        )

        completed = []
        missing = []
        suggestions = []
        percentage = 0

        for item in criteria:
            if item["filled"]:
                completed.append(item["key"])
                percentage += item["weight"]
            else:
                missing.append(item["key"])
                suggestions.append(item["suggestion"])

        return Response(
            {
                "percentage": percentage,
                "completed": completed,
                "missing": missing,
                "suggestions": suggestions,
                "items": [
                    {
                        "key": c["key"],
                        "label": c["label"],
                        "filled": c["filled"],
                        "weight": c["weight"],
                        "action": c["action"],
                        "action_label": c["action_label"],
                        "suggestion": c["suggestion"],
                    }
                    for c in criteria
                ],
            }
        )

    @extend_schema(
        summary="Daily motivational quote",
        description="Get a motivational quote that rotates daily. All users see the same quote on the same day.",
        responses={200: dict},
        tags=["Users"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="daily-quote",
        permission_classes=[IsAuthenticated],
    )
    def daily_quote(self, request):
        """Return a motivational quote that rotates based on the day of the year."""
        from datetime import date

        quotes = [
            {
                "quote": "The only way to do great work is to love what you do.",
                "author": "Steve Jobs",
                "category": "motivation",
            },
            {
                "quote": "It does not matter how slowly you go as long as you do not stop.",
                "author": "Confucius",
                "category": "perseverance",
            },
            {
                "quote": "Believe you can and you're halfway there.",
                "author": "Theodore Roosevelt",
                "category": "self-belief",
            },
            {
                "quote": "The future belongs to those who believe in the beauty of their dreams.",
                "author": "Eleanor Roosevelt",
                "category": "dreams",
            },
            {
                "quote": "Success is not final, failure is not fatal: it is the courage to continue that counts.",
                "author": "Winston Churchill",
                "category": "courage",
            },
            {
                "quote": "In the middle of every difficulty lies opportunity.",
                "author": "Albert Einstein",
                "category": "perseverance",
            },
            {
                "quote": "What you get by achieving your goals is not as important as what you become by achieving your goals.",
                "author": "Zig Ziglar",
                "category": "growth",
            },
            {
                "quote": "The secret of getting ahead is getting started.",
                "author": "Mark Twain",
                "category": "action",
            },
            {
                "quote": "Everything you've ever wanted is on the other side of fear.",
                "author": "George Addair",
                "category": "courage",
            },
            {
                "quote": "Don't watch the clock; do what it does. Keep going.",
                "author": "Sam Levenson",
                "category": "perseverance",
            },
            {
                "quote": "You are never too old to set another goal or to dream a new dream.",
                "author": "C.S. Lewis",
                "category": "dreams",
            },
            {
                "quote": "The only limit to our realization of tomorrow will be our doubts of today.",
                "author": "Franklin D. Roosevelt",
                "category": "self-belief",
            },
            {
                "quote": "Act as if what you do makes a difference. It does.",
                "author": "William James",
                "category": "action",
            },
            {
                "quote": "What lies behind us and what lies before us are tiny matters compared to what lies within us.",
                "author": "Ralph Waldo Emerson",
                "category": "self-belief",
            },
            {
                "quote": "The best time to plant a tree was 20 years ago. The second best time is now.",
                "author": "Chinese Proverb",
                "category": "action",
            },
            {
                "quote": "Your limitation—it's only your imagination.",
                "author": "Unknown",
                "category": "self-belief",
            },
            {
                "quote": "Great things never come from comfort zones.",
                "author": "Unknown",
                "category": "courage",
            },
            {
                "quote": "Dream it. Wish it. Do it.",
                "author": "Unknown",
                "category": "action",
            },
            {
                "quote": "The harder you work for something, the greater you'll feel when you achieve it.",
                "author": "Unknown",
                "category": "perseverance",
            },
            {
                "quote": "Don't stop when you're tired. Stop when you're done.",
                "author": "Unknown",
                "category": "perseverance",
            },
            {
                "quote": "Wake up with determination. Go to bed with satisfaction.",
                "author": "Unknown",
                "category": "motivation",
            },
            {
                "quote": "Little things make big days.",
                "author": "Unknown",
                "category": "growth",
            },
            {
                "quote": "It's going to be hard, but hard does not mean impossible.",
                "author": "Unknown",
                "category": "perseverance",
            },
            {
                "quote": "The only person you are destined to become is the person you decide to be.",
                "author": "Ralph Waldo Emerson",
                "category": "growth",
            },
            {
                "quote": "Go the extra mile. It's never crowded there.",
                "author": "Dr. Wayne D. Dyer",
                "category": "action",
            },
            {
                "quote": "Keep your face always toward the sunshine—and shadows will fall behind you.",
                "author": "Walt Whitman",
                "category": "motivation",
            },
            {
                "quote": "You don't have to be great to start, but you have to start to be great.",
                "author": "Zig Ziglar",
                "category": "action",
            },
            {
                "quote": "A champion is defined not by their wins but by how they can recover when they fall.",
                "author": "Serena Williams",
                "category": "courage",
            },
            {
                "quote": "The mind is everything. What you think you become.",
                "author": "Buddha",
                "category": "self-belief",
            },
            {
                "quote": "Strive not to be a success, but rather to be of value.",
                "author": "Albert Einstein",
                "category": "growth",
            },
        ]

        day_of_year = date.today().timetuple().tm_yday
        index = day_of_year % len(quotes)

        return Response(quotes[index])

    @extend_schema(
        summary="AI motivational message based on mood",
        description=(
            "Generate a personalized motivational message based on the user's current mood "
            "and dream progress. Requires Premium or Pro subscription. Rate limited to 5/day."
        ),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "mood": {
                        "type": "string",
                        "enum": [
                            "excited",
                            "motivated",
                            "neutral",
                            "tired",
                            "frustrated",
                            "anxious",
                            "sad",
                        ],
                    },
                },
                "required": ["mood"],
            },
        },
        responses={200: dict},
        tags=["Users"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="motivation",
        permission_classes=[IsAuthenticated, CanUseAI],
        throttle_classes=[AIMotivationRateThrottle],
    )
    def motivation(self, request):
        """Generate a personalized motivational message based on the user's mood."""
        from apps.dreams.models import Dream, Task
        from integrations.openai_service import OpenAIService

        user = request.user
        mood = (request.data.get("mood") or "").strip().lower()

        valid_moods = [
            "excited",
            "motivated",
            "neutral",
            "tired",
            "frustrated",
            "anxious",
            "sad",
        ]
        if mood not in valid_moods:
            return Response(
                {"error": f'Invalid mood. Must be one of: {", ".join(valid_moods)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build dream progress summary
        active_dreams = Dream.objects.filter(user=user, status="active").order_by(
            "-updated_at"
        )[:5]
        progress_lines = []
        for dream in active_dreams:
            progress_lines.append(
                f"- {dream.title}: {dream.progress_percentage:.0f}% complete"
            )
        dream_progress_summary = "\n".join(progress_lines) if progress_lines else ""

        # Recent completions (last 7 days)
        recent_tasks = (
            Task.objects.filter(
                goal__dream__user=user,
                status="completed",
                completed_at__gte=timezone.now() - timedelta(days=7),
            )
            .select_related("goal__dream")
            .order_by("-completed_at")[:5]
        )
        completion_lines = []
        for task in recent_tasks:
            dream_title = (
                task.goal.dream.title if task.goal and task.goal.dream else "Unknown"
            )
            completion_lines.append(
                f'- Completed "{task.title}" (dream: {dream_title})'
            )
        recent_completions = "\n".join(completion_lines) if completion_lines else ""

        current_streak = user.streak_days

        # Generate AI motivation
        service = OpenAIService()
        result = service.generate_motivation(
            mood=mood,
            dream_progress_summary=dream_progress_summary,
            recent_completions=recent_completions,
            current_streak=current_streak,
        )

        return Response(result)

    @extend_schema(
        summary="Morning briefing",
        description="Aggregated morning briefing: greeting, today's tasks/events, streak, dream spotlight, motivation, yesterday's recap.",
        responses={200: dict},
        tags=["Users"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="morning-briefing",
        permission_classes=[IsAuthenticated],
    )
    def morning_briefing(self, request):
        """Return personalized morning briefing data for the home screen widget."""
        from datetime import datetime as dt
        from datetime import timedelta as td

        from apps.calendar.models import CalendarEvent
        from apps.dreams.models import Dream, FocusSession, Task

        user = request.user
        now = timezone.now()
        today = now.date()
        user_tz = user.timezone or "UTC"

        # ── Time-of-day aware greeting ──
        try:
            import zoneinfo

            local_now = now.astimezone(zoneinfo.ZoneInfo(user_tz))
        except Exception:
            local_now = now
        hour = local_now.hour

        if hour < 12:
            time_of_day = "morning"
            greeting_prefix = "Good morning"
        elif hour < 17:
            time_of_day = "afternoon"
            greeting_prefix = "Good afternoon"
        else:
            time_of_day = "evening"
            greeting_prefix = "Good evening"

        display_name = user.display_name or user.email.split("@")[0]
        greeting = f"{greeting_prefix}, {display_name}!"

        # ── Formatted date ──
        date_str = local_now.strftime("%A, %B %-d, %Y")

        # ── Tasks today ──
        today_start = timezone.make_aware(
            dt.combine(today, dt.min.time()),
            timezone.get_current_timezone(),
        )
        today_end = today_start + td(days=1)

        tasks_today_qs = (
            Task.objects.filter(
                goal__dream__user=user,
                status="pending",
            )
            .filter(
                Q(scheduled_date__gte=today_start, scheduled_date__lt=today_end)
                | Q(expected_date=today)
                | Q(deadline_date=today)
            )
            .select_related("goal__dream")
            .order_by("scheduled_date", "scheduled_time", "order")[:10]
        )

        tasks_today = []
        for t in tasks_today_qs:
            time_str = ""
            if t.scheduled_time:
                time_str = t.scheduled_time
            elif t.scheduled_date:
                time_str = t.scheduled_date.strftime("%H:%M")

            # Determine priority from dream priority
            dream_priority = t.goal.dream.priority if t.goal and t.goal.dream else 1
            priority = (
                "high"
                if dream_priority >= 3
                else ("medium" if dream_priority >= 2 else "low")
            )

            tasks_today.append(
                {
                    "id": str(t.id),
                    "title": t.title,
                    "dream_title": (
                        t.goal.dream.title if t.goal and t.goal.dream else ""
                    ),
                    "dream_id": str(t.goal.dream.id) if t.goal and t.goal.dream else "",
                    "time": time_str,
                    "priority": priority,
                    "duration_mins": t.duration_mins,
                }
            )

        # ── Events today ──
        events_today_qs = CalendarEvent.objects.filter(
            user=user,
            status="scheduled",
            start_time__gte=today_start,
            start_time__lt=today_end,
        ).order_by("start_time")[:10]

        events_today = [
            {
                "id": str(e.id),
                "title": e.title,
                "start_time": e.start_time.strftime("%H:%M"),
                "end_time": e.end_time.strftime("%H:%M"),
            }
            for e in events_today_qs
        ]

        # ── Streak ──
        streak_days = user.streak_days or 0
        if streak_days >= 100:
            streak_message = (
                f"Legendary! {streak_days} day streak \U0001f525\U0001f525\U0001f525"
            )
        elif streak_days >= 30:
            streak_message = (
                f"Unstoppable! {streak_days} day streak \U0001f525\U0001f525"
            )
        elif streak_days >= 7:
            streak_message = f"You're on fire! {streak_days} day streak \U0001f525"
        elif streak_days >= 3:
            streak_message = f"Nice momentum! {streak_days} day streak \U0001f4aa"
        elif streak_days == 1:
            streak_message = "Great start! Keep it going tomorrow \u2728"
        else:
            streak_message = "Start your streak today! \U0001f31f"

        streak = {
            "days": streak_days,
            "message": streak_message,
        }

        # ── Dream spotlight — deterministic random pick based on day of year ──
        active_dreams = list(
            Dream.objects.filter(user=user, status="active").values(
                "id", "title", "progress_percentage"
            )
        )
        dream_spotlight = None
        if active_dreams:
            day_of_year = today.timetuple().tm_yday
            spotlight_dream = active_dreams[day_of_year % len(active_dreams)]
            # Get the next pending task for this dream
            next_task_obj = (
                Task.objects.filter(
                    goal__dream__id=spotlight_dream["id"],
                    status="pending",
                )
                .order_by("scheduled_date", "order")
                .first()
            )

            dream_spotlight = {
                "id": str(spotlight_dream["id"]),
                "title": spotlight_dream["title"],
                "progress": round(spotlight_dream["progress_percentage"]),
                "next_task": next_task_obj.title if next_task_obj else None,
                "next_task_id": str(next_task_obj.id) if next_task_obj else None,
            }

        # ── Motivation quote (reuse daily quote logic) ──
        quotes = [
            {
                "quote": "The only way to do great work is to love what you do.",
                "author": "Steve Jobs",
            },
            {
                "quote": "It does not matter how slowly you go as long as you do not stop.",
                "author": "Confucius",
            },
            {
                "quote": "Believe you can and you're halfway there.",
                "author": "Theodore Roosevelt",
            },
            {
                "quote": "The future belongs to those who believe in the beauty of their dreams.",
                "author": "Eleanor Roosevelt",
            },
            {
                "quote": "Success is not final, failure is not fatal: it is the courage to continue that counts.",
                "author": "Winston Churchill",
            },
            {
                "quote": "In the middle of every difficulty lies opportunity.",
                "author": "Albert Einstein",
            },
            {
                "quote": "What you get by achieving your goals is not as important as what you become by achieving your goals.",
                "author": "Zig Ziglar",
            },
            {
                "quote": "The secret of getting ahead is getting started.",
                "author": "Mark Twain",
            },
            {
                "quote": "Everything you've ever wanted is on the other side of fear.",
                "author": "George Addair",
            },
            {
                "quote": "Don't watch the clock; do what it does. Keep going.",
                "author": "Sam Levenson",
            },
            {
                "quote": "You are never too old to set another goal or to dream a new dream.",
                "author": "C.S. Lewis",
            },
            {
                "quote": "Act as if what you do makes a difference. It does.",
                "author": "William James",
            },
            {
                "quote": "The best time to plant a tree was 20 years ago. The second best time is now.",
                "author": "Chinese Proverb",
            },
            {
                "quote": "Wake up with determination. Go to bed with satisfaction.",
                "author": "Unknown",
            },
            {
                "quote": "Go the extra mile. It's never crowded there.",
                "author": "Dr. Wayne D. Dyer",
            },
        ]
        day_of_year = today.timetuple().tm_yday
        motivation = quotes[day_of_year % len(quotes)]

        # ── Yesterday's recap ──
        yesterday = today - td(days=1)
        yesterday_activity = DailyActivity.objects.filter(
            user=user, date=yesterday
        ).first()

        # Focus minutes from FocusSession
        focus_minutes = 0
        yesterday_start = timezone.make_aware(
            dt.combine(yesterday, dt.min.time()),
            timezone.get_current_timezone(),
        )
        yesterday_end = yesterday_start + td(days=1)
        focus_sessions = FocusSession.objects.filter(
            user=user,
            completed=True,
            started_at__gte=yesterday_start,
            started_at__lt=yesterday_end,
        )
        for fs in focus_sessions:
            focus_minutes += fs.actual_minutes or 0

        stats_yesterday = {
            "tasks_completed": (
                yesterday_activity.tasks_completed if yesterday_activity else 0
            ),
            "focus_minutes": focus_minutes,
            "xp_earned": yesterday_activity.xp_earned if yesterday_activity else 0,
        }

        return Response(
            {
                "greeting": greeting,
                "date": date_str,
                "time_of_day": time_of_day,
                "tasks_today": tasks_today,
                "events_today": events_today,
                "streak": streak,
                "dream_spotlight": dream_spotlight,
                "motivation": motivation,
                "stats_yesterday": stats_yesterday,
            }
        )

    # ── Weekly Progress Report ────────────────────────────────────────
    @extend_schema(
        summary="Weekly progress report",
        description=(
            "Generate a comprehensive weekly progress report with AI-powered insights. "
            "Gathers last 7 days of activity (tasks, focus sessions, dream progress, XP) "
            "and compares with the previous week."
        ),
        responses={200: dict},
        tags=["Users"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="weekly-report",
        permission_classes=[IsAuthenticated],
    )
    def weekly_report(self, request):
        """Generate a weekly progress report with AI insights."""
        from datetime import datetime as dt
        from datetime import timedelta as td

        from django.db.models import Count, Sum

        from apps.dreams.models import (
            Dream,
            DreamProgressSnapshot,
            FocusSession,
            Goal,
        )
        from core.exceptions import OpenAIError
        from core.permissions import CanUseAI
        from integrations.openai_service import OpenAIService

        user = request.user

        # Check AI permission
        perm = CanUseAI()
        if not perm.has_permission(request, self):
            return Response(
                {"error": perm.message},
                status=status.HTTP_403_FORBIDDEN,
            )

        now = timezone.now()
        today = now.date()

        # ── Current week: last 7 days ──
        week_start = today - td(days=7)
        prev_week_start = today - td(days=14)

        # Helper: gather weekly stats for a date range
        def _gather_stats(start_date, end_date):
            """Collect activity stats for a date range."""
            activities = DailyActivity.objects.filter(
                user=user,
                date__gte=start_date,
                date__lt=end_date,
            )
            agg = activities.aggregate(
                total_tasks=Sum("tasks_completed"),
                total_xp=Sum("xp_earned"),
                total_minutes=Sum("minutes_active"),
                active_days=Count("id"),
            )

            # Focus sessions
            range_start = timezone.make_aware(
                dt.combine(start_date, dt.min.time()),
                timezone.get_current_timezone(),
            )
            range_end = timezone.make_aware(
                dt.combine(end_date, dt.min.time()),
                timezone.get_current_timezone(),
            )
            focus_agg = FocusSession.objects.filter(
                user=user,
                completed=True,
                started_at__gte=range_start,
                started_at__lt=range_end,
            ).aggregate(
                total_focus=Sum("actual_minutes"),
                session_count=Count("id"),
            )

            # Dreams that progressed (had progress snapshots with changes)
            dreams_progressed = (
                DreamProgressSnapshot.objects.filter(
                    dream__user=user,
                    date__gte=start_date,
                    date__lt=end_date,
                )
                .values("dream")
                .distinct()
                .count()
            )

            # Dreams completed in this period
            dreams_completed = Dream.objects.filter(
                user=user,
                status="completed",
                completed_at__gte=range_start,
                completed_at__lt=range_end,
            ).count()

            # Goals completed in this period
            goals_completed = Goal.objects.filter(
                dream__user=user,
                status="completed",
                completed_at__gte=range_start,
                completed_at__lt=range_end,
            ).count()

            return {
                "tasks_completed": agg["total_tasks"] or 0,
                "focus_minutes": (focus_agg["total_focus"] or 0)
                + (agg["total_minutes"] or 0),
                "streak_days": user.streak_days or 0,
                "xp_earned": agg["total_xp"] or 0,
                "dreams_progressed": dreams_progressed,
                "dreams_completed": dreams_completed,
                "goals_completed": goals_completed,
                "active_days": agg["active_days"] or 0,
                "focus_sessions": focus_agg["session_count"] or 0,
            }

        current_stats = _gather_stats(week_start, today)
        previous_stats = _gather_stats(prev_week_start, week_start)

        # ── Track AI usage ──
        tracker = AIUsageTracker()
        allowed, usage_info = tracker.check_quota(user, "ai_background")
        if not allowed:
            return Response(
                {
                    "error": "Daily AI quota exceeded for background tasks.",
                    "usage": usage_info,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # ── Call AI for insights ──
        try:
            ai_service = OpenAIService()
            ai_report = ai_service.generate_weekly_report(
                weekly_stats=current_stats,
                previous_week_stats=previous_stats,
            )
        except OpenAIError as e:
            logger.error("Weekly report AI generation failed: %s", str(e))
            # Return stats without AI insights
            ai_report = {
                "summary": "Unable to generate AI insights at this time.",
                "achievements": [],
                "trends": [],
                "recommendations": [],
                "score": 0,
                "encouragement": "Keep up the great work!",
            }

        # Increment usage after successful call
        tracker.increment(user, "ai_background")

        # ── Compute comparison deltas ──
        def _delta(current, previous):
            diff = current - previous
            if diff > 0:
                return {"value": diff, "direction": "up"}
            elif diff < 0:
                return {"value": abs(diff), "direction": "down"}
            return {"value": 0, "direction": "stable"}

        comparisons = {
            "tasks_completed": _delta(
                current_stats["tasks_completed"],
                previous_stats["tasks_completed"],
            ),
            "focus_minutes": _delta(
                current_stats["focus_minutes"],
                previous_stats["focus_minutes"],
            ),
            "xp_earned": _delta(
                current_stats["xp_earned"],
                previous_stats["xp_earned"],
            ),
            "dreams_progressed": _delta(
                current_stats["dreams_progressed"],
                previous_stats["dreams_progressed"],
            ),
            "active_days": _delta(
                current_stats["active_days"],
                previous_stats["active_days"],
            ),
        }

        # ── Build response ──
        return Response(
            {
                "week_start": week_start.isoformat(),
                "week_end": today.isoformat(),
                "stats": current_stats,
                "previous_stats": previous_stats,
                "comparisons": comparisons,
                "ai_report": ai_report,
            }
        )

    # ── Accountability Check-in ───────────────────────────────────────
    @extend_schema(
        summary="Accountability check-in",
        description=(
            "Generate a personalized AI accountability check-in prompt "
            "based on the user's recent activity, pending tasks, dream "
            "progress, and streak data."
        ),
        tags=["Users"],
        responses={200: OpenApiResponse(description="Accountability check-in data")},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="check-in",
        permission_classes=[IsAuthenticated, CanUseAI],
        throttle_classes=[AICheckinRateThrottle],
    )
    def check_in(self, request):
        """Return a personalized accountability check-in prompt."""

        from apps.dreams.models import Dream, Task
        from core.exceptions import OpenAIError
        from integrations.openai_service import OpenAIService

        user = request.user
        now = timezone.now()

        # ── AI quota check ──
        tracker = AIUsageTracker()
        allowed, quota_info = tracker.check_quota(user, "ai_background")
        if not allowed:
            return Response(
                {
                    "error": _("AI quota reached for today. Try again tomorrow."),
                    "quota": quota_info,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # ── Days since last activity ──
        days_since = 0
        if user.last_activity:
            delta = now - user.last_activity
            days_since = delta.days

        # ── Dream progress ──
        active_dreams = Dream.objects.filter(user=user, status="active").values(
            "id", "title", "progress_percentage", "category"
        )
        dream_progress = [
            {
                "id": str(d["id"]),
                "title": d["title"],
                "progress": round(d["progress_percentage"], 1),
                "category": d["category"] or "personal",
            }
            for d in active_dreams
        ]

        # ── Pending tasks ──
        pending_tasks_qs = (
            Task.objects.filter(
                goal__dream__user=user,
                goal__dream__status="active",
                status="pending",
            )
            .select_related("goal__dream")
            .order_by("scheduled_date", "order")[:10]
        )

        pending_tasks = []
        for t in pending_tasks_qs:
            due = ""
            if t.deadline_date:
                due = str(t.deadline_date)
            elif t.scheduled_date:
                due = (
                    str(t.scheduled_date.date())
                    if hasattr(t.scheduled_date, "date")
                    else str(t.scheduled_date)
                )
            pending_tasks.append(
                {
                    "id": str(t.id),
                    "title": t.title,
                    "dream_title": (
                        t.goal.dream.title if t.goal and t.goal.dream else ""
                    ),
                    "dream_id": str(t.goal.dream.id) if t.goal and t.goal.dream else "",
                    "due_date": due,
                }
            )

        total_pending = Task.objects.filter(
            goal__dream__user=user,
            goal__dream__status="active",
            status="pending",
        ).count()

        # ── Streak data ──
        streak_data = {
            "current_streak": user.streak_days or 0,
            "best_streak": user.streak_days or 0,  # best streak not tracked separately
        }

        # ── Generate AI check-in ──
        display_name = user.display_name or user.email.split("@")[0]
        try:
            ai_service = OpenAIService()
            checkin = ai_service.generate_checkin(
                dream_progress=dream_progress,
                days_since_activity=days_since,
                pending_tasks=pending_tasks,
                streak_data=streak_data,
                display_name=display_name,
            )
        except OpenAIError as e:
            logger.error("Check-in AI generation failed: %s", str(e))
            checkin = {
                "message": f"Hey {display_name}! Just checking in on your progress. Every step counts!",
                "prompt_type": "progress_check",
                "suggested_questions": [
                    "How can I stay motivated this week?",
                    "What should I focus on next?",
                    "Can you help me break down my next task?",
                ],
                "quick_actions": [
                    {
                        "label": "Start a focus session",
                        "type": "start_focus",
                        "target_id": None,
                    },
                ],
            }

        # Track AI usage
        tracker.increment(user, "ai_background")

        return Response(
            {
                "checkin": checkin,
                "context": {
                    "days_since_activity": days_since,
                    "active_dreams": len(dream_progress),
                    "pending_tasks": total_pending,
                    "streak_days": streak_data["current_streak"],
                },
            }
        )

    @extend_schema(
        summary="Productivity insights",
        description=(
            "Get AI-powered productivity insights and trend analysis based on "
            "the last 30 days of activity, focus sessions, and task completion."
        ),
        responses={200: dict},
        tags=["Users"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="productivity-insights",
        permission_classes=[IsAuthenticated, CanUseAI],
    )
    def productivity_insights(self, request):
        """Get AI-powered productivity insights and trend analysis."""
        from datetime import timedelta as td

        from django.db.models import Avg, Count, Sum

        from apps.dreams.models import FocusSession, Task
        from core.exceptions import OpenAIError
        from integrations.openai_service import OpenAIService

        user = request.user
        today = timezone.now().date()
        thirty_days_ago = today - td(days=30)

        # ── Gather 30 days of DailyActivity ──
        daily_qs = DailyActivity.objects.filter(
            user=user,
            date__gte=thirty_days_ago,
            date__lte=today,
        ).order_by("date")

        activity_data = []
        for da in daily_qs:
            activity_data.append(
                {
                    "date": da.date.isoformat(),
                    "day_of_week": da.date.strftime("%A"),
                    "tasks_completed": da.tasks_completed,
                    "xp_earned": da.xp_earned,
                    "minutes_active": da.minutes_active,
                }
            )

        # ── Gather FocusSession data aggregated by day ──
        focus_qs = FocusSession.objects.filter(
            user=user,
            started_at__date__gte=thirty_days_ago,
            started_at__date__lte=today,
            session_type="work",
        )

        from django.db.models.functions import TruncDate

        focus_by_day = (
            focus_qs.annotate(day=TruncDate("started_at"))
            .values("day")
            .annotate(
                total_minutes=Sum("actual_minutes"),
                sessions_count=Count("id"),
                completed_count=Count("id", filter=Q(completed=True)),
            )
            .order_by("day")
        )

        focus_sessions = []
        for f in focus_by_day:
            focus_sessions.append(
                {
                    "date": f["day"].isoformat() if f["day"] else "",
                    "total_minutes": f["total_minutes"] or 0,
                    "sessions_count": f["sessions_count"] or 0,
                    "completed_count": f["completed_count"] or 0,
                }
            )

        # ── Task completion rates ──
        tasks_in_period = Task.objects.filter(
            goal__dream__user=user,
        )
        total_tasks = tasks_in_period.count()
        completed_tasks = tasks_in_period.filter(status="completed").count()
        completion_rate = (
            round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0
        )

        # By day of week
        completed_by_dow = (
            tasks_in_period.filter(status="completed", completed_at__isnull=False)
            .filter(completed_at__date__gte=thirty_days_ago)
            .extra(select={"dow": "EXTRACT(DOW FROM completed_at)"})
            .values("dow")
            .annotate(completed=Count("id"))
            .order_by("dow")
        )

        day_names = [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ]
        dow_data = []
        for entry in completed_by_dow:
            dow_idx = int(entry["dow"])
            dow_data.append(
                {
                    "day": day_names[dow_idx] if 0 <= dow_idx < 7 else str(dow_idx),
                    "completed": entry["completed"],
                }
            )

        task_completion_rates = {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_rate": completion_rate,
            "by_day_of_week": dow_data,
        }

        # ── Aggregate stats for raw response ──
        totals = daily_qs.aggregate(
            total_tasks=Sum("tasks_completed"),
            total_xp=Sum("xp_earned"),
            total_minutes=Sum("minutes_active"),
            avg_tasks=Avg("tasks_completed"),
            avg_minutes=Avg("minutes_active"),
        )

        # Day-of-week averages from DailyActivity
        from django.db.models.functions import ExtractWeekDay

        dow_averages = (
            daily_qs.annotate(dow=ExtractWeekDay("date"))
            .values("dow")
            .annotate(
                avg_tasks=Avg("tasks_completed"),
                avg_xp=Avg("xp_earned"),
                avg_minutes=Avg("minutes_active"),
            )
            .order_by("dow")
        )

        # Django ExtractWeekDay: 1=Sunday, 2=Monday, ... 7=Saturday
        django_day_names = {
            1: "Sunday",
            2: "Monday",
            3: "Tuesday",
            4: "Wednesday",
            5: "Thursday",
            6: "Friday",
            7: "Saturday",
        }
        day_of_week_stats = []
        for entry in dow_averages:
            day_of_week_stats.append(
                {
                    "day": django_day_names.get(entry["dow"], str(entry["dow"])),
                    "avg_tasks": round(float(entry["avg_tasks"] or 0), 1),
                    "avg_xp": round(float(entry["avg_xp"] or 0), 1),
                    "avg_minutes": round(float(entry["avg_minutes"] or 0), 1),
                }
            )

        # ── Call AI for analysis ──
        ai_insights = None
        try:
            service = OpenAIService()
            ai_insights = service.analyze_productivity(
                activity_data=activity_data,
                focus_sessions=focus_sessions,
                task_completion_rates=task_completion_rates,
            )
        except OpenAIError as e:
            logger.error("Productivity analysis AI call failed: %s", str(e))
            ai_insights = {
                "overall_score": 50,
                "summary": "AI analysis is temporarily unavailable.",
                "trends": [],
                "peak_days": [],
                "productivity_patterns": [],
                "monthly_comparison": {"improved": [], "declined": [], "stable": []},
            }

        return Response(
            {
                "period": {
                    "start": thirty_days_ago.isoformat(),
                    "end": today.isoformat(),
                    "days": 30,
                },
                "daily_activity": activity_data,
                "focus_sessions": focus_sessions,
                "task_completion": task_completion_rates,
                "totals": {
                    "tasks_completed": totals["total_tasks"] or 0,
                    "xp_earned": totals["total_xp"] or 0,
                    "minutes_active": totals["total_minutes"] or 0,
                    "avg_tasks_per_day": round(float(totals["avg_tasks"] or 0), 1),
                    "avg_minutes_per_day": round(float(totals["avg_minutes"] or 0), 1),
                },
                "day_of_week_stats": day_of_week_stats,
                "ai_insights": ai_insights,
            }
        )

    @extend_schema(
        summary="Generate celebration",
        description=(
            "Generate an AI-powered celebration message for an achievement. "
            "Available to all users (no AI permission required)."
        ),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "task_completed",
                            "goal_completed",
                            "milestone_reached",
                            "dream_completed",
                            "streak_milestone",
                            "level_up",
                        ],
                    },
                    "context": {"type": "object"},
                },
                "required": ["type"],
            },
        },
        responses={200: dict},
        tags=["Users"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="celebrate",
        permission_classes=[IsAuthenticated],
    )
    def celebrate(self, request):
        """Generate an AI-powered celebration message for an achievement."""
        from core.exceptions import OpenAIError
        from integrations.openai_service import OpenAIService

        achievement_type = (request.data.get("type") or "").strip().lower()
        context_data = request.data.get("context") or {}

        valid_types = [
            "task_completed",
            "goal_completed",
            "milestone_reached",
            "dream_completed",
            "streak_milestone",
            "level_up",
        ]
        if achievement_type not in valid_types:
            return Response(
                {
                    "error": f'Invalid achievement type. Must be one of: {", ".join(valid_types)}'
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Sanitize context — only allow string/number values, limit size
        sanitized_context = {}
        for key, val in context_data.items():
            if isinstance(val, (str, int, float, bool)):
                sanitized_context[str(key)[:50]] = str(val)[:200]

        try:
            service = OpenAIService()
            result = service.generate_celebration(
                achievement_type=achievement_type,
                context_data=sanitized_context,
            )
        except OpenAIError as e:
            logger.error("Celebration generation failed: %s", str(e))
            # Return fallback instead of error — celebrations should never fail
            result = {
                "message": "Amazing work! You are making incredible progress!",
                "emoji": "\U0001f389",
                "animation_type": "confetti",
                "share_text": "Just hit a new milestone on my journey! #Stepora",
            }

        return Response(result)
