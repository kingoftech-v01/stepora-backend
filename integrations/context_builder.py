"""
Build rich context strings for AI check-in agents.

Queries stable data (dream description, calibration, persona, check-in history,
obstacles) and returns a formatted block that gets injected into the user message
so the AI *always* has full context about the dream and user.
"""

import json
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

# Max chars per calibration answer to keep token budget reasonable
_MAX_ANSWER_LEN = 250


def build_dream_context(dream, user):
    """
    Build a comprehensive context string for the AI agent.

    Queries:
      - Dream: description, category, ai_analysis
      - CalibrationResponse: all Q&A pairs for this dream
      - User persona: full persona JSON
      - Last 3 completed PlanCheckIn records (coaching, responses, pace, summary)
      - Active Obstacle records for this dream

    Returns:
        str — formatted multi-section context block (~1500-2500 tokens)
    """
    sections = []

    # --- 1. Dream Identity ---
    sections.append(_build_dream_identity(dream))

    # --- 2. AI Analysis ---
    if dream.ai_analysis:
        sections.append(_build_ai_analysis(dream))

    # --- 3. Calibration Q&A ---
    calibration = _build_calibration(dream)
    if calibration:
        sections.append(calibration)

    # --- 4. User Persona ---
    persona = _build_persona(user)
    if persona:
        sections.append(persona)

    # --- 5. Previous Check-in History ---
    history = _build_checkin_history(dream)
    if history:
        sections.append(history)

    # --- 6. Obstacles ---
    obstacles = _build_obstacles(dream)
    if obstacles:
        sections.append(obstacles)

    return "\n\n".join(sections)


def _build_dream_identity(dream):
    """Core dream info the AI must always see."""
    lines = ["=== DREAM CONTEXT ==="]
    lines.append(f"Title: {dream.title}")
    lines.append(f"Description: {dream.description or '(no description)'}")
    if dream.category:
        lines.append(f"Category: {dream.category}")
    if dream.target_date:
        target = dream.target_date.date() if hasattr(dream.target_date, 'date') else dream.target_date
        lines.append(f"Target date: {target}")
        created = dream.created_at.date() if dream.created_at else None
        if created:
            total_days = (target - created).days
            elapsed = (timezone.now().date() - created).days
            lines.append(f"Timeline: {elapsed} days elapsed of {total_days} total ({round(elapsed / max(1, total_days) * 100)}%)")
    lines.append(f"Current progress: {round(dream.progress_percentage, 1)}%")
    return "\n".join(lines)


def _build_ai_analysis(dream):
    """The AI's own initial analysis of feasibility / strategy."""
    analysis = dream.ai_analysis
    if isinstance(analysis, dict):
        text = analysis.get('analysis', json.dumps(analysis, ensure_ascii=False))
    elif isinstance(analysis, str):
        text = analysis
    else:
        text = str(analysis)
    # Truncate very long analyses
    if len(text) > 800:
        text = text[:800] + "..."
    return f"=== AI INITIAL ANALYSIS ===\n{text}"


def _build_calibration(dream):
    """Calibration Q&A pairs — the user's constraints, motivation, experience."""
    from apps.dreams.models import CalibrationResponse

    responses = CalibrationResponse.objects.filter(
        dream=dream
    ).order_by('question_number')[:15]

    if not responses:
        return None

    lines = ["=== CALIBRATION RESPONSES ==="]
    for r in responses:
        answer = r.answer or "(no answer)"
        if len(answer) > _MAX_ANSWER_LEN:
            answer = answer[:_MAX_ANSWER_LEN] + "..."
        cat = f" [{r.category}]" if r.category else ""
        lines.append(f"Q{r.question_number}{cat}: {r.question}")
        lines.append(f"  A: {answer}")
    return "\n".join(lines)


def _build_persona(user):
    """User persona — available hours, schedule, constraints, motivation."""
    persona = user.persona
    if not persona:
        return None

    lines = ["=== USER PERSONA ==="]
    key_labels = {
        'available_hours_per_week': 'Available hours/week',
        'preferred_schedule': 'Preferred schedule',
        'budget_range': 'Budget',
        'fitness_level': 'Fitness level',
        'learning_style': 'Learning style',
        'typical_day': 'Typical day',
        'occupation': 'Occupation',
        'global_motivation': 'Global motivation',
        'global_constraints': 'Global constraints',
        'astrological_sign': 'Astrological sign',
    }
    for key, label in key_labels.items():
        val = persona.get(key)
        if val:
            lines.append(f"- {label}: {val}")

    # Also include work schedule if available
    work = user.work_schedule
    if work:
        lines.append(f"- Work schedule: {json.dumps(work, ensure_ascii=False)}")

    return "\n".join(lines) if len(lines) > 1 else None


def _build_checkin_history(dream):
    """Last 3 completed check-ins — what was adjusted, user said, pace."""
    from apps.dreams.models import PlanCheckIn

    checkins = PlanCheckIn.objects.filter(
        dream=dream,
        status='completed',
    ).order_by('-completed_at')[:3]

    if not checkins:
        return None

    lines = ["=== PREVIOUS CHECK-INS (most recent first) ==="]
    for i, ci in enumerate(checkins):
        date_str = ci.completed_at.strftime('%Y-%m-%d') if ci.completed_at else '?'
        recency = ['most recent', '2nd most recent', '3rd most recent'][i] if i < 3 else f'{i+1}th'
        lines.append(f"\n--- Check-in ({recency}, {date_str}) ---")
        if ci.pace_status:
            lines.append(f"Pace: {ci.pace_status}")
        if ci.coaching_message:
            msg = ci.coaching_message[:300]
            if len(ci.coaching_message) > 300:
                msg += "..."
            lines.append(f"Coaching: {msg}")
        if ci.adjustment_summary:
            lines.append(f"Adjustments: {ci.adjustment_summary[:200]}")
        if ci.user_responses:
            # Compact summary of user answers
            resp_summary = json.dumps(ci.user_responses, ensure_ascii=False)
            if len(resp_summary) > 400:
                resp_summary = resp_summary[:400] + "..."
            lines.append(f"User responses: {resp_summary}")

    return "\n".join(lines)


def _build_obstacles(dream):
    """Active obstacles — predicted and actual blockers."""
    from apps.dreams.models import Obstacle

    obstacles = Obstacle.objects.filter(
        dream=dream,
        status='active',
    ).select_related('milestone', 'goal')[:10]

    if not obstacles:
        return None

    lines = ["=== ACTIVE OBSTACLES ==="]
    for obs in obstacles:
        scope = ""
        if obs.milestone:
            scope = f" (milestone: {obs.milestone.title})"
        elif obs.goal:
            scope = f" (goal: {obs.goal.title})"
        lines.append(f"- [{obs.obstacle_type}]{scope} {obs.title}: {obs.description[:150]}")
        if obs.solution:
            lines.append(f"  Suggested solution: {obs.solution[:150]}")

    return "\n".join(lines)
