"""
Celery tasks for the Social system.

Handles story expiration cleanup and social event status transitions.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.social.tasks.expire_stories")
def expire_stories():
    """
    Delete expired stories (older than 24h).

    Stories set their own expires_at on save. This task removes any
    that have passed that timestamp, freeing storage and keeping
    queries fast.  Runs every hour via Celery beat (or on-demand).
    """
    from .models import Story

    now = timezone.now()
    expired = Story.objects.filter(expires_at__lt=now)
    count = expired.count()
    expired.delete()
    logger.info("Deleted %d expired stories", count)
    return count


@shared_task(name="apps.social.tasks.update_event_statuses")
def update_event_statuses():
    """
    Transition social events from 'upcoming' to 'active' or 'completed'
    based on their start_time / end_time.

    Runs periodically (e.g. every 15 minutes).
    """
    from .models import SocialEvent

    now = timezone.now()

    # upcoming -> active
    activated = SocialEvent.objects.filter(
        status="upcoming",
        start_time__lte=now,
        end_time__gt=now,
    ).update(status="active")

    # active (or upcoming that already passed) -> completed
    completed = SocialEvent.objects.filter(
        status__in=["upcoming", "active"],
        end_time__lte=now,
    ).update(status="completed")

    logger.info(
        "Event status transitions: %d activated, %d completed",
        activated,
        completed,
    )
    return {"activated": activated, "completed": completed}
