"""
Celery tasks for the Gamification system.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.gamification.tasks.check_broken_streaks")
def check_broken_streaks():
    """Reset broken streaks and send at-risk notifications.

    Runs daily at midnight UTC. Delegates to StreakService.reset_broken_streaks
    which handles:
    - Resetting streaks for users who missed 2+ days
    - Sending at-risk push notifications for meaningful streaks (3+ days)
    """
    from .services import StreakService

    result = StreakService.reset_broken_streaks()
    logger.info(
        "check_broken_streaks completed: %d reset, %d notified",
        result["reset"],
        result["notified"],
    )
    return result


@shared_task(name="apps.gamification.tasks.refresh_leaderboard_cache")
def refresh_leaderboard_cache():
    """Refresh cached leaderboard data."""
    logger.info("Leaderboard cache refresh triggered.")
    # Placeholder for leaderboard cache refresh logic
