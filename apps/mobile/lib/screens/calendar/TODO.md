# Calendar Screen - TODO

## Current Status
- calendar_screen.dart: Full CRUD calendar with event creation, editing, and deletion

## Placeholders to Fix
- [x] **Add event creation**: FAB button to create CalendarEvent; form dialog with title, description, start/end DateTimePicker; call `POST /api/calendar/`
- [x] **Add event editing**: Tap event to open edit dialog; call `PUT /api/calendar/{id}/`
- [x] **Add event deletion**: Long-press or swipe-to-delete; call `DELETE /api/calendar/{id}/`

## Missing Functionality
- [x] Add time block management UI (backend: `GET/POST/PUT/DELETE /api/time-blocks/`)
- [x] Add auto-schedule button (backend: `POST /api/calendar/auto-schedule/`)
- [ ] Add overdue tasks indicator/badge
- [x] Add week/day view toggle (currently month view only)
- [x] Add task reschedule via drag-and-drop or dialog (backend: `POST /api/calendar/{id}/reschedule/`)

## Small Improvements
- [ ] Show task completion status on calendar markers (green=done, red=overdue)
- [x] Add "Today" quick-nav button
- [x] Show task count badge per day on calendar
