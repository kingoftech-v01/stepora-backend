# Offboarding & Access Revocation Checklist

**Last updated:** 2026-03-26
**Owner:** Engineering team
**Security audit reference:** V-598

---

## Purpose

This checklist ensures all access is revoked when a team member departs.
The process must be completed within **24 hours** of departure notification.

---

## Checklist

### 1. AWS Access

- [ ] Delete or deactivate IAM user account
- [ ] Revoke any active access keys
- [ ] Remove from any IAM groups
- [ ] Verify no inline policies remain
- [ ] Check for and remove any assumed role sessions
- [ ] Review CloudTrail for recent activity by the departing user

### 2. GitHub Access

- [ ] Remove from `kingoftech-v01` organization
- [ ] Remove from all repository teams:
  - [ ] `stepora-backend`
  - [ ] `stepora-frontend`
  - [ ] `stepora-site`
- [ ] Revoke any personal access tokens (PATs) if known
- [ ] Review and remove from any GitHub Actions secrets access
- [ ] Remove any deploy keys they created

### 3. VPS / Server Access

- [ ] Remove SSH public key from `~/.ssh/authorized_keys` on all servers
- [ ] Remove user account from VPS (if individual accounts exist)
- [ ] Change any shared passwords they had access to
- [ ] Revoke VPN access (if applicable)

### 4. Application Admin Access

- [ ] Deactivate Django admin account (`is_staff=False`, `is_superuser=False`)
- [ ] Remove from Wagtail admin (stepora-site)
- [ ] Review and revoke any API tokens they created

### 5. Third-Party Services

- [ ] **Cloudflare**: Remove from account / change API tokens they accessed
- [ ] **Stripe**: Remove from Stripe Dashboard team
- [ ] **Sentry**: Remove from Sentry organization
- [ ] **OpenAI**: Rotate API key if they had direct access
- [ ] **Agora**: Rotate App Certificate if they had access
- [ ] **Google Cloud Console**: Remove from project (Calendar OAuth)
- [ ] **Firebase**: Remove from Firebase Console project

### 6. Communication & Tools

- [ ] Remove from team Slack/Discord channels
- [ ] Remove from project management tools (Jira, Linear, Notion, etc.)
- [ ] Revoke access to shared email accounts
- [ ] Remove from any shared password managers (1Password, Bitwarden)

### 7. Secrets Rotation (if departing member had access)

If the team member had access to production secrets, rotate them within 7 days:

- [ ] `DJANGO_SECRET_KEY` (invalidates sessions)
- [ ] `DB_PASSWORD` (update RDS + Secrets Manager + deploy)
- [ ] `FIELD_ENCRYPTION_KEY` (requires data migration -- plan carefully)
- [ ] AWS IAM access keys used in CI/CD (generate new, update GitHub Secrets)
- [ ] Any API keys they directly accessed

See `docs/INCIDENT_RESPONSE.md` for detailed rotation procedures.

### 8. Knowledge Transfer

- [ ] Document any in-progress work
- [ ] Transfer ownership of any open PRs
- [ ] Update on-call rotation
- [ ] Ensure deployment procedures are documented for remaining team

---

## Verification

After completing the checklist:

1. **Verify AWS access revoked**: Attempt to authenticate with former credentials.
2. **Verify GitHub access revoked**: Check organization members list.
3. **Verify VPS access revoked**: Check SSH authorized_keys on all servers.
4. **Document completion**: Record the date and who performed the offboarding.

---

## Record of Offboardings

| Date | Team Member | Completed By | Notes |
|------|-------------|--------------|-------|
| | | | |
