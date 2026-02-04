"""
Models for the Buddies system.

Implements Dream Buddy pairing: an accountability partnership between
two users. Buddies can track each other's progress, send encouragement,
and share goals for mutual motivation.
"""

import uuid

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.users.models import User


class BuddyPairing(models.Model):
    """
    Represents a Dream Buddy accountability pairing between two users.

    Each pairing has a compatibility score calculated at match time
    and tracks the lifecycle of the partnership from creation through
    active use to optional ending.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this buddy pairing.'
    )
    user1 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='buddy_pairings_as_user1',
        help_text='The first user in the pairing (initiator).'
    )
    user2 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='buddy_pairings_as_user2',
        help_text='The second user in the pairing (matched partner).'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text='Current status of the buddy pairing.'
    )
    compatibility_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text='Compatibility score between 0.0 and 1.0, calculated at match time.'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when the pairing ended (completed or cancelled).'
    )

    class Meta:
        db_table = 'buddy_pairings'
        ordering = ['-created_at']
        verbose_name = 'Buddy Pairing'
        verbose_name_plural = 'Buddy Pairings'
        indexes = [
            models.Index(fields=['user1', 'status'], name='idx_buddy_user1_status'),
            models.Index(fields=['user2', 'status'], name='idx_buddy_user2_status'),
            models.Index(fields=['status'], name='idx_buddy_status'),
            models.Index(fields=['-created_at'], name='idx_buddy_created'),
        ]

    def __str__(self):
        return (
            f"Buddy: {self.user1.display_name or self.user1.email} <-> "
            f"{self.user2.display_name or self.user2.email} ({self.status})"
        )


class BuddyEncouragement(models.Model):
    """
    Represents an encouragement message sent between buddies.

    Users in an active pairing can send motivational messages
    to each other to maintain accountability.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this encouragement.'
    )
    pairing = models.ForeignKey(
        BuddyPairing,
        on_delete=models.CASCADE,
        related_name='encouragements',
        help_text='The buddy pairing this encouragement belongs to.'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_encouragements',
        help_text='The user who sent the encouragement.'
    )
    message = models.TextField(
        blank=True,
        default='',
        help_text='Optional motivational message.'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'buddy_encouragements'
        ordering = ['-created_at']
        verbose_name = 'Buddy Encouragement'
        verbose_name_plural = 'Buddy Encouragements'
        indexes = [
            models.Index(fields=['pairing', '-created_at'], name='idx_encourage_pairing'),
            models.Index(fields=['sender'], name='idx_encourage_sender'),
        ]

    def __str__(self):
        preview = self.message[:50] + '...' if len(self.message) > 50 else (self.message or '(no message)')
        return f"{self.sender.display_name or self.sender.email}: {preview}"
