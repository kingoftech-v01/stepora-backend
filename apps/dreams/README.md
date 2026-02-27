# Dreams App

Django application for managing dreams, goals, tasks, obstacles, calibration, vision boards, and collaboration.

## Overview

The Dreams app is the core of DreamPlanner. It manages the complete hierarchy:
- **Dream** - The user's main objective/vision with AI analysis and calibration
- **DreamMilestone** - Time-based milestone within a dream plan (1 per month). NOT to be confused with "streak milestones" (7/14/30-day streaks in notifications) or "progress milestones" (25/50/75% in tasks.py)
- **Goal** - Intermediate steps within a milestone (min 4 per milestone)
- **Task** - Concrete actions to complete (min 4 per goal, with recurrence, scheduling, XP rewards)
- **Obstacle** - Challenges and blockers linked to milestones and/or goals (predicted by AI or reported by user)
- **CalibrationResponse** - Q&A pairs from the calibration questionnaire for personalized plans

**Plan Hierarchy:** Dream → DreamMilestone → Goal → Task (with Obstacles on milestones/goals)
- **DreamTemplate** - Pre-built templates for quick dream creation
- **DreamTag / DreamTagging** - Custom tags for organizing dreams
- **SharedDream** - Share dreams with other users (view/comment permissions)
- **DreamCollaborator** - Collaboration roles on shared dreams
- **DreamProgressSnapshot** - Daily progress snapshots for sparkline charts
- **VisionBoardImage** - Image gallery for dream vision boards

## Models

### Dream

Main dream/objective model.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | Dream owner (related_name: `dreams`) |
| title | CharField(255) | Dream title |
| description | TextField | Detailed description |
| category | CharField(50) | Category (career, health, etc.) |
| target_date | DateTimeField | Target completion date (nullable) |
| priority | IntegerField | Priority level (default: 1) |
| status | CharField(20) | `active`, `completed`, `paused`, `archived` (default: `active`) |
| ai_analysis | JSONField | AI-generated analysis and insights (nullable) |
| vision_image_url | URLField(500) | Vision board image URL (DALL-E generated) |
| progress_percentage | FloatField | Progress percentage (default: 0.0) |
| completed_at | DateTimeField | Completion timestamp (nullable) |
| has_two_minute_start | BooleanField | Whether a 2-minute start task exists (default: False) |
| calibration_status | CharField(20) | `pending`, `in_progress`, `completed`, `skipped` (default: `pending`) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `dreams`

**Methods:**
- `update_progress()` - Recalculate progress from completed goals, record snapshot
- `complete()` - Mark as completed, award 500 XP, check achievements

### DreamMilestone

Time-based milestone within a dream plan. Each milestone represents one month of the plan timeline. Milestones contain goals, and goals contain tasks. For long dreams (> 6 months), the plan is generated in 6-month chunks to maintain quality.

**NOTE:** This is different from "streak milestones" (7/14/30/60/100/365-day streaks in `notifications/tasks.py`) and "progress milestones" (25%/50%/75% progress thresholds in `dreams/tasks.py::_check_milestone`).

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| dream | FK(Dream) | Parent dream (related_name: `milestones`) |
| title | EncryptedCharField(255) | Milestone title |
| description | EncryptedTextField | Description of what this milestone achieves |
| order | IntegerField | Order within the dream (1 = first milestone) |
| target_date | DateTimeField | Target date for this milestone (nullable) |
| expected_date | DateField | Ideal/soft date to complete (no penalty if missed, nullable) |
| deadline_date | DateField | Hard deadline — must be done by this date (nullable) |
| status | CharField(20) | `pending`, `in_progress`, `completed`, `skipped` (default: `pending`) |
| completed_at | DateTimeField | Completion timestamp (nullable) |
| progress_percentage | FloatField | Progress (default: 0.0) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `milestones`

**Methods:**
- `update_progress()` - Recalculate progress from completed goals, update parent dream
- `complete()` - Mark as completed, update dream progress, award 200 XP

### Goal

Intermediate step within a milestone (or legacy: directly within a dream).

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| dream | FK(Dream) | Parent dream (related_name: `goals`) |
| milestone | FK(DreamMilestone) | Parent milestone (related_name: `goals`, nullable for legacy) |
| title | CharField(255) | Goal title |
| description | TextField | Description |
| order | IntegerField | Order in the sequence |
| estimated_minutes | IntegerField | Estimated duration (nullable) |
| scheduled_start | DateTimeField | Scheduled start date (nullable) |
| scheduled_end | DateTimeField | Scheduled end date (nullable) |
| expected_date | DateField | Ideal/soft date to complete (no penalty if missed, nullable) |
| deadline_date | DateField | Hard deadline — must be done by this date (nullable) |
| status | CharField(20) | `pending`, `in_progress`, `completed`, `skipped` (default: `pending`) |
| completed_at | DateTimeField | Completion timestamp (nullable) |
| reminder_enabled | BooleanField | Reminders enabled (default: True) |
| reminder_time | DateTimeField | Reminder time (nullable) |
| progress_percentage | FloatField | Progress (default: 0.0) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `goals`

**Methods:**
- `update_progress()` - Recalculate progress from completed tasks, update parent dream
- `complete()` - Mark as completed, update dream progress, award 100 XP

### Task

Individual action within a goal.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| goal | FK(Goal) | Parent goal (related_name: `tasks`) |
| title | CharField(255) | Task title |
| description | TextField | Detailed execution instructions (step-by-step) |
| order | IntegerField | Order within the goal |
| scheduled_date | DateTimeField | Scheduled date (nullable) |
| scheduled_time | CharField(5) | Time in HH:MM format |
| duration_mins | IntegerField | Duration in minutes (nullable) |
| expected_date | DateField | Ideal/soft date to do this task (calendar event, nullable) |
| deadline_date | DateField | Hard deadline for this task (calendar deadline, nullable) |
| recurrence | JSONField | Recurrence pattern: `{type: "daily|weekly|monthly", interval: 1, ...}` (nullable) |
| status | CharField(20) | `pending`, `completed`, `skipped` (default: `pending`) |
| completed_at | DateTimeField | Completion timestamp (nullable) |
| is_two_minute_start | BooleanField | Whether this is a 2-minute start task (default: False) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `tasks`

**Methods:**
- `complete()` - Mark as completed, update goal progress, award XP (min 10, based on duration), update streak, record daily activity, check achievements

### Obstacle

Predicted or actual obstacle for a dream, optionally linked to a milestone and/or goal.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| dream | FK(Dream) | Associated dream (related_name: `obstacles`) |
| milestone | FK(DreamMilestone) | Linked milestone (related_name: `obstacles`, nullable) |
| goal | FK(Goal) | Linked goal (nullable) |
| title | CharField(255) | Obstacle title |
| description | TextField | Description |
| obstacle_type | CharField(20) | `predicted` or `actual` (default: `predicted`) |
| solution | TextField | AI-generated solution |
| status | CharField(20) | `active`, `resolved`, `ignored` (default: `active`) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `obstacles`

### CalibrationResponse

Stores a calibration Q&A pair for a dream. Used to build a personalized user profile before plan generation.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| dream | FK(Dream) | Associated dream (related_name: `calibration_responses`) |
| question | TextField | AI-generated calibration question |
| answer | TextField | User response to the question |
| question_number | IntegerField | Order of question in the calibration flow |
| category | CharField(30) | Question category: `experience`, `timeline`, `resources`, `motivation`, `constraints`, `specifics`, `lifestyle`, `preferences` |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `calibration_responses`

### DreamTag

Custom tag for organizing and filtering dreams.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| name | CharField(50) | Tag name (unique) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `dream_tags`

### DreamTagging

M2M through model for Dream-Tag relationship.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| dream | FK(Dream) | Tagged dream (related_name: `taggings`) |
| tag | FK(DreamTag) | Applied tag (related_name: `taggings`) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `dream_taggings`
**Constraint:** `unique_together = [['dream', 'tag']]`

### DreamTemplate

Pre-built dream template for quick dream creation with structured goals and tasks.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| title | CharField(255) | Template title |
| description | TextField | Template description |
| category | CharField(30) | Category (see choices below) |
| template_goals | JSONField | JSON array of goal templates: `[{title, description, order, tasks: [{title, description, order, duration_mins}]}]` |
| estimated_duration_days | IntegerField | Estimated days to complete (default: 90) |
| difficulty | CharField(20) | `beginner`, `intermediate`, `advanced` (default: `intermediate`) |
| icon | CharField(100) | Icon identifier |
| is_featured | BooleanField | Whether shown in featured templates (default: False) |
| is_active | BooleanField | Whether template is available (default: True) |
| usage_count | IntegerField | Number of times used (default: 0) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `dream_templates`

**Category choices:**

| Value | Display Name |
|-------|-------------|
| `health` | Health & Fitness |
| `career` | Career & Business |
| `education` | Education & Learning |
| `finance` | Finance & Savings |
| `creative` | Creative & Arts |
| `personal` | Personal Growth |
| `social` | Social & Relationships |
| `travel` | Travel & Adventure |

### DreamCollaborator

Collaboration roles for shared dreams.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| dream | FK(Dream) | Collaborative dream (related_name: `collaborators`) |
| user | FK(User) | Collaborator (related_name: `dream_collaborations`) |
| role | CharField(20) | `owner`, `collaborator`, `viewer` (default: `viewer`) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `dream_collaborators`
**Constraint:** `unique_together = [['dream', 'user']]`

### SharedDream

Dream shared with another user with granular permissions.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| dream | FK(Dream) | Shared dream (related_name: `shares`) |
| shared_by | FK(User) | User who shared (related_name: `dreams_shared`) |
| shared_with | FK(User) | User the dream was shared with (related_name: `dreams_shared_with_me`) |
| permission | CharField(20) | `view` or `comment` (default: `view`) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `shared_dreams`
**Constraint:** `unique_together = [['dream', 'shared_with']]`

### DreamProgressSnapshot

Daily snapshot of dream progress for sparkline charts.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| dream | FK(Dream) | Associated dream (related_name: `progress_snapshots`) |
| date | DateField | Snapshot date |
| progress_percentage | FloatField | Progress at that date |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `dream_progress_snapshots`
**Constraint:** `unique_together = ('dream', 'date')`

**Methods:**
- `record_snapshot(dream)` (classmethod) - Record or update today's progress snapshot

### VisionBoardImage

Image in a dream's vision board gallery.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| dream | FK(Dream) | Associated dream (related_name: `vision_images`) |
| image_url | URLField(500) | URL to image |
| image_file | ImageField | Uploaded image file (upload_to: `vision_boards/`) |
| caption | CharField(500) | Image caption |
| is_ai_generated | BooleanField | Whether generated by DALL-E (default: False) |
| order | IntegerField | Display order (default: 0) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `vision_board_images`

## API Endpoints

### Dreams

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List dreams (filterable by `status`, `category`; searchable by `title`, `description`) |
| POST | `/` | Create a new dream |
| GET | `/{id}/` | Dream detail with nested goals, tasks, obstacles, calibration responses |
| PUT | `/{id}/` | Update a dream |
| PATCH | `/{id}/` | Partial update |
| DELETE | `/{id}/` | Delete a dream |
| POST | `/{id}/analyze/` | AI analysis of the dream |
| POST | `/{id}/start-calibration/` | Generate 7 initial calibration questions |
| POST | `/{id}/answer-calibration/` | Submit answers, get follow-up questions or completion |
| POST | `/{id}/skip-calibration/` | Skip calibration, proceed with basic info |
| POST | `/{id}/generate-plan/` | Generate AI plan with goals and tasks (uses calibration data if available) |
| POST | `/{id}/generate-two-minute-start/` | Generate a micro-action to start in 2 minutes |
| POST | `/{id}/generate-vision/` | Generate DALL-E vision board image |
| GET | `/{id}/vision-board/` | List vision board images |
| POST | `/{id}/vision-board/add/` | Add an image to the vision board (file upload or URL) |
| DELETE | `/{id}/vision-board/{image_id}/` | Remove a vision board image |
| GET | `/{id}/progress-history/?days=30` | Get progress snapshots for sparkline charts |
| POST | `/{id}/complete/` | Mark dream as completed (awards 500 XP) |
| POST | `/{id}/duplicate/` | Deep-copy dream with all goals, tasks, and tags |
| POST | `/{id}/share/` | Share with another user (body: `{shared_with_id, permission}`) |
| DELETE | `/{id}/unshare/{user_id}/` | Remove sharing with a user |
| POST | `/{id}/tags/` | Add a tag (body: `{tag_name}`), creates tag if needed |
| DELETE | `/{id}/tags/{tag_name}/` | Remove a tag from the dream |
| POST | `/{id}/collaborators/` | Add a collaborator (body: `{user_id, role}`) |
| GET | `/{id}/collaborators/list/` | List collaborators |
| DELETE | `/{id}/collaborators/{user_id}/` | Remove a collaborator |

**ViewSet:** `DreamViewSet` (ModelViewSet)
- Permission: `IsAuthenticated`, `IsOwner`
- AI actions require `CanUseAI` permission
- Vision board actions require `CanUseVisionBoard` permission
- Dream creation requires `CanCreateDream` permission

#### Calibration Flow

1. `POST /{id}/start-calibration/` - Generates 7 initial questions via AI across 8 mandatory areas (experience, time, resources, motivation, constraints, specifics, lifestyle, preferences)
2. `POST /{id}/answer-calibration/` - Submit answers as `{answers: [{question_id, answer}]}`. Returns either follow-up questions or completion status. Max 25 questions total. AI must reach 0.95+ confidence. Each answer is moderated.
3. `POST /{id}/generate-plan/` - If calibration completed, generates a calibration summary first, then uses it for a personalized milestone-based plan. For dreams > 6 months, the plan is generated in **6-month chunks** (multiple API calls) to maintain full quality. Includes `plan_evidence` with `calibration_references` and `coherence_warnings`.

#### Date Validation

- `target_date` must be at least **1 month** from now (30 days minimum)
- `target_date` must be within **3 years** from now (1095 days maximum)
- Enforced on both create and update

#### Dual Date System (Calendar Integration)

Every DreamMilestone, Goal, and Task has two date fields for calendar integration:

| Field | Type | Purpose |
|-------|------|---------|
| `expected_date` | DateField | **Soft target** — the ideal date to complete. If missed, no penalty. Shows as a regular calendar event. |
| `deadline_date` | DateField | **Hard deadline** — must be done by this date. Shows as a deadline alert in the calendar. |

**Buffer rules** (AI-generated):
- **Tasks**: 2-5 days between expected and deadline
- **Goals**: 3-7 days between expected and deadline
- **Milestones**: 5-10 days between expected and deadline

**Scheduling philosophy:**
- AI accounts for weekends, rest days, and natural pauses
- Not every day has tasks — breathing room is built in
- Dates are realistic for a human (not a machine)
- The user receives notifications on both dates (expected = reminder, deadline = alert)

### Dream Milestones

| Method | Path | Description |
|--------|------|-------------|
| GET | `/milestones/` | List dream milestones (query param `dream` to filter by dream) |
| GET | `/milestones/{id}/` | Milestone detail with nested goals, tasks, obstacles |
| DELETE | `/milestones/{id}/` | Delete a milestone |
| POST | `/milestones/{id}/complete/` | Mark as completed (awards 200 XP) |

**ViewSet:** `DreamMilestoneViewSet` (ModelViewSet)
- Permission: `IsAuthenticated`

### Goals

| Method | Path | Description |
|--------|------|-------------|
| GET | `/goals/` | List goals (filterable by `status`, query param `dream` to filter by dream) |
| POST | `/goals/` | Create a goal |
| GET | `/goals/{id}/` | Goal detail with nested tasks |
| PUT | `/goals/{id}/` | Update a goal |
| PATCH | `/goals/{id}/` | Partial update |
| DELETE | `/goals/{id}/` | Delete a goal |
| POST | `/goals/{id}/complete/` | Mark as completed (awards 100 XP) |

**ViewSet:** `GoalViewSet` (ModelViewSet)
- Permission: `IsAuthenticated`

### Tasks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tasks/` | List tasks (filterable by `status`, query param `goal` to filter by goal) |
| POST | `/tasks/` | Create a task |
| GET | `/tasks/{id}/` | Task detail |
| PUT | `/tasks/{id}/` | Update a task |
| PATCH | `/tasks/{id}/` | Partial update |
| DELETE | `/tasks/{id}/` | Delete a task |
| POST | `/tasks/{id}/complete/` | Mark as completed (awards XP based on duration) |
| POST | `/tasks/{id}/skip/` | Skip a task |

**ViewSet:** `TaskViewSet` (ModelViewSet)
- Permission: `IsAuthenticated`

### Obstacles

| Method | Path | Description |
|--------|------|-------------|
| GET | `/obstacles/` | List obstacles (query param `dream` to filter by dream) |
| POST | `/obstacles/` | Create an obstacle |
| GET | `/obstacles/{id}/` | Obstacle detail |
| PUT | `/obstacles/{id}/` | Update an obstacle |
| PATCH | `/obstacles/{id}/` | Partial update |
| DELETE | `/obstacles/{id}/` | Delete an obstacle |
| POST | `/obstacles/{id}/resolve/` | Mark as resolved |

**ViewSet:** `ObstacleViewSet` (ModelViewSet)
- Permission: `IsAuthenticated`

### Dream Templates

| Method | Path | Description |
|--------|------|-------------|
| GET | `/dreams/templates/` | List active templates (query param `category` to filter) |
| GET | `/dreams/templates/{id}/` | Template detail |
| POST | `/dreams/templates/{id}/use/` | Create a new dream from template (creates goals + tasks, increments usage_count) |
| GET | `/dreams/templates/featured/` | Get featured templates (max 10) |

**ViewSet:** `DreamTemplateViewSet` (ReadOnlyModelViewSet)
- Permission: `IsAuthenticated`

### Dream Tags

| Method | Path | Description |
|--------|------|-------------|
| GET | `/dreams/tags/` | List all available tags |

**View:** `DreamTagListView` (ListAPIView)
- Permission: `IsAuthenticated`

### Dream Sharing

| Method | Path | Description |
|--------|------|-------------|
| GET | `/dreams/shared-with-me/` | List dreams shared with the current user |

**View:** `SharedWithMeView` (ListAPIView)
- Permission: `IsAuthenticated`

### PDF Export

| Method | Path | Description |
|--------|------|-------------|
| GET | `/dreams/{id}/export-pdf/` | Export dream as PDF (includes goals, tasks, obstacles, progress) |

**View:** `DreamPDFExportView` (APIView)
- Permission: `IsAuthenticated`
- Requires `reportlab` package

## Serializers

| Serializer | Purpose |
|------------|---------|
| `DreamSerializer` | Dream with computed `goals_count`, `tasks_count`, `tags`, `sparkline_data` (last 7 snapshots) |
| `DreamDetailSerializer` | Full dream with nested `milestones` (with goals/tasks/obstacles), `goals`, `obstacles`, `calibration_responses`, `milestones_count`, `completed_milestones_count` |
| `DreamCreateSerializer` | Input: `title` (min 3 chars, sanitized, moderated), `description` (sanitized, moderated), `category`, `target_date` (min 1mo, max 3yr), `priority` |
| `DreamUpdateSerializer` | Input: `title`, `description`, `category`, `target_date` (min 1mo, max 3yr), `priority`, `status` (all sanitized and moderated) |
| `DreamMilestoneSerializer` | Milestone with nested `goals` (with tasks), `obstacles`, `expected_date`, `deadline_date`, computed `goals_count`, `completed_goals_count` |
| `GoalSerializer` | Goal with nested `tasks`, `milestone` FK, `expected_date`, `deadline_date`, computed `tasks_count`, `completed_tasks_count` |
| `GoalCreateSerializer` | Input: `dream`, `milestone` (optional), `title`, `description`, `order`, `estimated_minutes`, `scheduled_start/end`, `expected_date`, `deadline_date`, `reminder_enabled`, `reminder_time` |
| `TaskSerializer` | Full task with all fields including `expected_date`, `deadline_date`, `recurrence`, `is_two_minute_start` |
| `TaskCreateSerializer` | Input: `goal`, `title`, `description`, `order`, `scheduled_date/time`, `duration_mins`, `expected_date`, `deadline_date`, `recurrence`, `is_two_minute_start` |
| `ObstacleSerializer` | Full obstacle with `solution` |
| `CalibrationResponseSerializer` | Calibration Q&A pair with `question_number`, `category` |
| `DreamTagSerializer` | Tag with `id`, `name`, `created_at` |
| `SharedDreamSerializer` | Shared dream with `dream_title`, `shared_by_name`, `shared_with_name` |
| `ShareDreamRequestSerializer` | Input: `shared_with_id` (UUID), `permission` (view/comment) |
| `AddTagSerializer` | Input: `tag_name` (max 50 chars, validated) |
| `DreamTemplateSerializer` | Template with `category_display`, `difficulty_display`, `template_goals` |
| `DreamCollaboratorSerializer` | Collaborator with `user_display_name`, `user_avatar`, `dream_title` |
| `AddCollaboratorSerializer` | Input: `user_id` (UUID), `role` (collaborator/viewer) |
| `VisionBoardImageSerializer` | Vision board image with `image_url`, `image_file`, `caption`, `is_ai_generated`, `order` |

## Permissions

| Permission | Description |
|------------|-------------|
| `IsAuthenticated` | All views require authentication |
| `IsOwner` | Verifies the user owns the dream |
| `CanCreateDream` | Subscription-based limit on dream creation |
| `CanUseAI` | Subscription-based access to AI features (analyze, calibration, plan generation) |
| `CanUseVisionBoard` | Subscription-based access to vision board features |

## Gamification (XP Rewards)

| Action | XP Awarded |
|--------|-----------|
| Complete a **Task** | `max(10, duration_mins / 3)` - minimum 10 XP |
| Complete a **Goal** | 100 XP |
| Complete a **DreamMilestone** | 200 XP |
| Complete a **Dream** | 500 XP |

Streaks are updated on each task completion based on consecutive day activity.

## Rate Limiting

| Throttle | Applies to |
|----------|-----------|
| `AIPlanRateThrottle` | analyze, calibration, generate_plan |
| `AIPlanDailyThrottle` | analyze, calibration, generate_plan, generate_two_minute_start |
| `AIImageDailyThrottle` | generate_vision |

## Celery Tasks

| Task | Retries | Description |
|------|---------|-------------|
| `generate_two_minute_start` | 3 | Generate a 2-minute start micro-task for a dream using AI |
| `auto_schedule_tasks` | 3 | Automatically schedule unscheduled tasks based on user's work schedule and preferences |
| `detect_obstacles` | 3 | Use AI to predict potential obstacles for a dream |
| `update_dream_progress` | 3 | Recalculate progress for all active dreams, check milestones (25/50/75/100%) |
| `check_overdue_tasks` | 3 | Find overdue tasks and send notifications to users |
| `suggest_task_adjustments` | 3 | AI-based task adjustment suggestions when completion rate < 50% |
| `generate_vision_board` | 3 | Generate DALL-E vision board image for a dream |
| `cleanup_abandoned_dreams` | 3 | Archive dreams inactive for 90+ days |
| `smart_archive_dreams` | 3 | Pause dreams inactive for 30+ days (with notification), before 90-day archive |

**Helper:** `_check_milestone(dream, old_progress, new_progress)` - Sends notifications at 25%, 50%, 75% milestones.

## Management Commands

| Command | Description |
|---------|-------------|
| `seed_dream_templates` | Seeds 8 dream templates (one per category: health, career, education, finance, creative, personal, social, travel). Idempotent (update_or_create by title) |

## Admin

All 4 core models are registered with Django admin:

- **DreamAdmin** - Shows title, user, status, category, progress, target_date. Fieldsets: Basic Info, Scheduling, Progress, AI & Vision (collapsed), Timestamps (collapsed). Inlines: `GoalInline`, `ObstacleInline`. Filter by status, category, date. Search by title, description, user email
- **GoalAdmin** - Shows title, dream, order, status, progress, scheduled_start. Fieldsets: Basic Info, Scheduling, Progress & Reminders, Timestamps (collapsed). Inline: `TaskInline`. Filter by status, date. Search by title, description, dream title
- **TaskAdmin** - Shows title, goal, order, status, scheduled_date, duration, is_two_minute_start. Fieldsets: Basic Info, Scheduling, Status, Timestamps (collapsed). Filter by status, is_two_minute_start, date. Search by title, description, goal title
- **ObstacleAdmin** - Shows title, dream, obstacle_type, status. Filter by type, status, date. Search by title, description, dream title

## Content Moderation

- Dream titles and descriptions are sanitized and moderated via `ContentModerationService` on create and update
- Task and goal titles/descriptions are sanitized via `sanitize_text`
- Tag names are validated via `validate_tag_name`
- Calibration answers are moderated before saving
- AI outputs (plans, analyses, calibration questions) are validated via `core.ai_validators`

## OpenAI Integration

**Model used:** GPT-4 Turbo (configurable via `OPENAI_MODEL`)

**AI features:**
- `analyze` - AI analysis of dream feasibility and insights
- `start_calibration` / `answer_calibration` - AI-generated calibration questions (7-25 questions across 8 mandatory areas). AI must reach 95% confidence before marking as sufficient. Vague answers trigger deeper follow-ups.
- `generate_plan` - AI milestone-based plan generation (Dream → DreamMilestone → Goal → Task). Always 1 milestone/month. For dreams > 6 months, generated in **6-month chunks** (multiple API calls) to maintain full quality. Uses calibration profile if available. Each chunk passes a summary to the next for continuity.
- `generate_two_minute_start` - AI micro-action generation
- `generate_vision` - DALL-E image generation for vision board
- `detect_obstacles` (Celery) - AI obstacle prediction
- `suggest_task_adjustments` (Celery) - AI coaching suggestions

AI usage is tracked via `AIUsageTracker` for subscription-based rate limiting.

## Token & Cost Estimation (GPT-4o)

**GPT-4o pricing:** Input $2.50/1M tokens | Output $10.00/1M tokens

### Calibration Phase (constant, all durations)

| Phase | API Calls | Input Tokens | Output Tokens | Cost |
|-------|-----------|-------------|---------------|------|
| Initial questions (7 Qs) | 1 | ~3,000 | ~2,000 | $0.028 |
| Follow-up round 1 | 1 | ~4,000 | ~2,000 | $0.030 |
| Follow-up round 2 | 1 | ~5,000 | ~1,500 | $0.028 |
| Profile generation | 1 | ~5,500 | ~2,000 | $0.034 |
| **Calibration Total** | **4** | **~17,500** | **~7,500** | **~$0.12** |

### Planning Phase (varies by duration)

Objects generated per duration (1 milestone/month, 4+ goals/milestone, 4+ tasks/goal):

| Duration | Chunks | Milestones | Goals | Tasks | Obstacles | Total Objects |
|----------|--------|------------|-------|-------|-----------|---------------|
| 1 month | 1 | 1 | 4 | 16 | ~2 | ~23 |
| 2 months | 1 | 2 | 8 | 32 | ~4 | ~46 |
| 3 months | 1 | 3 | 12 | 48 | ~6 | ~69 |
| 6 months | 1 | 6 | 24 | 96 | ~10 | ~136 |
| 12 months | 2 | 12 | 48 | 192 | ~18 | ~270 |
| 18 months | 3 | 18 | 72 | 288 | ~24 | ~402 |
| 24 months | 4 | 24 | 96 | 384 | ~30 | ~534 |
| 36 months | 6 | 36 | 144 | 576 | ~42 | ~798 |

### Total Cost (Calibration + Planning)

| Duration | Total API Calls | Total Input | Total Output | Total Tokens | **Total Cost** | Est. Time |
|----------|----------------|-------------|-------------|-------------|---------------|-----------|
| **1 month** | 5 | ~21,000 | ~10,000 | ~31,000 | **$0.15** | ~25s |
| **2 months** | 5 | ~21,000 | ~12,500 | ~33,500 | **$0.18** | ~30s |
| **3 months** | 5 | ~21,000 | ~15,000 | ~36,000 | **$0.20** | ~35s |
| **6 months** | 5 | ~21,000 | ~21,500 | ~42,500 | **$0.27** | ~50s |
| **12 months** | 6 | ~24,500 | ~35,500 | ~60,000 | **$0.42** | ~1m 40s |
| **18 months** | 7 | ~28,500 | ~49,500 | ~78,000 | **$0.57** | ~2m 30s |
| **24 months** | 8 | ~33,000 | ~63,500 | ~96,500 | **$0.72** | ~3m 20s |
| **36 months** | 10 | ~43,000 | ~91,500 | ~134,500 | **$1.02** | ~5m 00s |

**Key notes:**
- Output tokens dominate cost (~85%) because GPT-4o output is 4x more expensive than input
- Chunked generation (>6 months) adds ~$0.15 per additional 6-month chunk
- Each chunk maxes out at 16,384 output tokens (GPT-4o limit)
- Calibration is 3-4 rounds (~$0.12) — constant regardless of dream duration
- **1,000 users x 12-month dream = ~$420 total**
- **10,000 users x 6-month dream = ~$2,700 total**

## Testing

```bash
pytest apps/dreams/tests.py -v
```

## Configuration

Environment variables:
- `OPENAI_API_KEY` - OpenAI API key
- `OPENAI_MODEL` - Model (default: gpt-4o-mini)
- `OPENAI_TIMEOUT` - Timeout in seconds (default: 30)

## Dependencies

- `openai` - OpenAI API (GPT-4, DALL-E)
- `reportlab` - PDF export (optional)
- `django-filter` - Queryset filtering
