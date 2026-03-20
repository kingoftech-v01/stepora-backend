"""
Tests for apps/users/tasks.py — Celery tasks.

Covers:
- send_email_change_verification
- export_user_data
- hard_delete_expired_accounts
- generate_weekly_reports
- send_accountability_checkins
"""

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.dreams.models import Dream, Goal, Task
from apps.notifications.models import Notification
from apps.users.models import User


# ──────────────────────────────────────────────────────────────────────
#  send_email_change_verification
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendEmailChangeVerification:
    """Tests for send_email_change_verification task."""

    @patch("apps.users.tasks.send_templated_email")
    def test_sends_verification_email(self, mock_send_email, users_user):
        """Sends verification email to the new email address."""
        from apps.users.tasks import send_email_change_verification

        send_email_change_verification(
            users_user.pk, "new@example.com", "token123"
        )

        mock_send_email.assert_called_once()
        call_kwargs = mock_send_email.call_args
        assert "new@example.com" in call_kwargs.kwargs.get("to", call_kwargs[1].get("to", []))

    @patch("apps.users.tasks.send_templated_email")
    def test_skips_nonexistent_user(self, mock_send_email, db):
        """Does not send email for nonexistent user."""
        from apps.users.tasks import send_email_change_verification

        send_email_change_verification(99999999, "new@example.com", "token")
        mock_send_email.assert_not_called()

    @patch("apps.users.tasks.send_templated_email")
    def test_includes_verification_url(self, mock_send_email, users_user):
        """Context includes the correct verification URL."""
        from apps.users.tasks import send_email_change_verification

        send_email_change_verification(
            users_user.pk, "new@example.com", "abc123"
        )

        call_args = mock_send_email.call_args
        context = call_args.kwargs.get("context", call_args[1].get("context", {}))
        assert "abc123" in context.get("verification_url", "")


# ──────────────────────────────────────────────────────────────────────
#  export_user_data
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestExportUserData:
    """Tests for export_user_data task."""

    @patch("apps.users.tasks.send_templated_email")
    @patch("apps.users.tasks.default_storage")
    def test_exports_and_emails(self, mock_storage, mock_send_email, users_user):
        """Exports user data to storage and sends download link."""
        mock_storage.save.return_value = "exports/test.json"

        from apps.users.tasks import export_user_data

        export_user_data(users_user.pk)

        mock_storage.save.assert_called_once()
        mock_send_email.assert_called_once()

    @patch("apps.users.tasks.send_templated_email")
    @patch("apps.users.tasks.default_storage")
    def test_skips_nonexistent_user(self, mock_storage, mock_send_email, db):
        """Does not export for nonexistent user."""
        from apps.users.tasks import export_user_data

        export_user_data(99999999)
        mock_storage.save.assert_not_called()
        mock_send_email.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
#  hard_delete_expired_accounts
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestHardDeleteExpiredAccounts:
    """Tests for hard_delete_expired_accounts task."""

    def test_deletes_old_deactivated_accounts(self, db):
        """Hard-deletes accounts deactivated more than 30 days ago."""
        user = User.objects.create_user(
            email="expired_utask@example.com",
            password="testpass123",
            is_active=False,
        )
        # Set updated_at to 40 days ago
        User.objects.filter(id=user.id).update(
            updated_at=timezone.now() - timedelta(days=40)
        )

        from apps.users.tasks import hard_delete_expired_accounts

        result = hard_delete_expired_accounts()
        assert result["deleted"] >= 1
        assert not User.objects.filter(id=user.id).exists()

    def test_keeps_recently_deactivated(self, db):
        """Keeps accounts deactivated less than 30 days ago."""
        user = User.objects.create_user(
            email="recent_deact_utask@example.com",
            password="testpass123",
            is_active=False,
        )

        from apps.users.tasks import hard_delete_expired_accounts

        result = hard_delete_expired_accounts()
        assert User.objects.filter(id=user.id).exists()

    def test_keeps_active_accounts(self, db):
        """Does not delete active accounts even if old."""
        user = User.objects.create_user(
            email="active_old_utask@example.com",
            password="testpass123",
            is_active=True,
        )
        User.objects.filter(id=user.id).update(
            updated_at=timezone.now() - timedelta(days=100)
        )

        from apps.users.tasks import hard_delete_expired_accounts

        result = hard_delete_expired_accounts()
        assert User.objects.filter(id=user.id).exists()

    def test_reports_failed_deletions(self, db):
        """Reports failed IDs without crashing."""
        from apps.users.tasks import hard_delete_expired_accounts

        result = hard_delete_expired_accounts()
        assert "deleted" in result
        assert "failed" in result


# ──────────────────────────────────────────────────────────────────────
#  generate_weekly_reports
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateWeeklyReports:
    """Tests for generate_weekly_reports task."""

    @patch("apps.users.tasks.AIUsageTracker")
    @patch("apps.users.tasks.OpenAIService")
    def test_generates_report_for_premium_user(
        self, mock_ai_cls, mock_tracker_cls, db
    ):
        """Generates weekly report for an active premium user."""
        user = User.objects.create_user(
            email="premium_wr_utask@example.com",
            password="testpass123",
            subscription="premium",
            last_activity=timezone.now() - timedelta(days=1),
        )

        mock_ai = Mock()
        mock_ai.generate_weekly_report.return_value = {
            "score": 75,
            "summary": "Great progress this week!",
        }
        mock_ai_cls.return_value = mock_ai

        mock_tracker = Mock()
        mock_tracker.check_quota.return_value = (True, {})
        mock_tracker_cls.return_value = mock_tracker

        from apps.users.tasks import generate_weekly_reports

        result = generate_weekly_reports()
        assert result >= 1

        assert Notification.objects.filter(
            user=user, notification_type="system"
        ).exists()

    @patch("apps.users.tasks.AIUsageTracker")
    @patch("apps.users.tasks.OpenAIService")
    def test_skips_free_users(self, mock_ai_cls, mock_tracker_cls, db):
        """Does not generate reports for free users."""
        User.objects.create_user(
            email="free_wr_utask@example.com",
            password="testpass123",
            subscription="free",
            last_activity=timezone.now() - timedelta(days=1),
        )

        from apps.users.tasks import generate_weekly_reports

        result = generate_weekly_reports()
        assert result == 0

    @patch("apps.users.tasks.AIUsageTracker")
    @patch("apps.users.tasks.OpenAIService")
    def test_skips_users_at_quota(self, mock_ai_cls, mock_tracker_cls, db):
        """Skips users who have reached their AI quota."""
        User.objects.create_user(
            email="quota_wr_utask@example.com",
            password="testpass123",
            subscription="premium",
            last_activity=timezone.now() - timedelta(days=1),
        )

        mock_ai_cls.return_value = Mock()
        mock_tracker = Mock()
        mock_tracker.check_quota.return_value = (False, {})
        mock_tracker_cls.return_value = mock_tracker

        from apps.users.tasks import generate_weekly_reports

        result = generate_weekly_reports()
        assert result == 0

    @patch("apps.users.tasks.AIUsageTracker")
    @patch("apps.users.tasks.OpenAIService")
    def test_handles_openai_error(self, mock_ai_cls, mock_tracker_cls, db):
        """OpenAI errors are handled gracefully per user."""
        from core.exceptions import OpenAIError

        User.objects.create_user(
            email="err_wr_utask@example.com",
            password="testpass123",
            subscription="premium",
            last_activity=timezone.now() - timedelta(days=1),
        )

        mock_ai = Mock()
        mock_ai.generate_weekly_report.side_effect = OpenAIError("API fail")
        mock_ai_cls.return_value = mock_ai

        mock_tracker = Mock()
        mock_tracker.check_quota.return_value = (True, {})
        mock_tracker_cls.return_value = mock_tracker

        from apps.users.tasks import generate_weekly_reports

        result = generate_weekly_reports()
        assert result == 0  # All failed gracefully


# ──────────────────────────────────────────────────────────────────────
#  send_accountability_checkins
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendAccountabilityCheckins:
    """Tests for send_accountability_checkins task."""

    @patch("apps.users.tasks.AIUsageTracker")
    @patch("apps.users.tasks.OpenAIService")
    def test_sends_checkin_for_inactive_users(
        self, mock_ai_cls, mock_tracker_cls, db
    ):
        """Creates check-in notification for user inactive 2+ days."""
        user = User.objects.create_user(
            email="inactive_ac_utask@example.com",
            password="testpass123",
            last_activity=timezone.now() - timedelta(days=3),
        )
        Dream.objects.create(
            user=user, title="Dream", description="d", status="active"
        )

        mock_ai = Mock()
        mock_ai.generate_checkin.return_value = {
            "message": "Hey! You have been away.",
            "prompt_type": "gentle_nudge",
            "suggested_questions": [],
            "quick_actions": [],
        }
        mock_ai_cls.return_value = mock_ai

        mock_tracker = Mock()
        mock_tracker.check_quota.return_value = (True, {})
        mock_tracker_cls.return_value = mock_tracker

        from apps.users.tasks import send_accountability_checkins

        result = send_accountability_checkins()
        assert result >= 1

        assert Notification.objects.filter(
            user=user, notification_type="check_in"
        ).exists()

    @patch("apps.users.tasks.AIUsageTracker")
    @patch("apps.users.tasks.OpenAIService")
    def test_skips_recently_active_users(
        self, mock_ai_cls, mock_tracker_cls, db
    ):
        """Does not send check-in for recently active users."""
        user = User.objects.create_user(
            email="active_ac_utask@example.com",
            password="testpass123",
            last_activity=timezone.now(),
        )
        Dream.objects.create(
            user=user, title="Dream", description="d", status="active"
        )

        from apps.users.tasks import send_accountability_checkins

        result = send_accountability_checkins()
        assert result == 0

    @patch("apps.users.tasks.AIUsageTracker")
    @patch("apps.users.tasks.OpenAIService")
    def test_respects_notification_preferences(
        self, mock_ai_cls, mock_tracker_cls, db
    ):
        """Skips users who disabled accountability_checkins."""
        user = User.objects.create_user(
            email="nopref_ac_utask@example.com",
            password="testpass123",
            last_activity=timezone.now() - timedelta(days=3),
            notification_prefs={"accountability_checkins": False},
        )
        Dream.objects.create(
            user=user, title="Dream", description="d", status="active"
        )

        from apps.users.tasks import send_accountability_checkins

        result = send_accountability_checkins()
        assert result == 0

    @patch("apps.users.tasks.AIUsageTracker")
    @patch("apps.users.tasks.OpenAIService")
    def test_skips_users_without_active_dreams(
        self, mock_ai_cls, mock_tracker_cls, db
    ):
        """Does not send check-in to users with no active dreams."""
        User.objects.create_user(
            email="nodream_ac_utask@example.com",
            password="testpass123",
            last_activity=timezone.now() - timedelta(days=5),
        )

        from apps.users.tasks import send_accountability_checkins

        result = send_accountability_checkins()
        assert result == 0

    @patch("apps.users.tasks.AIUsageTracker")
    @patch("apps.users.tasks.OpenAIService")
    def test_handles_openai_error_gracefully(
        self, mock_ai_cls, mock_tracker_cls, db
    ):
        """OpenAI errors for a user do not crash the task."""
        from core.exceptions import OpenAIError

        user = User.objects.create_user(
            email="err_ac_utask@example.com",
            password="testpass123",
            last_activity=timezone.now() - timedelta(days=4),
        )
        Dream.objects.create(
            user=user, title="Dream", description="d", status="active"
        )

        mock_ai = Mock()
        mock_ai.generate_checkin.side_effect = OpenAIError("fail")
        mock_ai_cls.return_value = mock_ai

        mock_tracker = Mock()
        mock_tracker.check_quota.return_value = (True, {})
        mock_tracker_cls.return_value = mock_tracker

        from apps.users.tasks import send_accountability_checkins

        result = send_accountability_checkins()
        assert result == 0  # Graceful failure
