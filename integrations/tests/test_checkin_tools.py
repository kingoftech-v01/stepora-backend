"""
Tests for integrations.checkin_tools.CheckInToolExecutor.

All methods are tested with database fixtures (Django models).
"""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.dreams.models import Dream, DreamMilestone, Goal, Task
from apps.users.models import User
from integrations.checkin_tools import CheckInToolExecutor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def checkin_user(db):
    return User.objects.create_user(
        email="checkin@example.com",
        password="testpassword123",
        display_name="Check User",
        persona={"available_hours_per_week": 10, "preferred_schedule": "morning"},
        work_schedule={"monday": "9-17"},
    )


@pytest.fixture
def checkin_dream(db, checkin_user):
    return Dream.objects.create(
        user=checkin_user,
        title="Learn French",
        description="Become fluent in French",
        category="language",
        status="active",
        target_date=timezone.now() + timedelta(days=180),
    )


@pytest.fixture
def checkin_milestone(db, checkin_dream):
    return DreamMilestone.objects.create(
        dream=checkin_dream,
        title="Month 1 - Basics",
        description="Learn basic vocabulary and grammar",
        order=1,
        status="pending",
        expected_date=date.today() + timedelta(days=30),
        deadline_date=date.today() + timedelta(days=35),
    )


@pytest.fixture
def checkin_milestone2(db, checkin_dream):
    return DreamMilestone.objects.create(
        dream=checkin_dream,
        title="Month 2 - Intermediate",
        description="Build on basics",
        order=2,
        status="pending",
        expected_date=date.today() + timedelta(days=60),
        deadline_date=date.today() + timedelta(days=65),
    )


@pytest.fixture
def checkin_goal(db, checkin_dream, checkin_milestone):
    return Goal.objects.create(
        dream=checkin_dream,
        milestone=checkin_milestone,
        title="Learn 100 Words",
        description="Memorize 100 basic French words",
        order=1,
        status="pending",
    )


@pytest.fixture
def checkin_task(db, checkin_goal):
    return Task.objects.create(
        goal=checkin_goal,
        title="Study 10 words",
        description="Study 10 new words today",
        order=1,
        duration_mins=30,
        status="pending",
        deadline_date=date.today() - timedelta(days=1),  # overdue
    )


@pytest.fixture
def completed_task(db, checkin_goal):
    return Task.objects.create(
        goal=checkin_goal,
        title="Study 10 words - done",
        description="Study done",
        order=2,
        duration_mins=20,
        status="completed",
        completed_at=timezone.now() - timedelta(days=2),
    )


@pytest.fixture
def executor(checkin_dream, checkin_user):
    return CheckInToolExecutor(checkin_dream, checkin_user)


# ===================================================================
# dispatch()
# ===================================================================

class TestDispatch:

    def test_dispatch_unknown_tool(self, executor):
        result, is_finish = executor.dispatch("nonexistent_tool", {})
        assert result["success"] is False
        assert "Unknown tool" in result["error"]
        assert is_finish is False

    def test_dispatch_known_tool(self, executor, checkin_milestone):
        result, is_finish = executor.dispatch("get_dream_progress", {})
        assert result["success"] is True
        assert is_finish is False

    def test_dispatch_finish_signal(self, executor):
        result, is_finish = executor.dispatch("finish_check_in", {
            "coaching_message": "Great!",
            "months_now_covered_through": 3,
        })
        assert is_finish is True
        assert result["coaching_message"] == "Great!"

    def test_dispatch_questionnaire_finish_signal(self, executor):
        result, is_finish = executor.dispatch("finish_questionnaire_generation", {
            "questions": [{"id": "q1"}],
        })
        assert is_finish is True
        assert result["success"] is True

    def test_dispatch_exception_handled(self, executor):
        # Pass invalid args to a method to trigger an exception
        result, is_finish = executor.dispatch("create_tasks", {})
        assert result["success"] is False
        assert is_finish is False


# ===================================================================
# get_dream_progress()
# ===================================================================

class TestGetDreamProgress:

    def test_basic_progress(self, executor, checkin_milestone, checkin_goal, checkin_task, completed_task):
        result = executor.get_dream_progress()
        assert result["success"] is True
        assert result["total_tasks"] == 2
        assert result["completed_tasks"] == 1
        assert result["pending_tasks"] == 1
        assert len(result["milestones"]) == 1
        assert result["milestones"][0]["goals"][0]["total_tasks"] == 2

    def test_empty_dream(self, executor):
        result = executor.get_dream_progress()
        assert result["success"] is True
        assert result["total_tasks"] == 0
        assert result["milestones"] == []

    def test_velocity_calculation(self, executor, checkin_goal):
        # Create tasks completed in last 4 weeks
        for i in range(8):
            Task.objects.create(
                goal=checkin_goal, title=f"T{i}", order=i,
                status="completed",
                completed_at=timezone.now() - timedelta(days=i * 3),
                duration_mins=15,
            )
        result = executor.get_dream_progress()
        assert result["velocity_tasks_per_week"] > 0

    def test_overdue_count(self, executor, checkin_task):
        result = executor.get_dream_progress()
        assert result["overdue_tasks"] == 1


# ===================================================================
# get_completed_tasks()
# ===================================================================

class TestGetCompletedTasks:

    def test_with_since_date(self, executor, completed_task):
        since = (timezone.now() - timedelta(days=7)).date().isoformat()
        result = executor.get_completed_tasks(since_date=since)
        assert result["success"] is True
        assert result["count"] >= 1

    def test_no_since_date(self, executor, completed_task):
        result = executor.get_completed_tasks()
        assert result["success"] is True

    def test_invalid_since_date(self, executor, completed_task):
        result = executor.get_completed_tasks(since_date="not-a-date")
        assert result["success"] is True  # falls back to 14 days ago


# ===================================================================
# get_overdue_tasks()
# ===================================================================

class TestGetOverdueTasks:

    def test_returns_overdue(self, executor, checkin_task):
        result = executor.get_overdue_tasks()
        assert result["success"] is True
        assert result["count"] >= 1
        assert result["tasks"][0]["days_overdue"] >= 1

    def test_no_overdue(self, executor, checkin_goal):
        # Create a task with future deadline
        Task.objects.create(
            goal=checkin_goal, title="Future", order=1, status="pending",
            deadline_date=date.today() + timedelta(days=30), duration_mins=15,
        )
        result = executor.get_overdue_tasks()
        assert result["count"] == 0


# ===================================================================
# create_tasks()
# ===================================================================

class TestCreateTasks:

    def test_success(self, executor, checkin_goal, checkin_milestone):
        result = executor.create_tasks(str(checkin_goal.id), [
            {"title": "New Task 1", "description": "Do X", "duration_mins": 20, "day_number": 5},
            {"title": "New Task 2", "expected_date": "2026-05-01", "deadline_date": "2026-05-03"},
        ])
        assert result["success"] is True
        assert result["tasks_created"] == 2
        # Milestone should be marked as having tasks
        checkin_milestone.refresh_from_db()
        assert checkin_milestone.has_tasks is True

    def test_goal_not_found(self, executor):
        import uuid
        result = executor.create_tasks(str(uuid.uuid4()), [{"title": "T"}])
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_invalid_dates_ignored(self, executor, checkin_goal):
        result = executor.create_tasks(str(checkin_goal.id), [
            {"title": "T", "expected_date": "invalid", "deadline_date": "invalid"},
        ])
        assert result["success"] is True
        assert result["tasks_created"] == 1


# ===================================================================
# update_milestone()
# ===================================================================

class TestUpdateMilestone:

    def test_update_dates(self, executor, checkin_milestone):
        result = executor.update_milestone(
            str(checkin_milestone.id),
            new_expected_date="2026-05-01",
            new_deadline_date="2026-05-10",
        )
        assert result["success"] is True
        assert "expected_date" in result["updated_fields"]
        checkin_milestone.refresh_from_db()
        assert checkin_milestone.expected_date == date(2026, 5, 1)

    def test_update_description(self, executor, checkin_milestone):
        result = executor.update_milestone(
            str(checkin_milestone.id),
            new_description="Updated description",
        )
        assert result["success"] is True
        assert "description" in result["updated_fields"]

    def test_milestone_not_found(self, executor):
        import uuid
        result = executor.update_milestone(str(uuid.uuid4()))
        assert result["success"] is False

    def test_no_updates(self, executor, checkin_milestone):
        result = executor.update_milestone(str(checkin_milestone.id))
        assert result["success"] is True
        assert result["updated_fields"] == []

    def test_invalid_date_ignored(self, executor, checkin_milestone):
        result = executor.update_milestone(
            str(checkin_milestone.id),
            new_expected_date="not-a-date",
        )
        assert result["success"] is True
        assert result["updated_fields"] == []


# ===================================================================
# get_calendar_availability()
# ===================================================================

class TestGetCalendarAvailability:

    def test_basic(self, executor):
        result = executor.get_calendar_availability()
        assert result["success"] is True
        assert "recurring_availability" in result
        assert "work_schedule" in result

    def test_with_dates(self, executor):
        result = executor.get_calendar_availability(
            start_date=date.today().isoformat(),
            end_date=(date.today() + timedelta(days=7)).isoformat(),
        )
        assert result["success"] is True

    def test_invalid_dates(self, executor):
        result = executor.get_calendar_availability(
            start_date="bad", end_date="bad"
        )
        assert result["success"] is True  # falls back to defaults


# ===================================================================
# mark_goal_completed()
# ===================================================================

class TestMarkGoalCompleted:

    def test_success(self, executor, checkin_goal):
        result = executor.mark_goal_completed(str(checkin_goal.id))
        assert result["success"] is True
        checkin_goal.refresh_from_db()
        assert checkin_goal.status == "completed"
        assert checkin_goal.progress_percentage == 100.0

    def test_goal_not_found(self, executor):
        import uuid
        result = executor.mark_goal_completed(str(uuid.uuid4()))
        assert result["success"] is False


# ===================================================================
# create_new_goal()
# ===================================================================

class TestCreateNewGoal:

    def test_success(self, executor, checkin_milestone):
        initial_count = Goal.objects.filter(dream=executor.dream).count()
        result = executor.create_new_goal(
            str(checkin_milestone.id),
            "New Goal",
            "Description",
            expected_date="2026-05-01",
            deadline_date="2026-05-15",
            estimated_minutes=300,
        )
        assert result["success"] is True
        assert result["title"] == "New Goal"
        assert Goal.objects.filter(dream=executor.dream).count() == initial_count + 1

    def test_milestone_not_found(self, executor):
        import uuid
        result = executor.create_new_goal(str(uuid.uuid4()), "T", "D")
        assert result["success"] is False

    def test_invalid_dates(self, executor, checkin_milestone):
        result = executor.create_new_goal(
            str(checkin_milestone.id), "T", "D",
            expected_date="bad", deadline_date="bad",
        )
        assert result["success"] is True  # dates silently ignored


# ===================================================================
# add_milestone()
# ===================================================================

class TestAddMilestone:

    def test_success(self, executor, checkin_milestone):
        result = executor.add_milestone(
            "New Milestone", "Description", 1,
            expected_date="2026-06-01", deadline_date="2026-06-10",
        )
        assert result["success"] is True
        assert result["order"] == 1
        # Original milestone should have been shifted to order 2
        checkin_milestone.refresh_from_db()
        assert checkin_milestone.order == 2

    def test_invalid_dates(self, executor):
        result = executor.add_milestone("M", "D", 1, expected_date="bad")
        assert result["success"] is True


# ===================================================================
# remove_milestone()
# ===================================================================

class TestRemoveMilestone:

    def test_delete_empty_milestone(self, executor, checkin_milestone):
        result = executor.remove_milestone(str(checkin_milestone.id), reason="Not needed")
        assert result["success"] is True
        assert result["action"] == "deleted"
        assert not DreamMilestone.objects.filter(pk=checkin_milestone.id).exists()

    def test_skip_milestone_with_completed_tasks(self, executor, checkin_milestone, checkin_goal, completed_task):
        result = executor.remove_milestone(str(checkin_milestone.id))
        assert result["success"] is True
        assert result["action"] == "skipped"
        checkin_milestone.refresh_from_db()
        assert checkin_milestone.status == "skipped"

    def test_not_found(self, executor):
        import uuid
        result = executor.remove_milestone(str(uuid.uuid4()))
        assert result["success"] is False

    def test_resequence_after_delete(self, executor, checkin_milestone, checkin_milestone2):
        executor.remove_milestone(str(checkin_milestone.id))
        checkin_milestone2.refresh_from_db()
        assert checkin_milestone2.order == 1


# ===================================================================
# reorder_milestone()
# ===================================================================

class TestReorderMilestone:

    def test_move_forward(self, executor, checkin_milestone, checkin_milestone2):
        result = executor.reorder_milestone(str(checkin_milestone.id), 2)
        assert result["success"] is True
        assert result["old_order"] == 1
        assert result["new_order"] == 2
        checkin_milestone.refresh_from_db()
        assert checkin_milestone.order == 2
        checkin_milestone2.refresh_from_db()
        assert checkin_milestone2.order == 1

    def test_move_backward(self, executor, checkin_milestone, checkin_milestone2):
        result = executor.reorder_milestone(str(checkin_milestone2.id), 1)
        assert result["success"] is True
        checkin_milestone2.refresh_from_db()
        assert checkin_milestone2.order == 1

    def test_same_position(self, executor, checkin_milestone):
        result = executor.reorder_milestone(str(checkin_milestone.id), 1)
        assert result["success"] is True
        assert result["old_order"] == result["new_order"]

    def test_not_found(self, executor):
        import uuid
        result = executor.reorder_milestone(str(uuid.uuid4()), 1)
        assert result["success"] is False


# ===================================================================
# shift_milestone_dates()
# ===================================================================

class TestShiftMilestoneDates:

    def test_shift_forward(self, executor, checkin_milestone, checkin_goal, checkin_task):
        # Set dates on goal and task
        checkin_goal.expected_date = date.today()
        checkin_goal.deadline_date = date.today() + timedelta(days=5)
        checkin_goal.save()
        checkin_task.expected_date = date.today()
        checkin_task.deadline_date = date.today() + timedelta(days=3)
        checkin_task.scheduled_date = date.today()
        checkin_task.save()

        result = executor.shift_milestone_dates(str(checkin_milestone.id), 7)
        assert result["success"] is True
        assert result["shift_days"] == 7
        checkin_milestone.refresh_from_db()
        assert checkin_milestone.expected_date == date.today() + timedelta(days=37)  # original 30 + 7

    def test_not_found(self, executor):
        import uuid
        result = executor.shift_milestone_dates(str(uuid.uuid4()), 5)
        assert result["success"] is False

    def test_no_dates_to_shift(self, executor):
        ms = DreamMilestone.objects.create(
            dream=executor.dream, title="No Dates", description="D", order=5,
        )
        result = executor.shift_milestone_dates(str(ms.id), 10)
        assert result["success"] is True


# ===================================================================
# get_goals_for_milestone()
# ===================================================================

class TestGetGoalsForMilestone:

    def test_success(self, executor, checkin_milestone, checkin_goal, checkin_task, completed_task):
        result = executor.get_goals_for_milestone(str(checkin_milestone.id))
        assert result["success"] is True
        assert len(result["goals"]) == 1
        goal_data = result["goals"][0]
        assert goal_data["total_tasks"] == 2
        assert goal_data["completed_tasks"] == 1
        assert goal_data["pending_tasks"] == 1

    def test_not_found(self, executor):
        import uuid
        result = executor.get_goals_for_milestone(str(uuid.uuid4()))
        assert result["success"] is False


# ===================================================================
# generate_extension_tasks()
# ===================================================================

class TestGenerateExtensionTasks:

    def test_delegates_to_create_tasks(self, executor, checkin_goal, checkin_milestone):
        result = executor.generate_extension_tasks(
            str(checkin_goal.id),
            [{"title": "Extension Task 1", "duration_mins": 15}],
        )
        assert result["success"] is True
        assert result["tasks_created"] == 1


# ===================================================================
# finish_check_in()
# ===================================================================

class TestFinishCheckIn:

    def test_success(self, executor):
        result = executor.finish_check_in(
            coaching_message="Great work!",
            months_now_covered_through=4,
            adjustment_summary="Shifted dates",
            pace_status="ahead",
            next_checkin_days=21,
        )
        assert result["success"] is True
        assert result["coaching_message"] == "Great work!"
        assert result["months_now_covered_through"] == 4
        assert result["pace_status"] == "ahead"
        assert result["next_checkin_days"] == 21


# ===================================================================
# finish_questionnaire_generation()
# ===================================================================

class TestFinishQuestionnaireGeneration:

    def test_success(self, executor):
        result = executor.finish_questionnaire_generation(
            questions=[{"id": "satisfaction", "question_type": "slider"}],
            opening_message="Hi!",
            pace_summary="On track",
        )
        assert result["success"] is True
        assert len(result["questions"]) == 1
        assert result["opening_message"] == "Hi!"


# ===================================================================
# _assert_owned()
# ===================================================================

class TestAssertOwned:

    def test_object_not_found(self, executor):
        import uuid
        with pytest.raises(ValueError, match="not found"):
            executor._assert_owned(Goal, uuid.uuid4())

    def test_dream_mismatch(self, executor, checkin_user):
        other_dream = Dream.objects.create(
            user=checkin_user, title="Other", description="D", status="active"
        )
        other_goal = Goal.objects.create(
            dream=other_dream, title="Other Goal", order=1, status="pending"
        )
        with pytest.raises(ValueError, match="does not belong"):
            executor._assert_owned(Goal, other_goal.id)

    def test_goal_field_mismatch(self, executor, checkin_user):
        other_dream = Dream.objects.create(
            user=checkin_user, title="Other", description="D", status="active"
        )
        other_goal = Goal.objects.create(
            dream=other_dream, title="OG", order=1, status="pending"
        )
        other_task = Task.objects.create(
            goal=other_goal, title="OT", order=1, status="pending", duration_mins=15
        )
        with pytest.raises(ValueError, match="does not belong"):
            executor._assert_owned(Task, other_task.id, field="goal")

    def test_success(self, executor, checkin_goal):
        obj = executor._assert_owned(Goal, checkin_goal.id)
        assert obj == checkin_goal
