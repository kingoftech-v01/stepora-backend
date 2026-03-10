"""
Management command to ensure all Elasticsearch indexes exist.

Creates any missing indexes and populates them. Safe to run on every startup
— it is a no-op for indexes that already exist.

Usage:
    python manage.py ensure_search_index
"""

import logging

from django.core.management.base import BaseCommand
from django_elasticsearch_dsl.registries import registry

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create missing Elasticsearch indexes and populate them (idempotent).'

    def handle(self, *args, **options):
        documents = registry.get_documents()
        created = 0

        for doc_class in documents:
            index_name = doc_class.Index.name
            index = doc_class._index

            if index.exists():
                self.stdout.write(f'  Index already exists: {index_name}')
                continue

            self.stdout.write(f'  Creating index: {index_name}')
            try:
                index.create()
            except Exception as e:
                logger.warning('Failed to create index %s: %s', index_name, e)
                self.stderr.write(self.style.WARNING(f'  Failed to create {index_name}: {e}'))
                continue

            # Populate newly created index
            qs = doc_class.Django.model.objects.all()
            count = qs.count()
            self.stdout.write(f'  Populating {index_name} with {count} documents...')

            batch_size = 500
            for start in range(0, count, batch_size):
                batch = list(qs[start:start + batch_size])
                doc_class().update(batch)

            self.stdout.write(self.style.SUCCESS(f'  Done: {index_name} ({count} documents)'))
            created += 1

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created {created} missing index(es).'))
        else:
            self.stdout.write(self.style.SUCCESS('All indexes already exist.'))
