"""
Centralized calibration status management.

Single source of truth for determining and updating Dream.calibration_status.
All status transitions go through check_and_update_calibration_status() instead
of inline logic scattered across views.

IMPORTANT: CalibrationResponse.answer is EncryptedTextField. DB-level filters
(answer="", answer__gt="") compare ciphertext, not plaintext. All answer checks
MUST fetch responses and filter in Python after decryption.
"""
import logging

from apps.plans.models import CalibrationResponse, Goal

logger = logging.getLogger(__name__)

# Minimum answers required before calibration can be marked completed
MIN_ANSWERS_FOR_COMPLETION = 7


def get_calibration_counts(dream):
    """
    Fetch all calibration responses and count answered/unanswered in Python.
    Returns (all_responses, answered_count, unanswered_count).

    Uses Python filtering because answer is EncryptedTextField —
    DB filters on encrypted fields compare ciphertext, not plaintext.
    """
    all_responses = list(
        CalibrationResponse.objects.filter(dream=dream).order_by("question_number")
    )
    answered = [cr for cr in all_responses if cr.answer and cr.answer.strip()]
    unanswered = [cr for cr in all_responses if not cr.answer or not cr.answer.strip()]
    return all_responses, len(answered), len(unanswered)


def get_answered_qa_pairs(dream):
    """
    Return list of {"question": ..., "answer": ...} for answered questions.
    Filters in Python (EncryptedTextField).
    """
    all_responses = CalibrationResponse.objects.filter(dream=dream).order_by(
        "question_number"
    )
    return [
        {"question": cr.question, "answer": cr.answer}
        for cr in all_responses
        if cr.answer and cr.answer.strip()
    ]


def get_unanswered_responses(dream):
    """
    Return queryset-like list of unanswered CalibrationResponse objects.
    Filters in Python (EncryptedTextField).
    """
    all_responses = list(
        CalibrationResponse.objects.filter(dream=dream).order_by("question_number")
    )
    return [cr for cr in all_responses if not cr.answer or not cr.answer.strip()]


def check_and_update_calibration_status(dream):
    """
    Evaluate calibration conditions and update status if needed.
    Returns the current status after evaluation.

    Rules (priority order):
    1. skipped → stays skipped (final state, explicit user choice)
    2. completed → stays completed (final state)
    3. Goals exist (plan already generated) → completed
    4. ≥7 answers AND 0 unanswered → completed
    5. CalibrationResponses exist with unanswered → in_progress
    6. Otherwise → pending
    """
    current = dream.calibration_status

    # Rule 1 & 2: Final states
    if current in ("skipped", "completed"):
        return current

    # Rule 3: Plan already generated = calibration is done
    if Goal.objects.filter(dream=dream).exists():
        if current != "completed":
            dream.calibration_status = "completed"
            dream.save(update_fields=["calibration_status"])
            logger.info(
                f"Calibration auto-completed for dream {dream.id}: plan already exists"
            )
        return "completed"

    # Rule 4 & 5: Check answers
    all_responses, answered_count, unanswered_count = get_calibration_counts(dream)

    if answered_count >= MIN_ANSWERS_FOR_COMPLETION and unanswered_count == 0:
        dream.calibration_status = "completed"
        dream.save(update_fields=["calibration_status"])
        logger.info(
            f"Calibration completed for dream {dream.id}: "
            f"{answered_count} answers, 0 unanswered"
        )
        return "completed"

    # Rule 5: Questions exist but some unanswered
    if len(all_responses) > 0:
        if current != "in_progress":
            dream.calibration_status = "in_progress"
            dream.save(update_fields=["calibration_status"])
        return "in_progress"

    # Rule 6: No questions at all
    return current  # stays pending (or whatever it was)
