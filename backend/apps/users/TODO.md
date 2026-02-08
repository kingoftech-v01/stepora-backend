# Users App - TODO

## Current Status: Production Ready

All core features are implemented and tested. This document tracks future enhancements and maintenance tasks.

---

## Completed

### Core Features
- [x] User model with django-allauth + Token authentication
- [x] Profile management (CRUD)
- [x] FCM token management
- [x] Subscription system (free/premium/pro)
- [x] Work schedule configuration
- [x] Notification preferences with DND

### Gamification
- [x] XP and leveling system
- [x] Streak tracking
- [x] Level-up detection
- [x] GamificationProfile model
- [x] Badge system
- [x] Rank tiers

### API
- [x] User profile endpoints
- [x] FCM token registration
- [x] Preferences update
- [x] Statistics endpoint
- [x] IsOwner permission
- [x] IsPremiumUser permission

### Testing
- [x] Model tests (100% coverage)
- [x] Authentication tests
- [x] ViewSet tests
- [x] Permission tests
- [x] Gamification tests

### Security
- [x] django-allauth authentication backend
- [x] Token verification
- [x] IsOwner permission on all endpoints
- [x] Input validation
- [x] Rate limiting

### Documentation
- [x] README.md
- [x] API documentation
- [x] Model documentation
- [x] Admin interface

---

## Recently Completed

### Account Management
- [x] Add DELETE /api/users/me/delete-account/ endpoint (account deletion with GDPR compliance)
- [x] Add profile photo upload via media storage (POST /upload-avatar/)
- [x] Add email change with verification flow
- [x] Export user data (data export functionality)
- [x] Notification preferences (granular per-type preferences)

### Two-Factor Authentication (2FA)
- [x] TOTP support
- [x] Backup codes
- [x] 2FA setup endpoint
- [x] 2FA verification
- [x] 2FA disable with password

### Enhanced Profile
- [x] Bio field
- [x] Location field
- [x] Social links (Twitter, LinkedIn, etc.)
- [x] Avatar image support

### Stats
- [x] Stats endpoint (enhanced)

---

## In Progress

Currently, no tasks in progress. All features are complete.

---

## Planned Features

### High Priority

#### Social Graph
- [ ] Friend model (user-to-user relationships)
- [ ] Friend request system
- [ ] Accept/reject friend requests
- [ ] Unfriend functionality
- [ ] Friend list endpoint
- [ ] Friend search
- [ ] Tests for friend system

**Estimated Effort**: 2-3 days

#### Activity Feed
- [ ] Activity model (user actions)
- [ ] Activity types (dream created, task completed, etc.)
- [ ] Feed generation algorithm
- [ ] Feed endpoint (paginated)
- [ ] Privacy controls (public/friends/private)
- [ ] Tests for activity feed

**Estimated Effort**: 2-3 days

### Medium Priority

#### Email Verification
- [ ] Email verification token model
- [ ] Send verification email (Celery task)
- [ ] Verification endpoint
- [ ] Resend verification email
- [ ] Email templates
- [ ] Tests

**Estimated Effort**: 1-2 days

#### User Blocking/Reporting
- [ ] BlockedUser model
- [ ] ReportedUser model
- [ ] Block user endpoint
- [ ] Unblock user endpoint
- [ ] Report user endpoint
- [ ] Admin review interface
- [ ] Tests

**Estimated Effort**: 2 days

#### Account Deletion (Extended)
- [x] Data export functionality (GDPR compliance)
- [ ] Soft delete option
- [ ] Hard delete with cascade
- [ ] Anonymization option
- [ ] Delete confirmation
- [ ] Tests

**Estimated Effort**: 2-3 days

### Low Priority

#### Enhanced Profile (Extended)
- [ ] Profile visibility settings
- [ ] Profile views counter
- [ ] Tests

**Estimated Effort**: 1 day

#### Advanced Gamification
- [ ] Skill trees
- [ ] Achievement categories
- [ ] Badge rarity (common, rare, epic, legendary)
- [ ] Badge showcase (featured badges)
- [ ] XP decay for inactivity
- [ ] Seasonal challenges
- [ ] Tests

**Estimated Effort**: 3-5 days

#### Password Management
- [ ] Wire password change to dj-rest-auth endpoint in frontend

---

## Bugs

### Known Issues

None currently reported.

### To Investigate

- [ ] Streak calculation edge case at timezone boundaries
- [ ] Level-up animation trigger delay
- [ ] FCM token cleanup for uninstalled apps

---

## Performance Optimizations

### Database
- [ ] Add composite index on (subscription, subscription_ends)
- [ ] Optimize streak calculation query
- [ ] Cache user statistics (Redis)

### API
- [ ] Implement ETag for profile endpoint
- [ ] Add pagination to badges list
- [ ] Reduce payload size for list endpoints

---

## Technical Debt

### Code Quality
- [ ] Add type hints to all methods
- [ ] Refactor `update_streak()` logic
- [ ] Extract XP calculation to service class
- [ ] Add docstrings to all public methods

### Testing
- [ ] Add integration tests for django-allauth auth flow
- [ ] Add load testing for high XP users
- [ ] Test timezone edge cases

### Documentation
- [ ] Add Swagger/OpenAPI schema
- [ ] Create sequence diagrams for auth flow
- [ ] Document XP formula in detail

---

## Maintenance

### Regular Tasks

**Weekly**:
- [ ] Review inactive users (>30 days)
- [ ] Check for duplicate FCM tokens
- [ ] Monitor subscription expiration

**Monthly**:
- [ ] Analyze XP distribution
- [ ] Review badge earn rates
- [ ] Check for data anomalies

**Quarterly**:
- [ ] Security audit
- [ ] Performance review
- [ ] Dependency updates

---

## Ideas / Discussion

### Potential Features

**Referral System**:
- Users can invite friends
- Reward XP for successful referrals
- Track referral tree

**Premium Features**:
- Custom themes
- Advanced statistics
- Priority support
- Extended history

**Achievements**:
- Secret achievements
- Time-limited achievements
- Community achievements

### Questions to Resolve

1. Should we allow users to change their email?
2. What happens to data when user downgrades subscription?
3. Should streak reset immediately or have a "grace period"?
4. How to handle timezone changes for streak calculation?

---

## Dependencies

### Required for Social Graph
- [ ] Notification system update (friend request notifications)
- [ ] Real-time events (friend came online)

### Required for Activity Feed
- [ ] Event tracking system across all apps
- [ ] Feed generation service
- [ ] Real-time updates via WebSocket

---

## Breaking Changes

No planned breaking changes.

---

## Notes

- Keep backward compatibility for mobile app versions
- All new features must have tests before merge
- Update API documentation with every change
- Consider mobile bandwidth when adding new fields

---

**Last Updated**: 2026-02-08
**Next Review**: 2026-03-08
