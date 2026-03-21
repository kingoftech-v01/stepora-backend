#!/bin/bash
# ============================================================================
# Deploy Stepora Backend to Preprod VPS
# ============================================================================
# Usage: ./scripts/deploy_preprod.sh [--skip-build] [--keep-db]
#
# Options:
#   --skip-build  Skip Docker image rebuild (use existing images)
#   --keep-db     Skip database reset (just restart services)
#
# Prerequisites:
#   - .env file at /root/stepora/.env with all required variables
#   - Docker and docker compose installed
#   - Nginx configured for dpapi.jhpetitfrere.com (port 8085)
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Parse arguments
SKIP_BUILD=false
KEEP_DB=false
for arg in "$@"; do
    case "$arg" in
        --skip-build) SKIP_BUILD=true ;;
        --keep-db)    KEEP_DB=true ;;
        *)            echo "Unknown option: $arg"; exit 1 ;;
    esac
done

echo "==========================================="
echo " Stepora Backend — Preprod Deployment"
echo "==========================================="
echo " Branch: $(git branch --show-current 2>/dev/null || echo 'unknown')"
echo " Commit: $(git log --oneline -1 2>/dev/null || echo 'unknown')"
echo " Time:   $(date '+%Y-%m-%d %H:%M:%S')"
echo "==========================================="
echo ""

# Preflight: check .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found at $PROJECT_DIR/.env"
    echo "Copy .env.example and fill in the values."
    exit 1
fi

# ── Step 1: Build Docker images ──────────────────────────────────────────
if [ "$SKIP_BUILD" = false ]; then
    echo "[1/7] Building backend Docker images..."
    docker compose build --no-cache
else
    echo "[1/7] Skipping build (--skip-build)"
fi

# ── Step 2: Stop current containers ──────────────────────────────────────
echo "[2/7] Stopping current containers..."
docker compose down --remove-orphans

# ── Step 3: Clean up stale volumes/state ─────────────────────────────────
echo "[3/7] Cleaning up stale state..."
# Remove celery beat PID file (causes restart loops)
docker compose run --rm --no-deps celery-beat sh -c "rm -f /tmp/celerybeat.pid" 2>/dev/null || true

# ── Step 4: Database reset or keep ───────────────────────────────────────
if [ "$KEEP_DB" = false ]; then
    echo "[4/7] Resetting database (clean install)..."
    # Start only DB and Redis (needed for migrations)
    docker compose up -d db redis
    echo "  Waiting for PostgreSQL to be ready..."
    for i in $(seq 1 30); do
        if docker compose exec db pg_isready -U stepora -q 2>/dev/null; then
            echo "  PostgreSQL ready."
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "  ERROR: PostgreSQL not ready after 30s"
            exit 1
        fi
        sleep 1
    done

    # Drop and recreate database
    echo "  Dropping and recreating database..."
    docker compose exec db psql -U stepora -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" stepora
    docker compose exec db psql -U stepora -c "GRANT ALL ON SCHEMA public TO stepora;" stepora

    # Start elasticsearch (needed for ensure_search_index in web startup)
    echo "  Starting Elasticsearch..."
    docker compose up -d elasticsearch
    echo "  Waiting for Elasticsearch to be ready (can take 30-60s)..."
    for i in $(seq 1 60); do
        if docker compose exec elasticsearch curl -fsSL -u "elastic:${ELASTIC_PASSWORD:-changeme}" http://localhost:9200/_cluster/health?wait_for_status=yellow\&timeout=2s 2>/dev/null | grep -q '"status"'; then
            echo "  Elasticsearch ready."
            break
        fi
        if [ "$i" -eq 60 ]; then
            echo "  WARNING: Elasticsearch not ready after 60s, continuing anyway..."
            break
        fi
        sleep 1
    done

    # Run migrations
    echo "  Running migrations..."
    docker compose run --rm web python manage.py migrate --noinput

    # Seed data
    echo "  Seeding data..."
    docker compose run --rm web python manage.py create_admin \
        --email=victorstephanearthur@gmail.com \
        --name=kingoftechv_01

    docker compose run --rm web python manage.py seed_dream_templates 2>/dev/null \
        && echo "  Dream templates seeded." \
        || echo "  WARNING: seed_dream_templates failed (non-blocking)"

    docker compose run --rm web python manage.py seed_leagues 2>/dev/null \
        && echo "  Leagues seeded." \
        || echo "  WARNING: seed_leagues failed (non-blocking)"

    # SeasonConfig initialization
    docker compose run --rm web python manage.py shell -c \
        "from apps.leagues.models import SeasonConfig; SeasonConfig.get(); print('SeasonConfig ready')" 2>/dev/null \
        || echo "  WARNING: SeasonConfig init failed (non-blocking)"

    # Search index
    docker compose run --rm web python manage.py ensure_search_index 2>/dev/null \
        && echo "  Search index ready." \
        || echo "  WARNING: ensure_search_index failed (non-blocking)"
else
    echo "[4/7] Keeping existing database (--keep-db)"
    # Still need to run migrations for any new changes
    docker compose up -d db redis elasticsearch
    echo "  Waiting for DB..."
    sleep 5
    docker compose run --rm web python manage.py migrate --noinput
fi

# ── Step 5: Stop temporary containers from seeding ───────────────────────
echo "[5/7] Cleaning up seed containers..."
docker compose down

# ── Step 6: Start all services ───────────────────────────────────────────
echo "[6/7] Starting all services..."
docker compose up -d

# ── Step 7: Verify deployment ────────────────────────────────────────────
echo "[7/7] Verifying deployment..."
echo "  Waiting for services to start (15s)..."
sleep 15

# Check each service
echo ""
echo "  Service Status:"
echo "  ───────────────"

check_container() {
    local name="$1"
    local status
    status=$(docker inspect --format='{{.State.Status}}' "$name" 2>/dev/null || echo "not found")
    local health
    health=$(docker inspect --format='{{.State.Health.Status}}' "$name" 2>/dev/null || echo "N/A")
    printf "  %-25s status=%-10s health=%s\n" "$name" "$status" "$health"
}

check_container "stepora_db"
check_container "stepora_redis"
check_container "stepora_elasticsearch"
check_container "stepora_web"
check_container "stepora_daphne"
check_container "stepora_celery"
check_container "stepora_celery_beat"
check_container "stepora_nginx"

echo ""

# Health check via nginx (the actual public endpoint)
if curl -sf http://127.0.0.1:8085/health/liveness/ > /dev/null 2>&1; then
    echo "  Health check: PASS (http://127.0.0.1:8085/health/liveness/)"
else
    echo "  Health check: FAIL (http://127.0.0.1:8085/health/liveness/)"
    echo "  Check logs: docker compose logs web --tail 50"
fi

echo ""
echo "==========================================="
echo " Deployment complete!"
echo "==========================================="
echo " API:      https://dpapi.jhpetitfrere.com"
echo " Frontend: https://dp.jhpetitfrere.com"
echo " Admin:    https://dpapi.jhpetitfrere.com/admin/"
echo ""
echo " Useful commands:"
echo "   docker compose logs -f web          # Backend logs"
echo "   docker compose logs -f celery       # Celery worker logs"
echo "   docker compose logs -f nginx        # Nginx access logs"
echo "   docker compose exec web python manage.py createsuperuser"
echo "==========================================="
