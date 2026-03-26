# Security Policy

**Version:** 1.0
**Last Updated:** 2026-03-26

## 1. Overview

This document defines the security policies governing the development, deployment, and operation of the Stepora platform.

## 2. Development Security

### Secure Coding Standards
- All user input validated server-side via DRF serializers + `core/validators.py`
- HTML output sanitized: DOMPurify (frontend), nh3 (backend)
- No broad `except Exception` in security-critical paths (auth, payments, permissions)
- SQL injection prevention: Django ORM only, no raw SQL without parameterization
- Secrets via environment variables or AWS Secrets Manager, never in code

### Code Review Requirements
- All changes to `core/auth/`, `core/permissions.py`, `apps/subscriptions/` require security-focused review
- CI/CD runs Black, isort, Flake8 on all PRs
- Recommended: Add Bandit (SAST) and pip-audit (dependency scanning) to CI pipeline

### Dependency Management
- Pin all dependencies in `requirements/` files
- Run `pip-audit` before releases
- Monitor GitHub Dependabot alerts (when enabled)
- Patch critical CVEs within 7 days, high within 14 days

## 3. Authentication & Authorization

### Authentication
- JWT access tokens: 15 min lifetime, stored in memory (not localStorage)
- Refresh tokens: 7 day lifetime, httpOnly secure cookie (web) or body (native)
- Account lockout: 5 failed attempts triggers 15-min lockout per IP and email
- 2FA: TOTP-based, challenge token flow prevents token leakage before verification
- Social auth: Google and Apple Sign-In via direct ID token verification

### Authorization
- Default permission: `IsAuthenticated` (fail-closed)
- Object-level: `IsOwner` permission on all user resources
- Subscription-gated: 9 tier-based permission classes
- Admin: IP-restricted via `AdminIPRestrictionMiddleware`

### Password Policy
- Minimum 8 characters
- Cannot be similar to user attributes
- Cannot be in common password list (20,000 entries)
- Cannot be entirely numeric

## 4. Data Protection

### Data Classification
See `docs/DATA_CLASSIFICATION.md` for full classification scheme.

### Encryption
- **In transit**: TLS 1.2+ (HSTS enforced, 1-year max-age)
- **At rest**: RDS encryption enabled, S3 server-side encryption
- **Field-level**: Fernet encryption for TOTP secrets and sensitive PII

### Data Retention
- User data: retained until account deletion
- Soft-deleted accounts: hard-deleted after 30 days (GDPR compliance)
- Security logs: 30 days in CloudWatch
- Audit events: logged to `security` logger

## 5. Infrastructure Security

### Network
- ECS Fargate in public subnets with security groups
- RDS in private subnets, accessible only from ECS security group
- Redis (ElastiCache) in VPC, no public access
- ALB with AWS Shield Standard

### Container Security
- Non-root user (`appuser`) in all containers
- Immutable container images from CI/CD
- PgBouncer sidecar for database connection pooling

### Secret Management
- All secrets in AWS Secrets Manager (`stepora/backend-env`)
- No secrets in source code, environment files, or container images
- Secret rotation: manual (recommended: automate via Secrets Manager rotation)

## 6. Monitoring & Alerting

### Security Monitoring
- Auth failures logged via `core/audit.py` (structured security logger)
- Anomaly detection: Celery task checks auth failure threshold every 15 min
- Sentry for application error tracking

### Alerts
- Auth failure spike (>50 in 15 min): email alert to admins
- Application errors: Sentry notifications
- ECS health check failures: ECS auto-restart

## 7. Incident Response

See `docs/INCIDENT_RESPONSE_PLAN.md` for full incident response procedures.

## 8. Compliance

- **GDPR**: Right to deletion (30-day hard delete), data export endpoint, privacy policy at stepora.net/privacy/
- **PCI DSS**: Payment processing delegated to Stripe (no card data stored)
- **Email**: SPF, DKIM, DMARC configured for stepora.net

## 9. Policy Review

This policy is reviewed:
- Annually (minimum)
- After security incidents
- When significant infrastructure changes occur
