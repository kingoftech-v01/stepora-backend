# Information Security Management System (ISMS) Outline

Security audit reference: Vuln 792 (ISO 27001 ISMS), Vuln 784 (SOC 2 Security)

This document provides the framework for a formal ISMS. Sections marked [TODO] require
population with actual organizational details before this becomes an active policy.

---

## 1. Scope

**In scope:**
- Stepora web application (stepora.app)
- Stepora API backend (api.stepora.app)
- Stepora site vitrine (stepora.net)
- AWS infrastructure (ECS, RDS, ElastiCache, S3, CloudFront)
- VPS preprod environment
- CI/CD pipelines (GitHub Actions)
- Source code repositories (GitHub)

**Out of scope:**
- End-user devices
- Third-party services beyond API integrations (Stripe, OpenAI, Google, Agora, Firebase)

---

## 2. Information Security Policy

### 2.1 Purpose
Protect the confidentiality, integrity, and availability of Stepora user data and
application infrastructure.

### 2.2 Principles
- Defense in depth: multiple layers of security controls
- Least privilege: minimal access required for each role
- Fail secure: errors must not expose data or bypass controls
- No silent failures: all errors must be logged and visible

### 2.3 Responsibilities
[TODO: Assign roles]
- **Security Lead**: [Name] -- Owns ISMS, conducts reviews, manages incidents
- **Development Lead**: [Name] -- Implements security controls in code
- **Infrastructure Lead**: [Name] -- Manages AWS, DNS, certificates
- **Data Protection Officer**: [Name] -- GDPR compliance, data handling

---

## 3. Risk Management

See `RISK_ASSESSMENT_TEMPLATE.md` for the risk assessment methodology.

### 3.1 Risk Assessment Schedule
- Full assessment: annually
- Trigger-based: after significant changes, incidents, or new threats
- Continuous: automated scanning in CI/CD (bandit, pip-audit, ruff security rules)

### 3.2 Risk Treatment Options
1. **Mitigate**: Implement controls to reduce risk
2. **Accept**: Document accepted risks with business justification
3. **Transfer**: Use insurance or third-party services (e.g., Stripe for payments)
4. **Avoid**: Remove the risk source entirely

---

## 4. Security Controls (Implemented)

### 4.1 Access Control
- JWT authentication with 15-minute access tokens
- Token blacklisting on rotation
- Admin IP restriction middleware
- Email verification enforcement
- Rate limiting on all endpoints (tiered by endpoint sensitivity)
- Non-root container user (appuser, UID 1000)

### 4.2 Cryptography
- Field-level encryption for PII (django-encrypted-model-fields)
- TLS in transit (HSTS with 1-year max-age, preload)
- Database SSL (sslmode=require)
- Secure cookie flags (Secure, SameSite, HttpOnly)
- AWS KMS for secrets encryption at rest

### 4.3 Communications Security
- CORS strict origin validation
- CSRF protection with trusted origins
- Security headers (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, COOP, CORP)
- WebSocket authentication via JWT

### 4.4 Operations Security
- Structured JSON logging to CloudWatch
- Sentry error tracking (send_default_pii=False)
- Health checks on all containers
- Automated container restart on failure
- Database connection pooling (PgBouncer sidecar)
- Container resource limits (CPU + memory)
- Read-only container filesystems

### 4.5 Supplier Relations
| Supplier | Data Shared | Controls |
|---|---|---|
| AWS | All application data | IAM, encryption at rest, VPC isolation |
| Stripe | Customer ID only | PCI-DSS Level 1 certified, redirect checkout |
| OpenAI | Dream text (anonymized) | API-only, no data retention agreement |
| Google | Calendar events (user-consented) | OAuth 2.0, minimal scope |
| Sentry | Error traces (no PII) | send_default_pii=False |
| Firebase | Push notification tokens | Device tokens only |
| Agora | Session tokens | Token-based auth, no user data |

---

## 5. Incident Management

### 5.1 Incident Classification
[TODO: Define severity levels]
- **P1 (Critical)**: Data breach, service down, security bypass
- **P2 (High)**: Partial service degradation, potential data exposure
- **P3 (Medium)**: Non-critical bug with security implications
- **P4 (Low)**: Security improvement opportunity

### 5.2 Response Process
[TODO: Document response procedures]
1. **Detection**: CloudWatch alarms, Sentry alerts, user reports
2. **Triage**: Classify severity, identify scope
3. **Containment**: Isolate affected systems
4. **Eradication**: Remove root cause
5. **Recovery**: Restore service
6. **Post-mortem**: Document lessons learned

### 5.3 Communication Plan
[TODO: Define communication channels and escalation]
- Internal: [communication channel]
- External (users): [notification method]
- Regulatory: CNIL notification within 72 hours for GDPR breaches

---

## 6. Business Continuity

### 6.1 Backup Strategy
- **Database**: RDS automated daily snapshots (7-day retention)
- **Media files**: S3 with versioning
- **Source code**: GitHub with branch protection
- **Infrastructure**: Infrastructure defined in ECS task definitions + CI/CD workflows

### 6.2 Recovery Targets
[TODO: Define and validate]
- **RTO** (Recovery Time Objective): Target 1 hour
- **RPO** (Recovery Point Objective): Target 24 hours (daily DB snapshots)

### 6.3 Disaster Recovery
[TODO: Document step-by-step recovery procedures]
1. Database: Restore from RDS snapshot
2. Application: Redeploy via CI/CD pipeline
3. DNS: Cloudflare failover (if needed)

---

## 7. Compliance Monitoring

- Security audit: Quarterly code review (automated + manual)
- SAST scanning: Every CI/CD build (bandit + ruff + pip-audit)
- Dependency updates: Monthly review of pip-audit reports
- Access review: [TODO: Quarterly IAM review]
- Log review: [TODO: Weekly CloudWatch review]

---

## 8. Document Control

| Version | Date | Author | Changes |
|---|---|---|---|
| 0.1 | 2026-03-26 | Security audit | Initial outline created |

**Review schedule**: Annually, or after significant incidents/changes.
