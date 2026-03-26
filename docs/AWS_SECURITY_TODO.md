# AWS Infrastructure Security TODO

**Last updated:** 2026-03-26
**Source:** Security audit batch 501-600
**Priority:** Items ordered by severity (CRITICAL first)

---

## CRITICAL Priority

### V-549/V-550: Enable CloudTrail

**Status:** TODO
**Estimated cost:** ~$2-5/month (S3 storage for logs)

- [ ] Enable multi-region CloudTrail trail
- [ ] Store logs in a dedicated S3 bucket with:
  - [ ] S3 Object Lock (WORM) for log integrity (V-578, V-579)
  - [ ] KMS CMK encryption (V-550)
  - [ ] Lifecycle policy (archive to Glacier after 90 days)
- [ ] Enable CloudTrail Insights for anomaly detection
- [ ] Configure SNS notifications for critical API calls

```bash
aws cloudtrail create-trail \
  --name stepora-audit-trail \
  --s3-bucket-name stepora-cloudtrail-logs \
  --is-multi-region-trail \
  --enable-log-file-validation \
  --kms-key-id <KMS_KEY_ARN>
```

---

### V-541: Verify RDS Not Publicly Accessible

**Status:** TODO (requires AWS Console verification)

- [ ] Check: `aws rds describe-db-instances --db-instance-identifier stepora-db --query 'DBInstances[0].PubliclyAccessible'`
- [ ] If `true`, set to `false`: `aws rds modify-db-instance --db-instance-identifier stepora-db --no-publicly-accessible`
- [ ] Ensure RDS security group only allows inbound from ECS task security groups

---

### V-552: Verify ECS Security Group Rules

**Status:** TODO (requires AWS Console verification)

- [ ] Verify ECS task security group only allows inbound on port 8000 from ALB security group
- [ ] Verify no 0.0.0.0/0 inbound rules on ECS task security group
- [ ] Verify egress rules are scoped (currently likely allows all outbound)
- [ ] Document security group IDs and rules

---

### V-570: Enable Cost Anomaly Detection

**Status:** TODO
**Estimated cost:** Free

- [ ] Enable AWS Cost Anomaly Detection
- [ ] Set up budget alerts ($50/month threshold)
- [ ] Configure SNS notification for cost spikes

```bash
aws ce create-anomaly-monitor \
  --anomaly-monitor '{"MonitorName":"stepora-cost-monitor","MonitorType":"DIMENSIONAL","MonitorDimension":"SERVICE"}'
```

---

### V-575: Privilege Escalation Monitoring

**Status:** TODO

- [ ] Create CloudWatch Events rule for IAM policy changes
- [ ] Monitor `PutUserPolicy`, `AttachUserPolicy`, `CreateUser`, `AddUserToGroup`
- [ ] Set up SNS alerts for admin account modifications
- [ ] Add Django signal to log `is_staff`/`is_superuser` changes in application

---

## HIGH Priority

### V-538/V-559: Deploy AWS WAF

**Status:** TODO
**Estimated cost:** ~$5-10/month (managed rules)

- [ ] Create WAF Web ACL
- [ ] Attach to ALB (`stepora-alb`)
- [ ] Enable managed rule groups:
  - [ ] AWS Managed Rules - Common Rule Set (SQLi, XSS)
  - [ ] AWS Managed Rules - Known Bad Inputs
  - [ ] AWS Managed Rules - Bot Control (optional, higher cost)
- [ ] Configure rate-based rules as backup to DRF throttling
- [ ] Optionally attach to CloudFront distribution (EAG7EHOMSZ47W)

---

### V-542: Enable RDS Encryption at Rest

**Status:** TODO (requires verification)

- [ ] Check: `aws rds describe-db-instances --db-instance-identifier stepora-db --query 'DBInstances[0].StorageEncrypted'`
- [ ] If `false`, encryption requires creating a new encrypted instance from snapshot:
  1. Create snapshot
  2. Copy snapshot with encryption enabled
  3. Restore new instance from encrypted snapshot
  4. Update DNS/endpoints
  5. Delete old instance

---

### V-544: Enable ElastiCache Auth & TLS

**Status:** TODO
**Impact:** Requires Redis connection string update

- [ ] Enable in-transit encryption on ElastiCache cluster
- [ ] Enable AUTH token
- [ ] Update `REDIS_URL` in Secrets Manager to use `rediss://` scheme with AUTH token
- [ ] Force new ECS deployment
- [ ] Test Celery broker, cache, and Channel Layers connectivity

---

### V-547/V-548: Migrate CI/CD to OIDC Federation

**Status:** TODO (eliminates static IAM keys)

- [ ] Create IAM OIDC identity provider for GitHub Actions
- [ ] Create IAM role with trust policy for GitHub repos
- [ ] Update all three CI/CD workflows to use `aws-actions/configure-aws-credentials` with OIDC
- [ ] Delete static IAM access keys
- [ ] Remove `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from GitHub Secrets

---

### V-551: Enable VPC Flow Logs

**Status:** TODO
**Estimated cost:** ~$1-3/month (CloudWatch Logs storage)

- [ ] Enable flow logs on VPC `vpc-07d8842dc93e6d3c2`
- [ ] Send to CloudWatch log group `/vpc/stepora-flow-logs`
- [ ] Set retention to 30 days

```bash
aws ec2 create-flow-logs \
  --resource-type VPC \
  --resource-ids vpc-07d8842dc93e6d3c2 \
  --traffic-type ALL \
  --log-destination-type cloud-watch-logs \
  --log-group-name /vpc/stepora-flow-logs
```

---

### V-554: Scope ECS Task Roles

**Status:** TODO

- [ ] Create separate task roles for each ECS service:
  - `stepora-backend-task-role`: S3 (media), Secrets Manager, CloudWatch Logs, SSM Messages
  - `stepora-celery-task-role`: S3 (media), Secrets Manager, CloudWatch Logs (no SSM)
  - `stepora-celery-beat-task-role`: Secrets Manager, CloudWatch Logs (no SSM, no S3)
- [ ] Apply least-privilege: remove `ssmmessages:*` from celery roles
- [ ] Update task definitions to use service-specific roles

---

### V-555: Enable ECR Image Scanning

**Status:** TODO
**Estimated cost:** Free (basic scanning) or ~$1/month (enhanced)

- [ ] Enable scan-on-push for ECR repositories:
  ```bash
  aws ecr put-image-scanning-configuration --repository-name stepora/backend --image-scanning-configuration scanOnPush=true
  aws ecr put-image-scanning-configuration --repository-name stepora/site --image-scanning-configuration scanOnPush=true
  ```
- [ ] Add scan results check to CI/CD pipeline (fail on CRITICAL/HIGH vulnerabilities)
- [ ] Consider Amazon Inspector for enhanced scanning

---

### V-558: Enable GuardDuty

**Status:** TODO
**Estimated cost:** ~$3-5/month (depends on CloudTrail/VPC Flow volume)

- [ ] Enable GuardDuty in eu-west-3:
  ```bash
  aws guardduty create-detector --enable --finding-publishing-frequency FIFTEEN_MINUTES
  ```
- [ ] Configure SNS notification for HIGH/CRITICAL findings
- [ ] Review findings weekly

---

### V-510/V-556: Automate Secret Rotation

**Status:** TODO (manual rotation documented in INCIDENT_RESPONSE.md)

- [ ] Create Lambda function for RDS password rotation
- [ ] Configure Secrets Manager automatic rotation for `stepora/backend-env`:
  - DB_PASSWORD: 90-day rotation
- [ ] Implement application-level secret refresh (currently reads env vars at startup only)
- [ ] Document rotation schedule for API keys that cannot be auto-rotated

---

## MEDIUM Priority

### V-540/V-585: Encrypt CloudWatch Logs with KMS

**Status:** TODO

- [ ] Create KMS CMK for log encryption
- [ ] Associate with CloudWatch log group `/ecs/stepora-backend`

---

### V-553: Tighten NACLs

**Status:** TODO

- [ ] Review default NACLs on public subnets
- [ ] Add explicit deny rules for unnecessary ports
- [ ] Allow only: 80, 443 (inbound from internet), 8000 (from ALB), ephemeral ports (responses)

---

### V-562: Enable ALB Access Logs

**Status:** TODO
**Estimated cost:** ~$1-2/month (S3 storage)

- [ ] Create S3 bucket for ALB access logs
- [ ] Enable access logging on `stepora-alb`
- [ ] Set lifecycle policy (delete after 90 days)

---

### V-569: Implement Resource Tagging

**Status:** TODO

- [ ] Define tagging strategy:
  - `Project: stepora`
  - `Environment: production`
  - `Service: backend|celery|site`
  - `ManagedBy: terraform|manual`
- [ ] Tag all existing resources
- [ ] Consider AWS Organizations tag policies for enforcement

---

### V-557: Enable AWS Config

**Status:** TODO
**Estimated cost:** ~$2-3/month

- [ ] Enable AWS Config in eu-west-3
- [ ] Enable conformance packs for security best practices
- [ ] Configure SNS notifications for non-compliant resources

---

## LOW Priority / Process Items

### V-571/V-572: SIEM & IDS

**Status:** Deferred (structured JSON logging is the prerequisite, now implemented)

- Consider CloudWatch Logs Insights as a lightweight SIEM alternative
- GuardDuty provides cloud-native IDS capabilities (see above)
- Full SIEM (Splunk, Elastic SIEM) deferred until team/budget grows

### V-592: Vulnerability Disclosure Policy

- [ ] Create `security.txt` file and serve at `/.well-known/security.txt`
- [ ] Add security contact email to public-facing site

### V-593: Bug Bounty Program

- Deferred until post-launch stabilization

### V-594: Penetration Testing

- [ ] Schedule first external pentest (recommend after all HIGH items above are resolved)

### V-596: Data Classification Policy

- [ ] Document data categories: PII, financial (Stripe), encrypted fields, public content

### V-597: Access Review Process

- [ ] Establish quarterly access review cadence
- [ ] Review IAM users, GitHub members, admin accounts

### V-599: Third-Party Security Assessment

- [ ] Verify SOC 2 compliance for: Stripe, AWS, Cloudflare
- [ ] Document vendor security posture

### V-600: Security Training

- [ ] Create secure coding guidelines document
- [ ] OWASP Top 10 awareness for all developers
