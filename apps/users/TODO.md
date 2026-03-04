# Users App — TODO

Feature ideas and improvements for user management, authentication, gamification, and achievements.

---

## Authentication & Security

- [ ] **Social account linking** — Allow users to link multiple social accounts (Google + Apple) to a single DreamPlanner account
- [ ] **Account recovery** — Recovery flow using backup email or phone number when primary email is lost
- [ ] **Password breach check** — Check passwords against HaveIBeenPwned API during registration and password change
- [ ] **Email verification on register** — Require email verification before account activation (currently optional)
- [ ] **Login notifications** — Notify user via email/push when login occurs from a new device or location

## Profile & Personalization

- [ ] **Profile themes** — Let users customize their public profile with colors, banners, and layout
- [ ] **Profile badges showcase** — Drag-and-drop arrangement of badges on public profile
- [ ] **Pronouns field** — Add preferred pronouns to user profile
- [ ] **Cover photo** — Add cover/banner image to user profile (with upload validation)
- [ ] **Profile completeness** — Gamified profile completion bar with XP rewards for filling out each section
- [ ] **QR code profile sharing** — Generate QR code for sharing profile link

## Gamification

- [ ] **Daily challenges** — Auto-generated daily mini-challenges with bonus XP
- [ ] **XP decay** — Gradual XP decay for inactive users to encourage consistent engagement
- [ ] **Prestige system** — Reset to level 1 with a prestige badge after reaching max level (opt-in)
- [ ] **XP multiplier events** — Time-limited global events with boosted XP
- [ ] **Custom achievements** — Let users create personal achievements with custom conditions
- [ ] **Achievement rarity** — Show percentage of users who have unlocked each achievement
- [ ] **Streak recovery** — One-time streak recovery (purchasable with XP) if user misses a single day
- [ ] **RPG attribute quests** — Specific quests per attribute category with targeted XP rewards
- [ ] **Level-up rewards** — Unlock store items or features at specific levels

## Data & Privacy

- [ ] **Data portability** — Export user data in standard formats (JSON, CSV) with dream progress history
- [ ] **Account pause** — Temporarily freeze account without deleting
- [ ] **Activity heatmap** — GitHub-style contribution heatmap showing daily activity over the past year
- [ ] **Login analytics** — Show user their login frequency, peak usage times, and device breakdown

## Two-Factor Authentication

- [ ] **SMS 2FA** — Add SMS-based 2FA as alternative to TOTP
- [ ] **Hardware key support** — Support FIDO2/U2F hardware security keys for 2FA
- [ ] **Trusted devices** — Remember trusted devices for 30 days (skip 2FA on recognized devices)
- [ ] **2FA backup email** — Send backup codes via email as recovery option
