"""
Views for Notifications app.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

from .models import Notification, NotificationTemplate, WebPushSubscription
from .serializers import (
    NotificationSerializer, NotificationCreateSerializer,
    NotificationTemplateSerializer, WebPushSubscriptionSerializer,
)


@extend_schema_view(
    list=extend_schema(summary="List notifications", description="Get all notifications for the current user", tags=["Notifications"]),
    create=extend_schema(summary="Create notification", description="Create a new notification", responses={400: OpenApiResponse(description='Validation error.')}, tags=["Notifications"]),
    retrieve=extend_schema(summary="Get notification", description="Get a specific notification", responses={404: OpenApiResponse(description='Resource not found.')}, tags=["Notifications"]),
    update=extend_schema(summary="Update notification", description="Update a notification", responses={404: OpenApiResponse(description='Resource not found.')}, tags=["Notifications"]),
    partial_update=extend_schema(summary="Partial update notification", description="Partially update a notification", responses={404: OpenApiResponse(description='Resource not found.')}, tags=["Notifications"]),
    destroy=extend_schema(summary="Delete notification", description="Delete a notification", responses={404: OpenApiResponse(description='Resource not found.')}, tags=["Notifications"]),
)
class NotificationViewSet(viewsets.ModelViewSet):
    """CRUD operations for notifications."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['notification_type', 'status']
    ordering = ['-scheduled_for']
    lookup_value_regex = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'

    # Notification types accessible to free users
    FREE_TIER_TYPES = {'reminder', 'progress', 'dream_completed', 'system'}

    def get_queryset(self):
        """Get notifications for current user, filtered by subscription tier."""
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        qs = Notification.objects.filter(user=self.request.user)
        # Free users only see basic notification types
        if self.request.user.subscription == 'free':
            qs = qs.filter(notification_type__in=self.FREE_TIER_TYPES)
        return qs

    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action == 'create':
            return NotificationCreateSerializer
        return NotificationSerializer

    def perform_create(self, serializer):
        """Create notification for current user."""
        serializer.save(user=self.request.user)

    @extend_schema(summary="Mark as read", description="Mark a notification as read", tags=["Notifications"], responses={200: NotificationSerializer, 404: OpenApiResponse(description='Resource not found.')})
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

    @extend_schema(summary="Mark as opened", description="Mark a notification as opened/interacted with", tags=["Notifications"], responses={200: NotificationSerializer, 404: OpenApiResponse(description='Resource not found.')})
    @action(detail=True, methods=['post'])
    def opened(self, request, pk=None):
        """Mark notification as opened (for analytics tracking)."""
        notification = self.get_object()
        notification.mark_opened()
        return Response(NotificationSerializer(notification).data)

    @extend_schema(summary="Grouped notifications", description="Get notifications grouped by type with counts", tags=["Notifications"], responses={200: dict})
    @action(detail=False, methods=['get'])
    def grouped(self, request):
        """Get notifications grouped by type."""
        groups = Notification.objects.filter(
            user=request.user,
            status='sent',
        ).values('notification_type').annotate(
            total=Count('id'),
            unread=Count('id', filter=Count('id', filter=None) if False else None),
        ).order_by('-total')

        # Build proper grouped response
        result = []
        for g in Notification.objects.filter(
            user=request.user, status='sent'
        ).values('notification_type').annotate(
            total=Count('id'),
        ).order_by('-total'):
            unread = Notification.objects.filter(
                user=request.user,
                status='sent',
                notification_type=g['notification_type'],
                read_at__isnull=True,
            ).count()
            result.append({
                'type': g['notification_type'],
                'total': g['total'],
                'unread': unread,
            })

        return Response({'groups': result})


@extend_schema_view(
    list=extend_schema(summary="List templates", description="Get all notification templates", tags=["Notification Templates"]),
    retrieve=extend_schema(summary="Get template", description="Get a specific notification template", tags=["Notification Templates"]),
)
class NotificationTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to notification templates."""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationTemplateSerializer
    queryset = NotificationTemplate.objects.filter(is_active=True)


@extend_schema_view(
    create=extend_schema(summary="Register push subscription", description="Register a Web Push subscription for the current user", tags=["Notifications"]),
    destroy=extend_schema(summary="Remove push subscription", description="Remove a Web Push subscription", tags=["Notifications"]),
    list=extend_schema(summary="List push subscriptions", description="List Web Push subscriptions for the current user", tags=["Notifications"]),
)
class WebPushSubscriptionViewSet(viewsets.ModelViewSet):
    """Manage Web Push subscriptions."""

    permission_classes = [IsAuthenticated]
    serializer_class = WebPushSubscriptionSerializer
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return WebPushSubscription.objects.none()
        return WebPushSubscription.objects.filter(
            user=self.request.user,
            is_active=True,
        )

    def perform_create(self, serializer):
        # Deactivate existing subscriptions with the same endpoint
        endpoint = serializer.validated_data.get('subscription_info', {}).get('endpoint')
        if endpoint:
            WebPushSubscription.objects.filter(
                user=self.request.user,
                subscription_info__endpoint=endpoint,
            ).update(is_active=False)

        serializer.save(user=self.request.user)
