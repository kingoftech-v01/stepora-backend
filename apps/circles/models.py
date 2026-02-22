"""
Models for the Circles system.

Implements Dream Circles: small, focused groups where users share goals,
post progress updates, and participate in challenges. Each circle has a
maximum of 20 members and can be public or private.
"""

import uuid

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone as django_timezone

from apps.users.models import User


class Circle(models.Model):
    """
    Represents a Dream Circle - a small group of users with shared goals.

    Circles can be public (anyone can join) or private (invite only).
    Each circle has a maximum membership cap (default 20) and is organized
    by category for discovery purposes.
    """

    CATEGORY_CHOICES = [
        ('career', 'Career'),
        ('health', 'Health'),
        ('fitness', 'Fitness'),
        ('education', 'Education'),
        ('finance', 'Finance'),
        ('creativity', 'Creativity'),
        ('relationships', 'Relationships'),
        ('personal_growth', 'Personal Growth'),
        ('hobbies', 'Hobbies'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this circle.'
    )
    name = models.CharField(
        max_length=200,
        help_text='Display name of the circle.'
    )
    description = models.TextField(
        blank=True,
        help_text='Description of the circle and its goals.'
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default='other',
        db_index=True,
        help_text='Category of the circle for discovery.'
    )
    is_public = models.BooleanField(
        default=True,
        db_index=True,
        help_text='Whether the circle is publicly visible and joinable.'
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_circles',
        help_text='The user who created this circle.'
    )
    max_members = models.IntegerField(
        default=20,
        validators=[MinValueValidator(2), MaxValueValidator(100)],
        help_text='Maximum number of members allowed in this circle.'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'circles'
        ordering = ['-created_at']
        verbose_name = 'Circle'
        verbose_name_plural = 'Circles'
        indexes = [
            models.Index(fields=['category'], name='idx_circle_category'),
            models.Index(fields=['is_public'], name='idx_circle_public'),
            models.Index(fields=['creator'], name='idx_circle_creator'),
            models.Index(fields=['-created_at'], name='idx_circle_created'),
        ]

    def __str__(self):
        visibility = "Public" if self.is_public else "Private"
        return f"{self.name} ({visibility}, {self.category})"

    @property
    def member_count(self):
        """Return the current number of members in this circle."""
        return self.memberships.count()

    @property
    def is_full(self):
        """Check if the circle has reached its member capacity."""
        return self.member_count >= self.max_members


class CircleMembership(models.Model):
    """
    Tracks a user's membership in a circle.

    Each membership has a role (member, moderator, admin) that determines
    the user's permissions within the circle. The circle creator is
    automatically assigned the admin role.
    """

    ROLE_CHOICES = [
        ('member', 'Member'),
        ('moderator', 'Moderator'),
        ('admin', 'Admin'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this membership.'
    )
    circle = models.ForeignKey(
        Circle,
        on_delete=models.CASCADE,
        related_name='memberships',
        help_text='The circle this membership belongs to.'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='circle_memberships',
        help_text='The user who is a member of the circle.'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='member',
        help_text='The role of the user within the circle.'
    )

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'circle_memberships'
        ordering = ['-joined_at']
        verbose_name = 'Circle Membership'
        verbose_name_plural = 'Circle Memberships'
        unique_together = [['circle', 'user']]
        indexes = [
            models.Index(fields=['circle', 'user'], name='idx_membership_circle_user'),
            models.Index(fields=['user'], name='idx_membership_user'),
            models.Index(fields=['circle', 'role'], name='idx_membership_role'),
        ]

    def __str__(self):
        return f"{self.user.display_name or self.user.email} in {self.circle.name} ({self.role})"


class CirclePost(models.Model):
    """
    Represents a post/update within a circle's feed.

    Members can share progress updates, motivational messages, or
    general discussion within their circle's feed.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this post.'
    )
    circle = models.ForeignKey(
        Circle,
        on_delete=models.CASCADE,
        related_name='posts',
        help_text='The circle this post belongs to.'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='circle_posts',
        help_text='The user who created this post.'
    )
    content = models.TextField(
        help_text='The text content of the post.'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'circle_posts'
        ordering = ['-created_at']
        verbose_name = 'Circle Post'
        verbose_name_plural = 'Circle Posts'
        indexes = [
            models.Index(fields=['circle', '-created_at'], name='idx_post_circle_date'),
            models.Index(fields=['author'], name='idx_post_author'),
        ]

    def __str__(self):
        preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{self.author.display_name or self.author.email}: {preview}"


class CircleChallenge(models.Model):
    """
    Represents a challenge within a circle.

    Challenges have a defined time period and can be joined by circle
    members. They provide structured goals and accountability.
    """

    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this challenge.'
    )
    circle = models.ForeignKey(
        Circle,
        on_delete=models.CASCADE,
        related_name='challenges',
        help_text='The circle this challenge belongs to.'
    )
    title = models.CharField(
        max_length=200,
        help_text='Title of the challenge.'
    )
    description = models.TextField(
        blank=True,
        help_text='Detailed description of the challenge.'
    )
    start_date = models.DateTimeField(
        help_text='When this challenge starts.'
    )
    end_date = models.DateTimeField(
        help_text='When this challenge ends.'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='upcoming',
        db_index=True,
        help_text='Current status of the challenge.'
    )
    participants = models.ManyToManyField(
        User,
        related_name='circle_challenges',
        blank=True,
        help_text='Users who have joined this challenge.'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'circle_challenges'
        ordering = ['-start_date']
        verbose_name = 'Circle Challenge'
        verbose_name_plural = 'Circle Challenges'
        indexes = [
            models.Index(fields=['circle', 'status'], name='idx_challenge_circle_status'),
            models.Index(fields=['status'], name='idx_challenge_status'),
            models.Index(fields=['start_date', 'end_date'], name='idx_challenge_dates'),
        ]

    def __str__(self):
        return f"{self.title} ({self.circle.name}) - {self.status}"

    @property
    def is_active(self):
        """Check if the challenge is currently active."""
        now = django_timezone.now()
        return self.start_date <= now <= self.end_date and self.status == 'active'

    @property
    def participant_count(self):
        """Return the number of participants in this challenge."""
        return self.participants.count()


class PostReaction(models.Model):
    """
    Represents a reaction to a circle post.

    Users can react with emoji-style reactions (thumbs_up, fire, clap, heart).
    Each user can only have one reaction per post.
    """

    REACTION_CHOICES = [
        ('thumbs_up', 'Thumbs Up'),
        ('fire', 'Fire'),
        ('clap', 'Clap'),
        ('heart', 'Heart'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    post = models.ForeignKey(
        CirclePost,
        on_delete=models.CASCADE,
        related_name='reactions',
        help_text='The post this reaction is on.'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='post_reactions',
        help_text='The user who reacted.'
    )
    reaction_type = models.CharField(
        max_length=20,
        choices=REACTION_CHOICES,
        help_text='Type of reaction.'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'post_reactions'
        ordering = ['-created_at']
        verbose_name = 'Post Reaction'
        verbose_name_plural = 'Post Reactions'
        unique_together = [['post', 'user']]
        indexes = [
            models.Index(fields=['post', 'reaction_type'], name='idx_reaction_post_type'),
        ]

    def __str__(self):
        return f"{self.user.display_name or self.user.email} reacted {self.reaction_type} on post"


class CircleInvitation(models.Model):
    """
    Invitation to join a private circle.

    Supports two modes:
    - Direct invite: inviter specifies an invitee user
    - Link invite: generates a shareable invite_code (no specific invitee)
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    circle = models.ForeignKey(
        Circle,
        on_delete=models.CASCADE,
        related_name='invitations',
    )
    inviter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='circle_invites_sent',
    )
    invitee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='circle_invites_received',
        null=True,
        blank=True,
        help_text='The user invited (null for link invitations).',
    )
    invite_code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text='Shareable code for link-based invitations.',
    )
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
    )
    expires_at = models.DateTimeField(
        help_text='When this invitation expires.',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'circle_invitations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invite_code']),
            models.Index(fields=['circle', 'invitee', 'status']),
        ]

    def __str__(self):
        target = self.invitee.email if self.invitee else f'code:{self.invite_code}'
        return f"Invite to {self.circle.name} for {target}"

    @property
    def is_expired(self):
        return django_timezone.now() > self.expires_at


class ChallengeProgress(models.Model):
    """
    Tracks a user's progress within a circle challenge.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    challenge = models.ForeignKey(
        CircleChallenge,
        on_delete=models.CASCADE,
        related_name='progress_entries',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='challenge_progress',
    )
    progress_value = models.FloatField(
        default=0,
        help_text='Numeric progress value (interpretation depends on challenge).',
    )
    notes = models.TextField(
        blank=True,
        help_text='Optional notes about this progress update.',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'challenge_progress'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['challenge', 'user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.display_name or self.user.email}: {self.progress_value} on {self.challenge.title}"
