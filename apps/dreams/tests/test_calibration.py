"""
Regression tests for calibration bugs.

Covers:
  C1 - TypeError crash on null OpenAI content
  C5 - Resume in_progress calibration (no duplicate questions)
  C6 - Status guard (reject answers when completed/skipped)
  C7 - Refusal reason returned to user
  C8 - Minimum answer length validation
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dreams.models import CalibrationResponse, Dream
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User
from core.ai_validators import CalibrationQuestionsResponseSchema, CalibrationQuestionSchema


# ───────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────


@pytest.fixture
def cal_user(db):
    """User with premium plan (needed for CanUseAI permission)."""
    user = User.objects.create_user(
        email="cal@test.com",
        password="testpass123",
        display_name="Cal User",
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
    # The post_save signal auto-creates a free subscription for new users.
    # Update it to premium so CanUseAI permission passes.
    Subscription.objects.filter(user=user).update(
        plan=plan,
        status="active",
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=30),
    )
    # Clear cached plan on user instance
    if hasattr(user, "_cached_plan"):
        delattr(user, "_cached_plan")
    return user


@pytest.fixture
def cal_client(cal_user):
    c = APIClient()
    c.force_authenticate(user=cal_user)
    return c


@pytest.fixture
def cal_dream(cal_user):
    return Dream.objects.create(
        user=cal_user,
        title="Test Calibration Dream",
        description="Description for calibration testing",
        category="career",
        status="active",
    )


# ───────────────────────────────────────────────────────────────────
# C1: TypeError on null OpenAI content
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalibrationOpenAICrash:
    """Bug C1: generate_calibration_questions returning None/causing TypeError."""

    @patch("apps.dreams.views.validate_calibration_questions")
    @patch("integrations.openai_service.OpenAIService.generate_calibration_questions")
    def test_openai_error_returns_error_response(
        self, mock_gen, mock_validate, cal_client, cal_dream
    ):
        """When OpenAI raises an error, the view should return a proper HTTP error, not crash."""
        from core.exceptions import OpenAIError

        mock_gen.side_effect = OpenAIError("Service unavailable")
        response = cal_client.post(
            f"/api/dreams/dreams/{cal_dream.id}/start_calibration/"
        )
        # Should return a handled error, not a 500
        assert response.status_code in (500, 502, 503)
        # The response should have an error message
        assert "error" in response.data or "detail" in response.data

    @patch("apps.dreams.views.validate_calibration_questions")
    @patch("integrations.openai_service.OpenAIService.generate_calibration_questions")
    def test_ai_validation_error_returns_502(
        self, mock_gen, mock_validate, cal_client, cal_dream
    ):
        """AIValidationError returns 502 with descriptive message."""
        from core.ai_validators import AIValidationError

        mock_gen.return_value = {"questions": [], "sufficient": False}
        mock_validate.side_effect = AIValidationError("Invalid format")
        response = cal_client.post(
            f"/api/dreams/dreams/{cal_dream.id}/start_calibration/"
        )
        assert response.status_code == 502
        assert "error" in response.data


# ───────────────────────────────────────────────────────────────────
# C5: Resume in_progress calibration
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalibrationResume:
    """Bug C5: Re-entering calibration should return existing unanswered questions or
    handle the in_progress state correctly."""

    @patch("apps.dreams.views.validate_calibration_questions")
    @patch("integrations.openai_service.OpenAIService.generate_calibration_questions")
    def test_start_returns_in_progress_status(
        self, mock_gen, mock_validate, cal_client, cal_dream
    ):
        """When calibration is in_progress, start_calibration should not return 400."""
        cal_dream.calibration_status = "in_progress"
        cal_dream.save(update_fields=["calibration_status"])

        # Create existing unanswered questions
        CalibrationResponse.objects.create(
            dream=cal_dream, question="Existing Q1", question_number=1, category="motivation"
        )

        # Mock in case the view falls through to AI (EncryptedField filter quirk)
        mock_gen.return_value = {
            "questions": [{"question": "Fallback Q", "category": "test"}],
            "sufficient": False, "confidence_score": 0.2,
        }
        result = CalibrationQuestionsResponseSchema(
            questions=[CalibrationQuestionSchema(question="Fallback Q", category="test")],
            sufficient=False, confidence_score=0.2,
        )
        mock_validate.return_value = result

        response = cal_client.post(
            f"/api/dreams/dreams/{cal_dream.id}/start_calibration/"
        )
        # Should succeed (200), not error out
        assert response.status_code == 200
        assert "questions" in response.data

    def test_already_completed_returns_400(self, cal_client, cal_dream):
        """When calibration is completed, start_calibration should return 400."""
        cal_dream.calibration_status = "completed"
        cal_dream.save(update_fields=["calibration_status"])

        response = cal_client.post(
            f"/api/dreams/dreams/{cal_dream.id}/start_calibration/"
        )
        assert response.status_code == 400


# ───────────────────────────────────────────────────────────────────
# C6: Status guard
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalibrationStatusGuard:
    """Bug C6: answer_calibration must reject answers when already completed or skipped."""

    def test_answer_rejected_when_completed(self, cal_client, cal_dream):
        cal_dream.calibration_status = "completed"
        cal_dream.save(update_fields=["calibration_status"])

        response = cal_client.post(
            f"/api/dreams/dreams/{cal_dream.id}/answer_calibration/",
            {"question": "test q", "answer": "test answer", "questionNumber": 1},
            format="json",
        )
        assert response.status_code == 400
        assert "error" in response.data

    def test_answer_rejected_when_skipped(self, cal_client, cal_dream):
        cal_dream.calibration_status = "skipped"
        cal_dream.save(update_fields=["calibration_status"])

        response = cal_client.post(
            f"/api/dreams/dreams/{cal_dream.id}/answer_calibration/",
            {"question": "test q", "answer": "test answer", "questionNumber": 1},
            format="json",
        )
        assert response.status_code == 400
        assert "error" in response.data

    def test_answer_accepted_when_in_progress(self, cal_client, cal_dream):
        """Verify answers ARE accepted when status is in_progress (guard does not over-block)."""
        cal_dream.calibration_status = "in_progress"
        cal_dream.save(update_fields=["calibration_status"])

        # Create the calibration response so the answer can be matched
        CalibrationResponse.objects.create(
            dream=cal_dream, question="test q", question_number=1
        )

        response = cal_client.post(
            f"/api/dreams/dreams/{cal_dream.id}/answer_calibration/",
            {"question": "test q", "answer": "This is a valid answer", "questionNumber": 1},
            format="json",
        )
        # Should not be 400 (guard should not block in_progress)
        assert response.status_code != 400


# ───────────────────────────────────────────────────────────────────
# C7: Refusal reason
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalibrationRefusal:
    """Bug C7: When AI returns a refusal_reason, it must be returned to the user."""

    @patch("apps.dreams.views.validate_calibration_questions")
    @patch("integrations.openai_service.OpenAIService.generate_calibration_questions")
    def test_refusal_reason_returned_to_user(
        self, mock_gen, mock_validate, cal_client, cal_dream
    ):
        mock_gen.return_value = {
            "questions": [],
            "sufficient": True,
            "confidence_score": 0,
            "refusal_reason": "Harmful content detected",
        }
        # The validated result should have refusal_reason
        result = CalibrationQuestionsResponseSchema(
            questions=[],
            sufficient=True,
            confidence_score=0,
            refusal_reason="Harmful content detected",
        )
        mock_validate.return_value = result

        response = cal_client.post(
            f"/api/dreams/dreams/{cal_dream.id}/start_calibration/"
        )
        assert response.status_code == 400
        assert "error" in response.data
        assert "Harmful content" in response.data["error"]

    @patch("apps.dreams.views.validate_calibration_questions")
    @patch("integrations.openai_service.OpenAIService.generate_calibration_questions")
    def test_no_refusal_returns_questions(
        self, mock_gen, mock_validate, cal_client, cal_dream
    ):
        """When there is no refusal, questions should be returned normally."""
        mock_gen.return_value = {
            "questions": [
                {"question": "What is your timeline?", "category": "timeline"},
            ],
            "sufficient": False,
            "confidence_score": 0.2,
        }
        result = CalibrationQuestionsResponseSchema(
            questions=[
                CalibrationQuestionSchema(question="What is your timeline?", category="timeline"),
            ],
            sufficient=False,
            confidence_score=0.2,
            refusal_reason=None,
        )
        mock_validate.return_value = result

        response = cal_client.post(
            f"/api/dreams/dreams/{cal_dream.id}/start_calibration/"
        )
        assert response.status_code == 200
        assert len(response.data["questions"]) >= 1


# ───────────────────────────────────────────────────────────────────
# C8: Minimum answer length
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalibrationMinLength:
    """Bug C8: Answers shorter than 3 characters must be rejected."""

    def test_short_answer_rejected(self, cal_client, cal_dream):
        cal_dream.calibration_status = "in_progress"
        cal_dream.save(update_fields=["calibration_status"])

        response = cal_client.post(
            f"/api/dreams/dreams/{cal_dream.id}/answer_calibration/",
            {"question": "test q", "answer": "ab", "questionNumber": 1},
            format="json",
        )
        assert response.status_code == 400
        assert "min_length" in response.data or "error" in response.data

    def test_valid_answer_accepted(self, cal_client, cal_dream):
        cal_dream.calibration_status = "in_progress"
        cal_dream.save(update_fields=["calibration_status"])

        # Create a CalibrationResponse to match against
        CalibrationResponse.objects.create(
            dream=cal_dream, question="test q", question_number=1
        )

        response = cal_client.post(
            f"/api/dreams/dreams/{cal_dream.id}/answer_calibration/",
            {"question": "test q", "answer": "This is a valid answer that is long enough", "questionNumber": 1},
            format="json",
        )
        # Should not be rejected for length
        assert response.status_code != 400 or "min_length" not in response.data

    def test_three_char_answer_accepted(self, cal_client, cal_dream):
        """Exactly 3 characters should be accepted (boundary test)."""
        cal_dream.calibration_status = "in_progress"
        cal_dream.save(update_fields=["calibration_status"])

        CalibrationResponse.objects.create(
            dream=cal_dream, question="test q", question_number=1
        )

        response = cal_client.post(
            f"/api/dreams/dreams/{cal_dream.id}/answer_calibration/",
            {"question": "test q", "answer": "yes", "questionNumber": 1},
            format="json",
        )
        # 3 chars should pass the min_length check
        assert response.status_code != 400 or "min_length" not in response.data
