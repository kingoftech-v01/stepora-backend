"""
Models for the Friends system.

Implements friendships, follows, blocking, and reporting.
Friendships are bidirectional (require acceptance), while follows
are unidirectional.
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from encrypted_model_fields.fields import EncryptedTextField


class BlockedUser(models.Model):
    """
    Represents a user blocking another user.

    Blocked users are excluded from search results, friend requests,
    follows, buddy matching, and circle interactions.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_users",
        help_text="The user who performed the block.",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_by",
        help_text="The user who was blocked.",
    )
    reason = EncryptedTextField(
        blank=True,
        default="",
        help_text="Optional reason for blocking (encrypted at rest).",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "blocked_users"
        ordering = ["-created_at"]
        verbose_name = "Blocked User"
        verbose_name_plural = "Blocked Users"
        constraints = [
            models.UniqueConstraint(
                fields=["blocker", "blocked"], name="unique_blocker_blocked"
            ),
        ]
        indexes = [
            models.Index(fields=["blocker"], name="idx_blocked_blocker"),
            models.Index(fields=["blocked"], name="idx_blocked_blocked"),
        ]

    def __str__(self):
        return (
            f"{self.blocker.display_name or self.blocker.email} blocked "
            f"{self.blocked.display_name or self.blocked.email}"
        )

    @staticmethod
    def is_blocked(user_a, user_b):
        """Check if either user has blocked the other."""
        return BlockedUser.objects.filter(
            Q(blocker=user_a, blocked=user_b) | Q(blocker=user_b, blocked=user_a)
        ).exists()


class ReportedUser(models.Model):
    """
    Represents a user report for moderation.
    """

    CATEGORY_CHOICES = [
        ("spam", "Spam"),
        ("harassment", "Harassment"),
        ("inappropriate", "Inappropriate Content"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("reviewed", "Reviewed"),
        ("dismissed", "Dismissed"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_made",
        help_text="The user who filed the report.",
    )
    reported = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_received",
        help_text="The user being reported.",
    )
    reason = EncryptedTextField(
        help_text="Description of why the user is being reported (encrypted at rest)."
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="other",
        help_text="Category of the report.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    admin_notes = models.TextField(
        blank=True, default="", help_text="Internal notes from admin review."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reported_users"
        ordering = ["-created_at"]
        verbose_name = "Reported User"
        verbose_name_plural = "Reported Users"
        indexes = [
            models.Index(fields=["status"], name="idx_report_status"),
            models.Index(fields=["-created_at"], name="idx_report_created"),
        ]

    def __str__(self):
        return (
            f"Report: {self.reporter.display_name or self.reporter.email} -> "
            f"{self.reported.display_name or self.reported.email} ({self.category})"
        )


class Friendship(models.Model):
    """
    Represents a friendship request/relationship between two users.

    Friendships are bidirectional and require mutual acceptance.
    user1 is always the sender of the request and user2 is the receiver.
    Status transitions: pending -> accepted/rejected.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this friendship.",
    )
    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friendships_sent",
        help_text="The user who sent the friend request.",
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friendships_received",
        help_text="The user who received the friend request.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
        help_text="Current status of the friendship.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "friendships"
        ordering = ["-created_at"]
        verbose_name = "Friendship"
        verbose_name_plural = "Friendships"
        constraints = [
            models.UniqueConstraint(
                fields=["user1", "user2"], name="unique_friendship_pair"
            ),
        ]
        indexes = [
            models.Index(
                fields=["user1", "status"], name="idx_friendship_user1_status"
            ),
            models.Index(
                fields=["user2", "status"], name="idx_friendship_user2_status"
            ),
            models.Index(fields=["status"], name="idx_friendship_status"),
            models.Index(fields=["-created_at"], name="idx_friendship_created"),
        ]

    def __str__(self):
        return (
            f"{self.user1.display_name or self.user1.email} -> "
            f"{self.user2.display_name or self.user2.email} ({self.status})"
        )


class UserFollow(models.Model):
    """
    Represents a unidirectional follow relationship.

    Unlike friendships, follows do not require acceptance. A user can
    follow anyone to see their public activity in the feed.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this follow.",
    )
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following_set",
        help_text="The user who is following.",
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followers_set",
        help_text="The user being followed.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_follows"
        ordering = ["-created_at"]
        verbose_name = "User Follow"
        verbose_name_plural = "User Follows"
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "following"], name="unique_follower_following"
            ),
        ]
        indexes = [
            models.Index(fields=["follower"], name="idx_follow_follower"),
            models.Index(fields=["following"], name="idx_follow_following"),
        ]

    def __str__(self):
        return (
            f"{self.follower.display_name or self.follower.email} follows "
            f"{self.following.display_name or self.following.email}"
        )
