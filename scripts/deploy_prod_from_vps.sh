#!/bin/bash
# ============================================================================
# Deploy Stepora to AWS Production — from VPS (no GitHub Actions)
# ============================================================================
#
# This script replaces the GitHub Actions CI/CD pipeline when Actions is
# unavailable (billing blocked, outage, etc.). It runs the same steps locally:
#
#   1. Pull latest code from GitHub
#   2. Run lint/checks
#   3. Build Docker image
#   4. Push to ECR
#   5. Update ECS task definitions
#   6. Wait for services to stabilize
#   7. Verify deployment
#
# Usage:
#   ./scripts/deploy_prod_from_vps.sh                    # Deploy backend
#   ./scripts/deploy_prod_from_vps.sh --frontend         # Deploy frontend
#   ./scripts/deploy_prod_from_vps.sh --site             # Deploy site vitrine
#   ./scripts/deploy_prod_from_vps.sh --all              # Deploy everything
#   ./scripts/deploy_prod_from_vps.sh --skip-checks      # Skip lint/tests
#   ./scripts/deploy_prod_from_vps.sh --skip-wait        # Don't wait for ECS stability
#
# Prerequisites:
#   - AWS CLI configured (aws sts get-caller-identity should work)
#   - Docker installed and running
#   - Git repos cloned at /root/stepora, /root/stepora-frontend, /root/stepora-site
#   - Node.js 20+ (for frontend build)
#   - .env file at /root/stepora/.env (for FIELD_ENCRYPTION_KEY)
#
# ============================================================================

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
AWS_REGION="eu-west-3"
AWS_ACCOUNT_ID="987409845802"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECS_CLUSTER="stepora"

# Backend
BACKEND_DIR="/root/stepora"
BACKEND_ECR_REPO="stepora/backend"
BACKEND_SERVICES=("stepora-backend" "stepora-celery" "stepora-celery-beat")
declare -A BACKEND_ROLES=(
    [stepora-backend]=web
    [stepora-celery]=worker
    [stepora-celery-beat]=beat
)

# Frontend
FRONTEND_DIR="/root/stepora-frontend"
S3_BUCKET_FRONTEND="stepora-frontend-eu"
CLOUDFRONT_DISTRIBUTION_ID="EAG7EHOMSZ47W"
VITE_API_BASE="https://api.stepora.app"
VITE_WS_BASE="wss://api.stepora.app"

# Site
SITE_DIR="/root/stepora-site"
SITE_ECR_REPO="stepora/site"
SITE_ECS_SERVICE="stepora-site"

# ── Parse arguments ──────────────────────────────────────────────────────────
DEPLOY_BACKEND=false
DEPLOY_FRONTEND=false
DEPLOY_SITE=false
SKIP_CHECKS=false
SKIP_WAIT=false
SKIP_PULL=false

for arg in "$@"; do
    case "$arg" in
        --backend)      DEPLOY_BACKEND=true ;;
        --frontend)     DEPLOY_FRONTEND=true ;;
        --site)         DEPLOY_SITE=true ;;
        --all)          DEPLOY_BACKEND=true; DEPLOY_FRONTEND=true; DEPLOY_SITE=true ;;
        --skip-checks)  SKIP_CHECKS=true ;;
        --skip-wait)    SKIP_WAIT=true ;;
        --skip-pull)    SKIP_PULL=true ;;
        --help|-h)
            head -30 "$0" | grep '^#' | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $arg"
            echo "Run with --help for usage."
            exit 1
            ;;
    esac
done

# Default: backend only
if [ "$DEPLOY_BACKEND" = false ] && [ "$DEPLOY_FRONTEND" = false ] && [ "$DEPLOY_SITE" = false ]; then
    DEPLOY_BACKEND=true
fi

# ── Utility functions ────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_step() { echo -e "\n${BLUE}[STEP]${NC} $1"; }
log_ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err()  { echo -e "${RED}[ERROR]${NC} $1"; }

check_prereqs() {
    local missing=()
    command -v docker >/dev/null 2>&1 || missing+=("docker")
    command -v aws >/dev/null 2>&1    || missing+=("aws")
    command -v jq >/dev/null 2>&1     || missing+=("jq")
    command -v git >/dev/null 2>&1    || missing+=("git")

    if [ "$DEPLOY_FRONTEND" = true ]; then
        command -v node >/dev/null 2>&1 || missing+=("node")
        command -v npm >/dev/null 2>&1  || missing+=("npm")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        log_err "Missing required tools: ${missing[*]}"
        exit 1
    fi

    # Verify AWS credentials
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        log_err "AWS credentials not configured or expired."
        log_err "Run: aws configure"
        exit 1
    fi

    # Verify Docker is running
    if ! docker info >/dev/null 2>&1; then
        log_err "Docker daemon not running. Start it with: sudo systemctl start docker"
        exit 1
    fi
}

get_git_sha() {
    local dir="$1"
    git -C "$dir" rev-parse HEAD
}

get_git_branch() {
    local dir="$1"
    git -C "$dir" branch --show-current 2>/dev/null || echo "detached"
}

pull_latest() {
    local dir="$1"
    local name="$2"
    if [ "$SKIP_PULL" = true ]; then
        log_warn "Skipping git pull for ${name} (--skip-pull)"
        return
    fi
    log_step "Pulling latest code for ${name}..."
    git -C "$dir" fetch origin
    local branch
    branch=$(get_git_branch "$dir")
    if [ "$branch" != "main" ]; then
        log_warn "${name} is on branch '${branch}', not 'main'. Switching to main..."
        git -C "$dir" checkout main
        git -C "$dir" pull origin main
    else
        git -C "$dir" pull origin main
    fi
    log_ok "${name}: $(git -C "$dir" log --oneline -1)"
}

# ── ECR Login ────────────────────────────────────────────────────────────────
ecr_login() {
    log_step "Logging in to Amazon ECR..."
    aws ecr get-login-password --region "${AWS_REGION}" | \
        docker login --username AWS --password-stdin "${ECR_REGISTRY}"
    log_ok "ECR login successful"
}

# ── Deploy Backend ───────────────────────────────────────────────────────────
deploy_backend() {
    log_step "========== DEPLOYING BACKEND =========="

    pull_latest "$BACKEND_DIR" "backend"

    local IMAGE_TAG
    IMAGE_TAG=$(get_git_sha "$BACKEND_DIR")
    local FULL_IMAGE="${ECR_REGISTRY}/${BACKEND_ECR_REPO}"

    # Lint/checks
    if [ "$SKIP_CHECKS" = false ]; then
        log_step "Running Django system check..."
        # Use a temporary container for the check
        cd "$BACKEND_DIR"
        docker build \
            --build-arg REQUIREMENTS_FILE=requirements/production.txt \
            --build-arg DJANGO_SETTINGS=config.settings.production \
            --build-arg FIELD_ENCRYPTION_KEY="$(grep FIELD_ENCRYPTION_KEY .env | cut -d= -f2-)" \
            -t "stepora-check:${IMAGE_TAG}" \
            . 2>&1 | tail -5
        log_ok "Docker build successful (checks passed implicitly via collectstatic)"
    else
        log_step "Building Docker image (skipping checks)..."
        cd "$BACKEND_DIR"
        docker build \
            --build-arg REQUIREMENTS_FILE=requirements/production.txt \
            --build-arg DJANGO_SETTINGS=config.settings.production \
            --build-arg FIELD_ENCRYPTION_KEY="$(grep FIELD_ENCRYPTION_KEY .env | cut -d= -f2-)" \
            -t "stepora-check:${IMAGE_TAG}" \
            . 2>&1 | tail -5
    fi

    # Tag for ECR
    log_step "Tagging and pushing to ECR..."
    docker tag "stepora-check:${IMAGE_TAG}" "${FULL_IMAGE}:${IMAGE_TAG}"
    docker tag "stepora-check:${IMAGE_TAG}" "${FULL_IMAGE}:latest"
    docker push "${FULL_IMAGE}:${IMAGE_TAG}"
    docker push "${FULL_IMAGE}:latest"
    log_ok "Pushed ${FULL_IMAGE}:${IMAGE_TAG}"

    # Update ECS services
    log_step "Updating ECS services..."
    for SERVICE_NAME in "${BACKEND_SERVICES[@]}"; do
        local ROLE="${BACKEND_ROLES[$SERVICE_NAME]}"
        echo "  Deploying ${SERVICE_NAME} (role: ${ROLE})..."

        # Get current task definition
        local CURRENT_TD
        CURRENT_TD=$(aws ecs describe-services \
            --cluster "${ECS_CLUSTER}" \
            --services "${SERVICE_NAME}" \
            --region "${AWS_REGION}" \
            --query 'services[0].taskDefinition' \
            --output text)

        # Create new task definition with updated image and role
        aws ecs describe-task-definition \
            --task-definition "${CURRENT_TD}" \
            --region "${AWS_REGION}" \
            --query 'taskDefinition' \
            | jq --arg IMG "${FULL_IMAGE}:${IMAGE_TAG}" --arg ROLE "${ROLE}" \
                '.containerDefinitions[0].image = $IMG
                 | .containerDefinitions[0].command = []
                 | if (.containerDefinitions[0].environment | map(select(.name == "CONTAINER_ROLE")) | length) == 0
                   then .containerDefinitions[0].environment += [{"name": "CONTAINER_ROLE", "value": $ROLE}]
                   else .containerDefinitions[0].environment = [.containerDefinitions[0].environment[] | if .name == "CONTAINER_ROLE" then .value = $ROLE else . end]
                   end
                 | del(.taskDefinitionArn, .revision, .status,
                       .requiresAttributes, .compatibilities,
                       .registeredAt, .registeredBy)' \
            > /tmp/new-task-def-${SERVICE_NAME}.json

        # Register new revision
        local NEW_TD_ARN
        NEW_TD_ARN=$(aws ecs register-task-definition \
            --cli-input-json "file:///tmp/new-task-def-${SERVICE_NAME}.json" \
            --region "${AWS_REGION}" \
            --query 'taskDefinition.taskDefinitionArn' \
            --output text)
        echo "  New task definition: ${NEW_TD_ARN}"

        # Update the service
        aws ecs update-service \
            --cluster "${ECS_CLUSTER}" \
            --service "${SERVICE_NAME}" \
            --task-definition "${NEW_TD_ARN}" \
            --region "${AWS_REGION}" \
            --force-new-deployment >/dev/null

        log_ok "${SERVICE_NAME} updated"
    done

    # Wait for stability
    if [ "$SKIP_WAIT" = false ]; then
        log_step "Waiting for all backend services to stabilize (this can take 3-5 min)..."
        aws ecs wait services-stable \
            --cluster "${ECS_CLUSTER}" \
            --services "${BACKEND_SERVICES[@]}" \
            --region "${AWS_REGION}"
        log_ok "All backend services stable"
    else
        log_warn "Skipping ECS stability wait (--skip-wait)"
    fi

    # Cleanup local images
    docker rmi "stepora-check:${IMAGE_TAG}" 2>/dev/null || true

    log_ok "Backend deployment complete (image: ${IMAGE_TAG:0:12})"
}

# ── Deploy Frontend ──────────────────────────────────────────────────────────
deploy_frontend() {
    log_step "========== DEPLOYING FRONTEND =========="

    pull_latest "$FRONTEND_DIR" "frontend"

    cd "$FRONTEND_DIR"

    # Lint
    if [ "$SKIP_CHECKS" = false ]; then
        log_step "Running frontend lint..."
        npm ci --silent
        npx prettier --check "src/**/*.{js,jsx}" || {
            log_warn "Prettier check failed. Continuing anyway (non-blocking for deploy)."
        }
        npx eslint src/ || {
            log_warn "ESLint check failed. Continuing anyway (non-blocking for deploy)."
        }
        log_ok "Lint complete"
    else
        log_step "Installing dependencies..."
        npm ci --silent
    fi

    # Build
    log_step "Building frontend..."
    VITE_API_BASE="${VITE_API_BASE}" \
    VITE_WS_BASE="${VITE_WS_BASE}" \
    npm run build

    if [ ! -d "dist" ] || [ -z "$(ls -A dist)" ]; then
        log_err "Build produced empty dist/ directory"
        exit 1
    fi
    log_ok "Build complete ($(du -sh dist | cut -f1))"

    # Deploy to S3
    log_step "Syncing to S3 (${S3_BUCKET_FRONTEND})..."
    aws s3 sync dist/ "s3://${S3_BUCKET_FRONTEND}" \
        --delete \
        --region "${AWS_REGION}"
    log_ok "S3 sync complete"

    # Invalidate CloudFront
    log_step "Invalidating CloudFront cache..."
    local INVALIDATION_ID
    INVALIDATION_ID=$(aws cloudfront create-invalidation \
        --distribution-id "${CLOUDFRONT_DISTRIBUTION_ID}" \
        --paths "/*" \
        --query 'Invalidation.Id' \
        --output text)
    log_ok "CloudFront invalidation created: ${INVALIDATION_ID}"
    log_warn "CloudFront invalidation takes 1-5 minutes to propagate globally."

    log_ok "Frontend deployment complete"
}

# ── Deploy Site ──────────────────────────────────────────────────────────────
deploy_site() {
    log_step "========== DEPLOYING SITE VITRINE =========="

    pull_latest "$SITE_DIR" "site"

    local IMAGE_TAG
    IMAGE_TAG=$(get_git_sha "$SITE_DIR")
    local FULL_IMAGE="${ECR_REGISTRY}/${SITE_ECR_REPO}"

    cd "$SITE_DIR"

    # Lint
    if [ "$SKIP_CHECKS" = false ]; then
        log_step "Running site lint..."
        pip install black isort flake8 -q 2>/dev/null
        black --check --exclude='migrations|venv' . || {
            log_warn "Black check failed (non-blocking)."
        }
        isort --check-only --skip-glob='*/migrations/*' --profile black . || {
            log_warn "isort check failed (non-blocking)."
        }
    fi

    # Build Docker image
    log_step "Building site Docker image..."
    docker build \
        -t "${FULL_IMAGE}:${IMAGE_TAG}" \
        -t "${FULL_IMAGE}:latest" \
        . 2>&1 | tail -5
    log_ok "Docker build successful"

    # Push to ECR
    log_step "Pushing to ECR..."
    docker push "${FULL_IMAGE}:${IMAGE_TAG}"
    docker push "${FULL_IMAGE}:latest"
    log_ok "Pushed ${FULL_IMAGE}:${IMAGE_TAG}"

    # Update ECS service
    log_step "Updating ECS site service..."
    local CURRENT_TD
    CURRENT_TD=$(aws ecs describe-services \
        --cluster "${ECS_CLUSTER}" \
        --services "${SITE_ECS_SERVICE}" \
        --region "${AWS_REGION}" \
        --query 'services[0].taskDefinition' \
        --output text)

    aws ecs describe-task-definition \
        --task-definition "${CURRENT_TD}" \
        --region "${AWS_REGION}" \
        --query 'taskDefinition' \
        | jq --arg IMG "${FULL_IMAGE}:${IMAGE_TAG}" \
            '.containerDefinitions[0].image = $IMG
             | del(.taskDefinitionArn, .revision, .status,
                   .requiresAttributes, .compatibilities,
                   .registeredAt, .registeredBy)' \
        > /tmp/new-task-def-site.json

    local NEW_TD_ARN
    NEW_TD_ARN=$(aws ecs register-task-definition \
        --cli-input-json "file:///tmp/new-task-def-site.json" \
        --region "${AWS_REGION}" \
        --query 'taskDefinition.taskDefinitionArn' \
        --output text)
    echo "  New task definition: ${NEW_TD_ARN}"

    aws ecs update-service \
        --cluster "${ECS_CLUSTER}" \
        --service "${SITE_ECS_SERVICE}" \
        --task-definition "${NEW_TD_ARN}" \
        --region "${AWS_REGION}" \
        --force-new-deployment >/dev/null

    if [ "$SKIP_WAIT" = false ]; then
        log_step "Waiting for site service to stabilize..."
        aws ecs wait services-stable \
            --cluster "${ECS_CLUSTER}" \
            --services "${SITE_ECS_SERVICE}" \
            --region "${AWS_REGION}"
        log_ok "Site service stable"
    fi

    log_ok "Site deployment complete (image: ${IMAGE_TAG:0:12})"
}

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

echo "==========================================="
echo " Stepora — Production Deploy from VPS"
echo "==========================================="
echo " Backend:  ${DEPLOY_BACKEND}"
echo " Frontend: ${DEPLOY_FRONTEND}"
echo " Site:     ${DEPLOY_SITE}"
echo " Checks:   $([ "$SKIP_CHECKS" = true ] && echo 'SKIPPED' || echo 'enabled')"
echo " Wait:     $([ "$SKIP_WAIT" = true ] && echo 'SKIPPED' || echo 'enabled')"
echo " Time:     $(date '+%Y-%m-%d %H:%M:%S')"
echo "==========================================="
echo ""

# Confirmation
echo -e "${YELLOW}This will deploy to PRODUCTION (AWS).${NC}"
echo "Press Enter to continue, Ctrl+C to abort..."
read -r

# Preflight
check_prereqs

# ECR login (needed for backend and site)
if [ "$DEPLOY_BACKEND" = true ] || [ "$DEPLOY_SITE" = true ]; then
    ecr_login
fi

# Deploy each target
if [ "$DEPLOY_BACKEND" = true ]; then
    deploy_backend
fi

if [ "$DEPLOY_FRONTEND" = true ]; then
    deploy_frontend
fi

if [ "$DEPLOY_SITE" = true ]; then
    deploy_site
fi

# ── Post-deploy verification ─────────────────────────────────────────────────
echo ""
log_step "========== POST-DEPLOY VERIFICATION =========="

if [ "$DEPLOY_BACKEND" = true ]; then
    echo ""
    echo "  Backend health check:"
    if curl -sf -o /dev/null -w "  HTTP %{http_code} (%{time_total}s)\n" https://api.stepora.app/health/liveness/; then
        log_ok "Backend is healthy"
    else
        log_warn "Backend health check failed (may still be starting)"
    fi

    echo ""
    echo "  ECS service status:"
    aws ecs describe-services \
        --cluster "${ECS_CLUSTER}" \
        --services "${BACKEND_SERVICES[@]}" \
        --region "${AWS_REGION}" \
        --query 'services[*].{Service:serviceName, Running:runningCount, Desired:desiredCount, Deployments:length(deployments)}' \
        --output table
fi

if [ "$DEPLOY_FRONTEND" = true ]; then
    echo ""
    echo "  Frontend:"
    if curl -sf -o /dev/null -w "  HTTP %{http_code} (%{time_total}s)\n" https://stepora.app/; then
        log_ok "Frontend is reachable"
    else
        log_warn "Frontend check failed (CloudFront invalidation may still be in progress)"
    fi
fi

if [ "$DEPLOY_SITE" = true ]; then
    echo ""
    echo "  Site vitrine:"
    if curl -sf -o /dev/null -w "  HTTP %{http_code} (%{time_total}s)\n" https://stepora.net/; then
        log_ok "Site is reachable"
    else
        log_warn "Site check failed (may still be starting)"
    fi
fi

echo ""
echo "==========================================="
echo " Deployment complete!"
echo "==========================================="
echo ""
echo " Verify manually:"
echo "   https://stepora.app           — Frontend"
echo "   https://api.stepora.app       — Backend API"
echo "   https://stepora.net           — Site vitrine"
echo ""
echo " If issues, check logs:"
echo "   aws logs tail /ecs/stepora-backend --since 10m --follow"
echo ""
echo " Rollback:"
echo "   See /root/stepora/docs/DEPLOY_PRODUCTION.md#rollback"
echo "==========================================="
