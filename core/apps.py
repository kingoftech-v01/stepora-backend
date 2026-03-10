"""
Core app configuration.

Auto-syncs the Django Site record (domain + name) from FRONTEND_URL
on startup so emails always use the correct domain without manual
database edits. Just set FRONTEND_URL in .env and restart.
"""

import logging
import warnings

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Sync Site domain on every startup (gunicorn, runserver, etc.)
        # Suppress the "Accessing the database during app initialization" warning
        # since this is intentional and safe.
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='Accessing the database during app initialization')
            _sync_site_from_frontend_url()


def _sync_site_from_frontend_url():
    """
    Update Django Site (SITE_ID=1) domain and name from FRONTEND_URL.
    Runs at startup so the correct domain is always in the database.
    """
    from urllib.parse import urlparse

    try:
        from django.contrib.sites.models import Site
        from django.conf import settings
    except Exception as e:
        logger.debug("Could not import Site model: %s", e)
        return

    frontend_url = getattr(settings, 'FRONTEND_URL', '')
    if not frontend_url or frontend_url.startswith('http://localhost'):
        return  # Don't override in local dev

    try:
        parsed = urlparse(frontend_url)
        domain = parsed.hostname or ''
        if not domain:
            return

        site = Site.objects.get(pk=getattr(settings, 'SITE_ID', 1))
        if site.domain != domain:
            site.domain = domain
            site.name = 'Stepora'
            site.save(update_fields=['domain', 'name'])
            logger.info("Auto-synced Site domain to %s from FRONTEND_URL", domain)
    except Exception as e:
        # Don't crash startup if DB not ready (migrations, etc.)
        logger.debug("Could not sync Site domain: %s", e)
