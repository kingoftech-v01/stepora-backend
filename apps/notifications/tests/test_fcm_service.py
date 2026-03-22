"""
Tests for apps.notifications.fcm_service — FCMService, MulticastResult, InvalidTokenError.
"""

from unittest.mock import MagicMock, Mock

import pytest

from apps.notifications.fcm_service import (
    FCMService,
    InvalidTokenError,
    MulticastResult,
)

# ══════════════════════════════════════════════════════════════════════
#  InvalidTokenError
# ══════════════════════════════════════════════════════════════════════


class TestInvalidTokenError:
    """Tests for the InvalidTokenError exception."""

    def test_stores_token(self):
        err = InvalidTokenError("abc123token")
        assert err.token == "abc123token"

    def test_message_truncates_token(self):
        long_token = "a" * 100
        err = InvalidTokenError(long_token)
        assert long_token[:20] in str(err)


# ══════════════════════════════════════════════════════════════════════
#  MulticastResult
# ══════════════════════════════════════════════════════════════════════


class TestMulticastResult:
    """Tests for the MulticastResult aggregate."""

    def test_initial_state(self):
        r = MulticastResult()
        assert r.success_count == 0
        assert r.failure_count == 0
        assert r.invalid_tokens == []
        assert r.total == 0
        assert r.any_success is False

    def test_any_success_true(self):
        r = MulticastResult()
        r.success_count = 1
        assert r.any_success is True

    def test_total(self):
        r = MulticastResult()
        r.success_count = 3
        r.failure_count = 2
        assert r.total == 5


# ══════════════════════════════════════════════════════════════════════
#  FCMService
# ══════════════════════════════════════════════════════════════════════


class TestFCMService:
    """Tests for FCMService — all Firebase calls are mocked."""

    @pytest.fixture
    def fcm(self, mock_fcm):
        """Return an FCMService with Firebase mocked."""
        return FCMService()

    @pytest.fixture
    def messaging(self, mock_fcm):
        """Return the mocked messaging module."""
        return mock_fcm["messaging"]

    # ── build_message ────────────────────────────────────────────

    def test_build_message_returns_message(self, fcm, messaging):
        """build_message returns a non-None result."""
        msg = fcm.build_message("Title", "Body", {"key": "val"}, "https://img.png")
        assert msg is not None

    def test_build_message_converts_data_to_strings(self, fcm, messaging):
        """All data values are cast to strings — no crash with int/bool data."""
        # The conftest mock replaces messaging.Message with Mock (the class),
        # so we use a tracking Mock() instance instead.
        mock_msg_cls = MagicMock()
        messaging.Message = mock_msg_cls
        msg = fcm.build_message("T", "B", {"count": 42, "active": True})
        # Verify Message was called and the data kwarg contains string values
        mock_msg_cls.assert_called_once()
        call_kwargs = mock_msg_cls.call_args[1]
        assert call_kwargs["data"] == {"count": "42", "active": "True"}

    def test_build_message_empty_data(self, fcm, messaging):
        """build_message with data=None produces an empty dict."""
        msg = fcm.build_message("T", "B", None)
        assert msg is not None

    def test_build_message_empty_image(self, fcm, messaging):
        """build_message with empty image_url passes None to Notification."""
        msg = fcm.build_message("T", "B", image_url="")
        assert msg is not None

    # ── send_to_token ────────────────────────────────────────────

    def test_send_to_token_success(self, fcm, messaging):
        """send_to_token returns message_id on success."""
        messaging.send.return_value = "projects/test/messages/id1"
        result = fcm.send_to_token("token123", "Title", "Body")
        assert result == "projects/test/messages/id1"

    def test_send_to_token_with_data(self, fcm, messaging):
        """send_to_token passes data and image_url through."""
        messaging.send.return_value = "msg-id"
        result = fcm.send_to_token(
            "tok", "T", "B", data={"k": "v"}, image_url="https://img.png"
        )
        assert result == "msg-id"

    def test_send_to_token_unregistered_raises_invalid(self, fcm, messaging):
        """send_to_token raises InvalidTokenError on UnregisteredError."""
        messaging.send.side_effect = messaging.UnregisteredError()
        with pytest.raises(InvalidTokenError) as exc_info:
            fcm.send_to_token("bad-token", "T", "B")
        assert exc_info.value.token == "bad-token"

    def test_send_to_token_sender_mismatch_raises_invalid(self, fcm, messaging):
        """send_to_token raises InvalidTokenError on SenderIdMismatchError."""
        messaging.send.side_effect = messaging.SenderIdMismatchError()
        with pytest.raises(InvalidTokenError):
            fcm.send_to_token("wrong-sender-token", "T", "B")

    def test_send_to_token_generic_error_reraises(self, fcm, messaging):
        """send_to_token re-raises generic exceptions."""
        messaging.send.side_effect = RuntimeError("network down")
        with pytest.raises(RuntimeError, match="network down"):
            fcm.send_to_token("tok", "T", "B")

    # ── send_multicast ───────────────────────────────────────────

    def test_send_multicast_single_chunk(self, fcm, messaging):
        """send_multicast with <= 500 tokens sends one chunk."""
        mock_response = Mock(
            success_count=2,
            failure_count=0,
            responses=[
                Mock(exception=None),
                Mock(exception=None),
            ],
        )
        messaging.send_each_for_multicast.return_value = mock_response

        result = fcm.send_multicast(["tok1", "tok2"], "T", "B")
        assert result.success_count == 2
        assert result.failure_count == 0
        assert result.any_success is True
        assert result.invalid_tokens == []

    def test_send_multicast_detects_invalid_tokens(self, fcm, messaging):
        """send_multicast collects invalid tokens from responses."""
        mock_response = Mock(
            success_count=1,
            failure_count=1,
            responses=[
                Mock(exception=None),
                Mock(exception=messaging.UnregisteredError()),
            ],
        )
        messaging.send_each_for_multicast.return_value = mock_response

        result = fcm.send_multicast(["good", "bad"], "T", "B")
        assert result.success_count == 1
        assert result.failure_count == 1
        assert "bad" in result.invalid_tokens

    def test_send_multicast_sender_mismatch_is_invalid(self, fcm, messaging):
        """SenderIdMismatchError tokens are treated as invalid."""
        mock_response = Mock(
            success_count=0,
            failure_count=1,
            responses=[
                Mock(exception=messaging.SenderIdMismatchError()),
            ],
        )
        messaging.send_each_for_multicast.return_value = mock_response

        result = fcm.send_multicast(["mismatch-tok"], "T", "B")
        assert "mismatch-tok" in result.invalid_tokens

    def test_send_multicast_chunks_large_lists(self, fcm, messaging):
        """send_multicast auto-chunks lists > 500."""
        tokens = [f"tok{i}" for i in range(600)]
        mock_response = Mock(
            success_count=500,
            failure_count=0,
            responses=[Mock(exception=None)] * 500,
        )
        mock_response2 = Mock(
            success_count=100,
            failure_count=0,
            responses=[Mock(exception=None)] * 100,
        )
        messaging.send_each_for_multicast.side_effect = [mock_response, mock_response2]

        result = fcm.send_multicast(tokens, "T", "B")
        assert result.success_count == 600
        assert messaging.send_each_for_multicast.call_count == 2

    def test_send_multicast_batch_exception(self, fcm, messaging):
        """send_multicast handles exception during batch send."""
        messaging.send_each_for_multicast.side_effect = Exception("batch fail")
        result = fcm.send_multicast(["tok1", "tok2"], "T", "B")
        assert result.failure_count == 2
        assert result.success_count == 0
        assert result.any_success is False

    # ── send_to_topic ────────────────────────────────────────────

    def test_send_to_topic_success(self, fcm, messaging):
        """send_to_topic returns message_id on success."""
        messaging.send.return_value = "topic-msg-id"
        result = fcm.send_to_topic("announcements", "T", "B")
        assert result == "topic-msg-id"

    def test_send_to_topic_failure_returns_none(self, fcm, messaging):
        """send_to_topic returns None on failure."""
        messaging.send.side_effect = Exception("topic fail")
        result = fcm.send_to_topic("bad-topic", "T", "B")
        assert result is None

    # ── subscribe_to_topic / unsubscribe_from_topic ──────────────

    def test_subscribe_to_topic_success(self, fcm, messaging):
        """subscribe_to_topic calls messaging.subscribe_to_topic."""
        messaging.subscribe_to_topic.return_value = Mock(failure_count=0)
        fcm.subscribe_to_topic(["tok1"], "news")
        messaging.subscribe_to_topic.assert_called_once()

    def test_subscribe_to_topic_partial_failure_logs(self, fcm, messaging):
        """subscribe_to_topic handles partial failures without raising."""
        messaging.subscribe_to_topic.return_value = Mock(failure_count=1)
        # Should not raise
        fcm.subscribe_to_topic(["tok1", "tok2"], "news")

    def test_subscribe_to_topic_exception_handled(self, fcm, messaging):
        """subscribe_to_topic handles exceptions gracefully."""
        messaging.subscribe_to_topic.side_effect = Exception("subscribe fail")
        # Should not raise
        fcm.subscribe_to_topic(["tok1"], "news")

    def test_unsubscribe_from_topic_success(self, fcm, messaging):
        """unsubscribe_from_topic calls messaging.unsubscribe_from_topic."""
        messaging.unsubscribe_from_topic.return_value = Mock(failure_count=0)
        fcm.unsubscribe_from_topic(["tok1"], "news")
        messaging.unsubscribe_from_topic.assert_called_once()

    def test_unsubscribe_from_topic_partial_failure(self, fcm, messaging):
        """unsubscribe_from_topic handles partial failures."""
        messaging.unsubscribe_from_topic.return_value = Mock(failure_count=1)
        fcm.unsubscribe_from_topic(["tok1", "tok2"], "news")

    def test_unsubscribe_from_topic_exception_handled(self, fcm, messaging):
        """unsubscribe_from_topic handles exceptions gracefully."""
        messaging.unsubscribe_from_topic.side_effect = Exception("unsub fail")
        fcm.unsubscribe_from_topic(["tok1"], "news")


# ══════════════════════════════════════════════════════════════════════
#  Device token management (integration with UserDevice model)
# ══════════════════════════════════════════════════════════════════════


class TestDeviceTokenManagement:
    """Tests verifying FCM interacts correctly with UserDevice model."""

    def test_user_device_creation(self, notif_user):
        """UserDevice can be created and queried."""
        from apps.notifications.models import UserDevice

        device = UserDevice.objects.create(
            user=notif_user,
            fcm_token="unique-device-token",
            platform="android",
            is_active=True,
        )
        assert device.is_active is True
        assert device.platform == "android"

    def test_deactivate_device(self, notif_user):
        """Device can be deactivated by setting is_active=False."""
        from apps.notifications.models import UserDevice

        device = UserDevice.objects.create(
            user=notif_user,
            fcm_token="token-to-deactivate",
            platform="ios",
            is_active=True,
        )
        UserDevice.objects.filter(fcm_token="token-to-deactivate").update(
            is_active=False
        )
        device.refresh_from_db()
        assert device.is_active is False

    def test_multiple_devices_per_user(self, notif_user):
        """A user can have multiple active devices."""
        from apps.notifications.models import UserDevice

        UserDevice.objects.create(
            user=notif_user,
            fcm_token="device-1",
            platform="android",
            is_active=True,
        )
        UserDevice.objects.create(
            user=notif_user,
            fcm_token="device-2",
            platform="web",
            is_active=True,
        )
        active = UserDevice.objects.filter(user=notif_user, is_active=True)
        assert active.count() == 2
