# Change Management Process

**Last updated:** 2026-03-26
**Owner:** Development / DevOps

## Branch Strategy

```
feature/xxx ──PR──> development (CI only) ──merge──> main (CI + CD to AWS)
fix/xxx     ──────> main (hotfixes for prod)
```

- **main**: Mirror of AWS production. Merges trigger CI + CD deploy.
- **development**: All new features and non-urgent bug fixes. CI lint/test only.
- **fix/xxx**: Hotfix branches from `main` for production-only issues.

## Change Categories

| Category | Branch From | Merge To | Approval | Deploy |
|----------|------------|----------|----------|--------|
| Feature | development | development -> main | PR review | Automatic on main merge |
| Bug fix | development | development -> main | PR review | Automatic on main merge |
| Hotfix | main | main | PR review (expedited) | Automatic on main merge |
| Infrastructure | N/A | Manual | DevOps decision | Manual AWS CLI/Console |
| Database migration | development | development -> main | PR review + migration review | Via entrypoint.sh on deploy |

## Pre-Deployment Checklist

### Code Changes
- [ ] All CI checks pass (lint, tests)
- [ ] PR reviewed and approved
- [ ] No security scanning failures (once integrated)
- [ ] Database migrations are reversible (`python manage.py showmigrations`)
- [ ] No secrets or credentials in the diff

### Infrastructure Changes
- [ ] Change documented before applying
- [ ] Rollback plan identified
- [ ] Cost impact estimated
- [ ] Applied to staging/preprod first (VPS) if applicable

### High-Risk Changes
These require additional review:
- Authentication/authorization logic changes
- Database schema migrations (especially destructive)
- Payment/Stripe integration changes
- CORS, CSP, or security header changes
- Environment variable additions/changes
- ECS task definition changes

## Deployment Process

### Automated (CI/CD)

1. Merge PR to `main`
2. GitHub Actions triggers (`deploy-backend.yml` / `deploy-frontend.yml`)
3. CI: lint + test
4. Build: Docker image with commit SHA tag
5. Push: ECR
6. Deploy: New ECS task definition, `--force-new-deployment`
7. ECS: `entrypoint.sh` runs `migrate --noinput` then starts daphne
8. Health check: ALB verifies `/health/` returns 200

### Rollback

1. Identify the previous working ECS task definition revision
2. Update ECS service to use previous task definition
3. Or: revert the git commit and re-deploy

```bash
# Quick rollback: revert to previous task definition
aws ecs update-service \
  --cluster stepora \
  --service stepora-backend \
  --task-definition stepora-backend:<previous-revision>
```

## Post-Deployment Verification

- [ ] Health endpoint returns 200: `curl https://api.stepora.app/health/`
- [ ] Check ECS task logs for errors: CloudWatch `/ecs/stepora-backend`
- [ ] Verify key user flows (login, dream creation) work
- [ ] Monitor error rates in logs for 15 minutes post-deploy

## Emergency Changes

For production-down scenarios:
1. Create `fix/` branch from `main`
2. Apply minimal fix
3. PR with expedited review (can self-approve if sole developer)
4. Merge to `main` (triggers automatic deploy)
5. Document the incident and root cause after resolution
