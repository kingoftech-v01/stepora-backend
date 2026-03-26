# Incident Response Plan

Security audit reference: Vuln 798 (NIST CSF Respond), Vuln 784 (SOC 2 Security)

Status: DRAFT -- requires review and approval before activation.

---

## 1. Purpose

Define procedures for detecting, responding to, and recovering from security incidents
affecting Stepora infrastructure, data, or users.

---

## 2. Scope

All Stepora systems: production (AWS), preprod (VPS), CI/CD (GitHub Actions),
source code repositories, and third-party integrations.

---

## 3. Incident Classification

| Severity | Description | Response Time | Examples |
|---|---|---|---|
| P1 - Critical | Active data breach, full service outage | 15 minutes | DB compromised, credentials leaked publicly |
| P2 - High | Partial compromise, significant degradation | 1 hour | API vulnerability exploited, single service down |
| P3 - Medium | Potential security issue, minor impact | 4 hours | Suspicious activity detected, failed login spike |
| P4 - Low | Security improvement, no active threat | Next business day | Dependency CVE (no exploit available) |

---

## 4. Detection Sources

- **Automated**: Sentry error alerts, CloudWatch log anomalies, ECS health check failures
- **CI/CD**: Bandit SAST findings, pip-audit CVE alerts, ruff security rule violations
- **Manual**: User reports, code review findings, security audit results
- **External**: Stripe webhook anomalies, AWS GuardDuty (if enabled)

---

## 5. Response Procedures

### 5.1 P1 - Critical Incident

1. **Immediate containment** (0-15 min)
   - Identify affected systems
   - If data breach: rotate all secrets in AWS Secrets Manager
   - If service compromise: stop affected ECS services
   - If credential leak: revoke and rotate affected credentials

2. **Assessment** (15 min - 1 hour)
   - Determine scope of compromise
   - Identify attack vector
   - Preserve evidence (CloudWatch logs, ECS exec session logs)

3. **Eradication** (1-4 hours)
   - Remove attacker access
   - Patch vulnerability
   - Deploy fix via CI/CD

4. **Recovery** (4-24 hours)
   - Restore services from known-good state
   - Verify data integrity
   - Monitor for recurrence

5. **Post-incident** (within 48 hours)
   - Write post-mortem document
   - Identify root cause
   - Create follow-up action items
   - Notify affected users if required
   - CNIL notification within 72 hours if GDPR breach

### 5.2 P2 - High Incident

Follow P1 steps with relaxed timelines (1 hour initial response).

### 5.3 P3/P4 - Medium/Low Incidents

1. Create tracking issue in GitHub
2. Assess during next business day
3. Schedule fix in next sprint

---

## 6. Communication

### Internal
- [TODO: Primary communication channel]
- [TODO: Escalation contacts]

### External (Users)
- [TODO: Status page URL]
- [TODO: Email notification process]

### Regulatory
- CNIL (French DPA): 72-hour notification for GDPR personal data breaches
- Contact: [TODO: DPO email]

---

## 7. Key Contacts

| Role | Name | Contact |
|---|---|---|
| Security Lead | [TODO] | [TODO] |
| Development Lead | [TODO] | [TODO] |
| Infrastructure Lead | [TODO] | [TODO] |
| Data Protection Officer | [TODO] | [TODO] |

---

## 8. Useful Commands

### Check ECS service status
```bash
aws ecs describe-services --cluster stepora --services stepora-backend stepora-celery stepora-celery-beat --region eu-west-3
```

### View recent logs
```bash
aws logs tail /ecs/stepora-backend --since 1h --region eu-west-3
```

### Rotate secrets
```bash
aws secretsmanager update-secret --secret-id stepora/backend-env --region eu-west-3 --secret-string '...'
```

### Force redeploy (after fix)
```bash
aws ecs update-service --cluster stepora --service stepora-backend --force-new-deployment --region eu-west-3
```

---

## 9. Review Schedule

- Plan review: Every 6 months
- Tabletop exercise: Annually
- Post-incident update: After every P1/P2 incident
