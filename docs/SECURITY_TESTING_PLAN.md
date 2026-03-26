# Security Testing Plan

**Last updated:** 2026-03-26
**Owner:** Development / Security

## Overview

This document defines the security testing strategy for Stepora across all three repositories (backend, frontend, mobile).

## Testing Layers

### 1. Pre-Commit (Developer Machine)

| Tool | Purpose | Config |
|------|---------|--------|
| detect-secrets | Prevent secret commits | `.pre-commit-config.yaml` |
| gitleaks | Scan git history for leaked secrets | `.pre-commit-config.yaml` |
| bandit | Python SAST (security-focused linting) | `.pre-commit-config.yaml` |

**Setup:**
```bash
pip install pre-commit
pre-commit install
```

### 2. CI Pipeline (Automated on Every PR)

#### Backend (`django-ci.yml`)

| Stage | Tool | Addresses |
|-------|------|-----------|
| SAST | bandit | Code-level vulnerabilities (SQLi, command injection, etc.) |
| SCA | pip-audit | Known CVEs in Python dependencies |
| Secrets | detect-secrets | Leaked credentials in code |
| Unit tests | pytest (tests_security_integration.py) | Auth flows, IDOR, rate limiting |

**Recommended CI additions:**
```yaml
- name: Security - pip-audit
  run: pip install pip-audit && pip-audit -r requirements/production.txt

- name: Security - bandit
  run: pip install bandit && bandit -r . -ll -x tests/,*/tests/,*/test_*

- name: Security - detect-secrets
  run: pip install detect-secrets && detect-secrets scan --baseline .secrets.baseline
```

#### Frontend (`deploy-frontend.yml`)

| Stage | Tool | Addresses |
|-------|------|-----------|
| SCA | npm audit | Known CVEs in npm dependencies |

```yaml
- name: Security - npm audit
  run: npm audit --audit-level=high
```

### 3. Pre-Deploy (CI on merge to main)

| Tool | Purpose | Addresses |
|------|---------|-----------|
| Trivy | Container image scanning | CVEs in OS packages, Python libs |

```yaml
- name: Scan Docker image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ steps.login-ecr.outputs.registry }}/stepora/backend:${{ github.sha }}
    format: 'table'
    exit-code: '1'
    severity: 'CRITICAL,HIGH'
```

### 4. Periodic Security Testing

| Frequency | Activity | Tool/Method |
|-----------|----------|-------------|
| Weekly | Dependency vulnerability scan | Dependabot or pip-audit cron |
| Monthly | OWASP ZAP baseline scan against staging | OWASP ZAP Docker |
| Quarterly | Manual penetration test of auth flows | Manual review |
| Quarterly | Review of AWS IAM roles and permissions | AWS Console / CLI |
| Annually | Full third-party security audit | External consultant |

### 5. Existing Security Test Coverage

**File:** `tests/tests_security_integration.py`

Covers:
- Token expiry and refresh
- CSRF enforcement
- Object ownership (IDOR prevention)
- Rate limiting on auth endpoints
- Account lockout after failed logins
- 2FA challenge flow
- Password reset flow

**Gaps to address:**
- [ ] OWASP API Top 10 comprehensive tests
- [ ] Mass assignment testing
- [ ] Security header snapshot tests (CSP, CORS, HSTS)
- [ ] Input validation fuzzing on auth endpoints

## Security Regression Testing

Every security bug fix MUST include a regression test:

1. Write a test that reproduces the vulnerability
2. Verify the test fails without the fix
3. Apply the fix and verify the test passes
4. Add the test to `tests/tests_security_integration.py`
5. Reference the vulnerability ID in the test docstring

## OWASP API Top 10 Coverage

| # | Risk | Status |
|---|------|--------|
| API1 | Broken Object-Level Authorization | Tested (IDOR fixes + tests) |
| API2 | Broken Authentication | Tested (lockout, 2FA, token lifecycle) |
| API3 | Broken Object Property Level Authorization | Partial (serializer field control) |
| API4 | Unrestricted Resource Consumption | Partial (rate limiting configured) |
| API5 | Broken Function Level Authorization | Tested (IsOwner permissions) |
| API6 | Unrestricted Access to Sensitive Business Flows | Partial |
| API7 | Server-Side Request Forgery | Not tested |
| API8 | Security Misconfiguration | Partial (security headers middleware) |
| API9 | Improper Inventory Management | OpenAPI schema generated |
| API10 | Unsafe Consumption of APIs | Partial (token verification on social login) |

## Responsible Disclosure

Security issues found during testing should be documented in a private channel and never committed to public repositories.
