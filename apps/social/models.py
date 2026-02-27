"""
Models for the Social system.

Implements friendships, follows, activity feeds, blocking, and reporting
for the DreamPlanner community. Friendships are bidirectional (require
acceptance), while follows are unidirectional.
"""

import uuid

from django.db import models
from django.db.models import Q
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField

from apps.users.models import User


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
        User,
        on_delete=models.CASCADE,
        related_name='blocked_users',
        help_text='The user who performed the block.'
    )
    blocked = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='blocked_by',
        help_text='The user who was blocked.'
    )
    reason = EncryptedTextField(
        blank=True,
        default='',
        help_text='Optional reason for blocking (encrypted at rest).'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'blocked_users'
        ordering = ['-created_at']
        verbose_name = 'Blocked User'
        verbose_name_plural = 'Blocked Users'
        constraints = [
            models.UniqueConstraint(fields=['blocker', 'blocked'], name='unique_blocker_blocked'),
        ]
        indexes = [
            models.Index(fields=['blocker'], name='idx_blocked_blocker'),
            models.Index(fields=['blocked'], name='idx_blocked_blocked'),
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
        ('spam', 'Spam'),
        ('harassment', 'Harassment'),
        ('inappropriate', 'Inappropriate Content'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('dismissed', 'Dismissed'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reports_made',
        help_text='The user who filed the report.'
    )
    reported = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reports_received',
        help_text='The user being reported.'
    )
    reason = EncryptedTextField(
        help_text='Description of why the user is being reported (encrypted at rest).'
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='other',
        help_text='Category of the report.'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
    )
    admin_notes = models.TextField(
        blank=True,
        default='',
        help_text='Internal notes from admin review.'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reported_users'
        ordering = ['-created_at']
        verbose_name = 'Reported User'
        verbose_name_plural = 'Reported Users'
        indexes = [
            models.Index(fields=['status'], name='idx_report_status'),
            models.Index(fields=['-created_at'], name='idx_report_created'),
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
        constraints = [
            models.UniqueConstraint(fields=['user1', 'user2'], name='unique_friendship_pair'),
        ]
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
        constraints = [
            models.UniqueConstraint(fields=['follower', 'following'], name='unique_follower_following'),
        ]
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


class ActivityLike(models.Model):
    """
    Represents a like on an activity feed item.

    Each user can like an activity item at most once. Liking is idempotent:
    re-liking an already-liked item is a no-op.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activity_likes',
        help_text='The user who liked the activity.',
    )
    activity = models.ForeignKey(
        ActivityFeedItem,
        on_delete=models.CASCADE,
        related_name='likes',
        help_text='The activity feed item that was liked.',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'activity_likes'
        ordering = ['-created_at']
        verbose_name = 'Activity Like'
        verbose_name_plural = 'Activity Likes'
        constraints = [
            models.UniqueConstraint(fields=['user', 'activity'], name='unique_user_activity_like'),
        ]
        indexes = [
            models.Index(fields=['activity'], name='idx_activity_like_activity'),
            models.Index(fields=['user'], name='idx_activity_like_user'),
        ]

    def __str__(self):
        return f"{self.user.display_name or self.user.email} liked {self.activity_id}"


class ActivityComment(models.Model):
    """
    Represents a comment on an activity feed item.

    Users can leave multiple comments on any activity item visible
    in their feed.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activity_comments',
        help_text='The user who wrote the comment.',
    )
    activity = models.ForeignKey(
        ActivityFeedItem,
        on_delete=models.CASCADE,
        related_name='comments',
        help_text='The activity feed item that was commented on.',
    )
    text = EncryptedTextField(help_text='The comment text (encrypted at rest).')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'activity_comments'
        ordering = ['created_at']
        verbose_name = 'Activity Comment'
        verbose_name_plural = 'Activity Comments'
        indexes = [
            models.Index(fields=['activity', 'created_at'], name='idx_activity_comment_activity'),
            models.Index(fields=['user'], name='idx_activity_comment_user'),
        ]

    def __str__(self):
        return f"{self.user.display_name or self.user.email} commented on {self.activity_id}"


class RecentSearch(models.Model):
    """Stores recent search queries for a user."""

    SEARCH_TYPE_CHOICES = [
        ('users', 'Users'),
        ('dreams', 'Dreams'),
        ('all', 'All'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='recent_searches',
    )
    query = EncryptedCharField(max_length=200)
    search_type = models.CharField(
        max_length=10, choices=SEARCH_TYPE_CHOICES, default='all',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recent_searches'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.email}: {self.query}"


class DreamPost(models.Model):
    """
    A dream shared publicly on the social feed.

    Users can post their dreams with captions, images, and GoFundMe links
    for community support and encouragement.
    """

    VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('followers', 'Followers Only'),
        ('private', 'Private'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='dream_posts',
    )
    dream = models.ForeignKey(
        'dreams.Dream',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='social_posts',
        help_text='Optionally linked dream.',
    )
    content = EncryptedTextField(
        help_text='Caption/description (encrypted at rest).',
    )
    image_url = models.URLField(blank=True, help_text='Optional image URL.')
    image_file = models.ImageField(
        upload_to='dream_posts/', blank=True,
        help_text='Optional uploaded image.',
    )
    gofundme_url = models.URLField(
        blank=True, help_text='External fundraising link.',
    )
    visibility = models.CharField(
        max_length=15, choices=VISIBILITY_CHOICES, default='public', db_index=True,
    )
    likes_count = models.IntegerField(default=0, help_text='Denormalized like count.')
    comments_count = models.IntegerField(default=0, help_text='Denormalized comment count.')
    shares_count = models.IntegerField(default=0)
    is_pinned = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dream_posts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='idx_dreampost_user_date'),
            models.Index(fields=['-created_at'], name='idx_dreampost_created'),
            models.Index(fields=['visibility'], name='idx_dreampost_visibility'),
        ]

    def __str__(self):
        preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{self.user.display_name or self.user.email}: {preview}"


class DreamPostLike(models.Model):
    """Like on a dream post. One per user per post."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(
        DreamPost, on_delete=models.CASCADE, related_name='likes',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='dream_post_likes',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dream_post_likes'
        constraints = [
            models.UniqueConstraint(fields=['post', 'user'], name='unique_dreampost_like'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.display_name or self.user.email} liked post {self.post_id}"


class DreamPostComment(models.Model):
    """Comment on a dream post, with optional threaded replies."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(
        DreamPost, on_delete=models.CASCADE, related_name='comments',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='dream_post_comments',
    )
    content = EncryptedTextField(
        help_text='Comment content (encrypted at rest).',
    )
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE,
        related_name='replies',
        help_text='Parent comment for threaded replies.',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dream_post_comments'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post', '-created_at'], name='idx_dreamcomment_post_date'),
        ]

    def __str__(self):
        preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{self.user.display_name or self.user.email}: {preview}"


class DreamEncouragement(models.Model):
    """
    Encouragement on a dream post — distinct from likes (more intentional).
    """

    ENCOURAGEMENT_TYPES = [
        ('you_got_this', 'You Got This!'),
        ('keep_going', 'Keep Going!'),
        ('inspired', 'You Inspire Me!'),
        ('proud', 'So Proud!'),
        ('fire', 'On Fire!'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(
        DreamPost, on_delete=models.CASCADE, related_name='encouragements',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='given_encouragements',
    )
    encouragement_type = models.CharField(
        max_length=20, choices=ENCOURAGEMENT_TYPES,
    )
    message = EncryptedTextField(
        blank=True, help_text='Optional personal message (encrypted at rest).',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dream_encouragements'
        constraints = [
            models.UniqueConstraint(fields=['post', 'user'], name='unique_dreampost_encouragement'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.display_name or self.user.email} encouraged: {self.encouragement_type}"
