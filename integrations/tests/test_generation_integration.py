"""Integration tests for category-specific dream generation.

Validates that CATEGORY_PROMPTS, CATEGORY_OBSTACLES, CATEGORY_CALIBRATION_HINTS,
CATEGORY_TASK_DETAILS, CATEGORY_MILESTONE_PATTERNS, CATEGORY_SCHEDULING_RULES,
and CATEGORY_PROFESSIONAL_REFERRALS are properly defined and injected into the
generation prompts by OpenAIService.
"""
import json
from datetime import date, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from integrations.openai_service import (
    CATEGORY_CALIBRATION_HINTS,
    CATEGORY_MILESTONE_PATTERNS,
    CATEGORY_OBSTACLES,
    CATEGORY_PROFESSIONAL_REFERRALS,
    CATEGORY_PROMPTS,
    CATEGORY_SCHEDULING_RULES,
    CATEGORY_TASK_DETAILS,
    OpenAIService,
    _build_referral_prompt_section,
    _get_scheduling_rules,
)


# ---------------------------------------------------------------------------
# Helper: build a mock OpenAI ChatCompletion response
# ---------------------------------------------------------------------------


def _mock_response(content, finish_reason="stop"):
    """Return a Mock that mimics an OpenAI ChatCompletion response."""
    message = Mock()
    message.content = content

    choice = Mock()
    choice.message = message
    choice.finish_reason = finish_reason

    response = Mock()
    response.choices = [choice]
    response.usage = Mock(total_tokens=100)
    response.model = "gpt-4"
    return response


# All main categories that should be present in every dict
MAIN_CATEGORIES = [
    "health",
    "career",
    "education",
    "finance",
    "creative",
    "personal",
    "hobbies",
    "social",
    "relationships",
    "travel",
]


# ===================================================================
# Data completeness & consistency
# ===================================================================


class TestCategoryPromptInjection:
    """Test that category-specific prompts are defined and well-formed."""

    def test_category_prompts_exist_for_at_least_one_category(self):
        """CATEGORY_PROMPTS currently only covers 'health'; verify it exists."""
        assert "health" in CATEGORY_PROMPTS, "Missing CATEGORY_PROMPTS['health']"
        assert len(CATEGORY_PROMPTS) >= 1

    def test_category_obstacles_exist(self):
        assert len(CATEGORY_OBSTACLES) >= 10

    def test_category_obstacles_exist_for_all_main_categories(self):
        for cat in MAIN_CATEGORIES:
            assert cat in CATEGORY_OBSTACLES, f"Missing CATEGORY_OBSTACLES['{cat}']"
            assert len(CATEGORY_OBSTACLES[cat]) >= 3, (
                f"CATEGORY_OBSTACLES['{cat}'] should have at least 3 items"
            )

    def test_category_prompts_not_empty(self):
        for cat, prompt in CATEGORY_PROMPTS.items():
            assert len(prompt) > 50, f"CATEGORY_PROMPTS['{cat}'] too short"

    def test_category_calibration_hints_exist_for_all_main_categories(self):
        for cat in MAIN_CATEGORIES:
            assert cat in CATEGORY_CALIBRATION_HINTS, (
                f"Missing CATEGORY_CALIBRATION_HINTS['{cat}']"
            )
            assert len(CATEGORY_CALIBRATION_HINTS[cat]) > 20, (
                f"CATEGORY_CALIBRATION_HINTS['{cat}'] too short"
            )

    def test_category_task_details_exist_for_all_main_categories(self):
        for cat in MAIN_CATEGORIES:
            assert cat in CATEGORY_TASK_DETAILS, (
                f"Missing CATEGORY_TASK_DETAILS['{cat}']"
            )
            assert len(CATEGORY_TASK_DETAILS[cat]) > 50, (
                f"CATEGORY_TASK_DETAILS['{cat}'] too short"
            )

    def test_category_milestone_patterns_not_empty(self):
        """At least some categories should have milestone patterns."""
        assert len(CATEGORY_MILESTONE_PATTERNS) >= 3
        for cat, pattern in CATEGORY_MILESTONE_PATTERNS.items():
            assert len(pattern) > 30, (
                f"CATEGORY_MILESTONE_PATTERNS['{cat}'] too short"
            )

    def test_category_scheduling_rules_exist_for_all_main_categories(self):
        for cat in MAIN_CATEGORIES:
            assert cat in CATEGORY_SCHEDULING_RULES, (
                f"Missing CATEGORY_SCHEDULING_RULES['{cat}']"
            )
            assert len(CATEGORY_SCHEDULING_RULES[cat]) > 30, (
                f"CATEGORY_SCHEDULING_RULES['{cat}'] too short"
            )

    def test_category_professional_referrals_have_triggers_and_professionals(self):
        """Each referral entry must have non-empty triggers and professionals."""
        for cat, data in CATEGORY_PROFESSIONAL_REFERRALS.items():
            assert "triggers" in data, (
                f"CATEGORY_PROFESSIONAL_REFERRALS['{cat}'] missing 'triggers'"
            )
            assert "professionals" in data, (
                f"CATEGORY_PROFESSIONAL_REFERRALS['{cat}'] missing 'professionals'"
            )
            assert len(data["triggers"]) >= 1, (
                f"CATEGORY_PROFESSIONAL_REFERRALS['{cat}'] triggers empty"
            )
            assert len(data["professionals"]) >= 1, (
                f"CATEGORY_PROFESSIONAL_REFERRALS['{cat}'] professionals empty"
            )


# ===================================================================
# Helper function tests
# ===================================================================


class TestHelperFunctions:
    """Test helper functions that build prompt sections."""

    def test_build_referral_prompt_section_health(self):
        section = _build_referral_prompt_section("health")
        assert "HEALTH" in section
        assert "requires_professional" in section
        assert "professional_note" in section

    def test_build_referral_prompt_section_unknown_returns_empty(self):
        section = _build_referral_prompt_section("nonexistent_category")
        assert section == ""

    def test_get_scheduling_rules_known_category(self):
        rules = _get_scheduling_rules("health")
        assert "HEALTH SCHEDULING RULES" in rules

    def test_get_scheduling_rules_unknown_returns_empty(self):
        rules = _get_scheduling_rules("nonexistent")
        assert rules == ""

    def test_get_scheduling_rules_empty_string(self):
        rules = _get_scheduling_rules("")
        assert rules == ""


# ===================================================================
# OpenAIService instantiation
# ===================================================================


class TestServiceInstantiation:
    """Test that OpenAIService can be instantiated."""

    def test_service_instantiation(self):
        service = OpenAIService()
        assert service is not None

    def test_service_has_system_prompts(self):
        service = OpenAIService()
        assert "planning" in service.SYSTEM_PROMPTS
        assert "dream_creation" in service.SYSTEM_PROMPTS

    def test_service_has_ethical_preamble(self):
        service = OpenAIService()
        assert len(service.ETHICAL_PREAMBLE) > 100
        assert "ETHICAL GUIDELINES" in service.ETHICAL_PREAMBLE


# ===================================================================
# analyze_dream
# ===================================================================


class TestAnalyzeDream:
    """Test analyze_dream with mocked OpenAI client."""

    @patch("integrations.openai_service._client")
    def test_analyze_dream_returns_category(self, mock_client):
        analysis_result = {
            "category": "health",
            "detected_language": "en",
            "estimated_duration_weeks": 12,
            "difficulty": "medium",
            "key_challenges": ["consistency", "injury prevention", "nutrition"],
            "recommended_approach": "progressive overload with periodization",
            "requires_professional": False,
            "professional_type": None,
            "professional_note": None,
            "recommended_professionals": [],
        }
        mock_client.chat.completions.create.return_value = _mock_response(
            json.dumps(analysis_result)
        )

        service = OpenAIService()
        result = service.analyze_dream(
            "Run a marathon", "I want to complete my first marathon in under 4 hours"
        )

        assert result is not None
        assert result["category"] == "health"
        assert result["difficulty"] == "medium"
        assert len(result["key_challenges"]) >= 3

    @patch("integrations.openai_service._client")
    def test_analyze_dream_injects_referral_section(self, mock_client):
        """Verify the prompt sent to OpenAI includes referral rules for health."""
        analysis_result = {
            "category": "health",
            "detected_language": "en",
            "estimated_duration_weeks": 24,
            "difficulty": "hard",
            "key_challenges": ["weight management"],
            "recommended_approach": "consult a dietitian",
            "requires_professional": True,
            "professional_type": "Registered Dietitian",
            "professional_note": "Weight loss >30 lbs requires professional guidance",
            "recommended_professionals": ["Registered Dietitian", "Sports Medicine Doctor"],
        }
        mock_client.chat.completions.create.return_value = _mock_response(
            json.dumps(analysis_result)
        )

        service = OpenAIService()
        service.analyze_dream(
            "Lose 50 pounds",
            "I need to lose weight for health reasons, currently 250 lbs",
        )

        # Check the prompt that was sent to OpenAI
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        user_message = messages[1]["content"]

        # The referral section should be injected into the prompt
        assert "PROFESSIONAL REFERRAL" in user_message

    @patch("integrations.openai_service._client")
    def test_analyze_dream_returns_professional_fields(self, mock_client):
        """Test that professional referral fields are returned."""
        analysis_result = {
            "category": "health",
            "detected_language": "en",
            "estimated_duration_weeks": 24,
            "difficulty": "hard",
            "key_challenges": ["consistency"],
            "recommended_approach": "progressive",
            "requires_professional": True,
            "professional_type": "Personal Trainer",
            "professional_note": "Recommended for form correction",
            "recommended_professionals": ["Personal Trainer", "Sports Medicine Doctor"],
        }
        mock_client.chat.completions.create.return_value = _mock_response(
            json.dumps(analysis_result)
        )

        service = OpenAIService()
        result = service.analyze_dream("Get a six pack", "Build visible abdominal muscles")
        assert result["requires_professional"] is True
        assert result["professional_type"] is not None
        assert len(result["recommended_professionals"]) >= 1


# ===================================================================
# generate_skeleton — category prompt injection
# ===================================================================


class TestGenerateSkeletonInjection:
    """Test that generate_skeleton injects category-specific content."""

    @patch("integrations.openai_service._plan_client")
    def test_skeleton_injects_category_prompts(self, mock_plan_client):
        """CATEGORY_PROMPTS for 'health' should appear in the system prompt."""
        skeleton_result = {
            "analysis": "Good plan",
            "estimated_duration_weeks": 12,
            "weekly_time_hours": 5,
            "milestones": [],
            "tips": [],
            "potential_obstacles": [],
            "calibration_references": [],
        }
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            json.dumps(skeleton_result)
        )

        service = OpenAIService()
        service.generate_skeleton(
            dream_title="Run a marathon",
            dream_description="Complete a marathon in under 4 hours",
            user_context={"category": "health"},
            target_date=(date.today() + timedelta(days=180)).isoformat(),
        )

        call_args = mock_plan_client.chat.completions.create.call_args
        system_prompt = call_args[1]["messages"][0]["content"]

        # CATEGORY_PROMPTS['health'] should be injected
        assert "HEALTH & FITNESS SPECIFIC RULES" in system_prompt

    @patch("integrations.openai_service._plan_client")
    def test_skeleton_injects_milestone_patterns(self, mock_plan_client):
        """CATEGORY_MILESTONE_PATTERNS for 'health' in system prompt."""
        skeleton_result = {
            "analysis": "ok",
            "estimated_duration_weeks": 12,
            "weekly_time_hours": 5,
            "milestones": [],
            "tips": [],
            "potential_obstacles": [],
            "calibration_references": [],
        }
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            json.dumps(skeleton_result)
        )

        service = OpenAIService()
        service.generate_skeleton(
            dream_title="Run a marathon",
            dream_description="Complete a marathon in under 4 hours",
            user_context={"category": "health"},
            target_date=(date.today() + timedelta(days=180)).isoformat(),
        )

        call_args = mock_plan_client.chat.completions.create.call_args
        system_prompt = call_args[1]["messages"][0]["content"]

        assert "HEALTH MILESTONE NAMING" in system_prompt

    @patch("integrations.openai_service._plan_client")
    def test_skeleton_injects_obstacles_hints(self, mock_plan_client):
        """CATEGORY_OBSTACLES for 'health' should be in the system prompt."""
        skeleton_result = {
            "analysis": "ok",
            "estimated_duration_weeks": 12,
            "weekly_time_hours": 5,
            "milestones": [],
            "tips": [],
            "potential_obstacles": [],
            "calibration_references": [],
        }
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            json.dumps(skeleton_result)
        )

        service = OpenAIService()
        service.generate_skeleton(
            dream_title="Lose weight",
            dream_description="Lose 20 pounds in 6 months",
            user_context={"category": "health"},
            target_date=(date.today() + timedelta(days=180)).isoformat(),
        )

        call_args = mock_plan_client.chat.completions.create.call_args
        system_prompt = call_args[1]["messages"][0]["content"]

        assert "COMMON OBSTACLES FOR HEALTH DREAMS" in system_prompt
        # Check a specific obstacle is injected
        assert "Injury risk from overtraining" in system_prompt

    @patch("integrations.openai_service._plan_client")
    def test_skeleton_injects_scheduling_rules(self, mock_plan_client):
        """CATEGORY_SCHEDULING_RULES for 'health' should be in system prompt."""
        skeleton_result = {
            "analysis": "ok",
            "estimated_duration_weeks": 12,
            "weekly_time_hours": 5,
            "milestones": [],
            "tips": [],
            "potential_obstacles": [],
            "calibration_references": [],
        }
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            json.dumps(skeleton_result)
        )

        service = OpenAIService()
        service.generate_skeleton(
            dream_title="Run a 5K",
            dream_description="Train for a 5K race",
            user_context={"category": "health"},
            target_date=(date.today() + timedelta(days=90)).isoformat(),
        )

        call_args = mock_plan_client.chat.completions.create.call_args
        system_prompt = call_args[1]["messages"][0]["content"]

        assert "HEALTH SCHEDULING RULES" in system_prompt

    @patch("integrations.openai_service._plan_client")
    def test_skeleton_no_injection_for_unknown_category(self, mock_plan_client):
        """Unknown category should not inject any category-specific content."""
        skeleton_result = {
            "analysis": "ok",
            "estimated_duration_weeks": 12,
            "weekly_time_hours": 5,
            "milestones": [],
            "tips": [],
            "potential_obstacles": [],
            "calibration_references": [],
        }
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            json.dumps(skeleton_result)
        )

        service = OpenAIService()
        service.generate_skeleton(
            dream_title="Something vague",
            dream_description="A vague goal",
            user_context={"category": "unknown_category_xyz"},
            target_date=(date.today() + timedelta(days=90)).isoformat(),
        )

        call_args = mock_plan_client.chat.completions.create.call_args
        system_prompt = call_args[1]["messages"][0]["content"]

        # No category-specific sections should be injected
        assert "HEALTH & FITNESS SPECIFIC RULES" not in system_prompt
        assert "CAREER" not in system_prompt or "CAREER SCHEDULING RULES" not in system_prompt


# ===================================================================
# generate_tasks_for_months — category prompt injection
# ===================================================================


class TestGenerateTasksInjection:
    """Test that generate_tasks_for_months injects category-specific content."""

    @patch("integrations.openai_service._plan_client")
    def test_tasks_injects_category_prompts_and_task_details(self, mock_plan_client):
        """CATEGORY_PROMPTS and CATEGORY_TASK_DETAILS should appear in the prompts."""
        task_result = {
            "task_patches": [
                {
                    "milestone_order": 1,
                    "goal_order": 1,
                    "tasks": [
                        {
                            "title": "Day 1: Baseline assessment",
                            "order": 1,
                            "day_number": 1,
                            "expected_date": "2026-04-01",
                            "deadline_date": "2026-04-02",
                            "duration_mins": 30,
                            "description": "Measure current fitness level",
                            "reasoning": "Starting point",
                        }
                    ],
                }
            ]
        }
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            json.dumps(task_result)
        )

        skeleton = {
            "milestones": [
                {
                    "title": "Month 1: Foundation",
                    "description": "Build the base",
                    "order": 1,
                    "target_day": 30,
                    "goals": [
                        {
                            "title": "Learn fundamentals",
                            "description": "Learn the basics",
                            "order": 1,
                        }
                    ],
                    "obstacles": [],
                }
            ],
            "estimated_duration_weeks": 12,
        }

        service = OpenAIService()
        service.generate_tasks_for_months(
            dream_title="Run a marathon",
            dream_description="Complete a marathon in under 4 hours",
            skeleton=skeleton,
            user_context={"category": "health", "available_hours": 8},
            month_start=1,
            month_end=1,
            target_date=(date.today() + timedelta(days=180)).isoformat(),
        )

        call_args = mock_plan_client.chat.completions.create.call_args
        system_prompt = call_args[1]["messages"][0]["content"]
        user_prompt = call_args[1]["messages"][1]["content"]

        # CATEGORY_PROMPTS injected into system prompt
        assert "HEALTH & FITNESS SPECIFIC RULES" in system_prompt

        # CATEGORY_TASK_DETAILS injected into user prompt
        assert "HEALTH TASK DETAIL REQUIREMENTS" in user_prompt

    @patch("integrations.openai_service._plan_client")
    def test_tasks_injects_obstacles_for_career(self, mock_plan_client):
        """CATEGORY_OBSTACLES for 'career' should appear in the system prompt."""
        task_result = {
            "task_patches": [
                {
                    "milestone_order": 1,
                    "goal_order": 1,
                    "tasks": [
                        {
                            "title": "Day 1: Self-assessment",
                            "order": 1,
                            "day_number": 1,
                            "expected_date": "2026-04-01",
                            "deadline_date": "2026-04-02",
                            "duration_mins": 30,
                            "description": "Assess current skills",
                            "reasoning": "Starting point",
                        }
                    ],
                }
            ]
        }
        mock_plan_client.chat.completions.create.return_value = _mock_response(
            json.dumps(task_result)
        )

        skeleton = {
            "milestones": [
                {
                    "title": "Month 1: Research",
                    "description": "Research the market",
                    "order": 1,
                    "target_day": 30,
                    "goals": [
                        {
                            "title": "Market analysis",
                            "description": "Analyze the job market",
                            "order": 1,
                        }
                    ],
                    "obstacles": [],
                }
            ],
            "estimated_duration_weeks": 12,
        }

        service = OpenAIService()
        service.generate_tasks_for_months(
            dream_title="Get promoted to senior engineer",
            dream_description="Achieve a senior engineering role at a FAANG company",
            skeleton=skeleton,
            user_context={"category": "career", "available_hours": 10},
            month_start=1,
            month_end=1,
            target_date=(date.today() + timedelta(days=180)).isoformat(),
        )

        call_args = mock_plan_client.chat.completions.create.call_args
        system_prompt = call_args[1]["messages"][0]["content"]

        assert "COMMON OBSTACLES FOR CAREER DREAMS" in system_prompt
        assert "Rejection fatigue" in system_prompt


# ===================================================================
# Calibration hint injection
# ===================================================================


class TestCalibrationHintInjection:
    """Test _get_category_calibration_hint injects correctly."""

    def test_calibration_hint_for_known_category(self):
        service = OpenAIService()
        hint = service._get_category_calibration_hint(
            "health", "Run a marathon", "Complete my first marathon"
        )
        assert "HEALTH" in hint
        assert "fitness level" in hint

    def test_calibration_hint_for_unknown_falls_back_to_detection(self):
        service = OpenAIService()
        # "other" triggers fallback detection from title/description
        hint = service._get_category_calibration_hint(
            "other", "Save money for retirement", "Build a retirement fund of $1M"
        )
        # detect_category_from_text should detect "finance" from title
        assert "FINANCE" in hint or hint == ""

    def test_calibration_hint_for_empty_category(self):
        service = OpenAIService()
        hint = service._get_category_calibration_hint(
            "", "Learn Python programming", "Become proficient in Python"
        )
        # Should attempt detection from text — may or may not find a match
        assert isinstance(hint, str)


# ===================================================================
# Cross-category consistency
# ===================================================================


class TestCrossCategoryConsistency:
    """Test that all category dicts use the same key set where expected."""

    def test_obstacles_keys_subset_of_prompts_or_vice_versa(self):
        """CATEGORY_OBSTACLES keys should be a superset of CATEGORY_PROMPTS keys,
        since obstacles exist for all categories that have prompts."""
        prompts_keys = set(CATEGORY_PROMPTS.keys())
        obstacles_keys = set(CATEGORY_OBSTACLES.keys())
        missing = prompts_keys - obstacles_keys
        assert not missing, (
            f"Categories in CATEGORY_PROMPTS but not in CATEGORY_OBSTACLES: {missing}"
        )

    def test_calibration_hints_cover_main_categories(self):
        """Calibration hints should cover all main categories."""
        for cat in MAIN_CATEGORIES:
            assert cat in CATEGORY_CALIBRATION_HINTS, (
                f"Missing calibration hint for '{cat}'"
            )

    def test_scheduling_rules_cover_main_categories(self):
        """Scheduling rules should cover all main categories."""
        for cat in MAIN_CATEGORIES:
            assert cat in CATEGORY_SCHEDULING_RULES, (
                f"Missing scheduling rules for '{cat}'"
            )

    def test_task_details_cover_main_categories(self):
        """Task details should cover all main categories."""
        for cat in MAIN_CATEGORIES:
            assert cat in CATEGORY_TASK_DETAILS, (
                f"Missing task details for '{cat}'"
            )


# ===================================================================
# Referral prompt construction
# ===================================================================


class TestReferralPromptConstruction:
    """Test _build_referral_prompt_section for various categories."""

    @pytest.mark.parametrize(
        "category",
        list(CATEGORY_PROFESSIONAL_REFERRALS.keys()),
    )
    def test_referral_section_contains_category_name(self, category):
        section = _build_referral_prompt_section(category)
        assert category.upper() in section

    @pytest.mark.parametrize(
        "category",
        list(CATEGORY_PROFESSIONAL_REFERRALS.keys()),
    )
    def test_referral_section_contains_professionals(self, category):
        section = _build_referral_prompt_section(category)
        referral = CATEGORY_PROFESSIONAL_REFERRALS[category]
        for professional in referral["professionals"]:
            assert professional in section

    @pytest.mark.parametrize(
        "category",
        list(CATEGORY_PROFESSIONAL_REFERRALS.keys()),
    )
    def test_referral_section_contains_trigger_text(self, category):
        section = _build_referral_prompt_section(category)
        referral = CATEGORY_PROFESSIONAL_REFERRALS[category]
        # At least one trigger should appear in the section
        found = any(trigger in section for trigger in referral["triggers"])
        assert found, f"No triggers from '{category}' found in referral section"
