# Incident Response Playbook

**Last updated:** 2026-03-26
**Owner:** Engineering team
**Security audit references:** V-589, V-590

---

## 1. Severity Classification

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| **P0 - Critical** | Service down, data breach, security compromise | 15 minutes | RDS compromise, credential leak, full outage |
| **P1 - High** | Major feature broken, partial data exposure | 1 hour | Auth system failure, payment processing down |
| **P2 - Medium** | Degraded performance, minor feature broken | 4 hours | Slow API responses, Celery queue backlog |
| **P3 - Low** | Cosmetic issues, non-critical bugs | Next business day | UI glitches, minor logging errors |

---

## 2. Incident Response Phases

### Phase 1: Detection & Triage (0-15 min)

1. **Identify the incident** via:
   - CloudWatch alarms (ECS task failures, high error rates)
   - Sentry error alerts
   - User reports
   - Monitoring dashboards

2. **Classify severity** using the table above.

3. **Assign an Incident Commander (IC)** -- the first responder owns coordination until handoff.

4. **Create an incident channel/thread** for communication.

### Phase 2: Containment (15-60 min)

- **Service outage:** Check ECS task status, ALB health checks, RDS connectivity.
- **Security breach:** Rotate affected credentials immediately (see Secret Rotation below).
- **Data exposure:** Identify scope of exposed data and affected users.
- **DDoS/abuse:** Enable WAF rules if available; update security group rules to block IPs.

**Key commands for investigation:**

```bash
# Check ECS service status
aws ecs describe-services --cluster stepora --services stepora-backend stepora-celery stepora-celery-beat

# View recent logs
aws logs filter-log-events --log-group-name /ecs/stepora-backend --start-time $(date -d '30 minutes ago' +%s000)

# ECS exec into running container
aws ecs execute-command --cluster stepora --task <TASK_ID> --container backend --interactive --command "/bin/bash"

# Check RDS connectivity
aws rds describe-db-instances --db-instance-identifier stepora-db

# Check Redis (ElastiCache)
aws elasticache describe-cache-clusters --cache-cluster-id stepora-redis
```

### Phase 3: Eradication (1-4 hours)

1. **Root cause analysis** -- identify the underlying issue.
2. **Apply fix:**
   - Code fix: push to `fix/` branch, merge to `main`, CI/CD deploys automatically.
   - Infrastructure fix: apply via AWS Console or CLI.
   - Configuration fix: update Secrets Manager, force new ECS deployment.
3. **Verify fix** in production.

### Phase 4: Recovery

1. **Confirm service is fully operational.**
2. **Monitor for recurrence** (30-60 min observation period).
3. **Notify affected users** if applicable (see Communication Plan below).

### Phase 5: Post-Mortem (within 48 hours)

1. **Document the incident** in `/root/stepora/docs/postmortems/` with:
   - Timeline of events
   - Root cause
   - Impact (users affected, duration)
   - What went well
   - What needs improvement
   - Action items with owners and deadlines
2. **Update monitoring** to detect similar issues earlier.
3. **Update this playbook** if gaps were identified.

---

## 3. Communication Plan

### Internal Communication

| Audience | Channel | When |
|----------|---------|------|
| Engineering team | Slack/Discord #incidents | Immediately |
| Product owner | Direct message | P0/P1 within 30 min |

### External Communication (User-facing)

| Scenario | Action | Timeline |
|----------|--------|----------|
| Service outage > 30 min | Status page update | Within 30 min |
| Data breach (GDPR) | Notify CNIL + affected users | Within 72 hours |
| Payment system issue | Email affected users | Within 24 hours |
| Security vulnerability patched | Optional disclosure | After fix deployed |

### GDPR Data Breach Notification

**72-hour rule:** If personal data is exposed, notify the supervisory authority (CNIL for France) within 72 hours.

Required information:
- Nature of the breach
- Categories and approximate number of data subjects affected
- Likely consequences
- Measures taken or proposed to address the breach

---

## 4. Secret Rotation Procedures

### Database Password (RDS)

1. Generate new password.
2. Update RDS master password: `aws rds modify-db-instance --db-instance-identifier stepora-db --master-user-password <NEW_PASSWORD>`
3. Update `stepora/backend-env` in Secrets Manager with new `DB_PASSWORD`.
4. Force new deployment of all ECS services (backend, celery, celery-beat).
5. Verify connectivity.

### Django Secret Key

1. Generate: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
2. Update `DJANGO_SECRET_KEY` in Secrets Manager.
3. Force new ECS deployment. Note: existing sessions will be invalidated.

### FIELD_ENCRYPTION_KEY

**WARNING:** Changing this key makes all encrypted fields unreadable. Only rotate if compromised.

1. Plan a data migration to re-encrypt all encrypted fields.
2. Generate new Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
3. Run migration to decrypt with old key and re-encrypt with new key.
4. Update Secrets Manager and deploy.

### API Keys (OpenAI, Stripe, Agora)

1. Generate new key in the provider's dashboard.
2. Update the corresponding key in `stepora/backend-env` Secrets Manager.
3. Force new ECS deployment.
4. Revoke the old key in the provider's dashboard.

### IAM Access Keys (CI/CD)

1. Create new access key in IAM Console.
2. Update `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in GitHub Secrets for all repos.
3. Verify CI/CD pipeline works with new keys.
4. Deactivate and delete old access key.

### VAPID Keys (Web Push)

1. Generate new VAPID key pair.
2. Update `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` in Secrets Manager.
3. Deploy backend. Note: existing push subscriptions will need re-registration.

---

## 5. Emergency Contacts & Access

| Resource | Access Method |
|----------|--------------|
| AWS Console | IAM user login at https://987409845802.signin.aws.amazon.com/console |
| ECS Services | AWS CLI with appropriate IAM credentials |
| RDS Database | Via ECS exec (no direct access) |
| GitHub Repos | https://github.com/kingoftech-v01/ |
| Cloudflare DNS | Dashboard at dash.cloudflare.com |
| Stripe Dashboard | dashboard.stripe.com |
| Sentry | sentry.io |

---

## 6. Rollback Procedures

### Backend Rollback

```bash
# Find previous task definition revision
aws ecs list-task-definitions --family-prefix stepora-backend --sort DESC --max-items 5

# Update service to previous revision
aws ecs update-service --cluster stepora --service stepora-backend --task-definition stepora-backend:<PREVIOUS_REVISION> --force-new-deployment
```

### Frontend Rollback

```bash
# S3 versioning (if enabled) -- restore previous version
# Or re-deploy from the previous Git tag/commit
git checkout <PREVIOUS_TAG>
npm run build
aws s3 sync dist/ s3://stepora-frontend-eu/ --delete
aws cloudfront create-invalidation --distribution-id EAG7EHOMSZ47W --paths "/*"
```
