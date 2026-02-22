# TODO - Notifications App

## Completed

- [x] Models: Notification, NotificationTemplate, NotificationBatch
- [x] Template system with variables
- [x] Do Not Disturb (DND) support
- [x] Celery tasks for automatic sending
- [x] Full REST API
- [x] Retry logic on send failure
- [x] Unit tests

## Recently Completed

- [x] Add @extend_schema decorators for Swagger
- [x] XSS sanitization of notification content
- [x] **Granular notification preferences** - Per notification type
- [x] **In-app notifications** - Notification center in the app (mark-read, unread-count, grouped)
- [x] **Analytics** - Open rate tracking (opened_at tracking)
- [x] **Notification grouping** - Group similar notifications

## Planned - High Priority

- [ ] **Rich notifications** - Images and actions in notifications
- [ ] **Notification channels** - Distinct Android channels

## Planned - Medium Priority

- [ ] **Email fallback** - Email if push fails
- [ ] **A/B testing** - Test different messages

## Planned - Low Priority

- [ ] **SMS notifications** - For critical reminders
- [ ] **Webhook notifications** - For third-party integrations
- [ ] **Notification scheduling UI** - Advanced admin interface

## Known Bugs

- [ ] Expired push tokens are not cleaned up automatically
- [ ] DND can have issues during daylight saving time changes
- [ ] Batches over 500 are not handled

## Technical Debt

- [ ] Add type hints
- [ ] Add Prometheus metrics

## Performance Optimizations

- [ ] Batch processing for high volumes
- [ ] Priority queue for urgent notifications
- [ ] Cache frequently used templates
- [ ] Index on scheduled_for for queries
