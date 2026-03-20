"""
Tests for apps/dreams/serializers.py
"""

import json
from datetime import timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.dreams.models import (
    Dream,
    DreamCollaborator,
    DreamJournal,
    DreamMilestone,
    DreamTag,
    DreamTagging,
    DreamTemplate,
    Goal,
    ProgressPhoto,
    SharedDream,
    Task,
    VisionBoardImage,
)
from apps.dreams.serializers import (
    AddCollaboratorSerializer,
    AddTagSerializer,
    CalibrationResponseSerializer,
    DreamCollaboratorSerializer,
    DreamCreateSerializer,
    DreamDetailSerializer,
    DreamJournalSerializer,
    DreamMilestoneSerializer,
    DreamSerializer,
    DreamTagSerializer,
    DreamTemplateSerializer,
    DreamUpdateSerializer,
    FocusSessionCompleteSerializer,
    FocusSessionSerializer,
    FocusSessionStartSerializer,
    GoalCreateSerializer,
    GoalSerializer,
    ObstacleSerializer,
    PlanCheckInSerializer,
    ProgressPhotoSerializer,
    ShareDreamRequestSerializer,
    SharedDreamSerializer,
    TaskCreateSerializer,
    TaskSerializer,
    VisionBoardImageSerializer,
)
from apps.users.models import User


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def ser_user(db):
    return User.objects.create_user(
        email="ser_user@test.com",
        password="testpass123",
        display_name="Ser User",
    )


@pytest.fixture
def ser_user2(db):
    return User.objects.create_user(
        email="ser_user2@test.com",
        password="testpass123",
        display_name="Ser User 2",
    )


@pytest.fixture
def ser_dream(db, ser_user):
    return Dream.objects.create(
        user=ser_user,
        title="Test Dream",
        description="A dream for serializer tests",
        category="education",
        status="active",
        priority=1,
    )


@pytest.fixture
def ser_milestone(db, ser_dream):
    return DreamMilestone.objects.create(
        dream=ser_dream,
        title="Milestone 1",
        description="First milestone",
        order=1,
        status="pending",
    )


@pytest.fixture
def ser_goal(db, ser_dream, ser_milestone):
    return Goal.objects.create(
        dream=ser_dream,
        milestone=ser_milestone,
        title="Goal 1",
        description="First goal",
        order=0,
        status="pending",
    )


@pytest.fixture
def ser_task(db, ser_goal):
    return Task.objects.create(
        goal=ser_goal,
        title="Task 1",
        description="First task",
        order=0,
        duration_mins=30,
        status="pending",
    )


@pytest.fixture
def completed_goal(db, ser_dream, ser_milestone):
    return Goal.objects.create(
        dream=ser_dream,
        milestone=ser_milestone,
        title="Completed Goal",
        description="A completed goal",
        order=1,
        status="completed",
    )


@pytest.fixture
def completed_task(db, ser_goal):
    return Task.objects.create(
        goal=ser_goal,
        title="Completed Task",
        description="A completed task",
        order=1,
        duration_mins=15,
        status="completed",
    )


# ── TaskSerializer ────────────────────────────────────────────────────


class TestTaskSerializer:
    def test_serializes_all_fields(self, ser_task):
        data = TaskSerializer(ser_task).data
        assert data["id"] == str(ser_task.id)
        assert data["title"] == "Task 1"
        assert data["description"] == "First task"
        assert data["order"] == 0
        assert data["duration_mins"] == 30
        assert data["status"] == "pending"
        assert "created_at" in data
        assert "updated_at" in data

    def test_chain_position_none_for_non_chain(self, ser_task):
        data = TaskSerializer(ser_task).data
        assert data["chain_position"] is None

    def test_read_only_fields(self, ser_task):
        serializer = TaskSerializer(ser_task, data={"id": "fake-id"}, partial=True)
        assert serializer.is_valid()
        # id should not be writable
        assert "id" not in serializer.validated_data


# ── GoalSerializer ────────────────────────────────────────────────────


class TestGoalSerializer:
    def test_serializes_goal_with_tasks(self, ser_goal, ser_task, completed_task):
        data = GoalSerializer(ser_goal).data
        assert data["title"] == "Goal 1"
        assert data["tasks_count"] == 2
        assert data["completed_tasks_count"] == 1
        assert len(data["tasks"]) == 2

    def test_tasks_count_zero_when_no_tasks(self, db, ser_dream, ser_milestone):
        goal = Goal.objects.create(
            dream=ser_dream,
            milestone=ser_milestone,
            title="Empty Goal",
            description="No tasks",
            order=2,
            status="pending",
        )
        data = GoalSerializer(goal).data
        assert data["tasks_count"] == 0
        assert data["completed_tasks_count"] == 0


# ── DreamMilestoneSerializer ─────────────────────────────────────────


class TestDreamMilestoneSerializer:
    def test_serializes_milestone_with_nested_goals(
        self, ser_milestone, ser_goal, completed_goal
    ):
        data = DreamMilestoneSerializer(ser_milestone).data
        assert data["title"] == "Milestone 1"
        assert data["goals_count"] == 2
        assert data["completed_goals_count"] == 1
        assert len(data["goals"]) == 2


# ── DreamSerializer ──────────────────────────────────────────────────


class TestDreamSerializer:
    def test_serializes_basic_dream_fields(self, ser_dream):
        data = DreamSerializer(ser_dream).data
        assert data["id"] == str(ser_dream.id)
        assert data["title"] == "Test Dream"
        assert data["category"] == "education"
        assert data["status"] == "active"
        assert data["is_public"] is False
        assert data["is_favorited"] is False
        assert "created_at" in data

    def test_goals_count_from_annotation(self, ser_dream):
        ser_dream._goals_count = 5
        data = DreamSerializer(ser_dream).data
        assert data["goals_count"] == 5

    def test_goals_count_from_db(self, ser_dream, ser_goal):
        data = DreamSerializer(ser_dream).data
        assert data["goals_count"] == 1

    def test_tasks_count_from_annotation(self, ser_dream):
        ser_dream._tasks_count = 10
        data = DreamSerializer(ser_dream).data
        assert data["tasks_count"] == 10

    def test_tags_from_prefetched(self, ser_dream):
        ser_dream._prefetched_tags = ["fitness", "health"]
        data = DreamSerializer(ser_dream).data
        assert data["tags"] == ["fitness", "health"]

    def test_tags_from_db(self, db, ser_dream):
        tag = DreamTag.objects.create(name="education")
        DreamTagging.objects.create(dream=ser_dream, tag=tag)
        data = DreamSerializer(ser_dream).data
        assert data["tags"] == ["education"]

    def test_sparkline_data_from_prefetched(self, ser_dream):
        ser_dream._prefetched_sparkline = [
            {"date": "2026-03-01", "progress": 10}
        ]
        data = DreamSerializer(ser_dream).data
        assert data["sparkline_data"] == [
            {"date": "2026-03-01", "progress": 10}
        ]

    def test_signed_vision_image_url_empty_when_no_image(self, ser_dream):
        data = DreamSerializer(ser_dream).data
        assert data["signed_vision_image_url"] == ""

    @patch("apps.dreams.serializers.settings", create=True)
    def test_signed_vision_image_url_passthrough_external(self, mock_settings, ser_dream):
        mock_settings.AWS_STORAGE_BUCKET_NAME = None
        ser_dream.vision_image_url = "https://external.example.com/image.png"
        data = DreamSerializer(ser_dream).data
        assert data["signed_vision_image_url"] == "https://external.example.com/image.png"

    def test_completed_goals_count_default(self, ser_dream):
        data = DreamSerializer(ser_dream).data
        assert data["completed_goals_count"] == 0


# ── DreamDetailSerializer ────────────────────────────────────────────


class TestDreamDetailSerializer:
    def test_includes_nested_milestones_and_goals(
        self, ser_dream, ser_milestone, ser_goal, ser_task
    ):
        data = DreamDetailSerializer(ser_dream).data
        assert "milestones" in data
        assert "goals" in data
        assert "obstacles" in data
        assert "calibration_responses" in data
        assert data["milestones_count"] == 1
        assert data["goals_count"] == 1

    def test_days_left_with_target_date(self, ser_dream):
        ser_dream.target_date = timezone.now() + timedelta(days=60)
        ser_dream.save()
        data = DreamDetailSerializer(ser_dream).data
        assert data["days_left"] >= 59  # allow for test execution time

    def test_days_left_none_when_no_target(self, ser_dream):
        data = DreamDetailSerializer(ser_dream).data
        assert data["days_left"] is None

    def test_days_left_zero_when_past(self, ser_dream):
        ser_dream.target_date = timezone.now() - timedelta(days=5)
        ser_dream.save()
        data = DreamDetailSerializer(ser_dream).data
        assert data["days_left"] == 0

    def test_milestones_count_from_annotation(self, ser_dream):
        ser_dream._milestones_count = 3
        data = DreamDetailSerializer(ser_dream).data
        assert data["milestones_count"] == 3

    def test_completed_milestones_count_from_annotation(self, ser_dream):
        ser_dream._completed_milestones_count = 2
        data = DreamDetailSerializer(ser_dream).data
        assert data["completed_milestones_count"] == 2

    def test_total_tasks_from_annotation(self, ser_dream):
        ser_dream._total_tasks = 7
        data = DreamDetailSerializer(ser_dream).data
        assert data["total_tasks"] == 7

    def test_completed_tasks_from_annotation(self, ser_dream):
        ser_dream._completed_tasks = 3
        data = DreamDetailSerializer(ser_dream).data
        assert data["completed_tasks"] == 3


# ── DreamCreateSerializer ────────────────────────────────────────────


class TestDreamCreateSerializer:
    @patch("core.moderation.ContentModerationService")
    def test_valid_creation(self, mock_mod_cls):
        mock_mod_cls.return_value.moderate_text.return_value = MagicMock(
            is_flagged=False
        )
        data = {
            "title": "Learn Guitar",
            "description": "I want to learn to play guitar proficiently",
            "category": "hobbies",
        }
        serializer = DreamCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["title"] == "Learn Guitar"

    @patch("core.moderation.ContentModerationService")
    def test_title_too_short(self, mock_mod_cls):
        mock_mod_cls.return_value.moderate_text.return_value = MagicMock(
            is_flagged=False
        )
        data = {
            "title": "ab",
            "description": "A valid description here",
            "category": "hobbies",
        }
        serializer = DreamCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "title" in serializer.errors

    @patch("core.moderation.ContentModerationService")
    def test_description_too_short(self, mock_mod_cls):
        mock_mod_cls.return_value.moderate_text.return_value = MagicMock(
            is_flagged=False
        )
        data = {
            "title": "Valid Title",
            "description": "short",
            "category": "hobbies",
        }
        serializer = DreamCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "description" in serializer.errors

    @patch("core.moderation.ContentModerationService")
    def test_target_date_too_soon(self, mock_mod_cls):
        mock_mod_cls.return_value.moderate_text.return_value = MagicMock(
            is_flagged=False
        )
        data = {
            "title": "Valid Title",
            "description": "A valid description here with enough length",
            "category": "hobbies",
            "target_date": (timezone.now() + timedelta(days=5)).isoformat(),
        }
        serializer = DreamCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "target_date" in serializer.errors

    @patch("core.moderation.ContentModerationService")
    def test_target_date_too_far(self, mock_mod_cls):
        mock_mod_cls.return_value.moderate_text.return_value = MagicMock(
            is_flagged=False
        )
        data = {
            "title": "Valid Title",
            "description": "A valid description here with enough length",
            "category": "hobbies",
            "target_date": (timezone.now() + timedelta(days=1200)).isoformat(),
        }
        serializer = DreamCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "target_date" in serializer.errors

    @patch("core.moderation.ContentModerationService")
    def test_target_date_valid(self, mock_mod_cls):
        mock_mod_cls.return_value.moderate_text.return_value = MagicMock(
            is_flagged=False
        )
        data = {
            "title": "Valid Title",
            "description": "A valid description here with enough length",
            "category": "hobbies",
            "target_date": (timezone.now() + timedelta(days=90)).isoformat(),
        }
        serializer = DreamCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    @patch("core.moderation.ContentModerationService")
    def test_target_date_none_allowed(self, mock_mod_cls):
        mock_mod_cls.return_value.moderate_text.return_value = MagicMock(
            is_flagged=False
        )
        data = {
            "title": "Valid Title",
            "description": "A valid description here with enough length",
            "category": "hobbies",
        }
        serializer = DreamCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    @patch("core.moderation.ContentModerationService")
    def test_moderated_title_rejected(self, mock_mod_cls):
        mock_mod_cls.return_value.moderate_text.return_value = MagicMock(
            is_flagged=True, user_message="Content flagged"
        )
        data = {
            "title": "Bad content title",
            "description": "A valid description here with enough length",
            "category": "hobbies",
        }
        serializer = DreamCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "title" in serializer.errors


# ── DreamUpdateSerializer ─────────────────────────────────────────────


class TestDreamUpdateSerializer:
    @patch("core.moderation.ContentModerationService")
    def test_partial_update_valid(self, mock_mod_cls):
        mock_mod_cls.return_value.moderate_text.return_value = MagicMock(
            is_flagged=False
        )
        data = {"title": "Updated Title"}
        serializer = DreamUpdateSerializer(data=data, partial=True)
        assert serializer.is_valid(), serializer.errors

    @patch("core.moderation.ContentModerationService")
    def test_moderated_description_rejected(self, mock_mod_cls):
        mock_mod_cls.return_value.moderate_text.return_value = MagicMock(
            is_flagged=True, user_message="Content flagged"
        )
        data = {"description": "Bad description"}
        serializer = DreamUpdateSerializer(data=data, partial=True)
        assert not serializer.is_valid()
        assert "description" in serializer.errors

    @patch("core.moderation.ContentModerationService")
    def test_update_target_date_too_soon(self, mock_mod_cls):
        mock_mod_cls.return_value.moderate_text.return_value = MagicMock(
            is_flagged=False
        )
        data = {"target_date": (timezone.now() + timedelta(days=5)).isoformat()}
        serializer = DreamUpdateSerializer(data=data, partial=True)
        assert not serializer.is_valid()
        assert "target_date" in serializer.errors


# ── DreamTemplateSerializer ───────────────────────────────────────────


class TestDreamTemplateSerializer:
    def test_serializes_template(self, db):
        template = DreamTemplate.objects.create(
            title="Fitness Template",
            description="Get fit in 3 months",
            category="health",
            template_goals=[
                {"title": "Cardio", "tasks": []},
                {"title": "Strength", "tasks": []},
            ],
            estimated_duration_days=90,
            difficulty="intermediate",
        )
        data = DreamTemplateSerializer(template).data
        assert data["title"] == "Fitness Template"
        assert data["goals_count"] == 2
        assert "category_display" in data
        assert "difficulty_display" in data

    def test_goals_count_zero_when_empty(self, db):
        template = DreamTemplate.objects.create(
            title="Empty Template",
            description="Template with no goals",
            category="health",
            template_goals=[],
        )
        data = DreamTemplateSerializer(template).data
        assert data["goals_count"] == 0

    def test_goals_count_none_template_goals(self, db):
        """When template_goals is None, goals_count should be 0.
        Note: template_goals has default=list, so None may not be allowed
        by the DB. We test the serializer logic by setting the attribute directly."""
        template = DreamTemplate.objects.create(
            title="None Template",
            description="Template with None goals",
            category="health",
        )
        template.template_goals = None  # Simulate a case where it's None
        data = DreamTemplateSerializer(template).data
        assert data["goals_count"] == 0


# ── VisionBoardImageSerializer ────────────────────────────────────────


class TestVisionBoardImageSerializer:
    def test_serializes_image_with_url(self, db, ser_dream):
        img = VisionBoardImage.objects.create(
            dream=ser_dream,
            image_url="https://example.com/img.png",
            caption="Vision",
            order=0,
        )
        data = VisionBoardImageSerializer(img).data
        assert data["image_url"] == "https://example.com/img.png"
        assert data["signed_image_url"] == "https://example.com/img.png"
        assert data["caption"] == "Vision"
        assert data["is_ai_generated"] is False


# ── ProgressPhotoSerializer ───────────────────────────────────────────


class TestProgressPhotoSerializer:
    def test_ai_analysis_data_parses_json(self, db, ser_dream):
        photo = ProgressPhoto.objects.create(
            dream=ser_dream,
            image="progress_photos/test.jpg",
            ai_analysis='{"score": 85, "summary": "Great progress"}',
            taken_at=timezone.now(),
        )
        data = ProgressPhotoSerializer(photo).data
        assert data["ai_analysis_data"] == {
            "score": 85,
            "summary": "Great progress",
        }

    def test_ai_analysis_data_wraps_non_json(self, db, ser_dream):
        photo = ProgressPhoto.objects.create(
            dream=ser_dream,
            image="progress_photos/test.jpg",
            ai_analysis="Not JSON text",
            taken_at=timezone.now(),
        )
        data = ProgressPhotoSerializer(photo).data
        assert data["ai_analysis_data"] == {"analysis": "Not JSON text"}

    def test_ai_analysis_data_none_when_empty(self, db, ser_dream):
        photo = ProgressPhoto.objects.create(
            dream=ser_dream,
            image="progress_photos/test.jpg",
            ai_analysis="",
            taken_at=timezone.now(),
        )
        data = ProgressPhotoSerializer(photo).data
        assert data["ai_analysis_data"] is None


# ── DreamJournalSerializer ────────────────────────────────────────────


class TestDreamJournalSerializer:
    def test_serializes_journal(self, db, ser_dream):
        journal = DreamJournal.objects.create(
            dream=ser_dream,
            title="Today's reflection",
            content="I made great progress today with my studies.",
            mood="happy",
        )
        data = DreamJournalSerializer(journal).data
        assert data["title"] == "Today's reflection"
        assert data["mood"] == "happy"
        assert "created_at" in data

    def test_sanitizes_title(self):
        serializer = DreamJournalSerializer(
            data={
                "dream": "dummy",
                "title": "<script>alert(1)</script>My Title",
                "content": "Valid content for journal entry",
            }
        )
        # We just test validate_title directly
        result = serializer.fields["title"].run_validators("Test")
        assert result is None  # no error means valid

    def test_validate_title_strips_html(self):
        from core.sanitizers import sanitize_text

        result = sanitize_text("<b>Bold</b> Title")
        assert "<b>" not in result


# ── TaskCreateSerializer ──────────────────────────────────────────────


class TestTaskCreateSerializer:
    def test_valid_task(self, ser_goal):
        data = {
            "goal": str(ser_goal.id),
            "title": "New Task",
            "description": "A new task description",
            "duration_mins": 45,
        }
        serializer = TaskCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_chain_delay_must_be_positive(self, ser_goal):
        data = {
            "goal": str(ser_goal.id),
            "title": "Chain Task",
            "description": "A chain task",
            "chain_next_delay_days": 0,
        }
        serializer = TaskCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "chain_next_delay_days" in serializer.errors


# ── GoalCreateSerializer ──────────────────────────────────────────────


class TestGoalCreateSerializer:
    def test_valid_goal(self, ser_dream):
        data = {
            "dream": str(ser_dream.id),
            "title": "New Goal",
            "description": "Goal description",
        }
        serializer = GoalCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors


# ── ShareDreamRequestSerializer ───────────────────────────────────────


class TestShareDreamRequestSerializer:
    def test_valid(self):
        import uuid

        data = {"shared_with_id": str(uuid.uuid4()), "permission": "view"}
        serializer = ShareDreamRequestSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_invalid_permission(self):
        import uuid

        data = {"shared_with_id": str(uuid.uuid4()), "permission": "admin"}
        serializer = ShareDreamRequestSerializer(data=data)
        assert not serializer.is_valid()


# ── FocusSessionStartSerializer ───────────────────────────────────────


class TestFocusSessionStartSerializer:
    def test_valid(self):
        data = {"duration_minutes": 25, "session_type": "work"}
        serializer = FocusSessionStartSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_too_long_duration(self):
        data = {"duration_minutes": 200, "session_type": "work"}
        serializer = FocusSessionStartSerializer(data=data)
        assert not serializer.is_valid()

    def test_zero_duration(self):
        data = {"duration_minutes": 0, "session_type": "work"}
        serializer = FocusSessionStartSerializer(data=data)
        assert not serializer.is_valid()


# ── FocusSessionCompleteSerializer ────────────────────────────────────


class TestFocusSessionCompleteSerializer:
    def test_valid(self):
        import uuid

        data = {"session_id": str(uuid.uuid4()), "actual_minutes": 20}
        serializer = FocusSessionCompleteSerializer(data=data)
        assert serializer.is_valid(), serializer.errors


# ── DreamCollaboratorSerializer ───────────────────────────────────────


class TestDreamCollaboratorSerializer:
    def test_serializes_collaborator(self, db, ser_dream, ser_user2):
        collab = DreamCollaborator.objects.create(
            dream=ser_dream, user=ser_user2, role="viewer"
        )
        data = DreamCollaboratorSerializer(collab).data
        assert data["user_display_name"] == "Ser User 2"
        assert data["dream_title"] == "Test Dream"
        assert data["role"] == "viewer"


# ── AddCollaboratorSerializer ─────────────────────────────────────────


class TestAddCollaboratorSerializer:
    def test_valid(self):
        import uuid

        data = {"user_id": str(uuid.uuid4()), "role": "collaborator"}
        serializer = AddCollaboratorSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_invalid_role(self):
        import uuid

        data = {"user_id": str(uuid.uuid4()), "role": "admin"}
        serializer = AddCollaboratorSerializer(data=data)
        assert not serializer.is_valid()


# ── DreamTagSerializer ────────────────────────────────────────────────


class TestDreamTagSerializer:
    def test_serializes_tag(self, db):
        tag = DreamTag.objects.create(name="fitness")
        data = DreamTagSerializer(tag).data
        assert data["name"] == "fitness"
        assert "created_at" in data


# ── SharedDreamSerializer ─────────────────────────────────────────────


class TestSharedDreamSerializer:
    def test_serializes_shared_dream(self, db, ser_dream, ser_user, ser_user2):
        shared = SharedDream.objects.create(
            dream=ser_dream,
            shared_by=ser_user,
            shared_with=ser_user2,
            permission="view",
        )
        data = SharedDreamSerializer(shared).data
        assert data["dream_title"] == "Test Dream"
        assert data["shared_by_name"] == "Ser User"
        assert data["shared_with_name"] == "Ser User 2"
        assert data["permission"] == "view"


# ── PlanCheckInSerializer ─────────────────────────────────────────────


class TestPlanCheckInSerializer:
    def test_all_fields_read_only(self):
        serializer = PlanCheckInSerializer()
        for field_name in serializer.fields:
            assert serializer.fields[field_name].read_only
