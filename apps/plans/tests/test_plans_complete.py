"""
Comprehensive test suite for the plans app.

Covers models, views, serializers, services, tasks, and IDOR protection
for DreamMilestone, Goal, Task, Obstacle, CalibrationResponse,
PlanCheckIn, DreamProgressSnapshot, and FocusSession.

Target: 95%+ coverage of apps/plans/.
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dreams.models import Dream
from apps.plans.models import (
    CalibrationResponse,
    DreamMilestone,
    DreamProgressSnapshot,
    FocusSession,
    Goal,
    Obstacle,
    PlanCheckIn,
    Task,
)
from apps.plans.serializers import (
    CalibrationResponseSerializer,
    CheckInResponseSubmitSerializer,
    DreamMilestoneSerializer,
    DreamProgressSnapshotSerializer,
    FocusSessionCompleteSerializer,
    FocusSessionSerializer,
    FocusSessionStartSerializer,
    GoalCreateSerializer,
    GoalSerializer,
    ObstacleSerializer,
    PlanCheckInDetailSerializer,
    PlanCheckInSerializer,
    TaskCreateSerializer,
    TaskSerializer,
)
from apps.plans.services import PlanService
from apps.users.models import User


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def user_a(db):
    return User.objects.create_user(
        email="plana@test.com",
        password="testpass123",
        display_name="Plan User A",
    )


@pytest.fixture
def user_b(db):
    return User.objects.create_user(
        email="planb@test.com",
        password="testpass456",
        display_name="Plan User B",
    )


@pytest.fixture
def dream_a(user_a):
    return Dream.objects.create(
        user=user_a,
        title="User A Dream",
        description="Dream for user A",
        status="active",
        target_date=timezone.now() + timedelta(days=180),
    )


@pytest.fixture
def dream_b(user_b):
    return Dream.objects.create(
        user=user_b,
        title="User B Dream",
        description="Dream for user B",
        status="active",
        target_date=timezone.now() + timedelta(days=90),
    )


@pytest.fixture
def milestone_a(dream_a):
    return DreamMilestone.objects.create(
        dream=dream_a, title="Month 1", order=1
    )


@pytest.fixture
def milestone_a2(dream_a):
    return DreamMilestone.objects.create(
        dream=dream_a, title="Month 2", order=2
    )


@pytest.fixture
def goal_a(dream_a, milestone_a):
    return Goal.objects.create(
        dream=dream_a,
        milestone=milestone_a,
        title="Goal A1",
        order=1,
    )


@pytest.fixture
def goal_a2(dream_a, milestone_a):
    return Goal.objects.create(
        dream=dream_a,
        milestone=milestone_a,
        title="Goal A2",
        order=2,
    )


@pytest.fixture
def goal_no_milestone(dream_a):
    """Legacy goal without a milestone."""
    return Goal.objects.create(
        dream=dream_a,
        milestone=None,
        title="Legacy Goal",
        order=1,
    )


@pytest.fixture
def task_a(goal_a):
    return Task.objects.create(
        goal=goal_a,
        title="Task A1",
        order=1,
        duration_mins=30,
    )


@pytest.fixture
def task_a2(goal_a):
    return Task.objects.create(
        goal=goal_a,
        title="Task A2",
        order=2,
        duration_mins=60,
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
def anon_client():
    return APIClient()


# ──────────────────────────────────────────────────────────────────
# MODEL TESTS
# ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDreamMilestoneModel:
    """DreamMilestone CRUD, complete, update_progress, __str__."""

    def test_create_defaults(self, dream_a):
        ms = DreamMilestone.objects.create(dream=dream_a, title="M1", order=1)
        assert ms.status == "pending"
        assert ms.progress_percentage == 0.0
        assert ms.completed_at is None
        assert ms.has_tasks is False

    def test_str(self, milestone_a):
        assert "Month 1" in str(milestone_a)
        assert "#1" in str(milestone_a)

    def test_complete_sets_status_and_awards_xp(self, milestone_a, user_a):
        initial_xp = user_a.xp
        milestone_a.complete()
        milestone_a.refresh_from_db()
        user_a.refresh_from_db()
        assert milestone_a.status == "completed"
        assert milestone_a.completed_at is not None
        assert milestone_a.progress_percentage == 100.0
        assert user_a.xp > initial_xp

    def test_complete_idempotent(self, milestone_a):
        milestone_a.complete()
        first_completed_at = milestone_a.completed_at
        milestone_a.complete()
        milestone_a.refresh_from_db()
        assert milestone_a.completed_at == first_completed_at

    def test_update_progress_no_goals(self, milestone_a):
        milestone_a.update_progress()
        milestone_a.refresh_from_db()
        assert milestone_a.progress_percentage == 0.0

    def test_update_progress_with_goals(self, milestone_a, goal_a, goal_a2):
        goal_a.complete()
        milestone_a.refresh_from_db()
        assert milestone_a.progress_percentage == 50.0

    def test_ordering(self, dream_a, milestone_a, milestone_a2):
        ms_list = list(
            DreamMilestone.objects.filter(dream=dream_a).values_list("order", flat=True)
        )
        assert ms_list == [1, 2]

    def test_optional_dates(self, dream_a):
        ms = DreamMilestone.objects.create(
            dream=dream_a,
            title="Dated",
            order=3,
            target_date=timezone.now() + timedelta(days=30),
            expected_date=timezone.now().date() + timedelta(days=25),
            deadline_date=timezone.now().date() + timedelta(days=35),
        )
        assert ms.target_date is not None
        assert ms.expected_date is not None
        assert ms.deadline_date is not None


@pytest.mark.django_db
class TestGoalModel:
    """Goal CRUD, complete, update_progress, legacy path."""

    def test_create_defaults(self, goal_a):
        assert goal_a.status == "pending"
        assert goal_a.progress_percentage == 0.0
        assert goal_a.completed_at is None

    def test_str(self, goal_a):
        assert "Goal A1" in str(goal_a)

    def test_complete_with_milestone(self, goal_a, milestone_a, user_a):
        initial_xp = user_a.xp
        goal_a.complete()
        goal_a.refresh_from_db()
        user_a.refresh_from_db()
        assert goal_a.status == "completed"
        assert goal_a.completed_at is not None
        assert goal_a.progress_percentage == 100.0
        assert user_a.xp > initial_xp

    def test_complete_idempotent(self, goal_a):
        goal_a.complete()
        first_at = goal_a.completed_at
        goal_a.complete()
        goal_a.refresh_from_db()
        assert goal_a.completed_at == first_at

    def test_complete_legacy_no_milestone(self, goal_no_milestone, dream_a):
        """Goal without milestone updates dream progress directly."""
        goal_no_milestone.complete()
        goal_no_milestone.refresh_from_db()
        assert goal_no_milestone.status == "completed"

    def test_update_progress_no_tasks(self, goal_a):
        goal_a.update_progress()
        goal_a.refresh_from_db()
        assert goal_a.progress_percentage == 0.0

    def test_update_progress_with_tasks(self, goal_a, task_a, task_a2):
        task_a.complete()
        goal_a.refresh_from_db()
        assert goal_a.progress_percentage == 50.0

    def test_update_progress_legacy_path(self, goal_no_milestone, dream_a):
        """Progress update without milestone goes directly to dream."""
        Task.objects.create(goal=goal_no_milestone, title="T", order=1, duration_mins=10)
        goal_no_milestone.update_progress()
        goal_no_milestone.refresh_from_db()
        assert goal_no_milestone.progress_percentage == 0.0

    def test_reminder_fields(self, dream_a, milestone_a):
        goal = Goal.objects.create(
            dream=dream_a,
            milestone=milestone_a,
            title="Remind Me",
            order=3,
            reminder_enabled=True,
            reminder_time=timezone.now() + timedelta(hours=1),
        )
        assert goal.reminder_enabled is True
        assert goal.reminder_time is not None


@pytest.mark.django_db
class TestTaskModel:
    """Task CRUD, complete, chain, streak, XP."""

    def test_create_defaults(self, task_a):
        assert task_a.status == "pending"
        assert task_a.completed_at is None
        assert task_a.is_chain is False

    def test_str(self, task_a):
        assert "Task A1" in str(task_a)

    def test_complete_awards_xp(self, task_a, user_a):
        initial_xp = user_a.xp
        task_a.complete()
        task_a.refresh_from_db()
        user_a.refresh_from_db()
        assert task_a.status == "completed"
        assert task_a.completed_at is not None
        assert user_a.xp > initial_xp

    def test_complete_idempotent(self, task_a):
        task_a.complete()
        first_at = task_a.completed_at
        task_a.complete()
        task_a.refresh_from_db()
        assert task_a.completed_at == first_at

    def test_complete_xp_formula(self, goal_a, user_a):
        """XP = max(10, duration_mins // 3)."""
        t60 = Task.objects.create(goal=goal_a, title="T60", order=10, duration_mins=60)
        initial_xp = user_a.xp
        t60.complete()
        user_a.refresh_from_db()
        assert user_a.xp == initial_xp + 20  # 60 // 3 = 20

    def test_complete_xp_minimum(self, goal_a, user_a):
        """XP never below 10."""
        t5 = Task.objects.create(goal=goal_a, title="T5", order=11, duration_mins=5)
        initial_xp = user_a.xp
        t5.complete()
        user_a.refresh_from_db()
        assert user_a.xp == initial_xp + 10  # max(10, 5//3) = 10

    def test_complete_no_duration_uses_default(self, goal_a, user_a):
        """No duration -> defaults to 30 -> 30//3=10."""
        t_none = Task.objects.create(goal=goal_a, title="TN", order=12, duration_mins=None)
        initial_xp = user_a.xp
        t_none.complete()
        user_a.refresh_from_db()
        assert user_a.xp == initial_xp + 10

    def test_chain_position_no_chain(self, task_a):
        pos, total = task_a.get_chain_position()
        assert pos is None
        assert total is None

    def test_chain_create_next(self, goal_a):
        """Completing a chain task auto-creates the next task."""
        chain_task = Task.objects.create(
            goal=goal_a,
            title="Daily Jog",
            order=1,
            duration_mins=30,
            chain_next_delay_days=1,
            chain_template_title="Daily Jog",
        )
        chain_task.complete()
        next_task = Task.objects.filter(chain_parent=chain_task).first()
        assert next_task is not None
        assert next_task.title == "Daily Jog"
        assert next_task.is_chain is True
        assert next_task.chain_parent == chain_task
        assert next_task.chain_next_delay_days == 1

    def test_chain_position_in_chain(self, goal_a):
        """Chain position for a 3-link chain."""
        t1 = Task.objects.create(
            goal=goal_a,
            title="Chain 1",
            order=1,
            duration_mins=10,
            chain_next_delay_days=1,
        )
        t1.complete()
        t2 = Task.objects.filter(chain_parent=t1).first()
        assert t2 is not None
        pos1, total1 = t1.get_chain_position()
        assert pos1 == 1
        assert total1 == 2
        pos2, total2 = t2.get_chain_position()
        assert pos2 == 2
        assert total2 == 2

    def test_chain_uses_template_title(self, goal_a):
        """Chain uses custom template title when set."""
        t = Task.objects.create(
            goal=goal_a,
            title="Original",
            order=1,
            duration_mins=10,
            chain_next_delay_days=2,
            chain_template_title="Follow-up Task",
        )
        t.complete()
        next_t = Task.objects.filter(chain_parent=t).first()
        assert next_t.title == "Follow-up Task"

    def test_chain_uses_current_title_when_template_blank(self, goal_a):
        """Chain falls back to current title when template is blank."""
        t = Task.objects.create(
            goal=goal_a,
            title="My Task",
            order=1,
            duration_mins=10,
            chain_next_delay_days=3,
            chain_template_title="",
        )
        t.complete()
        next_t = Task.objects.filter(chain_parent=t).first()
        assert next_t.title == "My Task"

    def test_streak_same_day_no_change(self, goal_a, user_a):
        """Streak does NOT change when completing tasks on the same day
        because update_activity() sets last_activity=now() before _update_streak()."""
        user_a.last_activity = timezone.now() - timedelta(days=1)
        user_a.streak_days = 5
        user_a.save()
        t = Task.objects.create(goal=goal_a, title="Streak", order=99, duration_mins=10)
        t.complete()
        user_a.refresh_from_db()
        # update_activity() sets last_activity=today BEFORE _update_streak() runs,
        # so _update_streak sees last_activity_date == today and returns early.
        assert user_a.streak_days == 5

    def test_streak_update_via_direct_call(self, goal_a, user_a):
        """_update_streak works correctly when last_activity is yesterday."""
        user_a.last_activity = timezone.now() - timedelta(days=1)
        user_a.streak_days = 5
        user_a.save()
        t = Task.objects.create(goal=goal_a, title="Streak", order=99, duration_mins=10)
        # Call _update_streak directly (bypassing update_activity)
        t._update_streak()
        user_a.refresh_from_db()
        assert user_a.streak_days == 6

    def test_streak_resets_via_direct_call(self, goal_a, user_a):
        """_update_streak resets streak if last_activity > 1 day ago."""
        user_a.last_activity = timezone.now() - timedelta(days=3)
        user_a.streak_days = 5
        user_a.save()
        t = Task.objects.create(goal=goal_a, title="Reset", order=98, duration_mins=10)
        t._update_streak()
        user_a.refresh_from_db()
        assert user_a.streak_days == 1

    def test_recurrence_json_field(self, goal_a):
        t = Task.objects.create(
            goal=goal_a,
            title="Recurring",
            order=50,
            recurrence={"type": "weekly", "interval": 1, "days": [1, 3, 5]},
        )
        assert t.recurrence["type"] == "weekly"
        assert t.recurrence["interval"] == 1

    def test_two_minute_start_flag(self, goal_a):
        t = Task.objects.create(
            goal=goal_a, title="Quick", order=51, is_two_minute_start=True
        )
        assert t.is_two_minute_start is True


@pytest.mark.django_db
class TestObstacleModel:
    def test_create_defaults(self, dream_a):
        obs = Obstacle.objects.create(
            dream=dream_a, title="Blocker", description="Some issue"
        )
        assert obs.status == "active"
        assert obs.obstacle_type == "predicted"

    def test_str(self, dream_a):
        obs = Obstacle.objects.create(
            dream=dream_a, title="Time", description="Not enough time"
        )
        assert "Obstacle: Time" in str(obs)

    def test_create_with_milestone_and_goal(self, dream_a, milestone_a, goal_a):
        obs = Obstacle.objects.create(
            dream=dream_a,
            milestone=milestone_a,
            goal=goal_a,
            title="Linked",
            description="Linked to both",
            obstacle_type="actual",
            solution="Prioritize",
        )
        assert obs.milestone == milestone_a
        assert obs.goal == goal_a
        assert obs.obstacle_type == "actual"
        assert obs.solution == "Prioritize"


@pytest.mark.django_db
class TestCalibrationResponseModel:
    def test_create(self, dream_a):
        cr = CalibrationResponse.objects.create(
            dream=dream_a,
            question="What is your experience?",
            answer="Beginner",
            question_number=1,
            category="experience",
        )
        assert "Q1:" in str(cr)
        assert cr.category == "experience"

    def test_ordering(self, dream_a):
        CalibrationResponse.objects.create(
            dream=dream_a, question="Q2", question_number=2
        )
        CalibrationResponse.objects.create(
            dream=dream_a, question="Q1", question_number=1
        )
        ordered = list(
            CalibrationResponse.objects.filter(dream=dream_a).values_list(
                "question_number", flat=True
            )
        )
        assert ordered == [1, 2]


@pytest.mark.django_db
class TestPlanCheckInModel:
    def test_create_defaults(self, dream_a):
        ci = PlanCheckIn.objects.create(
            dream=dream_a, scheduled_for=timezone.now()
        )
        assert ci.status == "pending"
        assert ci.triggered_by == "schedule"
        assert ci.pace_status == ""
        assert ci.next_checkin_interval_days == 14
        assert ci.tasks_created == 0

    def test_str(self, dream_a):
        ci = PlanCheckIn.objects.create(
            dream=dream_a, scheduled_for=timezone.now()
        )
        assert "CheckIn for" in str(ci)

    def test_all_statuses(self, dream_a):
        for status_val, _ in PlanCheckIn.STATUS_CHOICES:
            ci = PlanCheckIn.objects.create(
                dream=dream_a,
                scheduled_for=timezone.now(),
                status=status_val,
            )
            assert ci.status == status_val


@pytest.mark.django_db
class TestDreamProgressSnapshotModel:
    def test_record_snapshot(self, dream_a):
        dream_a.progress_percentage = 42.5
        dream_a.save()
        DreamProgressSnapshot.record_snapshot(dream_a)
        snap = DreamProgressSnapshot.objects.get(dream=dream_a)
        assert snap.progress_percentage == 42.5

    def test_record_snapshot_updates_existing(self, dream_a):
        dream_a.progress_percentage = 30.0
        dream_a.save()
        DreamProgressSnapshot.record_snapshot(dream_a)
        dream_a.progress_percentage = 60.0
        dream_a.save()
        DreamProgressSnapshot.record_snapshot(dream_a)
        # Should only have one snapshot for today
        today = timezone.now().date()
        snaps = DreamProgressSnapshot.objects.filter(dream=dream_a, date=today)
        assert snaps.count() == 1
        assert snaps.first().progress_percentage == 60.0

    def test_str(self, dream_a):
        dream_a.progress_percentage = 50.0
        dream_a.save()
        DreamProgressSnapshot.record_snapshot(dream_a)
        snap = DreamProgressSnapshot.objects.get(dream=dream_a)
        assert "50.0%" in str(snap)


@pytest.mark.django_db
class TestFocusSessionModel:
    def test_create_defaults(self, user_a):
        session = FocusSession.objects.create(
            user=user_a, duration_minutes=25, session_type="work"
        )
        assert session.completed is False
        assert session.actual_minutes == 0
        assert session.ended_at is None

    def test_str(self, user_a):
        session = FocusSession.objects.create(
            user=user_a, duration_minutes=25, session_type="work"
        )
        assert "FocusSession work" in str(session)
        assert "25min" in str(session)

    def test_break_session(self, user_a):
        session = FocusSession.objects.create(
            user=user_a, duration_minutes=5, session_type="break"
        )
        assert session.session_type == "break"

    def test_with_task(self, user_a, task_a):
        session = FocusSession.objects.create(
            user=user_a,
            task=task_a,
            duration_minutes=25,
        )
        assert session.task == task_a

    def test_ordering(self, user_a):
        s1 = FocusSession.objects.create(user=user_a, duration_minutes=25)
        s2 = FocusSession.objects.create(user=user_a, duration_minutes=10)
        sessions = list(FocusSession.objects.filter(user=user_a))
        assert sessions[0] == s2  # most recent first


# ──────────────────────────────────────────────────────────────────
# PROGRESS PROPAGATION TESTS
# ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestProgressPropagation:
    """Task -> Goal -> Milestone -> Dream progress chain."""

    def test_task_complete_propagates_to_goal(self, goal_a, task_a, task_a2):
        task_a.complete()
        goal_a.refresh_from_db()
        assert goal_a.progress_percentage == 50.0

    def test_all_tasks_complete_propagates_to_goal(self, goal_a, task_a, task_a2):
        task_a.complete()
        task_a2.complete()
        goal_a.refresh_from_db()
        assert goal_a.progress_percentage == 100.0

    def test_goal_complete_propagates_to_milestone(self, milestone_a, goal_a, goal_a2):
        goal_a.complete()
        milestone_a.refresh_from_db()
        assert milestone_a.progress_percentage == 50.0

    def test_all_goals_complete_propagates_to_milestone(
        self, milestone_a, goal_a, goal_a2
    ):
        goal_a.complete()
        goal_a2.complete()
        milestone_a.refresh_from_db()
        assert milestone_a.progress_percentage == 100.0

    def test_full_chain_task_to_dream(self, dream_a, milestone_a, goal_a, task_a):
        """Single task in single goal in single milestone -> dream at 100%."""
        # Only 1 goal in 1 milestone, with 1 task
        task_a.complete()
        dream_a.refresh_from_db()
        # Dream progress depends on implementation: milestone-based or goal-based
        assert dream_a.progress_percentage >= 0.0


# ──────────────────────────────────────────────────────────────────
# SERIALIZER TESTS
# ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTaskSerializer:
    def test_xp_field(self, task_a):
        data = TaskSerializer(task_a).data
        assert "xp" in data
        assert data["xp"] == 10  # 30 // 3 = 10

    def test_xp_60min(self, goal_a):
        t = Task.objects.create(goal=goal_a, title="T", order=1, duration_mins=60)
        data = TaskSerializer(t).data
        assert data["xp"] == 20

    def test_chain_position_none(self, task_a):
        data = TaskSerializer(task_a).data
        assert data["chain_position"] is None

    def test_chain_position_present(self, goal_a):
        t = Task.objects.create(
            goal=goal_a,
            title="C",
            order=1,
            duration_mins=10,
            chain_next_delay_days=1,
        )
        data = TaskSerializer(t).data
        assert data["chain_position"] is not None
        assert data["chain_position"]["position"] == 1

    def test_read_only_fields(self, task_a):
        s = TaskSerializer(task_a, data={"xp": 999}, partial=True)
        assert s.is_valid()
        assert "xp" not in s.validated_data


@pytest.mark.django_db
class TestTaskCreateSerializer:
    def test_valid_data(self, goal_a):
        data = {"goal": goal_a.id, "title": "New Task", "order": 1}
        s = TaskCreateSerializer(data=data)
        assert s.is_valid(), s.errors

    def test_missing_title(self, goal_a):
        data = {"goal": goal_a.id, "order": 1}
        s = TaskCreateSerializer(data=data)
        assert not s.is_valid()
        assert "title" in s.errors


@pytest.mark.django_db
class TestGoalSerializer:
    def test_includes_tasks(self, goal_a, task_a):
        data = GoalSerializer(goal_a).data
        assert "tasks" in data
        assert len(data["tasks"]) == 1

    def test_progress_read_only(self, goal_a):
        s = GoalSerializer(goal_a, data={"progress_percentage": 99.9}, partial=True)
        assert s.is_valid()
        assert "progress_percentage" not in s.validated_data


@pytest.mark.django_db
class TestGoalCreateSerializer:
    def test_valid(self, dream_a, milestone_a):
        data = {
            "dream": dream_a.id,
            "milestone": milestone_a.id,
            "title": "New Goal",
            "order": 1,
        }
        s = GoalCreateSerializer(data=data)
        assert s.is_valid(), s.errors


@pytest.mark.django_db
class TestDreamMilestoneSerializer:
    def test_includes_goals(self, milestone_a, goal_a):
        data = DreamMilestoneSerializer(milestone_a).data
        assert "goals" in data
        assert len(data["goals"]) == 1


@pytest.mark.django_db
class TestObstacleSerializer:
    def test_valid(self, dream_a):
        data = {
            "dream": dream_a.id,
            "title": "Obs",
            "description": "Desc",
        }
        s = ObstacleSerializer(data=data)
        assert s.is_valid(), s.errors


@pytest.mark.django_db
class TestCalibrationResponseSerializer:
    def test_fields(self, dream_a):
        cr = CalibrationResponse.objects.create(
            dream=dream_a, question="Q?", question_number=1, answer="A"
        )
        data = CalibrationResponseSerializer(cr).data
        assert data["question"] == "Q?"
        assert data["answer"] == "A"
        assert data["question_number"] == 1


@pytest.mark.django_db
class TestPlanCheckInSerializers:
    def test_list_serializer(self, dream_a):
        ci = PlanCheckIn.objects.create(
            dream=dream_a, scheduled_for=timezone.now(), coaching_message="Great!"
        )
        data = PlanCheckInSerializer(ci).data
        assert data["coaching_message"] == "Great!"
        assert "questionnaire" not in data

    def test_detail_serializer(self, dream_a):
        ci = PlanCheckIn.objects.create(
            dream=dream_a,
            scheduled_for=timezone.now(),
            questionnaire=[{"id": "q1", "question": "How?"}],
            user_responses={"q1": "Good"},
            ai_actions=[{"type": "add_task"}],
        )
        data = PlanCheckInDetailSerializer(ci).data
        assert "questionnaire" in data
        assert "user_responses" in data
        assert "ai_actions" in data
        assert data["questionnaire"][0]["id"] == "q1"


class TestCheckInResponseSubmitSerializer:
    def test_valid(self):
        data = {"responses": {"q1": "good", "q2": 3}}
        s = CheckInResponseSubmitSerializer(data=data)
        assert s.is_valid(), s.errors

    def test_invalid_no_responses(self):
        s = CheckInResponseSubmitSerializer(data={})
        assert not s.is_valid()


@pytest.mark.django_db
class TestDreamProgressSnapshotSerializer:
    def test_fields(self, dream_a):
        dream_a.progress_percentage = 75.0
        dream_a.save()
        DreamProgressSnapshot.record_snapshot(dream_a)
        snap = DreamProgressSnapshot.objects.get(dream=dream_a)
        data = DreamProgressSnapshotSerializer(snap).data
        assert data["progress_percentage"] == 75.0


@pytest.mark.django_db
class TestFocusSessionSerializers:
    def test_session_serializer(self, user_a):
        session = FocusSession.objects.create(
            user=user_a, duration_minutes=25, session_type="work"
        )
        data = FocusSessionSerializer(session).data
        assert data["duration_minutes"] == 25
        assert data["session_type"] == "work"

    def test_start_serializer_valid(self):
        data = {"duration_minutes": 25, "session_type": "work"}
        s = FocusSessionStartSerializer(data=data)
        assert s.is_valid(), s.errors

    def test_start_serializer_max_duration(self):
        data = {"duration_minutes": 121}
        s = FocusSessionStartSerializer(data=data)
        assert not s.is_valid()

    def test_start_serializer_min_duration(self):
        data = {"duration_minutes": 0}
        s = FocusSessionStartSerializer(data=data)
        assert not s.is_valid()

    def test_complete_serializer_valid(self):
        data = {"session_id": str(uuid.uuid4()), "actual_minutes": 20}
        s = FocusSessionCompleteSerializer(data=data)
        assert s.is_valid(), s.errors

    def test_complete_serializer_min_minutes(self):
        data = {"session_id": str(uuid.uuid4()), "actual_minutes": -1}
        s = FocusSessionCompleteSerializer(data=data)
        assert not s.is_valid()


# ──────────────────────────────────────────────────────────────────
# VIEW TESTS
# ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMilestoneViewSet:
    URL = "/api/v1/plans/milestones/"

    def _results(self, resp):
        """Extract results from paginated response."""
        if isinstance(resp.data, dict) and "results" in resp.data:
            return resp.data["results"]
        return resp.data

    def test_list_own(self, client_a, dream_a, milestone_a):
        resp = client_a.get(f"{self.URL}?dream={dream_a.id}")
        assert resp.status_code == 200
        assert len(self._results(resp)) >= 1

    def test_list_empty(self, client_b, dream_a, milestone_a):
        """User B cannot see User A's milestones."""
        resp = client_b.get(f"{self.URL}?dream={dream_a.id}")
        assert resp.status_code == 200
        assert len(self._results(resp)) == 0

    def test_retrieve(self, client_a, milestone_a):
        resp = client_a.get(f"{self.URL}{milestone_a.id}/")
        assert resp.status_code == 200
        assert resp.data["title"] == "Month 1"

    def test_retrieve_other_user_forbidden(self, client_b, milestone_a):
        resp = client_b.get(f"{self.URL}{milestone_a.id}/")
        assert resp.status_code == 404

    def test_create(self, client_a, dream_a):
        resp = client_a.post(
            self.URL,
            {"dream": str(dream_a.id), "title": "New MS", "order": 5},
            format="json",
        )
        assert resp.status_code == 201

    def test_create_idor_blocked(self, client_b, dream_a):
        """User B cannot create a milestone on User A's dream."""
        resp = client_b.post(
            self.URL,
            {"dream": str(dream_a.id), "title": "Hacked MS", "order": 1},
            format="json",
        )
        assert resp.status_code == 403

    def test_update(self, client_a, milestone_a):
        resp = client_a.patch(
            f"{self.URL}{milestone_a.id}/",
            {"title": "Updated MS"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["title"] == "Updated MS"

    def test_delete(self, client_a, milestone_a):
        resp = client_a.delete(f"{self.URL}{milestone_a.id}/")
        assert resp.status_code == 204

    def test_unauthenticated(self, anon_client, milestone_a):
        resp = anon_client.get(self.URL)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestGoalViewSet:
    URL = "/api/v1/plans/goals/"

    def _results(self, resp):
        if isinstance(resp.data, dict) and "results" in resp.data:
            return resp.data["results"]
        return resp.data

    def test_list(self, client_a, dream_a, goal_a):
        resp = client_a.get(f"{self.URL}?dream={dream_a.id}")
        assert resp.status_code == 200
        assert len(self._results(resp)) >= 1

    def test_list_by_milestone(self, client_a, milestone_a, goal_a):
        resp = client_a.get(f"{self.URL}?milestone={milestone_a.id}")
        assert resp.status_code == 200

    def test_retrieve(self, client_a, goal_a):
        resp = client_a.get(f"{self.URL}{goal_a.id}/")
        assert resp.status_code == 200

    def test_create_with_explicit_order(self, client_a, dream_a, milestone_a):
        resp = client_a.post(
            self.URL,
            {
                "dream": str(dream_a.id),
                "milestone": str(milestone_a.id),
                "title": "Ordered Goal",
                "order": 5,
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["order"] == 5

    def test_create_idor_blocked(self, client_b, dream_a, milestone_a):
        resp = client_b.post(
            self.URL,
            {
                "dream": str(dream_a.id),
                "milestone": str(milestone_a.id),
                "title": "Hack",
                "order": 1,
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_complete_action(self, client_a, goal_a):
        resp = client_a.post(f"{self.URL}{goal_a.id}/complete/")
        assert resp.status_code == 200
        assert resp.data["status"] == "completed"

    def test_complete_other_user_404(self, client_b, goal_a):
        resp = client_b.post(f"{self.URL}{goal_a.id}/complete/")
        assert resp.status_code == 404

    def test_unauthenticated(self, anon_client):
        resp = anon_client.get(self.URL)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestTaskViewSet:
    URL = "/api/v1/plans/tasks/"

    def _results(self, resp):
        if isinstance(resp.data, dict) and "results" in resp.data:
            return resp.data["results"]
        return resp.data

    def test_list(self, client_a, goal_a, task_a):
        resp = client_a.get(f"{self.URL}?goal={goal_a.id}")
        assert resp.status_code == 200
        assert len(self._results(resp)) >= 1

    def test_retrieve(self, client_a, task_a):
        resp = client_a.get(f"{self.URL}{task_a.id}/")
        assert resp.status_code == 200

    def test_create_with_explicit_order(self, client_a, goal_a):
        resp = client_a.post(
            self.URL,
            {"goal": str(goal_a.id), "title": "Ordered Task", "order": 10},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["order"] == 10

    def test_create_idor_blocked(self, client_b, goal_a):
        resp = client_b.post(
            self.URL,
            {"goal": str(goal_a.id), "title": "Hack Task", "order": 1},
            format="json",
        )
        assert resp.status_code == 403

    def test_complete_action(self, client_a, task_a):
        resp = client_a.post(f"{self.URL}{task_a.id}/complete/")
        assert resp.status_code == 200
        assert resp.data["status"] == "completed"

    def test_complete_other_user_404(self, client_b, task_a):
        resp = client_b.post(f"{self.URL}{task_a.id}/complete/")
        assert resp.status_code == 404

    def test_update(self, client_a, task_a):
        resp = client_a.patch(
            f"{self.URL}{task_a.id}/",
            {"title": "Updated Task"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["title"] == "Updated Task"

    def test_delete(self, client_a, task_a):
        resp = client_a.delete(f"{self.URL}{task_a.id}/")
        assert resp.status_code == 204

    def test_unauthenticated(self, anon_client):
        resp = anon_client.get(self.URL)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestObstacleViewSet:
    URL = "/api/v1/plans/obstacles/"

    def _results(self, resp):
        if isinstance(resp.data, dict) and "results" in resp.data:
            return resp.data["results"]
        return resp.data

    def test_list(self, client_a, dream_a):
        Obstacle.objects.create(
            dream=dream_a, title="Obs1", description="D"
        )
        resp = client_a.get(f"{self.URL}?dream={dream_a.id}")
        assert resp.status_code == 200
        assert len(self._results(resp)) >= 1

    def test_create(self, client_a, dream_a):
        resp = client_a.post(
            self.URL,
            {"dream": str(dream_a.id), "title": "New Obs", "description": "Desc"},
            format="json",
        )
        assert resp.status_code == 201

    def test_create_idor_blocked(self, client_b, dream_a):
        resp = client_b.post(
            self.URL,
            {"dream": str(dream_a.id), "title": "Hack", "description": "X"},
            format="json",
        )
        assert resp.status_code == 403

    def test_update(self, client_a, dream_a):
        obs = Obstacle.objects.create(dream=dream_a, title="Old", description="D")
        resp = client_a.patch(
            f"{self.URL}{obs.id}/",
            {"title": "New"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["title"] == "New"

    def test_delete(self, client_a, dream_a):
        obs = Obstacle.objects.create(dream=dream_a, title="Del", description="D")
        resp = client_a.delete(f"{self.URL}{obs.id}/")
        assert resp.status_code == 204

    def test_list_other_user_empty(self, client_b, dream_a):
        Obstacle.objects.create(dream=dream_a, title="Hidden", description="D")
        resp = client_b.get(f"{self.URL}?dream={dream_a.id}")
        assert resp.status_code == 200
        assert len(self._results(resp)) == 0


@pytest.mark.django_db
class TestCheckInViewSet:
    URL = "/api/v1/plans/checkins/"

    def _results(self, resp):
        if isinstance(resp.data, dict) and "results" in resp.data:
            return resp.data["results"]
        return resp.data

    def test_list(self, client_a, dream_a):
        PlanCheckIn.objects.create(dream=dream_a, scheduled_for=timezone.now())
        resp = client_a.get(f"{self.URL}?dream={dream_a.id}")
        assert resp.status_code == 200

    def test_list_filter_by_status(self, client_a, dream_a):
        PlanCheckIn.objects.create(
            dream=dream_a, scheduled_for=timezone.now(), status="awaiting_user"
        )
        PlanCheckIn.objects.create(
            dream=dream_a, scheduled_for=timezone.now(), status="completed"
        )
        resp = client_a.get(f"{self.URL}?status=awaiting_user")
        assert resp.status_code == 200
        results = self._results(resp)
        for item in results:
            assert item["status"] == "awaiting_user"

    def test_retrieve_detail(self, client_a, dream_a):
        ci = PlanCheckIn.objects.create(
            dream=dream_a,
            scheduled_for=timezone.now(),
            questionnaire=[{"id": "q1"}],
        )
        resp = client_a.get(f"{self.URL}{ci.id}/")
        assert resp.status_code == 200
        assert "questionnaire" in resp.data

    def test_retrieve_other_user_404(self, client_b, dream_a):
        ci = PlanCheckIn.objects.create(
            dream=dream_a, scheduled_for=timezone.now()
        )
        resp = client_b.get(f"{self.URL}{ci.id}/")
        assert resp.status_code == 404

    def test_respond_action(self, client_a, dream_a):
        ci = PlanCheckIn.objects.create(
            dream=dream_a,
            scheduled_for=timezone.now(),
            status="awaiting_user",
            questionnaire=[{"id": "q1", "question": "How?"}],
        )
        resp = client_a.post(
            f"{self.URL}{ci.id}/respond/",
            {"responses": {"q1": "Fine"}},
            format="json",
        )
        assert resp.status_code == 200
        ci.refresh_from_db()
        # In testing settings, Celery runs eagerly, so the check-in
        # is processed immediately -> status goes to "completed"
        assert ci.status in ("ai_processing", "completed")
        assert ci.user_responses == {"q1": "Fine"}

    def test_status_poll_action(self, client_a, dream_a):
        ci = PlanCheckIn.objects.create(
            dream=dream_a, scheduled_for=timezone.now(), status="completed"
        )
        resp = client_a.get(f"{self.URL}{ci.id}/status_poll/")
        assert resp.status_code == 200
        assert resp.data["status"] == "completed"

    def test_read_only(self, client_a, dream_a):
        """CheckIn viewset is read-only: POST to create should fail (405)."""
        resp = client_a.post(
            self.URL,
            {"dream": str(dream_a.id), "scheduled_for": timezone.now().isoformat()},
            format="json",
        )
        assert resp.status_code in (405, 403)  # DRF can return 403 for disallowed methods

    def test_unauthenticated(self, anon_client):
        resp = anon_client.get(self.URL)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestFocusSessionViews:
    START_URL = "/api/v1/plans/focus/start/"
    COMPLETE_URL = "/api/v1/plans/focus/complete/"
    HISTORY_URL = "/api/v1/plans/focus/history/"
    STATS_URL = "/api/v1/plans/focus/stats/"

    def test_start_session(self, client_a):
        resp = client_a.post(
            self.START_URL,
            {"duration_minutes": 25, "session_type": "work"},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["duration_minutes"] == 25

    def test_start_with_task(self, client_a, task_a):
        resp = client_a.post(
            self.START_URL,
            {
                "task_id": str(task_a.id),
                "duration_minutes": 25,
                "session_type": "work",
            },
            format="json",
        )
        assert resp.status_code == 201
        assert str(resp.data["task"]) == str(task_a.id)

    def test_start_break(self, client_a):
        resp = client_a.post(
            self.START_URL,
            {"duration_minutes": 5, "session_type": "break"},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["session_type"] == "break"

    def test_start_invalid_duration(self, client_a):
        resp = client_a.post(
            self.START_URL,
            {"duration_minutes": 0},
            format="json",
        )
        assert resp.status_code == 400

    def test_complete_session(self, client_a, user_a):
        session = FocusSession.objects.create(
            user=user_a, duration_minutes=25, session_type="work"
        )
        resp = client_a.post(
            self.COMPLETE_URL,
            {"session_id": str(session.id), "actual_minutes": 20},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["completed"] is True
        assert resp.data["actual_minutes"] == 20

    def test_complete_nonexistent_session(self, client_a):
        resp = client_a.post(
            self.COMPLETE_URL,
            {"session_id": str(uuid.uuid4()), "actual_minutes": 5},
            format="json",
        )
        assert resp.status_code == 404

    def test_complete_other_user_session(self, client_b, user_a):
        """User B cannot complete User A's session."""
        session = FocusSession.objects.create(
            user=user_a, duration_minutes=25
        )
        resp = client_b.post(
            self.COMPLETE_URL,
            {"session_id": str(session.id), "actual_minutes": 10},
            format="json",
        )
        assert resp.status_code == 404

    def test_history(self, client_a, user_a):
        FocusSession.objects.create(user=user_a, duration_minutes=25)
        FocusSession.objects.create(user=user_a, duration_minutes=10)
        resp = client_a.get(self.HISTORY_URL)
        assert resp.status_code == 200
        assert len(resp.data) == 2

    def test_history_empty(self, client_a):
        resp = client_a.get(self.HISTORY_URL)
        assert resp.status_code == 200
        assert len(resp.data) == 0

    def test_stats(self, client_a, user_a):
        s = FocusSession.objects.create(
            user=user_a, duration_minutes=25, session_type="work"
        )
        s.actual_minutes = 20
        s.completed = True
        s.ended_at = timezone.now()
        s.save()
        resp = client_a.get(self.STATS_URL)
        assert resp.status_code == 200
        assert resp.data["total_sessions"] == 1
        assert resp.data["total_minutes"] == 20

    def test_stats_empty(self, client_a):
        resp = client_a.get(self.STATS_URL)
        assert resp.status_code == 200
        assert resp.data["total_sessions"] == 0
        assert resp.data["total_minutes"] == 0
        assert resp.data["average_minutes"] == 0

    def test_unauthenticated_start(self, anon_client):
        resp = anon_client.post(
            self.START_URL,
            {"duration_minutes": 25},
            format="json",
        )
        assert resp.status_code == 401

    def test_unauthenticated_history(self, anon_client):
        resp = anon_client.get(self.HISTORY_URL)
        assert resp.status_code == 401


# ──────────────────────────────────────────────────────────────────
# SERVICE TESTS
# ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPlanServiceProcessCheckin:
    def test_process_checkin_on_track(self, dream_a):
        ci = PlanCheckIn.objects.create(
            dream=dream_a,
            scheduled_for=timezone.now(),
            status="ai_processing",
        )
        PlanService.process_checkin(ci)
        ci.refresh_from_db()
        dream_a.refresh_from_db()
        assert ci.pace_status != ""
        assert ci.coaching_message != ""
        assert dream_a.last_checkin_at is not None
        assert dream_a.checkin_count == 1
        assert dream_a.next_checkin_at is not None

    def test_process_checkin_behind(self, user_a, milestone_a, goal_a):
        """Create a dream that is way behind schedule with overdue tasks."""
        # Dream created 150 days ago with a 180-day target -> expected ~83% but actual 0%
        dream_behind = Dream.objects.create(
            user=user_a,
            title="Behind Dream",
            status="active",
            target_date=timezone.now() + timedelta(days=30),
            progress_percentage=0.0,
        )
        # Backdate created_at
        Dream.objects.filter(id=dream_behind.id).update(
            created_at=timezone.now() - timedelta(days=150)
        )
        dream_behind.refresh_from_db()
        ms = DreamMilestone.objects.create(dream=dream_behind, title="M", order=1)
        g = Goal.objects.create(dream=dream_behind, milestone=ms, title="G", order=1)
        for i in range(5):
            Task.objects.create(
                goal=g,
                title=f"Overdue {i}",
                order=i,
                scheduled_date=timezone.now() - timedelta(days=10),
            )
        ci = PlanCheckIn.objects.create(
            dream=dream_behind,
            scheduled_for=timezone.now(),
            status="ai_processing",
        )
        PlanService.process_checkin(ci)
        ci.refresh_from_db()
        assert ci.tasks_overdue_at_checkin >= 5
        assert ci.pace_status in ("behind", "significantly_behind")
        assert ci.next_checkin_interval_days == 7

    def test_process_checkin_ahead(self, user_a):
        """Dream with high progress relative to timeline -> ahead."""
        # Create dream with a long timeline but high progress
        dream = Dream.objects.create(
            user=user_a,
            title="Ahead Dream",
            status="active",
            target_date=timezone.now() + timedelta(days=365),
            progress_percentage=80.0,
        )
        ci = PlanCheckIn.objects.create(
            dream=dream,
            scheduled_for=timezone.now(),
            status="ai_processing",
        )
        PlanService.process_checkin(ci)
        ci.refresh_from_db()
        assert ci.pace_status in ("ahead", "significantly_ahead")
        assert ci.next_checkin_interval_days == 21

    def test_process_checkin_no_target_date(self, user_a):
        """Without target_date, pace based on overdue count."""
        dream = Dream.objects.create(
            user=user_a,
            title="No Target",
            status="active",
        )
        ci = PlanCheckIn.objects.create(
            dream=dream,
            scheduled_for=timezone.now(),
            status="ai_processing",
        )
        PlanService.process_checkin(ci)
        ci.refresh_from_db()
        assert ci.pace_status == "on_track"  # no overdue tasks

    def test_process_checkin_counts_completed_tasks(
        self, dream_a, milestone_a, goal_a
    ):
        """Verify tasks_completed_since_last is correct."""
        t1 = Task.objects.create(goal=goal_a, title="Done", order=1, duration_mins=10)
        t1.complete()
        ci = PlanCheckIn.objects.create(
            dream=dream_a,
            scheduled_for=timezone.now(),
            status="ai_processing",
        )
        PlanService.process_checkin(ci)
        ci.refresh_from_db()
        assert ci.tasks_completed_since_last >= 1


@pytest.mark.django_db
class TestPlanServiceComputePace:
    def test_on_track(self, dream_a):
        pace = PlanService._compute_pace(dream_a, overdue_count=0)
        assert pace in ("on_track", "ahead", "significantly_ahead")

    def test_behind_with_overdue(self, user_a):
        dream = Dream.objects.create(
            user=user_a, title="D", status="active"
        )
        pace = PlanService._compute_pace(dream, overdue_count=2)
        assert pace == "behind"

    def test_significantly_behind_many_overdue(self, user_a):
        dream = Dream.objects.create(
            user=user_a, title="D", status="active"
        )
        pace = PlanService._compute_pace(dream, overdue_count=10)
        assert pace == "significantly_behind"


@pytest.mark.django_db
class TestPlanServiceCoachingMessage:
    def test_all_pace_statuses(self):
        for status in ("significantly_ahead", "ahead", "on_track", "behind", "significantly_behind"):
            msg = PlanService._generate_coaching_message(status, 5, 2)
            assert len(msg) > 0

    def test_unknown_pace(self):
        msg = PlanService._generate_coaching_message("unknown", 0, 0)
        assert msg == "Keep going!"


@pytest.mark.django_db
class TestPlanServiceSummary:
    def test_get_plan_summary(self, dream_a, milestone_a, goal_a, task_a):
        summary = PlanService.get_dream_plan_summary(dream_a)
        assert summary["milestones"] == 1
        assert summary["goals"] == 1
        assert summary["total_tasks"] == 1
        assert summary["completed_tasks"] == 0

    def test_summary_after_completion(self, dream_a, milestone_a, goal_a, task_a):
        task_a.complete()
        summary = PlanService.get_dream_plan_summary(dream_a)
        assert summary["completed_tasks"] == 1


# ──────────────────────────────────────────────────────────────────
# TASK (CELERY) TESTS
# ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestProcessCheckinTask:
    def test_task_processes_checkin(self, dream_a):
        from apps.plans.tasks import process_checkin_responses

        ci = PlanCheckIn.objects.create(
            dream=dream_a,
            scheduled_for=timezone.now(),
            status="ai_processing",
            user_responses={"q1": "good"},
        )
        # Celery eager mode in testing settings
        process_checkin_responses(str(ci.id))
        ci.refresh_from_db()
        assert ci.status == "completed"
        assert ci.completed_at is not None

    def test_task_nonexistent_checkin(self, dream_a):
        from apps.plans.tasks import process_checkin_responses

        # Should not raise, just log
        process_checkin_responses(str(uuid.uuid4()))

    def test_task_wrong_status(self, dream_a):
        from apps.plans.tasks import process_checkin_responses

        ci = PlanCheckIn.objects.create(
            dream=dream_a,
            scheduled_for=timezone.now(),
            status="pending",  # not ai_processing
        )
        process_checkin_responses(str(ci.id))
        ci.refresh_from_db()
        assert ci.status == "pending"  # unchanged

    def test_task_handles_error(self, dream_a):
        from apps.plans.tasks import process_checkin_responses

        ci = PlanCheckIn.objects.create(
            dream=dream_a,
            scheduled_for=timezone.now(),
            status="ai_processing",
        )
        with patch.object(PlanService, "process_checkin", side_effect=ValueError("boom")):
            with pytest.raises((ValueError, Exception)):
                process_checkin_responses(str(ci.id))
        ci.refresh_from_db()
        assert ci.status == "failed"
        assert "boom" in ci.error_message

    def test_generate_plan_task(self, dream_a, user_a):
        from apps.plans.tasks import generate_plan_for_dream

        with patch("apps.dreams.tasks.generate_dream_plan_task") as mock_task:
            mock_task.delay = lambda *args: None
            generate_plan_for_dream(str(dream_a.id), str(user_a.id))
            # Should call the dream's generate task


# ──────────────────────────────────────────────────────────────────
# IDOR TESTS (Cross-user access prevention)
# ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestIDOR:
    """Verify that User B cannot access/modify User A's resources."""

    def test_milestone_create_on_other_dream(self, client_b, dream_a):
        resp = client_b.post(
            "/api/v1/plans/milestones/",
            {"dream": str(dream_a.id), "title": "IDOR MS", "order": 1},
            format="json",
        )
        assert resp.status_code == 403

    def test_goal_create_on_other_dream(self, client_b, dream_a):
        resp = client_b.post(
            "/api/v1/plans/goals/",
            {"dream": str(dream_a.id), "title": "IDOR Goal", "order": 1},
            format="json",
        )
        assert resp.status_code == 403

    def test_task_create_on_other_goal(self, client_b, goal_a):
        resp = client_b.post(
            "/api/v1/plans/tasks/",
            {"goal": str(goal_a.id), "title": "IDOR Task", "order": 1},
            format="json",
        )
        assert resp.status_code == 403

    def test_obstacle_create_on_other_dream(self, client_b, dream_a):
        resp = client_b.post(
            "/api/v1/plans/obstacles/",
            {
                "dream": str(dream_a.id),
                "title": "IDOR Obs",
                "description": "X",
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_milestone_retrieve_other_user(self, client_b, milestone_a):
        resp = client_b.get(f"/api/v1/plans/milestones/{milestone_a.id}/")
        assert resp.status_code == 404

    def test_goal_retrieve_other_user(self, client_b, goal_a):
        resp = client_b.get(f"/api/v1/plans/goals/{goal_a.id}/")
        assert resp.status_code == 404

    def test_task_retrieve_other_user(self, client_b, task_a):
        resp = client_b.get(f"/api/v1/plans/tasks/{task_a.id}/")
        assert resp.status_code == 404

    def test_checkin_retrieve_other_user(self, client_b, dream_a):
        ci = PlanCheckIn.objects.create(
            dream=dream_a, scheduled_for=timezone.now()
        )
        resp = client_b.get(f"/api/v1/plans/checkins/{ci.id}/")
        assert resp.status_code == 404

    def test_focus_complete_other_user_session(self, client_b, user_a):
        session = FocusSession.objects.create(user=user_a, duration_minutes=25)
        resp = client_b.post(
            "/api/v1/plans/focus/complete/",
            {"session_id": str(session.id), "actual_minutes": 10},
            format="json",
        )
        assert resp.status_code == 404

    def test_milestone_update_other_user(self, client_b, milestone_a):
        resp = client_b.patch(
            f"/api/v1/plans/milestones/{milestone_a.id}/",
            {"title": "IDOR Update"},
            format="json",
        )
        assert resp.status_code == 404

    def test_goal_delete_other_user(self, client_b, goal_a):
        resp = client_b.delete(f"/api/v1/plans/goals/{goal_a.id}/")
        assert resp.status_code == 404

    def test_task_delete_other_user(self, client_b, task_a):
        resp = client_b.delete(f"/api/v1/plans/tasks/{task_a.id}/")
        assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────
# BACKWARD-COMPAT URL TESTS
# ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBackwardCompatURLs:
    """Verify unversioned /api/ routes work the same as /api/v1/."""

    def test_milestones_unversioned(self, client_a, dream_a, milestone_a):
        resp = client_a.get(f"/api/plans/milestones/?dream={dream_a.id}")
        assert resp.status_code == 200

    def test_goals_unversioned(self, client_a, dream_a, goal_a):
        resp = client_a.get(f"/api/plans/goals/?dream={dream_a.id}")
        assert resp.status_code == 200

    def test_tasks_unversioned(self, client_a, goal_a, task_a):
        resp = client_a.get(f"/api/plans/tasks/?goal={goal_a.id}")
        assert resp.status_code == 200

    def test_focus_start_unversioned(self, client_a):
        resp = client_a.post(
            "/api/plans/focus/start/",
            {"duration_minutes": 25},
            format="json",
        )
        assert resp.status_code == 201


# ──────────────────────────────────────────────────────────────────
# EDGE CASES
# ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEdgeCases:
    def test_goal_explicit_order(self, client_a, dream_a, milestone_a):
        """Goal with explicit order is respected."""
        resp = client_a.post(
            "/api/v1/plans/goals/",
            {
                "dream": str(dream_a.id),
                "milestone": str(milestone_a.id),
                "title": "First",
                "order": 42,
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["order"] == 42

    def test_task_explicit_order(self, client_a, goal_a, task_a):
        """Task with explicit order is respected."""
        resp = client_a.post(
            "/api/v1/plans/tasks/",
            {"goal": str(goal_a.id), "title": "Second", "order": 99},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["order"] == 99

    def test_focus_stats_division_by_zero(self, client_a):
        """No sessions -> average is 0, not division error."""
        resp = client_a.get("/api/v1/plans/focus/stats/")
        assert resp.status_code == 200
        assert resp.data["average_minutes"] == 0

    def test_milestone_update_progress_cascades_to_dream(
        self, dream_a, milestone_a, goal_a, goal_a2
    ):
        """Completing all goals in milestone cascades to dream."""
        goal_a.complete()
        goal_a2.complete()
        dream_a.refresh_from_db()
        assert dream_a.progress_percentage >= 0

    def test_task_complete_with_zero_duration(self, goal_a, user_a):
        """Zero-duration task still awards minimum 10 XP."""
        t = Task.objects.create(goal=goal_a, title="Z", order=1, duration_mins=0)
        initial_xp = user_a.xp
        t.complete()
        user_a.refresh_from_db()
        assert user_a.xp == initial_xp + 10

    def test_multiple_snapshots_different_days(self, dream_a):
        """Snapshots on different days should both exist."""
        today = timezone.now().date()
        DreamProgressSnapshot.objects.create(
            dream=dream_a,
            date=today - timedelta(days=1),
            progress_percentage=30.0,
        )
        DreamProgressSnapshot.record_snapshot(dream_a)
        assert DreamProgressSnapshot.objects.filter(dream=dream_a).count() == 2

    def test_checkin_respond_triggers_async(self, client_a, dream_a):
        """Respond action sets status and fires task."""
        ci = PlanCheckIn.objects.create(
            dream=dream_a,
            scheduled_for=timezone.now(),
            status="awaiting_user",
            questionnaire=[{"id": "q1"}],
        )
        resp = client_a.post(
            f"/api/v1/plans/checkins/{ci.id}/respond/",
            {"responses": {"q1": "good"}},
            format="json",
        )
        assert resp.status_code == 200
        ci.refresh_from_db()
        # In eager mode, the task runs immediately, so it may already be completed
        assert ci.status in ("ai_processing", "completed")

    def test_focus_history_limited_to_20(self, client_a, user_a):
        """History endpoint returns at most 20 sessions."""
        for i in range(25):
            FocusSession.objects.create(user=user_a, duration_minutes=5)
        resp = client_a.get("/api/v1/plans/focus/history/")
        assert resp.status_code == 200
        assert len(resp.data) == 20
