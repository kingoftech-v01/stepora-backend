# Architecture Technique - DreamPlanner

## 1. Vue d'Ensemble de l'Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTS                                   │
│  ┌──────────────┐                    ┌──────────────┐           │
│  │   iOS App    │                    │  Android App │           │
│  │ React Native │                    │ React Native │           │
│  └──────┬───────┘                    └──────┬───────┘           │
└─────────┼───────────────────────────────────┼───────────────────┘
          │                                   │
          └───────────────┬───────────────────┘
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
│  (Firebase) │   │  Gunicorn   │   │   Daphne    │
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
                   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
                   │  OpenAI API │   │ Firebase    │   │   AWS S3    │
                   │   (GPT-4)   │   │    FCM      │   │   (Media)   │
                   └─────────────┘   └─────────────┘   └─────────────┘
```

## 2. Stack Technique Détaillé

### 2.1 Application Mobile (Frontend)

```json
{
  "framework": "React Native 0.73+",
  "language": "TypeScript",
  "stateManagement": "Zustand",
  "navigation": "React Navigation 6",
  "ui": {
    "components": "React Native Paper / NativeBase",
    "icons": "React Native Vector Icons",
    "animations": "React Native Reanimated 3"
  },
  "networking": "Axios + React Query",
  "storage": "React Native MMKV",
  "calendar": "React Native Calendars",
  "notifications": "Notifee + Firebase"
}
```

### 2.2 Backend Services (Django)

```json
{
  "framework": "Django 5.0.1",
  "language": "Python 3.11",
  "api": "Django REST Framework 3.14.0",
  "orm": "Django ORM",
  "validation": "DRF Serializers",
  "authentication": "Firebase Admin SDK + Custom Django Backend",
  "websocket": "Django Channels 4.0.0",
  "background_jobs": "Celery 5.3.4",
  "broker": "Redis",
  "server": "Gunicorn (HTTP) + Daphne (WebSocket)",
  "testing": "pytest + pytest-django + pytest-cov"
}
```

### 2.3 Base de Données

**PostgreSQL 15** - Données principales:
- Utilisateurs (User, GamificationProfile, FcmToken, DreamBuddy, Badge)
- Rêves et objectifs (Dream, Goal, Task, Obstacle)
- Conversations IA (Conversation, Message)
- Notifications (Notification, NotificationTemplate)

**Redis 7** - Cache et temps réel:
- Sessions WebSocket (Channels layer)
- Cache des réponses IA
- File d'attente Celery (broker + result backend)
- Rate limiting
- Données de session

### 2.4 Services Cloud

| Service | Provider | Usage |
|---------|----------|-------|
| Hosting Backend | AWS ECS (Fargate) | Containers Django |
| Database | AWS RDS PostgreSQL | Base de données |
| Cache | AWS ElastiCache Redis | Cache + Celery |
| Storage | AWS S3 | Vision boards, médias |
| CDN | CloudFront | Assets statiques |
| Load Balancer | AWS ALB | Distribution du trafic |
| Push Notifications | Firebase FCM | Notifications mobiles |
| Authentication | Firebase Auth | Authentification |
| AI | OpenAI GPT-4 + DALL-E 3 | IA conversationnelle |
| Monitoring | Sentry | Error tracking |
| Logs | CloudWatch | Logging centralisé |

## 3. Modèle de Données Django

### 3.1 Schéma de Base de Données

```python
# apps/users/models.py

class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    firebase_uid = models.CharField(max_length=128, unique=True, db_index=True)
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

class FcmToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fcm_tokens')
    token = models.CharField(max_length=255)
    device_type = models.CharField(max_length=20)  # ios, android
    created_at = models.DateTimeField(auto_now_add=True)

class DreamBuddy(models.Model):
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
# apps/dreams/models.py

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
# apps/conversations/models.py

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
# apps/notifications/models.py

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

## 4. API Endpoints Django REST Framework

### Base URL
- **Development**: `http://localhost:8000/api`
- **Production**: `https://api.dreamplanner.app/api`

### 4.1 Authentication (Firebase)
```
Toutes les requêtes API nécessitent un token Firebase dans le header:
Authorization: Bearer <firebase_id_token>
```

### 4.2 Users
```
GET    /api/users/me/                      # Profil utilisateur actuel
PUT    /api/users/me/                      # Modifier profil
PATCH  /api/users/me/                      # Modifier partiellement
POST   /api/users/me/register-fcm-token/  # Enregistrer token FCM
POST   /api/users/me/update-preferences/  # Mettre à jour préférences
GET    /api/users/me/stats/                # Statistiques utilisateur
```

### 4.3 Dreams (Rêves/Objectifs)
```
GET    /api/dreams/                        # Liste des rêves
POST   /api/dreams/                        # Créer un rêve
GET    /api/dreams/{id}/                   # Détail d'un rêve
PUT    /api/dreams/{id}/                   # Modifier un rêve
PATCH  /api/dreams/{id}/                   # Modifier partiellement
DELETE /api/dreams/{id}/                   # Supprimer un rêve
POST   /api/dreams/{id}/analyze/           # Analyser avec IA (GPT-4)
POST   /api/dreams/{id}/generate-plan/     # Générer planning complet avec IA
POST   /api/dreams/{id}/generate-two-minute-start/  # Créer micro-action de démarrage
POST   /api/dreams/{id}/generate-vision/   # Générer vision board (DALL-E)
```

### 4.4 Goals & Tasks
```
GET    /api/dreams/{dream_id}/goals/       # Liste des objectifs
POST   /api/dreams/{dream_id}/goals/       # Créer un objectif
GET    /api/goals/{id}/                    # Détail d'un objectif
PUT    /api/goals/{id}/                    # Modifier un objectif
DELETE /api/goals/{id}/                    # Supprimer un objectif
POST   /api/goals/{id}/complete/           # Marquer comme terminé (XP)

GET    /api/goals/{goal_id}/tasks/         # Liste des tâches
POST   /api/goals/{goal_id}/tasks/         # Créer une tâche
GET    /api/tasks/{id}/                    # Détail d'une tâche
PUT    /api/tasks/{id}/                    # Modifier une tâche
DELETE /api/tasks/{id}/                    # Supprimer une tâche
POST   /api/tasks/{id}/complete/           # Marquer comme terminée (XP + streak)
POST   /api/tasks/{id}/reschedule/         # Replanifier une tâche
```

### 4.5 Conversations (Chat IA)
```
GET    /api/conversations/                 # Liste des conversations
POST   /api/conversations/                 # Nouvelle conversation
GET    /api/conversations/{id}/            # Détail conversation
GET    /api/conversations/{id}/messages/   # Messages d'une conversation
POST   /api/conversations/{id}/messages/   # Envoyer un message (GPT-4)
DELETE /api/conversations/{id}/            # Supprimer conversation
```

### 4.6 WebSocket (Chat en temps réel)
```
ws://localhost:9000/ws/conversations/{conversation_id}/
wss://api.dreamplanner.app/ws/conversations/{conversation_id}/

Messages:
- Envoi: {"type": "message", "message": "Bonjour IA"}
- Réception streaming:
  {"type": "stream_start"}
  {"type": "stream_chunk", "chunk": "Bonjour"}
  {"type": "stream_end"}
  {"type": "message", "message": {...}}
- Typing: {"type": "typing", "is_typing": true}
```

### 4.7 Calendar
```
GET    /api/calendar/                      # Vue calendrier (query: start_date, end_date)
GET    /api/calendar/today/                # Tâches du jour
GET    /api/calendar/week/                 # Vue hebdomadaire
GET    /api/calendar/month/                # Vue mensuelle
GET    /api/calendar/overdue/              # Tâches en retard
POST   /api/calendar/reschedule/           # Replanifier plusieurs tâches
POST   /api/calendar/auto-schedule/        # Auto-planification IA
```

### 4.8 Notifications
```
GET    /api/notifications/                 # Liste des notifications
GET    /api/notifications/{id}/            # Détail notification
POST   /api/notifications/{id}/mark_read/  # Marquer comme lue
POST   /api/notifications/mark_all_read/   # Tout marquer comme lu
GET    /api/notifications/unread_count/    # Nombre de non-lues
```

### 4.9 Health Checks
```
GET    /health/                            # Health check général
GET    /health/liveness/                   # Liveness probe (K8s)
GET    /health/readiness/                  # Readiness probe (DB check)
```

## 5. Intégration OpenAI GPT-4

### 5.1 Service d'Intégration Django

```python
# integrations/openai_service.py

import openai
from django.conf import settings

openai.api_key = settings.OPENAI_API_KEY

class OpenAIService:
    SYSTEM_PROMPTS = {
        'dream_creation': """Tu es DreamPlanner, un assistant bienveillant qui aide les utilisateurs à réaliser leurs rêves.

TON RÔLE:
1. Écouter attentivement les rêves et objectifs
2. Poser des questions pertinentes pour bien comprendre
3. Décomposer les grands objectifs en étapes réalisables
4. Créer un planning réaliste tenant compte des contraintes
5. Motiver et encourager sans être condescendant

RÈGLES:
- Demander des précisions si l'objectif est vague
- Proposer des délais réalistes
- Tenir compte de l'équilibre vie pro/perso
- Inclure des pauses et temps de repos
- Être encourageant mais honnête sur la faisabilité""",

        'planning': """Tu es expert en planification. Génère un plan détaillé et réaliste.""",

        'motivation': """Tu génères des messages de motivation courts et personnalisés.""",

        'coaching': """Tu analyses les patterns d'activité et suggères des ajustements.""",

        'rescue': """Tu créés des messages bienveillants pour réengager les utilisateurs inactifs."""
    }

    def chat(self, messages, conversation_type='general'):
        """Chat synchrone avec GPT-4"""
        system_prompt = self.SYSTEM_PROMPTS.get(conversation_type, self.SYSTEM_PROMPTS['dream_creation'])

        response = openai.ChatCompletion.create(
            model='gpt-4-turbo-preview',
            messages=[
                {'role': 'system', 'content': system_prompt},
                *messages
            ],
            temperature=0.7,
            max_tokens=2000
        )

        return response.choices[0].message.content

    async def chat_stream_async(self, messages, conversation_type='general'):
        """Chat asynchrone avec streaming pour WebSocket"""
        system_prompt = self.SYSTEM_PROMPTS.get(conversation_type, self.SYSTEM_PROMPTS['dream_creation'])

        response = await openai.ChatCompletion.acreate(
            model='gpt-4-turbo-preview',
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
        """Génère un plan complet avec goals et tasks"""
        prompt = f"""
Génère un plan détaillé pour atteindre cet objectif:

RÊVE/OBJECTIF: {dream.title}
DESCRIPTION: {dream.description}
DATE CIBLE: {dream.target_date or 'Non spécifiée'}
CATÉGORIE: {dream.category}

Contexte utilisateur:
- Horaires de travail: {user.work_schedule}
- Timezone: {user.timezone}

Réponds UNIQUEMENT avec un JSON structuré contenant:
{{
  "analysis": "Analyse du rêve",
  "feasibility": "high|medium|low",
  "goals": [
    {{
      "title": "Titre de l'étape",
      "description": "Description",
      "order": 0,
      "tasks": [
        {{"title": "Tâche", "order": 0, "duration": 30}}
      ]
    }}
  ]
}}
"""

        response = openai.ChatCompletion.create(
            model='gpt-4-turbo-preview',
            messages=[
                {'role': 'system', 'content': self.SYSTEM_PROMPTS['planning']},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.5,
            response_format={'type': 'json_object'}
        )

        return json.loads(response.choices[0].message.content)

    def generate_motivational_message(self, user):
        """Message de motivation quotidien personnalisé"""
        prompt = f"""Génère un message de motivation court (max 150 caractères) pour {user.display_name}.
        Contexte: XP={user.xp}, Niveau={user.level}, Série={user.streak_days} jours"""

        response = openai.ChatCompletion.create(
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
        """Génère une micro-action de démarrage (2 minutes max)"""
        prompt = f"""Pour l'objectif "{dream.title}", génère UNE micro-action très simple
        qui prend 30 secondes à 2 minutes maximum. Réponds uniquement avec l'action,
        sans guillemets ni formatage."""

        response = openai.ChatCompletion.create(
            model='gpt-4-turbo-preview',
            messages=[
                {'role': 'system', 'content': 'Tu suggères des micro-actions ultra-simples.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.7,
            max_tokens=50
        )

        return response.choices[0].message.content

    def generate_vision_board_image(self, dream):
        """Génère une image de vision board avec DALL-E 3"""
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
        """Message de réengagement pour utilisateurs inactifs (Rescue Mode)"""
        recent_dream = user.dreams.filter(status='active').order_by('-updated_at').first()

        prompt = f"""Génère un message bienveillant pour réengager {user.display_name}
        qui n'a pas été actif depuis quelques jours. Son objectif: "{recent_dream.title if recent_dream else 'ses rêves'}".
        Sois encourageant et compréhensif. Max 200 caractères."""

        response = openai.ChatCompletion.create(
            model='gpt-4-turbo-preview',
            messages=[
                {'role': 'system', 'content': self.SYSTEM_PROMPTS['rescue']},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.8,
            max_tokens=100
        )

        return response.choices[0].message.content

    def predict_obstacles(self, dream):
        """Prédiction d'obstacles avec suggestions de solutions"""
        prompt = f"""Pour l'objectif "{dream.title}: {dream.description}",
        prédis 3-5 obstacles potentiels avec leurs solutions.
        Réponds en JSON: [{{"title": "...", "description": "...", "likelihood": "high|medium|low", "solution": "..."}}]"""

        response = openai.ChatCompletion.create(
            model='gpt-4-turbo-preview',
            messages=[
                {'role': 'system', 'content': 'Tu prédis des obstacles et proposes des solutions.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.6,
            response_format={'type': 'json_object'}
        )

        result = json.loads(response.choices[0].message.content)
        return result.get('obstacles', [])

    def generate_task_adjustments(self, user, tasks, completion_rate):
        """Analyse patterns et suggère des ajustements (Proactive AI Coach)"""
        prompt = f"""L'utilisateur a un taux de complétion de {completion_rate}% sur {len(tasks)} tâches.
        Analyse et suggère 3 ajustements concrets pour améliorer la productivité.
        JSON: {{"summary": "...", "detailed": ["suggestion1", "suggestion2", "suggestion3"]}}"""

        response = openai.ChatCompletion.create(
            model='gpt-4-turbo-preview',
            messages=[
                {'role': 'system', 'content': self.SYSTEM_PROMPTS['coaching']},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.7,
            response_format={'type': 'json_object'}
        )

        return json.loads(response.choices[0].message.content)

    def generate_weekly_report(self, user, completed_tasks, total_tasks, xp_gained):
        """Génère rapport hebdomadaire personnalisé"""
        prompt = f"""Génère un rapport hebdomadaire encourageant pour {user.display_name}.
        Stats: {completed_tasks}/{total_tasks} tâches, +{xp_gained} XP.
        Max 250 caractères."""

        response = openai.ChatCompletion.create(
            model='gpt-4-turbo-preview',
            messages=[
                {'role': 'system', 'content': 'Tu génères des rapports hebdomadaires encourageants.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )

        return response.choices[0].message.content
```

## 6. Système de Notifications avec Celery

### 6.1 Tâches Celery Périodiques

```python
# config/celery.py

from celery import Celery
from celery.schedules import crontab

app = Celery('dreamplanner')
app.config_from_object('django.conf:settings', namespace='CELERY')

app.conf.beat_schedule = {
    # Traiter notifications en attente (chaque minute)
    'process-pending-notifications': {
        'task': 'apps.notifications.tasks.process_pending_notifications',
        'schedule': 60.0,
    },

    # Rappels de tâches (toutes les 15 minutes)
    'send-reminder-notifications': {
        'task': 'apps.notifications.tasks.send_reminder_notifications',
        'schedule': 900.0,
    },

    # Message de motivation quotidien (8h du matin)
    'generate-daily-motivation': {
        'task': 'apps.notifications.tasks.generate_daily_motivation',
        'schedule': crontab(hour=8, minute=0),
    },

    # Rescue Mode - utilisateurs inactifs (9h du matin)
    'check-inactive-users': {
        'task': 'apps.notifications.tasks.check_inactive_users',
        'schedule': crontab(hour=9, minute=0),
    },

    # Rapport hebdomadaire (dimanche 10h)
    'send-weekly-report': {
        'task': 'apps.notifications.tasks.send_weekly_report',
        'schedule': crontab(day_of_week=0, hour=10, minute=0),
    },

    # Mettre à jour progression des rêves (3h du matin)
    'update-dream-progress': {
        'task': 'apps.dreams.tasks.update_dream_progress',
        'schedule': crontab(hour=3, minute=0),
    },

    # Vérifier tâches en retard (10h du matin)
    'check-overdue-tasks': {
        'task': 'apps.dreams.tasks.check_overdue_tasks',
        'schedule': crontab(hour=10, minute=0),
    },

    # Nettoyage notifications anciennes (lundi 2h)
    'cleanup-old-notifications': {
        'task': 'apps.notifications.tasks.cleanup_old_notifications',
        'schedule': crontab(day_of_week=1, hour=2, minute=0),
    },

    # Archiver rêves abandonnés (dimanche 3h)
    'cleanup-abandoned-dreams': {
        'task': 'apps.dreams.tasks.cleanup_abandoned_dreams',
        'schedule': crontab(day_of_week=0, hour=3, minute=0),
    },
}
```

### 6.2 Types de Notifications

| Type | Déclencheur | Exemple | Celery Task |
|------|-------------|---------|-------------|
| `reminder` | Tâche programmée | "C'est l'heure de pratiquer l'anglais!" | `send_reminder_notifications` |
| `motivation` | Quotidien 8h | "Tu as déjà accompli 3 tâches cette semaine!" | `generate_daily_motivation` |
| `progress` | Milestone atteint | "50% de ton objectif atteint!" | Déclenché par completion |
| `achievement` | Badge débloqué | "Badge 'Régulier' obtenu!" | Déclenché par XP/streak |
| `rescue` | Inactivité 3+ jours | "On est toujours là pour toi!" | `check_inactive_users` |
| `weekly_report` | Dimanche 10h | "Ton rapport hebdomadaire" | `send_weekly_report` |
| `task_created` | 2-minute start généré | "Prêt à démarrer en 2 minutes?" | `generate_two_minute_start` |
| `vision_ready` | Image DALL-E générée | "Ta vision est prête!" | `generate_vision_board` |
| `coaching` | Taux complétion < 50% | "Suggestions pour mieux réussir" | `suggest_task_adjustments` |

### 6.3 Service de Notifications FCM

```python
# integrations/fcm_service.py

import firebase_admin
from firebase_admin import messaging

class FCMService:
    def send_notification(self, notification):
        """Envoie notification via Firebase Cloud Messaging"""
        user = notification.user
        tokens = user.fcm_tokens.values_list('token', flat=True)

        if not tokens:
            return False

        # Vérifier DND (Do Not Disturb)
        if not self.should_send_notification(user, timezone.now()):
            # Reporter pour plus tard
            notification.scheduled_for = self.get_next_available_time(user)
            notification.save()
            return False

        # Construire message FCM
        message = messaging.MulticastMessage(
            tokens=list(tokens),
            notification=messaging.Notification(
                title=notification.title,
                body=notification.body,
            ),
            data=notification.data or {},
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id=notification.notification_type,
                    sound='default',
                )
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound='default',
                        badge=1,
                    )
                )
            )
        )

        # Envoyer
        response = messaging.send_multicast(message)

        # Marquer comme envoyée
        notification.status = 'sent'
        notification.sent_at = timezone.now()
        notification.save()

        return response.success_count > 0

    def should_send_notification(self, user, now):
        """Vérifie les heures DND (Do Not Disturb)"""
        if not user.notification_prefs:
            return True

        dnd_start = user.notification_prefs.get('dnd_start', '22:00')
        dnd_end = user.notification_prefs.get('dnd_end', '08:00')

        user_tz = timezone(user.timezone)
        user_time = now.astimezone(user_tz)
        hour = user_time.hour

        dnd_start_hour = int(dnd_start.split(':')[0])
        dnd_end_hour = int(dnd_end.split(':')[0])

        # Vérifier si dans période DND
        if dnd_start_hour < dnd_end_hour:
            return not (dnd_start_hour <= hour < dnd_end_hour)
        else:  # DND traverse minuit
            return dnd_end_hour <= hour < dnd_start_hour
```

## 7. WebSocket avec Django Channels

### 7.1 Configuration ASGI

```python
# config/asgi.py

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from apps.conversations.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
```

### 7.2 Consumer WebSocket

```python
# apps/conversations/consumers.py

from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'conversation_{self.conversation_id}'
        self.user = self.scope['user']

        # Vérifier accès
        has_access = await self.check_conversation_access()
        if not has_access:
            await self.close(code=4003)
            return

        # Rejoindre groupe
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Confirmation de connexion
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

        # Sauvegarder message utilisateur
        user_message = await self.save_message('user', message_content)

        # Broadcaster message utilisateur
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

        # Obtenir réponse IA en streaming
        await self.get_ai_response_stream(message_content)

    async def get_ai_response_stream(self, user_message):
        conversation = await self.get_conversation()
        messages = await self.get_messages_for_api(conversation)

        ai_service = OpenAIService()

        # Indiquer démarrage du streaming
        await self.send(text_data=json.dumps({'type': 'stream_start'}))

        # Streamer réponse IA
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

        # Fin du streaming
        await self.send(text_data=json.dumps({'type': 'stream_end'}))

        # Sauvegarder réponse complète
        assistant_message = await self.save_message('assistant', full_response)

        # Broadcaster message complet
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

## 8. Déploiement AWS

### 8.1 Architecture de Production

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

### 8.2 Services AWS Utilisés

- **ECS Fargate**: Containers Django (HTTP + WebSocket + Celery)
- **RDS PostgreSQL**: Multi-AZ pour haute disponibilité
- **ElastiCache Redis**: Cluster mode pour Channels + Celery
- **S3**: Vision boards et médias utilisateurs
- **ALB**: Load balancer avec health checks
- **CloudFront**: CDN pour static files
- **CloudWatch**: Logs et monitoring
- **Secrets Manager**: Gestion des secrets
- **ECR**: Registry Docker privé

## 9. Structure des Dossiers

```
dreamplanner/
├── backend/                      # Backend Django
│   ├── config/                   # Configuration Django
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   ├── production.py
│   │   │   └── testing.py
│   │   ├── urls.py
│   │   ├── asgi.py              # WebSocket config
│   │   ├── wsgi.py              # HTTP config
│   │   └── celery.py            # Celery config
│   │
│   ├── apps/                     # Applications Django
│   │   ├── users/               # Gestion utilisateurs
│   │   ├── dreams/              # Dreams, Goals, Tasks
│   │   ├── conversations/       # Chat IA (WebSocket)
│   │   ├── notifications/       # Push notifications
│   │   └── calendar/            # Vues calendrier
│   │
│   ├── core/                     # Utilitaires centraux
│   │   ├── authentication.py    # Firebase backend
│   │   ├── permissions.py       # DRF permissions
│   │   ├── exceptions.py        # Exceptions custom
│   │   └── pagination.py        # Pagination
│   │
│   ├── integrations/             # Services externes
│   │   ├── openai_service.py    # OpenAI GPT-4
│   │   ├── fcm_service.py       # Firebase FCM
│   │   └── firebase_admin_service.py
│   │
│   ├── requirements/             # Dépendances Python
│   │   ├── base.txt
│   │   ├── development.txt
│   │   ├── production.txt
│   │   └── testing.txt
│   │
│   ├── docker/                   # Configuration Docker
│   │   └── nginx.conf
│   │
│   ├── Dockerfile               # Image production
│   ├── docker-compose.yml       # Dev local
│   ├── docker-compose.prod.yml  # Production
│   ├── Makefile                 # Commandes utiles
│   ├── pytest.ini               # Config tests
│   ├── manage.py                # Django CLI
│   └── README.md
│
├── apps/
│   └── mobile/                   # Application React Native
│       ├── src/
│       │   ├── components/       # Composants réutilisables
│       │   ├── screens/          # Écrans
│       │   ├── navigation/       # Navigation
│       │   ├── services/         # Services API
│       │   ├── stores/           # État global (Zustand)
│       │   ├── hooks/            # Hooks personnalisés
│       │   ├── utils/            # Utilitaires
│       │   ├── types/            # Types TypeScript
│       │   └── theme/            # Thème et styles
│       ├── android/
│       ├── ios/
│       └── package.json
│
├── _archived/                    # Backend Node.js archivé
│   └── apps-api/                 # (non utilisé)
│
├── docs/                         # Documentation
│   ├── TECHNICAL_ARCHITECTURE.md
│   ├── FEATURES_SPECIFICATIONS.md
│   ├── IMPROVEMENTS_STRATEGY.md
│   └── ...
│
└── .github/                      # CI/CD
    └── workflows/
```

## 10. Performance et Sécurité

### 10.1 Optimisations Performance

- **Caching Redis**: Réponses API, sessions, rate limiting
- **Database Indexing**: Indexes sur firebase_uid, user_id, dates
- **Query Optimization**: select_related(), prefetch_related()
- **Connection Pooling**: PostgreSQL pooling via Django
- **Static Files**: Servis via CloudFront CDN
- **Gunicorn Workers**: 4 workers + threads pour concurrence
- **Celery**: Background tasks pour opérations lourdes

### 10.2 Sécurité

- ✅ **Firebase Authentication**: Tokens vérifiés côté serveur
- ✅ **HTTPS Only**: TLS 1.2+ en production
- ✅ **CORS**: Whitelist origins autorisées
- ✅ **SQL Injection**: Protection via Django ORM
- ✅ **XSS Protection**: Django middleware
- ✅ **CSRF Protection**: Django REST Framework
- ✅ **Rate Limiting**: Nginx + DRF throttling
- ✅ **Secrets Management**: AWS Secrets Manager
- ✅ **Container Security**: Non-root user dans Docker
- ✅ **Security Headers**: Nginx config (HSTS, X-Frame-Options, etc.)
- ✅ **Input Validation**: DRF Serializers

### 10.3 Monitoring

- **Sentry**: Error tracking et performance monitoring
- **CloudWatch**: Logs centralisés et métriques
- **Health Checks**: /health/, /health/liveness/, /health/readiness/
- **Flower**: Monitoring Celery tasks
- **Database Metrics**: RDS Performance Insights

## 11. Tests

### 11.1 Stack de Tests

- **pytest**: Framework de tests
- **pytest-django**: Plugin Django
- **pytest-cov**: Couverture de code
- **pytest-asyncio**: Tests async (WebSocket)
- **Factory Boy**: Fixtures de données
- **Coverage Target**: 80%+

### 11.2 Types de Tests

```bash
# Tests unitaires
pytest -m unit

# Tests d'intégration
pytest -m integration

# Tests async (WebSocket)
pytest -m asyncio

# Couverture complète
pytest --cov --cov-report=html
```

---

**Architecture complétée**: Django 5.0.1 + DRF 3.14.0 + Channels 4.0.0 + Celery 5.3.4
**Status**: ✅ Backend production-ready
**Dernière mise à jour**: 2026-01-28
