"""
Models for the Social system.

Implements friendships, follows, and activity feeds for the DreamPlanner
community. Friendships are bidirectional (require acceptance), while
follows are unidirectional.
"""

import uuid

from django.db import models

from apps.users.models import User


class Friendship(models.Model):
    """
    Represents a friendship request/relationship between two users.

    Friendships are bidirectional and require mutual acceptance.
    user1 is always the sender of the request and user2 is the receiver.
    Status transitions: pending -> accepted/rejected.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this friendship.'
    )
    user1 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='friendships_sent',
        help_text='The user who sent the friend request.'
    )
    user2 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='friendships_received',
        help_text='The user who received the friend request.'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text='Current status of the friendship.'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'friendships'
        ordering = ['-created_at']
        verbose_name = 'Friendship'
        verbose_name_plural = 'Friendships'
        unique_together = [['user1', 'user2']]
        indexes = [
            models.Index(fields=['user1', 'status'], name='idx_friendship_user1_status'),
            models.Index(fields=['user2', 'status'], name='idx_friendship_user2_status'),
            models.Index(fields=['status'], name='idx_friendship_status'),
            models.Index(fields=['-created_at'], name='idx_friendship_created'),
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
        help_text='Unique identifier for this follow.'
    )
    follower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='following_set',
        help_text='The user who is following.'
    )
    following = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='followers_set',
        help_text='The user being followed.'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_follows'
        ordering = ['-created_at']
        verbose_name = 'User Follow'
        verbose_name_plural = 'User Follows'
        unique_together = [['follower', 'following']]
        indexes = [
            models.Index(fields=['follower'], name='idx_follow_follower'),
            models.Index(fields=['following'], name='idx_follow_following'),
        ]

    def __str__(self):
        return (
            f"{self.follower.display_name or self.follower.email} follows "
            f"{self.following.display_name or self.following.email}"
        )


class ActivityFeedItem(models.Model):
    """
    Represents an item in the social activity feed.

    Activity items are generated when users complete tasks, achieve dreams,
    reach milestones, join circles, or match with buddies. The feed shows
    activity from friends and followed users.
    """

    ACTIVITY_TYPE_CHOICES = [
        ('task_completed', 'Task Completed'),
        ('dream_completed', 'Dream Completed'),
        ('milestone_reached', 'Milestone Reached'),
        ('buddy_matched', 'Buddy Matched'),
        ('circle_joined', 'Circle Joined'),
        ('level_up', 'Level Up'),
        ('streak_milestone', 'Streak Milestone'),
        ('badge_earned', 'Badge Earned'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this activity item.'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activity_items',
        help_text='The user who performed the activity.'
    )
    activity_type = models.CharField(
        max_length=30,
        choices=ACTIVITY_TYPE_CHOICES,
        db_index=True,
        help_text='The type of activity.'
    )
    content = models.JSONField(
        default=dict,
        blank=True,
        help_text='Structured content data for the activity (e.g., task title, dream name).'
    )
    related_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='related_activity_items',
        help_text='Another user related to this activity (e.g., buddy partner).'
    )
    data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional metadata for the activity.'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'activity_feed_items'
        ordering = ['-created_at']
        verbose_name = 'Activity Feed Item'
        verbose_name_plural = 'Activity Feed Items'
        indexes = [
            models.Index(fields=['user', '-created_at'], name='idx_activity_user_date'),
            models.Index(fields=['activity_type'], name='idx_activity_type'),
            models.Index(fields=['-created_at'], name='idx_activity_created'),
        ]

    def __str__(self):
        return f"{self.user.display_name or self.user.email}: {self.activity_type}"
