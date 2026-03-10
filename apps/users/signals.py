"""
Signals for users app.
Auto-create GamificationProfile when a new User is created.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="users.User")
def create_gamification_profile(sender, instance, created, **kwargs):
    """Automatically create a GamificationProfile for every new user."""
    if created:
        from .models import GamificationProfile

        GamificationProfile.objects.get_or_create(user=instance)
