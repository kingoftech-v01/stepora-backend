"""
Celery tasks for the Friends system.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def cleanup_rejected_requests():
    """Clean up rejected friend requests older than 30 days."""
    from datetime import timedelta

    from django.utils import timezone

    from .models import Friendship

    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = Friendship.objects.filter(
        status="rejected", updated_at__lt=cutoff
    ).delete()
    logger.info("Cleaned up %d rejected friend requests", deleted)
