# Access Review Process

**Last updated:** 2026-03-26
**Owner:** Infrastructure / Security

## Scope

This process covers periodic review of all access credentials and permissions for the Stepora platform.

## Access Inventory

| System | Access Type | Who Has Access | Review Frequency |
|--------|------------|---------------|-----------------|
| AWS Console (987409845802) | IAM users/roles | DevOps | Quarterly |
| AWS Secrets Manager | Read via ECS task roles | ECS services only | Quarterly |
| GitHub repos (kingoftech-v01) | Repository collaborators | Development team | Quarterly |
| GitHub Actions secrets | CI/CD workflows | Automated only | Quarterly |
| RDS PostgreSQL | DB user via Secrets Manager | Backend services | Quarterly |
| Cloudflare DNS | API token / dashboard | DevOps | Quarterly |
| Stripe Dashboard | API keys in Secrets Manager | DevOps + Finance | Quarterly |
| Google Cloud Console | OAuth client credentials | DevOps | Quarterly |
| Apple Developer Portal | OAuth service ID | DevOps | Quarterly |
| OpenAI API | API key in Secrets Manager | Backend services | Quarterly |

## Quarterly Review Checklist

### AWS IAM
- [ ] List all IAM users: `aws iam list-users`
- [ ] Review each user's access keys: `aws iam list-access-keys --user-name <user>`
- [ ] Check for unused access keys (>90 days): `aws iam generate-credential-report`
- [ ] Review IAM policies attached to ECS task roles
- [ ] Verify no wildcard (`*`) resource permissions on sensitive actions
- [ ] Confirm MFA is enabled on all human IAM users

### GitHub
- [ ] Review repository collaborators and their permission levels
- [ ] Audit GitHub Actions secrets (remove unused)
- [ ] Verify PAT (Personal Access Token) expiration dates
- [ ] Review branch protection rules on `main` and `development`

### Application-Level
- [ ] Review Django admin superuser accounts: `python manage.py shell -c "from apps.users.models import User; print(User.objects.filter(is_superuser=True).values_list('email', flat=True))"`
- [ ] Audit active API tokens (if any legacy DRF tokens remain)
- [ ] Review third-party OAuth app registrations (Google, Apple)

### Secrets Rotation
- [ ] Check age of `DJANGO_SECRET_KEY` (rotate annually)
- [ ] Check age of `FIELD_ENCRYPTION_KEY` (rotate with data migration plan)
- [ ] Check age of database password (rotate quarterly)
- [ ] Verify Stripe API keys are current
- [ ] Verify VAPID keys are current

## Offboarding

When a team member leaves:
1. Remove from AWS IAM immediately
2. Remove from GitHub organization
3. Rotate any shared credentials they had access to
4. Remove from Cloudflare, Stripe, and other dashboards
5. See [OFFBOARDING_CHECKLIST.md](OFFBOARDING_CHECKLIST.md) for full procedure

## Audit Log

| Date | Reviewer | Findings | Actions Taken |
|------|----------|----------|--------------|
| 2026-03-26 | Initial | Document created | N/A |
