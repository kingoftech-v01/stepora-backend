"""
Celery tasks for the Plans system.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1, soft_time_limit=300, time_limit=360)
def process_checkin_responses(self, checkin_id):
    """Process user responses for an interactive check-in.

    This task runs the AI analysis after the user submits their
    questionnaire responses.
    """
    from .models import PlanCheckIn

    try:
        checkin = PlanCheckIn.objects.select_related("dream").get(id=checkin_id)
    except PlanCheckIn.DoesNotExist:
        logger.error("PlanCheckIn %s not found", checkin_id)
        return

    if checkin.status != "ai_processing":
        logger.warning(
            "PlanCheckIn %s not in ai_processing state (current: %s)",
            checkin_id,
            checkin.status,
        )
        return

    try:
        checkin.started_at = timezone.now()
        checkin.save(update_fields=["started_at"])

        # Delegate to PlanService for the actual AI processing
        from .services import PlanService

        PlanService.process_checkin(checkin)

        checkin.status = "completed"
        checkin.completed_at = timezone.now()
        checkin.save(update_fields=["status", "completed_at"])
        logger.info("CheckIn %s completed successfully", checkin_id)

    except Exception as exc:
        logger.exception("CheckIn %s failed: %s", checkin_id, exc)
        checkin.status = "failed"
        checkin.error_message = str(exc)[:500]
        checkin.save(update_fields=["status", "error_message"])
        raise self.retry(exc=exc)


@shared_task
def generate_plan_for_dream(dream_id, user_id):
    """Background task for AI plan generation.

    Delegates to the existing generate_dream_plan_task in apps.dreams.tasks
    for backward compatibility.
    """
    from apps.dreams.tasks import generate_dream_plan_task

    generate_dream_plan_task.delay(dream_id, user_id)
