# Security Audit TODOs (batch 301-400)

Items that require frontend changes, policy updates, or infrastructure work
beyond what can be fixed in the backend codebase alone.

## Frontend TODOs

### V-336: Cookie Consent Banner
- **Priority:** HIGH
- **Location:** Frontend (`/root/stepora-frontend`)
- **Action:** Add a cookie consent banner/CMP before setting any non-essential cookies
- **Notes:** The app uses httpOnly cookies for JWT refresh tokens (essential, no consent needed). Google Fonts is the main non-essential item. Consider self-hosting Google Fonts to eliminate the need for consent.

### V-372-mobile: Mobile AsyncStorage Unencrypted Tokens
- **Priority:** HIGH
- **Location:** Mobile (`/root/stepora-mobile/src/services/api.js`)
- **Action:** Replace `AsyncStorage` with `react-native-keychain` or `expo-secure-store` for access/refresh token storage
- **Lines:** 83-94 in mobile `api.js`

### V-381: SRI on Google Fonts
- **Priority:** MEDIUM
- **Location:** Frontend `index.html`
- **Action:** Add `integrity` attribute to Google Fonts stylesheet link, or self-host the fonts
- **Alternative:** Self-host fonts (eliminates external CDN risk entirely)

### V-386: WebRTC IP Leak via Agora
- **Priority:** MEDIUM
- **Location:** Frontend `src/services/agora.js`
- **Action:** Configure ICE candidate policy to `relay` only if privacy is critical, or document in privacy policy that IPs may be shared with Agora
- **Notes:** Agora Cloud handles TURN relay automatically. IP leak is to Agora, not to other users.

### V-392: window.open Missing noopener
- **Priority:** MEDIUM
- **Location:** Frontend `src/services/native.js:150`
- **Action:** Change `window.open(url, '_blank')` to `window.open(url, '_blank', 'noopener,noreferrer')`
- **Notes:** Modern browsers (2021+) default to noopener, but explicit is best practice

## Privacy/Compliance TODOs

### V-340: Data Retention Policy Enforcement
- **Priority:** HIGH
- **Action:** Add Celery tasks to purge old data:
  - Notifications older than 90 days
  - Chat messages older than 1 year (or configurable)
  - Completed/abandoned dreams older than 2 years
  - Old audit logs
- **Location:** Backend `apps/*/tasks.py`

### V-342: CCPA "Do Not Sell" Mechanism
- **Priority:** HIGH (if targeting California users)
- **Action:** Add "Do Not Sell My Personal Information" link to privacy page and implement GPC signal handling
- **Notes:** Stepora does not sell data, so this is primarily a disclosure/link requirement

### V-344: Cross-Border Data Transfer Documentation
- **Priority:** HIGH
- **Action:** Document Standard Contractual Clauses (SCCs) with US-based processors:
  - OpenAI (AI coaching)
  - Stripe (payments)
  - Agora.io (voice/video)
  - Firebase/Google (push notifications, calendar)
- **Location:** Legal documentation, link from privacy policy

### V-350: User Activity Tracking Disclosure
- **Priority:** HIGH
- **Action:** Update privacy policy at stepora.net/privacy/ to explicitly disclose:
  - `LastActivityMiddleware` tracks last_seen and is_online status
  - AI usage tracking records feature usage counts
  - These are used for gamification (streaks, XP) and online status display

### V-313: Cache Stampede Protection
- **Priority:** MEDIUM
- **Action:** Add probabilistic early expiration or cache lock pattern for hot keys
- **Location:** Backend cache calls in `apps/users/models.py` (get_active_plan), etc.
