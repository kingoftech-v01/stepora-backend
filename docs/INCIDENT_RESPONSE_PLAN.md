# Incident Response Plan

**Version:** 1.0
**Last Updated:** 2026-03-26
**Owner:** Security Lead / CTO

## 1. Purpose

This document defines procedures for detecting, responding to, and recovering from security incidents affecting the Stepora platform (api.stepora.app, stepora.app, stepora.net).

## 2. Incident Classification

| Severity | Definition | Response Time | Examples |
|----------|-----------|---------------|----------|
| **P1 - Critical** | Active exploitation, data breach, service fully compromised | 15 min | Data exfiltration, RCE, credential leak, DB compromise |
| **P2 - High** | Significant vulnerability discovered or partial compromise | 1 hour | Auth bypass, privilege escalation, payment fraud |
| **P3 - Medium** | Potential vulnerability, no active exploitation | 4 hours | XSS, CSRF, suspicious auth patterns, dependency CVE |
| **P4 - Low** | Minor issue, minimal impact | 24 hours | Info disclosure, non-sensitive config exposure |

## 3. Incident Response Team

| Role | Responsibility | Contact |
|------|---------------|---------|
| **Incident Commander** | Coordinates response, makes decisions | CTO / Founder |
| **Technical Lead** | Investigates, implements fixes | Lead Developer |
| **Communications** | Handles user/regulatory notifications | CTO / Founder |

For a solo/small team: the founder serves all roles. As the team grows, assign dedicated roles.

## 4. Detection

### Automated Detection
- **Auth failure anomalies**: Celery task `check_auth_failure_anomalies` runs every 15 min, alerts when >50 failures in 15 min window
- **Error spikes**: Sentry alerts on error rate increase
- **CloudWatch Logs**: `/ecs/stepora-backend` with AUTH_FAILURE, PERMISSION_DENIED, JAILBREAK_ATTEMPT filters
- **AWS GuardDuty**: (recommended) Enable for AWS-level threat detection

### Manual Detection
- Security reports via security@stepora.app
- Unusual patterns in admin panel or logs
- User reports of unauthorized activity

## 5. Response Phases

### Phase 1: Identification (0-15 min)
1. Acknowledge the alert or report
2. Assess severity using classification table above
3. Create a private incident channel/thread
4. Begin logging all actions with timestamps

### Phase 2: Containment (15-60 min)
**Immediate containment options:**
- **Block IP**: Add to ALB deny list or AWS WAF rule
- **Disable account**: `User.objects.filter(id=X).update(is_active=False)`
- **Revoke tokens**: Clear Redis cache keys `login_fails:*`, `login_lockout:*`
- **Enable maintenance mode**: Set `MAINTENANCE_MODE=true` env var in ECS
- **Rotate secrets**: Update `stepora/backend-env` in AWS Secrets Manager, redeploy
- **Scale down**: Set ECS desired count to 0 for affected service

### Phase 3: Eradication (1-24 hours)
1. Identify root cause through log analysis
2. Develop and test fix locally
3. Deploy fix via CI/CD (feature branch -> development -> main)
4. Verify fix in production
5. Scan for similar vulnerabilities

### Phase 4: Recovery (1-48 hours)
1. Restore normal operations
2. Monitor for recurrence (increased logging for 7 days)
3. Verify data integrity
4. Re-enable any disabled features

### Phase 5: Post-Incident Review (within 5 business days)
1. Document timeline of events
2. Identify what went well and what needs improvement
3. Create action items with owners and deadlines
4. Update this plan if needed
5. Share lessons learned

## 6. Communication

### Internal
- All incident communications in dedicated private channel
- Status updates every 30 min for P1, every 2 hours for P2

### External (User Notification)
Required when user data is compromised:
- **Within 72 hours** (GDPR requirement): Notify affected users via email
- Include: what happened, what data was affected, what we are doing, what users should do
- Template: see `docs/templates/breach_notification_email.txt`

### Regulatory
- **CNIL (France)**: Notify within 72 hours if EU user data breached
- Contact: notifications@cnil.fr
- Include: nature of breach, categories/number of data subjects, likely consequences, measures taken

## 7. Evidence Preservation

During any incident:
- Do NOT delete logs, containers, or data
- Export CloudWatch logs for the incident period
- Screenshot relevant dashboards
- Save ECS task definitions and container states
- Document all commands executed during response

## 8. Key Resources

| Resource | Location |
|----------|----------|
| CloudWatch Logs | `/ecs/stepora-backend` (eu-west-3) |
| ECS Cluster | `stepora` (eu-west-3) |
| RDS Instance | `stepora-db` (eu-west-3) |
| Secrets Manager | `stepora/backend-env` |
| Security audit log | `security` logger in application |
| Sentry | Project dashboard |
| DNS (Cloudflare) | stepora.app zone, stepora.net zone |

## 9. Review Schedule

This plan is reviewed:
- After every security incident
- Quarterly (minimum)
- When infrastructure changes significantly
