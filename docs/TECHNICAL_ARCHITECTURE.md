# Technical Architecture - DreamPlanner

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTS                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Web App     │  │  Mobile App  │  │  API Clients │          │
│  │  (Frontend)  │  │  (external)  │  │  (third-party)│          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼───────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │ HTTPS/WSS
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LOAD BALANCER                                 │
│              (AWS ALB + CloudFront CDN)                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│   Auth      │   │  Django API │   │  WebSocket  │
│  Service    │   │   (REST)    │   │  (Channels) │
│(dj-rest-auth│   │  Gunicorn   │   │   Daphne    │
└─────────────┘   └──────┬──────┘   └──────┬──────┘
                         │                  │
        ┌────────────────┼──────────────────┘
        │                │
        ▼                ▼                  ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ PostgreSQL  │   │    Redis    │   │   Celery    │
│   (RDS)     │   │   (Cache)   │   │  Workers    │
└─────────────┘   └─────────────┘   └──────┬──────┘
                                            │
                          ┌─────────────────┼─────────────────┐
                          ▼                 ▼                 ▼
                   ┌─────────────┐                     ┌─────────────┐
                   │  OpenAI API │                     │   AWS S3    │
                   │   (GPT-4)   │                     │   (Media)   │
                   └─────────────┘                     └─────────────┘
```

## 2. Detailed Tech Stack

### 2.1 Backend Services (Django)

```json
{
  "framework": "Django 5.0.1",
  "language": "Python 3.11",
  "api": "Django REST Framework 3.14.0",
  "orm": "Django ORM",
  "validation": "DRF Serializers",
  "authentication": "dj-rest-auth + django-allauth (Token auth)",
  "websocket": "Django Channels 4.0.0",
  "background_jobs": "Celery 5.3.4",
  "broker": "Redis",
  "server": "Gunicorn (HTTP) + Daphne (WebSocket)",
  "testing": "pytest + pytest-django + pytest-cov"
}
```

### 2.2 Database

**PostgreSQL 15** - Primary data:
- Users (User, GamificationProfile, BuddyPairing, Badge)
- Dreams and goals (Dream, Goal, Task, Obstacle)
- AI Conversations (Conversation, Message)
- Notifications (Notification, NotificationTemplate)

**Redis 7** - Cache and real-time:
- WebSocket sessions (Channels layer)
- AI response cache
- Celery queue (broker + result backend)
- Rate limiting
- Session data

### 2.3 Cloud Services

| Service | Provider | Usage |
|---------|----------|-------|
| Backend Hosting | AWS ECS (Fargate) | Django Containers |
| Database | AWS RDS PostgreSQL | Database |
| Cache | AWS ElastiCache Redis | Cache + Celery |
| Storage | AWS S3 | Vision boards, media |
| CDN | CloudFront | Static assets |
| Load Balancer | AWS ALB | Traffic distribution |
| Authentication | dj-rest-auth + allauth | Authentication |
| AI | OpenAI GPT-4 + DALL-E 3 | Conversational AI |
| Monitoring | Sentry | Error tracking |
| Logs | CloudWatch | Centralized logging |

## 3. Django Data Model

### 3.1 Database Schema

```python
# users/models.py

class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    timezone = models.CharField(max_length=50, default='Europe/Paris')

    # Subscription
    subscription = models.CharField(max_length=20, choices=SUBSCRIPTION_CHOICES, default='free')
    subscription_ends = models.DateTimeField(null=True, blank=True)

    # Gamification
    xp = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    streak_days = models.IntegerField(default=0)
    last_activity = models.DateTimeField(auto_now=True)

    # JSON preferences
    work_schedule = models.JSONField(null=True, blank=True)
    notification_prefs = models.JSONField(null=True, blank=True)
    app_prefs = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class GamificationProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    xp = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    attributes = models.JSONField(default=dict)  # health, career, education, etc.

class BuddyPairing(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buddy_requests')
    buddy = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buddies')
    status = models.CharField(max_length=20, default='pending')  # pending, active, ended
    matched_at = models.DateTimeField(auto_now_add=True)

class Badge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='badges')
    badge_type = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon_url = models.URLField(blank=True)
    is_claimed = models.BooleanField(default=False)
    earned_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
```

```python
# dreams/models.py

class Dream(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dreams')

    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=50, blank=True)
    target_date = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(default=1)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    progress_percentage = models.FloatField(default=0.0)

    ai_analysis = models.JSONField(null=True, blank=True)
    has_two_minute_start = models.BooleanField(default=False)
    vision_image_url = models.URLField(max_length=500, blank=True)

    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Goal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name='goals')

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.IntegerField()

    estimated_minutes = models.IntegerField(null=True)
    scheduled_start = models.DateTimeField(null=True)
    scheduled_end = models.DateTimeField(null=True)

    status = models.CharField(max_length=20, default='pending')
    completed_at = models.DateTimeField(null=True)

    reminder_enabled = models.BooleanField(default=True)
    reminder_time = models.DateTimeField(null=True)

class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='tasks')

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.IntegerField()

    scheduled_date = models.DateTimeField(null=True)
    scheduled_time = models.CharField(max_length=5, blank=True)
    duration_mins = models.IntegerField(null=True)

    recurrence = models.JSONField(null=True)
    status = models.CharField(max_length=20, default='pending')
    completed_at = models.DateTimeField(null=True)

class Obstacle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    dream = models.ForeignKey(Dream, on_delete=models.CASCADE, related_name='obstacles')

    title = models.CharField(max_length=255)
    description = models.TextField()
    type = models.CharField(max_length=20)  # predicted, actual
    likelihood = models.CharField(max_length=20, blank=True)  # low, medium, high

    ai_suggested_solution = models.TextField(blank=True)
    encountered = models.BooleanField(default=False)
    encountered_at = models.DateTimeField(null=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True)
    resolution_notes = models.TextField(blank=True)
```

```python
# conversations/models.py

class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')

    conversation_type = models.CharField(max_length=50, default='general')
    title = models.CharField(max_length=255, blank=True)
    context = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')

    role = models.CharField(max_length=20)  # user, assistant, system
    content = models.TextField()
    metadata = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
```

```python
# notifications/models.py

class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')

    notification_type = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(null=True, blank=True)

    scheduled_for = models.DateTimeField()
    sent_at = models.DateTimeField(null=True)
    read_at = models.DateTimeField(null=True)

    status = models.CharField(max_length=20, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)

class NotificationTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    notification_type = models.CharField(max_length=50)
    title_template = models.CharField(max_length=255)
    body_template = models.TextField()
    is_active = models.BooleanField(default=True)
```

## 4. Django REST Framework API Endpoints

### Base URL
- **Development**: `http://localhost:8000/api`
- **Production**: `https://api.dreamplanner.app/api`

### 4.1 Authentication (dj-rest-auth)
```
All API requests require a token in the header:
Authorization: Token <key>
or
Authorization: Bearer <key>
```

### 4.2 Users
```
GET    /api/users/me/                      # Current user profile
PUT    /api/users/me/                      # Update profile
PATCH  /api/users/me/                      # Partially update profile
POST   /api/users/me/update-preferences/  # Update preferences
GET    /api/users/me/stats/                # User statistics
```

### 4.3 Dreams (Dreams/Goals)
```
GET    /api/dreams/                        # List dreams
POST   /api/dreams/                        # Create a dream
GET    /api/dreams/{id}/                   # Dream detail
PUT    /api/dreams/{id}/                   # Update a dream
PATCH  /api/dreams/{id}/                   # Partially update a dream
DELETE /api/dreams/{id}/                   # Delete a dream
POST   /api/dreams/{id}/analyze/           # Analyze with AI (GPT-4)
POST   /api/dreams/{id}/generate-plan/     # Generate full plan with AI
POST   /api/dreams/{id}/generate-two-minute-start/  # Create startup micro-action
POST   /api/dreams/{id}/generate-vision/   # Generate vision board (DALL-E)
```

### 4.4 Goals & Tasks
```
GET    /api/dreams/{dream_id}/goals/       # List goals
POST   /api/dreams/{dream_id}/goals/       # Create a goal
GET    /api/goals/{id}/                    # Goal detail
PUT    /api/goals/{id}/                    # Update a goal
DELETE /api/goals/{id}/                    # Delete a goal
POST   /api/goals/{id}/complete/           # Mark as completed (XP)

GET    /api/goals/{goal_id}/tasks/         # List tasks
POST   /api/goals/{goal_id}/tasks/         # Create a task
GET    /api/tasks/{id}/                    # Task detail
PUT    /api/tasks/{id}/                    # Update a task
DELETE /api/tasks/{id}/                    # Delete a task
POST   /api/tasks/{id}/complete/           # Mark as completed (XP + streak)
POST   /api/tasks/{id}/reschedule/         # Reschedule a task
```

### 4.5 Conversations (AI Chat)
```
GET    /api/conversations/                 # List conversations
POST   /api/conversations/                 # New conversation
GET    /api/conversations/{id}/            # Conversation detail
GET    /api/conversations/{id}/messages/   # Conversation messages
POST   /api/conversations/{id}/messages/   # Send a message (GPT-4)
DELETE /api/conversations/{id}/            # Delete conversation
```

### 4.6 WebSocket (Real-time Chat)
```
ws://localhost:9000/ws/conversations/{conversation_id}/
wss://api.dreamplanner.app/ws/conversations/{conversation_id}/

Messages:
- Send: {"type": "message", "message": "Hello AI"}
- Receive streaming:
  {"type": "stream_start"}
  {"type": "stream_chunk", "chunk": "Hello"}
  {"type": "stream_end"}
  {"type": "message", "message": {...}}
- Typing: {"type": "typing", "is_typing": true}
```

### 4.7 Calendar
```
GET    /api/calendar/                      # Calendar view (query: start_date, end_date)
GET    /api/calendar/today/                # Today's tasks
GET    /api/calendar/week/                 # Weekly view
GET    /api/calendar/month/                # Monthly view
GET    /api/calendar/overdue/              # Overdue tasks
POST   /api/calendar/reschedule/           # Reschedule multiple tasks
POST   /api/calendar/auto-schedule/        # AI auto-scheduling
```

### 4.8 Notifications
```
GET    /api/notifications/                 # List notifications
GET    /api/notifications/{id}/            # Notification detail
POST   /api/notifications/{id}/mark_read/  # Mark as read
POST   /api/notifications/mark_all_read/   # Mark all as read
GET    /api/notifications/unread_count/    # Unread count
```

### 4.9 Health Checks
```
GET    /health/                            # General health check
GET    /health/liveness/                   # Liveness probe (K8s)
GET    /health/readiness/                  # Readiness probe (DB check)
```

## 5. OpenAI GPT-4 Integration

### 5.1 Django Integration Service

```python
# openai_service.py

import openai
from django.conf import settings

openai.api_key = settings.OPENAI_API_KEY

class OpenAIService:
    SYSTEM_PROMPTS = {
        'dream_creation': """You are DreamPlanner, a caring assistant that helps users achieve their dreams.

YOUR ROLE:
1. Listen carefully to dreams and goals
2. Ask relevant questions to understand well
3. Break down large goals into achievable steps
4. Create a realistic schedule accounting for constraints
5. Motivate and encourage without being condescending

RULES:
- Ask for clarification if the goal is vague
- Suggest realistic deadlines
- Account for work-life balance
- Include breaks and rest time
- Be encouraging but honest about feasibility""",

        'planning': """You are a planning expert. Generate a detailed and realistic plan.""",

        'motivation': """You generate short and personalized motivational messages.""",

        'coaching': """You analyze activity patterns and suggest adjustments.""",

        'rescue': """You create caring messages to re-engage inactive users."""
    }

    def chat(self, messages, conversation_type='general'):
        """Synchronous chat with GPT-4"""
        system_prompt = self.SYSTEM_PROMPTS.get(conversation_type, self.SYSTEM_PROMPTS['dream_creation'])

        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                *messages
            ],
            temperature=0.7,
            max_tokens=2000
        )

        return response.choices[0].message.content

    async def chat_stream_async(self, messages, conversation_type='general'):
        """Asynchronous chat with streaming for WebSocket"""
        system_prompt = self.SYSTEM_PROMPTS.get(conversation_type, self.SYSTEM_PROMPTS['dream_creation'])

        response = await client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                *messages
            ],
            temperature=0.7,
            stream=True
        )

        async for chunk in response:
            content = chunk.choices[0].delta.get('content', '')
            if content:
                yield content

    def generate_plan(self, dream, user):
        """Generate a complete plan with goals and tasks"""
        prompt = f"""
Generate a detailed plan to achieve this goal:

DREAM/GOAL: {dream.title}
DESCRIPTION: {dream.description}
TARGET DATE: {dream.target_date or 'Not specified'}
CATEGORY: {dream.category}

User context:
- Work schedule: {user.work_schedule}
- Timezone: {user.timezone}

Respond ONLY with a structured JSON containing:
{{
  "analysis": "Dream analysis",
  "feasibility": "high|medium|low",
  "goals": [
    {{
      "title": "Step title",
      "description": "Description",
      "order": 0,
      "tasks": [
        {{"title": "Task", "order": 0, "duration": 30}}
      ]
    }}
  ]
}}
"""

        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': self.SYSTEM_PROMPTS['planning']},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.5,
            response_format={'type': 'json_object'}
        )

        return json.loads(response.choices[0].message.content)

    def generate_motivational_message(self, user):
        """Personalized daily motivational message"""
        prompt = f"""Generate a short motivational message (max 150 characters) for {user.display_name}.
        Context: XP={user.xp}, Level={user.level}, Streak={user.streak_days} days"""

        response = client.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=[
                {'role': 'system', 'content': self.SYSTEM_PROMPTS['motivation']},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.8,
            max_tokens=50
        )

        return response.choices[0].message.content

    def generate_two_minute_start(self, dream):
        """Generate a startup micro-action (2 minutes max)"""
        prompt = f"""For the goal "{dream.title}", generate ONE very simple micro-action
        that takes 30 seconds to 2 minutes maximum. Respond only with the action,
        without quotes or formatting."""

        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': 'You suggest ultra-simple micro-actions.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.7,
            max_tokens=50
        )

        return response.choices[0].message.content

    def generate_vision_board_image(self, dream):
        """Generate a vision board image with DALL-E 3"""
        prompt = f"""Create an inspiring, photorealistic image representing someone
        who has achieved: {dream.title}. Focus on success, happiness, and fulfillment."""

        response = openai.Image.create(
            model='dall-e-3',
            prompt=prompt,
            size='1024x1024',
            quality='standard',
            n=1
        )

        return response.data[0].url

    def generate_rescue_message(self, user):
        """Re-engagement message for inactive users (Rescue Mode)"""
        recent_dream = user.dreams.filter(status='active').order_by('-updated_at').first()

        prompt = f"""Generate a caring message to re-engage {user.display_name}
        who has not been active for a few days. Their goal: "{recent_dream.title if recent_dream else 'their dreams'}".
        Be encouraging and understanding. Max 200 characters."""

        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': self.SYSTEM_PROMPTS['rescue']},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.8,
            max_tokens=100
        )

        return response.choices[0].message.content

    def predict_obstacles(self, dream):
        """Obstacle prediction with solution suggestions"""
        prompt = f"""For the goal "{dream.title}: {dream.description}",
        predict 3-5 potential obstacles with their solutions.
        Respond in JSON: [{{"title": "...", "description": "...", "likelihood": "high|medium|low", "solution": "..."}}]"""

        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': 'You predict obstacles and propose solutions.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.6,
            response_format={'type': 'json_object'}
        )

        result = json.loads(response.choices[0].message.content)
        return result.get('obstacles', [])

    def generate_task_adjustments(self, user, tasks, completion_rate):
        """Analyze patterns and suggest adjustments (Proactive AI Coach)"""
        prompt = f"""The user has a completion rate of {completion_rate}% on {len(tasks)} tasks.
        Analyze and suggest 3 concrete adjustments to improve productivity.
        JSON: {{"summary": "...", "detailed": ["suggestion1", "suggestion2", "suggestion3"]}}"""

        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': self.SYSTEM_PROMPTS['coaching']},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.7,
            response_format={'type': 'json_object'}
        )

        return json.loads(response.choices[0].message.content)

    def generate_weekly_report(self, user, completed_tasks, total_tasks, xp_gained):
        """Generate personalized weekly report"""
        prompt = f"""Generate an encouraging weekly report for {user.display_name}.
        Stats: {completed_tasks}/{total_tasks} tasks, +{xp_gained} XP.
        Max 250 characters."""

        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': 'You generate encouraging weekly reports.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )

        return response.choices[0].message.content
```

## 6. Notification System with Celery

### 6.1 Periodic Celery Tasks

```python
# celery.py (config/celery.py)

from celery import Celery
from celery.schedules import crontab

app = Celery('dreamplanner')
app.config_from_object('django.conf:settings', namespace='CELERY')

app.conf.beat_schedule = {
    # Process pending notifications (every minute)
    'process-pending-notifications': {
        'task': 'notifications.tasks.process_pending_notifications',
        'schedule': 60.0,
    },

    # Task reminders (every 15 minutes)
    'send-reminder-notifications': {
        'task': 'notifications.tasks.send_reminder_notifications',
        'schedule': 900.0,
    },

    # Daily motivational message (8 AM)
    'generate-daily-motivation': {
        'task': 'notifications.tasks.generate_daily_motivation',
        'schedule': crontab(hour=8, minute=0),
    },

    # Rescue Mode - inactive users (9 AM)
    'check-inactive-users': {
        'task': 'notifications.tasks.check_inactive_users',
        'schedule': crontab(hour=9, minute=0),
    },

    # Weekly report (Sunday 10 AM)
    'send-weekly-report': {
        'task': 'notifications.tasks.send_weekly_report',
        'schedule': crontab(day_of_week=0, hour=10, minute=0),
    },

    # Update dream progress (3 AM)
    'update-dream-progress': {
        'task': 'dreams.tasks.update_dream_progress',
        'schedule': crontab(hour=3, minute=0),
    },

    # Check overdue tasks (10 AM)
    'check-overdue-tasks': {
        'task': 'dreams.tasks.check_overdue_tasks',
        'schedule': crontab(hour=10, minute=0),
    },

    # Clean up old notifications (Monday 2 AM)
    'cleanup-old-notifications': {
        'task': 'notifications.tasks.cleanup_old_notifications',
        'schedule': crontab(day_of_week=1, hour=2, minute=0),
    },

    # Archive abandoned dreams (Sunday 3 AM)
    'cleanup-abandoned-dreams': {
        'task': 'dreams.tasks.cleanup_abandoned_dreams',
        'schedule': crontab(day_of_week=0, hour=3, minute=0),
    },
}
```

### 6.2 Notification Types

| Type | Trigger | Example | Celery Task |
|------|---------|---------|-------------|
| `reminder` | Scheduled task | "It's time to practice English!" | `send_reminder_notifications` |
| `motivation` | Daily 8 AM | "You've already completed 3 tasks this week!" | `generate_daily_motivation` |
| `progress` | Milestone reached | "50% of your goal achieved!" | Triggered by completion |
| `achievement` | Badge unlocked | "Badge 'Regular' earned!" | Triggered by XP/streak |
| `rescue` | Inactivity 3+ days | "We're still here for you!" | `check_inactive_users` |
| `weekly_report` | Sunday 10 AM | "Your weekly report" | `send_weekly_report` |
| `task_created` | 2-minute start generated | "Ready to get started in 2 minutes?" | `generate_two_minute_start` |
| `vision_ready` | DALL-E image generated | "Your vision is ready!" | `generate_vision_board` |
| `coaching` | Completion rate < 50% | "Suggestions for better success" | `suggest_task_adjustments` |

## 7. WebSocket with Django Channels

### 7.1 ASGI Configuration

```python
# asgi.py (config/asgi.py)

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from conversations.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
```

### 7.2 WebSocket Consumer

```python
# conversations/consumers.py

from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'conversation_{self.conversation_id}'
        self.user = self.scope['user']

        # Check access
        has_access = await self.check_conversation_access()
        if not has_access:
            await self.close(code=4003)
            return

        # Join group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'conversation_id': self.conversation_id
        }))

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'message')

        if message_type == 'message':
            await self.handle_message(data)
        elif message_type == 'typing':
            await self.handle_typing(data)

    async def handle_message(self, data):
        message_content = data.get('message', '').strip()

        # Save user message
        user_message = await self.save_message('user', message_content)

        # Broadcast user message
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': str(user_message.id),
                    'role': 'user',
                    'content': message_content,
                    'created_at': user_message.created_at.isoformat()
                }
            }
        )

        # Get AI response via streaming
        await self.get_ai_response_stream(message_content)

    async def get_ai_response_stream(self, user_message):
        conversation = await self.get_conversation()
        messages = await self.get_messages_for_api(conversation)

        ai_service = OpenAIService()

        # Indicate streaming start
        await self.send(text_data=json.dumps({'type': 'stream_start'}))

        # Stream AI response
        full_response = ""
        async for chunk in ai_service.chat_stream_async(
            messages=messages,
            conversation_type=conversation.conversation_type
        ):
            full_response += chunk
            await self.send(text_data=json.dumps({
                'type': 'stream_chunk',
                'chunk': chunk
            }))

        # End of streaming
        await self.send(text_data=json.dumps({'type': 'stream_end'}))

        # Save complete response
        assistant_message = await self.save_message('assistant', full_response)

        # Broadcast complete message
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': str(assistant_message.id),
                    'role': 'assistant',
                    'content': full_response,
                    'created_at': assistant_message.created_at.isoformat()
                }
            }
        )
```

## 8. AWS Deployment

### 8.1 Production Architecture

```
CloudFront (CDN)
    ↓
ALB (Load Balancer)
    ↓
┌─────────────────────────────────────────┐
│  ECS Cluster (Fargate)                  │
│  ┌──────────┐  ┌──────────┐  ┌────────┐│
│  │ Django   │  │ Daphne   │  │ Celery ││
│  │ (HTTP)   │  │ (WebSoc) │  │ Worker ││
│  │ x3       │  │ x2       │  │ x2     ││
│  └──────────┘  └──────────┘  └────────┘│
└─────────────────────────────────────────┘
    │           │           │
    ▼           ▼           ▼
┌─────────┐  ┌───────────┐  ┌──────┐
│ RDS     │  │ElastiCache│  │  S3  │
│(Postgres│  │  (Redis)  │  │(Media│
│  Multi  │  │  Cluster  │  │Files)│
│   AZ)   │  └───────────┘  └──────┘
└─────────┘
```

### 8.2 AWS Services Used

- **ECS Fargate**: Django containers (HTTP + WebSocket + Celery)
- **RDS PostgreSQL**: Multi-AZ for high availability
- **ElastiCache Redis**: Cluster mode for Channels + Celery
- **S3**: Vision boards and user media
- **ALB**: Load balancer with health checks
- **CloudFront**: CDN for static files
- **CloudWatch**: Logs and monitoring
- **Secrets Manager**: Secrets management
- **ECR**: Private Docker registry

## 9. Directory Structure

```
dreamplanner/
├── config/                       # Django Configuration
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   │   └── testing.py
│   ├── urls.py
│   ├── asgi.py                  # WebSocket config
│   ├── wsgi.py                  # HTTP config
│   └── celery.py                # Celery config
│
├── apps/                         # Django Applications
│   ├── users/                   # User management
│   ├── dreams/                  # Dreams, Goals, Tasks
│   ├── conversations/           # AI Chat (WebSocket)
│   ├── notifications/           # Push notifications
│   └── calendar/                # Calendar views
│
├── core/                         # Core utilities
│   ├── authentication.py        # Token auth backend
│   ├── permissions.py           # DRF permissions
│   ├── exceptions.py            # Custom exceptions
│   └── pagination.py            # Pagination
│
├── integrations/                 # External services
│   ├── openai_service.py        # OpenAI GPT-4
│
├── requirements/                 # Python dependencies
│   ├── base.txt
│   ├── development.txt
│   ├── production.txt
│   └── testing.txt
│
├── docker/                       # Docker configuration
│   └── nginx.conf
│
├── docs/                         # Documentation
│   ├── TECHNICAL_ARCHITECTURE.md
│   ├── FEATURES_SPECIFICATIONS.md
│   ├── IMPROVEMENTS_STRATEGY.md
│   └── ...
│
├── .github/                      # CI/CD
│   └── workflows/
│
├── Dockerfile                   # Production image
├── docker-compose.yml           # Local dev
├── docker-compose.prod.yml      # Production
├── Makefile                     # Useful commands
├── pytest.ini                   # Test config
├── manage.py                    # Django CLI
└── README.md
```

## 10. Performance and Security

### 10.1 Performance Optimizations

- **Redis Caching**: API responses, sessions, rate limiting
- **Database Indexing**: Indexes on email, user_id, dates
- **Query Optimization**: select_related(), prefetch_related()
- **Connection Pooling**: PostgreSQL pooling via Django
- **Static Files**: Served via CloudFront CDN
- **Gunicorn Workers**: 4 workers + threads for concurrency
- **Celery**: Background tasks for heavy operations

### 10.2 Security

- ✅ **Token Authentication**: dj-rest-auth tokens verified server-side
- ✅ **HTTPS Only**: TLS 1.2+ in production
- ✅ **CORS**: Whitelisted allowed origins
- ✅ **SQL Injection**: Protection via Django ORM
- ✅ **XSS Protection**: Django middleware
- ✅ **CSRF Protection**: Django REST Framework
- ✅ **Rate Limiting**: Nginx + DRF throttling
- ✅ **Secrets Management**: AWS Secrets Manager
- ✅ **Container Security**: Non-root user in Docker
- ✅ **Security Headers**: Nginx config (HSTS, X-Frame-Options, etc.)
- ✅ **Input Validation**: DRF Serializers

### 10.3 Monitoring

- **Sentry**: Error tracking and performance monitoring
- **CloudWatch**: Centralized logs and metrics
- **Health Checks**: /health/, /health/liveness/, /health/readiness/
- **Flower**: Celery tasks monitoring
- **Database Metrics**: RDS Performance Insights

## 11. Tests

### 11.1 Test Stack

- **pytest**: Test framework
- **pytest-django**: Django plugin
- **pytest-cov**: Code coverage
- **pytest-asyncio**: Async tests (WebSocket)
- **Factory Boy**: Data fixtures
- **Coverage Target**: 84%

### 11.2 Test Types

```bash
# Unit tests
pytest -m unit

# Integration tests
pytest -m integration

# Async tests (WebSocket)
pytest -m asyncio

# Full coverage
pytest --cov --cov-report=html
```

---

**Architecture completed**: Django 5.0.1 + DRF 3.14.0 + Channels 4.0.0 + Celery 5.3.4
**Status**: ✅ Backend production-ready
**Last updated**: 2026-01-28
