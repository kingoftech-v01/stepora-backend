# Users App

Core user management for Stepora. Handles profiles, preferences, gamification,
2FA, onboarding, AI-powered features, and GDPR-compliant account lifecycle.

## Models

| Model | Table | Description |
|-------|-------|-------------|
| `User` | `users` | Custom user model (UUID PK, email auth). Encrypted fields: `display_name`, `avatar_url`, `bio`, `location`, `totp_secret`. |
| `EmailChangeRequest` | `email_change_requests` | Pending email-change tokens with 24-hour expiry. |
| Re-exports | -- | `GamificationProfile`, `Achievement`, `UserAchievement`, `DailyActivity`, `HabitChain` re-exported from `apps.gamification.models`. |

### Key User fields

- **Auth**: `email`, `password`, `totp_enabled`, `totp_secret`, `backup_codes`
- **Profile**: `display_name`, `avatar_url`, `avatar_image`, `bio`, `location`, `social_links`, `profile_visibility`
- **Preferences**: `timezone`, `theme_mode`, `accent_color`, `work_schedule`, `notification_prefs`, `app_prefs`, `calendar_preferences`, `energy_profile`, `notification_timing`
- **AI personalization**: `persona` (JSON with hours, schedule, motivation, constraints)
- **Gamification**: `xp`, `level`, `streak_days`, `longest_streak`, `streak_updated_at`, `streak_freeze_used_at`
- **Subscription**: `subscription` (denormalized CharField), `subscription_ends`
- **Onboarding**: `onboarding_completed`, `dreamer_type`
- **Lifecycle**: `is_active`, `deactivated_at`, `created_at`, `updated_at`

## API Endpoints

Base path: `/api/users/`

### Profile and Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/me/` | Current user's full profile |
| PUT/PATCH | `/update_profile/` | Update editable profile fields |
| POST | `/upload_avatar/` | Upload avatar image (JPEG/PNG/GIF/WebP, 5 MB max, magic-byte validated) |
| GET | `/{id}/` | Public profile (respects `profile_visibility`) |
| GET | `/` | List (returns only the authenticated user) |

### Gamification and Stats

| Method | Path | Description |
|--------|------|-------------|
| GET | `/stats/` | Level, XP, streaks, dream/task counts |
| GET | `/dashboard/` | Heatmap (28 days), stats, upcoming tasks, top dreams |
| GET | `/gamification/` | Gamification profile with 6-category skill radar |
| GET | `/achievements/` | All achievements with live progress + unlock status |
| GET | `/streak-details/` | 14-day history, longest streak, freeze status |
| GET | `/ai-usage/` | Daily AI quota usage |
| GET | `/daily-quote/` | Deterministic daily motivational quote |
| GET | `/profile-completeness/` | Percentage + suggestions for completing profile |
| GET | `/morning-briefing/` | Greeting, today's tasks/events, streak, spotlight, recap |
| GET | `/weekly-report/` | AI-powered weekly progress report (premium) |
| GET | `/productivity-insights/` | Task completion patterns and focus analytics |

### AI-Powered (premium/pro only)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/motivation/` | Mood-based AI motivational message |
| GET | `/check-in/` | Personalized accountability check-in |
| POST | `/celebrate/` | AI celebration for achievements |
| GET/PUT | `/notification-timing/` | AI-optimized notification scheduling |

### Preferences

| Method | Path | Description |
|--------|------|-------------|
| GET/PUT | `/persona/` | User persona for AI calibration |
| GET/PUT | `/energy-profile/` | Peak/low energy hours + pattern |
| PUT | `/notification-preferences/` | Push/email toggle per notification type |

### Onboarding

| Method | Path | Description |
|--------|------|-------------|
| POST | `/complete-onboarding/` | Mark onboarding as done |
| POST | `/personality-quiz/` | 8-question quiz -> dreamer type + 50 XP |

### Account Lifecycle

| Method | Path | Description |
|--------|------|-------------|
| POST | `/change-email/` | Request email change (sends verification via Celery), requires password |
| GET | `/verify-email/{token}/` | Confirm email change via token link |
| POST/DELETE | `/delete-account/` | Soft-delete (anonymize + 30-day grace) |
| GET | `/export-data/` | GDPR export as JSON or CSV |

### Two-Factor Authentication

| Method | Path | Description |
|--------|------|-------------|
| POST | `/2fa/setup/` | Generate TOTP secret + provisioning URI |
| POST | `/2fa/verify/` | Verify TOTP code (completes setup or login) |
| POST | `/2fa/disable/` | Disable 2FA (requires password) |
| GET | `/2fa/status/` | Check 2FA enabled + remaining backup codes |
| POST | `/2fa/backup-codes/` | Regenerate 10 backup codes (requires password) |

## Celery Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| `send_email_change_verification` | On-demand | Sends verification email for email change |
| `export_user_data` | On-demand | Exports user data as JSON, emails download link |
| `hard_delete_expired_accounts` | Daily | GDPR: permanently deletes accounts soft-deleted 30+ days ago |
| `generate_weekly_reports` | Sunday evening | AI weekly progress reports for premium/pro users |
| `send_accountability_checkins` | Daily 10 AM | AI check-in for users inactive 2+ days |

## Services

- **`UserStatsService`**: Comprehensive user statistics (dreams, tasks, streaks).
- **`AchievementService`**: Checks all achievement conditions and unlocks newly met ones (with XP + notification).
- **`_BuddyMatchingServiceDeprecated`**: Legacy buddy matching (use `apps.buddies.services` instead).

## Security

- Profile visibility: `public` / `friends` / `private` with friendship check
- Avatar upload: content-type whitelist + magic-byte validation + UUID filename
- Email change: password required, 2FA code required if enabled
- Account deletion: password required, Stripe cancellation, data anonymization
- 2FA: TOTP with PBKDF2-hashed backup codes, rate-limited endpoints
- All text fields sanitized via `core.sanitizers`
- Display name uniqueness validated

## Tests

| File | Tests | Focus |
|------|-------|-------|
| `test_unit.py` | 179 | Model methods, serializers, managers |
| `test_integration.py` | 109 | All API endpoints end-to-end |
| `test_users_views_extra.py` | ~100 | Deep coverage of edge cases |
| `test_users_complete.py` | 110 | IDOR, 2FA lifecycle, password change, email change with 2FA, persona, energy profile, notification timing, achievements, export, AI mocks |
| `test_user_services.py` | ~15 | Service classes |
| `test_user_tasks.py` | ~20 | Celery task logic |

Total: approximately 530 tests.

Run tests:
```bash
pytest apps/users/tests/ --reuse-db -q
```

## Frontend Integration

All endpoints mapped in `src/services/endpoints.js` under `USERS` and `USERS.TFA`.

### Feature gaps

- `USERS.PERSONA` endpoint constant added but no UI screen uses it yet.
