# Stepora Compliance Status

Last updated: 2026-03-26
Security audit reference: `security-audit-2026-03-26/batch_701_800.md`

## Overview

Stepora is a dream/goal planning SaaS. It processes user-generated content and personal goals
but does NOT handle cardholder data (Stripe Checkout redirect), ePHI, or classified information.
This document tracks compliance posture against major frameworks.

---

## PCI-DSS (Payment Card Industry)

**Applicability**: Minimal. Stepora uses Stripe Checkout (redirect model). No cardholder data
(PAN, CVV, PIN) touches Stepora servers. Stripe is the PCI-DSS Level 1 compliant processor.

| Requirement | Status | Notes |
|---|---|---|
| 1. Firewall / network controls | PASS | AWS Security Groups + ALB |
| 2. No default passwords | PASS | Env-var-based secrets, 4 password validators |
| 3. Protect cardholder data | PASS | No cardholder data stored |
| 4. Encryption in transit | PASS | HSTS, TLS, secure cookies, DB SSL |
| 6. Secure systems | PARTIAL | SAST added (bandit + ruff S-rules). No WAF yet |
| 8. Authentication | PASS | JWT, rate limiting, token blacklisting |
| 10. Logging & monitoring | PARTIAL | JSON structured logs. CloudWatch retention 30 days (need 12 months) |
| 11. Security testing | PARTIAL | SAST in CI. No formal pen-test program yet |

**Action items**:
- [ ] Extend CloudWatch log retention to 365 days (`/ecs/stepora-backend` log group)
- [ ] Evaluate AWS WAF for ALB (cost vs. risk)
- [ ] Schedule annual penetration test
- [ ] File SAQ-A with Stripe (self-assessment questionnaire for redirect-only merchants)

---

## SOC 2 Type II

**Applicability**: Relevant if pursuing enterprise customers. Not currently required.

| Trust Service Criteria | Status | Notes |
|---|---|---|
| Security | PARTIAL | Strong technical controls. Missing formal policies |
| Availability | PARTIAL | Health checks, auto-restart, DB backups. Missing SLA/DR docs |
| Confidentiality | PARTIAL | Field encryption, no PII in Sentry. Missing data classification |
| Processing Integrity | PASS | Input validation, DB constraints, Stripe webhook verification |
| Privacy | PARTIAL | Account deletion + data export exist. Missing privacy impact assessment |

**Action items**:
- [ ] Create Information Security Policy (see `ISMS_OUTLINE.md`)
- [ ] Document incident response plan
- [ ] Define SLAs with RTO/RPO targets
- [ ] Create data classification policy
- [ ] Conduct privacy impact assessment (DPIA)

---

## ISO 27001

**Applicability**: Not currently pursuing certification. Controls assessed for best-practice alignment.

| Control Area | Status | Notes |
|---|---|---|
| ISMS framework | NOT STARTED | Outline created (see `ISMS_OUTLINE.md`) |
| Risk assessment | NOT STARTED | Template created (see `RISK_ASSESSMENT_TEMPLATE.md`) |
| Access control (technical) | PASS | JWT, RBAC, admin IP restriction, rate limiting |
| Access control (governance) | NOT STARTED | Need formal access control policy |

**Action items**:
- [ ] Populate ISMS outline with actual scope and responsibilities
- [ ] Conduct initial risk assessment using template
- [ ] Document access review process

---

## NIST Cybersecurity Framework (CSF)

| Function | Status | Notes |
|---|---|---|
| Identify | PARTIAL | Architecture docs exist. Missing asset inventory, data classification |
| Protect | PASS | Access controls, encryption, security headers, content moderation |
| Detect | PARTIAL | CloudWatch logs + Sentry. No SIEM, no anomaly detection |
| Respond | NOT STARTED | No incident response plan |
| Recover | PARTIAL | DB backups, ECS auto-restart. Missing DR plan, RTO/RPO |

**Action items**:
- [ ] Create asset inventory (servers, services, data stores)
- [ ] Implement CloudWatch alarms for security events
- [ ] Create incident response playbook
- [ ] Document disaster recovery with restoration procedures
- [ ] Define and test RTO (target: 1 hour) and RPO (target: 24 hours)

---

## CIS Benchmarks

**Status**: Not formally assessed. Container images use slim/alpine bases.

**Action items**:
- [ ] Run Docker CIS Benchmark against development environment
- [ ] Document applicable benchmarks and exceptions
- [ ] Automate CIS checks in CI (e.g., `docker-bench-security`)

---

## HIPAA

**Applicability**: N/A. Stepora is not a healthcare application. No ePHI is collected or processed.

---

## GDPR / Data Privacy

| Area | Status | Notes |
|---|---|---|
| Right to erasure | IMPLEMENTED | Account deletion with anonymization |
| Right to data portability | IMPLEMENTED | Data export functionality |
| Privacy policy | PUBLISHED | Available at stepora.net/privacy/ |
| Terms of service | PUBLISHED | Available at stepora.net/terms/ |
| Cookie consent | PARTIAL | Stepora.app is API-only (no cookies for tracking) |
| Data processing records | NOT STARTED | Need Article 30 records |

---

## Log Retention Requirements (Vuln 782)

Current CloudWatch log retention: 30 days.

Compliance requirements:
- PCI-DSS Req 10: 12 months minimum (3 months immediately available)
- SOC 2: Varies, typically 12 months
- GDPR: "As long as necessary" (minimize retention)

**Recommended action**: Set `/ecs/stepora-backend` log group retention to 365 days.
AWS CLI command:
```bash
aws logs put-retention-policy \
  --log-group-name /ecs/stepora-backend \
  --retention-in-days 365 \
  --region eu-west-3
```

Estimated cost increase: ~$2-5/month depending on log volume.

---

## Priority Remediation Roadmap

### Immediate (Week 1)
1. Extend CloudWatch log retention to 365 days
2. SAST in CI (DONE -- bandit + ruff security rules added)
3. Container resource limits (DONE)
4. Container read-only filesystems (DONE)
5. JSON structured logging (DONE)

### Short-term (Month 1)
6. AWS WAF evaluation for ALB
7. Container image signing with cosign (TODO added in CI)
8. ECR image vulnerability scanning (added to CI)

### Medium-term (Quarter 1)
9. Populate ISMS outline
10. Conduct risk assessment
11. Create incident response plan
12. Define SLAs with RTO/RPO

### Long-term (Quarter 2+)
13. Annual penetration test
14. SOC 2 readiness assessment (if pursuing enterprise)
15. SIEM integration (CloudWatch + Lambda alerting as first step)
