"""
Serializers for Notifications app.
"""

from rest_framework import serializers
from core.sanitizers import sanitize_text
from .models import Notification, NotificationTemplate, NotificationBatch, WebPushSubscription


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model."""

    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'notification_type', 'title', 'body',
            'data', 'scheduled_for', 'sent_at', 'read_at',
            'status', 'is_read',
            'created_at'
        ]
        read_only_fields = ['id', 'user', 'sent_at', 'read_at', 'status', 'created_at']

    def get_is_read(self, obj):
        return obj.read_at is not None


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notifications."""

    class Meta:
        model = Notification
        fields = [
            'notification_type', 'title', 'body',
            'data', 'scheduled_for'
        ]

    def validate_title(self, value):
        """Sanitize title to prevent XSS."""
        return sanitize_text(value)

    def validate_body(self, value):
        """Sanitize body to prevent XSS."""
        return sanitize_text(value)


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """Serializer for Notification templates."""

    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'name', 'notification_type',
            'title_template', 'body_template',
            'available_variables', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class NotificationBatchSerializer(serializers.ModelSerializer):
    """Serializer for Notification batches."""

    success_rate = serializers.SerializerMethodField()

    class Meta:
        model = NotificationBatch
        fields = [
            'id', 'name', 'notification_type',
            'total_scheduled', 'total_sent', 'total_failed',
            'status', 'success_rate',
            'created_at', 'completed_at'
        ]
        read_only_fields = fields

    def get_success_rate(self, obj):
        if obj.total_scheduled == 0:
            return 0.0
        return round((obj.total_sent / obj.total_scheduled) * 100, 2)


class WebPushSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Web Push subscriptions."""

    class Meta:
        model = WebPushSubscription
        fields = ['id', 'subscription_info', 'browser', 'is_active', 'created_at']
        read_only_fields = ['id', 'is_active', 'created_at']
