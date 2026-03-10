# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of DreamPlanner very seriously. If you discover a security vulnerability, please report it to us responsibly.

### How to Report

1. **Do not** create a public issue on GitHub
2. Send an email to **security@dreamplanner.app** with:
   - Detailed description of the vulnerability
   - Steps to reproduce the issue
   - Potential impact
   - Suggested fixes (if possible)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 7 days
- **Resolution**: Depending on severity (critical: 7 days, high: 14 days, medium: 30 days)

### Scope

The following vulnerabilities are within our scope:

- SQL Injection
- Cross-Site Scripting (XSS)
- Cross-Site Request Forgery (CSRF)
- Broken Authentication/Authorization
- Sensitive Data Exposure
- Security Misconfiguration
- Components with Known Vulnerabilities

### Out of Scope

- Denial of Service (DoS) attacks
- Spam or social engineering
- Issues on systems we do not control

## Implemented Security Measures

### Authentication & 2FA

- **JWT authentication** — Short-lived access tokens (memory-only on web), refresh tokens as httpOnly cookies
- **2FA enforcement at login** — Challenge token flow: credentials validated → signed challenge token issued (5min TTL, Django `signing.dumps`) → OTP verified → JWT tokens issued. No tokens leak before 2FA verification.
- **Account lockout** — 5 failed login attempts locks IP + email for 15 minutes via Redis
- **Rate limiting** — `AuthRateThrottle` at 5/min on login, register, password reset, and password reset confirm endpoints
- **Social auth** — Google Sign-In and Apple Sign-In via direct ID token verification (`core.auth.social`)

### Authorization

- Ownership verification on all resources
- 9 subscription-tier permission classes enforce limits across all endpoints
- Role-based permissions (owner, moderator, member) in circles

### Data Protection

- **Encryption in transit** — HTTPS/TLS enforced, HSTS with 1-year max-age, includeSubDomains, preload
- **Field encryption** — `django-encrypted-model-fields` (Fernet) for TOTP secrets and sensitive user data
- **Backup code hashing** — PBKDF2 with SHA-256, 100k iterations
- **XSS prevention** — DOMPurify with restricted `ALLOWED_TAGS` on frontend, `nh3` sanitizer on backend
- **Input validation** — DRF Serializers + custom validation (avatar magic bytes, notification schema whitelist, channel name regex, message length limits)
- **CORS** — `CORS_ALLOW_ALL_ORIGINS=False`, origins from env var, credentials allowed
- **CSRF** — `CSRF_TRUSTED_ORIGINS` configured, `X-CSRFToken` auto-attached on mutating requests

### Infrastructure Security

- **Security headers** — `SecurityHeadersMiddleware` sets CSP (`frame-ancestors 'none'`), `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, COOP, CORP
- **SSRF prevention** — `validate_url_no_ssrf()` resolves DNS once and returns IP for connection pinning (prevents TOCTOU/DNS rebinding)
- **Upload validation** — Type + size + magic byte checks on all file uploads, UUID filenames. Django-level ceilings: `DATA_UPLOAD_MAX_MEMORY_SIZE=110MB`, `FILE_UPLOAD_MAX_MEMORY_SIZE=10MB`
- **Cookie security** — `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `JWT_AUTH_SECURE` all True in production
- **DB SSL** — `sslmode=require` default in production
- **Error redaction** — 5xx responses return generic message in production, full error logged server-side
- **WebSocket auth** — Token in message body (not URL), JWT signature + expiry validated
- **Supply chain** — 0 npm audit vulnerabilities, gunicorn CVE-2024-1135 patched (>=22.0.0)
- **Logging** — Sentry for error tracking, structured logging with PII redaction

### Docker & Server Hardening

- **Read-only filesystem** — Nginx container runs with `read_only: true`
- **Resource limits** — PostgreSQL: 512M/1CPU, Redis: 256M/0.5CPU, ES: 512M/1CPU, Nginx: 128M/0.5CPU
- **Port isolation** — Internal services use `expose` (not `ports`); only nginx is port-mapped to localhost
- **UFW firewall** — Only ports 22 (SSH), 80 (HTTP/certbot), 443 (HTTPS) open
- **Fail2ban** — SSH (3 retries/2h ban), nginx-http-auth (5 retries), nginx-botsearch (3 retries/24h ban)

## Best Practices for Contributors

1. Never commit secrets or credentials
2. Use environment variables for all sensitive configuration
3. Validate all user input
4. Use parameterized queries (Django ORM)
5. Follow the principle of least privilege
6. Run `npm audit` and `pip-audit` before releases

## Acknowledgments

We thank all security researchers who help us improve DreamPlanner.
