"""
Signals for the Dreams app.

Recalculates goal and dream progress when a task is deleted,
preventing stale progress values.
"""

import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_delete, sender="plans.Task")
def recalculate_goal_progress_on_task_delete(sender, instance, **kwargs):
    """
    Recalculate goal and dream progress when a task is deleted.

    Without this signal, deleting a task would leave the goal's
    progress_percentage stale (e.g., showing 50% when 1 of 2 tasks
    was deleted, leaving only 1 completed task out of 1).

    Args:
        sender: The Task model class.
        instance: The Task instance that was deleted.
    """
    try:
        goal = instance.goal
        goal.update_progress()
        logger.info("Recalculated progress for goal %s after task deletion.", goal.id)
    except Exception:
        logger.exception(
            "Failed to recalculate progress after task deletion for goal %s.",
            getattr(instance, "goal_id", "unknown"),
        )
