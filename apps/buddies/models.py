"""
Models for the Buddies system.

Implements Dream Buddy pairing: an accountability partnership between
two users. Buddies can track each other's progress, send encouragement,
and share goals for mutual motivation.
"""

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from encrypted_model_fields.fields import EncryptedTextField


class BuddyPairing(models.Model):
    """
    Represents a Dream Buddy accountability pairing between two users.

    Each pairing has a compatibility score calculated at match time
    and tracks the lifecycle of the partnership from creation through
    active use to optional ending.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this buddy pairing.",
    )
    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="buddy_pairings_as_user1",
        help_text="The first user in the pairing (initiator).",
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="buddy_pairings_as_user2",
        help_text="The second user in the pairing (matched partner).",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
        help_text="Current status of the buddy pairing.",
    )
    compatibility_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Compatibility score between 0.0 and 1.0, calculated at match time.",
    )

    encouragement_streak = models.IntegerField(
        default=0, help_text="Current consecutive-day encouragement streak."
    )
    best_encouragement_streak = models.IntegerField(
        default=0, help_text="Best-ever consecutive-day encouragement streak."
    )
    last_encouragement_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last encouragement sent in this pairing.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the pairing ended (completed or cancelled).",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When a pending buddy request expires (auto-cancelled after 7 days).",
    )

    class Meta:
        db_table = "buddy_pairings"
        ordering = ["-created_at"]
        verbose_name = "Buddy Pairing"
        verbose_name_plural = "Buddy Pairings"
        indexes = [
            models.Index(fields=["user1", "status"], name="idx_buddy_user1_status"),
            models.Index(fields=["user2", "status"], name="idx_buddy_user2_status"),
            models.Index(fields=["status"], name="idx_buddy_status"),
            models.Index(fields=["-created_at"], name="idx_buddy_created"),
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
        help_text="Unique identifier for this encouragement.",
    )
    pairing = models.ForeignKey(
        BuddyPairing,
        on_delete=models.CASCADE,
        related_name="encouragements",
        help_text="The buddy pairing this encouragement belongs to.",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_encouragements",
        help_text="The user who sent the encouragement.",
    )
    message = EncryptedTextField(
        blank=True,
        default="",
        help_text="Optional motivational message (encrypted at rest).",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "buddy_encouragements"
        ordering = ["-created_at"]
        verbose_name = "Buddy Encouragement"
        verbose_name_plural = "Buddy Encouragements"
        indexes = [
            models.Index(
                fields=["pairing", "-created_at"], name="idx_encourage_pairing"
            ),
            models.Index(fields=["sender"], name="idx_encourage_sender"),
        ]

    def __str__(self):
        preview = (
            self.message[:50] + "..."
            if len(self.message) > 50
            else (self.message or "(no message)")
        )
        return f"{self.sender.display_name or self.sender.email}: {preview}"


class AccountabilityContract(models.Model):
    """
    Represents an accountability contract between two buddies.

    A contract defines shared goals with measurable targets, a check-in
    frequency, and a date range. Both partners track progress via check-ins
    and can compare results side by side.
    """

    CHECK_IN_FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("biweekly", "Bi-weekly"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this contract.",
    )
    pairing = models.ForeignKey(
        "BuddyPairing",
        on_delete=models.CASCADE,
        related_name="contracts",
        help_text="The buddy pairing this contract belongs to.",
    )
    title = models.CharField(
        max_length=200, help_text="Title of the accountability contract."
    )
    description = models.TextField(
        blank=True, help_text="Optional description of the contract."
    )
    goals = models.JSONField(
        default=list, help_text="List of goals: [{title, target, unit}]."
    )
    check_in_frequency = models.CharField(
        max_length=20,
        choices=CHECK_IN_FREQUENCY_CHOICES,
        default="weekly",
        help_text="How often partners should check in.",
    )
    start_date = models.DateField(help_text="When the contract period begins.")
    end_date = models.DateField(help_text="When the contract period ends.")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
        help_text="Current status of the contract.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_contracts",
        help_text="The user who created this contract.",
    )
    accepted_by_partner = models.BooleanField(
        default=False, help_text="Whether the partner has accepted this contract."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "buddy_contracts"
        ordering = ["-created_at"]
        verbose_name = "Accountability Contract"
        verbose_name_plural = "Accountability Contracts"
        indexes = [
            models.Index(
                fields=["pairing", "status"], name="idx_contract_pairing_status"
            ),
            models.Index(fields=["created_by"], name="idx_contract_created_by"),
            models.Index(fields=["-created_at"], name="idx_contract_created"),
        ]

    def __str__(self):
        return f"Contract: {self.title} ({self.status})"


class ContractCheckIn(models.Model):
    """
    Represents a single check-in entry for an accountability contract.

    Each check-in records progress against the contract's goals,
    an optional note, and the user's current mood.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this check-in.",
    )
    contract = models.ForeignKey(
        AccountabilityContract,
        on_delete=models.CASCADE,
        related_name="check_ins",
        help_text="The contract this check-in belongs to.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contract_check_ins",
        help_text="The user who submitted this check-in.",
    )
    progress = models.JSONField(
        default=dict,
        help_text="Progress values keyed by goal index: {goal_index: value}.",
    )
    note = models.TextField(
        blank=True, help_text="Optional note accompanying the check-in."
    )
    mood = models.CharField(
        max_length=20, blank=True, help_text="User mood at time of check-in."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "buddy_contract_check_ins"
        ordering = ["-created_at"]
        verbose_name = "Contract Check-In"
        verbose_name_plural = "Contract Check-Ins"
        indexes = [
            models.Index(fields=["contract", "user"], name="idx_checkin_contract_user"),
            models.Index(
                fields=["contract", "-created_at"], name="idx_checkin_contract_date"
            ),
        ]

    def __str__(self):
        return f"Check-in by {self.user_id} on {self.created_at:%Y-%m-%d}"
