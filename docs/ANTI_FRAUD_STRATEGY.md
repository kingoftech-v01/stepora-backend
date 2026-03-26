# Anti-Fraud Strategy

**V-1471, V-1472, V-1496, V-1499** | Last updated: 2026-03-26

## Current Defenses (already implemented)

| Layer | Mechanism | Location |
|-------|-----------|----------|
| **Rate limiting** | Per-endpoint throttles (auth, AI, subscription, etc.) | `core/throttles.py`, `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES` |
| **Account lockout** | 5 failed login attempts = 15-min lockout | `core/auth/views.py` |
| **New device alerts** | Email notification on login from unknown device/IP | `core/auth/tasks.py` |
| **Honeypot** | Hidden `website` field on registration rejects bots | `core/auth/serializers.py` (V-1476) |
| **Stripe Radar** | ML-based payment fraud detection | Stripe-side, automatic |
| **AI usage quotas** | Daily limits per subscription tier | `AIUsageTracker` |
| **Promotion guards** | `max_redemptions`, email conditions, audience targeting | `apps/subscriptions/services.py` |
| **Content moderation** | OpenAI moderation API + custom patterns | `core/moderation.py` |
| **Audit logging** | Security events logged with IP, user agent, timestamp | `core/audit.py` |

## Roadmap (prioritized)

### Phase 1: Quick Wins (next sprint)

1. **Chargeback webhook handling (V-1496)**
   - Handle `charge.dispute.created`, `charge.dispute.closed` Stripe webhooks
   - Auto-suspend account on open dispute
   - Track chargeback rate; alert if > 0.5%
   - Location: `apps/subscriptions/services.py` webhook handler

2. **Disposable email blocking (V-1479)**
   - Block registration from known disposable email domains
   - Use a maintained blocklist (e.g., `disposable-email-domains` package)
   - Location: `core/auth/serializers.py` `validate_email`

3. **Account cooling period (V-1489)**
   - After password reset: 24h restriction on email change and payment method updates
   - Store `last_password_reset_at` on User model
   - Check in relevant endpoints

### Phase 2: Enhanced Detection (Q2 2026)

4. **Credential stuffing detection (V-1499)**
   - Track failed login attempts by IP across all accounts
   - If single IP fails against multiple accounts in short window, block IP temporarily
   - Use Redis sorted sets with TTL for tracking

5. **Impossible travel detection (V-1484)**
   - Compare login IP geolocation with previous login
   - Flag if distance/time ratio implies impossible travel (> 500 km/h)
   - Require 2FA re-verification on suspicious logins

6. **Refund abuse tracking (V-1498)**
   - Track refund count per user
   - Flag accounts with > 2 refunds in 90 days
   - Require manual review for flagged accounts

### Phase 3: Advanced Measures (Q3 2026)

7. **Device fingerprinting (V-1474)**
   - Integrate FingerprintJS Pro or similar
   - Associate device fingerprints with accounts
   - Flag account sharing (same device, multiple accounts)

8. **CAPTCHA on critical flows (V-1477)**
   - Integrate Cloudflare Turnstile (privacy-friendly)
   - Apply to: registration, login (after 2 failures), password reset
   - Invisible challenge for good traffic, explicit for suspicious

9. **Transaction monitoring dashboard (V-1472)**
   - Admin dashboard showing subscription events, revenue, chargebacks
   - Anomaly alerts for unusual patterns (spike in signups, cancellations)

## Fraud Response Procedure

1. **Detection**: Automated alert or manual report
2. **Investigation**: Check audit logs (`core/audit.py`), Stripe dashboard, CloudWatch
3. **Action**:
   - Suspend account via Django admin (`is_active = False`)
   - Cancel Stripe subscription
   - Block IP if applicable (add to rate limit deny list)
4. **Documentation**: Log incident with evidence
5. **Prevention**: Update rules to prevent recurrence

## Metrics to Track

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Chargeback rate | < 0.5% | > 0.75% |
| Failed login rate (per IP) | Normal variance | > 50/hour from single IP |
| Registration rate | Normal variance | > 100/hour (bot attack) |
| Refund rate | < 5% | > 10% |
| Account takeover attempts | 0 | Any confirmed ATO |
