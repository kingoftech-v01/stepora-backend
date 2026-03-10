"""
Models for the Blog system.

Implements categories, tags, and posts for the Stepora blog.
Posts support drafts, scheduling, featured flags, and view tracking.
"""

import uuid

from django.db import models
from django.utils import timezone

from apps.users.models import User


class PublishedPostManager(models.Manager):
    """Manager that returns only published posts with a published_at in the past."""

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(status='published', published_at__lte=timezone.now())
        )


class Category(models.Model):
    """
    Blog post category.

    Categories organize posts into broad topics (e.g., Productivity,
    Mindset, Goal Setting). Each category has an optional icon for
    display in the frontend.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Category display name.',
    )
    slug = models.SlugField(
        max_length=120,
        unique=True,
        help_text='URL-friendly identifier.',
    )
    description = models.TextField(
        blank=True,
        default='',
        help_text='Short description of the category.',
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text='Emoji or icon name for the category (e.g., a Lucide icon name).',
    )
    order = models.IntegerField(
        default=0,
        help_text='Display order (ascending).',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'blog_categories'
        ordering = ['order', 'name']
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class Tag(models.Model):
    """
    Blog post tag.

    Tags provide fine-grained labeling for posts (e.g., #morning-routine,
    #accountability). Posts can have multiple tags.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        max_length=80,
        unique=True,
        help_text='Tag display name.',
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text='URL-friendly identifier.',
    )

    class Meta:
        db_table = 'blog_tags'
        ordering = ['name']
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'

    def __str__(self):
        return self.name


class Post(models.Model):
    """
    Blog post.

    Posts are the core content unit. They support draft/published status,
    featured flags, cover images (Unsplash URLs), read time estimation,
    and view counting. Published posts are filtered by the PublishedPostManager.
    """

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    title = models.CharField(
        max_length=255,
        help_text='Post title.',
    )
    slug = models.SlugField(
        max_length=280,
        unique=True,
        help_text='URL-friendly identifier (must be unique).',
    )
    excerpt = models.TextField(
        blank=True,
        default='',
        help_text='Short summary displayed in list views.',
    )
    content = models.TextField(
        help_text='Full post content (Markdown or HTML).',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts',
        help_text='Primary category for this post.',
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name='posts',
        help_text='Tags associated with this post.',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='blog_posts',
        help_text='The user who authored this post.',
    )
    cover_image = models.URLField(
        blank=True,
        default='',
        help_text='Cover image URL (e.g., Unsplash).',
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True,
        help_text='Publication status.',
    )
    featured = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Whether this post is featured/highlighted.',
    )
    read_time_minutes = models.PositiveIntegerField(
        default=5,
        help_text='Estimated read time in minutes.',
    )
    views_count = models.PositiveIntegerField(
        default=0,
        help_text='Number of times this post has been viewed.',
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text='When the post was (or will be) published.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Default manager (all posts)
    objects = models.Manager()
    # Published-only manager
    published = PublishedPostManager()

    class Meta:
        db_table = 'blog_posts'
        ordering = ['-published_at']
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'
        indexes = [
            models.Index(fields=['status', '-published_at'], name='idx_blogpost_status_pub'),
            models.Index(fields=['category', '-published_at'], name='idx_blogpost_cat_pub'),
            models.Index(fields=['featured', '-published_at'], name='idx_blogpost_featured_pub'),
            models.Index(fields=['-created_at'], name='idx_blogpost_created'),
            models.Index(fields=['author', '-published_at'], name='idx_blogpost_author_pub'),
        ]

    def __str__(self):
        return self.title
