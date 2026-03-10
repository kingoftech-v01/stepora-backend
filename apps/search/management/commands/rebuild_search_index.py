"""
Management command to rebuild all Elasticsearch indexes.

Usage:
    python manage.py rebuild_search_index
    python manage.py rebuild_search_index --models dreams,users

This iterates all registered ES document classes, deletes the index,
recreates it, and re-indexes every row from PostgreSQL.
"""

from django.core.management.base import BaseCommand
from django_elasticsearch_dsl.registries import registry


class Command(BaseCommand):
    help = "Rebuild all Elasticsearch indexes from PostgreSQL data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--models",
            type=str,
            default="",
            help='Comma-separated list of model names to rebuild (e.g. "dream,user"). Empty = all.',
        )

    def handle(self, *args, **options):
        filter_models = options["models"]
        filter_set = set()
        if filter_models:
            filter_set = {m.strip().lower() for m in filter_models.split(",")}

        documents = registry.get_documents()

        for doc_class in documents:
            model_name = doc_class.Django.model.__name__.lower()

            if filter_set and model_name not in filter_set:
                continue

            index_name = doc_class.Index.name
            self.stdout.write(f"Rebuilding index: {index_name} (model: {model_name})")

            # Delete and recreate the index
            index = doc_class._index
            if index.exists():
                index.delete()
            index.create()

            # Re-index all objects
            qs = doc_class.Django.model.objects.all()
            count = qs.count()
            self.stdout.write(f"  Indexing {count} documents...")

            # Bulk index in batches
            batch_size = 500
            for start in range(0, count, batch_size):
                batch = list(qs[start : start + batch_size])
                doc_class().update(batch)

            self.stdout.write(
                self.style.SUCCESS(f"  Done: {index_name} ({count} documents)")
            )

        self.stdout.write(self.style.SUCCESS("All indexes rebuilt successfully."))
