"""
Tests for apps.notifications.services — NotificationService & NotificationDeliveryService.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.notifications.models import Notification, UserDevice, WebPushSubscription
from apps.notifications.services import NotificationDeliveryService, NotificationService

# ══════════════════════════════════════════════════════════════════════
#  NotificationService.create
# ══════════════════════════════════════════════════════════════════════


class TestNotificationServiceCreate:
    """Tests for the centralised notification creation factory."""

    def test_create_basic(self, notif_user):
        """Create a notification with minimal args."""
        n = NotificationService.create(
            user=notif_user,
            notification_type="reminder",
            title="Hello",
            body="World",
        )
        assert isinstance(n, Notification)
        assert n.user == notif_user
        assert n.notification_type == "reminder"
        assert n.title == "Hello"
        assert n.body == "World"
        assert n.status == "pending"
        assert n.data == {}
        assert n.action_url == ""
        assert n.image_url == ""
        assert n.scheduled_for is not None

    def test_create_all_types(self, notif_user):
        """Every Notification.TYPE_CHOICES value is accepted."""
        for code, _label in Notification.TYPE_CHOICES:
            n = NotificationService.create(
                user=notif_user,
                notification_type=code,
                title=f"Title {code}",
                body=f"Body {code}",
            )
            assert n.notification_type == code

    def test_create_with_optional_fields(self, notif_user):
        """Optional fields (data, action_url, image_url, scheduled_for, sent_at) are persisted."""
        now = timezone.now()
        n = NotificationService.create(
            user=notif_user,
            notification_type="achievement",
            title="Achievement",
            body="You did it",
            data={"key": "value"},
            action_url="/dreams/123",
            image_url="https://img.example.com/a.png",
            scheduled_for=now,
            status="sent",
            sent_at=now,
        )
        assert n.data == {"key": "value"}
        assert n.action_url == "/dreams/123"
        assert n.image_url == "https://img.example.com/a.png"
        assert n.scheduled_for == now
        assert n.status == "sent"
        assert n.sent_at == now

    def test_create_defaults_data_to_dict(self, notif_user):
        """Passing data=None results in an empty dict, not None."""
        n = NotificationService.create(
            user=notif_user,
            notification_type="system",
            title="T",
            body="B",
            data=None,
        )
        assert n.data == {}

    def test_create_stores_in_database(self, notif_user):
        """Notification is persisted and retrievable from DB."""
        n = NotificationService.create(
            user=notif_user,
            notification_type="buddy",
            title="Buddy!",
            body="New buddy",
        )
        from_db = Notification.objects.get(pk=n.pk)
        assert from_db.title == "Buddy!"


# ══════════════════════════════════════════════════════════════════════
#  NotificationDeliveryService
# ══════════════════════════════════════════════════════════════════════


class TestNotificationDeliveryService:
    """Tests for multi-channel notification delivery."""

    @pytest.fixture
    def delivery_service(self):
        """Return a delivery service with a mocked channel layer."""
        with patch(
            "apps.notifications.services.get_channel_layer"
        ) as mock_get_cl:
            mock_cl = MagicMock()
            mock_get_cl.return_value = mock_cl
            svc = NotificationDeliveryService()
            svc._mock_channel_layer = mock_cl
            yield svc

    @pytest.fixture
    def pending_notification(self, notif_user):
        """A pending notification ready for delivery."""
        notif_user.notification_prefs = None
        notif_user.save(update_fields=["notification_prefs"])
        return Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="Deliver me",
            body="Please",
            scheduled_for=timezone.now(),
            status="pending",
        )

    # ── Max retries ──────────────────────────────────────────────

    def test_deliver_skips_when_max_retries_exceeded(
        self, delivery_service, pending_notification
    ):
        """If retry_count >= max_retries, deliver returns False immediately."""
        pending_notification.retry_count = 5
        pending_notification.max_retries = 3
        pending_notification.save()
        result = delivery_service.deliver(pending_notification)
        assert result is False

    # ── WebSocket channel ────────────────────────────────────────

    def test_deliver_sends_websocket(self, delivery_service, pending_notification):
        """WebSocket is sent by default (websocket_enabled defaults to True)."""
        with patch.object(
            delivery_service, "_send_websocket", return_value=True
        ) as ws_mock, patch.object(
            delivery_service, "_send_fcm", return_value=False
        ), patch.object(
            delivery_service, "_send_webpush", return_value=False
        ):
            result = delivery_service.deliver(pending_notification)
            ws_mock.assert_called_once_with(pending_notification)
            assert result is True

    def test_websocket_disabled_via_prefs(self, delivery_service, pending_notification):
        """When websocket_enabled=False, _send_websocket is NOT called."""
        user = pending_notification.user
        user.notification_prefs = {"websocket_enabled": False}
        user.save(update_fields=["notification_prefs"])
        with patch.object(
            delivery_service, "_send_websocket", return_value=True
        ) as ws_mock, patch.object(
            delivery_service, "_send_fcm", return_value=False
        ), patch.object(
            delivery_service, "_send_webpush", return_value=False
        ), patch.object(
            delivery_service, "_send_email", return_value=False
        ):
            delivery_service.deliver(pending_notification)
            ws_mock.assert_not_called()

    # ── Email channel ────────────────────────────────────────────

    def test_email_sent_when_enabled(self, delivery_service, pending_notification):
        """When email_enabled=True, _send_email is called."""
        user = pending_notification.user
        user.notification_prefs = {"email_enabled": True}
        user.save(update_fields=["notification_prefs"])
        with patch.object(
            delivery_service, "_send_websocket", return_value=False
        ), patch.object(
            delivery_service, "_send_email", return_value=True
        ) as email_mock, patch.object(
            delivery_service, "_send_fcm", return_value=False
        ), patch.object(
            delivery_service, "_send_webpush", return_value=False
        ):
            result = delivery_service.deliver(pending_notification)
            email_mock.assert_called_once_with(pending_notification)
            assert result is True

    def test_email_fallback_when_all_fail(self, delivery_service, pending_notification):
        """Email is sent as fallback when all other channels fail and email was not tried."""
        user = pending_notification.user
        user.notification_prefs = {"email_enabled": False}
        user.save(update_fields=["notification_prefs"])
        with patch.object(
            delivery_service, "_send_websocket", return_value=False
        ), patch.object(
            delivery_service, "_send_fcm", return_value=False
        ), patch.object(
            delivery_service, "_send_webpush", return_value=False
        ), patch.object(
            delivery_service, "_send_email", return_value=True
        ) as email_mock:
            result = delivery_service.deliver(pending_notification)
            email_mock.assert_called_once_with(pending_notification)
            assert result is True

    def test_no_email_fallback_when_already_tried(
        self, delivery_service, pending_notification
    ):
        """When email_enabled=True and already tried, email fallback is skipped."""
        user = pending_notification.user
        user.notification_prefs = {"email_enabled": True}
        user.save(update_fields=["notification_prefs"])
        with patch.object(
            delivery_service, "_send_websocket", return_value=False
        ), patch.object(
            delivery_service, "_send_email", return_value=False
        ) as email_mock, patch.object(
            delivery_service, "_send_fcm", return_value=False
        ), patch.object(
            delivery_service, "_send_webpush", return_value=False
        ):
            result = delivery_service.deliver(pending_notification)
            # email called once (from prefs) but NOT again as fallback
            assert email_mock.call_count == 1
            assert result is False

    # ── FCM / push channel ───────────────────────────────────────

    def test_fcm_sent_when_push_enabled(self, delivery_service, pending_notification):
        """FCM is attempted when push_enabled (default True)."""
        with patch.object(
            delivery_service, "_send_websocket", return_value=False
        ), patch.object(
            delivery_service, "_send_fcm", return_value=True
        ) as fcm_mock, patch.object(
            delivery_service, "_send_email", return_value=False
        ):
            result = delivery_service.deliver(pending_notification)
            fcm_mock.assert_called_once_with(pending_notification)
            assert result is True

    def test_webpush_fallback_when_fcm_fails(
        self, delivery_service, pending_notification
    ):
        """Web push VAPID is tried when FCM returns False."""
        with patch.object(
            delivery_service, "_send_websocket", return_value=False
        ), patch.object(
            delivery_service, "_send_fcm", return_value=False
        ), patch.object(
            delivery_service, "_send_webpush", return_value=True
        ) as wp_mock, patch.object(
            delivery_service, "_send_email", return_value=False
        ):
            result = delivery_service.deliver(pending_notification)
            wp_mock.assert_called_once_with(pending_notification)
            assert result is True

    def test_webpush_skipped_when_fcm_succeeds(
        self, delivery_service, pending_notification
    ):
        """Web push is NOT tried when FCM succeeds."""
        with patch.object(
            delivery_service, "_send_websocket", return_value=False
        ), patch.object(
            delivery_service, "_send_fcm", return_value=True
        ), patch.object(
            delivery_service, "_send_webpush", return_value=False
        ) as wp_mock, patch.object(
            delivery_service, "_send_email", return_value=False
        ):
            delivery_service.deliver(pending_notification)
            wp_mock.assert_not_called()

    def test_push_disabled_skips_fcm_and_webpush(
        self, delivery_service, pending_notification
    ):
        """When push_enabled=False, neither FCM nor webpush are called."""
        user = pending_notification.user
        user.notification_prefs = {"push_enabled": False}
        user.save(update_fields=["notification_prefs"])
        with patch.object(
            delivery_service, "_send_websocket", return_value=False
        ), patch.object(
            delivery_service, "_send_fcm", return_value=False
        ) as fcm_mock, patch.object(
            delivery_service, "_send_webpush", return_value=False
        ) as wp_mock, patch.object(
            delivery_service, "_send_email", return_value=False
        ):
            delivery_service.deliver(pending_notification)
            fcm_mock.assert_not_called()
            wp_mock.assert_not_called()

    # ── _send_websocket ──────────────────────────────────────────

    def test_send_websocket_success(self, delivery_service, pending_notification):
        """_send_websocket returns True when channel layer succeeds."""
        # async_to_sync wraps group_send, so make it a coroutine mock

        async def fake_group_send(*args, **kwargs):
            pass

        delivery_service._mock_channel_layer.group_send = fake_group_send
        result = delivery_service._send_websocket(pending_notification)
        assert result is True

    def test_send_websocket_exception_returns_false(
        self, delivery_service, pending_notification
    ):
        """_send_websocket returns False when channel layer raises."""

        async def fail_group_send(*args, **kwargs):
            raise Exception("boom")

        delivery_service._mock_channel_layer.group_send = fail_group_send
        result = delivery_service._send_websocket(pending_notification)
        assert result is False

    # ── _send_email ──────────────────────────────────────────────

    def test_send_email_success(self, delivery_service, pending_notification):
        """_send_email returns True when send_templated_email succeeds."""
        # The import is local: `from core.email import send_templated_email`
        # Patch at the source module so the local import picks up the mock.
        with patch("core.email.send_templated_email") as mock_send:
            result = delivery_service._send_email(pending_notification)
            assert result is True
            mock_send.assert_called_once()

    def test_send_email_exception_returns_false(
        self, delivery_service, pending_notification
    ):
        """_send_email returns False when email sending raises."""
        with patch(
            "core.email.send_templated_email", side_effect=Exception("smtp down")
        ):
            result = delivery_service._send_email(pending_notification)
            assert result is False

    # ── _send_fcm ────────────────────────────────────────────────

    def test_send_fcm_no_devices_returns_false(
        self, delivery_service, pending_notification
    ):
        """_send_fcm returns False when user has no active devices."""
        result = delivery_service._send_fcm(pending_notification)
        assert result is False

    def test_send_fcm_single_token_success(
        self, delivery_service, pending_notification, mock_fcm
    ):
        """_send_fcm returns True when single token send succeeds."""
        user = pending_notification.user
        UserDevice.objects.create(
            user=user,
            fcm_token="test-token-abc",
            platform="android",
            is_active=True,
        )
        mock_fcm["messaging"].send.return_value = "projects/test/messages/123"
        result = delivery_service._send_fcm(pending_notification)
        assert result is True

    def test_send_fcm_invalid_token_deactivates_device(
        self, delivery_service, pending_notification, mock_fcm
    ):
        """_send_fcm deactivates device when InvalidTokenError is raised."""
        user = pending_notification.user
        device = UserDevice.objects.create(
            user=user,
            fcm_token="bad-token-xyz",
            platform="ios",
            is_active=True,
        )
        from apps.notifications.fcm_service import InvalidTokenError

        # _send_fcm imports FCMService locally from .fcm_service,
        # so patch it at the source module.
        with patch(
            "apps.notifications.fcm_service.FCMService"
        ) as MockFCMService:
            mock_instance = MockFCMService.return_value
            mock_instance.send_to_token.side_effect = InvalidTokenError("bad-token-xyz")
            result = delivery_service._send_fcm(pending_notification)

        assert result is False
        device.refresh_from_db()
        assert device.is_active is False

    def test_send_fcm_multicast_deactivates_invalid_tokens(
        self, delivery_service, pending_notification, mock_fcm
    ):
        """_send_fcm with multiple tokens deactivates invalid ones via multicast."""
        user = pending_notification.user
        d1 = UserDevice.objects.create(
            user=user, fcm_token="good-token", platform="android", is_active=True
        )
        d2 = UserDevice.objects.create(
            user=user, fcm_token="bad-token", platform="android", is_active=True
        )

        mock_result = MagicMock()
        mock_result.invalid_tokens = ["bad-token"]
        mock_result.any_success = True
        mock_result.success_count = 1
        mock_result.total = 2

        with patch(
            "apps.notifications.fcm_service.FCMService"
        ) as MockFCMService:
            mock_instance = MockFCMService.return_value
            mock_instance.send_multicast.return_value = mock_result
            result = delivery_service._send_fcm(pending_notification)

        assert result is True
        d2.refresh_from_db()
        assert d2.is_active is False
        d1.refresh_from_db()
        assert d1.is_active is True

    # ── _send_webpush ────────────────────────────────────────────

    def test_send_webpush_no_subscriptions_returns_false(
        self, delivery_service, pending_notification
    ):
        """_send_webpush returns False when user has no active subscriptions."""
        result = delivery_service._send_webpush(pending_notification)
        assert result is False

    def test_send_webpush_success(self, delivery_service, pending_notification):
        """_send_webpush returns True when webpush send succeeds."""
        user = pending_notification.user
        WebPushSubscription.objects.create(
            user=user,
            subscription_info={"endpoint": "https://push.example.com", "keys": {}},
            is_active=True,
        )
        with patch.dict("sys.modules", {"pywebpush": MagicMock()}), patch(
            "apps.notifications.services.settings"
        ) as mock_settings:
            mock_settings.WEBPUSH_SETTINGS = {
                "VAPID_PRIVATE_KEY": "fake-key",
                "VAPID_ADMIN_EMAIL": "admin@example.com",
            }
            mock_settings.FRONTEND_URL = "https://stepora.app"
            # Re-import to pick up our mocked pywebpush

            # Instead of re-import, directly patch the webpush callable
            with patch(
                "pywebpush.webpush"
            ) as mock_webpush:
                result = delivery_service._send_webpush(pending_notification)
                assert result is True

    def test_send_webpush_no_vapid_key_returns_false(
        self, delivery_service, pending_notification
    ):
        """_send_webpush returns False when VAPID_PRIVATE_KEY is empty."""
        user = pending_notification.user
        WebPushSubscription.objects.create(
            user=user,
            subscription_info={"endpoint": "https://push.example.com", "keys": {}},
            is_active=True,
        )
        with patch(
            "apps.notifications.services.settings"
        ) as mock_settings:
            mock_settings.WEBPUSH_SETTINGS = {
                "VAPID_PRIVATE_KEY": "",
                "VAPID_ADMIN_EMAIL": "",
            }
            result = delivery_service._send_webpush(pending_notification)
            assert result is False
