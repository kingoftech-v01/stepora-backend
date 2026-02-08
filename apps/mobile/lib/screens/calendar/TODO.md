# Calendar Screen - TODO

## Current Status
- calendar_screen.dart: Read-only calendar with event display, no CRUD actions

## Placeholders to Fix
- [ ] **Add event creation**: FAB button to create CalendarEvent; form dialog with title, description, start/end DateTimePicker; call `POST /api/calendar/`
- [ ] **Add event editing**: Tap event to open edit dialog; call `PUT /api/calendar/{id}/`
- [ ] **Add event deletion**: Long-press or swipe-to-delete; call `DELETE /api/calendar/{id}/`

## Missing Functionality
- [ ] Add time block management UI (backend: `GET/POST/PUT/DELETE /api/time-blocks/`)
- [ ] Add auto-schedule button (backend: `POST /api/calendar/auto-schedule/`)
- [ ] Add overdue tasks indicator/badge
- [ ] Add week/day view toggle (currently month view only)
- [ ] Add task reschedule via drag-and-drop or dialog (backend: `POST /api/calendar/{id}/reschedule/`)

## Small Improvements
- [ ] Show task completion status on calendar markers (green=done, red=overdue)
- [ ] Add "Today" quick-nav button
- [ ] Show task count badge per day on calendar
