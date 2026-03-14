#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────────────────
# Stepora Backend Entrypoint
# ─────────────────────────────────────────────────────────────────────
# Single entrypoint for all container roles. Set CONTAINER_ROLE env var:
#   web    (default) — migrate + daphne (ASGI)
#   worker           — celery worker (auto-discovers all queues)
#   beat             — celery beat scheduler
#
# For specialized workers, set CELERY_QUEUES to override auto-discovery:
#   CELERY_QUEUES=notifications,dreams
# ─────────────────────────────────────────────────────────────────────

ROLE="${CONTAINER_ROLE:-web}"

case "$ROLE" in
  web)
    echo "[entrypoint] Role: web — running migrations then starting daphne (ASGI)"
    python manage.py migrate --noinput
    python manage.py ensure_stripe_webhook || echo "[entrypoint] WARNING: Stripe webhook setup skipped"

    exec daphne \
        --bind 0.0.0.0 \
        --port 8000 \
        --verbosity 1 \
        --access-log - \
        config.asgi:application
    ;;

  worker)
    # Auto-discover all queues from task_routes, or use CELERY_QUEUES override
    if [ -n "$CELERY_QUEUES" ]; then
      QUEUES="$CELERY_QUEUES"
      echo "[entrypoint] Role: worker — using CELERY_QUEUES override: $QUEUES"
    else
      QUEUES=$(python -c "
from config.celery import app
routes = app.conf.get('task_routes') or {}
queues = set()
for route in routes.values():
    q = route.get('queue')
    if q:
        queues.add(q)
queues.add('celery')  # always include default queue
print(','.join(sorted(queues)))
")
      echo "[entrypoint] Role: worker — auto-discovered queues: $QUEUES"
    fi

    exec celery -A config worker \
        --loglevel="${CELERY_LOG_LEVEL:-info}" \
        --concurrency="${CELERY_CONCURRENCY:-2}" \
        --max-tasks-per-child="${CELERY_MAX_TASKS:-1000}" \
        -Q "$QUEUES"
    ;;

  beat)
    echo "[entrypoint] Role: beat — starting celery beat scheduler"
    exec celery -A config beat \
        --loglevel="${CELERY_LOG_LEVEL:-info}" \
        --scheduler django_celery_beat.schedulers:DatabaseScheduler \
        --pidfile=/tmp/celerybeat.pid
    ;;

  *)
    echo "[entrypoint] ERROR: Unknown CONTAINER_ROLE '$ROLE'. Use: web, worker, beat"
    exit 1
    ;;
esac
