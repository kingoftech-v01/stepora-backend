# Zero-Day Response Plan

**V-1441** | Last updated: 2026-03-26

## 1. Detection & Triage

| Step | Action | Owner | SLA |
|------|--------|-------|-----|
| 1.1 | Monitor vulnerability feeds (GitHub Advisory, NVD, Django/Python security lists) | Lead Dev | Continuous |
| 1.2 | Assess severity: Does it affect Stepora's stack (Django, DRF, Python, Node, Capacitor)? | Lead Dev | < 2 hours |
| 1.3 | Determine exploitability: Is the vulnerable component reachable in production? | Lead Dev | < 4 hours |
| 1.4 | Assign CVSS-based priority: Critical (9-10), High (7-8.9), Medium (4-6.9), Low (0-3.9) | Lead Dev | < 4 hours |

## 2. Containment (Critical/High only)

| Step | Action | Details |
|------|--------|---------|
| 2.1 | Enable maintenance mode | Set `MAINTENANCE_MODE=true` in ECS env if user data is at risk |
| 2.2 | WAF rules (when available) | Add virtual patch via AWS WAF to block exploit patterns |
| 2.3 | Rotate secrets | If credentials may be compromised, rotate via AWS Secrets Manager |
| 2.4 | Revoke tokens | Flush JWT blacklist, force re-authentication |
| 2.5 | Snapshot evidence | RDS snapshot, CloudWatch log export for forensic analysis |

## 3. Patch & Deploy

| Step | Action | SLA by Severity |
|------|--------|-----------------|
| 3.1 | Create `fix/zero-day-CVE-XXXX` branch from `main` | Critical: < 4h, High: < 24h |
| 3.2 | Apply upstream patch or implement workaround | Critical: < 8h, High: < 48h |
| 3.3 | Run full test suite (`pytest`) | Before merge |
| 3.4 | Merge to `main`, CI/CD auto-deploys to AWS | After tests pass |
| 3.5 | Verify fix in production (smoke test) | < 30 min post-deploy |
| 3.6 | Backport to `development` branch | Same day |

## 4. Communication

| Audience | Channel | When |
|----------|---------|------|
| Team | Internal chat | Immediately on detection |
| Users (if data affected) | Email via Stepora + in-app notification | Within 72h (GDPR Article 33) |
| Authorities (if personal data breach) | CNIL (France) notification | Within 72h (GDPR Article 33) |

## 5. Post-Incident Review

- [ ] Root cause analysis document
- [ ] Timeline of detection to resolution
- [ ] What monitoring would have caught it earlier?
- [ ] Update this plan with lessons learned
- [ ] Add regression test for the specific vulnerability

## 6. Preventive Measures

- **pip-audit** runs in CI on every PR (added V-1403)
- **Bandit** SAST runs in CI on every PR (added V-1403)
- **Dependabot** / GitHub security alerts enabled on repo
- **Django security announcements** mailing list subscription
- **Quarterly dependency updates** scheduled

## 7. Emergency Contacts

| Role | Contact |
|------|---------|
| Lead Developer | (update with contact info) |
| AWS Account Admin | (update with contact info) |
| Stripe Support | https://support.stripe.com |
| Django Security Team | security@djangoproject.com |
