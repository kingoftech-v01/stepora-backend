# Dreams App

Django application for managing dreams, goals, tasks, and obstacles.

## Overview

The Dreams app is the core of DreamPlanner. It manages the complete hierarchy:
- **Dream** - The user's main objective/vision
- **Goal** - Intermediate steps to achieve the dream
- **Task** - Concrete actions to complete
- **Obstacle** - Challenges and blockers (predicted or actual)

## Models

### DreamTemplate

Reusable dream templates for common dream types. Users can browse and use templates to quickly create new dreams.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| title | CharField(255) | Template title |
| description | TextField | Template description |
| category | CharField(50) | Category (career, health, etc.) |
| is_featured | Boolean | Whether shown in featured templates |
| template_data | JSONField | Pre-filled dream data (goals, tasks, etc.) |

### DreamTag

Custom tags for organizing and filtering dreams.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| name | CharField(100) | Tag name |
| slug | SlugField(100) | URL-friendly slug |

### DreamTagging

Association between dreams and tags (many-to-many through model).

| Field | Type | Description |
|-------|------|-------------|
| dream | FK(Dream) | Tagged dream |
| tag | FK(DreamTag) | Applied tag |

### SharedDream

Tracks dream sharing with granular permissions.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| dream | FK(Dream) | Shared dream |
| shared_with | FK(User) | User the dream is shared with |
| permission | CharField | `view` or `comment` |

### DreamCollaborator

Collaboration roles for shared dreams.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| dream | FK(Dream) | Collaborative dream |
| user | FK(User) | Collaborator |
| role | CharField | `owner`, `collaborator`, or `viewer` |

### Dream

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| user | FK(User) | Dream owner |
| title | CharField(255) | Dream title |
| description | TextField | Detailed description |
| category | CharField(50) | Category (career, health, etc.) |
| target_date | DateTime | Target completion date |
| priority | Integer | Priority level (1-5) |
| status | CharField | active, completed, paused, archived |
| ai_analysis | JSONField | AI analysis of the dream |
| vision_image_url | URLField | Vision board image (DALL-E) |
| progress_percentage | Float | Progress percentage |
| has_two_minute_start | Boolean | Whether a 2-minute start exists |

### Goal

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| dream | FK(Dream) | Parent dream |
| title | CharField(255) | Goal title |
| description | TextField | Description |
| order | Integer | Order in the sequence |
| estimated_minutes | Integer | Estimated duration |
| scheduled_start/end | DateTime | Scheduling |
| status | CharField | pending, in_progress, completed, skipped |
| reminder_enabled | Boolean | Reminders enabled |
| progress_percentage | Float | Progress |

### Task

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| goal | FK(Goal) | Parent goal |
| title | CharField(255) | Task title |
| description | TextField | Description |
| order | Integer | Order within the goal |
| scheduled_date | DateTime | Scheduled date |
| scheduled_time | CharField(5) | Time (HH:MM) |
| duration_mins | Integer | Duration in minutes |
| recurrence | JSONField | Recurrence pattern |
| status | CharField | pending, completed, skipped |
| is_two_minute_start | Boolean | 2-minute start task |

### Obstacle

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| dream | FK(Dream) | Associated dream |
| title | CharField(255) | Obstacle title |
| description | TextField | Description |
| obstacle_type | CharField | predicted, actual |
| solution | TextField | AI solution |
| status | CharField | active, resolved, ignored |

## API Endpoints

### Dreams
- `GET /api/dreams/` - List dreams
- `POST /api/dreams/` - Create a dream
- `GET /api/dreams/{id}/` - Dream detail
- `PUT /api/dreams/{id}/` - Update a dream
- `DELETE /api/dreams/{id}/` - Delete a dream
- `POST /api/dreams/{id}/analyze/` - AI analysis of the dream
- `POST /api/dreams/{id}/generate-plan/` - Generate a GPT-4 plan
- `POST /api/dreams/{id}/generate-vision/` - Generate DALL-E vision board
- `POST /api/dreams/{id}/generate-two-minute-start/` - Generate micro-action
- `POST /api/dreams/{id}/duplicate/` - Duplicate a dream with all its goals and tasks
- `GET /api/dreams/{id}/export-pdf/` - Export dream as PDF (includes goals, tasks, progress)

### Dream Templates
- `GET /api/dream-templates/` - Browse available dream templates
- `GET /api/dream-templates/featured/` - Get featured templates
- `POST /api/dream-templates/{id}/use/` - Create a new dream from a template

### Dream Tags
- `GET /api/dream-tags/` - List custom tags
- `POST /api/dream-tags/` - Create a custom tag
- `POST /api/dreams/{id}/tag/` - Add a tag to a dream
- `DELETE /api/dreams/{id}/tag/{tag_id}/` - Remove a tag from a dream

### Dream Sharing
- `POST /api/dreams/{id}/share/` - Share a dream with another user (view/comment permissions)
- `GET /api/dreams/shared-with-me/` - List dreams shared with the current user
- `POST /api/dreams/{id}/collaborators/` - Add a collaborator (owner/collaborator/viewer roles)
- `GET /api/dreams/{id}/collaborators/` - List collaborators on a dream
- `DELETE /api/dreams/{id}/collaborators/{user_id}/` - Remove a collaborator

### Goals
- `GET /api/dreams/{dream_id}/goals/` - List goals
- `POST /api/dreams/{dream_id}/goals/` - Create a goal
- `GET /api/goals/{id}/` - Goal detail
- `PUT /api/goals/{id}/` - Update a goal
- `DELETE /api/goals/{id}/` - Delete a goal
- `POST /api/goals/{id}/complete/` - Mark as completed

### Tasks
- `GET /api/goals/{goal_id}/tasks/` - List tasks
- `POST /api/goals/{goal_id}/tasks/` - Create a task
- `GET /api/tasks/{id}/` - Task detail
- `PUT /api/tasks/{id}/` - Update a task
- `DELETE /api/tasks/{id}/` - Delete a task
- `POST /api/tasks/{id}/complete/` - Mark as completed (awards XP)

### Obstacles
- `GET /api/dreams/{dream_id}/obstacles/` - List obstacles
- `POST /api/dreams/{dream_id}/obstacles/` - Create an obstacle
- `POST /api/obstacles/{id}/resolve/` - Mark as resolved

## Serializers

- `DreamSerializer` - Full serialization with nested goals
- `DreamListSerializer` - Lightweight version for lists
- `GoalSerializer` - With nested tasks
- `TaskSerializer` - Full serialization
- `ObstacleSerializer` - With AI solution

## Permissions

- `IsAuthenticated` - All views require authentication
- `IsOwner` - Verifies the user owns the dream

## Gamification

- Completing a **Task**: 10-100 XP (based on duration)
- Completing a **Goal**: 100 XP
- Completing a **Dream**: 500 XP
- Streaks are updated on each task completion

## Testing

```bash
# Run app tests
python manage.py test apps.dreams

# With coverage
pytest apps/dreams/tests.py -v --cov=apps.dreams
```

## Configuration

Environment variables used:
- `OPENAI_API_KEY` - For plan generation and analysis
- `OPENAI_MODEL` - GPT model to use (default: gpt-4-turbo-preview)

## Celery Tasks

- `generate_dream_plan` - AI plan generation (async)
- `generate_two_minute_start` - Micro-action generation (async)
- `generate_vision_board` - DALL-E image generation (async)
- `analyze_dream` - AI analysis of the dream (async)
- `predict_obstacles` - Obstacle prediction (async)
- `auto_schedule_tasks` - Automatic task scheduling
- `smart_archive_dreams` - Automatically archives stale/inactive dreams based on configurable criteria
- `send_milestone_notifications` - Sends notifications when users reach dream milestones (25%, 50%, 75%, 100% completion)
