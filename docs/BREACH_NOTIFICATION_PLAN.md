# Data Breach Notification Plan

**Owner:** Stepora Engineering
**Last Updated:** 2026-03-26
**Review Frequency:** Annually or after any incident

---

## 1. Definitions

**Personal Data Breach:** A breach of security leading to the accidental or unlawful destruction, loss, alteration, unauthorized disclosure of, or access to personal data.

**Severity Levels:**
- **Critical:** Credentials, payment data, or encrypted PII keys compromised
- **High:** Unencrypted PII exposed (emails, display names, locations)
- **Medium:** Metadata or behavioral data exposed (activity logs, preferences)
- **Low:** Non-personal data breach or attempted breach without data exposure

## 2. Detection Sources

| Source | Monitoring |
|--------|-----------|
| Sentry | Application errors, unhandled exceptions |
| CloudWatch | ECS container logs, ALB access logs |
| AWS GuardDuty | (Recommended) Threat detection for AWS resources |
| Stripe Dashboard | Payment anomalies |
| Manual Report | User reports via privacy@stepora.app |

## 3. Response Timeline (GDPR Art. 33-34)

| Action | Deadline | Responsible |
|--------|----------|-------------|
| **Identify & Contain** | Within 1 hour of detection | On-call engineer |
| **Initial Assessment** | Within 4 hours | Engineering lead |
| **DPA Notification** | Within 72 hours (if required) | DPO / privacy@stepora.app |
| **User Notification** | Without undue delay (if high risk) | DPO + Engineering |
| **Post-Incident Review** | Within 7 days | Full team |

## 4. Containment Procedures

### Immediate Actions (Hour 0-1)
1. **Rotate compromised credentials** (DB passwords, API keys, FIELD_ENCRYPTION_KEY)
2. **Revoke active sessions** -- flush Redis, invalidate all JWT tokens
3. **Block attack vector** -- update security groups, WAF rules, or disable compromised endpoint
4. **Preserve evidence** -- snapshot CloudWatch logs, RDS snapshots, ECS task definitions

### Credential Rotation Checklist
- [ ] `DJANGO_SECRET_KEY` in AWS Secrets Manager
- [ ] `FIELD_ENCRYPTION_KEY` in AWS Secrets Manager (CRITICAL: requires data re-encryption)
- [ ] `DB_PASSWORD` in RDS + Secrets Manager
- [ ] `OPENAI_API_KEY` in Secrets Manager
- [ ] `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET`
- [ ] `AGORA_APP_CERTIFICATE`
- [ ] GitHub PAT for CI/CD
- [ ] Force new ECS task deployments after secret rotation

## 5. Assessment Criteria

### Determine if Notification is Required

Notify the supervisory authority (CNIL for France) if the breach is **likely to result in a risk to the rights and freedoms of natural persons**.

**Factors:**
- Type of data (encrypted PII vs. plaintext)
- Number of affected users
- Whether FIELD_ENCRYPTION_KEY was also compromised
- Whether data was actually accessed or just exposed

**No notification required if:**
- Data was encrypted and encryption key was NOT compromised
- Breach involved only anonymized/pseudonymized data
- Attack was contained before any data was accessed

## 6. Notification Templates

### Supervisory Authority (CNIL) Notification
Include:
- Nature of the breach (what happened)
- Categories and approximate number of data subjects
- Categories of personal data records concerned
- Likely consequences
- Measures taken or proposed to address the breach

### User Notification (if high risk)
Template available at: `templates/emails/breach_notification.html`

Required content:
- Clear description of what happened
- What data was affected
- What we have done
- What users should do (change password, monitor accounts)
- Contact point for questions (privacy@stepora.app)

## 7. Post-Incident Review

After every breach or near-miss:
1. **Root Cause Analysis** -- document the exact vulnerability chain
2. **Timeline** -- minute-by-minute account of detection, containment, resolution
3. **Impact Assessment** -- final count of affected users and data types
4. **Remediation** -- code fixes, infrastructure changes, process improvements
5. **Lessons Learned** -- update this plan, security audit checklist, monitoring

## 8. Incident Log

All incidents are logged in a private incident register (not in this public document).

| Date | Severity | Description | Users Affected | DPA Notified | Resolution |
|------|----------|-------------|----------------|--------------|------------|
| -- | -- | No incidents to date | -- | -- | -- |

## 9. Regulatory Contacts

| Authority | Contact |
|-----------|---------|
| CNIL (France) | https://www.cnil.fr/fr/notifier-une-violation-de-donnees-personnelles |
| ICO (UK, if applicable) | https://ico.org.uk/make-a-complaint/data-protection-complaints/data-protection-complaints/ |

## 10. Annual Review Checklist

- [ ] Review and update this plan
- [ ] Test incident response procedure (tabletop exercise)
- [ ] Verify all monitoring/alerting is active
- [ ] Confirm credential rotation procedures are documented and tested
- [ ] Review third-party processor DPAs
