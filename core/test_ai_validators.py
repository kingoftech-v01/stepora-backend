"""
Tests for core/ai_validators.py — Pydantic validation schemas and validation functions.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from .ai_validators import (
    _clamp_int,
    _sanitize_str,
    PlanTaskSchema,
    PlanGoalSchema,
    PlanObstacleSchema,
    PlanResponseSchema,
    AnalysisResponseSchema,
    CalibrationQuestionSchema,
    CalibrationQuestionsResponseSchema,
    UserProfileSchema,
    PlanRecommendationsSchema,
    CalibrationSummaryResponseSchema,
    ChatResponseSchema,
    FunctionCallSchema,
    AIValidationError,
    validate_plan_response,
    validate_analysis_response,
    validate_calibration_questions,
    validate_calibration_summary,
    validate_chat_response,
    validate_function_call,
    check_plan_calibration_coherence,
    VALID_CATEGORIES,
    VALID_DIFFICULTIES,
    VALID_EXPERIENCE_LEVELS,
    VALID_PACES,
    VALID_RISK_LEVELS,
    VALID_CALIBRATION_CATEGORIES,
    MAX_TITLE_LEN,
    MAX_DESCRIPTION_LEN,
    MAX_TEXT_LEN,
    MAX_SHORT_TEXT_LEN,
)


# ===================================================================
# Helper functions
# ===================================================================

class TestClampInt:
    """Test _clamp_int helper."""

    def test_within_range(self):
        assert _clamp_int(5, 0, 10) == 5

    def test_below_range(self):
        assert _clamp_int(-5, 0, 10) == 0

    def test_above_range(self):
        assert _clamp_int(15, 0, 10) == 10

    def test_none_returns_none(self):
        assert _clamp_int(None, 0, 10) is None

    def test_at_boundaries(self):
        assert _clamp_int(0, 0, 10) == 0
        assert _clamp_int(10, 0, 10) == 10


class TestSanitizeStr:
    """Test _sanitize_str helper."""

    def test_none_returns_empty(self):
        assert _sanitize_str(None) == ""

    def test_strips_html(self):
        result = _sanitize_str('<script>alert("xss")</script>Hello')
        assert '<script>' not in result
        assert 'Hello' in result

    def test_truncates_to_max_len(self):
        long_str = "a" * 20000
        result = _sanitize_str(long_str, max_len=100)
        assert len(result) <= 100

    def test_normal_string_passes_through(self):
        result = _sanitize_str("Hello World", max_len=500)
        assert result == "Hello World"


# ===================================================================
# PlanTaskSchema
# ===================================================================

class TestPlanTaskSchema:
    """Test PlanTaskSchema validation."""

    def test_valid_task(self):
        task = PlanTaskSchema(
            title="Write tests",
            description="Cover all edge cases",
            order=1,
            duration_mins=60,
            reasoning="Tests improve reliability",
        )
        assert task.title == "Write tests"
        assert task.order == 1
        assert task.duration_mins == 60

    def test_sanitizes_title(self):
        task = PlanTaskSchema(
            title='<b>Bold task</b>',
            order=0,
        )
        assert '<b>' not in task.title
        assert 'Bold task' in task.title

    def test_coerces_order_from_string(self):
        task = PlanTaskSchema(title="Task", order="5", duration_mins=30)
        assert task.order == 5

    def test_coerces_invalid_order_to_zero(self):
        task = PlanTaskSchema(title="Task", order="abc")
        assert task.order == 0

    def test_coerces_duration_from_string(self):
        task = PlanTaskSchema(title="Task", order=0, duration_mins="45")
        assert task.duration_mins == 45

    def test_coerces_invalid_duration_raises(self):
        """Coercer returns 0, but ge=1 constraint rejects it."""
        with pytest.raises(PydanticValidationError):
            PlanTaskSchema(title="Task", order=0, duration_mins="invalid")

    def test_default_values(self):
        task = PlanTaskSchema(title="Task", order=0)
        assert task.description == ""
        assert task.duration_mins == 30
        assert task.reasoning == ""

    def test_sanitizes_none_fields(self):
        task = PlanTaskSchema(title="Task", order=0, description=None)
        assert task.description == ""


# ===================================================================
# PlanGoalSchema
# ===================================================================

class TestPlanGoalSchema:
    """Test PlanGoalSchema validation."""

    def test_valid_goal(self):
        goal = PlanGoalSchema(
            title="Learn Python",
            description="Master the language",
            order=0,
            estimated_minutes=600,
            tasks=[{"title": "Read docs", "order": 0}],
            reasoning="Good foundation",
        )
        assert goal.title == "Learn Python"
        assert len(goal.tasks) == 1

    def test_sanitizes_strings(self):
        goal = PlanGoalSchema(
            title='<script>alert(1)</script>Goal',
            order=0,
            tasks=[{"title": "Task 1", "order": 0}],
        )
        assert '<script>' not in goal.title

    def test_coerces_order(self):
        goal = PlanGoalSchema(
            title="Goal",
            order="3",
            tasks=[{"title": "Task", "order": 0}],
        )
        assert goal.order == 3

    def test_coerces_invalid_order(self):
        goal = PlanGoalSchema(
            title="Goal",
            order="abc",
            tasks=[{"title": "Task", "order": 0}],
        )
        assert goal.order == 0

    def test_requires_at_least_one_task(self):
        with pytest.raises(PydanticValidationError):
            PlanGoalSchema(title="Goal", order=0, tasks=[])

    def test_estimated_minutes_none(self):
        goal = PlanGoalSchema(
            title="Goal", order=0,
            estimated_minutes=None,
            tasks=[{"title": "Task", "order": 0}],
        )
        assert goal.estimated_minutes is None

    def test_coerces_estimated_minutes_from_string(self):
        goal = PlanGoalSchema(
            title="Goal", order=0,
            estimated_minutes="120",
            tasks=[{"title": "Task", "order": 0}],
        )
        assert goal.estimated_minutes == 120

    def test_coerces_invalid_estimated_minutes(self):
        goal = PlanGoalSchema(
            title="Goal", order=0,
            estimated_minutes="abc",
            tasks=[{"title": "Task", "order": 0}],
        )
        assert goal.estimated_minutes is None


# ===================================================================
# PlanObstacleSchema
# ===================================================================

class TestPlanObstacleSchema:
    """Test PlanObstacleSchema validation."""

    def test_valid_obstacle(self):
        obstacle = PlanObstacleSchema(
            title="Time constraints",
            description="Limited free time",
            solution="Schedule dedicated blocks",
            evidence="User mentioned 5h/week",
        )
        assert obstacle.title == "Time constraints"

    def test_sanitizes_strings(self):
        obstacle = PlanObstacleSchema(
            title='<img onerror=alert(1)>Obstacle',
        )
        assert '<img' not in obstacle.title

    def test_default_empty_strings(self):
        obstacle = PlanObstacleSchema(title="Obstacle")
        assert obstacle.description == ""
        assert obstacle.solution == ""
        assert obstacle.evidence == ""


# ===================================================================
# PlanResponseSchema
# ===================================================================

class TestPlanResponseSchema:
    """Test PlanResponseSchema validation."""

    def _valid_plan_data(self):
        return {
            "analysis": "Good plan for a beginner",
            "estimated_duration_weeks": 12,
            "weekly_time_hours": 5,
            "goals": [
                {
                    "title": "Goal 1",
                    "order": 0,
                    "tasks": [{"title": "Task 1", "order": 0}],
                }
            ],
            "tips": ["Stay consistent"],
            "calibration_references": ["User wants 5h/week"],
        }

    def test_valid_plan(self):
        data = self._valid_plan_data()
        plan = PlanResponseSchema.model_validate(data)
        assert len(plan.goals) == 1
        assert plan.estimated_duration_weeks == 12

    def test_sanitizes_analysis(self):
        data = self._valid_plan_data()
        data["analysis"] = '<script>bad</script>Analysis'
        plan = PlanResponseSchema.model_validate(data)
        assert '<script>' not in plan.analysis

    def test_coerces_duration_from_string(self):
        data = self._valid_plan_data()
        data["estimated_duration_weeks"] = "24"
        plan = PlanResponseSchema.model_validate(data)
        assert plan.estimated_duration_weeks == 24

    def test_coerces_invalid_duration(self):
        data = self._valid_plan_data()
        data["estimated_duration_weeks"] = "abc"
        plan = PlanResponseSchema.model_validate(data)
        assert plan.estimated_duration_weeks == 12

    def test_coerces_hours_from_string(self):
        data = self._valid_plan_data()
        data["weekly_time_hours"] = "10"
        plan = PlanResponseSchema.model_validate(data)
        assert plan.weekly_time_hours == 10

    def test_sanitizes_tips(self):
        data = self._valid_plan_data()
        data["tips"] = ['<b>Tip 1</b>', None, '', 'Tip 2']
        plan = PlanResponseSchema.model_validate(data)
        assert '<b>' not in plan.tips[0]
        # None and empty string filtered out
        assert len(plan.tips) == 2

    def test_sanitizes_references(self):
        data = self._valid_plan_data()
        data["calibration_references"] = ['<em>Ref</em>', 'Normal']
        plan = PlanResponseSchema.model_validate(data)
        assert '<em>' not in plan.calibration_references[0]

    def test_tips_non_list_returns_empty(self):
        data = self._valid_plan_data()
        data["tips"] = "not a list"
        plan = PlanResponseSchema.model_validate(data)
        assert plan.tips == []

    def test_refs_non_list_returns_empty(self):
        data = self._valid_plan_data()
        data["calibration_references"] = "not a list"
        plan = PlanResponseSchema.model_validate(data)
        assert plan.calibration_references == []

    def test_requires_at_least_one_goal(self):
        data = self._valid_plan_data()
        data["goals"] = []
        with pytest.raises(PydanticValidationError):
            PlanResponseSchema.model_validate(data)

    def test_obstacles_optional(self):
        data = self._valid_plan_data()
        plan = PlanResponseSchema.model_validate(data)
        assert plan.potential_obstacles == []


# ===================================================================
# AnalysisResponseSchema
# ===================================================================

class TestAnalysisResponseSchema:
    """Test AnalysisResponseSchema validation."""

    def test_valid_analysis(self):
        analysis = AnalysisResponseSchema(
            category="career",
            estimated_duration_weeks=8,
            difficulty="hard",
            key_challenges=["Time", "Budget"],
            recommended_approach="Start small",
        )
        assert analysis.category == "career"
        assert analysis.difficulty == "hard"

    def test_invalid_category_defaults_to_other(self):
        analysis = AnalysisResponseSchema(category="invalid_category")
        assert analysis.category == "other"

    def test_invalid_difficulty_defaults_to_medium(self):
        analysis = AnalysisResponseSchema(difficulty="extreme")
        assert analysis.difficulty == "medium"

    def test_valid_categories(self):
        for cat in VALID_CATEGORIES:
            analysis = AnalysisResponseSchema(category=cat)
            assert analysis.category == cat

    def test_valid_difficulties(self):
        for diff in VALID_DIFFICULTIES:
            analysis = AnalysisResponseSchema(difficulty=diff)
            assert analysis.difficulty == diff

    def test_coerces_duration(self):
        analysis = AnalysisResponseSchema(estimated_duration_weeks="16")
        assert analysis.estimated_duration_weeks == 16

    def test_sanitizes_challenges(self):
        analysis = AnalysisResponseSchema(
            key_challenges=['<b>Challenge</b>', 'Normal']
        )
        assert '<b>' not in analysis.key_challenges[0]

    def test_challenges_non_list_returns_empty(self):
        analysis = AnalysisResponseSchema(key_challenges="not a list")
        assert analysis.key_challenges == []

    def test_sanitizes_approach(self):
        analysis = AnalysisResponseSchema(
            recommended_approach='<script>alert(1)</script>Approach'
        )
        assert '<script>' not in analysis.recommended_approach


# ===================================================================
# CalibrationQuestionSchema
# ===================================================================

class TestCalibrationQuestionSchema:
    """Test CalibrationQuestionSchema validation."""

    def test_valid_question(self):
        q = CalibrationQuestionSchema(
            question="What is your experience level?",
            category="experience",
        )
        assert q.question == "What is your experience level?"
        assert q.category == "experience"

    def test_sanitizes_question(self):
        q = CalibrationQuestionSchema(
            question='<b>What</b> is your goal?',
            category="specifics",
        )
        assert '<b>' not in q.question

    def test_invalid_category_defaults_to_specifics(self):
        q = CalibrationQuestionSchema(
            question="Valid question here?",
            category="invalid",
        )
        assert q.category == "specifics"

    def test_valid_categories(self):
        for cat in VALID_CALIBRATION_CATEGORIES:
            q = CalibrationQuestionSchema(
                question="A valid question for test?",
                category=cat,
            )
            assert q.category == cat


# ===================================================================
# CalibrationQuestionsResponseSchema
# ===================================================================

class TestCalibrationQuestionsResponseSchema:
    """Test CalibrationQuestionsResponseSchema validation."""

    def test_valid_response(self):
        resp = CalibrationQuestionsResponseSchema(
            sufficient=True,
            confidence_score=0.8,
            missing_areas=["timeline"],
            questions=[
                {"question": "What is your timeline?", "category": "timeline"}
            ],
        )
        assert resp.sufficient is True
        assert resp.confidence_score == 0.8

    def test_coerces_confidence_below_zero(self):
        resp = CalibrationQuestionsResponseSchema(confidence_score=-0.5)
        assert resp.confidence_score == 0.0

    def test_coerces_confidence_above_one(self):
        resp = CalibrationQuestionsResponseSchema(confidence_score=1.5)
        assert resp.confidence_score == 1.0

    def test_coerces_invalid_confidence(self):
        resp = CalibrationQuestionsResponseSchema(confidence_score="abc")
        assert resp.confidence_score == 0.5

    def test_sanitizes_missing_areas(self):
        resp = CalibrationQuestionsResponseSchema(
            missing_areas=['<b>Budget</b>', 'Timeline']
        )
        assert '<b>' not in resp.missing_areas[0]

    def test_missing_areas_non_list_returns_empty(self):
        resp = CalibrationQuestionsResponseSchema(missing_areas="not a list")
        assert resp.missing_areas == []

    def test_defaults(self):
        resp = CalibrationQuestionsResponseSchema()
        assert resp.sufficient is False
        assert resp.confidence_score == 0.5
        assert resp.missing_areas == []
        assert resp.questions == []


# ===================================================================
# UserProfileSchema
# ===================================================================

class TestUserProfileSchema:
    """Test UserProfileSchema validation."""

    def test_valid_profile(self):
        profile = UserProfileSchema(
            experience_level="advanced",
            available_hours_per_week=10,
            risk_tolerance="high",
            primary_motivation="Career growth",
        )
        assert profile.experience_level == "advanced"
        assert profile.available_hours_per_week == 10
        assert profile.risk_tolerance == "high"

    def test_invalid_experience_defaults_to_beginner(self):
        profile = UserProfileSchema(experience_level="expert")
        assert profile.experience_level == "beginner"

    def test_invalid_risk_defaults_to_medium(self):
        profile = UserProfileSchema(risk_tolerance="extreme")
        assert profile.risk_tolerance == "medium"

    def test_coerces_hours_from_string(self):
        profile = UserProfileSchema(available_hours_per_week="15")
        assert profile.available_hours_per_week == 15

    def test_clamps_hours_low(self):
        profile = UserProfileSchema(available_hours_per_week=0)
        assert profile.available_hours_per_week == 1

    def test_clamps_hours_high(self):
        profile = UserProfileSchema(available_hours_per_week=200)
        assert profile.available_hours_per_week == 168

    def test_invalid_hours_defaults_to_5(self):
        profile = UserProfileSchema(available_hours_per_week="abc")
        assert profile.available_hours_per_week == 5

    def test_sanitizes_string_fields(self):
        profile = UserProfileSchema(
            primary_motivation='<script>alert(1)</script>Career',
        )
        assert '<script>' not in profile.primary_motivation

    def test_sanitizes_list_fields(self):
        profile = UserProfileSchema(
            tools_available=['<b>Laptop</b>', 'Phone'],
            secondary_motivations=['<em>Fun</em>'],
            known_constraints=['<img src=x>Time'],
        )
        assert '<b>' not in profile.tools_available[0]
        assert '<em>' not in profile.secondary_motivations[0]
        assert '<img' not in profile.known_constraints[0]

    def test_non_list_returns_empty(self):
        profile = UserProfileSchema(tools_available="not a list")
        assert profile.tools_available == []

    def test_valid_experience_levels(self):
        for level in VALID_EXPERIENCE_LEVELS:
            profile = UserProfileSchema(experience_level=level)
            assert profile.experience_level == level

    def test_valid_risk_levels(self):
        for risk in VALID_RISK_LEVELS:
            profile = UserProfileSchema(risk_tolerance=risk)
            assert profile.risk_tolerance == risk

    def test_defaults(self):
        profile = UserProfileSchema()
        assert profile.experience_level == "beginner"
        assert profile.available_hours_per_week == 5
        assert profile.risk_tolerance == "medium"
        assert profile.budget == ""
        assert profile.tools_available == []


# ===================================================================
# PlanRecommendationsSchema
# ===================================================================

class TestPlanRecommendationsSchema:
    """Test PlanRecommendationsSchema validation."""

    def test_valid_recommendations(self):
        rec = PlanRecommendationsSchema(
            suggested_pace="aggressive",
            focus_areas=["Consistency", "Budget"],
            potential_pitfalls=["Burnout"],
            personalization_notes="User prefers mornings",
        )
        assert rec.suggested_pace == "aggressive"

    def test_invalid_pace_defaults_to_moderate(self):
        rec = PlanRecommendationsSchema(suggested_pace="supersonic")
        assert rec.suggested_pace == "moderate"

    def test_valid_paces(self):
        for pace in VALID_PACES:
            rec = PlanRecommendationsSchema(suggested_pace=pace)
            assert rec.suggested_pace == pace

    def test_sanitizes_lists(self):
        rec = PlanRecommendationsSchema(
            focus_areas=['<b>Area</b>'],
            potential_pitfalls=['<script>pitfall</script>'],
        )
        assert '<b>' not in rec.focus_areas[0]
        assert '<script>' not in rec.potential_pitfalls[0]

    def test_non_list_returns_empty(self):
        rec = PlanRecommendationsSchema(focus_areas="not a list")
        assert rec.focus_areas == []

    def test_sanitizes_notes(self):
        rec = PlanRecommendationsSchema(
            personalization_notes='<script>bad</script>Notes'
        )
        assert '<script>' not in rec.personalization_notes


# ===================================================================
# CalibrationSummaryResponseSchema
# ===================================================================

class TestCalibrationSummaryResponseSchema:
    """Test CalibrationSummaryResponseSchema validation."""

    def test_valid_summary(self):
        summary = CalibrationSummaryResponseSchema(
            user_profile={"experience_level": "advanced"},
            plan_recommendations={"suggested_pace": "aggressive"},
            enriched_description="Enhanced dream description",
        )
        assert summary.user_profile.experience_level == "advanced"
        assert summary.plan_recommendations.suggested_pace == "aggressive"

    def test_defaults(self):
        summary = CalibrationSummaryResponseSchema()
        assert summary.user_profile.experience_level == "beginner"
        assert summary.plan_recommendations.suggested_pace == "moderate"
        assert summary.enriched_description == ""

    def test_sanitizes_description(self):
        summary = CalibrationSummaryResponseSchema(
            enriched_description='<script>xss</script>Description'
        )
        assert '<script>' not in summary.enriched_description


# ===================================================================
# ChatResponseSchema
# ===================================================================

class TestChatResponseSchema:
    """Test ChatResponseSchema validation."""

    def test_valid_chat_response(self):
        resp = ChatResponseSchema(
            content="Here's your answer",
            tokens_used=150,
            model="gpt-4",
        )
        assert resp.content == "Here's your answer"
        assert resp.tokens_used == 150
        assert resp.model == "gpt-4"

    def test_sanitizes_none_content(self):
        resp = ChatResponseSchema(content=None)
        assert resp.content == ""

    def test_coerces_tokens_from_string(self):
        resp = ChatResponseSchema(tokens_used="100")
        assert resp.tokens_used == 100

    def test_coerces_negative_tokens_to_zero(self):
        resp = ChatResponseSchema(tokens_used=-5)
        assert resp.tokens_used == 0

    def test_coerces_invalid_tokens_to_zero(self):
        resp = ChatResponseSchema(tokens_used="abc")
        assert resp.tokens_used == 0

    def test_defaults(self):
        resp = ChatResponseSchema()
        assert resp.content == ""
        assert resp.tokens_used == 0
        assert resp.model == ""


# ===================================================================
# FunctionCallSchema
# ===================================================================

class TestFunctionCallSchema:
    """Test FunctionCallSchema validation."""

    def test_valid_function_call(self):
        fc = FunctionCallSchema(
            name="create_task",
            arguments={"title": "New task", "priority": "high"},
        )
        assert fc.name == "create_task"
        assert fc.arguments["title"] == "New task"

    def test_all_allowed_functions(self):
        for fn in FunctionCallSchema.ALLOWED_FUNCTIONS:
            fc = FunctionCallSchema(name=fn)
            assert fc.name == fn

    def test_unknown_function_raises(self):
        with pytest.raises(PydanticValidationError):
            FunctionCallSchema(name="delete_database")

    def test_empty_arguments_default(self):
        fc = FunctionCallSchema(name="create_task")
        assert fc.arguments == {}


# ===================================================================
# AIValidationError
# ===================================================================

class TestAIValidationError:
    """Test AIValidationError exception."""

    def test_message(self):
        error = AIValidationError("Invalid plan")
        assert str(error) == "Invalid plan"
        assert error.message == "Invalid plan"

    def test_errors_list(self):
        errors = ["field1 required", "field2 invalid"]
        error = AIValidationError("Validation failed", errors=errors)
        assert error.errors == errors

    def test_default_errors_empty(self):
        error = AIValidationError("Error")
        assert error.errors == []

    def test_isinstance_exception(self):
        error = AIValidationError("Error")
        assert isinstance(error, Exception)


# ===================================================================
# Public validation functions
# ===================================================================

class TestValidatePlanResponse:
    """Test validate_plan_response function."""

    def test_valid_plan(self):
        raw = {
            "analysis": "Analysis",
            "goals": [
                {
                    "title": "Goal",
                    "order": 0,
                    "tasks": [{"title": "Task", "order": 0}],
                }
            ],
        }
        plan = validate_plan_response(raw)
        assert isinstance(plan, PlanResponseSchema)

    def test_invalid_plan_raises_ai_error(self):
        with pytest.raises(AIValidationError, match="invalid plan"):
            validate_plan_response({"goals": []})

    def test_missing_goals_raises(self):
        with pytest.raises(AIValidationError):
            validate_plan_response({})


class TestValidateAnalysisResponse:
    """Test validate_analysis_response function."""

    def test_valid_analysis(self):
        raw = {"category": "health", "difficulty": "easy"}
        result = validate_analysis_response(raw)
        assert isinstance(result, AnalysisResponseSchema)

    def test_invalid_raises_ai_error(self):
        with pytest.raises(AIValidationError, match="invalid analysis"):
            validate_analysis_response(None)


class TestValidateCalibrationQuestions:
    """Test validate_calibration_questions function."""

    def test_valid_questions(self):
        raw = {
            "sufficient": False,
            "confidence_score": 0.3,
            "questions": [
                {"question": "What is your budget?", "category": "resources"}
            ],
        }
        result = validate_calibration_questions(raw)
        assert isinstance(result, CalibrationQuestionsResponseSchema)

    def test_invalid_raises_ai_error(self):
        with pytest.raises(AIValidationError, match="invalid calibration questions"):
            validate_calibration_questions(None)


class TestValidateCalibrationSummary:
    """Test validate_calibration_summary function."""

    def test_valid_summary(self):
        raw = {
            "user_profile": {"experience_level": "intermediate"},
            "enriched_description": "Better description",
        }
        result = validate_calibration_summary(raw)
        assert isinstance(result, CalibrationSummaryResponseSchema)

    def test_invalid_raises_ai_error(self):
        with pytest.raises(AIValidationError, match="invalid calibration summary"):
            validate_calibration_summary(None)


class TestValidateChatResponse:
    """Test validate_chat_response function."""

    def test_valid_response(self):
        raw = {"content": "Hello!", "tokens_used": 10, "model": "gpt-4"}
        result = validate_chat_response(raw)
        assert isinstance(result, ChatResponseSchema)

    def test_invalid_raises_ai_error(self):
        with pytest.raises(AIValidationError, match="invalid chat response"):
            validate_chat_response(None)


class TestValidateFunctionCall:
    """Test validate_function_call function."""

    def test_valid_call(self):
        raw = {"name": "create_task", "arguments": {"title": "Test"}}
        result = validate_function_call(raw)
        assert isinstance(result, FunctionCallSchema)

    def test_invalid_raises_ai_error(self):
        with pytest.raises(AIValidationError, match="invalid function call"):
            validate_function_call({"name": "drop_tables"})


# ===================================================================
# Coherence checker
# ===================================================================

class TestCheckPlanCalibrationCoherence:
    """Test check_plan_calibration_coherence function."""

    def _make_plan(self, **overrides):
        data = {
            "goals": [
                {
                    "title": "Goal",
                    "order": 0,
                    "tasks": [{"title": "Task", "order": 0, "duration_mins": 30}],
                }
            ],
            "weekly_time_hours": 5,
            "calibration_references": ["User ref"],
        }
        data.update(overrides)
        return PlanResponseSchema.model_validate(data)

    def test_no_profile_returns_empty(self):
        plan = self._make_plan()
        warnings = check_plan_calibration_coherence(plan, None)
        assert warnings == []

    def test_empty_profile_returns_empty(self):
        plan = self._make_plan()
        warnings = check_plan_calibration_coherence(plan, {})
        assert warnings == []

    def test_hours_mismatch_warning(self):
        plan = self._make_plan(weekly_time_hours=20)
        profile = {"available_hours_per_week": 5}
        warnings = check_plan_calibration_coherence(plan, profile)
        assert any("20h/week" in w for w in warnings)
        assert any("5h/week" in w for w in warnings)

    def test_no_hours_mismatch_within_range(self):
        plan = self._make_plan(weekly_time_hours=7)
        profile = {"available_hours_per_week": 5}
        warnings = check_plan_calibration_coherence(plan, profile)
        hours_warnings = [w for w in warnings if "h/week" in w]
        assert len(hours_warnings) == 0

    def test_long_task_warning(self):
        plan = self._make_plan(
            goals=[
                {
                    "title": "Goal",
                    "order": 0,
                    "tasks": [
                        {"title": "Very Long Task", "order": 0, "duration_mins": 300}
                    ],
                }
            ]
        )
        profile = {"available_hours_per_week": 10}
        warnings = check_plan_calibration_coherence(plan, profile)
        assert any("Very Long Task" in w for w in warnings)
        assert any("300 minutes" in w for w in warnings)

    def test_no_calibration_references_warning(self):
        plan = self._make_plan(calibration_references=[])
        profile = {"available_hours_per_week": 5}
        warnings = check_plan_calibration_coherence(plan, profile)
        assert any("did not cite" in w for w in warnings)

    def test_no_warnings_for_good_plan(self):
        plan = self._make_plan(
            weekly_time_hours=5,
            calibration_references=["User said 5h/week"],
        )
        profile = {"available_hours_per_week": 5}
        warnings = check_plan_calibration_coherence(plan, profile)
        assert warnings == []
