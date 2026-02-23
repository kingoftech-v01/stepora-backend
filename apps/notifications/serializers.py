"""
Serializers for Notifications app.
"""

from rest_framework import serializers
from core.sanitizers import sanitize_text
from .models import Notification, NotificationTemplate, NotificationBatch, WebPushSubscription


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model."""

    is_read = serializers.SerializerMethodField(help_text='Whether the notification has been read.')

    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'notification_type', 'title', 'body',
            'data', 'scheduled_for', 'sent_at', 'read_at',
            'status', 'is_read',
            'created_at'
        ]
        read_only_fields = ['id', 'user', 'sent_at', 'read_at', 'status', 'created_at']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the notification.'},
            'user': {'help_text': 'User who receives this notification.'},
            'notification_type': {'help_text': 'Category of the notification.'},
            'title': {'help_text': 'Title displayed in the notification.'},
            'body': {'help_text': 'Body text of the notification.'},
            'data': {'help_text': 'Additional payload data for the notification.'},
            'scheduled_for': {'help_text': 'Scheduled delivery time for the notification.'},
            'sent_at': {'help_text': 'Timestamp when the notification was sent.'},
            'read_at': {'help_text': 'Timestamp when the notification was read.'},
            'status': {'help_text': 'Current delivery status of the notification.'},
            'created_at': {'help_text': 'Timestamp when the notification was created.'},
        }

    def get_is_read(self, obj) -> bool:
        return obj.read_at is not None


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notifications."""

    class Meta:
        model = Notification
        fields = [
            'notification_type', 'title', 'body',
            'data', 'scheduled_for'
        ]
        extra_kwargs = {
            'notification_type': {'help_text': 'Category of the notification to create.'},
            'title': {'help_text': 'Title to display in the notification.'},
            'body': {'help_text': 'Body text of the notification.'},
            'data': {'help_text': 'Additional payload data for the notification.'},
            'scheduled_for': {'help_text': 'Optional future time to deliver the notification.'},
        }

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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the template.'},
            'name': {'help_text': 'Internal name of the notification template.'},
            'notification_type': {'help_text': 'Type of notification this template generates.'},
            'title_template': {'help_text': 'Template string for the notification title.'},
            'body_template': {'help_text': 'Template string for the notification body.'},
            'available_variables': {'help_text': 'Variables that can be used in the template.'},
            'is_active': {'help_text': 'Whether this template is currently in use.'},
            'created_at': {'help_text': 'Timestamp when the template was created.'},
            'updated_at': {'help_text': 'Timestamp when the template was last updated.'},
        }


class NotificationBatchSerializer(serializers.ModelSerializer):
    """Serializer for Notification batches."""

    success_rate = serializers.SerializerMethodField(help_text='Percentage of notifications successfully sent.')

    class Meta:
        model = NotificationBatch
        fields = [
            'id', 'name', 'notification_type',
            'total_scheduled', 'total_sent', 'total_failed',
            'status', 'success_rate',
            'created_at', 'completed_at'
        ]
        read_only_fields = fields
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the batch.'},
            'name': {'help_text': 'Name of the notification batch.'},
            'notification_type': {'help_text': 'Type of notifications in this batch.'},
            'total_scheduled': {'help_text': 'Total notifications scheduled in the batch.'},
            'total_sent': {'help_text': 'Total notifications successfully sent.'},
            'total_failed': {'help_text': 'Total notifications that failed to send.'},
            'status': {'help_text': 'Current processing status of the batch.'},
            'created_at': {'help_text': 'Timestamp when the batch was created.'},
            'completed_at': {'help_text': 'Timestamp when the batch finished processing.'},
        }

    def get_success_rate(self, obj) -> float:
        if obj.total_scheduled == 0:
            return 0.0
        return round((obj.total_sent / obj.total_scheduled) * 100, 2)


class WebPushSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Web Push subscriptions."""

    class Meta:
        model = WebPushSubscription
        fields = ['id', 'subscription_info', 'browser', 'is_active', 'created_at']
        read_only_fields = ['id', 'is_active', 'created_at']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the subscription.'},
            'subscription_info': {'help_text': 'Web Push subscription endpoint and keys.'},
            'browser': {'help_text': 'Browser used for this push subscription.'},
            'is_active': {'help_text': 'Whether this subscription is currently active.'},
            'created_at': {'help_text': 'Timestamp when the subscription was created.'},
        }
