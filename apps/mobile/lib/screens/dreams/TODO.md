# Dream Screens - TODO

## Current Status
- create_dream_screen.dart: Fully functional (create with title, description, category, timeframe)
- dream_detail_screen.dart: Shows dream with goals/tasks, popup menu has Calibration/Generate Plan/Delete/Edit
- edit_dream_screen.dart: Fully functional (edit title, description, category, timeframe, status)
- calibration_screen.dart: Fully functional (scale/choice/text question types)
- vision_board_screen.dart: Functional (generate + view AI image)
- micro_start_screen.dart: Functional (2-minute timer with task completion)
- dream_templates_screen.dart: Functional (browse and use dream templates)

## Missing Screens
- [x] **Edit Dream screen**: Pre-populated form matching CreateDreamScreen fields (title, description, category, timeframe) + status change (active/paused/archived); call `PUT /api/dreams/{id}/`

## Placeholders to Fix
- [x] **dream_detail_screen.dart popup menu**: Add "Edit Dream" option navigating to `/dreams/:id/edit`

## Missing CRUD Actions
- [x] Add manual goal creation UI: Form with title, description; call `POST /api/dreams/{dreamId}/goals/`
- [x] Add goal editing: Tap goal title to edit; call `PUT /api/goals/{id}/`
- [x] Add goal deletion: Swipe or long-press; call `DELETE /api/goals/{id}/`
- [x] Add manual task creation UI: Form with title, scheduled_date, duration; call `POST /api/goals/{goalId}/tasks/`
- [x] Add task editing: Tap task to edit details

## Small Improvements
- [x] Add dream archiving/pausing toggle (status field supports it)
- [x] Add progress celebration animation on 25%/50%/75%/100% milestones
- [x] Add obstacle display section (backend has Obstacle model)
- [x] Add dream templates screen
- [x] Add dream PDF export
- [ ] Show 2-minute start availability badge on dream card
- [ ] Persist micro_start timer across screen navigation
