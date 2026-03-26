# Disaster Recovery Plan

**Last updated:** 2026-03-26
**Owner:** Infrastructure / DevOps

## Recovery Objectives

| Metric | Target | Current Capability |
|--------|--------|--------------------|
| **RTO** (Recovery Time Objective) | 2 hours | ~1-2 hours (RDS restore + ECS redeploy) |
| **RPO** (Recovery Point Objective) | 1 hour | ~24 hours (RDS daily snapshots); 5 min with PITR |

**Rationale:** Stepora is a consumer application. Users can tolerate brief outages (planning/tracking is not real-time critical). The 2-hour RTO and 1-hour RPO balance cost against user impact.

## Failure Scenarios & Recovery Procedures

### Scenario 1: Database Failure (RDS)

**Impact:** Full outage (all API calls fail)
**Detection:** Health check endpoint returns `database: down`, ECS tasks restart, ALB returns 503

**Recovery:**
```bash
# Option A: Point-in-Time Recovery (preferred, RPO = seconds)
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier stepora-db \
  --target-db-instance-identifier stepora-db-recovered \
  --restore-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --db-instance-class db.t3.micro \
  --vpc-security-group-ids <sg-id>

# Option B: Snapshot Recovery (RPO = last snapshot, typically <24h)
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier stepora-db-recovered \
  --db-snapshot-identifier <snapshot-id>

# After recovery: update DB_HOST in Secrets Manager, redeploy ECS
```
**Estimated recovery time:** 30-60 minutes

### Scenario 2: Redis Failure (ElastiCache)

**Impact:** Degraded (cache misses, Celery tasks queue locally, rate limits reset)
**Detection:** Health check shows `cache: down`

**Recovery:**
```bash
# Delete and recreate the cache cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id stepora-redis \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --num-cache-nodes 1
```
**Estimated recovery time:** 15-30 minutes. Application self-heals when Redis returns.

### Scenario 3: ECS Service Failure

**Impact:** Partial or full outage depending on which service fails
**Detection:** ALB health checks, CloudWatch alarms

**Recovery:**
```bash
# Force new deployment (pulls latest task definition)
aws ecs update-service --cluster stepora --service stepora-backend --force-new-deployment
aws ecs update-service --cluster stepora --service stepora-celery --force-new-deployment
aws ecs update-service --cluster stepora --service stepora-celery-beat --force-new-deployment
```
**Estimated recovery time:** 5-10 minutes

### Scenario 4: AWS Region Failure (eu-west-3)

**Impact:** Full outage
**Current mitigation:** None (single-region deployment)

**Recovery procedure:**
1. Restore RDS from cross-region snapshot (if configured) or latest available backup
2. Recreate ElastiCache in target region
3. Update ECR images (rebuild and push to new region)
4. Update CloudFront origin to new ALB
5. Update DNS records in Cloudflare

**Estimated recovery time:** 4-8 hours (manual process)

**Action items:**
- [ ] Enable cross-region RDS snapshot copy to eu-west-1
- [ ] Document full region migration runbook

### Scenario 5: Compromised Credentials

**Impact:** Potential data breach
**Detection:** Unusual API patterns, AWS GuardDuty alerts

**Recovery:**
1. Rotate all secrets in AWS Secrets Manager
2. Rotate database password
3. Invalidate all JWT tokens (change `DJANGO_SECRET_KEY`)
4. Force-redeploy all ECS services
5. Review CloudTrail and application logs
6. See [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) for full procedure

### Scenario 6: Accidental Data Deletion

**Recovery:**
- Database: RDS Point-in-Time Recovery to moment before deletion
- Media files: S3 versioning recovery (if enabled) or restore from user re-upload
- Code: Git history

## Communication During Outage

| Audience | Channel | Responsibility |
|----------|---------|---------------|
| Users | In-app banner (if app accessible) or email | Product owner |
| Team | Internal chat | On-call engineer |

## DR Drill Schedule

| Frequency | Scope |
|-----------|-------|
| Monthly | RDS snapshot restoration test |
| Quarterly | Full recovery drill (simulate Scenario 1) |
| Annually | Region failover tabletop exercise |

## Single Points of Failure (Known Risks)

| Component | Risk | Mitigation Path |
|-----------|------|-----------------|
| RDS (single-AZ) | AZ failure = DB down | Enable Multi-AZ ($15/mo additional) |
| Redis (single node) | Node failure = cache loss | Enable Multi-AZ replication |
| ECS (desiredCount=1) | Task crash = brief outage | ECS auto-restarts; consider desiredCount=2 |
