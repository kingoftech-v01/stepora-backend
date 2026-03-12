#!/bin/bash
# Role-aware health check for Docker/ECS
# - web: check gunicorn HTTP
# - worker: check celery worker process is alive
# - beat: check celery beat process is alive

ROLE="${CONTAINER_ROLE:-web}"

case "$ROLE" in
  web)
    curl -f http://localhost:8000/health/liveness/ || exit 1
    ;;
  worker)
    # Check celery worker main process is running
    pgrep -f "celery.*worker" > /dev/null || exit 1
    ;;
  beat)
    # Check celery beat process is running
    pgrep -f "celery.*beat" > /dev/null || exit 1
    ;;
  *)
    exit 0
    ;;
esac
