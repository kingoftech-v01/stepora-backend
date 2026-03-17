"""
Views for Notifications app.
"""

import logging

from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .models import (
    Notification,
    NotificationBatch,
    NotificationTemplate,
    ReminderPreference,
    UserDevice,
    WebPushSubscription,
)
from .serializers import (
    NotificationBatchSerializer,
    NotificationCreateSerializer,
    NotificationSerializer,
    NotificationTemplateSerializer,
    ReminderPreferenceSerializer,
    ReminderQuickSetupSerializer,
    UserDeviceSerializer,
    WebPushSubscriptionSerializer,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List notifications",
        description="Get all notifications for the current user",
        tags=["Notifications"],
    ),
    create=extend_schema(
        summary="Create notification",
        description="Create a new notification",
        responses={400: OpenApiResponse(description="Validation error.")},
        tags=["Notifications"],
    ),
    retrieve=extend_schema(
        summary="Get notification",
        description="Get a specific notification",
        responses={404: OpenApiResponse(description="Resource not found.")},
        tags=["Notifications"],
    ),
    update=extend_schema(
        summary="Update notification",
        description="Update a notification",
        responses={404: OpenApiResponse(description="Resource not found.")},
        tags=["Notifications"],
    ),
    partial_update=extend_schema(
        summary="Partial update notification",
        description="Partially update a notification",
        responses={404: OpenApiResponse(description="Resource not found.")},
        tags=["Notifications"],
    ),
    destroy=extend_schema(
        summary="Delete notification",
        description="Delete a notification",
        responses={404: OpenApiResponse(description="Resource not found.")},
        tags=["Notifications"],
    ),
)
class NotificationViewSet(viewsets.ModelViewSet):
    """CRUD operations for notifications."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["notification_type", "status"]
    ordering = ["-scheduled_for"]
    lookup_value_regex = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

    # Notification types accessible to free users
    FREE_TIER_TYPES = {"reminder", "progress", "dream_completed", "system"}

    def get_queryset(self):
        """Get notifications for current user, filtered by subscription tier."""
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        qs = Notification.objects.filter(user=self.request.user)
        # Free users only see basic notification types
        if self.request.user.subscription == "free":
            qs = qs.filter(notification_type__in=self.FREE_TIER_TYPES)
        return qs

    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action == "create":
            return NotificationCreateSerializer
        return NotificationSerializer

    def perform_create(self, serializer):
        """Create notification for current user."""
        serializer.save(user=self.request.user)

    @extend_schema(
        summary="Mark as read",
        description="Mark a notification as read",
        tags=["Notifications"],
        responses={
            200: NotificationSerializer,
            404: OpenApiResponse(description="Resource not found."),
        },
    )
    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        """Mark notification as read."""
        notification = self.get_object()
        notification.mark_read()

        return Response(NotificationSerializer(notification).data)

    @extend_schema(
        summary="Mark all as read",
        description="Delete all notifications for the current user (clears the inbox)",
        tags=["Notifications"],
        responses={200: dict},
    )
    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        """Delete all notifications to free up space."""
        deleted, _ = Notification.objects.filter(
            user=request.user,
        ).delete()

        return Response({"marked_read": deleted})

    @extend_schema(
        summary="Get unread count",
        description="Get count of unread notifications",
        tags=["Notifications"],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """Get count of unread notifications."""
        count = Notification.objects.filter(
            user=request.user, read_at__isnull=True, status="sent"
        ).count()

        return Response({"unread_count": count})

    @extend_schema(
        summary="Mark as opened",
        description="Mark a notification as opened/interacted with",
        tags=["Notifications"],
        responses={
            200: NotificationSerializer,
            404: OpenApiResponse(description="Resource not found."),
        },
    )
    @action(detail=True, methods=["post"])
    def opened(self, request, pk=None):
        """Mark notification as opened (for analytics tracking)."""
        notification = self.get_object()
        notification.mark_opened()
        return Response(NotificationSerializer(notification).data)

    @extend_schema(
        summary="Grouped notifications",
        description="Get notifications grouped by type with counts",
        tags=["Notifications"],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"])
    def grouped(self, request):
        """Get notifications grouped by type."""
        from django.db.models import Q

        groups = (
            Notification.objects.filter(
                user=request.user,
                status="sent",
            )
            .values("notification_type")
            .annotate(
                total=Count("id"),
                unread=Count("id", filter=Q(read_at__isnull=True)),
            )
            .order_by("-total")
        )

        result = [
            {
                "type": g["notification_type"],
                "total": g["total"],
                "unread": g["unread"],
            }
            for g in groups
        ]

        return Response({"groups": result})


@extend_schema_view(
    list=extend_schema(
        summary="List templates",
        description="Get all notification templates",
        tags=["Notification Templates"],
    ),
    retrieve=extend_schema(
        summary="Get template",
        description="Get a specific notification template",
        tags=["Notification Templates"],
    ),
)
class NotificationTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to notification templates."""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationTemplateSerializer
    queryset = NotificationTemplate.objects.filter(is_active=True)


@extend_schema_view(
    create=extend_schema(
        summary="Register push subscription",
        description="Register a Web Push subscription for the current user",
        tags=["Notifications"],
    ),
    destroy=extend_schema(
        summary="Remove push subscription",
        description="Remove a Web Push subscription",
        tags=["Notifications"],
    ),
    list=extend_schema(
        summary="List push subscriptions",
        description="List Web Push subscriptions for the current user",
        tags=["Notifications"],
    ),
)
class WebPushSubscriptionViewSet(viewsets.ModelViewSet):
    """Manage Web Push subscriptions."""

    permission_classes = [IsAuthenticated]
    serializer_class = WebPushSubscriptionSerializer
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return WebPushSubscription.objects.none()
        return WebPushSubscription.objects.filter(
            user=self.request.user,
            is_active=True,
        )

    def perform_create(self, serializer):
        # Deactivate existing subscriptions with the same endpoint
        endpoint = serializer.validated_data.get("subscription_info", {}).get(
            "endpoint"
        )
        if endpoint:
            WebPushSubscription.objects.filter(
                user=self.request.user,
                subscription_info__endpoint=endpoint,
            ).update(is_active=False)

        serializer.save(user=self.request.user)


@extend_schema_view(
    create=extend_schema(
        summary="Register device for push notifications",
        description="Register an FCM token for the current user's device. "
        "If the token already exists, the existing registration is updated.",
        tags=["Notifications"],
    ),
    list=extend_schema(
        summary="List registered devices",
        description="List all active device registrations for the current user.",
        tags=["Notifications"],
    ),
    destroy=extend_schema(
        summary="Unregister device",
        description="Deactivate a device registration (e.g., on logout).",
        tags=["Notifications"],
    ),
)
class UserDeviceViewSet(viewsets.ModelViewSet):
    """Manage FCM device registrations for push notifications."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserDeviceSerializer
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserDevice.objects.none()
        return UserDevice.objects.filter(
            user=self.request.user,
            is_active=True,
        )

    def create(self, request, *args, **kwargs):
        """
        Register or re-register a device token.
        Deletes any existing registration with the same token BEFORE
        serializer validation (to avoid unique constraint rejection).
        """
        fcm_token = request.data.get("fcm_token", "")
        if fcm_token:
            UserDevice.objects.filter(fcm_token=fcm_token, user=request.user).delete()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = serializer.save(user=request.user, is_active=True)

        # Subscribe to FCM topics
        self._subscribe_to_user_topics(device)

        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def perform_destroy(self, instance):
        """Soft-delete: deactivate rather than hard-delete."""
        instance.is_active = False
        instance.save(update_fields=["is_active"])

        # Unsubscribe from all topics
        self._unsubscribe_from_all_topics(instance)

    def _subscribe_to_user_topics(self, device):
        """Subscribe device to FCM topics based on notification_prefs."""
        try:
            from .fcm_service import FCMService

            fcm = FCMService()

            # Always subscribe to user-specific topic
            fcm.subscribe_to_topic([device.fcm_token], f"user_{device.user.id}")

            # Subscribe to notification type topics based on prefs
            prefs = device.user.notification_prefs or {}
            topic_map = {
                "motivation": "topic_motivation",
                "weekly_report": "topic_weekly_report",
                "achievement": "topic_achievement",
            }
            for pref_key, topic_name in topic_map.items():
                if prefs.get(pref_key, True):
                    fcm.subscribe_to_topic([device.fcm_token], topic_name)

        except Exception as e:
            logger.warning(f"Failed to subscribe device {device.id} to topics: {e}")

    def _unsubscribe_from_all_topics(self, device):
        """Unsubscribe device from all known FCM topics."""
        try:
            from .fcm_service import FCMService

            fcm = FCMService()
            topics = [
                f"user_{device.user.id}",
                "topic_motivation",
                "topic_weekly_report",
                "topic_achievement",
            ]
            for topic in topics:
                fcm.unsubscribe_from_topic([device.fcm_token], topic)
        except Exception as e:
            logger.warning(f"Failed to unsubscribe device {device.id} from topics: {e}")


@extend_schema_view(
    list=extend_schema(
        summary="List notification batches",
        description="Retrieve all notification batches. Admin access only.",
        tags=["Notification Batches"],
        responses={200: NotificationBatchSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Get notification batch",
        description="Retrieve details of a specific notification batch. Admin access only.",
        tags=["Notification Batches"],
        responses={
            200: NotificationBatchSerializer,
            404: OpenApiResponse(description="Batch not found."),
        },
    ),
)
class NotificationBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for NotificationBatch.

    Provides list and detail endpoints for notification batches.
    Restricted to admin (staff) users only.
    """

    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = NotificationBatchSerializer
    lookup_value_regex = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "notification_type"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return NotificationBatch.objects.none()
        return NotificationBatch.objects.all().order_by("-created_at")


@extend_schema_view(
    list=extend_schema(
        summary="List reminder preferences",
        description="Get all reminder preferences for the current user",
        tags=["Reminders"],
    ),
    create=extend_schema(
        summary="Create reminder preference",
        description="Create a new reminder preference",
        tags=["Reminders"],
    ),
    retrieve=extend_schema(
        summary="Get reminder preference",
        description="Get a specific reminder preference",
        tags=["Reminders"],
    ),
    update=extend_schema(
        summary="Update reminder preference",
        description="Update a reminder preference",
        tags=["Reminders"],
    ),
    partial_update=extend_schema(
        summary="Partial update reminder preference",
        description="Partially update a reminder preference",
        tags=["Reminders"],
    ),
    destroy=extend_schema(
        summary="Delete reminder preference",
        description="Delete a reminder preference",
        tags=["Reminders"],
    ),
)
class ReminderPreferenceViewSet(viewsets.ModelViewSet):
    """CRUD operations for reminder preferences."""

    permission_classes = [IsAuthenticated]
    serializer_class = ReminderPreferenceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["dream", "reminder_type", "is_active", "notify_method"]
    lookup_value_regex = (
        "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ReminderPreference.objects.none()
        return ReminderPreference.objects.filter(
            user=self.request.user
        ).select_related("dream")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        summary="Get preset options",
        description="Return available preset reminder times (morning, afternoon, evening)",
        tags=["Reminders"],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"])
    def presets(self, request):
        """Return preset options for quick setup."""
        return Response(
            {
                "presets": [
                    {
                        "id": "morning",
                        "label": "Morning",
                        "time": "08:00",
                        "description": "Start your day with a reminder",
                    },
                    {
                        "id": "afternoon",
                        "label": "Afternoon",
                        "time": "13:00",
                        "description": "Midday check-in on your tasks",
                    },
                    {
                        "id": "evening",
                        "label": "Evening",
                        "time": "19:00",
                        "description": "Evening review of your progress",
                    },
                ]
            }
        )

    @extend_schema(
        summary="Quick setup with preset",
        description="Create a reminder preference using a preset (morning/afternoon/evening)",
        tags=["Reminders"],
        request=ReminderQuickSetupSerializer,
        responses={
            201: ReminderPreferenceSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    @action(detail=False, methods=["post"], url_path="quick-setup")
    def quick_setup(self, request):
        """Create a reminder from a preset."""
        import datetime

        setup_serializer = ReminderQuickSetupSerializer(data=request.data)
        setup_serializer.is_valid(raise_exception=True)

        preset = setup_serializer.validated_data["preset"]
        dream_id = setup_serializer.validated_data.get("dream")
        notify_method = setup_serializer.validated_data.get("notify_method", "push")
        days = setup_serializer.validated_data.get(
            "days", "mon,tue,wed,thu,fri,sat,sun"
        )

        # Map preset to time
        preset_times = {
            "morning": datetime.time(8, 0),
            "afternoon": datetime.time(13, 0),
            "evening": datetime.time(19, 0),
        }
        reminder_time = preset_times[preset]

        # Resolve dream if provided
        dream = None
        if dream_id:
            from apps.dreams.models import Dream

            try:
                dream = Dream.objects.get(id=dream_id, user=request.user)
            except Dream.DoesNotExist:
                return Response(
                    {"detail": "Dream not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Check for existing duplicate
        existing = ReminderPreference.objects.filter(
            user=request.user, dream=dream, time=reminder_time
        ).first()
        if existing:
            # Re-activate if it was deactivated
            if not existing.is_active:
                existing.is_active = True
                existing.notify_method = notify_method
                existing.days = days
                existing.save(
                    update_fields=["is_active", "notify_method", "days", "updated_at"]
                )
            return Response(
                ReminderPreferenceSerializer(existing).data,
                status=status.HTTP_200_OK,
            )

        reminder = ReminderPreference.objects.create(
            user=request.user,
            dream=dream,
            reminder_type=preset,
            time=reminder_time,
            days=days,
            notify_method=notify_method,
        )

        return Response(
            ReminderPreferenceSerializer(reminder).data,
            status=status.HTTP_201_CREATED,
        )
