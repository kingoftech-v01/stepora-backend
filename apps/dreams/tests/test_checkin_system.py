"""
Regression tests for the check-in system refactor.

Covers:
- trigger_checkin rate limit (429 if < 7 days since last check-in)
- trigger_checkin success when eligible
- Celery task sends notifications on awaiting_user
- can_checkin serializer field
- days_until_checkin serializer field
- has_pending_checkin serializer field
"""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from apps.dreams.models import Dream
from apps.dreams.serializers import DreamDetailSerializer, DreamSerializer
from apps.plans.models import PlanCheckIn
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User

# ───────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────


@pytest.fixture
def checkin_user(db):
    """User with premium plan for CanUseAI permission."""
    user = User.objects.create_user(
        email="checkin-system@test.com",
        password="testpass123",
        display_name="CheckIn Tester",
        timezone="Europe/Paris",
    )
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="premium",
        defaults={
            "name": "Premium",
            "price_monthly": 19.99,
            "is_active": True,
            "dream_limit": 10,
            "has_ai": True,
            "has_vision_board": False,
        },
    )
    Subscription.objects.filter(user=user).update(
        plan=plan,
        status="active",
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=30),
    )
    if hasattr(user, "_cached_plan"):
        delattr(user, "_cached_plan")
    return user


@pytest.fixture
def checkin_client(checkin_user):
    c = APIClient()
    c.force_authenticate(user=checkin_user)
    return c


@pytest.fixture
def checkin_dream(checkin_user):
    return Dream.objects.create(
        user=checkin_user,
        title="Check-In Test Dream",
        description="Dream for testing check-in system",
        category="career",
        status="active",
        plan_phase="partial",
    )


def serialize_dream(dream, user, serializer_class=DreamSerializer):
    """Helper to serialize a dream with request context."""
    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = user
    return serializer_class(dream, context={"request": request}).data


# ───────────────────────────────────────────────────────────────────
# trigger_checkin rate limit: 429 if < 7 days since last check-in
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTriggerCheckinRateLimit:
    """Test the 7-day cooldown on trigger_checkin endpoint."""

    @patch("apps.dreams.tasks.generate_checkin_questionnaire_task")
    def test_rate_limit_429_when_checked_in_today(
        self, mock_task, checkin_client, checkin_dream
    ):
        """Returns 429 when last check-in was today (< 7 days ago)."""
        checkin_dream.last_checkin_at = timezone.now()
        checkin_dream.save(update_fields=["last_checkin_at"])

        response = checkin_client.post(
            f"/api/dreams/dreams/{checkin_dream.id}/trigger-checkin/"
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "days_remaining" in response.data

    @patch("apps.dreams.tasks.generate_checkin_questionnaire_task")
    def test_rate_limit_429_when_checked_in_3_days_ago(
        self, mock_task, checkin_client, checkin_dream
    ):
        """Returns 429 when last check-in was 3 days ago."""
        checkin_dream.last_checkin_at = timezone.now() - timedelta(days=3)
        checkin_dream.save(update_fields=["last_checkin_at"])

        response = checkin_client.post(
            f"/api/dreams/dreams/{checkin_dream.id}/trigger-checkin/"
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.data["days_remaining"] == 4

    @patch("apps.dreams.tasks.generate_checkin_questionnaire_task")
    def test_success_when_no_previous_checkin(
        self, mock_task, checkin_client, checkin_dream
    ):
        """Returns 202 when dream has never had a check-in."""
        mock_task.apply_async = Mock()
        response = checkin_client.post(
            f"/api/dreams/dreams/{checkin_dream.id}/trigger-checkin/"
        )
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "checkin_id" in response.data

    @patch("apps.dreams.tasks.generate_checkin_questionnaire_task")
    def test_success_when_checked_in_7_days_ago(
        self, mock_task, checkin_client, checkin_dream
    ):
        """Returns 202 when last check-in was exactly 7 days ago."""
        checkin_dream.last_checkin_at = timezone.now() - timedelta(days=7)
        checkin_dream.save(update_fields=["last_checkin_at"])

        mock_task.apply_async = Mock()
        response = checkin_client.post(
            f"/api/dreams/dreams/{checkin_dream.id}/trigger-checkin/"
        )
        assert response.status_code == status.HTTP_202_ACCEPTED

    @patch("apps.dreams.tasks.generate_checkin_questionnaire_task")
    def test_success_when_checked_in_10_days_ago(
        self, mock_task, checkin_client, checkin_dream
    ):
        """Returns 202 when last check-in was 10 days ago."""
        checkin_dream.last_checkin_at = timezone.now() - timedelta(days=10)
        checkin_dream.save(update_fields=["last_checkin_at"])

        mock_task.apply_async = Mock()
        response = checkin_client.post(
            f"/api/dreams/dreams/{checkin_dream.id}/trigger-checkin/"
        )
        assert response.status_code == status.HTTP_202_ACCEPTED

    def test_no_plan_returns_400(self, checkin_client, checkin_dream):
        """Returns 400 when dream has no plan."""
        checkin_dream.plan_phase = "none"
        checkin_dream.save(update_fields=["plan_phase"])

        response = checkin_client.post(
            f"/api/dreams/dreams/{checkin_dream.id}/trigger-checkin/"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ───────────────────────────────────────────────────────────────────
# Active check-in guard
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTriggerCheckinActiveGuard:
    """Test that active check-ins are returned instead of creating new ones."""

    @patch("apps.dreams.tasks.generate_checkin_questionnaire_task")
    def test_existing_awaiting_user_returns_202(
        self, mock_task, checkin_client, checkin_dream
    ):
        """Returns 202 with existing checkin_id when awaiting_user."""
        active = PlanCheckIn.objects.create(
            dream=checkin_dream,
            status="awaiting_user",
            scheduled_for=timezone.now(),
        )
        response = checkin_client.post(
            f"/api/dreams/dreams/{checkin_dream.id}/trigger-checkin/"
        )
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["checkin_id"] == str(active.id)
        assert response.data["status"] == "awaiting_user"

    @patch("apps.dreams.tasks.generate_checkin_questionnaire_task")
    def test_existing_pending_returns_202(
        self, mock_task, checkin_client, checkin_dream
    ):
        """Returns 202 with existing checkin_id when pending."""
        active = PlanCheckIn.objects.create(
            dream=checkin_dream,
            status="pending",
            scheduled_for=timezone.now(),
        )
        response = checkin_client.post(
            f"/api/dreams/dreams/{checkin_dream.id}/trigger-checkin/"
        )
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["checkin_id"] == str(active.id)


# ───────────────────────────────────────────────────────────────────
# Celery task: only sends notifications (doesn't create check-ins)
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCheckinCeleryTask:
    """Test that generate_checkin_questionnaire_task sends notification."""

    @patch("apps.notifications.services.NotificationDeliveryService")
    @patch("apps.dreams.tasks.NotificationService")
    @patch("apps.dreams.tasks.OpenAIService")
    @patch("core.ai_validators.validate_checkin_questionnaire")
    def test_task_sends_notification_on_success(
        self, mock_validate, mock_ai_cls, mock_notif_cls, mock_delivery_cls,
        checkin_dream,
    ):
        """Celery task creates notification when check-in becomes awaiting_user."""
        from apps.dreams.tasks import generate_checkin_questionnaire_task
        from core.ai_validators import CheckInQuestionnaireSchema, CheckInQuestionSchema

        checkin = PlanCheckIn.objects.create(
            dream=checkin_dream,
            status="pending",
            scheduled_for=timezone.now(),
            triggered_by="manual",
        )

        # Mock AI service
        mock_ai = mock_ai_cls.return_value
        mock_ai.generate_checkin_questionnaire.return_value = {
            "questions": [
                {
                    "id": "q1",
                    "question_type": "slider",
                    "question": "How is your progress?",
                }
            ],
        }

        # Mock validator
        mock_validate.return_value = CheckInQuestionnaireSchema(
            questions=[
                CheckInQuestionSchema(
                    id="q1",
                    question_type="slider",
                    question="How is your progress?",
                    scale_min=1,
                    scale_max=10,
                ),
            ],
            opening_message="Time for your check-in!",
        )

        # Mock notification
        mock_notification = Mock()
        mock_notif_cls.create.return_value = mock_notification

        generate_checkin_questionnaire_task(str(checkin.id))

        # Verify notification was created
        mock_notif_cls.create.assert_called_once()
        call_kwargs = mock_notif_cls.create.call_args
        assert call_kwargs[1]["notification_type"] == "check_in"
        assert "Check-in Ready" in call_kwargs[1]["title"]

        # Verify notification was delivered
        mock_delivery_cls.return_value.deliver.assert_called_once_with(
            mock_notification
        )

        # Verify check-in status updated
        checkin.refresh_from_db()
        assert checkin.status == "awaiting_user"


# ───────────────────────────────────────────────────────────────────
# Serializer fields: can_checkin, days_until_checkin, has_pending_checkin
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCanCheckinSerializerField:
    """Test can_checkin field in DreamSerializer."""

    def test_can_checkin_true_when_never_done(self, checkin_dream, checkin_user):
        data = serialize_dream(checkin_dream, checkin_user)
        assert data["can_checkin"] is True

    def test_can_checkin_false_when_no_plan(self, checkin_user):
        dream = Dream.objects.create(
            user=checkin_user,
            title="No Plan",
            description="Test",
            category="career",
            plan_phase="none",
        )
        data = serialize_dream(dream, checkin_user)
        assert data["can_checkin"] is False

    def test_can_checkin_false_when_checked_in_today(
        self, checkin_dream, checkin_user
    ):
        checkin_dream.last_checkin_at = timezone.now()
        checkin_dream.save(update_fields=["last_checkin_at"])
        data = serialize_dream(checkin_dream, checkin_user)
        assert data["can_checkin"] is False

    def test_can_checkin_true_when_checked_in_7_days_ago(
        self, checkin_dream, checkin_user
    ):
        checkin_dream.last_checkin_at = timezone.now() - timedelta(days=7)
        checkin_dream.save(update_fields=["last_checkin_at"])
        data = serialize_dream(checkin_dream, checkin_user)
        assert data["can_checkin"] is True

    def test_can_checkin_false_when_awaiting_user(
        self, checkin_dream, checkin_user
    ):
        PlanCheckIn.objects.create(
            dream=checkin_dream,
            status="awaiting_user",
            scheduled_for=timezone.now(),
        )
        data = serialize_dream(checkin_dream, checkin_user)
        assert data["can_checkin"] is False

    def test_can_checkin_false_when_pending(
        self, checkin_dream, checkin_user
    ):
        PlanCheckIn.objects.create(
            dream=checkin_dream,
            status="pending",
            scheduled_for=timezone.now(),
        )
        data = serialize_dream(checkin_dream, checkin_user)
        assert data["can_checkin"] is False


@pytest.mark.django_db
class TestDaysUntilCheckinSerializerField:
    """Test days_until_checkin field in DreamSerializer."""

    def test_days_0_when_never_done(self, checkin_dream, checkin_user):
        data = serialize_dream(checkin_dream, checkin_user)
        assert data["days_until_checkin"] == 0

    def test_days_0_when_can_checkin(self, checkin_dream, checkin_user):
        checkin_dream.last_checkin_at = timezone.now() - timedelta(days=10)
        checkin_dream.save(update_fields=["last_checkin_at"])
        data = serialize_dream(checkin_dream, checkin_user)
        assert data["days_until_checkin"] == 0

    def test_days_remaining_when_cooldown(self, checkin_dream, checkin_user):
        checkin_dream.last_checkin_at = timezone.now() - timedelta(days=3)
        checkin_dream.save(update_fields=["last_checkin_at"])
        data = serialize_dream(checkin_dream, checkin_user)
        # Should be 3 or 4 depending on time-of-day rounding
        assert data["days_until_checkin"] in (3, 4)

    def test_days_0_when_awaiting_user(self, checkin_dream, checkin_user):
        """When awaiting_user check-in exists, days=0 (finish that one)."""
        PlanCheckIn.objects.create(
            dream=checkin_dream,
            status="awaiting_user",
            scheduled_for=timezone.now(),
        )
        data = serialize_dream(checkin_dream, checkin_user)
        assert data["days_until_checkin"] == 0


@pytest.mark.django_db
class TestHasPendingCheckinSerializerField:
    """Test has_pending_checkin field in DreamSerializer."""

    def test_false_when_no_checkins(self, checkin_dream, checkin_user):
        data = serialize_dream(checkin_dream, checkin_user)
        assert data["has_pending_checkin"] is False

    def test_true_when_awaiting_user(self, checkin_dream, checkin_user):
        PlanCheckIn.objects.create(
            dream=checkin_dream,
            status="awaiting_user",
            scheduled_for=timezone.now(),
        )
        data = serialize_dream(checkin_dream, checkin_user)
        assert data["has_pending_checkin"] is True

    def test_false_when_completed(self, checkin_dream, checkin_user):
        PlanCheckIn.objects.create(
            dream=checkin_dream,
            status="completed",
            scheduled_for=timezone.now(),
        )
        data = serialize_dream(checkin_dream, checkin_user)
        assert data["has_pending_checkin"] is False

    def test_false_when_failed(self, checkin_dream, checkin_user):
        PlanCheckIn.objects.create(
            dream=checkin_dream,
            status="failed",
            scheduled_for=timezone.now(),
        )
        data = serialize_dream(checkin_dream, checkin_user)
        assert data["has_pending_checkin"] is False


# ───────────────────────────────────────────────────────────────────
# DreamDetailSerializer also includes check-in fields
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDreamDetailSerializerCheckinFields:
    """Verify DreamDetailSerializer also exposes check-in fields."""

    def test_detail_has_can_checkin(self, checkin_dream, checkin_user):
        data = serialize_dream(
            checkin_dream, checkin_user, DreamDetailSerializer
        )
        assert "can_checkin" in data

    def test_detail_has_days_until_checkin(self, checkin_dream, checkin_user):
        data = serialize_dream(
            checkin_dream, checkin_user, DreamDetailSerializer
        )
        assert "days_until_checkin" in data

    def test_detail_has_has_pending_checkin(self, checkin_dream, checkin_user):
        data = serialize_dream(
            checkin_dream, checkin_user, DreamDetailSerializer
        )
        assert "has_pending_checkin" in data
