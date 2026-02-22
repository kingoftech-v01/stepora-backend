"""
Notification delivery service — orchestrates WebSocket, Email, and Web Push channels.
"""

import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


class NotificationDeliveryService:
    """Delivers notifications via multiple channels based on user preferences."""

    def __init__(self):
        self.channel_layer = get_channel_layer()

    def deliver(self, notification):
        """
        Deliver notification via all enabled channels.
        Returns True if at least one channel succeeded.
        """
        user = notification.user
        prefs = user.notification_prefs or {}
        results = []

        # WebSocket (default: enabled)
        if prefs.get('websocket_enabled', True):
            results.append(self._send_websocket(notification))

        # Email (default: disabled — opt-in)
        if prefs.get('email_enabled', False):
            results.append(self._send_email(notification))

        # Web Push (default: enabled if user has subscriptions)
        if prefs.get('push_enabled', True):
            results.append(self._send_webpush(notification))

        return any(results)

    def _send_websocket(self, notification):
        """Send notification via WebSocket channel layer."""
        try:
            group_name = f'notifications_{notification.user.id}'
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    'type': 'send_notification',
                    'notification': {
                        'id': str(notification.id),
                        'notification_type': notification.notification_type,
                        'title': notification.title,
                        'body': notification.body,
                        'data': notification.data,
                        'image_url': notification.image_url,
                        'action_url': notification.action_url,
                        'created_at': notification.created_at.isoformat(),
                    },
                }
            )
            logger.debug(f"WebSocket sent for notification {notification.id}")
            return True
        except Exception as e:
            logger.warning(f"WebSocket delivery failed for {notification.id}: {e}")
            return False

    def _send_email(self, notification):
        """Send notification via email."""
        try:
            user = notification.user
            context = {
                'title': notification.title,
                'body': notification.body,
                'action_url': notification.action_url or settings.FRONTEND_URL,
                'user_name': user.display_name or user.email,
            }

            text_content = render_to_string(
                'notifications/email/notification.txt', context
            )
            html_content = render_to_string(
                'notifications/email/notification.html', context
            )

            email = EmailMultiAlternatives(
                subject=notification.title,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email.attach_alternative(html_content, 'text/html')
            email.send(fail_silently=False)

            logger.debug(f"Email sent for notification {notification.id} to {user.email}")
            return True
        except Exception as e:
            logger.warning(f"Email delivery failed for {notification.id}: {e}")
            return False

    def _send_webpush(self, notification):
        """Send notification via Web Push (VAPID)."""
        try:
            from pywebpush import webpush, WebPushException
            from .models import WebPushSubscription

            subscriptions = WebPushSubscription.objects.filter(
                user=notification.user,
                is_active=True,
            )

            if not subscriptions.exists():
                return False

            vapid_settings = getattr(settings, 'WEBPUSH_SETTINGS', {})
            vapid_private_key = vapid_settings.get('VAPID_PRIVATE_KEY', '')
            vapid_admin_email = vapid_settings.get('VAPID_ADMIN_EMAIL', '')

            if not vapid_private_key:
                logger.warning("VAPID_PRIVATE_KEY not configured, skipping web push")
                return False

            import json
            payload = json.dumps({
                'title': notification.title,
                'body': notification.body,
                'data': notification.data,
                'icon': '/static/icon-192.png',
                'url': notification.action_url or '/',
            })

            sent = False
            for sub in subscriptions:
                try:
                    webpush(
                        subscription_info=sub.subscription_info,
                        data=payload,
                        vapid_private_key=vapid_private_key,
                        vapid_claims={
                            'sub': f'mailto:{vapid_admin_email}',
                        },
                    )
                    sent = True
                except WebPushException as e:
                    if e.response and e.response.status_code in (404, 410):
                        # Subscription expired or invalid — deactivate
                        sub.is_active = False
                        sub.save(update_fields=['is_active'])
                        logger.info(f"Deactivated expired push subscription {sub.id}")
                    else:
                        logger.warning(f"Web push failed for subscription {sub.id}: {e}")
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
