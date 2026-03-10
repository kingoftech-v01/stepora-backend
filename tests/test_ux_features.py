"""
Functional tests for UX features (Steps 1-7):
  1. MessageReadStatus model
  2. Block enforcement (send-message + calls)
  3. Push notification on buddy message
  4. Unread count + mark-as-read
  5. Auto-expiration of ringing calls + missed call notifications
  6. Caller notification on call reject
  7. Call history endpoint
"""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.buddies.models import BuddyPairing
from apps.conversations.models import Call, Conversation, Message, MessageReadStatus
from apps.notifications.models import Notification
from apps.social.models import BlockedUser
from apps.users.models import User

# ── Disable Elasticsearch signals (no ES server in test env) ─────


@pytest.fixture(autouse=True)
def _disable_es_signals():
    """Disconnect django-elasticsearch-dsl auto-sync signals for tests."""
    from unittest.mock import patch as _patch

    with _patch(
        "django_elasticsearch_dsl.signals.RealTimeSignalProcessor.handle_save"
    ), _patch(
        "django_elasticsearch_dsl.signals.RealTimeSignalProcessor.handle_delete"
    ), _patch(
        "django_elasticsearch_dsl.signals.RealTimeSignalProcessor.handle_pre_delete"
    ):
        yield


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def user_a(db):
    """Premium user A (sender/caller)."""
    return User.objects.create_user(
        email="usera@example.com",
        password="testpass123",
        display_name="User A",
        timezone="Europe/Paris",
        subscription="premium",
        subscription_ends=timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def user_b(db):
    """Premium user B (recipient/callee)."""
    return User.objects.create_user(
        email="userb@example.com",
        password="testpass123",
        display_name="User B",
        timezone="Europe/Paris",
        subscription="premium",
        subscription_ends=timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def client_a(user_a):
    client = APIClient()
    client.force_authenticate(user=user_a)
    return client


@pytest.fixture
def client_b(user_b):
    client = APIClient()
    client.force_authenticate(user=user_b)
    return client


@pytest.fixture
def buddy_pairing(db, user_a, user_b):
    return BuddyPairing.objects.create(
        user1=user_a,
        user2=user_b,
        status="active",
    )


@pytest.fixture
def buddy_conversation(db, user_a, buddy_pairing):
    return Conversation.objects.create(
        user=user_a,
        conversation_type="buddy_chat",
        buddy_pairing=buddy_pairing,
    )


# ── Step 1: MessageReadStatus model ──────────────────────────────


class TestMessageReadStatus:
    def test_create_read_status(self, db, user_a, buddy_conversation):
        msg = Message.objects.create(
            conversation=buddy_conversation, role="user", content="Hello"
        )
        rs = MessageReadStatus.objects.create(
            user=user_a,
            conversation=buddy_conversation,
            last_read_message=msg,
        )
        assert rs.user == user_a
        assert rs.conversation == buddy_conversation
        assert rs.last_read_message == msg
        assert rs.last_read_at is not None

    def test_unique_per_user_conversation(self, db, user_a, buddy_conversation):
        MessageReadStatus.objects.create(user=user_a, conversation=buddy_conversation)
        with pytest.raises(Exception):  # IntegrityError
            MessageReadStatus.objects.create(
                user=user_a, conversation=buddy_conversation
            )

    def test_update_or_create(self, db, user_a, buddy_conversation):
        msg1 = Message.objects.create(
            conversation=buddy_conversation, role="user", content="First"
        )
        MessageReadStatus.objects.update_or_create(
            user=user_a,
            conversation=buddy_conversation,
            defaults={"last_read_message": msg1},
        )
        msg2 = Message.objects.create(
            conversation=buddy_conversation, role="user", content="Second"
        )
        MessageReadStatus.objects.update_or_create(
            user=user_a,
            conversation=buddy_conversation,
            defaults={"last_read_message": msg2},
        )
        rs = MessageReadStatus.objects.get(user=user_a, conversation=buddy_conversation)
        assert rs.last_read_message == msg2


# ── Step 2: Block enforcement ─────────────────────────────────────


class TestBlockEnforcement:

    def test_is_blocked_bidirectional(self, db, user_a, user_b):
        """BlockedUser.is_blocked checks both directions."""
        assert not BlockedUser.is_blocked(user_a, user_b)

        BlockedUser.objects.create(blocker=user_a, blocked=user_b)
        assert BlockedUser.is_blocked(user_a, user_b)
        assert BlockedUser.is_blocked(user_b, user_a)  # reverse also blocked

    def test_send_message_blocked_returns_403(
        self, client_a, user_a, user_b, buddy_conversation, buddy_pairing
    ):
        """Blocked user cannot send buddy message."""
        BlockedUser.objects.create(blocker=user_b, blocked=user_a)

        resp = client_a.post(
            "/api/buddies/send-message/",
            {
                "conversationId": str(buddy_conversation.id),
                "content": "Hello blocked!",
            },
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_send_message_unblocked_succeeds(
        self, client_a, user_a, user_b, buddy_conversation, buddy_pairing
    ):
        """Unblocked user can send buddy message."""
        resp = client_a.post(
            "/api/buddies/send-message/",
            {
                "conversationId": str(buddy_conversation.id),
                "content": "Hello buddy!",
            },
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_call_blocked_returns_403(self, client_a, user_a, user_b):
        """Blocked user cannot initiate a call."""
        BlockedUser.objects.create(blocker=user_b, blocked=user_a)

        with patch("apps.notifications.fcm_service.FCMService"):
            resp = client_a.post(
                "/api/conversations/calls/initiate/",
                {
                    "callee_id": str(user_b.id),
                    "call_type": "voice",
                },
            )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_call_unblocked_succeeds(self, client_a, user_a, user_b):
        """Unblocked user can initiate a call."""
        with patch("apps.notifications.fcm_service.FCMService"):
            resp = client_a.post(
                "/api/conversations/calls/initiate/",
                {
                    "callee_id": str(user_b.id),
                    "call_type": "voice",
                },
            )
        assert resp.status_code == status.HTTP_201_CREATED


# ── Step 3: Push notification on buddy message ────────────────────


class TestBuddyMessageNotification:

    def test_notification_created_on_send(
        self, client_a, user_a, user_b, buddy_conversation, buddy_pairing
    ):
        """Sending a buddy message creates a notification for recipient."""
        resp = client_a.post(
            "/api/buddies/send-message/",
            {
                "conversationId": str(buddy_conversation.id),
                "content": "Hey buddy!",
            },
        )
        assert resp.status_code == status.HTTP_200_OK

        notif = Notification.objects.filter(
            user=user_b, notification_type="buddy"
        ).first()
        assert notif is not None
        assert "User A" in notif.title
        assert notif.data["conversation_id"] == str(buddy_conversation.id)
        assert notif.data["sender_id"] == str(user_a.id)

    def test_notification_body_truncated(
        self, client_a, user_a, user_b, buddy_conversation, buddy_pairing
    ):
        """Notification body is truncated to 100 chars."""
        long_msg = "x" * 200
        client_a.post(
            "/api/buddies/send-message/",
            {
                "conversationId": str(buddy_conversation.id),
                "content": long_msg,
            },
        )

        notif = Notification.objects.filter(
            user=user_b, notification_type="buddy"
        ).first()
        assert notif is not None
        assert len(notif.body) <= 100


# ── Step 4: Unread count + mark-as-read ───────────────────────────


class TestUnreadCountAndMarkRead:

    def test_mark_read_creates_status(self, client_a, user_a, buddy_conversation):
        """POST mark-read creates MessageReadStatus."""
        msg = Message.objects.create(
            conversation=buddy_conversation, role="user", content="Test"
        )
        resp = client_a.post(f"/api/conversations/{buddy_conversation.id}/mark-read/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["last_read_message_id"] == str(msg.id)

        rs = MessageReadStatus.objects.get(user=user_a, conversation=buddy_conversation)
        assert rs.last_read_message == msg

    def test_mark_read_updates_existing(self, client_a, user_a, buddy_conversation):
        """Calling mark-read twice updates the existing status."""
        msg1 = Message.objects.create(
            conversation=buddy_conversation, role="user", content="First"
        )
        client_a.post(f"/api/conversations/{buddy_conversation.id}/mark-read/")

        msg2 = Message.objects.create(
            conversation=buddy_conversation, role="user", content="Second"
        )
        client_a.post(f"/api/conversations/{buddy_conversation.id}/mark-read/")

        assert (
            MessageReadStatus.objects.filter(
                user=user_a, conversation=buddy_conversation
            ).count()
            == 1
        )

        rs = MessageReadStatus.objects.get(user=user_a, conversation=buddy_conversation)
        assert rs.last_read_message == msg2

    def test_mark_read_empty_conversation(self, client_a, buddy_conversation):
        """Mark-read on empty conversation returns null last_read_message_id."""
        resp = client_a.post(f"/api/conversations/{buddy_conversation.id}/mark-read/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["last_read_message_id"] is None

    def test_unread_count_in_conversation_list(
        self, client_b, user_a, user_b, buddy_conversation, buddy_pairing
    ):
        """Conversation list includes unread_count field."""
        # Create messages from user A
        for i in range(3):
            Message.objects.create(
                conversation=buddy_conversation,
                role="user",
                content=f"Message {i}",
                metadata={"sender_id": str(user_a.id)},
            )

        resp = client_b.get("/api/conversations/")
        assert resp.status_code == status.HTTP_200_OK
        convs = (
            resp.data
            if isinstance(resp.data, list)
            else resp.data.get("results", resp.data)
        )
        # Find our conversation
        conv_data = None
        for c in convs:
            if str(c["id"]) == str(buddy_conversation.id):
                conv_data = c
                break
        assert conv_data is not None
        assert "unread_count" in conv_data

    def test_unread_count_decreases_after_mark_read(
        self, client_b, user_a, user_b, buddy_conversation, buddy_pairing
    ):
        """After marking read, unread count should be 0."""
        for i in range(3):
            Message.objects.create(
                conversation=buddy_conversation,
                role="user",
                content=f"Message {i}",
                metadata={"sender_id": str(user_a.id)},
            )

        # Mark as read
        client_b.post(f"/api/conversations/{buddy_conversation.id}/mark-read/")

        resp = client_b.get("/api/conversations/")
        convs = (
            resp.data
            if isinstance(resp.data, list)
            else resp.data.get("results", resp.data)
        )
        conv_data = None
        for c in convs:
            if str(c["id"]) == str(buddy_conversation.id):
                conv_data = c
                break
        assert conv_data is not None
        assert conv_data["unread_count"] == 0


# ── Step 5: Auto-expiration of ringing calls + missed call notif ──


class TestExpireRingingCalls:

    def test_expire_old_ringing_call(self, db, user_a, user_b):
        """Calls ringing > 30s are expired to 'missed'."""
        call = Call.objects.create(
            caller=user_a,
            callee=user_b,
            call_type="voice",
            status="ringing",
        )
        # Backdate created_at to 31 seconds ago
        Call.objects.filter(id=call.id).update(
            created_at=timezone.now() - timedelta(seconds=31)
        )

        from apps.notifications.tasks import expire_ringing_calls

        result = expire_ringing_calls()

        call.refresh_from_db()
        assert call.status == "missed"

    def test_do_not_expire_recent_call(self, db, user_a, user_b):
        """Calls ringing < 30s are NOT expired."""
        call = Call.objects.create(
            caller=user_a,
            callee=user_b,
            call_type="voice",
            status="ringing",
        )

        from apps.notifications.tasks import expire_ringing_calls

        expire_ringing_calls()

        call.refresh_from_db()
        assert call.status == "ringing"

    def test_expired_call_creates_callee_notification(self, db, user_a, user_b):
        """Expired call creates missed_call notification for callee."""
        call = Call.objects.create(
            caller=user_a,
            callee=user_b,
            call_type="voice",
            status="ringing",
        )
        Call.objects.filter(id=call.id).update(
            created_at=timezone.now() - timedelta(seconds=31)
        )

        from apps.notifications.tasks import expire_ringing_calls

        expire_ringing_calls()

        notif = Notification.objects.filter(
            user=user_b, notification_type="missed_call"
        ).first()
        assert notif is not None
        assert "Missed" in notif.title
        assert notif.data["caller_id"] == str(user_a.id)

    def test_expired_call_creates_caller_notification(self, db, user_a, user_b):
        """Expired call creates missed_call notification for caller."""
        call = Call.objects.create(
            caller=user_a,
            callee=user_b,
            call_type="voice",
            status="ringing",
        )
        Call.objects.filter(id=call.id).update(
            created_at=timezone.now() - timedelta(seconds=31)
        )

        from apps.notifications.tasks import expire_ringing_calls

        expire_ringing_calls()

        notif = Notification.objects.filter(
            user=user_a, notification_type="missed_call"
        ).first()
        assert notif is not None
        assert "didn't answer" in notif.title

    def test_atomic_no_double_expire(self, db, user_a, user_b):
        """If call is accepted before task runs, it is NOT expired."""
        call = Call.objects.create(
            caller=user_a,
            callee=user_b,
            call_type="voice",
            status="ringing",
        )
        Call.objects.filter(id=call.id).update(
            created_at=timezone.now() - timedelta(seconds=31)
        )
        # Simulate concurrent accept
        Call.objects.filter(id=call.id).update(status="accepted")

        from apps.notifications.tasks import expire_ringing_calls

        result = expire_ringing_calls()

        call.refresh_from_db()
        assert call.status == "accepted"
        assert result["expired"] == 0


# ── Step 6: Caller notification on call reject ────────────────────


class TestCallRejectNotification:

    def test_reject_creates_notification_for_caller(self, client_b, user_a, user_b):
        """Rejecting a call creates a notification for the caller."""
        call = Call.objects.create(
            caller=user_a,
            callee=user_b,
            call_type="voice",
            status="ringing",
        )

        with patch("channels.layers.get_channel_layer") as mock_layer:
            mock_layer.return_value = Mock()
            mock_layer.return_value.group_send = Mock()
            resp = client_b.post(f"/api/conversations/calls/{call.id}/reject/")

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["status"] == "rejected"

        notif = Notification.objects.filter(
            user=user_a, notification_type="buddy"
        ).first()
        assert notif is not None
        assert "declined" in notif.title
        assert notif.data["type"] == "call_rejected"

    def test_non_callee_cannot_reject(self, client_a, user_a, user_b):
        """Only the callee can reject the call."""
        call = Call.objects.create(
            caller=user_a,
            callee=user_b,
            call_type="voice",
            status="ringing",
        )
        resp = client_a.post(f"/api/conversations/calls/{call.id}/reject/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── Step 7: Call history ──────────────────────────────────────────


class TestCallHistory:

    def test_history_returns_user_calls(self, client_a, user_a, user_b):
        """Call history returns calls where user is caller or callee."""
        call1 = Call.objects.create(
            caller=user_a,
            callee=user_b,
            call_type="voice",
            status="completed",
        )
        call2 = Call.objects.create(
            caller=user_b,
            callee=user_a,
            call_type="video",
            status="missed",
        )

        resp = client_a.get("/api/conversations/calls/history/")
        assert resp.status_code == status.HTTP_200_OK
        ids = [c["id"] for c in resp.data]
        assert str(call1.id) in ids
        assert str(call2.id) in ids

    def test_history_excludes_other_users_calls(self, db, client_a, user_a, user_b):
        """Call history does not include calls between other users."""
        other = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            display_name="Other",
            subscription="premium",
            subscription_ends=timezone.now() + timedelta(days=30),
        )
        Call.objects.create(
            caller=user_b,
            callee=other,
            call_type="voice",
            status="completed",
        )

        resp = client_a.get("/api/conversations/calls/history/")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) == 0

    def test_history_ordered_by_most_recent(self, client_a, user_a, user_b):
        """Calls are ordered by created_at descending."""
        old = Call.objects.create(
            caller=user_a,
            callee=user_b,
            call_type="voice",
            status="completed",
        )
        Call.objects.filter(id=old.id).update(
            created_at=timezone.now() - timedelta(hours=1)
        )
        new = Call.objects.create(
            caller=user_a,
            callee=user_b,
            call_type="voice",
            status="completed",
        )

        resp = client_a.get("/api/conversations/calls/history/")
        assert resp.data[0]["id"] == str(new.id)
        assert resp.data[1]["id"] == str(old.id)

    def test_history_serializer_fields(self, client_a, user_a, user_b):
        """Call history includes expected fields."""
        Call.objects.create(
            caller=user_a,
            callee=user_b,
            call_type="voice",
            status="completed",
            duration_seconds=120,
        )

        resp = client_a.get("/api/conversations/calls/history/")
        entry = resp.data[0]
        assert "caller_name" in entry
        assert "callee_name" in entry
        assert "call_type" in entry
        assert "status" in entry
        assert "duration_seconds" in entry
        assert "created_at" in entry

    def test_history_max_100(self, client_a, user_a, user_b):
        """Call history is capped at 100 entries."""
        calls = [
            Call(caller=user_a, callee=user_b, call_type="voice", status="completed")
            for _ in range(105)
        ]
        Call.objects.bulk_create(calls)

        resp = client_a.get("/api/conversations/calls/history/")
        assert len(resp.data) <= 100


# ── Cross-feature integration tests ──────────────────────────────


class TestIntegration:

    def test_block_then_unblock_allows_message(
        self, client_a, user_a, user_b, buddy_conversation, buddy_pairing
    ):
        """Blocking and then unblocking allows messages again."""
        block = BlockedUser.objects.create(blocker=user_b, blocked=user_a)

        resp = client_a.post(
            "/api/buddies/send-message/",
            {
                "conversationId": str(buddy_conversation.id),
                "content": "Should fail",
            },
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        block.delete()

        resp = client_a.post(
            "/api/buddies/send-message/",
            {
                "conversationId": str(buddy_conversation.id),
                "content": "Should succeed",
            },
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_call_lifecycle_full(self, client_a, client_b, user_a, user_b):
        """Full call lifecycle: initiate -> accept -> end."""
        with patch("apps.notifications.fcm_service.FCMService"):
            resp = client_a.post(
                "/api/conversations/calls/initiate/",
                {
                    "callee_id": str(user_b.id),
                    "call_type": "voice",
                },
            )
        assert resp.status_code == status.HTTP_201_CREATED
        call_id = resp.data["callId"]

        resp = client_b.post(f"/api/conversations/calls/{call_id}/accept/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["status"] == "accepted"

        resp = client_a.post(f"/api/conversations/calls/{call_id}/end/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["status"] == "completed"
        assert resp.data["durationSeconds"] >= 0

    def test_missed_call_appears_in_history(self, client_a, user_a, user_b):
        """Expired ringing call appears in history as 'missed'."""
        call = Call.objects.create(
            caller=user_a,
            callee=user_b,
            call_type="voice",
            status="ringing",
        )
        Call.objects.filter(id=call.id).update(
            created_at=timezone.now() - timedelta(seconds=31)
        )

        from apps.notifications.tasks import expire_ringing_calls

        expire_ringing_calls()

        resp = client_a.get("/api/conversations/calls/history/")
        assert any(c["status"] == "missed" for c in resp.data)
