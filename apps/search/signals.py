"""
Post-save / post-delete signal handlers for updating Elasticsearch indexes.

django-elasticsearch-dsl automatically registers signals for models declared
in documents.py via the @registry.register_document decorator. This module
exists as a hook point (imported by apps.py ready()) in case we need custom
signal logic in the future.

The default behaviour from django-elasticsearch-dsl handles:
- post_save  -> update document in ES
- post_delete -> delete document from ES

No additional code is needed here unless we want to override the default
behaviour (e.g. async Celery tasks for index updates).
"""
