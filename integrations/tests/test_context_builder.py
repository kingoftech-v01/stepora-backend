"""
Tests for integrations.context_builder — build_dream_context and helpers.

All functions query real Django models, so these are @pytest.mark.django_db tests.
"""

import json
from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.dreams.models import (
    CalibrationResponse,
    Dream,
    DreamMilestone,
    Goal,
    Obstacle,
    PlanCheckIn,
)
from apps.users.models import User
from integrations.context_builder import (
    _build_ai_analysis,
    _build_calibration,
    _build_checkin_history,
    _build_dream_identity,
    _build_obstacles,
    _build_persona,
    build_dream_context,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ctx_user(db):
    return User.objects.create_user(
        email="ctx@example.com",
        password="testpassword123",
        display_name="Ctx User",
        persona={
            "available_hours_per_week": 10,
            "preferred_schedule": "morning",
            "occupation": "Developer",
            "global_motivation": "Be healthier",
            "astrological_sign": "Aries",
        },
        work_schedule={"monday": "9-17", "tuesday": "9-17"},
    )


@pytest.fixture
def ctx_dream(db, ctx_user):
    return Dream.objects.create(
        user=ctx_user,
        title="Run a Marathon",
        description="Complete a full marathon in under 4 hours",
        category="health",
        status="active",
        target_date=timezone.now() + timedelta(days=365),
        ai_analysis={"analysis": "This is a challenging but achievable goal"},
    )


@pytest.fixture
def ctx_dream_no_analysis(db, ctx_user):
    return Dream.objects.create(
        user=ctx_user,
        title="Learn Guitar",
        description="",
        status="active",
    )


# ===================================================================
# build_dream_context() — full pipeline
# ===================================================================

class TestBuildDreamContext:

    def test_minimal_dream(self, ctx_dream_no_analysis, ctx_user):
        result = build_dream_context(ctx_dream_no_analysis, ctx_user)
        assert "=== DREAM CONTEXT ===" in result
        assert "Learn Guitar" in result

    def test_full_dream(self, ctx_dream, ctx_user):
        # Add calibration, obstacles
        CalibrationResponse.objects.create(
            dream=ctx_dream, question="Fitness level?", answer="Intermediate",
            question_number=1, category="experience",
        )
        ms = DreamMilestone.objects.create(
            dream=ctx_dream, title="Month 1", order=1, status="pending"
        )
        Goal.objects.create(
            dream=ctx_dream, milestone=ms, title="G1", order=1, status="pending"
        )
        Obstacle.objects.create(
            dream=ctx_dream, title="Injury risk", description="Potential knee injury",
            obstacle_type="predicted", status="active", solution="See a physio",
        )
        result = build_dream_context(ctx_dream, ctx_user)
        assert "=== DREAM CONTEXT ===" in result
        assert "=== AI INITIAL ANALYSIS ===" in result
        assert "=== CALIBRATION RESPONSES ===" in result
        assert "=== USER PERSONA ===" in result
        assert "=== ACTIVE OBSTACLES ===" in result

    def test_no_optional_sections(self, ctx_dream_no_analysis, ctx_user):
        """Dream without analysis, calibration, checkins, or obstacles."""
        result = build_dream_context(ctx_dream_no_analysis, ctx_user)
        assert "=== AI INITIAL ANALYSIS ===" not in result
        assert "=== CALIBRATION RESPONSES ===" not in result
        assert "=== PREVIOUS CHECK-INS" not in result
        assert "=== ACTIVE OBSTACLES ===" not in result


# ===================================================================
# _build_dream_identity()
# ===================================================================

class TestBuildDreamIdentity:

    def test_with_target_date(self, ctx_dream):
        result = _build_dream_identity(ctx_dream)
        assert "Run a Marathon" in result
        assert "Target date:" in result
        assert "Timeline:" in result
        assert "Current progress:" in result

    def test_without_target_date(self, ctx_dream_no_analysis):
        result = _build_dream_identity(ctx_dream_no_analysis)
        assert "Learn Guitar" in result
        assert "Target date:" not in result

    def test_with_category(self, ctx_dream):
        result = _build_dream_identity(ctx_dream)
        assert "Category: health" in result

    def test_no_description(self, ctx_dream_no_analysis):
        result = _build_dream_identity(ctx_dream_no_analysis)
        assert "(no description)" in result


# ===================================================================
# _build_ai_analysis()
# ===================================================================

class TestBuildAiAnalysis:

    def test_dict_analysis(self, ctx_dream):
        result = _build_ai_analysis(ctx_dream)
        assert "=== AI INITIAL ANALYSIS ===" in result
        assert "challenging but achievable" in result

    def test_string_analysis(self, ctx_dream):
        ctx_dream.ai_analysis = "Simple string analysis"
        result = _build_ai_analysis(ctx_dream)
        assert "Simple string analysis" in result

    def test_long_analysis_truncated(self, ctx_dream):
        ctx_dream.ai_analysis = "X" * 1000
        result = _build_ai_analysis(ctx_dream)
        assert result.endswith("...")
        assert len(result) < 1000

    def test_non_string_non_dict(self, ctx_dream):
        ctx_dream.ai_analysis = 12345
        result = _build_ai_analysis(ctx_dream)
        assert "12345" in result

    def test_dict_without_analysis_key(self, ctx_dream):
        ctx_dream.ai_analysis = {"other_key": "value"}
        result = _build_ai_analysis(ctx_dream)
        # Should dump the whole dict
        assert "other_key" in result


# ===================================================================
# _build_calibration()
# ===================================================================

class TestBuildCalibration:

    def test_no_responses(self, ctx_dream):
        result = _build_calibration(ctx_dream)
        assert result is None

    def test_with_responses(self, ctx_dream):
        CalibrationResponse.objects.create(
            dream=ctx_dream, question="What is your experience?",
            answer="I am a beginner", question_number=1, category="experience",
        )
        CalibrationResponse.objects.create(
            dream=ctx_dream, question="Budget?",
            answer="100 euros", question_number=2,
        )
        result = _build_calibration(ctx_dream)
        assert "=== CALIBRATION RESPONSES ===" in result
        assert "Q1 [experience]:" in result
        assert "Q2:" in result
        assert "I am a beginner" in result

    def test_long_answer_truncated(self, ctx_dream):
        CalibrationResponse.objects.create(
            dream=ctx_dream, question="Q1",
            answer="A" * 500, question_number=1,
        )
        result = _build_calibration(ctx_dream)
        assert "..." in result

    def test_no_answer(self, ctx_dream):
        CalibrationResponse.objects.create(
            dream=ctx_dream, question="Q1",
            answer="", question_number=1,
        )
        result = _build_calibration(ctx_dream)
        assert "(no answer)" in result


# ===================================================================
# _build_persona()
# ===================================================================

class TestBuildPersona:

    def test_with_persona(self, ctx_user):
        result = _build_persona(ctx_user)
        assert "=== USER PERSONA ===" in result
        assert "Available hours/week: 10" in result
        assert "Occupation: Developer" in result
        assert "Astrological sign: Aries" in result

    def test_no_persona(self, ctx_user):
        ctx_user.persona = None
        result = _build_persona(ctx_user)
        assert result is None

    def test_empty_persona(self, ctx_user):
        ctx_user.persona = {}
        result = _build_persona(ctx_user)
        assert result is None

    def test_with_work_schedule(self, ctx_user):
        result = _build_persona(ctx_user)
        assert "Work schedule:" in result

    def test_no_work_schedule(self, ctx_user):
        ctx_user.work_schedule = None
        result = _build_persona(ctx_user)
        assert result is not None
        assert "Work schedule:" not in result


# ===================================================================
# _build_checkin_history()
# ===================================================================

class TestBuildCheckinHistory:

    def test_no_checkins(self, ctx_dream):
        result = _build_checkin_history(ctx_dream)
        assert result is None

    def test_with_checkins(self, ctx_dream):
        ci1 = PlanCheckIn.objects.create(
            dream=ctx_dream, status="completed",
            scheduled_for=timezone.now() - timedelta(days=2),
            completed_at=timezone.now() - timedelta(days=1),
            coaching_message="Great progress!",
            pace_status="on_track",
            adjustment_summary="Shifted dates",
            user_responses={"satisfaction": 5},
        )
        ci2 = PlanCheckIn.objects.create(
            dream=ctx_dream, status="completed",
            scheduled_for=timezone.now() - timedelta(days=15),
            completed_at=timezone.now() - timedelta(days=14),
            coaching_message="Keep going!",
            pace_status="behind",
        )
        result = _build_checkin_history(ctx_dream)
        assert result is not None
        assert "=== PREVIOUS CHECK-INS" in result
        assert "most recent" in result
        assert "on_track" in result
        assert "Great progress!" in result

    def test_long_coaching_message_truncated(self, ctx_dream):
        PlanCheckIn.objects.create(
            dream=ctx_dream, status="completed",
            scheduled_for=timezone.now() - timedelta(days=1),
            completed_at=timezone.now(),
            coaching_message="X" * 500,
        )
        result = _build_checkin_history(ctx_dream)
        assert "..." in result

    def test_long_user_responses_truncated(self, ctx_dream):
        PlanCheckIn.objects.create(
            dream=ctx_dream, status="completed",
            scheduled_for=timezone.now() - timedelta(days=1),
            completed_at=timezone.now(),
            user_responses={"key": "value" * 200},
        )
        result = _build_checkin_history(ctx_dream)
        assert "..." in result

    def test_pending_checkins_excluded(self, ctx_dream):
        PlanCheckIn.objects.create(
            dream=ctx_dream, status="pending",
            scheduled_for=timezone.now(),
            coaching_message="Should not appear",
        )
        result = _build_checkin_history(ctx_dream)
        assert result is None


# ===================================================================
# _build_obstacles()
# ===================================================================

class TestBuildObstacles:

    def test_no_obstacles(self, ctx_dream):
        result = _build_obstacles(ctx_dream)
        assert result is None

    def test_with_obstacles(self, ctx_dream):
        ms = DreamMilestone.objects.create(
            dream=ctx_dream, title="Month 1", order=1, status="pending"
        )
        Obstacle.objects.create(
            dream=ctx_dream, milestone=ms,
            title="Time management", description="Hard to find time",
            obstacle_type="predicted", status="active",
            solution="Use a calendar",
        )
        result = _build_obstacles(ctx_dream)
        assert "=== ACTIVE OBSTACLES ===" in result
        assert "Time management" in result
        assert "milestone: Month 1" in result
        assert "Use a calendar" in result

    def test_goal_level_obstacle(self, ctx_dream):
        goal = Goal.objects.create(
            dream=ctx_dream, title="Goal 1", order=1, status="pending"
        )
        Obstacle.objects.create(
            dream=ctx_dream, goal=goal,
            title="Motivation dip", description="Feeling unmotivated",
            obstacle_type="actual", status="active",
        )
        result = _build_obstacles(ctx_dream)
        assert "goal: Goal 1" in result

    def test_resolved_obstacles_excluded(self, ctx_dream):
        Obstacle.objects.create(
            dream=ctx_dream,
            title="Old obstacle", description="D",
            obstacle_type="predicted", status="resolved",
        )
        result = _build_obstacles(ctx_dream)
        assert result is None

    def test_no_solution(self, ctx_dream):
        Obstacle.objects.create(
            dream=ctx_dream,
            title="No solution obstacle", description="D",
            obstacle_type="predicted", status="active",
        )
        result = _build_obstacles(ctx_dream)
        assert "No solution obstacle" in result
        assert "Suggested solution:" not in result
