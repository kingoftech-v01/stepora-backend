"""
App configuration for the SEO module.

Provides:
- Dynamic sitemap generation for public content
- Social sharing preview metadata (Open Graph)
- JSON-LD structured data for search engines
- SEO-related API endpoints
"""

from django.apps import AppConfig


class SeoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.seo"
    verbose_name = "SEO"
