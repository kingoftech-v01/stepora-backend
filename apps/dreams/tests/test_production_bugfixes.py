"""
Regression tests for production bug fixes verified during QA session.

Covers 4 specific fixes:
1. `date_joined` -> `created_at` in subscriptions/tasks.py
2. `user.conversations` -> `user.ai_conversations` in users/tasks.py
3. `settings` import from django.conf in dreams/serializers.py
4. `is_read` -> `read_at` in users/tasks.py (notification field name)
"""

from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.users.models import User

# ───────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────


@pytest.fixture
def prod_user(db):
    return User.objects.create_user(
        email="prod_bugfix@test.com",
        password="testpass123",
        display_name="Prod Fix User",
    )


# ───────────────────────────────────────────────────────────────────
# Fix 1: date_joined -> created_at in subscriptions/tasks.py
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCreatedAtFieldInSubscriptionsTasks:
    """Verify subscriptions tasks use `created_at` (not `date_joined`)."""

    def test_user_model_has_created_at(self, prod_user):
        """User model has created_at field (not date_joined)."""
        assert hasattr(prod_user, "created_at")
        assert prod_user.created_at is not None

    def test_free_user_push_notification_filter(self, prod_user):
        """The subscription task filters by created_at, not date_joined.

        We verify by importing the task and checking it can be called
        without FieldError on date_joined.
        """
        from apps.subscriptions.tasks import send_free_user_upgrade_reminders

        # Patch to avoid actual notification sending
        with patch("apps.subscriptions.tasks._send_upgrade_push") as mock_push:
            mock_push.delay = Mock()
            # This should NOT raise FieldError about date_joined
            send_free_user_upgrade_reminders()
            # No assertion on call count — the user may or may not match
            # the filter criteria. The key test is no exception raised.


# ───────────────────────────────────────────────────────────────────
# Fix 2: user.conversations -> user.ai_conversations in users/tasks.py
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAIConversationsRelatedName:
    """Verify users/tasks.py uses `user.ai_conversations` (not `user.conversations`)."""

    def test_user_has_ai_conversations_related_name(self, prod_user):
        """User model has ai_conversations reverse relation."""
        # This should not raise AttributeError
        qs = prod_user.ai_conversations.all()
        assert qs.count() == 0

    @patch("core.email.send_templated_email")
    @patch("django.core.files.storage.default_storage")
    def test_export_user_data_uses_ai_conversations(
        self, mock_storage, mock_email, prod_user
    ):
        """export_user_data task accesses user.ai_conversations without error."""
        from apps.users.tasks import export_user_data

        mock_storage.save.return_value = "exports/test.json"

        # This should NOT raise AttributeError about 'conversations'
        export_user_data(str(prod_user.id))


# ───────────────────────────────────────────────────────────────────
# Fix 3: settings import in dreams/serializers.py
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSettingsImportInDreamSerializers:
    """Verify dreams/serializers.py imports settings from django.conf."""

    def test_settings_import_exists(self):
        """The import `from django.conf import settings` is present and valid."""
        from apps.dreams import serializers

        # Access settings through the module — no ImportError
        assert hasattr(serializers, "settings")

    def test_signed_vision_url_uses_settings(self, prod_user):
        """DreamSerializer.get_signed_vision_image_url uses settings.AWS_STORAGE_BUCKET_NAME."""
        from apps.dreams.models import Dream
        from apps.dreams.serializers import DreamSerializer

        dream = Dream.objects.create(
            user=prod_user,
            title="Settings Test",
            description="Test settings import",
            category="career",
        )
        # Should not raise NameError on 'settings'
        data = DreamSerializer(dream).data
        assert "signed_vision_image_url" in data


# ───────────────────────────────────────────────────────────────────
# Fix 4: is_read -> read_at in users/tasks.py
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestReadAtFieldInNotifications:
    """Verify users/tasks.py references `read_at` (not `is_read`)."""

    def test_notification_model_has_read_at(self):
        """Notification model has read_at field."""
        from apps.notifications.models import Notification

        assert hasattr(Notification, "read_at")

    @patch("core.email.send_templated_email")
    @patch("django.core.files.storage.default_storage")
    def test_export_references_read_at_not_is_read(
        self, mock_storage, mock_email, prod_user
    ):
        """export_user_data queries notification read_at without FieldError."""
        from apps.notifications.services import NotificationService
        from apps.users.tasks import export_user_data

        # Create a notification so the values() query has data to work with
        NotificationService.create(
            user=prod_user,
            notification_type="system",
            title="Test Notification",
            body="Test body",
            scheduled_for=timezone.now(),
        )

        mock_storage.save.return_value = "exports/test.json"

        # This should NOT raise FieldError about 'is_read'
        export_user_data(str(prod_user.id))
