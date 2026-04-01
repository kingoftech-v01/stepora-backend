"""
Regression tests for calibration bugs:
1. EncryptedTextField: DB-level filters (answer="", answer__gt="") don't work
   on ciphertext. Must filter in Python after decryption.
2. start_calibration with in_progress + all answered should complete,
   not regenerate duplicate questions.
3. answer_calibration should not auto-complete while unanswered questions remain.
"""
import uuid
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from django.contrib.auth import get_user_model
from apps.dreams.models import Dream
from apps.plans.models import CalibrationResponse, Goal
from apps.subscriptions.models import SubscriptionPlan, Subscription

User = get_user_model()


@pytest.fixture
def ai_user(db):
    """User with premium plan (CanUseAI permission)."""
    user = User.objects.create_user(
        email=f"test-{uuid.uuid4().hex[:8]}@stepora.app",
        password="Testpass123!",
        display_name="Test User",
    )
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="premium",
        defaults={
            "name": "Premium",
            "price_monthly": 19.99,
            "is_active": True,
            "dream_limit": 10,
            "has_ai": True,
        },
    )
    Subscription.objects.update_or_create(
        user=user,
        defaults={"plan": plan, "status": "active"},
    )
    if hasattr(user, "_cached_plan"):
        delattr(user, "_cached_plan")
    return user


@pytest.fixture
def client(ai_user):
    c = APIClient()
    c.force_authenticate(user=ai_user)
    return c


@pytest.fixture
def dream_in_progress(ai_user):
    return Dream.objects.create(
        user=ai_user,
        title="Test Dream",
        description="A test dream",
        calibration_status="in_progress",
        status="active",
    )


# ─── EncryptedTextField filtering ─────────────────────────────────


class TestEncryptedFieldFiltering:
    """Regression: EncryptedTextField makes DB-level empty checks unreliable."""

    def test_empty_answer_detected_correctly(self, ai_user, dream_in_progress):
        CalibrationResponse.objects.create(dream=dream_in_progress, question_number=1, question="Q1", answer="Real answer")
        CalibrationResponse.objects.create(dream=dream_in_progress, question_number=2, question="Q2", answer="")
        CalibrationResponse.objects.create(dream=dream_in_progress, question_number=3, question="Q3", answer="  ")

        all_responses = list(CalibrationResponse.objects.filter(dream=dream_in_progress))
        unanswered = [cr for cr in all_responses if not cr.answer or not cr.answer.strip()]

        assert len(unanswered) == 2, "Q2 (empty) and Q3 (whitespace) should be unanswered"

    def test_answered_count_correct(self, ai_user, dream_in_progress):
        for i in range(7):
            answer = f"Answer {i}" if i < 3 else ""
            CalibrationResponse.objects.create(dream=dream_in_progress, question_number=i + 1, question=f"Q{i+1}", answer=answer)

        all_responses = list(CalibrationResponse.objects.filter(dream=dream_in_progress))
        answered = [cr for cr in all_responses if cr.answer and cr.answer.strip()]

        assert len(answered) == 3
        assert len(all_responses) - len(answered) == 4


# ─── start_calibration resume ────────────────────────────────────


class TestStartCalibrationResume:
    """Regression: start_calibration should not create duplicates."""

    def test_resume_returns_unanswered_questions(self, client, dream_in_progress):
        CalibrationResponse.objects.create(dream=dream_in_progress, question_number=1, question="Q1", answer="Done")
        CalibrationResponse.objects.create(dream=dream_in_progress, question_number=2, question="Q2", answer="")
        CalibrationResponse.objects.create(dream=dream_in_progress, question_number=3, question="Q3", answer="")

        r = client.post(f"/api/dreams/dreams/{dream_in_progress.id}/start_calibration/")

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "in_progress"
        assert len(data["questions"]) == 2  # Q2 and Q3

    @patch("apps.dreams.views.OpenAIService")
    def test_all_answered_completes_not_duplicates(self, mock_ai, client, dream_in_progress):
        for i in range(7):
            CalibrationResponse.objects.create(dream=dream_in_progress, question_number=i + 1, question=f"Q{i+1}", answer=f"Answer {i+1}")

        count_before = CalibrationResponse.objects.filter(dream=dream_in_progress).count()

        r = client.post(f"/api/dreams/dreams/{dream_in_progress.id}/start_calibration/")

        assert r.status_code == 200
        assert r.json()["status"] == "completed"

        count_after = CalibrationResponse.objects.filter(dream=dream_in_progress).count()
        assert count_after == count_before, "No duplicate questions should be created"


# ─── answer_calibration completion guards ─────────────────────────


class TestAnswerCalibrationCompletion:
    """Regression: answer_calibration should not auto-complete prematurely."""

    def test_no_completion_while_unanswered_remain(self, client, dream_in_progress):
        for i in range(7):
            CalibrationResponse.objects.create(dream=dream_in_progress, question_number=i + 1, question=f"Q{i+1}", answer="")

        r = client.post(
            f"/api/dreams/dreams/{dream_in_progress.id}/answer_calibration/",
            {"question": "Q1", "answer": "My answer", "question_number": 1},
            format="json",
        )

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "in_progress"
        assert data["remaining"] == 6

        dream_in_progress.refresh_from_db()
        assert dream_in_progress.calibration_status == "in_progress"

    def test_already_answered_rejected(self, client, dream_in_progress):
        CalibrationResponse.objects.create(dream=dream_in_progress, question_number=1, question="Q1", answer="Already done")

        r = client.post(
            f"/api/dreams/dreams/{dream_in_progress.id}/answer_calibration/",
            {"question": "Q1", "answer": "Try again", "question_number": 1},
            format="json",
        )

        assert r.status_code == 400


# ─── Status guards ────────────────────────────────────────────────


class TestCalibrationStatusGuards:

    def test_answer_rejected_when_completed(self, client, ai_user):
        dream = Dream.objects.create(user=ai_user, title="Done", description="test", calibration_status="completed", status="active")

        r = client.post(
            f"/api/dreams/dreams/{dream.id}/answer_calibration/",
            {"question": "Q1", "answer": "answer", "question_number": 1},
            format="json",
        )
        assert r.status_code == 400

    def test_answer_rejected_when_pending(self, client, ai_user):
        dream = Dream.objects.create(user=ai_user, title="Pending", description="test", calibration_status="pending", status="active")

        r = client.post(
            f"/api/dreams/dreams/{dream.id}/answer_calibration/",
            {"question": "Q1", "answer": "answer", "question_number": 1},
            format="json",
        )
        assert r.status_code == 400

    def test_start_rejected_when_completed(self, client, ai_user):
        dream = Dream.objects.create(user=ai_user, title="Completed", description="test", calibration_status="completed", status="active")

        r = client.post(f"/api/dreams/dreams/{dream.id}/start_calibration/")
        assert r.status_code == 400


# ─── Centralized status function ─────────────────────────────────


class TestCheckAndUpdateCalibrationStatus:
    """Tests for the centralized check_and_update_calibration_status function."""

    def test_skipped_stays_skipped(self, ai_user):
        dream = Dream.objects.create(user=ai_user, title="Skipped", description="test", calibration_status="skipped", status="active")
        from apps.dreams.calibration import check_and_update_calibration_status
        result = check_and_update_calibration_status(dream)
        assert result == "skipped"

    def test_completed_stays_completed(self, ai_user):
        dream = Dream.objects.create(user=ai_user, title="Done", description="test", calibration_status="completed", status="active")
        from apps.dreams.calibration import check_and_update_calibration_status
        result = check_and_update_calibration_status(dream)
        assert result == "completed"

    def test_plan_exists_marks_completed(self, ai_user):
        dream = Dream.objects.create(user=ai_user, title="Has plan", description="test", calibration_status="in_progress", status="active")
        Goal.objects.create(dream=dream, title="Goal 1", order=1)
        from apps.dreams.calibration import check_and_update_calibration_status
        result = check_and_update_calibration_status(dream)
        assert result == "completed"
        dream.refresh_from_db()
        assert dream.calibration_status == "completed"

    def test_7_answers_all_done_marks_completed(self, ai_user):
        dream = Dream.objects.create(user=ai_user, title="All done", description="test", calibration_status="in_progress", status="active")
        for i in range(7):
            CalibrationResponse.objects.create(dream=dream, question_number=i+1, question=f"Q{i+1}", answer=f"Answer {i+1}")
        from apps.dreams.calibration import check_and_update_calibration_status
        result = check_and_update_calibration_status(dream)
        assert result == "completed"
        dream.refresh_from_db()
        assert dream.calibration_status == "completed"

    def test_unanswered_remain_stays_in_progress(self, ai_user):
        dream = Dream.objects.create(user=ai_user, title="Partial", description="test", calibration_status="in_progress", status="active")
        for i in range(7):
            answer = f"Answer {i+1}" if i < 5 else ""
            CalibrationResponse.objects.create(dream=dream, question_number=i+1, question=f"Q{i+1}", answer=answer)
        from apps.dreams.calibration import check_and_update_calibration_status
        result = check_and_update_calibration_status(dream)
        assert result == "in_progress"

    def test_no_responses_stays_pending(self, ai_user):
        dream = Dream.objects.create(user=ai_user, title="Fresh", description="test", calibration_status="pending", status="active")
        from apps.dreams.calibration import check_and_update_calibration_status
        result = check_and_update_calibration_status(dream)
        assert result == "pending"

    def test_fewer_than_7_all_answered_stays_in_progress(self, ai_user):
        dream = Dream.objects.create(user=ai_user, title="Few", description="test", calibration_status="in_progress", status="active")
        for i in range(3):
            CalibrationResponse.objects.create(dream=dream, question_number=i+1, question=f"Q{i+1}", answer=f"Answer {i+1}")
        from apps.dreams.calibration import check_and_update_calibration_status
        result = check_and_update_calibration_status(dream)
        # 3 answered, 0 unanswered, but < 7 total → stays in_progress
        assert result == "in_progress"
