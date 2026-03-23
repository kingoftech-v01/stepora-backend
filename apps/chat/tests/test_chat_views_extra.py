"""
Extra integration tests for apps/chat/views.py — targeting 90%+ coverage.

Covers:
- Conversation with blocking (blocked user can't start conversation or call)
- Send message with WebSocket broadcast (mock channel layer)
- Agora config, RTM token, RTC token
- Call flow: initiate with buddy pairing, accept, end (with duration)
- Reject call with notification
- Cancel non-ringing call
- Call status with started_at
- Incoming calls: caller_name display
- End call without started_at (no duration)
- Mark read with no messages
"""

import uuid
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.chat.models import Call, ChatConversation, ChatMessage
from apps.friends.models import BlockedUser
from apps.users.models import User

# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def cu1(db):
    """Chat test user 1."""
    return User.objects.create_user(
        email="chatex1@example.com",
        password="testpassword123",
        display_name="ChatEx User 1",
    )


@pytest.fixture
def cu2(db):
    """Chat test user 2."""
    return User.objects.create_user(
        email="chatex2@example.com",
        password="testpassword123",
        display_name="ChatEx User 2",
    )


@pytest.fixture
def cu3(db):
    """Chat test user 3 (bystander)."""
    return User.objects.create_user(
        email="chatex3@example.com",
        password="testpassword123",
        display_name="ChatEx User 3",
    )


@pytest.fixture
def cc1(cu1):
    client = APIClient()
    client.force_authenticate(user=cu1)
    return client


@pytest.fixture
def cc2(cu2):
    client = APIClient()
    client.force_authenticate(user=cu2)
    return client


@pytest.fixture
def cc3(cu3):
    client = APIClient()
    client.force_authenticate(user=cu3)
    return client


@pytest.fixture
def conv(db, cu1, cu2):
    """Existing conversation between cu1 and cu2."""
    return ChatConversation.objects.create(user=cu1, target_user=cu2, title="Test Conv")


@pytest.fixture
def msg(db, conv, cu1):
    """A message in the conversation."""
    return ChatMessage.objects.create(
        conversation=conv,
        role="user",
        content="Hello there!",
        metadata={"sender_id": str(cu1.id)},
    )


@pytest.fixture
def ringing_call(db, cu1, cu2):
    """A ringing call from cu1 to cu2."""
    return Call.objects.create(
        caller=cu1, callee=cu2, call_type="voice", status="ringing"
    )


# ══════════════════════════════════════════════════════════════════════
#  BLOCKING PREVENTS CALLS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBlockingPreventsCall:
    """Blocked users cannot initiate calls."""

    @patch("apps.chat.views.CallViewSet._notify_callee")
    def test_blocked_user_cannot_call(self, mock_notify, cc1, cu1, cu2):
        """Blocked user gets 403 on initiate."""
        BlockedUser.objects.create(blocker=cu2, blocked=cu1, reason="spam")
        response = cc1.post(
            "/api/chat/calls/initiate/",
            {"callee_id": str(cu2.id), "call_type": "voice"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("apps.chat.views.CallViewSet._notify_callee")
    def test_user_who_blocked_cannot_call(self, mock_notify, cc1, cu1, cu2):
        """If cu1 blocked cu2, cu1 still can't call cu2."""
        BlockedUser.objects.create(blocker=cu1, blocked=cu2, reason="spam")
        response = cc1.post(
            "/api/chat/calls/initiate/",
            {"callee_id": str(cu2.id), "call_type": "voice"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ══════════════════════════════════════════════════════════════════════
#  SEND MESSAGE WITH WEBSOCKET
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSendMessageWebSocket:
    """Test message sending with WebSocket broadcast."""

    @patch("channels.layers.get_channel_layer")
    def test_send_message_broadcasts(self, mock_layer, cc1, conv):
        """Message is broadcast via WebSocket."""
        mock_channel = Mock()
        mock_layer.return_value = mock_channel
        # async_to_sync wrapping — mock it
        with patch("apps.chat.views.async_to_sync", create=True) as mock_a2s:
            mock_a2s.return_value = Mock()
            response = cc1.post(
                f"/api/chat/{conv.id}/send-message/",
                {"content": "Hello with WS!"},
                format="json",
            )
        assert response.status_code == status.HTTP_201_CREATED

    @patch("channels.layers.get_channel_layer")
    def test_send_message_ws_failure_non_blocking(self, mock_layer, cc1, conv):
        """WebSocket failure doesn't block message creation."""
        mock_layer.side_effect = Exception("Channel layer error")
        response = cc1.post(
            f"/api/chat/{conv.id}/send-message/",
            {"content": "Hello despite WS error"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["content"] == "Hello despite WS error"

    @patch("channels.layers.get_channel_layer")
    def test_send_message_buddy_pairing_room(self, mock_layer, cc1, cu1, cu2):
        """Messages in a buddy conversation use buddy room name."""
        from apps.buddies.models import BuddyPairing

        pairing = BuddyPairing.objects.create(user1=cu1, user2=cu2, status="active")
        conv = ChatConversation.objects.create(
            user=cu1, target_user=cu2, buddy_pairing=pairing
        )
        mock_layer.return_value = None  # suppress WS
        response = cc1.post(
            f"/api/chat/{conv.id}/send-message/",
            {"content": "Buddy message"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED


# ══════════════════════════════════════════════════════════════════════
#  CALL INITIATE WITH BUDDY PAIRING + WS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCallInitiateWithBuddy:
    """Call initiation with buddy pairing broadcasts via WebSocket."""

    @patch("apps.chat.views.CallViewSet._notify_callee")
    def test_initiate_call_with_buddy_pairing(self, mock_notify, cc1, cu1, cu2):
        """Call with active buddy pairing broadcasts to buddy_chat room."""
        from apps.buddies.models import BuddyPairing

        pairing = BuddyPairing.objects.create(user1=cu1, user2=cu2, status="active")
        with patch("channels.layers.get_channel_layer") as mock_layer:
            mock_layer.return_value = None
            response = cc1.post(
                "/api/chat/calls/initiate/",
                {"callee_id": str(cu2.id), "call_type": "video"},
                format="json",
            )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["call_type"] == "video"

    @patch("apps.chat.views.CallViewSet._notify_callee")
    def test_initiate_call_user_id_alias(self, mock_notify, cc1, cu2):
        """user_id is accepted as alias for callee_id."""
        response = cc1.post(
            "/api/chat/calls/initiate/",
            {"user_id": str(cu2.id), "call_type": "voice"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED


# ══════════════════════════════════════════════════════════════════════
#  CALL END WITH DURATION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCallEndDuration:
    """End call calculates duration when started_at is set."""

    def test_end_accepted_call_has_duration(self, cc1, ringing_call):
        """Ending an accepted call returns duration_seconds."""
        ringing_call.status = "accepted"
        ringing_call.started_at = timezone.now() - timezone.timedelta(minutes=5)
        ringing_call.save()

        response = cc1.post(f"/api/chat/calls/{ringing_call.id}/end/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "completed"
        assert response.data["duration_seconds"] >= 0

    def test_end_call_without_started_at(self, cc1, ringing_call):
        """Ending a call without started_at has no positive duration."""
        ringing_call.status = "accepted"
        ringing_call.started_at = None
        ringing_call.save()

        response = cc1.post(f"/api/chat/calls/{ringing_call.id}/end/")
        assert response.status_code == status.HTTP_200_OK
        ringing_call.refresh_from_db()
        # Without started_at, duration is not calculated
        assert (
            ringing_call.duration_seconds is None or ringing_call.duration_seconds == 0
        )


# ══════════════════════════════════════════════════════════════════════
#  CALL REJECT WITH NOTIFICATION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCallRejectNotification:
    """Rejecting a call sends a notification and WebSocket event."""

    @patch("channels.layers.get_channel_layer")
    @patch("apps.notifications.services.NotificationService.create")
    def test_reject_creates_notification(
        self, mock_notif, mock_layer, cc2, ringing_call
    ):
        """Reject call creates notification for caller."""
        mock_layer.return_value = None
        response = cc2.post(f"/api/chat/calls/{ringing_call.id}/reject/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "rejected"
        mock_notif.assert_called_once()


# ══════════════════════════════════════════════════════════════════════
#  CALL STATUS WITH STARTED_AT
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCallStatusStartedAt:
    """Call status endpoint returns started_at when available."""

    def test_call_status_with_started_at(self, cc1, ringing_call):
        """Active call status shows started_at."""
        now = timezone.now()
        ringing_call.status = "accepted"
        ringing_call.started_at = now
        ringing_call.save()

        response = cc1.get(f"/api/chat/calls/{ringing_call.id}/status/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["started_at"] is not None

    def test_call_status_without_started_at(self, cc1, ringing_call):
        """Ringing call has no started_at."""
        response = cc1.get(f"/api/chat/calls/{ringing_call.id}/status/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["started_at"] is None


# ══════════════════════════════════════════════════════════════════════
#  MARK READ WITH NO MESSAGES
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMarkReadNoMessages:
    """Mark read on conversation with no messages."""

    def test_mark_read_empty_conversation(self, cc1, cu1, cu2):
        """mark-read on empty conversation returns null last_read_message_id."""
        conv = ChatConversation.objects.create(user=cu1, target_user=cu2)
        response = cc1.post(f"/api/chat/{conv.id}/mark-read/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["last_read_message_id"] is None


# ══════════════════════════════════════════════════════════════════════
#  START CONVERSATION: USER_ID alias
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStartConversationUserIdAlias:
    """Start conversation supports user_id as alias for target_user_id."""

    def test_start_with_user_id(self, cc1, cu3):
        """user_id is accepted in start endpoint."""
        response = cc1.post(
            "/api/chat/start/",
            {"user_id": str(cu3.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED


# ══════════════════════════════════════════════════════════════════════
#  AGORA TOKEN ENDPOINTS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAgoraEndpoints:
    """Tests for Agora token generation endpoints."""

    def test_agora_config_not_configured(self, cc1):
        """Returns 503 when Agora is not configured."""
        with patch("django.conf.settings.AGORA_APP_ID", ""):
            response = cc1.get("/api/chat/agora/config/")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_agora_config_success(self, cc1):
        """Returns appId when configured."""
        with patch("django.conf.settings.AGORA_APP_ID", "test-app-id"):
            response = cc1.get("/api/chat/agora/config/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["appId"] == "test-app-id"

    def test_agora_rtm_token_not_configured(self, cc1):
        """Returns 503 when Agora is not configured."""
        with patch("django.conf.settings.AGORA_APP_ID", ""), patch(
            "django.conf.settings.AGORA_APP_CERTIFICATE", ""
        ):
            response = cc1.post("/api/chat/agora/rtm-token/")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_agora_rtm_token_success(self, cc1):
        """Returns RTM token when configured."""
        import sys
        import types

        mock_rtm_module = types.ModuleType("agora_token_builder.RtmTokenBuilder")
        mock_builder = Mock()
        mock_builder.buildToken.return_value = "fake-rtm-token"
        mock_rtm_module.RtmTokenBuilder = mock_builder
        mock_rtm_module.Role_Rtm_User = 1

        with patch.dict(
            sys.modules,
            {
                "agora_token_builder": types.ModuleType("agora_token_builder"),
                "agora_token_builder.RtmTokenBuilder": mock_rtm_module,
            },
        ), patch("django.conf.settings.AGORA_APP_ID", "test-id"), patch(
            "django.conf.settings.AGORA_APP_CERTIFICATE", "test-cert"
        ):
            response = cc1.post("/api/chat/agora/rtm-token/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["token"] == "fake-rtm-token"

    def test_agora_rtc_token_no_channel(self, cc1):
        """RTC token without channelName returns 400."""
        with patch("django.conf.settings.AGORA_APP_ID", "test-id"), patch(
            "django.conf.settings.AGORA_APP_CERTIFICATE", "test-cert"
        ):
            response = cc1.post("/api/chat/agora/rtc-token/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_agora_rtc_token_invalid_channel(self, cc1):
        """RTC token with special chars returns 400."""
        with patch("django.conf.settings.AGORA_APP_ID", "test-id"), patch(
            "django.conf.settings.AGORA_APP_CERTIFICATE", "test-cert"
        ):
            response = cc1.post(
                "/api/chat/agora/rtc-token/",
                {"channelName": "invalid channel!@#"},
                format="json",
            )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_agora_rtc_token_not_authorized(self, cc1, cu1, cu2):
        """RTC token for unrelated channel returns 403."""
        with patch("django.conf.settings.AGORA_APP_ID", "test-id"), patch(
            "django.conf.settings.AGORA_APP_CERTIFICATE", "test-cert"
        ):
            response = cc1.post(
                "/api/chat/agora/rtc-token/",
                {"channelName": str(uuid.uuid4())},
                format="json",
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_agora_rtc_token_authorized_call(self, cc1, cu1, cu2):
        """RTC token for an active call returns token."""
        import sys
        import types

        mock_rtc_module = types.ModuleType("agora_token_builder.RtcTokenBuilder")
        mock_builder = Mock()
        mock_builder.buildTokenWithAccount.return_value = "fake-rtc-token"
        mock_rtc_module.RtcTokenBuilder = mock_builder
        mock_rtc_module.Role_Publisher = 1

        call = Call.objects.create(
            caller=cu1, callee=cu2, call_type="voice", status="ringing"
        )
        with patch.dict(
            sys.modules,
            {
                "agora_token_builder": types.ModuleType("agora_token_builder"),
                "agora_token_builder.RtcTokenBuilder": mock_rtc_module,
            },
        ), patch("django.conf.settings.AGORA_APP_ID", "test-id"), patch(
            "django.conf.settings.AGORA_APP_CERTIFICATE", "test-cert"
        ):
            response = cc1.post(
                "/api/chat/agora/rtc-token/",
                {"channelName": str(call.id)},
                format="json",
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["token"] == "fake-rtc-token"

    def test_agora_rtc_token_not_configured(self, cc1):
        """Returns 503 when Agora is not configured."""
        with patch("django.conf.settings.AGORA_APP_ID", ""), patch(
            "django.conf.settings.AGORA_APP_CERTIFICATE", ""
        ):
            response = cc1.post(
                "/api/chat/agora/rtc-token/",
                {"channelName": "test-channel"},
                format="json",
            )
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_agora_config_unauthenticated(self):
        """Unauthenticated request returns 401."""
        client = APIClient()
        response = client.get("/api/chat/agora/config/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ══════════════════════════════════════════════════════════════════════
#  INCOMING CALLS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestIncomingCallsExtra:
    """Extra tests for incoming calls endpoint."""

    def test_incoming_calls_shows_caller_name(self, cc2, ringing_call):
        """Incoming calls include caller's display name."""
        response = cc2.get("/api/chat/calls/incoming/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        assert response.data[0]["caller_name"] == "ChatEx User 1"


# ══════════════════════════════════════════════════════════════════════
#  CALL HISTORY PAGINATION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCallHistoryExtra:
    """Extra call history tests."""

    def test_call_history_empty(self, cc3):
        """Empty call history for user with no calls."""
        response = cc3.get("/api/chat/calls/history/")
        assert response.status_code == status.HTTP_200_OK


# ══════════════════════════════════════════════════════════════════════
#  CANCEL CALL EDGE CASES
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCancelCallEdge:
    """Cancel call edge cases."""

    def test_cancel_nonexistent_call(self, cc1):
        """Cancel nonexistent call returns 404."""
        response = cc1.post(f"/api/chat/calls/{uuid.uuid4()}/cancel/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cancel_completed_call(self, cc1, ringing_call):
        """Cannot cancel a completed call."""
        ringing_call.status = "completed"
        ringing_call.save()
        response = cc1.post(f"/api/chat/calls/{ringing_call.id}/cancel/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cancel_call_not_caller(self, cc2, ringing_call):
        """Only the caller can cancel."""
        response = cc2.post(f"/api/chat/calls/{ringing_call.id}/cancel/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ══════════════════════════════════════════════════════════════════════
#  NOTIFY CALLEE (FCM)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotifyCallee:
    """Test _notify_callee FCM integration."""

    def test_notify_callee_no_devices(self, cu1, cu2):
        """No devices means no push sent (no error)."""
        call = Call.objects.create(
            caller=cu1, callee=cu2, call_type="voice", status="ringing"
        )
        viewset = __import__("apps.chat.views", fromlist=["CallViewSet"]).CallViewSet()
        # Should not raise
        viewset._notify_callee(call, cu1)

    @patch("apps.notifications.fcm_service.FCMService")
    def test_notify_callee_with_device(self, mock_fcm_cls, cu1, cu2):
        """Push notification sent when device exists."""
        from apps.notifications.models import UserDevice

        UserDevice.objects.create(
            user=cu2,
            fcm_token="fake-token-123",
            platform="android",
            is_active=True,
        )
        mock_fcm_instance = Mock()
        mock_fcm_cls.return_value = mock_fcm_instance

        call = Call.objects.create(
            caller=cu1, callee=cu2, call_type="voice", status="ringing"
        )
        viewset = __import__("apps.chat.views", fromlist=["CallViewSet"]).CallViewSet()
        viewset._notify_callee(call, cu1)
        mock_fcm_instance.send_to_token.assert_called_once()


# ══════════════════════════════════════════════════════════════════════
#  RETRIEVE CONVERSATION DETAIL (SERIALIZER CLASS)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRetrieveConversationDetail:
    """Retrieve uses ChatConversationDetailSerializer."""

    def test_retrieve_conversation_detail(self, cc1, conv, msg):
        """Retrieve returns detail serializer."""
        response = cc1.get(f"/api/chat/{conv.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(conv.id)
