# Record of Processing Activities (ROPA)

**Controller:** Stepora SAS
**Last Updated:** 2026-03-26
**DPO Contact:** privacy@stepora.app

---

## 1. Account Registration & Authentication

| Field | Value |
|-------|-------|
| **Purpose** | Create and authenticate user accounts |
| **Legal Basis** | Contract performance (Art. 6(1)(b) GDPR) |
| **Categories of Data Subjects** | Registered users |
| **Personal Data Collected** | Email address, hashed password, display name, IP address (login logs) |
| **Retention Period** | Active account lifetime + 30 days post-deletion |
| **Recipients** | Internal systems only |
| **Third-Party Processors** | Google (social login), Apple (social login) |
| **Transfer Outside EU** | Google/Apple (US) -- Standard Contractual Clauses |
| **Technical Measures** | Bcrypt password hashing, field-level AES encryption (display_name, bio, location), JWT with short-lived access tokens, httpOnly refresh cookies |

## 2. User Profile

| Field | Value |
|-------|-------|
| **Purpose** | Personalize user experience and enable social features |
| **Legal Basis** | Contract performance (Art. 6(1)(b) GDPR) |
| **Categories of Data Subjects** | Registered users |
| **Personal Data Collected** | Display name, avatar, bio, location, social links, timezone, theme preferences |
| **Retention Period** | Active account lifetime; anonymized on soft-delete |
| **Recipients** | Other users (based on profile_visibility setting) |
| **Third-Party Processors** | AWS S3 (avatar storage) |
| **Transfer Outside EU** | AWS eu-west-3 (Paris) -- data stays in EU |
| **Technical Measures** | Encrypted fields (display_name, bio, location, avatar_url), user-controlled visibility settings |

## 3. Dream & Goal Management

| Field | Value |
|-------|-------|
| **Purpose** | Core service: help users plan and track personal goals |
| **Legal Basis** | Contract performance (Art. 6(1)(b) GDPR) |
| **Categories of Data Subjects** | Registered users |
| **Personal Data Collected** | Dream titles, descriptions, goals, tasks, milestones, obstacles, progress data |
| **Retention Period** | Active account lifetime; deleted on hard-delete (CASCADE) |
| **Recipients** | AI service (for plan generation), circle members (if shared) |
| **Third-Party Processors** | OpenAI (AI coaching), AWS RDS (storage) |
| **Transfer Outside EU** | OpenAI (US) -- Data Processing Agreement in place |
| **Technical Measures** | User-scoped queries (ownership validation on all viewsets), encrypted sensitive fields |

## 4. AI Coaching Conversations

| Field | Value |
|-------|-------|
| **Purpose** | AI-powered coaching, plan generation, and motivational support |
| **Legal Basis** | Contract performance (Art. 6(1)(b) GDPR) |
| **Categories of Data Subjects** | Premium/Pro subscribers |
| **Personal Data Collected** | Conversation messages, AI responses, chat memories, user persona data |
| **Retention Period** | Active account lifetime; deleted on hard-delete |
| **Recipients** | OpenAI API (for generating responses) |
| **Third-Party Processors** | OpenAI |
| **Transfer Outside EU** | OpenAI (US) -- DPA, data not used for training (API ToS) |
| **Technical Measures** | Content moderation (input/output), AI output safety validation, rate limiting, usage quotas |

## 5. Payment & Subscription

| Field | Value |
|-------|-------|
| **Purpose** | Process subscription payments and manage billing |
| **Legal Basis** | Contract performance (Art. 6(1)(b) GDPR) |
| **Categories of Data Subjects** | Paying subscribers |
| **Personal Data Collected** | Stripe customer ID, subscription status, plan type. Card details are NOT stored -- handled by Stripe |
| **Retention Period** | Active subscription + legal retention requirements (6 years for financial records) |
| **Recipients** | Stripe |
| **Third-Party Processors** | Stripe Inc. |
| **Transfer Outside EU** | Stripe (US/EU) -- SCCs in place, PCI-DSS certified |
| **Technical Measures** | Webhook signature verification, server-side session creation (no client-side card input) |

## 6. Push Notifications & Email

| Field | Value |
|-------|-------|
| **Purpose** | Send reminders, progress updates, and system notifications |
| **Legal Basis** | Legitimate interest (Art. 6(1)(f) GDPR) for system notifications; Consent for marketing |
| **Categories of Data Subjects** | Registered users |
| **Personal Data Collected** | FCM device tokens, VAPID push subscriptions, email address, notification preferences |
| **Retention Period** | Active account lifetime |
| **Recipients** | Firebase Cloud Messaging, SMTP provider |
| **Third-Party Processors** | Google Firebase (FCM), Email provider (Hostinger SMTP) |
| **Transfer Outside EU** | Firebase (US) -- Google DPA |
| **Technical Measures** | User-controlled notification preferences, rate limiting on notification triggers |

## 7. Voice/Video Calls

| Field | Value |
|-------|-------|
| **Purpose** | Enable voice/video calls between accountability buddies |
| **Legal Basis** | Contract performance (Art. 6(1)(b) GDPR) |
| **Categories of Data Subjects** | Users with buddy pairings |
| **Personal Data Collected** | Agora channel tokens, call metadata (duration, status). Audio/video is peer-to-peer, not recorded |
| **Retention Period** | Call metadata: 30 days. Media: not stored |
| **Recipients** | Agora.io (RTC relay) |
| **Third-Party Processors** | Agora.io |
| **Transfer Outside EU** | Agora (US/Global) -- DPA required |
| **Technical Measures** | Short-lived tokens (24h), permission-based access, camera/microphone restricted to same-origin |

## 8. Calendar & Scheduling

| Field | Value |
|-------|-------|
| **Purpose** | Sync tasks with external calendars and schedule reminders |
| **Legal Basis** | Consent (Art. 6(1)(a) GDPR) -- user explicitly connects calendar |
| **Categories of Data Subjects** | Users who connect Google Calendar |
| **Personal Data Collected** | Calendar event titles, times, Google Calendar OAuth tokens |
| **Retention Period** | Until user disconnects calendar or deletes account |
| **Recipients** | Google Calendar API |
| **Third-Party Processors** | Google |
| **Transfer Outside EU** | Google (US) -- SCCs |
| **Technical Measures** | OAuth2 with minimal scopes, encrypted token storage, user-initiated connection only |

## 9. Social Features (Feed, Stories, Circles)

| Field | Value |
|-------|-------|
| **Purpose** | Enable community features: posts, stories, comments, circles |
| **Legal Basis** | Contract performance (Art. 6(1)(b) GDPR) |
| **Categories of Data Subjects** | Users who engage with social features |
| **Personal Data Collected** | Posts, comments, reactions, stories (images/video), circle memberships |
| **Retention Period** | Stories: 24 hours. Posts/comments: active account lifetime |
| **Recipients** | Other users (based on visibility settings) |
| **Third-Party Processors** | AWS S3 (media storage) |
| **Transfer Outside EU** | AWS eu-west-3 (Paris) -- data stays in EU |
| **Technical Measures** | Content moderation, file validation (MIME + magic bytes), ownership-scoped queries |

## 10. Activity Tracking & Gamification

| Field | Value |
|-------|-------|
| **Purpose** | Track user engagement for gamification (XP, streaks, leagues) and online status |
| **Legal Basis** | Legitimate interest (Art. 6(1)(f) GDPR) -- essential for service value proposition |
| **Categories of Data Subjects** | Registered users |
| **Personal Data Collected** | last_seen, is_online, last_activity, XP, level, streak data, daily activity logs |
| **Retention Period** | Active account lifetime |
| **Recipients** | Other users (online status visible to friends/buddies) |
| **Third-Party Processors** | None (stored in own DB) |
| **Transfer Outside EU** | No |
| **Technical Measures** | Throttled updates (max once per 60s), user-scoped data |

---

## Data Subject Rights Implementation

| Right | Implementation |
|-------|---------------|
| **Access (Art. 15)** | `GET /api/v1/users/export-data/` -- JSON/CSV export |
| **Rectification (Art. 16)** | `PATCH /api/v1/users/me/` -- self-service profile updates |
| **Erasure (Art. 17)** | `POST /api/v1/users/delete-account/` -- soft-delete + 30-day hard-delete |
| **Portability (Art. 20)** | `GET /api/v1/users/export-data/?export_format=csv` |
| **Restriction** | Contact privacy@stepora.app |
| **Objection** | Contact privacy@stepora.app |

## Third-Party Sub-Processors Summary

| Processor | Data Shared | Purpose | Location | Safeguards |
|-----------|------------|---------|----------|------------|
| AWS (RDS, S3, ElastiCache) | All application data | Infrastructure | eu-west-3 (Paris) | EU data residency |
| OpenAI | Conversation messages, dream data | AI coaching | US | DPA, no training on API data |
| Stripe | Customer ID, subscription data | Payments | US/EU | PCI-DSS, SCCs |
| Google | Email, name (social login), calendar data | Auth, calendar | US | SCCs, Google DPA |
| Apple | Email, name (social login) | Auth | US | Apple DPA |
| Agora.io | Call channel tokens | Voice/video calls | US/Global | DPA required |
| Firebase/Google | Device tokens | Push notifications | US | Google DPA |
