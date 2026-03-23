"""
TDD tests for can_checkin + days_until_checkin serializer methods.

Logic:
- pending check-in exists (awaiting_user) -> can_checkin=False, days=0 (finish this one first)
- in-progress check-in (pending/generating/processing) -> can_checkin=False, days=0
- never done a check-in -> can_checkin=True, days=0
- last_checkin_at >= 7 days ago -> can_checkin=True, days=0
- last_checkin_at < 7 days ago -> can_checkin=False, days=7-days_since
- no plan (plan_phase not partial/full) -> can_checkin=False

Run: DJANGO_SETTINGS_MODULE=config.settings.testing python -m pytest apps/dreams/tests/test_next_checkin_days.py -v
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.dreams.models import Dream
from apps.dreams.serializers import DreamSerializer
from apps.plans.models import PlanCheckIn
from apps.users.models import User


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="checkin-test@test.com", password="testpass123", display_name="Test"
    )


@pytest.fixture
def dream(user):
    return Dream.objects.create(
        user=user,
        title="Test Dream",
        description="Test",
        category="career",
        plan_phase="partial",
    )


def serialize_dream(dream, user):
    """Helper to get can_checkin and days_until_checkin from serializer."""
    from rest_framework.test import APIRequestFactory

    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = user
    s = DreamSerializer(dream, context={"request": request})
    return s.data.get("can_checkin"), s.data.get("days_until_checkin")


# ============================================================
# Case 1: awaiting_user check-in exists -> can_checkin=False, days=0
# ============================================================
@pytest.mark.django_db
class TestAwaitingUser:
    def test_cannot_checkin_when_awaiting_user(self, dream, user):
        PlanCheckIn.objects.create(
            dream=dream,
            status="awaiting_user",
            triggered_by="auto",
            scheduled_for=timezone.now(),
        )
        can, days = serialize_dream(dream, user)
        assert can is False
        assert days == 0

    def test_cannot_checkin_even_if_last_completed_old(self, dream, user):
        """Even if last check-in was 30 days ago, if awaiting_user exists, can't trigger new."""
        dream.last_checkin_at = timezone.now() - timedelta(days=30)
        dream.save(update_fields=["last_checkin_at"])
        PlanCheckIn.objects.create(
            dream=dream,
            status="awaiting_user",
            triggered_by="auto",
            scheduled_for=timezone.now(),
        )
        can, days = serialize_dream(dream, user)
        assert can is False
        assert days == 0


# ============================================================
# Case 2: in-progress check-in (pending/generating/processing)
# ============================================================
@pytest.mark.django_db
class TestInProgressCheckin:
    def test_cannot_checkin_when_pending(self, dream, user):
        PlanCheckIn.objects.create(
            dream=dream,
            status="pending",
            triggered_by="auto",
            scheduled_for=timezone.now(),
        )
        can, days = serialize_dream(dream, user)
        assert can is False

    def test_cannot_checkin_when_questionnaire_generating(self, dream, user):
        PlanCheckIn.objects.create(
            dream=dream,
            status="questionnaire_generating",
            triggered_by="auto",
            scheduled_for=timezone.now(),
        )
        can, days = serialize_dream(dream, user)
        assert can is False

    def test_cannot_checkin_when_ai_processing(self, dream, user):
        PlanCheckIn.objects.create(
            dream=dream,
            status="ai_processing",
            triggered_by="auto",
            scheduled_for=timezone.now(),
        )
        can, days = serialize_dream(dream, user)
        assert can is False


# ============================================================
# Case 3: never done a check-in -> can_checkin=True, days=0
# ============================================================
@pytest.mark.django_db
class TestNeverCheckedIn:
    def test_can_checkin_no_checkins_ever(self, dream, user):
        can, days = serialize_dream(dream, user)
        assert can is True
        assert days == 0

    def test_can_checkin_with_only_failed_checkin(self, dream, user):
        """A failed check-in doesn't block; last_checkin_at stays None."""
        PlanCheckIn.objects.create(
            dream=dream,
            status="failed",
            triggered_by="auto",
            scheduled_for=timezone.now(),
        )
        can, days = serialize_dream(dream, user)
        assert can is True
        assert days == 0


# ============================================================
# Case 4: last check-in >= 7 days ago -> can_checkin=True, days=0
# ============================================================
@pytest.mark.django_db
class TestCheckinOverAWeekAgo:
    def test_can_checkin_exactly_7_days_ago(self, dream, user):
        dream.last_checkin_at = timezone.now() - timedelta(days=7)
        dream.save(update_fields=["last_checkin_at"])
        can, days = serialize_dream(dream, user)
        assert can is True
        assert days == 0

    def test_can_checkin_10_days_ago(self, dream, user):
        dream.last_checkin_at = timezone.now() - timedelta(days=10)
        dream.save(update_fields=["last_checkin_at"])
        can, days = serialize_dream(dream, user)
        assert can is True
        assert days == 0

    def test_can_checkin_30_days_ago(self, dream, user):
        dream.last_checkin_at = timezone.now() - timedelta(days=30)
        dream.save(update_fields=["last_checkin_at"])
        can, days = serialize_dream(dream, user)
        assert can is True
        assert days == 0


# ============================================================
# Case 5: check-in done today -> can_checkin=False, days ~= 7
# ============================================================
@pytest.mark.django_db
class TestCheckinToday:
    def test_cannot_checkin_done_today(self, dream, user):
        dream.last_checkin_at = timezone.now()
        dream.save(update_fields=["last_checkin_at"])
        can, days = serialize_dream(dream, user)
        assert can is False
        assert days == 6 or days == 7  # depends on time-of-day rounding


# ============================================================
# Case 6: check-in done 5 days ago -> can_checkin=False, days=2
# ============================================================
@pytest.mark.django_db
class TestCheckin5DaysAgo:
    def test_cannot_checkin_2_days_remaining(self, dream, user):
        dream.last_checkin_at = timezone.now() - timedelta(days=5)
        dream.save(update_fields=["last_checkin_at"])
        can, days = serialize_dream(dream, user)
        assert can is False
        assert days == 1 or days == 2  # depends on time-of-day rounding


# ============================================================
# Case 7: check-in done 3 days ago -> can_checkin=False, days=4
# ============================================================
@pytest.mark.django_db
class TestCheckin3DaysAgo:
    def test_cannot_checkin_4_days_remaining(self, dream, user):
        dream.last_checkin_at = timezone.now() - timedelta(days=3)
        dream.save(update_fields=["last_checkin_at"])
        can, days = serialize_dream(dream, user)
        assert can is False
        assert days == 3 or days == 4  # depends on time-of-day rounding


# ============================================================
# Case 8: check-in done 6 days ago -> can_checkin=False, days=1
# ============================================================
@pytest.mark.django_db
class TestCheckin6DaysAgo:
    def test_cannot_checkin_1_day_remaining(self, dream, user):
        dream.last_checkin_at = timezone.now() - timedelta(days=6)
        dream.save(update_fields=["last_checkin_at"])
        can, days = serialize_dream(dream, user)
        assert can is False
        assert days == 0 or days == 1  # depends on time-of-day rounding


# ============================================================
# Case 9: multiple dreams independent
# ============================================================
@pytest.mark.django_db
class TestMultipleDreamsIndependent:
    def test_each_dream_has_own_cooldown(self, user):
        dream1 = Dream.objects.create(
            user=user,
            title="Dream 1",
            description="D1",
            category="career",
            plan_phase="partial",
        )
        dream2 = Dream.objects.create(
            user=user,
            title="Dream 2",
            description="D2",
            category="health",
            plan_phase="partial",
        )

        # Check-in on dream1 today
        dream1.last_checkin_at = timezone.now()
        dream1.save(update_fields=["last_checkin_at"])

        can1, days1 = serialize_dream(dream1, user)
        can2, days2 = serialize_dream(dream2, user)

        assert can1 is False
        assert days1 >= 6  # cooldown active
        assert can2 is True
        assert days2 == 0  # no check-in done, available


# ============================================================
# Case 10: no plan -> can_checkin=False
# ============================================================
@pytest.mark.django_db
class TestNoPlan:
    def test_cannot_checkin_without_plan(self, user):
        dream = Dream.objects.create(
            user=user,
            title="No Plan Dream",
            description="NP",
            category="career",
            plan_phase="none",
        )
        can, days = serialize_dream(dream, user)
        assert can is False
