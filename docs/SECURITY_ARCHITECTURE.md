# Stepora Security Architecture

**Last updated:** 2026-03-26
**Status:** Living document — update on every security-relevant change.

---

## 1. Trust Boundaries

```
[Users]
   |
   | HTTPS (TLS 1.2+, HSTS 1yr, preload)
   v
[CloudFront CDN] ---- stepora.app (SPA, OAC to S3)
   |
   | HTTPS (ACM cert)
   v
[ALB] ---- host-based routing
   |
   +-- api.stepora.app --> [ECS Fargate: backend (Daphne ASGI)]
   |                            |
   |                            +-- [PgBouncer sidecar] --> [RDS PostgreSQL 15]
   |                            +-- [ElastiCache Redis]
   |                            +-- [S3 stepora-media-eu]
   |
   +-- stepora.net --> [ECS Fargate: site vitrine (Gunicorn)]
```

### External Trust Boundaries
- **Client <-> CDN/ALB**: TLS termination. HSTS enforced.
- **ALB <-> ECS**: Internal VPC traffic. ALB is the security boundary for `ALLOWED_HOSTS`.
- **ECS <-> RDS**: TLS (`sslmode=require`), connection pooled via PgBouncer sidecar.
- **ECS <-> Redis**: VPC-internal (no TLS, accepted risk — ElastiCache in same VPC).
- **ECS <-> S3**: IAM role-based access (task execution role).
- **ECS <-> External APIs**: Stripe (webhook signature verification), Agora (token-based), OpenAI (API key).

---

## 2. Authentication & Authorization

### Authentication Flow
- **Custom auth package**: `core.auth` (no allauth/dj-rest-auth dependency).
- **JWT via SimpleJWT**: Access token (short-lived) + Refresh token.
  - **Web**: Refresh token in httpOnly, Secure, SameSite=None cookie.
  - **Native (mobile)**: Both tokens in response body (detected via `X-Client-Platform: native` header).
- **Social auth**: Google, Apple sign-in via `core.auth.social`.
- **Email verification**: Required before full access. Celery task sends verification email.
- **Password reset**: UID~token format (tilde separator, not dash — UID contains dashes).

### Authorization
- **Default permission**: `IsAuthenticated` (all endpoints require auth unless explicitly public).
- **Object-level**: Ownership validation via `perform_create()` on Goal/Task/Milestone/Obstacle viewsets.
- **Subscription gating**: `SubscriptionPermission` checks tier for premium features. Returns `subscription_required` error code.
- **Admin**: `IsAdminUser` for schema endpoint, custom admin path (`stepora-manage/`).

### Rate Limiting
| Scope | Limit |
|-------|-------|
| `auth` (login) | 5/minute |
| `auth_register` | 5/minute |
| `auth_password` | 5/minute |
| `upload` | 10/minute |
| `check_in` | 10/minute |
| Default (anon) | 30/minute |
| Default (user) | 120/minute |

- `NUM_PROXIES = 1` prevents X-Forwarded-For spoofing.

---

## 3. Data Protection

### Encryption at Rest
- **RDS**: AWS-managed encryption (AES-256).
- **S3**: Server-side encryption (SSE-S3).
- **Sensitive fields**: `FIELD_ENCRYPTION_KEY` for encrypted model fields.

### Encryption in Transit
- **All external**: TLS 1.2+ (HSTS with preload).
- **DB connections**: `sslmode=require`.
- **Internal (VPC)**: Unencrypted Redis (accepted — same VPC, no public access).

### Secrets Management
- **AWS Secrets Manager**: All production secrets (`stepora/backend-env`).
- **No secrets in code**: `.gitignore` excludes `.env` files. CI/CD injects secrets.
- **Exception**: Agora App ID was hardcoded in mobile (fixed 2026-03-26 — moved to config).

### PII Handling
- **Sentry**: `send_default_pii=False`.
- **Logs**: WARNING level in production (no user data in logs).
- **API responses**: JSON only (`JSONRenderer`), no HTML error pages.

---

## 4. Input Validation & Output Encoding

### Input
- **DRF serializers**: Type validation, field-level validators.
- **File uploads**: Content-type whitelist + magic byte validation (`apps/social/validators.py`).
- **Text input**: `sanitizeText()` utility on frontend/mobile.
- **SQL injection**: ORM-only queries (no raw SQL).

### Output
- **XSS prevention**: React auto-escapes, `SECURE_BROWSER_XSS_FILTER = True`.
- **Content-Type**: `SECURE_CONTENT_TYPE_NOSNIFF = True`.
- **Clickjacking**: `X_FRAME_OPTIONS = "DENY"`.
- **CORS**: Strict origin list (not `ALLOW_ALL_ORIGINS`).

---

## 5. Session Management

- **Access token**: Short-lived JWT (in-memory on web, AsyncStorage on mobile).
- **Refresh token**: httpOnly cookie (web) / AsyncStorage (mobile).
- **Session backend**: Redis (`django.contrib.sessions.backends.cache`).
- **Cookie flags**: `Secure=True`, `SameSite=Lax` (session), `SameSite=None` (JWT cross-origin).
- **Token refresh**: Silent refresh with queue to prevent concurrent refresh races.

### Mobile-Specific
- **AsyncStorage**: Unencrypted. TODO: Migrate to react-native-keychain.
- **Biometric auth**: Local UI gate only (not cryptographic). TODO: Migrate to signed challenges.

---

## 6. Mobile Security

### Android
- **Certificate pinning**: `network_security_config.xml` with SHA-256 pins for `api.stepora.app`.
- **No cleartext**: `cleartextTrafficPermitted="false"`.
- **ProGuard/R8**: Code obfuscation in release builds.

### iOS
- **ATS**: App Transport Security enforces HTTPS.
- **Certificate pinning**: TODO — not yet implemented for iOS.
- **Root/jailbreak detection**: TODO — not yet implemented.

### Production Logging
- All `console.log/warn/error` calls wrapped in `__DEV__` guard via `utils/logger.js`.
- Zero console output in release builds.

---

## 7. Third-Party Integrations

| Service | Auth Method | Data Shared |
|---------|-------------|-------------|
| Stripe | API key + webhook signature | Payment data, customer ID |
| Agora | App ID + token (server-generated) | Channel ID, UID |
| OpenAI | API key | Dream text (for AI coaching) |
| Google Calendar | OAuth 2.0 | Calendar events |
| Firebase (FCM) | Service account | Push notification tokens |
| Sentry | DSN | Error reports (no PII) |

---

## 8. Infrastructure Security

- **ECS Fargate**: No SSH access, no host OS management.
- **ECS Exec**: Requires `ssmmessages:*` IAM permissions (4 actions).
- **RDS**: Private subnet, security group restricts to ECS tasks only.
- **S3 (frontend)**: OAC (Origin Access Control) — no public bucket access.
- **S3 (media)**: Signed URLs for private uploads.
- **CloudFront**: Custom error responses (403/404 -> /index.html for SPA routing).
- **No NAT Gateway**: ECS tasks in public subnets with `assignPublicIp=ENABLED`.

---

## 9. CI/CD Security

- **Branch protection**: `main` requires PR review. Deploy guard on `main` only.
- **Secrets**: GitHub repository secrets (never in code).
- **Container images**: Unique ECR tags per deploy (no `:latest` caching issues).
- **Entrypoint**: `migrate --noinput` runs before app starts.
- **No `--no-verify`**: Git hooks are never skipped.

---

## 10. Known Risks & Accepted Trade-offs

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| Redis unencrypted (VPC-internal) | LOW | Same VPC, security groups | Accepted |
| AsyncStorage tokens (mobile) | HIGH | Migrate to react-native-keychain | TODO |
| No iOS cert pinning | MEDIUM | ATS enforces HTTPS; add TrustKit | TODO |
| No root/jailbreak detection | MEDIUM | Add jail-monkey or Play Integrity | TODO |
| Biometric auth not cryptographic | MEDIUM | Migrate to signed challenges | TODO |
| `ALLOWED_HOSTS=*` in ECS | LOW | ALB is security boundary | Accepted |

---

## 11. Vulnerability Disclosure

- **Contact**: security@stepora.app
- **security.txt**: `https://stepora.app/.well-known/security.txt`
- **Response SLA**: Acknowledge within 48h, assess within 7 business days.
- **Disclosure policy**: 90-day coordinated disclosure.
