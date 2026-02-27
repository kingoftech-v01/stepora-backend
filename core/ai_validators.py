"""
Pydantic validation schemas for all AI-generated responses.

Every AI output is validated against these schemas before being saved to the
database. This prevents crashes from malformed responses, ensures type safety,
enforces field constraints, and guarantees the AI provides evidence/reasoning
so users can verify the plan makes sense for their situation.
"""

import re
import logging
from typing import ClassVar, Optional, Set
from pydantic import BaseModel, Field, field_validator, model_validator

from core.sanitizers import sanitize_text, sanitize_json_values

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Max lengths aligned with Django model CharField max_length values
# ---------------------------------------------------------------------------
MAX_TITLE_LEN = 255
MAX_DESCRIPTION_LEN = 5000
MAX_TEXT_LEN = 10000
MAX_SHORT_TEXT_LEN = 500

VALID_CATEGORIES = {
    "health", "career", "relationships", "finance",
    "personal_development", "hobbies", "education", "other",
}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_EXPERIENCE_LEVELS = {"beginner", "intermediate", "advanced"}
VALID_PACES = {"aggressive", "moderate", "relaxed"}
VALID_RISK_LEVELS = {"low", "medium", "high"}
VALID_CALIBRATION_CATEGORIES = {
    "experience", "timeline", "resources", "motivation",
    "constraints", "specifics", "lifestyle", "preferences",
}


def _clamp_int(v: int | None, lo: int, hi: int) -> int | None:
    if v is None:
        return None
    return max(lo, min(hi, v))


def _sanitize_str(v: str | None, max_len: int = MAX_TEXT_LEN) -> str:
    if v is None:
        return ""
    return sanitize_text(str(v))[:max_len]


# ===================================================================
# Plan generation schemas (generate_plan)
# ===================================================================

class PlanTaskSchema(BaseModel):
    """Single task inside a goal."""
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LEN)
    order: int = Field(..., ge=0, le=500)
    day_number: Optional[int] = Field(default=None, ge=1, le=730, description="Day number from start (1 = first day)")
    duration_mins: int = Field(default=30, ge=1, le=1440)
    reasoning: str = Field(
        default="",
        max_length=MAX_SHORT_TEXT_LEN,
        description="Why this specific task is recommended given the user's situation",
    )

    @field_validator("title", "description", "reasoning", mode="before")
    @classmethod
    def sanitize_strings(cls, v):
        return _sanitize_str(v, MAX_DESCRIPTION_LEN)

    @field_validator("order", "duration_mins", mode="before")
    @classmethod
    def coerce_to_int(cls, v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0


class PlanGoalSchema(BaseModel):
    """Single goal inside a plan."""
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LEN)
    order: int = Field(..., ge=0, le=100)
    estimated_minutes: Optional[int] = Field(default=None, ge=0, le=100000)
    tasks: list[PlanTaskSchema] = Field(default_factory=list, min_length=1)
    reasoning: str = Field(
        default="",
        max_length=MAX_SHORT_TEXT_LEN,
        description="Why this goal is important and how it fits the user's profile",
    )

    @field_validator("title", "description", "reasoning", mode="before")
    @classmethod
    def sanitize_strings(cls, v):
        return _sanitize_str(v, MAX_DESCRIPTION_LEN)

    @field_validator("order", mode="before")
    @classmethod
    def coerce_order(cls, v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    @field_validator("estimated_minutes", mode="before")
    @classmethod
    def coerce_estimated_minutes(cls, v):
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None


class PlanObstacleSchema(BaseModel):
    """Predicted obstacle with a solution."""
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LEN)
    solution: str = Field(default="", max_length=MAX_DESCRIPTION_LEN)
    evidence: str = Field(
        default="",
        max_length=MAX_SHORT_TEXT_LEN,
        description="Why this obstacle is likely given the user's specific context",
    )

    @field_validator("title", "description", "solution", "evidence", mode="before")
    @classmethod
    def sanitize_strings(cls, v):
        return _sanitize_str(v, MAX_DESCRIPTION_LEN)


class PlanResponseSchema(BaseModel):
    """Full plan response from AI. The top-level schema for generate_plan."""
    analysis: str = Field(default="", max_length=MAX_TEXT_LEN)
    estimated_duration_weeks: int = Field(default=12, ge=1, le=520)
    weekly_time_hours: int = Field(default=5, ge=1, le=168)
    goals: list[PlanGoalSchema] = Field(..., min_length=1)
    tips: list[str] = Field(default_factory=list)
    potential_obstacles: list[PlanObstacleSchema] = Field(default_factory=list)
    calibration_references: list[str] = Field(
        default_factory=list,
        description=(
            "List of specific calibration answers the AI used to shape this plan. "
            "This proves the plan is personalized and not generic."
        ),
    )

    @field_validator("analysis", mode="before")
    @classmethod
    def sanitize_analysis(cls, v):
        return _sanitize_str(v, MAX_TEXT_LEN)

    @field_validator("estimated_duration_weeks", "weekly_time_hours", mode="before")
    @classmethod
    def coerce_to_int(cls, v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 12

    @field_validator("tips", mode="before")
    @classmethod
    def sanitize_tips(cls, v):
        if not isinstance(v, list):
            return []
        return [_sanitize_str(t, MAX_SHORT_TEXT_LEN) for t in v if t]

    @field_validator("calibration_references", mode="before")
    @classmethod
    def sanitize_refs(cls, v):
        if not isinstance(v, list):
            return []
        return [_sanitize_str(r, MAX_SHORT_TEXT_LEN) for r in v if r]


# ===================================================================
# Dream analysis schemas (analyze_dream)
# ===================================================================

class AnalysisResponseSchema(BaseModel):
    """Response from analyze_dream."""
    category: str = Field(default="other", max_length=50)
    estimated_duration_weeks: int = Field(default=12, ge=1, le=520)
    difficulty: str = Field(default="medium", max_length=20)
    key_challenges: list[str] = Field(default_factory=list)
    recommended_approach: str = Field(default="", max_length=MAX_TEXT_LEN)

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, v):
        v = _sanitize_str(v, 50).lower().strip()
        return v if v in VALID_CATEGORIES else "other"

    @field_validator("difficulty", mode="before")
    @classmethod
    def validate_difficulty(cls, v):
        v = _sanitize_str(v, 20).lower().strip()
        return v if v in VALID_DIFFICULTIES else "medium"

    @field_validator("estimated_duration_weeks", mode="before")
    @classmethod
    def coerce_to_int(cls, v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 12

    @field_validator("key_challenges", mode="before")
    @classmethod
    def sanitize_challenges(cls, v):
        if not isinstance(v, list):
            return []
        return [_sanitize_str(c, MAX_SHORT_TEXT_LEN) for c in v if c]

    @field_validator("recommended_approach", mode="before")
    @classmethod
    def sanitize_approach(cls, v):
        return _sanitize_str(v, MAX_TEXT_LEN)


# ===================================================================
# Calibration question schemas
# ===================================================================

class CalibrationQuestionSchema(BaseModel):
    """A single calibration question."""
    question: str = Field(..., min_length=5, max_length=MAX_SHORT_TEXT_LEN)
    category: str = Field(default="specifics", max_length=30)

    @field_validator("question", mode="before")
    @classmethod
    def sanitize_question(cls, v):
        return _sanitize_str(v, MAX_SHORT_TEXT_LEN)

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, v):
        v = _sanitize_str(v, 30).lower().strip()
        return v if v in VALID_CALIBRATION_CATEGORIES else "specifics"


class CalibrationQuestionsResponseSchema(BaseModel):
    """Response from generate_calibration_questions."""
    sufficient: bool = Field(default=False)
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    missing_areas: list[str] = Field(default_factory=list)
    questions: list[CalibrationQuestionSchema] = Field(default_factory=list)

    @field_validator("confidence_score", mode="before")
    @classmethod
    def coerce_confidence(cls, v):
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.5

    @field_validator("missing_areas", mode="before")
    @classmethod
    def sanitize_areas(cls, v):
        if not isinstance(v, list):
            return []
        return [_sanitize_str(a, MAX_SHORT_TEXT_LEN) for a in v if a]


# ===================================================================
# Calibration summary schemas
# ===================================================================

class UserProfileSchema(BaseModel):
    """Structured user profile from calibration summary."""
    experience_level: str = Field(default="beginner", max_length=20)
    experience_details: str = Field(default="", max_length=MAX_DESCRIPTION_LEN)
    available_hours_per_week: int = Field(default=5, ge=1, le=168)
    preferred_schedule: str = Field(default="", max_length=MAX_SHORT_TEXT_LEN)
    budget: str = Field(default="", max_length=MAX_SHORT_TEXT_LEN)
    tools_available: list[str] = Field(default_factory=list)
    primary_motivation: str = Field(default="", max_length=MAX_SHORT_TEXT_LEN)
    secondary_motivations: list[str] = Field(default_factory=list)
    known_constraints: list[str] = Field(default_factory=list)
    success_definition: str = Field(default="", max_length=MAX_SHORT_TEXT_LEN)
    preferred_learning_style: str = Field(default="", max_length=MAX_SHORT_TEXT_LEN)
    timeline_preference: str = Field(default="", max_length=MAX_SHORT_TEXT_LEN)
    risk_tolerance: str = Field(default="medium", max_length=20)

    @field_validator("experience_level", mode="before")
    @classmethod
    def validate_experience(cls, v):
        v = _sanitize_str(v, 20).lower().strip()
        return v if v in VALID_EXPERIENCE_LEVELS else "beginner"

    @field_validator("risk_tolerance", mode="before")
    @classmethod
    def validate_risk(cls, v):
        v = _sanitize_str(v, 20).lower().strip()
        return v if v in VALID_RISK_LEVELS else "medium"

    @field_validator("available_hours_per_week", mode="before")
    @classmethod
    def coerce_hours(cls, v):
        try:
            return max(1, min(168, int(v)))
        except (TypeError, ValueError):
            return 5

    @field_validator(
        "experience_details", "preferred_schedule", "budget",
        "primary_motivation", "success_definition",
        "preferred_learning_style", "timeline_preference",
        mode="before",
    )
    @classmethod
    def sanitize_strings(cls, v):
        return _sanitize_str(v, MAX_SHORT_TEXT_LEN)

    @field_validator(
        "tools_available", "secondary_motivations", "known_constraints",
        mode="before",
    )
    @classmethod
    def sanitize_lists(cls, v):
        if not isinstance(v, list):
            return []
        return [_sanitize_str(item, MAX_SHORT_TEXT_LEN) for item in v if item]


class PlanRecommendationsSchema(BaseModel):
    """AI recommendations for plan generation."""
    suggested_pace: str = Field(default="moderate", max_length=20)
    focus_areas: list[str] = Field(default_factory=list)
    potential_pitfalls: list[str] = Field(default_factory=list)
    personalization_notes: str = Field(default="", max_length=MAX_TEXT_LEN)

    @field_validator("suggested_pace", mode="before")
    @classmethod
    def validate_pace(cls, v):
        v = _sanitize_str(v, 20).lower().strip()
        return v if v in VALID_PACES else "moderate"

    @field_validator("focus_areas", "potential_pitfalls", mode="before")
    @classmethod
    def sanitize_lists(cls, v):
        if not isinstance(v, list):
            return []
        return [_sanitize_str(item, MAX_SHORT_TEXT_LEN) for item in v if item]

    @field_validator("personalization_notes", mode="before")
    @classmethod
    def sanitize_notes(cls, v):
        return _sanitize_str(v, MAX_TEXT_LEN)


class CalibrationSummaryResponseSchema(BaseModel):
    """Response from generate_calibration_summary."""
    user_profile: UserProfileSchema = Field(default_factory=UserProfileSchema)
    plan_recommendations: PlanRecommendationsSchema = Field(
        default_factory=PlanRecommendationsSchema
    )
    enriched_description: str = Field(default="", max_length=MAX_TEXT_LEN)

    @field_validator("enriched_description", mode="before")
    @classmethod
    def sanitize_description(cls, v):
        return _sanitize_str(v, MAX_TEXT_LEN)


# ===================================================================
# Chat response schema
# ===================================================================

class ChatResponseSchema(BaseModel):
    """Response from chat / chat_async."""
    content: str = Field(default="", max_length=MAX_TEXT_LEN)
    tokens_used: int = Field(default=0, ge=0)
    model: str = Field(default="")

    @field_validator("content", mode="before")
    @classmethod
    def sanitize_content(cls, v):
        if v is None:
            return ""
        return _sanitize_str(v, MAX_TEXT_LEN)

    @field_validator("tokens_used", mode="before")
    @classmethod
    def coerce_tokens(cls, v):
        try:
            return max(0, int(v))
        except (TypeError, ValueError):
            return 0


class FunctionCallSchema(BaseModel):
    """Function call returned by AI."""
    name: str = Field(..., max_length=100)
    arguments: dict = Field(default_factory=dict)

    ALLOWED_FUNCTIONS: ClassVar[Set[str]] = {"create_task", "complete_task", "create_goal"}

    @field_validator("name", mode="before")
    @classmethod
    def validate_function_name(cls, v):
        v = _sanitize_str(v, 100)
        if v not in cls.ALLOWED_FUNCTIONS:
            raise ValueError(f"Unknown function '{v}'. Allowed: {cls.ALLOWED_FUNCTIONS}")
        return v


# ===================================================================
# Public validation functions — called from views / services
# ===================================================================

class AIValidationError(Exception):
    """Raised when AI output fails validation."""

    def __init__(self, message: str, errors: list | None = None):
        self.message = message
        self.errors = errors or []
        super().__init__(self.message)


def validate_plan_response(raw: dict) -> PlanResponseSchema:
    """Validate and sanitize a raw plan dict from the AI."""
    try:
        plan = PlanResponseSchema.model_validate(raw)
        logger.info(
            "Plan validated: %d goals, %d obstacles, %d calibration refs",
            len(plan.goals), len(plan.potential_obstacles),
            len(plan.calibration_references),
        )
        return plan
    except Exception as e:
        logger.error("Plan validation failed: %s | raw keys: %s", e, list(raw.keys()))
        raise AIValidationError(f"AI generated an invalid plan: {e}") from e


def validate_analysis_response(raw: dict) -> AnalysisResponseSchema:
    """Validate and sanitize a raw analysis dict from the AI."""
    try:
        return AnalysisResponseSchema.model_validate(raw)
    except Exception as e:
        logger.error("Analysis validation failed: %s", e)
        raise AIValidationError(f"AI generated an invalid analysis: {e}") from e


def validate_calibration_questions(raw: dict) -> CalibrationQuestionsResponseSchema:
    """Validate and sanitize calibration questions from the AI."""
    try:
        return CalibrationQuestionsResponseSchema.model_validate(raw)
    except Exception as e:
        logger.error("Calibration questions validation failed: %s", e)
        raise AIValidationError(f"AI generated invalid calibration questions: {e}") from e


def validate_calibration_summary(raw: dict) -> CalibrationSummaryResponseSchema:
    """Validate and sanitize calibration summary from the AI."""
    try:
        return CalibrationSummaryResponseSchema.model_validate(raw)
    except Exception as e:
        logger.error("Calibration summary validation failed: %s", e)
        raise AIValidationError(f"AI generated an invalid calibration summary: {e}") from e


def validate_chat_response(raw: dict) -> ChatResponseSchema:
    """Validate and sanitize a chat response dict from the AI."""
    try:
        return ChatResponseSchema.model_validate(raw)
    except Exception as e:
        logger.error("Chat response validation failed: %s", e)
        raise AIValidationError(f"AI generated an invalid chat response: {e}") from e


def validate_function_call(raw: dict) -> FunctionCallSchema:
    """Validate a function call from the AI."""
    try:
        return FunctionCallSchema.model_validate(raw)
    except Exception as e:
        logger.error("Function call validation failed: %s", e)
        raise AIValidationError(f"AI generated an invalid function call: {e}") from e


def validate_ai_output_safety(content: str) -> tuple[bool, str]:
    """
    Check if AI-generated output contains harmful content or character breach.

    This is a SECONDARY safety layer — the system prompt should prevent this,
    but this validates the AI didn't break character or produce harmful output.

    Returns:
        (is_safe, reason) - True if content is safe, else (False, reason string)
    """
    if not content:
        return True, ""

    # Check character integrity first (fast, no API)
    if not check_ai_character_integrity(content):
        logger.warning("AI output failed character integrity check")
        return False, "AI broke character"

    # Run content moderation on the output
    try:
        from core.moderation import ContentModerationService
        moderation = ContentModerationService()
        result = moderation.moderate_text(content, context='ai_output')
        if result.is_flagged:
            logger.warning(
                "AI OUTPUT FLAGGED: categories=%s, severity=%s",
                result.categories, result.severity
            )
            return False, f"AI output flagged: {','.join(result.categories)}"
    except Exception as e:
        # Don't block on moderation errors for output checks
        logger.error("AI output moderation error: %s", e)

    return True, ""


# Patterns that indicate the AI broke character or complied with a jailbreak
BROKEN_CHARACTER_PATTERNS = [
    re.compile(r'as\s+an?\s+AI\s+(language\s+)?model', re.IGNORECASE),
    re.compile(r'I\s+am\s+(just|only)\s+an?\s+(AI|language\s+model|chatbot)', re.IGNORECASE),
    re.compile(r'I\s+don\'?t\s+have\s+(personal\s+)?(feelings|emotions|opinions)', re.IGNORECASE),
    re.compile(r'(sure|okay|alright),?\s+I\'?ll\s+(pretend|act|role.?play|be)\s+', re.IGNORECASE),
    re.compile(r'\[DAN\]|\[JAILBREAK\]|\[NO\s+FILTER\]', re.IGNORECASE),
    re.compile(r'\*enters?\s+.*mode\*', re.IGNORECASE),
]


def check_ai_character_integrity(content: str) -> bool:
    """
    Check if the AI broke character or complied with a jailbreak.

    Returns True if integrity is maintained, False if broken.
    """
    for pattern in BROKEN_CHARACTER_PATTERNS:
        if pattern.search(content):
            logger.warning("AI character integrity breach detected: %s", pattern.pattern)
            return False
    return True


def check_plan_calibration_coherence(
    plan: PlanResponseSchema,
    calibration_profile: dict | None,
) -> list[str]:
    """
    Check that the plan actually reflects calibration data.

    Returns a list of warnings (empty = good). These are informational —
    the plan is still saved, but warnings are returned to the frontend
    so the user knows what to double-check.
    """
    if not calibration_profile:
        return []

    warnings = []
    profile = calibration_profile

    # Check hours alignment
    available_hours = profile.get("available_hours_per_week")
    if available_hours and plan.weekly_time_hours > available_hours * 1.5:
        warnings.append(
            f"Plan suggests {plan.weekly_time_hours}h/week but you said you "
            f"have ~{available_hours}h/week available. You may want to adjust."
        )

    # Check that goals exist
    if len(plan.goals) == 0:
        warnings.append("The plan has no goals — this shouldn't happen.")

    # Check that tasks have reasonable durations
    for goal in plan.goals:
        for task in goal.tasks:
            if task.duration_mins > 240:
                warnings.append(
                    f'Task "{task.title}" is {task.duration_mins} minutes '
                    f"({task.duration_mins / 60:.1f}h). Consider breaking it into smaller tasks."
                )

    # Check calibration references exist when calibration was done
    if not plan.calibration_references:
        warnings.append(
            "The AI did not cite specific calibration answers. "
            "The plan may be more generic than expected."
        )

    return warnings
