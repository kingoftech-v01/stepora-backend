"""
TDD tests for get_next_checkin_days serializer method.

Logic:
- awaiting_user check-in exists → 0
- never done a check-in → 0
- last check-in >= 7 days ago → 0
- last check-in < 7 days ago → min(7_day_cooldown, celery_scheduled)

Run: DJANGO_SETTINGS_MODULE=config.settings.testing python -m pytest apps/dreams/tests/test_next_checkin_days.py -v
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from apps.users.models import User
from apps.dreams.models import Dream
from apps.plans.models import PlanCheckIn
from apps.dreams.serializers import DreamSerializer


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
    """Helper to get next_checkin_days from serializer."""
    from rest_framework.test import APIRequestFactory

    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = user
    s = DreamSerializer(dream, context={"request": request})
    return s.data.get("next_checkin_days")


# ============================================================
# Case 1: awaiting_user check-in exists → 0
# ============================================================
@pytest.mark.django_db
class TestAwaitingUser:
    def test_returns_0_when_checkin_awaiting_user(self, dream, user):
        PlanCheckIn.objects.create(
            dream=dream, status="awaiting_user", triggered_by="auto",
            scheduled_for=timezone.now(),
        )
        assert serialize_dream(dream, user) == 0

    def test_returns_0_even_if_last_completed_recent(self, dream, user):
        """Even if we did a check-in yesterday, if a new one is awaiting, return 0."""
        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            completed_at=timezone.now() - timedelta(days=1),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )
        PlanCheckIn.objects.create(
            dream=dream, status="awaiting_user", triggered_by="auto",
            scheduled_for=timezone.now(),
        )
        assert serialize_dream(dream, user) == 0


# ============================================================
# Case 2: never done a check-in → 0
# ============================================================
@pytest.mark.django_db
class TestNeverCheckedIn:
    def test_returns_0_no_checkins_ever(self, dream, user):
        assert serialize_dream(dream, user) == 0

    def test_returns_0_with_pending_checkin_not_completed(self, dream, user):
        """A check-in in 'pending' or 'generating' doesn't count as completed."""
        PlanCheckIn.objects.create(
            dream=dream, status="pending", triggered_by="auto",
            scheduled_for=timezone.now(),
        )
        assert serialize_dream(dream, user) == 0


# ============================================================
# Case 3: last check-in >= 7 days ago → 0
# ============================================================
@pytest.mark.django_db
class TestCheckinOverAWeekAgo:
    def test_returns_0_exactly_7_days_ago(self, dream, user):
        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            completed_at=timezone.now() - timedelta(days=7),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )
        assert serialize_dream(dream, user) == 0

    def test_returns_0_10_days_ago(self, dream, user):
        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            completed_at=timezone.now() - timedelta(days=10),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )
        assert serialize_dream(dream, user) == 0

    def test_returns_0_30_days_ago(self, dream, user):
        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            completed_at=timezone.now() - timedelta(days=30),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )
        assert serialize_dream(dream, user) == 0


# ============================================================
# Case 4: check-in done today → min(7_day_cooldown, celery)
# ============================================================
@pytest.mark.django_db
class TestCheckinToday:
    def test_cooldown_7_days_no_celery(self, dream, user):
        """Done today, no celery date → 7 days cooldown."""
        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            completed_at=timezone.now(),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )
        dream.next_checkin_at = None
        dream.save()
        result = serialize_dream(dream, user)
        assert result == 6 or result == 7  # 6 or 7 depending on time of day

    def test_cooldown_7_when_celery_21_days(self, dream, user):
        """Done today, celery in 21 days → min(7, 21) = 7."""
        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            completed_at=timezone.now(),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )
        dream.next_checkin_at = timezone.now() + timedelta(days=21)
        dream.save()
        result = serialize_dream(dream, user)
        assert result == 6 or result == 7  # 7 day cooldown wins

    def test_cooldown_7_when_celery_14_days(self, dream, user):
        """Done today, celery in 14 days → min(7, 14) = 7."""
        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            completed_at=timezone.now(),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )
        dream.next_checkin_at = timezone.now() + timedelta(days=14)
        dream.save()
        result = serialize_dream(dream, user)
        assert result == 6 or result == 7

    def test_cooldown_7_when_celery_3_days(self, dream, user):
        """Done today, celery in 3 days → min(7, 3) = 3... BUT 7 day minimum!

        Since we just did a check-in today, minimum is 7 days regardless.
        Celery at 3 days makes no sense (would violate 1/week rule).
        So result should be 7, not 3.

        BUT with min() logic and celery < cooldown, we take the cooldown (7).
        The cooldown IS 7 days, so min(7, 3) shouldn't apply here.
        The correct logic: if days_since_last < 7, the cooldown = 7 - days_since.
        Celery date only matters if it's AFTER the cooldown expires.
        """
        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            completed_at=timezone.now(),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )
        dream.next_checkin_at = timezone.now() + timedelta(days=3)
        dream.save()
        result = serialize_dream(dream, user)
        # Cooldown = 7 days. Celery = 3 days.
        # Celery is before cooldown expires → use cooldown (7)
        assert result == 6 or result == 7


# ============================================================
# Case 5: check-in done 5 days ago → cooldown remaining = 2 days
# ============================================================
@pytest.mark.django_db
class TestCheckin5DaysAgo:
    def test_2_days_remaining_no_celery(self, dream, user):
        """Done 5 days ago → 2 days remaining cooldown."""
        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            completed_at=timezone.now() - timedelta(days=5),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )
        dream.next_checkin_at = None
        dream.save()
        result = serialize_dream(dream, user)
        assert result == 1 or result == 2

    def test_2_days_remaining_celery_10_days(self, dream, user):
        """Done 5 days ago, celery in 10 days → min(2, 10) = 2."""
        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            completed_at=timezone.now() - timedelta(days=5),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )
        dream.next_checkin_at = timezone.now() + timedelta(days=10)
        dream.save()
        result = serialize_dream(dream, user)
        assert result == 1 or result == 2

    def test_2_days_remaining_celery_1_day(self, dream, user):
        """Done 5 days ago, celery tomorrow → min(2, 1) = 1.

        Celery is tomorrow which is before cooldown expires (2 days).
        But 1/week rule means cooldown minimum. So result = 2, not 1.
        """
        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            completed_at=timezone.now() - timedelta(days=5),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )
        dream.next_checkin_at = timezone.now() + timedelta(days=1)
        dream.save()
        result = serialize_dream(dream, user)
        # Cooldown = 2 days remaining. Celery = 1 day.
        # Celery before cooldown → use cooldown (2)
        assert result == 1 or result == 2


# ============================================================
# Case 6: check-in done 3 days ago → cooldown remaining = 4 days
# ============================================================
@pytest.mark.django_db
class TestCheckin3DaysAgo:
    def test_4_days_remaining_celery_2_days(self, dream, user):
        """Done 3 days ago, celery in 2 days → cooldown 4 wins over celery 2."""
        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            completed_at=timezone.now() - timedelta(days=3),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )
        dream.next_checkin_at = timezone.now() + timedelta(days=2)
        dream.save()
        result = serialize_dream(dream, user)
        assert result == 3 or result == 4

    def test_4_days_remaining_celery_6_days(self, dream, user):
        """Done 3 days ago, celery in 6 days → min(4, 6) = 4."""
        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            completed_at=timezone.now() - timedelta(days=3),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )
        dream.next_checkin_at = timezone.now() + timedelta(days=6)
        dream.save()
        result = serialize_dream(dream, user)
        assert result == 3 or result == 4


# ============================================================
# Case 7: multiple dreams independent
# ============================================================
@pytest.mark.django_db
class TestMultipleDreamsIndependent:
    def test_each_dream_has_own_cooldown(self, user):
        dream1 = Dream.objects.create(
            user=user, title="Dream 1", description="D1", category="career", plan_phase="partial"
        )
        dream2 = Dream.objects.create(
            user=user, title="Dream 2", description="D2", category="health", plan_phase="partial"
        )

        # Check-in on dream1 today
        PlanCheckIn.objects.create(
            dream=dream1,
            status="completed",
            completed_at=timezone.now(),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )

        # Dream1 should have cooldown, Dream2 should be available
        d1_days = serialize_dream(dream1, user)
        d2_days = serialize_dream(dream2, user)

        assert d1_days >= 6  # cooldown active
        assert d2_days == 0  # no check-in done, available


# ============================================================
# Case 8: edge case — check-in done 6 days ago
# ============================================================
@pytest.mark.django_db
class TestCheckin6DaysAgo:
    def test_1_day_remaining(self, dream, user):
        """Done 6 days ago → 1 day remaining."""
        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            completed_at=timezone.now() - timedelta(days=6),
            triggered_by="manual",
            scheduled_for=timezone.now(),
        )
        dream.next_checkin_at = None
        dream.save()
        result = serialize_dream(dream, user)
        assert result == 0 or result == 1
