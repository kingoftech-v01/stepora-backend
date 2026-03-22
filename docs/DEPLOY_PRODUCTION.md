# Production Deployment Checklist

## Overview

Stepora uses a CI/CD pipeline triggered by pushes to `main`. The pipeline:
1. Runs lint and Django system checks
2. Builds Docker image and pushes to ECR (tagged with commit SHA + `latest`)
3. Updates all 3 ECS services: `stepora-backend`, `stepora-celery`, `stepora-celery-beat`
4. Waits for services to stabilize

Migrations run automatically via `entrypoint.sh` on the `web` container startup.

## Prerequisites

- All changes merged to `main` branch
- CI/CD pipeline passes (lint + Django check + build)
- AWS credentials configured in GitHub Secrets

## Automated Flow (CI/CD)

Push to `main` triggers `.github/workflows/deploy-backend.yml`:

```
test → build-and-push (ECR) → deploy (ECS rolling update)
```

The deploy step:
- Fetches current task definition for each service
- Swaps the container image to the new SHA tag
- Sets `CONTAINER_ROLE` env var (`web`, `worker`, `beat`)
- Registers new task definition revision
- Updates the ECS service
- Waits for all 3 services to stabilize

## Manual: One-Time DB Migration (Modular Architecture)

The modular architecture introduced fresh migrations across 17 apps. For the
initial deployment, the database needs a selective reset: **keep users and
subscriptions, wipe everything else**.

### 1. Wait for deploy to complete

Check that the new ECS tasks are running:

```bash
aws ecs describe-services --cluster stepora \
  --services stepora-backend stepora-celery stepora-celery-beat \
  --query 'services[*].{name:serviceName, running:runningCount, desired:desiredCount, status:status}' \
  --output table
```

### 2. Connect via ECS exec

```bash
TASK_ID=$(aws ecs list-tasks --cluster stepora \
  --service-name stepora-backend \
  --query 'taskArns[0]' --output text | awk -F/ '{print $NF}')

aws ecs execute-command \
  --cluster stepora \
  --task $TASK_ID \
  --container backend \
  --interactive \
  --command "/bin/bash"
```

### 3. Run the migration script

Inside the container:

```bash
bash scripts/prod_migrate.sh
```

The script will:
1. Back up all user-related data to `/tmp/stepora_migration_backup/`
2. Drop tables for non-user apps (dreams, plans, chat, etc.)
3. Clear stale content types
4. Run fresh migrations
5. Seed reference data (dream templates, leagues)
6. Print a verification summary

To skip the interactive confirmation:

```bash
bash scripts/prod_migrate.sh --yes
```

### 4. Verify

Still inside the container:

```bash
python manage.py shell -c "
from apps.users.models import User
print(f'Users: {User.objects.count()}')
"
```

## Post-Deploy Verification

### Health checks

```bash
# Liveness
curl -s https://api.stepora.app/health/liveness/

# Full API smoke test
./scripts/qa_api_health_check.sh https://api.stepora.app
```

### Frontend

1. Open https://stepora.app
2. Log in with an existing account
3. Create a new dream
4. Verify chat, notifications, circles features

### ECS service health

```bash
aws ecs describe-services --cluster stepora \
  --services stepora-backend stepora-celery stepora-celery-beat \
  --query 'services[*].{name:serviceName, running:runningCount, deployments:length(deployments)}' \
  --output table
```

### Logs (if something goes wrong)

```bash
aws logs tail /ecs/stepora-backend --since 30m --follow
```

## Rollback

If the deploy causes issues:

1. Find the last working task definition revision:
   ```bash
   aws ecs list-task-definitions --family-prefix stepora-backend \
     --sort DESC --max-items 5
   ```

2. Roll back the service:
   ```bash
   aws ecs update-service --cluster stepora \
     --service stepora-backend \
     --task-definition stepora-backend:PREVIOUS_REVISION \
     --force-new-deployment
   ```

3. Repeat for `stepora-celery` and `stepora-celery-beat` if needed.

## Key Infrastructure Details

| Resource | Value |
|---|---|
| AWS Region | eu-west-3 (Paris) |
| ECS Cluster | stepora |
| RDS | stepora-db (PostgreSQL 15) |
| Redis | stepora-redis (cache.t3.micro) |
| ECR | stepora/backend |
| CloudFront | EAG7EHOMSZ47W (stepora.app) |
| ALB | stepora-alb (api.stepora.app, stepora.net) |
| Secrets | stepora/backend-env (Secrets Manager) |
