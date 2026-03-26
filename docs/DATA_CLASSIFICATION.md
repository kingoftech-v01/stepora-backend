# Data Classification Policy

**Version:** 1.0
**Last Updated:** 2026-03-26

## 1. Purpose

This document classifies data processed by Stepora to ensure appropriate protection levels are applied based on sensitivity.

## 2. Classification Levels

| Level | Label | Description |
|-------|-------|-------------|
| **L4** | **Restricted** | Highly sensitive; breach causes severe harm. Encryption at rest + field-level encryption required. |
| **L3** | **Confidential** | Sensitive personal data; breach causes significant harm. Encryption at rest required. |
| **L2** | **Internal** | Internal operational data; not for public consumption. Standard DB protection. |
| **L1** | **Public** | Non-sensitive; safe for public access. |

## 3. Data Inventory

### L4 - Restricted

| Data | Storage | Protection |
|------|---------|------------|
| TOTP secrets | `users.User.totp_secret` | Fernet field encryption + DB encryption |
| Backup codes | `users.User.backup_codes` | PBKDF2 SHA-256 hashed (100k iterations) |
| Stripe customer IDs | `subscriptions.StripeCustomer` | DB encryption (RDS) |
| API keys / secrets | AWS Secrets Manager | Not in DB; injected as env vars |
| FIELD_ENCRYPTION_KEY | AWS Secrets Manager | Never logged or exposed |
| DJANGO_SECRET_KEY | AWS Secrets Manager | Never logged or exposed |

### L3 - Confidential

| Data | Storage | Protection |
|------|---------|------------|
| User email | `users.User.email` | DB encryption (RDS) |
| User password | `users.User.password` | Django PBKDF2 hash (never stored plaintext) |
| Display name | `users.User.display_name` | Fernet field encryption |
| Avatar URL | `users.User.avatar_url` | Fernet field encryption |
| Dream content | `dreams.Dream` fields | DB encryption (RDS) |
| Goal/task content | `dreams.Goal`, `dreams.Task` | DB encryption (RDS) |
| Journal entries | `dreams.JournalEntry` | DB encryption (RDS) |
| Chat messages | `messages.Message` | DB encryption (RDS) |
| Location data | `users.User` location fields | Input-validated, DB encryption |
| Social account UIDs | `core.auth.SocialAccount.uid` | DB encryption (RDS) |

### L2 - Internal

| Data | Storage | Protection |
|------|---------|------------|
| Subscription status | `subscriptions.Subscription` | Standard DB |
| Dream progress metrics | `dreams.Dream` progress fields | Standard DB |
| Notification preferences | `notifications.NotificationPreference` | Standard DB |
| Gamification scores | `gamification.*` models | Standard DB |
| Login events | `core.auth.LoginEvent` | Standard DB, 90-day retention |
| Audit logs | CloudWatch `/ecs/stepora-backend` | 30-day retention |
| Celery task results | Redis | In-memory, ephemeral |

### L1 - Public

| Data | Storage | Protection |
|------|---------|------------|
| Subscription plan names/prices | `subscriptions.SubscriptionPlan` | Public API |
| App version | Frontend build | Public |
| Privacy policy | stepora.net/privacy/ | Public |
| Terms of service | stepora.net/terms/ | Public |

## 4. Handling Requirements

| Level | Access Control | Logging | Backup | Disposal |
|-------|---------------|---------|--------|----------|
| **L4** | Need-to-know, field-level encryption | All access logged | Encrypted backups | Cryptographic erasure |
| **L3** | Authenticated users (own data only) | Bulk access logged | Encrypted backups | Soft delete + 30-day hard delete |
| **L2** | Authenticated users | Standard application logs | Regular backups | Standard deletion |
| **L1** | Public | Not required | Standard backups | Standard deletion |

## 5. Data Flow

```
User Input --> ALB (TLS) --> ECS Container --> RDS (encrypted, SSL)
                                           --> Redis (VPC-only)
                                           --> S3 (SSE, media uploads)
```

- All data in transit: TLS 1.2+
- All data at rest: RDS encryption, S3 SSE
- L4 data: additional Fernet field-level encryption
- Logs: CloudWatch (30-day retention), Sentry (PII redacted)

## 6. Third-Party Data Sharing

| Third Party | Data Shared | Purpose | Classification |
|-------------|------------|---------|----------------|
| Stripe | Email, subscription plan | Payment processing | L3 |
| OpenAI | Dream content (anonymized context) | AI coaching | L3 |
| Google | Email, name (OAuth) | Authentication | L3 |
| Apple | Email, name (OAuth) | Authentication | L3 |
| Firebase/FCM | Device tokens | Push notifications | L2 |
| Sentry | Error traces (PII redacted) | Error monitoring | L2 |
| AWS (S3) | Media uploads | File storage | L2-L3 |

## 7. Review

This classification is reviewed:
- When new data types are introduced
- When new third-party integrations are added
- Annually (minimum)
