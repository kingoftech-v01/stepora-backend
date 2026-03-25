# Stepora Backend — Security & Performance Fixes (2026-03-25)

## Overview
22 security vulnerabilities patched + 7 performance optimizations applied.
All fixes identified by automated security audit agents.

---

## CRITICAL Security Fixes

### 1. OAuth Audience Validation Bypass
- **Before**: Empty `GOOGLE_CLIENT_ID` / `APPLE_CLIENT_ID` caused `jwt.decode(audience="")` to accept ANY valid Google/Apple JWT token from any app
- **After**: Explicit guard raises `ValidationError` when client ID is not configured
- **Files**: `core/auth/social.py` (lines 142, 187)
- **Strategy**: Fail-hard on missing config instead of fail-open

### 2. 2FA Challenge No Lockout
- **Before**: `TwoFactorChallengeView` had no account lockout on failed TOTP attempts. Brute-force 6-digit codes was only limited by IP-based throttle (5/min)
- **After**: Calls `_check_lockout()` at start and `_record_failed_login()` on each failure, same as login endpoint
- **Files**: `core/auth/views.py` (lines 288, 340)
- **Strategy**: Reuse existing lockout infrastructure for all auth endpoints

### 3. Apple Redirect Unthrottled + Silent Errors
- **Before**: `AppleRedirectView` had no rate limiting and swallowed exceptions silently
- **After**: Added `AuthLoginRateThrottle`, exceptions logged with `logger.exception()`
- **Files**: `core/auth/views.py` (lines 845, 883)

### 4. TokenRefreshView Unthrottled
- **Before**: No rate limit on token refresh — stolen refresh token could generate unlimited access tokens
- **After**: Added `AuthLoginRateThrottle`
- **Files**: `core/auth/views.py` (line 551)

---

## HIGH Security Fixes

### 5. 2FA Setup Returns Raw TOTP Secret
- **Before**: API response included `secret` (raw Base32 seed) — interception = permanent 2FA compromise
- **After**: Only returns `otpauth_url` (which QR scanners need). Added `TwoFactorRateThrottle`
- **Files**: `apps/users/views.py` (line 1678)

### 6. 2FA Challenge Token Not IP-Bound
- **Before**: Challenge token contained only `user_id` + timestamp. Could be used from any IP
- **After**: Token includes SHA-256 hash of client IP. Verified on submission
- **Files**: `core/auth/views.py` (lines 105, 122-132)
- **Strategy**: Bind security tokens to originating context (IP + time)

### 7. X-Forwarded-For Spoofing
- **Before**: `_get_client_ip()` used first entry in XFF header (user-controllable)
- **After**: Uses last entry (appended by ALB, trustworthy)
- **Files**: `core/auth/views.py` (line 87)
- **Strategy**: Trust only proxy-appended entries, not client-supplied headers

### 8. Origin Validation Too Broad (10.0.0.0/8)
- **Before**: Any 10.x.x.x IP bypassed origin validation (entire AWS private range)
- **After**: Restricted to 10.0.x.x (VPC CIDR 10.0.0.0/16 only)
- **Files**: `core/middleware.py` (line 76)

### 9. SubscriptionPlanViewSet Throttle Disabled
- **Before**: `throttle_classes = []` explicitly disabled ALL throttling
- **After**: Removed override — inherits global defaults (anon: 20/min, user: 100/min)
- **Files**: `apps/subscriptions/views.py`

### 10. Stripe Webhook Secret Runtime Auto-Setup
- **Before**: Empty `STRIPE_WEBHOOK_SECRET` triggered runtime auto-setup via Stripe API — race condition in multi-process deployment
- **After**: Fails hard in production (non-DEBUG) with clear error. Returns 503 so Stripe retries
- **Files**: `apps/subscriptions/services.py`, `apps/subscriptions/views.py`

---

## MEDIUM Security Fixes

### 11. Content Moderation Fails Open
- **Before**: OpenAI API errors returned `ModerationResult(is_flagged=False)` — harmful content passed through
- **After**: Fails closed with `is_flagged=True, reason="moderation_service_unavailable"`. Also removed `"sk-placeholder"` fallback
- **Files**: `core/moderation.py` (lines 354-394)
- **Strategy**: Security-critical services must fail closed, not open

### 12. mark_all_read Deletes Notifications
- **Before**: `Notification.objects.filter(user=self.user).delete()` — permanently erased all notifications
- **After**: `.update(read_at=timezone.now())` — marks as read, preserves history
- **Files**: `apps/notifications/consumers.py` (lines 241-248)

### 13. WebSocket Unauthenticated Connection Window
- **Before**: Accepted connections stayed open indefinitely without auth — DoS vector
- **After**: 10-second auth timeout. Unauthenticated connections forcibly closed
- **Files**: `apps/notifications/consumers.py`, `apps/social/consumers.py`, `apps/circles/consumers.py`, `core/consumers.py`
- **Strategy**: All accepted connections must authenticate within bounded time

### 14. CSRF Cookie HttpOnly Blocks JS Access
- **Before**: `CSRF_COOKIE_HTTPONLY = True` prevented frontend from reading CSRF token
- **After**: Changed to `False` (Django default) so `api.js` can send `X-CSRFToken` header
- **Files**: `config/settings/base.py` (line 591)

### 15. Django Admin Publicly Accessible
- **Before**: `/admin/` accessible from any IP via ALB
- **After**: `AdminIPRestrictionMiddleware` restricts to localhost, VPC, and configurable `ADMIN_ALLOWED_IPS`
- **Files**: `core/middleware.py`, `config/settings/base.py`

### 16. Origin Validation Hardcoded
- **Before**: `ALLOWED_ORIGINS` manually maintained list separate from `CORS_ALLOWED_ORIGINS`
- **After**: Dynamically derived from `settings.CORS_ALLOWED_ORIGINS` + localhost fallbacks
- **Files**: `core/middleware.py`

---

## LOW Security Fixes

### 17. DreamTemplateViewSet No Throttle Scope
- **Before**: Public endpoint without specific throttle — ScopedRateThrottle ineffective
- **After**: Added `throttle_scope = "public"` + `"public": "30/minute"` rate
- **Files**: `apps/dreams/views.py`, `config/settings/base.py`

---

## Performance Fixes

### 18. N+1 Queries in Dream List Check-in Status
- **Before**: 2-3 extra DB queries PER DREAM for check-in status (has_pending, can_checkin, days_until)
- **After**: Prefetch active/latest checkins in DreamViewSet.get_queryset(). Serializer uses prefetched data
- **Files**: `apps/dreams/views.py`, `apps/dreams/serializers.py`
- **Impact**: Eliminates 30+ queries for user with 10 dreams

### 19. boto3 Client Per-Request
- **Before**: `get_signed_vision_image_url()` created new boto3 client per dream per request
- **After**: Module-level singleton via `_get_s3_client()` — one client reused across all requests
- **Files**: `apps/dreams/serializers.py`

### 20. Subscription Plan Not Cached
- **Before**: `get_active_plan()` hit DB on every API request via permission classes
- **After**: Redis cache with 5-min TTL + signal-based invalidation on subscription changes
- **Files**: `apps/users/models.py`, `apps/subscriptions/signals.py`

### 21. GoalSerializer Python Recomputation
- **Before**: `get_completed_tasks_count` iterated prefetched list in Python, ignoring existing DB annotations
- **After**: Checks for `_tasks_count`/`_completed_tasks_count` annotations first
- **Files**: `apps/dreams/serializers.py`

### 22. Missing Database Index
- **Before**: `ActivityFeedItem` queries (user + activity_type + date) did sequential scans
- **After**: Composite index on `(user, activity_type, -created_at)`
- **Files**: `apps/social/models.py` + new migration

### 23. Celery Result Accumulation
- **Before**: No `CELERY_RESULT_EXPIRES` — stale results fill Redis indefinitely
- **After**: 1-hour expiry
- **Files**: `config/settings/base.py`

### 24. Coverage Exclusions Hide Gaps
- **Before**: `*/tasks.py` and `*/consumers.py` excluded from coverage — hid real gaps
- **After**: Removed exclusions — all business logic measured
- **Files**: `pytest.ini`
