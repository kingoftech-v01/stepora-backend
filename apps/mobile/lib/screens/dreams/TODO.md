# Dream Screens - TODO

## Current Status
- create_dream_screen.dart: Fully functional (create with title, description, category, timeframe)
- dream_detail_screen.dart: Shows dream with goals/tasks, popup menu has Calibration/Generate Plan/Delete
- calibration_screen.dart: Fully functional (scale/choice/text question types)
- vision_board_screen.dart: Functional (generate + view AI image)
- micro_start_screen.dart: Functional (2-minute timer with task completion)

## Missing Screens
- [ ] **Edit Dream screen**: Pre-populated form matching CreateDreamScreen fields (title, description, category, timeframe) + status change (active/paused/archived); call `PUT /api/dreams/{id}/`

## Placeholders to Fix
- [ ] **dream_detail_screen.dart popup menu**: Add "Edit Dream" option navigating to `/dreams/:id/edit`

## Missing CRUD Actions
- [ ] Add manual goal creation UI: Form with title, description; call `POST /api/dreams/{dreamId}/goals/`
- [ ] Add goal editing: Tap goal title to edit; call `PUT /api/goals/{id}/`
- [ ] Add goal deletion: Swipe or long-press; call `DELETE /api/goals/{id}/`
- [ ] Add manual task creation UI: Form with title, scheduled_date, duration; call `POST /api/goals/{goalId}/tasks/`
- [ ] Add task editing: Tap task to edit details

## Small Improvements
- [ ] Add dream archiving/pausing toggle (status field supports it)
- [ ] Add progress celebration animation on 25%/50%/75%/100% milestones
- [ ] Add obstacle display section (backend has Obstacle model)
- [ ] Show 2-minute start availability badge on dream card
- [ ] Persist micro_start timer across screen navigation
