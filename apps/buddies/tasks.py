"""
Celery tasks for the Buddies system.

Handles periodic check-in reminders for buddy pairings.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


@shared_task(name="apps.buddies.tasks.send_buddy_checkin_reminders")
def send_buddy_checkin_reminders():
    """
    Send check-in reminders for buddy pairings with no recent encouragement.

    Notifies both users when the last encouragement was more than 3 days ago.
    Runs daily via Celery beat.
    """
    from apps.buddies.models import BuddyPairing
    from apps.notifications.models import Notification
    from apps.notifications.services import NotificationService

    now = timezone.now()
    threshold = now - timedelta(days=3)
    sent = 0

    stale_pairings = (
        BuddyPairing.objects.filter(
            status="active",
        )
        .filter(
            Q(last_encouragement_at__lt=threshold)
            | Q(last_encouragement_at__isnull=True)
        )
        .select_related("user1", "user2")
    )

    for pairing in stale_pairings:
        for user in [pairing.user1, pairing.user2]:
            partner = pairing.user2 if user == pairing.user1 else pairing.user1

            # Don't send if we already sent a reminder in the last 24h
            recent_reminder = Notification.objects.filter(
                user=user,
                notification_type="buddy",
                data__pairing_id=str(pairing.id),
                created_at__gte=now - timedelta(hours=24),
            ).exists()

            if recent_reminder:
                continue

            try:
                NotificationService.create(
                    user=user,
                    title=_("Check in with your buddy!"),
                    body=_(
                        "It's been a while since you encouraged "
                        "%(name)s. "
                        "Send them some motivation!"
                    )
                    % {"name": partner.display_name or _("your buddy")},
                    notification_type="buddy",
                    scheduled_for=now,
                    status="sent",
                    data={"pairing_id": str(pairing.id), "type": "checkin_reminder"},
                )
                sent += 1
            except Exception:
                logger.exception(
                    "Failed to send buddy checkin reminder for pairing %s", pairing.id
                )

    logger.info("Sent %d buddy check-in reminders", sent)
    return sent


@shared_task(name="apps.buddies.tasks.expire_pending_buddy_requests")
def expire_pending_buddy_requests():
    """
    Cancel pending buddy requests that have expired.
    Runs daily to clean up requests older than 7 days.
    """
    from django.utils import timezone

    from .models import BuddyPairing

    now = timezone.now()
    expired = BuddyPairing.objects.filter(
        status="pending",
        expires_at__lt=now,
        expires_at__isnull=False,
    )
    count = expired.update(status="cancelled", ended_at=now)
    logger.info("Expired %d pending buddy requests", count)
    return count
