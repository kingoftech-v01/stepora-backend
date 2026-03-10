"""
Celery tasks for the Circles system.

Handles circle challenge status transitions and expired invitation cleanup.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.circles.tasks.update_challenge_statuses")
def update_challenge_statuses():
    """
    Transition circle challenges from 'upcoming' to 'active' or 'completed'
    based on their start_date / end_date.

    Runs periodically (e.g. every hour).
    """
    from .models import CircleChallenge

    now = timezone.now()

    # upcoming -> active
    activated = CircleChallenge.objects.filter(
        status="upcoming",
        start_date__lte=now,
        end_date__gt=now,
    ).update(status="active")

    # active (or upcoming that already passed) -> completed
    completed = CircleChallenge.objects.filter(
        status__in=["upcoming", "active"],
        end_date__lte=now,
    ).update(status="completed")

    logger.info(
        "Challenge status transitions: %d activated, %d completed",
        activated,
        completed,
    )
    return {"activated": activated, "completed": completed}


@shared_task(name="apps.circles.tasks.expire_circle_invitations")
def expire_circle_invitations():
    """
    Mark expired circle invitations as 'expired'.

    Invitations have an expires_at timestamp. This task cleans up
    any pending invitations that have passed their expiry.
    """
    from .models import CircleInvitation

    now = timezone.now()
    expired = CircleInvitation.objects.filter(
        status="pending",
        expires_at__lt=now,
    ).update(status="expired")

    logger.info("Expired %d circle invitations", expired)
    return expired
