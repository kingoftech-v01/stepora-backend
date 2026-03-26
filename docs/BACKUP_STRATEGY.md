# Backup Strategy

**Last updated:** 2026-03-26
**Owner:** Infrastructure / DevOps

## Data Stores & Backup Configuration

### 1. PostgreSQL (RDS)

| Setting | Value |
|---------|-------|
| Instance | `stepora-db` (db.t3.micro, PostgreSQL 15) |
| Region | eu-west-3 (Paris) |
| Automated Backups | Enabled (AWS default) |
| Retention Period | 7 days |
| Backup Window | 03:00-04:00 UTC (low-traffic) |
| Multi-AZ | No (single-AZ) |
| Encryption at Rest | AES-256 (AWS KMS) |

**Manual Snapshots:**
- Create before major deployments: `aws rds create-db-snapshot --db-instance-identifier stepora-db --db-snapshot-identifier pre-deploy-$(date +%Y%m%d)`
- Retain production snapshots for 30 days minimum

**Point-in-Time Recovery:**
- RDS supports PITR to any second within the retention period
- Recovery command: `aws rds restore-db-instance-to-point-in-time --source-db-instance-identifier stepora-db --target-db-instance-identifier stepora-db-restored --restore-time <ISO-8601>`

### 2. Redis (ElastiCache)

| Setting | Value |
|---------|-------|
| Instance | `stepora-redis` (cache.t3.micro) |
| Persistence | None (ephemeral cache) |
| Backup | Not configured |

**Rationale:** Redis stores only transient data (cache, Celery task queue, rate limit counters, session data). All critical state lives in PostgreSQL. Loss of Redis data causes:
- Temporary cache miss (auto-repopulated)
- In-flight Celery tasks lost (email resends, etc.)
- Active rate limit windows reset

**Action items:**
- [ ] Enable Redis RDB snapshots if Celery task loss becomes unacceptable
- [ ] Consider ElastiCache automatic backups (1-day retention, costs ~$0.085/GB/mo)

### 3. S3 Media (User Uploads)

| Setting | Value |
|---------|-------|
| Bucket | `stepora-media-eu` |
| Versioning | Recommended to enable |
| Replication | None (single-region) |
| Durability | 99.999999999% (11 nines, S3 standard) |

**Action items:**
- [ ] Enable S3 versioning: `aws s3api put-bucket-versioning --bucket stepora-media-eu --versioning-configuration Status=Enabled`
- [ ] Add lifecycle rule to expire non-current versions after 30 days
- [ ] Consider cross-region replication to eu-west-1 for DR

### 4. S3 Frontend (SPA Assets)

| Setting | Value |
|---------|-------|
| Bucket | `stepora-frontend-eu` |
| Versioning | Not required (rebuilt from git) |

Frontend assets are fully reproducible from the git repository. No backup needed.

### 5. Application Secrets

| Store | Backup Method |
|-------|---------------|
| AWS Secrets Manager (`stepora/backend-env`) | Versioned by AWS (automatic) |
| GitHub Secrets | Documented in MEMORY.md (manual) |

## Backup Verification Schedule

| Frequency | Action |
|-----------|--------|
| Monthly | Test RDS snapshot restoration to a temporary instance |
| Quarterly | Full DR drill (see DISASTER_RECOVERY.md) |
| After each schema migration | Verify backup includes latest schema |

### RDS Restoration Test Procedure

```bash
# 1. Restore to a temporary instance
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier stepora-db-test-restore \
  --db-snapshot-identifier <latest-snapshot-id> \
  --db-instance-class db.t3.micro

# 2. Wait for instance to become available
aws rds wait db-instance-available --db-instance-identifier stepora-db-test-restore

# 3. Verify data integrity (connect and run checks)
psql -h <restored-endpoint> -U stepora_user -d stepora -c "SELECT count(*) FROM users_user;"

# 4. Clean up
aws rds delete-db-instance --db-instance-identifier stepora-db-test-restore --skip-final-snapshot
```

## Monitoring & Alerts

- [ ] Set CloudWatch alarm for `FreeStorageSpace` on RDS (threshold: 1 GB)
- [ ] Set CloudWatch alarm for failed automated backups
- [ ] Review backup logs monthly in AWS RDS console

## Recovery Objectives

See [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md) for RTO/RPO definitions.
