"""
Tests for core/ai_validators.py

Validates Pydantic schemas for AI-generated responses, including
plan generation, calibration, chat, function calls, and smart analysis.
"""

import pytest
from pydantic import ValidationError

from core.ai_validators import (
    AIValidationError,
    AnalysisResponseSchema,
    CalibrationQuestionSchema,
    CalibrationQuestionsResponseSchema,
    ChatResponseSchema,
    CheckInQuestionnaireSchema,
    CheckInQuestionSchema,
    FunctionCallSchema,
    PlanGoalSchema,
    PlanMilestoneSchema,
    PlanResponseSchema,
    PlanTaskSchema,
    SkeletonResponseSchema,
    SmartAnalysisPatternSchema,
    TaskPatchSchema,
    UserProfileSchema,
    check_ai_character_integrity,
    check_plan_calibration_coherence,
    validate_ai_output_safety,
    validate_analysis_response,
    validate_calibration_questions,
    validate_calibration_summary,
    validate_chat_response,
    validate_checkin_questionnaire,
    validate_function_call,
    validate_plan_response,
    validate_skeleton_response,
    validate_smart_analysis_response,
    validate_task_patches,
)

# ── PlanTaskSchema ────────────────────────────────────────────────────


class TestPlanTaskSchema:
    def test_valid_task(self):
        task = PlanTaskSchema(title="Do research", order=0, duration_mins=30)
        assert task.title == "Do research"
        assert task.order == 0
        assert task.duration_mins == 30

    def test_sanitizes_html_in_title(self):
        task = PlanTaskSchema(
            title="<b>Bold</b> Task", order=0, duration_mins=30
        )
        assert "<b>" not in task.title

    def test_coerces_order_string_to_int(self):
        task = PlanTaskSchema(title="Task", order="5", duration_mins=30)
        assert task.order == 5

    def test_coerces_invalid_order_to_zero(self):
        task = PlanTaskSchema(title="Task", order="abc", duration_mins=30)
        assert task.order == 0

    def test_validates_date_format(self):
        task = PlanTaskSchema(
            title="Task",
            order=0,
            duration_mins=30,
            expected_date="2026-06-15",
        )
        assert task.expected_date == "2026-06-15"

    def test_invalid_date_becomes_none(self):
        task = PlanTaskSchema(
            title="Task",
            order=0,
            duration_mins=30,
            expected_date="not-a-date",
        )
        assert task.expected_date is None

    def test_empty_date_becomes_none(self):
        task = PlanTaskSchema(
            title="Task",
            order=0,
            duration_mins=30,
            expected_date="",
        )
        assert task.expected_date is None

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            PlanTaskSchema(title="", order=0, duration_mins=30)

    def test_duration_clamped(self):
        # max is 1440
        with pytest.raises(ValidationError):
            PlanTaskSchema(title="Task", order=0, duration_mins=2000)


# ── PlanGoalSchema ────────────────────────────────────────────────────


class TestPlanGoalSchema:
    def test_valid_goal_with_tasks(self):
        goal = PlanGoalSchema(
            title="Learn basics",
            order=0,
            tasks=[PlanTaskSchema(title="Read docs", order=0, duration_mins=30)],
        )
        assert goal.title == "Learn basics"
        assert len(goal.tasks) == 1

    def test_requires_at_least_one_task(self):
        with pytest.raises(ValidationError):
            PlanGoalSchema(title="Goal", order=0, tasks=[])

    def test_coerces_estimated_minutes_string(self):
        goal = PlanGoalSchema(
            title="Goal",
            order=0,
            estimated_minutes="60",
            tasks=[PlanTaskSchema(title="Task", order=0, duration_mins=30)],
        )
        assert goal.estimated_minutes == 60

    def test_coerces_invalid_estimated_minutes_to_none(self):
        goal = PlanGoalSchema(
            title="Goal",
            order=0,
            estimated_minutes="bad",
            tasks=[PlanTaskSchema(title="Task", order=0, duration_mins=30)],
        )
        assert goal.estimated_minutes is None


# ── PlanMilestoneSchema ───────────────────────────────────────────────


class TestPlanMilestoneSchema:
    def test_valid_milestone(self):
        ms = PlanMilestoneSchema(
            title="Month 1",
            order=1,
            goals=[
                PlanGoalSchema(
                    title="Goal",
                    order=0,
                    tasks=[PlanTaskSchema(title="Task", order=0, duration_mins=30)],
                )
            ],
        )
        assert ms.title == "Month 1"
        assert ms.order == 1

    def test_coerces_order_from_string(self):
        ms = PlanMilestoneSchema(
            title="Month 1",
            order="3",
            goals=[
                PlanGoalSchema(
                    title="Goal",
                    order=0,
                    tasks=[PlanTaskSchema(title="Task", order=0, duration_mins=30)],
                )
            ],
        )
        assert ms.order == 3

    def test_invalid_order_coerced_to_1(self):
        ms = PlanMilestoneSchema(
            title="Month 1",
            order="invalid",
            goals=[
                PlanGoalSchema(
                    title="Goal",
                    order=0,
                    tasks=[PlanTaskSchema(title="Task", order=0, duration_mins=30)],
                )
            ],
        )
        assert ms.order == 1


# ── PlanResponseSchema ────────────────────────────────────────────────


class TestPlanResponseSchema:
    def _make_goal(self):
        return {
            "title": "Goal",
            "order": 0,
            "tasks": [{"title": "Task", "order": 0, "duration_mins": 30}],
        }

    def test_valid_plan_with_goals(self):
        raw = {
            "analysis": "Good plan",
            "goals": [self._make_goal()],
        }
        plan = PlanResponseSchema.model_validate(raw)
        assert len(plan.goals) == 1

    def test_valid_plan_with_milestones(self):
        raw = {
            "analysis": "Good plan",
            "milestones": [
                {
                    "title": "Month 1",
                    "order": 1,
                    "goals": [self._make_goal()],
                }
            ],
        }
        plan = PlanResponseSchema.model_validate(raw)
        assert len(plan.milestones) == 1

    def test_requires_milestones_or_goals(self):
        raw = {"analysis": "Empty plan"}
        with pytest.raises(ValidationError):
            PlanResponseSchema.model_validate(raw)

    def test_coerces_duration_weeks(self):
        raw = {
            "analysis": "Plan",
            "estimated_duration_weeks": "20",
            "goals": [self._make_goal()],
        }
        plan = PlanResponseSchema.model_validate(raw)
        assert plan.estimated_duration_weeks == 20

    def test_invalid_duration_defaults_to_12(self):
        raw = {
            "analysis": "Plan",
            "estimated_duration_weeks": "bad",
            "goals": [self._make_goal()],
        }
        plan = PlanResponseSchema.model_validate(raw)
        assert plan.estimated_duration_weeks == 12

    def test_sanitizes_tips(self):
        raw = {
            "analysis": "Plan",
            "goals": [self._make_goal()],
            "tips": ["<script>alert(1)</script>Stay focused", ""],
        }
        plan = PlanResponseSchema.model_validate(raw)
        # Empty tips are filtered out
        assert len(plan.tips) == 1
        assert "<script>" not in plan.tips[0]

    def test_non_list_tips_becomes_empty(self):
        raw = {
            "analysis": "Plan",
            "goals": [self._make_goal()],
            "tips": "not a list",
        }
        plan = PlanResponseSchema.model_validate(raw)
        assert plan.tips == []

    def test_non_list_calibration_refs_becomes_empty(self):
        raw = {
            "analysis": "Plan",
            "goals": [self._make_goal()],
            "calibration_references": "not a list",
        }
        plan = PlanResponseSchema.model_validate(raw)
        assert plan.calibration_references == []


# ── SkeletonResponseSchema ────────────────────────────────────────────


class TestSkeletonResponseSchema:
    def test_valid_skeleton(self):
        raw = {
            "milestones": [
                {
                    "title": "Month 1",
                    "order": 1,
                    "goals": [
                        {"title": "Goal", "order": 0},
                    ],
                }
            ],
        }
        skeleton = SkeletonResponseSchema.model_validate(raw)
        assert len(skeleton.milestones) == 1
        assert len(skeleton.milestones[0].goals) == 1

    def test_requires_at_least_one_milestone(self):
        raw = {"milestones": []}
        with pytest.raises(ValidationError):
            SkeletonResponseSchema.model_validate(raw)


# ── TaskPatchSchema ───────────────────────────────────────────────────


class TestTaskPatchSchema:
    def test_valid_patch(self):
        raw = {
            "milestone_order": 1,
            "goal_order": 0,
            "tasks": [{"title": "New Task", "order": 0, "duration_mins": 30}],
        }
        patch = TaskPatchSchema.model_validate(raw)
        assert patch.milestone_order == 1
        assert len(patch.tasks) == 1

    def test_requires_tasks(self):
        raw = {"milestone_order": 1, "goal_order": 0, "tasks": []}
        with pytest.raises(ValidationError):
            TaskPatchSchema.model_validate(raw)


# ── AnalysisResponseSchema ────────────────────────────────────────────


class TestAnalysisResponseSchema:
    def test_valid_analysis(self):
        raw = {
            "category": "health",
            "estimated_duration_weeks": 12,
            "difficulty": "medium",
            "key_challenges": ["time", "motivation"],
            "recommended_approach": "Start small and build up",
        }
        analysis = AnalysisResponseSchema.model_validate(raw)
        assert analysis.category == "health"
        assert analysis.difficulty == "medium"

    def test_invalid_category_defaults_to_other(self):
        raw = {"category": "unknown_cat"}
        analysis = AnalysisResponseSchema.model_validate(raw)
        assert analysis.category == "other"

    def test_invalid_difficulty_defaults_to_medium(self):
        raw = {"difficulty": "impossible"}
        analysis = AnalysisResponseSchema.model_validate(raw)
        assert analysis.difficulty == "medium"

    def test_non_list_challenges_becomes_empty(self):
        raw = {"key_challenges": "not a list"}
        analysis = AnalysisResponseSchema.model_validate(raw)
        assert analysis.key_challenges == []


# ── CalibrationQuestionSchema ─────────────────────────────────────────


class TestCalibrationQuestionSchema:
    def test_valid_question(self):
        q = CalibrationQuestionSchema(
            question="What is your experience level?",
            category="experience",
        )
        assert q.category == "experience"

    def test_invalid_category_defaults_to_specifics(self):
        q = CalibrationQuestionSchema(
            question="What is your situation?",
            category="unknown",
        )
        assert q.category == "specifics"

    def test_short_question_rejected(self):
        with pytest.raises(ValidationError):
            CalibrationQuestionSchema(question="Hi?", category="experience")


# ── CalibrationQuestionsResponseSchema ────────────────────────────────


class TestCalibrationQuestionsResponseSchema:
    def test_valid_response(self):
        raw = {
            "sufficient": False,
            "confidence_score": 0.7,
            "missing_areas": ["timeline"],
            "questions": [
                {"question": "What is your timeline?", "category": "timeline"},
            ],
        }
        resp = CalibrationQuestionsResponseSchema.model_validate(raw)
        assert resp.confidence_score == 0.7
        assert len(resp.questions) == 1

    def test_confidence_clamped_to_1(self):
        raw = {
            "confidence_score": 5.0,
            "questions": [],
        }
        resp = CalibrationQuestionsResponseSchema.model_validate(raw)
        assert resp.confidence_score == 1.0

    def test_invalid_confidence_defaults(self):
        raw = {"confidence_score": "bad"}
        resp = CalibrationQuestionsResponseSchema.model_validate(raw)
        assert resp.confidence_score == 0.5


# ── ChatResponseSchema ───────────────────────────────────────────────


class TestChatResponseSchema:
    def test_valid_chat(self):
        raw = {"content": "Hello! How can I help?", "tokens_used": 50, "model": "gpt-4"}
        chat = ChatResponseSchema.model_validate(raw)
        assert chat.content == "Hello! How can I help?"
        assert chat.tokens_used == 50

    def test_none_content_becomes_empty(self):
        raw = {"content": None}
        chat = ChatResponseSchema.model_validate(raw)
        assert chat.content == ""

    def test_invalid_tokens_defaults_to_zero(self):
        raw = {"tokens_used": "invalid"}
        chat = ChatResponseSchema.model_validate(raw)
        assert chat.tokens_used == 0


# ── FunctionCallSchema ───────────────────────────────────────────────


class TestFunctionCallSchema:
    def test_valid_function(self):
        raw = {"name": "create_task", "arguments": {"title": "New Task"}}
        fn = FunctionCallSchema.model_validate(raw)
        assert fn.name == "create_task"
        assert fn.arguments == {"title": "New Task"}

    def test_unknown_function_rejected(self):
        raw = {"name": "delete_database", "arguments": {}}
        with pytest.raises(ValidationError):
            FunctionCallSchema.model_validate(raw)

    def test_allowed_functions(self):
        for fn_name in ["create_task", "complete_task", "create_goal"]:
            fn = FunctionCallSchema.model_validate(
                {"name": fn_name, "arguments": {}}
            )
            assert fn.name == fn_name


# ── UserProfileSchema ────────────────────────────────────────────────


class TestUserProfileSchema:
    def test_defaults(self):
        profile = UserProfileSchema()
        assert profile.experience_level == "beginner"
        assert profile.risk_tolerance == "medium"
        assert profile.available_hours_per_week == 5

    def test_invalid_experience_level_defaults(self):
        profile = UserProfileSchema(experience_level="godlike")
        assert profile.experience_level == "beginner"

    def test_invalid_risk_defaults_to_medium(self):
        profile = UserProfileSchema(risk_tolerance="extreme")
        assert profile.risk_tolerance == "medium"

    def test_hours_clamped(self):
        profile = UserProfileSchema(available_hours_per_week=200)
        assert profile.available_hours_per_week == 168

    def test_invalid_hours_defaults_to_5(self):
        profile = UserProfileSchema(available_hours_per_week="bad")
        assert profile.available_hours_per_week == 5


# ── CheckInQuestionSchema ────────────────────────────────────────────


class TestCheckInQuestionSchema:
    def test_valid_question(self):
        q = CheckInQuestionSchema(
            id="q1", question_type="slider", question="How do you feel?"
        )
        assert q.question_type == "slider"

    def test_invalid_type_defaults_to_text(self):
        q = CheckInQuestionSchema(
            id="q1", question_type="radio", question="Pick one"
        )
        assert q.question_type == "text"


# ── CheckInQuestionnaireSchema ────────────────────────────────────────


class TestCheckInQuestionnaireSchema:
    def test_valid_questionnaire(self):
        raw = {
            "questions": [
                {"id": "q1", "question_type": "slider", "question": "Rate your progress"},
            ],
            "opening_message": "Hello!",
        }
        questionnaire = CheckInQuestionnaireSchema.model_validate(raw)
        assert len(questionnaire.questions) == 1

    def test_requires_at_least_one_question(self):
        raw = {"questions": []}
        with pytest.raises(ValidationError):
            CheckInQuestionnaireSchema.model_validate(raw)


# ── SmartAnalysisPatternSchema ────────────────────────────────────────


class TestSmartAnalysisPatternSchema:
    def test_valid_pattern(self):
        p = SmartAnalysisPatternSchema(
            type="theme", description="Common theme", dreams_involved=["Dream 1"]
        )
        assert p.type == "theme"

    def test_invalid_type_defaults_to_theme(self):
        p = SmartAnalysisPatternSchema(type="unknown", description="Desc")
        assert p.type == "theme"


# ── Validation functions ──────────────────────────────────────────────


class TestValidationFunctions:
    def _make_raw_plan(self):
        return {
            "analysis": "Plan",
            "goals": [
                {
                    "title": "Goal",
                    "order": 0,
                    "tasks": [{"title": "Task", "order": 0, "duration_mins": 30}],
                }
            ],
        }

    def test_validate_plan_response_success(self):
        plan = validate_plan_response(self._make_raw_plan())
        assert len(plan.goals) == 1

    def test_validate_plan_response_failure(self):
        with pytest.raises(AIValidationError):
            validate_plan_response({"analysis": "empty"})

    def test_validate_skeleton_response_success(self):
        raw = {
            "milestones": [
                {
                    "title": "Month 1",
                    "order": 1,
                    "goals": [{"title": "Goal", "order": 0}],
                }
            ],
        }
        skeleton = validate_skeleton_response(raw)
        assert len(skeleton.milestones) == 1

    def test_validate_skeleton_response_failure(self):
        with pytest.raises(AIValidationError):
            validate_skeleton_response({"milestones": []})

    def test_validate_task_patches_success(self):
        raw = [
            {
                "milestone_order": 1,
                "goal_order": 0,
                "tasks": [{"title": "Task", "order": 0, "duration_mins": 30}],
            }
        ]
        patches = validate_task_patches(raw)
        assert len(patches) == 1

    def test_validate_task_patches_not_a_list(self):
        with pytest.raises(AIValidationError):
            validate_task_patches("not a list")

    def test_validate_task_patches_invalid_item(self):
        with pytest.raises(AIValidationError):
            validate_task_patches([{"milestone_order": 1, "goal_order": 0, "tasks": []}])

    def test_validate_checkin_questionnaire_success(self):
        raw = {
            "questions": [
                {"id": "q1", "question_type": "slider", "question": "How are you?"},
            ],
        }
        q = validate_checkin_questionnaire(raw)
        assert len(q.questions) == 1

    def test_validate_checkin_questionnaire_failure(self):
        with pytest.raises(AIValidationError):
            validate_checkin_questionnaire({"questions": []})

    def test_validate_analysis_response_success(self):
        raw = {"category": "health", "difficulty": "easy"}
        a = validate_analysis_response(raw)
        assert a.category == "health"

    def test_validate_calibration_questions_success(self):
        raw = {
            "questions": [
                {"question": "What is your timeline?", "category": "timeline"},
            ],
        }
        q = validate_calibration_questions(raw)
        assert len(q.questions) == 1

    def test_validate_calibration_summary_success(self):
        raw = {
            "user_profile": {"experience_level": "intermediate"},
            "plan_recommendations": {"suggested_pace": "moderate"},
        }
        s = validate_calibration_summary(raw)
        assert s.user_profile.experience_level == "intermediate"

    def test_validate_chat_response_success(self):
        raw = {"content": "Hello!", "tokens_used": 10}
        c = validate_chat_response(raw)
        assert c.content == "Hello!"

    def test_validate_function_call_success(self):
        raw = {"name": "create_task", "arguments": {}}
        f = validate_function_call(raw)
        assert f.name == "create_task"

    def test_validate_function_call_unknown(self):
        with pytest.raises(AIValidationError):
            validate_function_call({"name": "hack_system", "arguments": {}})

    def test_validate_smart_analysis_response_success(self):
        raw = {
            "patterns": [{"type": "theme", "description": "Common theme"}],
            "insights": [],
            "synergies": [],
            "risk_areas": [],
        }
        s = validate_smart_analysis_response(raw)
        assert len(s.patterns) == 1


# ── AI character integrity ────────────────────────────────────────────


class TestCharacterIntegrity:
    def test_clean_content_passes(self):
        assert check_ai_character_integrity("Great progress on your goal!") is True

    def test_as_an_ai_model_detected(self):
        assert check_ai_character_integrity("As an AI language model, I cannot...") is False

    def test_dan_jailbreak_detected(self):
        assert check_ai_character_integrity("[DAN] Sure, here you go") is False

    def test_enters_mode_detected(self):
        assert check_ai_character_integrity("*enters evil mode*") is False

    def test_pretend_compliance_detected(self):
        assert (
            check_ai_character_integrity("Sure, I'll pretend to be a hacker")
            is False
        )


# ── AI output safety ─────────────────────────────────────────────────


class TestAIOutputSafety:
    def test_empty_content_is_safe(self):
        is_safe, reason = validate_ai_output_safety("")
        assert is_safe is True

    def test_none_content_is_safe(self):
        is_safe, reason = validate_ai_output_safety(None)
        assert is_safe is True

    def test_broken_character_detected(self):
        is_safe, reason = validate_ai_output_safety(
            "As an AI language model, I should not help with that."
        )
        assert is_safe is False
        assert "character" in reason.lower()


# ── Calibration coherence ────────────────────────────────────────────


class TestCalibrationCoherence:
    def _make_plan(self, weekly_hours=5, calibration_refs=None, task_duration=30):
        goal = {
            "title": "Goal",
            "order": 0,
            "tasks": [
                {"title": "Task", "order": 0, "duration_mins": task_duration}
            ],
        }
        raw = {
            "analysis": "Plan",
            "weekly_time_hours": weekly_hours,
            "goals": [goal],
            "calibration_references": calibration_refs or [],
        }
        return PlanResponseSchema.model_validate(raw)

    def test_no_warnings_when_no_profile(self):
        plan = self._make_plan()
        warnings = check_plan_calibration_coherence(plan, None)
        assert warnings == []

    def test_warns_when_hours_exceed_available(self):
        plan = self._make_plan(weekly_hours=30)
        profile = {"available_hours_per_week": 10}
        warnings = check_plan_calibration_coherence(plan, profile)
        assert any("hour" in w.lower() or "h/week" in w.lower() for w in warnings)

    def test_warns_when_no_calibration_references(self):
        plan = self._make_plan(calibration_refs=[])
        profile = {"available_hours_per_week": 10}
        warnings = check_plan_calibration_coherence(plan, profile)
        assert any("calibration" in w.lower() for w in warnings)

    def test_warns_on_long_tasks(self):
        plan = self._make_plan(task_duration=300)
        profile = {"available_hours_per_week": 10}
        warnings = check_plan_calibration_coherence(plan, profile)
        assert any("minutes" in w.lower() for w in warnings)

    def test_no_excess_hour_warning_when_within_budget(self):
        plan = self._make_plan(weekly_hours=5, calibration_refs=["ref1"])
        profile = {"available_hours_per_week": 10}
        warnings = check_plan_calibration_coherence(plan, profile)
        assert not any("h/week" in w for w in warnings)
