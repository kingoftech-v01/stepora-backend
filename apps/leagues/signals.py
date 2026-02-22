"""
Signals for the Leagues & Ranking system.

Listens for XP changes on the User model to automatically update
league standings. When a user's XP changes, their league placement
and rank are recalculated.
"""

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.users.models import User
from .services import LeagueService

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=User)
def track_xp_change(sender, instance, **kwargs):
    """
    Track whether XP has changed before the User is saved.

    Stores the previous XP value on the instance so that the
    post_save signal can detect if an update is needed.

    Args:
        sender: The User model class.
        instance: The User instance being saved.
    """
    if instance.pk:
        try:
            previous = User.objects.get(pk=instance.pk)
            instance._previous_xp = previous.xp
        except User.DoesNotExist:
            instance._previous_xp = None
    else:
        instance._previous_xp = None


@receiver(post_save, sender=User)
def update_league_standing_on_xp_change(sender, instance, created, **kwargs):
    """
    Update the user's league standing when their XP changes.

    Triggered after a User is saved. If the XP value has changed
    (or the user was just created), the league standing is recalculated
    to reflect the new XP.

    Args:
        sender: The User model class.
        instance: The User instance that was saved.
        created: Whether this is a newly created User.
    """
    previous_xp = getattr(instance, '_previous_xp', None)

    # Update standing if XP changed or user was just created with XP > 0
    xp_changed = previous_xp is not None and previous_xp != instance.xp
    new_user_with_xp = created and instance.xp > 0

    if xp_changed or new_user_with_xp:
        try:
            LeagueService.update_standing(instance)
            logger.info(
                "League standing updated for user %s (XP: %d -> %d).",
                instance.id,
                previous_xp if previous_xp is not None else 0,
                instance.xp
            )
        except Exception as e:
            # Log the error but do not prevent the User save from succeeding
            logger.error(
                "Failed to update league standing for user %s: %s",
                instance.id, str(e)
            )
