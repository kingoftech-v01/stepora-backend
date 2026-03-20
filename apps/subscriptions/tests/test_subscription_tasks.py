"""
Tests for apps/subscriptions/tasks.py — Celery tasks.

Covers:
- send_payment_receipt_email
- send_subscription_upgraded_email
- send_subscription_downgrade_scheduled_email
- send_subscription_cancel_scheduled_email
- send_subscription_cancelled_email
- send_subscription_reactivated_email
- send_free_user_upgrade_reminders
- _send_upgrade_push
- _get_user helper
"""

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.users.models import User


# ──────────────────────────────────────────────────────────────────────
#  _get_user helper
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGetUserHelper:
    """Tests for the _get_user helper."""

    def test_returns_user_for_valid_id(self, sub_user):
        from apps.subscriptions.tasks import _get_user

        user = _get_user(str(sub_user.id))
        assert user is not None
        assert user.id == sub_user.id

    def test_returns_none_for_invalid_id(self, db):
        from apps.subscriptions.tasks import _get_user

        user = _get_user(str(uuid.uuid4()))
        assert user is None


# ──────────────────────────────────────────────────────────────────────
#  send_payment_receipt_email
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendPaymentReceiptEmail:
    """Tests for send_payment_receipt_email task."""

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_sends_receipt(self, mock_send_email, sub_user):
        from apps.subscriptions.tasks import send_payment_receipt_email

        send_payment_receipt_email(
            str(sub_user.id), "Premium", "$19.99", "https://invoice.example.com"
        )

        mock_send_email.assert_called_once()
        call_kwargs = mock_send_email.call_args
        assert sub_user.email in (
            call_kwargs.kwargs.get("to", call_kwargs[1].get("to", []))
        )

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_skips_nonexistent_user(self, mock_send_email, db):
        from apps.subscriptions.tasks import send_payment_receipt_email

        send_payment_receipt_email(str(uuid.uuid4()), "Premium", "$19.99")
        mock_send_email.assert_not_called()

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_handles_email_exception(self, mock_send_email, sub_user):
        """Does not crash if email sending fails."""
        mock_send_email.side_effect = Exception("SMTP error")

        from apps.subscriptions.tasks import send_payment_receipt_email

        # Should not raise
        send_payment_receipt_email(str(sub_user.id), "Pro", "$29.99")


# ──────────────────────────────────────────────────────────────────────
#  send_subscription_upgraded_email
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendSubscriptionUpgradedEmail:
    """Tests for send_subscription_upgraded_email task."""

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_sends_upgrade_email(self, mock_send_email, sub_user):
        from apps.subscriptions.tasks import send_subscription_upgraded_email

        send_subscription_upgraded_email(str(sub_user.id), "Premium")

        mock_send_email.assert_called_once()
        call_kwargs = mock_send_email.call_args
        assert "Premium" in call_kwargs.kwargs.get("subject", call_kwargs[1].get("subject", ""))

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_skips_nonexistent_user(self, mock_send_email, db):
        from apps.subscriptions.tasks import send_subscription_upgraded_email

        send_subscription_upgraded_email(str(uuid.uuid4()), "Premium")
        mock_send_email.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
#  send_subscription_downgrade_scheduled_email
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendSubscriptionDowngradeScheduledEmail:
    """Tests for send_subscription_downgrade_scheduled_email task."""

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_sends_with_date(self, mock_send_email, sub_user):
        from apps.subscriptions.tasks import send_subscription_downgrade_scheduled_email

        send_subscription_downgrade_scheduled_email(
            str(sub_user.id), "Free", "2026-04-15T00:00:00"
        )

        mock_send_email.assert_called_once()
        call_kwargs = mock_send_email.call_args
        context = call_kwargs.kwargs.get("context", call_kwargs[1].get("context", {}))
        assert "April" in context.get("effective_date", "")

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_sends_without_date(self, mock_send_email, sub_user):
        from apps.subscriptions.tasks import send_subscription_downgrade_scheduled_email

        send_subscription_downgrade_scheduled_email(
            str(sub_user.id), "Free"
        )
        mock_send_email.assert_called_once()

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_handles_invalid_date_format(self, mock_send_email, sub_user):
        """Falls back to raw string for unparseable dates."""
        from apps.subscriptions.tasks import send_subscription_downgrade_scheduled_email

        send_subscription_downgrade_scheduled_email(
            str(sub_user.id), "Free", "not-a-date"
        )

        call_kwargs = mock_send_email.call_args
        context = call_kwargs.kwargs.get("context", call_kwargs[1].get("context", {}))
        assert context.get("effective_date") == "not-a-date"

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_skips_nonexistent_user(self, mock_send_email, db):
        from apps.subscriptions.tasks import send_subscription_downgrade_scheduled_email

        send_subscription_downgrade_scheduled_email(str(uuid.uuid4()), "Free")
        mock_send_email.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
#  send_subscription_cancel_scheduled_email
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendSubscriptionCancelScheduledEmail:
    """Tests for send_subscription_cancel_scheduled_email task."""

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_sends_cancel_scheduled(self, mock_send_email, sub_user):
        from apps.subscriptions.tasks import send_subscription_cancel_scheduled_email

        send_subscription_cancel_scheduled_email(
            str(sub_user.id), "Premium", "2026-04-30T00:00:00"
        )

        mock_send_email.assert_called_once()

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_skips_nonexistent_user(self, mock_send_email, db):
        from apps.subscriptions.tasks import send_subscription_cancel_scheduled_email

        send_subscription_cancel_scheduled_email(str(uuid.uuid4()), "Premium")
        mock_send_email.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
#  send_subscription_cancelled_email
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendSubscriptionCancelledEmail:
    """Tests for send_subscription_cancelled_email task."""

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_sends_cancelled_email(self, mock_send_email, sub_user):
        from apps.subscriptions.tasks import send_subscription_cancelled_email

        send_subscription_cancelled_email(str(sub_user.id), "Premium")

        mock_send_email.assert_called_once()
        call_kwargs = mock_send_email.call_args
        assert "ended" in call_kwargs.kwargs.get("subject", call_kwargs[1].get("subject", "")).lower()

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_skips_nonexistent_user(self, mock_send_email, db):
        from apps.subscriptions.tasks import send_subscription_cancelled_email

        send_subscription_cancelled_email(str(uuid.uuid4()), "Premium")
        mock_send_email.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
#  send_subscription_reactivated_email
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendSubscriptionReactivatedEmail:
    """Tests for send_subscription_reactivated_email task."""

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_sends_reactivation_email(self, mock_send_email, sub_user):
        from apps.subscriptions.tasks import send_subscription_reactivated_email

        send_subscription_reactivated_email(str(sub_user.id), "Premium")

        mock_send_email.assert_called_once()
        call_kwargs = mock_send_email.call_args
        assert "reactivated" in call_kwargs.kwargs.get("subject", call_kwargs[1].get("subject", "")).lower()

    @patch("apps.subscriptions.tasks.send_templated_email")
    def test_skips_nonexistent_user(self, mock_send_email, db):
        from apps.subscriptions.tasks import send_subscription_reactivated_email

        send_subscription_reactivated_email(str(uuid.uuid4()), "Premium")
        mock_send_email.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
#  send_free_user_upgrade_reminders
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendFreeUserUpgradeReminders:
    """Tests for send_free_user_upgrade_reminders task."""

    @patch("apps.subscriptions.tasks._send_upgrade_push")
    def test_queues_upgrade_pushes_for_free_users(self, mock_push, db):
        """Dispatches push tasks for eligible free users."""
        user = User.objects.create_user(
            email="free_upgrade_stask@example.com",
            password="testpass123",
            subscription="free",
        )
        # Set date_joined to 5 days ago and last_login to 1 day ago
        User.objects.filter(id=user.id).update(
            date_joined=timezone.now() - timedelta(days=5),
            last_login=timezone.now() - timedelta(days=1),
        )

        from apps.subscriptions.tasks import send_free_user_upgrade_reminders

        send_free_user_upgrade_reminders()
        mock_push.delay.assert_called()

    @patch("apps.subscriptions.tasks._send_upgrade_push")
    def test_skips_new_users(self, mock_push, db):
        """Does not send to users registered less than 3 days ago."""
        User.objects.create_user(
            email="new_upgrade_stask@example.com",
            password="testpass123",
            subscription="free",
        )
        # date_joined is now (< 3 days ago), so should be skipped

        from apps.subscriptions.tasks import send_free_user_upgrade_reminders

        send_free_user_upgrade_reminders()
        mock_push.delay.assert_not_called()

    @patch("apps.subscriptions.tasks._send_upgrade_push")
    def test_skips_premium_users(self, mock_push, db):
        """Does not send to premium/pro users."""
        user = User.objects.create_user(
            email="prem_upgrade_stask@example.com",
            password="testpass123",
            subscription="premium",
        )
        User.objects.filter(id=user.id).update(
            date_joined=timezone.now() - timedelta(days=10),
            last_login=timezone.now() - timedelta(days=1),
        )

        from apps.subscriptions.tasks import send_free_user_upgrade_reminders

        send_free_user_upgrade_reminders()
        mock_push.delay.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
#  _send_upgrade_push
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendUpgradePush:
    """Tests for _send_upgrade_push task."""

    @patch("apps.notifications.services.NotificationService.send_push")
    @patch("apps.subscriptions.services.PromotionService.get_active_promotions")
    def test_sends_push_with_promo(self, mock_promos, mock_send_push, sub_user):
        """Uses promotion name/description when promotions are active."""
        mock_promo = Mock(name="50% Off!", description="Upgrade and save!")
        mock_promos.return_value = [mock_promo]

        from apps.subscriptions.tasks import _send_upgrade_push

        _send_upgrade_push(str(sub_user.id))
        mock_send_push.assert_called_once()

    @patch("apps.notifications.services.NotificationService.send_push")
    @patch("apps.subscriptions.services.PromotionService.get_active_promotions")
    def test_sends_push_without_promo(self, mock_promos, mock_send_push, sub_user):
        """Uses default message when no promotions are active."""
        mock_promos.return_value = []

        from apps.subscriptions.tasks import _send_upgrade_push

        _send_upgrade_push(str(sub_user.id))
        mock_send_push.assert_called_once()

        call_kwargs = mock_send_push.call_args
        assert "level up" in call_kwargs.kwargs.get("title", call_kwargs[1].get("title", "")).lower()

    @patch("apps.notifications.services.NotificationService.send_push")
    @patch("apps.subscriptions.services.PromotionService.get_active_promotions")
    def test_skips_nonexistent_user(self, mock_promos, mock_send_push, db):
        from apps.subscriptions.tasks import _send_upgrade_push

        _send_upgrade_push(str(uuid.uuid4()))
        mock_send_push.assert_not_called()

    @patch("apps.notifications.services.NotificationService.send_push")
    @patch("apps.subscriptions.services.PromotionService.get_active_promotions")
    def test_handles_push_exception(self, mock_promos, mock_send_push, sub_user):
        """Does not crash if push fails."""
        mock_promos.return_value = []
        mock_send_push.side_effect = Exception("FCM error")

        from apps.subscriptions.tasks import _send_upgrade_push

        # Should not raise
        _send_upgrade_push(str(sub_user.id))
