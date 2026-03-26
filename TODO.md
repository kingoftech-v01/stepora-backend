# Stepora Backend — TODO

Feature ideas, improvements, and technical debt for the Stepora backend.

---

## High Priority

- [ ] **Migrate to PKCE OAuth** — Replace Google implicit flow (`response_type=token`) with Authorization Code + PKCE for stronger security. Also add OIDC nonce validation to `verify_google_token()` and `verify_apple_token()` in `core/auth/social.py` (audit #902, #903, #909)
- [ ] **DNSSEC verification** — Verify DNSSEC is enabled for both `stepora.app` and `stepora.net` zones in Cloudflare dashboard. Both zones should show DS records published to registrar (audit #950)
- [ ] **CSP Trusted Types** — Add `require-trusted-types-for 'script'` to CSP once frontend DOM manipulation is audited for compatibility. Defense-in-depth against DOM XSS (audit #960)
- [ ] **CSP nonce-based styles** — `style-src 'unsafe-inline'` is required due to widespread inline styles in the frontend (React inline styles, MUI). Migrating to nonce-based style CSP would require a server-rendered nonce injected into the SPA — not feasible with static S3 hosting (audit #961)
- [ ] **CSP violation reporting** — Add `report-uri` or `report-to` directive to CSP for monitoring policy violations. Consider using a service like report-uri.com or Sentry CSP reporting (audit #961)
- [ ] **Admin 2FA** — Add django-otp or IP whitelist for `/admin/` access in production
- [ ] **WebSocket token re-validation** — Long-lived WebSocket connections should re-validate JWT periodically (e.g., 1-hour max session or periodic re-auth ping)
- [ ] **Custom 500 JSON handler** — Django's default 500 handler returns HTML; API clients should receive JSON. Add `handler500` in `config/urls.py`
- [ ] **S3 media storage** — Migrate avatar, voice message, and vision board uploads to S3 with signed URLs for production scalability
- [ ] **Fix export download URL** — `apps/users/tasks.py:export_user_data` uses string concat instead of `default_storage.url()` — breaks on S3

## Features

- [ ] **AI conversation memory** — Implement long-term memory across conversations using embedding-based retrieval (RAG) so the AI coach remembers past interactions
- [ ] **Smart goal suggestions** — AI-powered goal suggestions based on user's dream description, past completed dreams, and industry benchmarks
- [ ] **Weekly progress email** — Automated weekly digest email with dream progress, streak status, upcoming tasks, and motivational content
- [ ] **Multi-language AI responses** — Detect user's language preference and instruct GPT-4 to respond in that language
- [ ] **Dream analytics dashboard** — Backend endpoints for time-series progress data, completion velocity, category breakdown, and prediction of completion date
- [ ] **Collaborative dream editing** — Real-time collaborative editing of shared dreams using operational transforms or CRDTs
- [ ] **API versioning** — Implement `/api/v2/` with proper versioning strategy for breaking changes
- [ ] **GraphQL endpoint** — Optional GraphQL API for mobile clients to reduce over-fetching (especially for social feed and dream detail)
- [ ] **Webhook system** — Allow users to configure webhooks for dream completions, achievement unlocks, and buddy events (useful for Zapier/IFTTT integrations)
- [ ] **Export to calendar** — One-click export of all dream tasks to Google Calendar or as .ics file

## Performance

- [ ] **Database read replicas** — Route read-heavy queries (leaderboards, feeds, search) to read replicas
- [ ] **Celery priority queues** — Separate high-priority (notifications, calls) from low-priority (analytics, cleanup) Celery tasks
- [ ] **Redis Cluster** — Migrate from single Redis to Redis Cluster for cache, channels, and Celery broker separation
- [ ] **Connection pooling** — Add PgBouncer for database connection pooling in production
- [ ] **Query monitoring** — Add django-silk or django-debug-toolbar profiling for slow query detection

## Testing

- [ ] **Load testing** — k6 or Locust load test suite for API endpoints and WebSocket connections
- [ ] **Contract testing** — Pact contract tests between frontend and backend API
- [ ] **E2E API tests** — Full flow tests (register → create dream → calibrate → generate plan → complete tasks)
- [ ] **WebSocket integration tests** — Automated tests for all 4 WebSocket consumers with concurrent connections

## DevOps

- [ ] **Blue/green deployment** — Zero-downtime deployment strategy with health check verification
- [ ] **Auto-scaling** — ECS auto-scaling policies based on CPU/memory and WebSocket connection count
- [ ] **Log aggregation** — Centralized logging with ELK stack or CloudWatch Logs Insights
- [ ] **Database migrations CI** — Automated migration testing in CI pipeline to catch issues before deploy
- [ ] **Dependency update automation** — Dependabot or Renovate for automated dependency updates with security alerts
