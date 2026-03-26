# Risk Assessment Template

Security audit reference: Vuln 793 (ISO 27001 Risk Assessment), Vuln 795 (NIST CSF Identify)

---

## Methodology

Risk is assessed as: **Risk = Likelihood x Impact**

### Likelihood Scale
| Score | Level | Description |
|---|---|---|
| 1 | Rare | Once per year or less |
| 2 | Unlikely | Once per quarter |
| 3 | Possible | Once per month |
| 4 | Likely | Once per week |
| 5 | Almost Certain | Daily or continuous |

### Impact Scale
| Score | Level | Description |
|---|---|---|
| 1 | Negligible | No data loss, no downtime, no user impact |
| 2 | Minor | Brief downtime (<1h), no data loss |
| 3 | Moderate | Extended downtime (1-4h), minor data exposure |
| 4 | Major | Significant downtime (>4h), PII exposure, financial loss |
| 5 | Critical | Full breach, regulatory notification required, reputational damage |

### Risk Matrix
| | Impact 1 | Impact 2 | Impact 3 | Impact 4 | Impact 5 |
|---|---|---|---|---|---|
| **Likelihood 5** | 5 (Med) | 10 (High) | 15 (High) | 20 (Crit) | 25 (Crit) |
| **Likelihood 4** | 4 (Low) | 8 (Med) | 12 (High) | 16 (High) | 20 (Crit) |
| **Likelihood 3** | 3 (Low) | 6 (Med) | 9 (Med) | 12 (High) | 15 (High) |
| **Likelihood 2** | 2 (Low) | 4 (Low) | 6 (Med) | 8 (Med) | 10 (High) |
| **Likelihood 1** | 1 (Low) | 2 (Low) | 3 (Low) | 4 (Low) | 5 (Med) |

### Treatment Thresholds
- **Critical (20-25)**: Immediate action required
- **High (10-16)**: Remediation within 30 days
- **Medium (5-9)**: Remediation within 90 days
- **Low (1-4)**: Accept or schedule for next cycle

---

## Risk Register

### R-001: Unauthorized API Access
- **Threat**: Attacker bypasses authentication to access user data
- **Likelihood**: 2 (Unlikely)
- **Impact**: 5 (Critical)
- **Risk Score**: 10 (High)
- **Existing controls**: JWT auth, rate limiting, CORS, token blacklisting
- **Treatment**: Mitigate -- add WAF, implement anomaly detection
- **Owner**: [TODO]
- **Status**: Partially mitigated

### R-002: SQL Injection
- **Threat**: Malicious input leads to database compromise
- **Likelihood**: 1 (Rare)
- **Impact**: 5 (Critical)
- **Risk Score**: 5 (Medium)
- **Existing controls**: Django ORM (parameterized queries), DRF serializer validation, nh3 sanitization
- **Treatment**: Mitigate -- SAST scanning (bandit S608 rule), regular code review
- **Owner**: [TODO]
- **Status**: Mitigated

### R-003: Dependency Vulnerability
- **Threat**: Known CVE in Python package exploited
- **Likelihood**: 3 (Possible)
- **Impact**: 4 (Major)
- **Risk Score**: 12 (High)
- **Existing controls**: pip-audit in CI, monthly dependency review
- **Treatment**: Mitigate -- automated Dependabot/Renovate, blocking CI on high-severity CVEs
- **Owner**: [TODO]
- **Status**: Partially mitigated

### R-004: Database Credential Exposure
- **Threat**: Database password leaked via logs, env vars, or code
- **Likelihood**: 1 (Rare)
- **Impact**: 5 (Critical)
- **Risk Score**: 5 (Medium)
- **Existing controls**: AWS Secrets Manager, .env in .gitignore, no PII in Sentry, JSON structured logging
- **Treatment**: Accept (current controls adequate)
- **Owner**: [TODO]
- **Status**: Mitigated

### R-005: Service Unavailability
- **Threat**: Application downtime affecting users
- **Likelihood**: 2 (Unlikely)
- **Impact**: 3 (Moderate)
- **Risk Score**: 6 (Medium)
- **Existing controls**: ECS health checks, auto-restart, PgBouncer, resource limits
- **Treatment**: Mitigate -- define RTO/RPO, document DR procedures, set up CloudWatch alarms
- **Owner**: [TODO]
- **Status**: Partially mitigated

### R-006: Cross-Site Scripting (XSS)
- **Threat**: Malicious script injected via user input
- **Likelihood**: 2 (Unlikely)
- **Impact**: 3 (Moderate)
- **Risk Score**: 6 (Medium)
- **Existing controls**: nh3 sanitization, CSP headers, React auto-escaping, DRF input validation
- **Treatment**: Accept (current controls adequate)
- **Owner**: [TODO]
- **Status**: Mitigated

### R-007: Insider Threat
- **Threat**: Developer with access misuses or leaks data
- **Likelihood**: 1 (Rare)
- **Impact**: 4 (Major)
- **Risk Score**: 4 (Low)
- **Existing controls**: GitHub branch protection, CI/CD pipeline, secrets in AWS Secrets Manager
- **Treatment**: Accept -- implement access reviews when team grows
- **Owner**: [TODO]
- **Status**: Accepted

### R-008: Container Escape
- **Threat**: Attacker breaks out of container to host
- **Likelihood**: 1 (Rare)
- **Impact**: 5 (Critical)
- **Risk Score**: 5 (Medium)
- **Existing controls**: Non-root user, read-only filesystem, resource limits, Fargate isolation
- **Treatment**: Accept (Fargate provides strong isolation)
- **Owner**: [TODO]
- **Status**: Mitigated

### R-009: Log Injection / Log Tampering
- **Threat**: Attacker injects misleading log entries or corrupts audit trail
- **Likelihood**: 2 (Unlikely)
- **Impact**: 3 (Moderate)
- **Risk Score**: 6 (Medium)
- **Existing controls**: JSON structured logging (newline-safe), CloudWatch (append-only)
- **Treatment**: Mitigate -- extend log retention to 365 days
- **Owner**: [TODO]
- **Status**: Partially mitigated

### R-010: Stripe Payment Fraud
- **Threat**: Fraudulent transactions or checkout manipulation
- **Likelihood**: 2 (Unlikely)
- **Impact**: 3 (Moderate)
- **Risk Score**: 6 (Medium)
- **Existing controls**: Stripe Checkout (redirect), webhook signature verification, server-side plan validation
- **Treatment**: Accept (Stripe handles fraud detection)
- **Owner**: [TODO]
- **Status**: Mitigated

---

## Assessment Metadata

| Field | Value |
|---|---|
| Assessment date | 2026-03-26 |
| Assessor | Security audit (automated) |
| Next review | [TODO: 2026-06-26 recommended] |
| Approved by | [TODO] |

---

## Summary

| Risk Level | Count |
|---|---|
| Critical | 0 |
| High | 2 (R-001, R-003) |
| Medium | 6 (R-002, R-004, R-005, R-006, R-008, R-009, R-010) |
| Low | 1 (R-007) |
| Accepted | 3 (R-004, R-006, R-007) |
