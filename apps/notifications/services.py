"""
Notification services — centralized creation and multi-channel delivery.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Centralized notification creation."""

    @staticmethod
    def create(user, notification_type, title, body, data=None, action_url=None,
               image_url=None, scheduled_for=None, status="pending", sent_at=None):
        """
        Centralized notification creation.

        Args:
            user: The user to notify.
            notification_type: Type of notification (e.g. 'buddy', 'achievement').
            title: Notification title.
            body: Notification body text.
            data: Optional JSON data dict for deep linking.
            action_url: Optional deep link URL.
            image_url: Optional image URL for rich notifications.
            scheduled_for: When to send (defaults to now).
            status: Initial status (defaults to 'pending').
            sent_at: Optional sent timestamp (for pre-sent notifications).

        Returns:
            The created Notification instance.
        """
        from django.utils import timezone

        from .models import Notification

        kwargs = {
            "user": user,
            "notification_type": notification_type,
            "title": title,
            "body": body,
            "data": data or {},
            "action_url": action_url or "",
            "image_url": image_url or "",
            "scheduled_for": scheduled_for or timezone.now(),
            "status": status,
        }
        if sent_at is not None:
            kwargs["sent_at"] = sent_at

        notification = Notification.objects.create(**kwargs)
        return notification


class NotificationDeliveryService:
    """Delivers notifications via multiple channels based on user preferences."""

    def __init__(self):
        self.channel_layer = get_channel_layer()

    def deliver(self, notification):
        """
        Deliver notification via all enabled channels.
        Returns True if at least one channel succeeded.
        """
        if notification.retry_count >= notification.max_retries:
            logger.warning(
                "Notification %s exceeded max retries, skipping", notification.id
            )
            return False

        user = notification.user
        prefs = user.notification_prefs or {}
        results = []

        # WebSocket (default: enabled)
        if prefs.get("websocket_enabled", True):
            results.append(self._send_websocket(notification))

        # Email (default: disabled — opt-in)
        email_enabled = prefs.get("email_enabled", False)
        if email_enabled:
            results.append(self._send_email(notification))

        # FCM Push (default: enabled if user has devices)
        fcm_sent = False
        if prefs.get("push_enabled", True):
            fcm_sent = self._send_fcm(notification)
            results.append(fcm_sent)

        # Web Push VAPID fallback (only if FCM didn't send and user has subscriptions)
        if prefs.get("push_enabled", True) and not fcm_sent:
            results.append(self._send_webpush(notification))

        # Email fallback: if no channel succeeded and email was not already tried, send email
        if not any(results) and not email_enabled:
            results.append(self._send_email(notification))

        return any(results)

    def _send_websocket(self, notification):
        """Send notification via WebSocket channel layer."""
        try:
            group_name = f"notifications_{notification.user.id}"
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    "type": "send_notification",
                    "notification": {
                        "id": str(notification.id),
                        "notification_type": notification.notification_type,
                        "title": notification.title,
                        "body": notification.body,
                        "data": notification.data,
                        "image_url": notification.image_url,
                        "action_url": notification.action_url,
                        "created_at": notification.created_at.isoformat(),
                    },
                },
            )
            logger.debug(f"WebSocket sent for notification {notification.id}")
            return True
        except Exception as e:
            logger.error(
                f"WebSocket delivery failed for {notification.id}: {e}", exc_info=True
            )
            return False

    def _send_email(self, notification):
        """Send notification via email using the glassmorphism template."""
        try:
            from core.email import send_templated_email

            user = notification.user

            send_templated_email(
                template_name="notifications/notification",
                subject=notification.title,
                to=[user.email],
                context={
                    "title": notification.title,
                    "body": notification.body,
                    "action_url": notification.action_url or settings.FRONTEND_URL,
                    "user_name": user.display_name or user.email,
                },
                from_name="Stepora Notifications",
            )

            logger.debug(
                f"Email sent for notification {notification.id} to {user.email}"
            )
            return True
        except Exception as e:
            logger.warning(f"Email delivery failed for {notification.id}: {e}")
            return False

    def _send_fcm(self, notification):
        """Send notification via Firebase Cloud Messaging to all user devices."""
        try:
            from .fcm_service import FCMService, InvalidTokenError
            from .models import UserDevice

            devices = UserDevice.objects.filter(
                user=notification.user,
                is_active=True,
            )

            tokens = list(devices.values_list("fcm_token", flat=True))
            if not tokens:
                return False

            fcm = FCMService()

            # Prepare data payload — all values must be strings
            data = {}
            if notification.data:
                data = {k: str(v) for k, v in notification.data.items()}
            data["notification_id"] = str(notification.id)
            data["notification_type"] = notification.notification_type

            if len(tokens) == 1:
                try:
                    message_id = fcm.send_to_token(
                        token=tokens[0],
                        title=notification.title,
                        body=notification.body,
                        data=data,
                        image_url=notification.image_url,
                    )
                    if message_id:
                        logger.debug(f"FCM sent for notification {notification.id}")
                        return True
                    return False
                except InvalidTokenError:
                    UserDevice.objects.filter(fcm_token=tokens[0]).update(
                        is_active=False
                    )
                    logger.info(
                        f"Deactivated invalid FCM token for user {notification.user.id}"
                    )
                    return False
                except Exception as e:
                    logger.error(
                        f"FCM send failed for notification {notification.id}: {e}",
                        exc_info=True,
                    )
                    return False
            else:
                result = fcm.send_multicast(
                    tokens=tokens,
                    title=notification.title,
                    body=notification.body,
                    data=data,
                    image_url=notification.image_url,
                )

                # Deactivate invalid tokens
                if result.invalid_tokens:
                    UserDevice.objects.filter(
                        fcm_token__in=result.invalid_tokens
                    ).update(is_active=False)
                    logger.info(
                        f"Deactivated {len(result.invalid_tokens)} invalid FCM tokens "
                        f"for user {notification.user.id}"
                    )

                if result.any_success:
                    logger.debug(
                        f"FCM multicast for notification {notification.id}: "
                        f"{result.success_count}/{result.total} succeeded"
                    )
                return result.any_success

        except ImportError:
            logger.warning("firebase-admin not installed, skipping FCM delivery")
            return False
        except Exception as e:
            logger.warning(
                f"FCM delivery failed for notification {notification.id}: {e}"
            )
            return False

    def _send_webpush(self, notification):
        """Send notification via Web Push (VAPID). Deprecated: use FCM instead."""
        try:
            from pywebpush import WebPushException, webpush

            from .models import WebPushSubscription

            subscriptions = WebPushSubscription.objects.filter(
                user=notification.user,
                is_active=True,
            )

            if not subscriptions.exists():
                return False

            vapid_settings = getattr(settings, "WEBPUSH_SETTINGS", {})
            vapid_private_key = vapid_settings.get("VAPID_PRIVATE_KEY", "")
            vapid_admin_email = vapid_settings.get("VAPID_ADMIN_EMAIL", "")

            if not vapid_private_key:
                logger.warning("VAPID_PRIVATE_KEY not configured, skipping web push")
                return False

            import json

            payload = json.dumps(
                {
                    "title": notification.title,
                    "body": notification.body,
                    "data": notification.data,
                    "icon": "/static/icon-192.png",
                    "url": notification.action_url or "/",
                }
            )

            sent = False
            for sub in subscriptions:
                try:
                    webpush(
                        subscription_info=sub.subscription_info,
                        data=payload,
                        vapid_private_key=vapid_private_key,
                        vapid_claims={
                            "sub": f"mailto:{vapid_admin_email}",
                        },
                    )
                    sent = True
                except WebPushException as e:
                    if e.response and e.response.status_code in (404, 410):
                        sub.is_active = False
                        sub.save(update_fields=["is_active"])
                        logger.info(f"Deactivated expired push subscription {sub.id}")
                    else:
                        logger.warning(
                            f"Web push failed for subscription {sub.id}: {e}"
                        )
                except Exception as e:
                    logger.warning(f"Web push error for subscription {sub.id}: {e}")

            if sent:
                logger.debug(f"Web push sent for notification {notification.id}")
            return sent
        except ImportError:
            logger.warning("pywebpush not installed, skipping web push delivery")
            return False
        except Exception as e:
            logger.warning(f"Web push delivery failed for {notification.id}: {e}")
            return False
