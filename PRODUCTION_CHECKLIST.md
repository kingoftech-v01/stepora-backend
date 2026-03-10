# Stepora Production Checklist

Pre-launch checklist for moving from beta to general availability.
Items marked with [x] are already implemented. Items marked with [ ] need operational action.

---

## Security (Code-Level) — All Done

- [x] **Rate limiting** on all auth endpoints (login, register, password reset) — `AuthRateThrottle` at 5/min
- [x] **Account lockout** — 5 failed attempts locks IP + email for 15 minutes via Redis
- [x] **2FA enforcement at login** — Challenge token flow: credentials validated → signed challenge token issued → OTP verified → JWT tokens issued. No tokens leak before 2FA verification
- [x] **Backup code hashing** — PBKDF2 with 100k iterations (consistent across `two_factor.py` and `users/views.py`)
- [x] **SSRF prevention** — `validate_url_no_ssrf()` resolves DNS once and returns IP for connection pinning (prevents TOCTOU/DNS rebinding)
- [x] **CSP headers** — `frame-ancestors 'none'` on both frontend meta tag and backend `SecurityHeadersMiddleware`
- [x] **Clickjacking** — `X-Frame-Options: DENY` in production settings + middleware
- [x] **XSS** — DOMPurify with restricted `ALLOWED_TAGS` on frontend, `nh3` sanitizer on backend
- [x] **CORS** — `CORS_ALLOW_ALL_ORIGINS=False`, origins from env var, credentials allowed
- [x] **Cookie security** — `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `JWT_AUTH_SECURE` all True
- [x] **HSTS** — 1 year, includeSubDomains, preload
- [x] **Upload validation** — Type + size + magic byte checks on all file uploads, UUID filenames
- [x] **Django upload ceiling** — `DATA_UPLOAD_MAX_MEMORY_SIZE=110MB`, `FILE_UPLOAD_MAX_MEMORY_SIZE=10MB`
- [x] **Protected routes** — `/change-password` wrapped in `ProtectedRoute`
- [x] **Password reset throttle** — `AuthRateThrottle` wired to reset + confirm views
- [x] **Supply chain** — 0 npm audit vulnerabilities, gunicorn CVE-2024-1135 patched (>=22.0.0)
- [x] **DB SSL** — `sslmode=require` default in production settings
- [x] **Error redaction** — 5xx responses return generic message in production, full error logged server-side
- [x] **WebSocket auth** — Token in message body (not URL), JWT signature + expiry validated

---

## Infrastructure (Ops-Level) — Action Required Before GA

### Critical

- [ ] **Move FIELD_ENCRYPTION_KEY out of Dockerfile** — Currently passed as build ARG. Before GA, move to runtime-only via AWS Secrets Manager. Do NOT store the key in any committed file.
- [ ] **Rotate all secrets** — After beta, rotate: OpenAI API key, Stripe secret key, DB password, Redis password, Agora credentials, FIELD_ENCRYPTION_KEY, DJANGO_SECRET_KEY
- [ ] **Set `client_max_body_size` in nginx** — Set to `110m` to match Django's `DATA_UPLOAD_MAX_MEMORY_SIZE`

### High Priority

- [ ] **Django admin protection** — Restrict `/admin/` to VPN/IP whitelist in nginx, or add django-otp for admin 2FA
- [ ] **Set Sentry DSN** — Ensure `SENTRY_DSN` env var is set for production error tracking
- [ ] **Configure SMTP** — Set `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` to enable email verification (currently falls back to console backend with a warning)
- [ ] **Set `CORS_ORIGIN` env var** — Required for production CORS. If empty, all cross-origin requests are silently blocked

### Medium Priority

- [ ] **Fix export download URL** — `apps/users/tasks.py:export_user_data` uses string concat for URL instead of `default_storage.url()`. Won't work on S3. Quick fix needed when testing export feature
- [ ] **Add custom 500 view** — Django's default 500 handler returns HTML for unhandled exceptions. API clients should get JSON. Add `handler500` in `config/urls.py`
- [ ] **WebSocket token re-validation** — Long-lived WebSocket connections don't re-validate expired JWT. Consider periodic re-auth or connection timeouts (e.g., 1 hour max)
- [ ] **Migrate Google OAuth to PKCE** — Currently uses `response_type=token` (implicit flow). Authorization Code + PKCE is more secure

### Low Priority / Nice to Have

- [ ] **Add frontend test suite** — No Jest/Vitest/Cypress currently
- [ ] **Add ESLint/Prettier** — No linting configured
- [ ] **Agora RTM v2 migration** — Using legacy RTM v1.x SDK
- [ ] **Remove `unsafe-eval` from CSP** — Blocked by Agora SDK requirement

---

## Environment Variables Required in Production

```bash
# Django
DJANGO_SECRET_KEY=<generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
ALLOWED_HOSTS=api.stepora.app
DJANGO_SETTINGS_MODULE=config.settings.production

# Database
DB_NAME=stepora
DB_USER=stepora
DB_PASSWORD=<strong-password>
DB_HOST=<rds-endpoint>
DB_PORT=5432
DB_SSLMODE=require

# Redis
REDIS_URL=rediss://<redis-host>:6379/0

# CORS & CSRF
CORS_ORIGIN=https://stepora.app,https://app.stepora.app
CSRF_TRUSTED_ORIGINS=https://stepora.app,https://app.stepora.app

# Frontend
FRONTEND_URL=https://app.stepora.app

# Encryption
FIELD_ENCRYPTION_KEY=<base64-fernet-key>

# OpenAI
OPENAI_API_KEY=sk-...

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Agora
AGORA_APP_ID=<app-id>
AGORA_APP_CERTIFICATE=<certificate>

# Firebase
FIREBASE_CREDENTIALS_PATH=/app/firebase-service-account.json

# VAPID (Web Push)
VAPID_PUBLIC_KEY=<base64>
VAPID_PRIVATE_KEY=<base64>

# Email (SMTP)
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=noreply@stepora.app
EMAIL_HOST_PASSWORD=<app-password>

# Monitoring
SENTRY_DSN=https://<key>@sentry.io/<project>
```

---

Last updated: 2026-03-03
