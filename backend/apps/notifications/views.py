"""
Views for Notifications app.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Notification, NotificationTemplate
from .serializers import (
    NotificationSerializer, NotificationCreateSerializer,
    NotificationTemplateSerializer
)


@extend_schema_view(
    list=extend_schema(summary="List notifications", description="Get all notifications for the current user", tags=["Notifications"]),
    create=extend_schema(summary="Create notification", description="Create a new notification", tags=["Notifications"]),
    retrieve=extend_schema(summary="Get notification", description="Get a specific notification", tags=["Notifications"]),
    update=extend_schema(summary="Update notification", description="Update a notification", tags=["Notifications"]),
    partial_update=extend_schema(summary="Partial update notification", description="Partially update a notification", tags=["Notifications"]),
    destroy=extend_schema(summary="Delete notification", description="Delete a notification", tags=["Notifications"]),
)
class NotificationViewSet(viewsets.ModelViewSet):
    """CRUD operations for notifications."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['notification_type', 'status']
    ordering = ['-scheduled_for']

    def get_queryset(self):
        """Get notifications for current user."""
        return Notification.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action == 'create':
            return NotificationCreateSerializer
        return NotificationSerializer

    def perform_create(self, serializer):
        """Create notification for current user."""
        serializer.save(user=self.request.user)

    @extend_schema(summary="Mark as read", description="Mark a notification as read", tags=["Notifications"], responses={200: NotificationSerializer})
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read."""
        notification = self.get_object()
        notification.mark_read()

        return Response(NotificationSerializer(notification).data)

    @extend_schema(summary="Mark all as read", description="Mark all notifications as read", tags=["Notifications"], responses={200: dict})
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read."""
        updated = Notification.objects.filter(
            user=request.user,
            read_at__isnull=True
        ).update(read_at=timezone.now())

        return Response({'marked_read': updated})

    @extend_schema(summary="Get unread count", description="Get count of unread notifications", tags=["Notifications"], responses={200: dict})
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread notifications."""
        count = Notification.objects.filter(
            user=request.user,
            read_at__isnull=True,
            status='sent'
        ).count()

        return Response({'unread_count': count})


@extend_schema_view(
    list=extend_schema(summary="List templates", description="Get all notification templates", tags=["Notification Templates"]),
    retrieve=extend_schema(summary="Get template", description="Get a specific notification template", tags=["Notification Templates"]),
)
class NotificationTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to notification templates."""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationTemplateSerializer
    queryset = NotificationTemplate.objects.filter(is_active=True)
