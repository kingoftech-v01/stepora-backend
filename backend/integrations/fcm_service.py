"""
Firebase Cloud Messaging service for push notifications.
"""

from firebase_admin import messaging
from django.utils import timezone
from core.exceptions import NotificationError
from apps.users.models import FcmToken


class FCMService:
    """Service for sending push notifications via Firebase Cloud Messaging."""

    def send_notification(self, notification_obj):
        """
        Send a single notification to a user.

        Args:
            notification_obj: Notification model instance

        Returns:
            bool: True if sent successfully

        Raises:
            NotificationError: If sending fails
        """
        user = notification_obj.user

        # Check if it's DND time
        if not notification_obj.should_send():
            # Reschedule for later
            self._reschedule_after_dnd(notification_obj)
            return False

        # Get active FCM tokens
        tokens = list(
            FcmToken.objects.filter(
                user=user,
                is_active=True
            ).values_list('token', flat=True)
        )

        if not tokens:
            notification_obj.mark_failed('No active FCM tokens')
            return False

        try:
            # Prepare message
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=notification_obj.title,
                    body=notification_obj.body,
                ),
                data=self._prepare_data(notification_obj.data),
                tokens=tokens,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        channel_id=notification_obj.notification_type,
                        sound='default',
                        color='#8B5CF6',  # Purple primary color
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound='default',
                            badge=1,
                            content_available=True,
                        ),
                    ),
                ),
            )

            # Send multicast message
            response = messaging.send_multicast(message)

            # Handle successful sends
            notification_obj.mark_sent()

            # Handle failed tokens
            if response.failure_count > 0:
                self._handle_failed_tokens(tokens, response)

            return True

        except messaging.FirebaseError as e:
            error_msg = f"FCM error: {str(e)}"
            notification_obj.mark_failed(error_msg)
            raise NotificationError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            notification_obj.mark_failed(error_msg)
            raise NotificationError(error_msg)

    def send_to_topic(self, topic, title, body, data=None):
        """
        Send notification to a topic (group of users).

        Args:
            topic: Topic name
            title: Notification title
            body: Notification body
            data: Optional data dictionary

        Returns:
            str: Message ID
        """
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=self._prepare_data(data or {}),
                topic=topic,
            )

            message_id = messaging.send(message)
            return message_id

        except messaging.FirebaseError as e:
            raise NotificationError(f"Failed to send to topic: {str(e)}")

    def subscribe_to_topic(self, tokens, topic):
        """Subscribe tokens to a topic."""
        try:
            response = messaging.subscribe_to_topic(tokens, topic)
            return response
        except messaging.FirebaseError as e:
            raise NotificationError(f"Failed to subscribe to topic: {str(e)}")

    def unsubscribe_from_topic(self, tokens, topic):
        """Unsubscribe tokens from a topic."""
        try:
            response = messaging.unsubscribe_from_topic(tokens, topic)
            return response
        except messaging.FirebaseError as e:
            raise NotificationError(f"Failed to unsubscribe from topic: {str(e)}")

    def _prepare_data(self, data_dict):
        """Prepare data payload - all values must be strings."""
        if not data_dict:
            return {}

        return {
            key: str(value) for key, value in data_dict.items()
        }

    def _handle_failed_tokens(self, tokens, response):
        """Remove invalid/expired FCM tokens."""
        if response.failure_count == 0:
            return

        # Get failed token indices
        failed_tokens = []
        for idx, result in enumerate(response.responses):
            if not result.success:
                failed_tokens.append(tokens[idx])

        # Deactivate failed tokens
        if failed_tokens:
            FcmToken.objects.filter(
                token__in=failed_tokens
            ).update(is_active=False)

    def _reschedule_after_dnd(self, notification_obj):
        """Reschedule notification for after DND period."""
        user = notification_obj.user

        if not user.notification_prefs:
            return

        dnd_end = user.notification_prefs.get('dndEnd', 7)

        # Get user's timezone
        user_tz = timezone.pytz.timezone(user.timezone)
        now = timezone.now().astimezone(user_tz)

        # Calculate next send time (after DND end)
        next_send = now.replace(hour=dnd_end, minute=0, second=0, microsecond=0)

        # If DND end already passed today, schedule for tomorrow
        if next_send <= now:
            next_send += timezone.timedelta(days=1)

        # Update notification
        notification_obj.scheduled_for = next_send
        notification_obj.save(update_fields=['scheduled_for'])

    def send_batch_notifications(self, notifications_list):
        """
        Send multiple notifications efficiently.

        Args:
            notifications_list: List of Notification model instances

        Returns:
            dict: Statistics about sent notifications
        """
        total = len(notifications_list)
        sent = 0
        failed = 0

        for notification in notifications_list:
            try:
                if self.send_notification(notification):
                    sent += 1
                else:
                    failed += 1
            except NotificationError:
                failed += 1

        return {
            'total': total,
            'sent': sent,
            'failed': failed,
        }
