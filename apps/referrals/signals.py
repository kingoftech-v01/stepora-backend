"""
Signals for the Referrals system.
Auto-create a ReferralCode for every new user.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="users.User")
def create_referral_code(sender, instance, created, **kwargs):
    """Automatically create a ReferralCode for every new user."""
    if created:
        from .models import ReferralCode

        ReferralCode.objects.get_or_create(user=instance)
