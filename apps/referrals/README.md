# Referrals App

Invite-based referral system with code sharing, referral tracking, reward
distribution, and a combined dashboard endpoint for the frontend.

## Models

| Model | Description |
|---|---|
| `ReferralCode` | One-per-user invite code (auto-created via signal on signup). Tracks `is_active`, `max_uses`, `times_used`. |
| `Referral` | Records a referrer-referred pair with status (`pending` / `completed` / `rewarded` / `expired`). Enforces uniqueness per pair. |
| `ReferralReward` | Reward granted to a user for a referral. Supports types: `xp`, `premium_days`, `cosmetic`, `discount`, `subscription_days`, `streak_freeze`. |

## Reward Flow

1. User A shares their referral code.
2. User B redeems the code via POST `/api/v1/referrals/redeem/` or POST
   `/api/v1/referrals/dashboard/`.
3. `ReferralService.create_referral()`:
   - Creates a `Referral` record (status=completed).
   - Atomically increments `ReferralCode.times_used`.
   - Creates XP rewards for both users (referrer: 200 XP, referred: 100 XP).
   - Auto-claims XP rewards.
   - Sends a notification to the referrer.
4. Tier progress: every 3 paid referrals = 1 free month (tracked in the
   dashboard endpoint).

## API Endpoints

All under `/api/v1/referrals/` (also accessible via `/api/referrals/`).

| Method | Path | Description |
|---|---|---|
| GET | `/code/` | Get (or auto-create) the current user's referral code |
| POST | `/redeem/` | Redeem a referral code (`{"code": "XXXX"}`) |
| GET | `/my-referrals/` | List referrals made by the current user |
| GET | `/rewards/` | List referral rewards for the current user |
| POST | `/rewards/<uuid>/claim/` | Claim a specific reward |
| GET | `/dashboard/` | Combined stats for frontend (code, totals, tier progress) |
| POST | `/dashboard/` | Redeem code via dashboard (`{"referral_code": "..."}` or `{"code": "..."}`) |

### Dashboard Response Shape (GET)

```json
{
  "referral_code": "ABC12345",
  "total_referrals": 5,
  "paid_referrals": 3,
  "free_months_earned": 1,
  "progress_to_next": 0,
  "referrals_until_next_reward": 3
}
```

## Signal

`post_save` on `users.User` (created=True) auto-creates a `ReferralCode` via
`apps.referrals.signals.create_referral_code`.

## Frontend Integration

The React frontend (`/root/stepora-frontend`) consumes the `/dashboard/`
endpoint via `SUBSCRIPTIONS.REFERRAL` in `src/services/endpoints.js`.

- Hook: `src/pages/store/ReferralScreen/useReferralScreen.js`
- Device variants: `ReferralMobile.jsx`, `ReferralTablet.jsx`, `ReferralDesktop.jsx`
- Route: `/referral`

## Tests

```bash
# Backend (from /root/stepora)
DB_HOST= python3 -m pytest apps/referrals/tests/ --no-cov -v

# Frontend (from /root/stepora-frontend)
npx vitest run src/pages/store/ReferralScreen/
```

### Backend test files

- `test_models.py` -- model-level unit tests
- `test_services.py` -- ReferralService business logic
- `test_views.py` -- basic API endpoint smoke tests
- `test_referrals_complete.py` -- comprehensive test suite (61 tests) covering
  models, services, all endpoints, edge cases, IDOR, dashboard, signals,
  serializers

### Frontend test files

- `useReferralScreen.test.js` -- hook unit tests (12 tests)
- `ReferralScreen.render.test.js` -- render tests for Mobile, Tablet, Desktop (19 tests)

## Key Constants

| Constant | Value | Location |
|---|---|---|
| `REFERRER_XP_REWARD` | 200 | `services.py` |
| `REFERRED_XP_REWARD` | 100 | `services.py` |
| `REFERRALS_PER_REWARD` | 3 | `views.py` |
