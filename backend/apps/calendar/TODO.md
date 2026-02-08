# TODO - Calendar App

## Completed

- [x] Models: CalendarEvent, TimeBlock
- [x] Full REST API
- [x] Filtering by date and range
- [x] Today/week/overdue views
- [x] Basic auto-scheduling
- [x] Integration with Tasks
- [x] Unit tests

## Recently Completed

- [x] Add @extend_schema decorators for Swagger
- [x] XSS sanitization for text fields

## Planned - High Priority

- [ ] **Drag & drop reschedule** - API support for reorganization
- [ ] **Conflict detection** - Detect overlapping events
- [ ] **Recurring events** - Native recurring events
- [ ] **Smart suggestions** - Optimal time slot suggestions
- [ ] Add event creation from Flutter frontend (currently read-only)
- [ ] Add event editing/deletion from frontend

## Planned - Medium Priority

- [ ] **Google Calendar sync** - Bidirectional synchronization
- [ ] **Apple Calendar sync** - iCal integration
- [ ] **Time zone handling** - Better timezone management
- [ ] **Buffer time** - Transition time between tasks

## Planned - Low Priority

- [ ] **Calendar sharing** - Share your calendar
- [ ] **Team calendars** - Team calendars
- [ ] **Availability API** - API to find free time slots
- [ ] **Calendar export** - iCal/ICS export

## Known Bugs

- [ ] Auto-schedule can create overlaps in certain cases
- [ ] Events spanning midnight are not handled properly
- [ ] Reschedule does not update the associated task

## Technical Debt

- [ ] Refactor the scheduling algorithm
- [ ] Add type hints
- [ ] Extract planning logic into a service
- [ ] Add time range validation
- [ ] Handle timezone edge cases

## Performance Optimizations

- [ ] Composite index on (user, start_time)
- [ ] Cache TimeBlocks (rarely modified)
- [ ] Pagination for long period views
- [ ] Optimize availability queries
