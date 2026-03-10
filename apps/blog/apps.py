"""
Application configuration for the Blog app.

Provides blog content management: categories, tags, and posts
for the Stepora platform.
"""

from django.apps import AppConfig


class BlogConfig(AppConfig):
    """Configuration for the Blog application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.blog'
    verbose_name = 'Blog'
