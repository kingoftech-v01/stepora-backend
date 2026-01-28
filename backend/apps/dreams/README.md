# Dreams App

Application Django pour la gestion des reves, objectifs, taches et obstacles.

## Overview

L'app Dreams est le coeur de DreamPlanner. Elle gere la hierarchie complete:
- **Dream** - L'objectif principal/vision de l'utilisateur
- **Goal** - Les etapes intermediaires pour atteindre le reve
- **Task** - Les actions concretes a realiser
- **Obstacle** - Les defis et blocages (predits ou reels)

## Models

### Dream

| Champ | Type | Description |
|-------|------|-------------|
| id | UUID | Identifiant unique |
| user | FK(User) | Proprietaire du reve |
| title | CharField(255) | Titre du reve |
| description | TextField | Description detaillee |
| category | CharField(50) | Categorie (carriere, sante, etc.) |
| target_date | DateTime | Date cible d'achevement |
| priority | Integer | Niveau de priorite (1-5) |
| status | CharField | active, completed, paused, archived |
| ai_analysis | JSONField | Analyse IA du reve |
| vision_image_url | URLField | Image du vision board (DALL-E) |
| progress_percentage | Float | Pourcentage de progression |
| has_two_minute_start | Boolean | Si un 2-minute start existe |

### Goal

| Champ | Type | Description |
|-------|------|-------------|
| id | UUID | Identifiant unique |
| dream | FK(Dream) | Reve parent |
| title | CharField(255) | Titre de l'objectif |
| description | TextField | Description |
| order | Integer | Ordre dans la sequence |
| estimated_minutes | Integer | Duree estimee |
| scheduled_start/end | DateTime | Planification |
| status | CharField | pending, in_progress, completed, skipped |
| reminder_enabled | Boolean | Rappels actives |
| progress_percentage | Float | Progression |

### Task

| Champ | Type | Description |
|-------|------|-------------|
| id | UUID | Identifiant unique |
| goal | FK(Goal) | Objectif parent |
| title | CharField(255) | Titre de la tache |
| description | TextField | Description |
| order | Integer | Ordre dans l'objectif |
| scheduled_date | DateTime | Date planifiee |
| scheduled_time | CharField(5) | Heure (HH:MM) |
| duration_mins | Integer | Duree en minutes |
| recurrence | JSONField | Pattern de recurrence |
| status | CharField | pending, completed, skipped |
| is_two_minute_start | Boolean | Tache 2-minute start |

### Obstacle

| Champ | Type | Description |
|-------|------|-------------|
| id | UUID | Identifiant unique |
| dream | FK(Dream) | Reve associe |
| title | CharField(255) | Titre de l'obstacle |
| description | TextField | Description |
| obstacle_type | CharField | predicted, actual |
| solution | TextField | Solution IA |
| status | CharField | active, resolved, ignored |

## API Endpoints

### Dreams
- `GET /api/dreams/` - Liste des reves
- `POST /api/dreams/` - Creer un reve
- `GET /api/dreams/{id}/` - Detail d'un reve
- `PUT /api/dreams/{id}/` - Modifier un reve
- `DELETE /api/dreams/{id}/` - Supprimer un reve
- `POST /api/dreams/{id}/analyze/` - Analyse IA du reve
- `POST /api/dreams/{id}/generate-plan/` - Generer un plan GPT-4
- `POST /api/dreams/{id}/generate-vision/` - Generer vision board DALL-E
- `POST /api/dreams/{id}/generate-two-minute-start/` - Generer micro-action

### Goals
- `GET /api/dreams/{dream_id}/goals/` - Liste des objectifs
- `POST /api/dreams/{dream_id}/goals/` - Creer un objectif
- `GET /api/goals/{id}/` - Detail d'un objectif
- `PUT /api/goals/{id}/` - Modifier un objectif
- `DELETE /api/goals/{id}/` - Supprimer un objectif
- `POST /api/goals/{id}/complete/` - Marquer comme complete

### Tasks
- `GET /api/goals/{goal_id}/tasks/` - Liste des taches
- `POST /api/goals/{goal_id}/tasks/` - Creer une tache
- `GET /api/tasks/{id}/` - Detail d'une tache
- `PUT /api/tasks/{id}/` - Modifier une tache
- `DELETE /api/tasks/{id}/` - Supprimer une tache
- `POST /api/tasks/{id}/complete/` - Marquer comme complete (donne XP)

### Obstacles
- `GET /api/dreams/{dream_id}/obstacles/` - Liste des obstacles
- `POST /api/dreams/{dream_id}/obstacles/` - Creer un obstacle
- `POST /api/obstacles/{id}/resolve/` - Marquer comme resolu

## Serializers

- `DreamSerializer` - Serialisation complete avec goals imbriques
- `DreamListSerializer` - Version legere pour les listes
- `GoalSerializer` - Avec tasks imbriques
- `TaskSerializer` - Serialisation complete
- `ObstacleSerializer` - Avec solution IA

## Permissions

- `IsAuthenticated` - Toutes les vues requierent l'authentification
- `IsOwner` - Verification que l'utilisateur est proprietaire du reve

## Gamification

- Completer une **Task** : 10-100 XP (selon duree)
- Completer un **Goal** : 100 XP
- Completer un **Dream** : 500 XP
- Les streaks sont mis a jour a chaque completion de tache

## Testing

```bash
# Lancer les tests de l'app
python manage.py test apps.dreams

# Avec coverage
pytest apps/dreams/tests.py -v --cov=apps.dreams
```

## Configuration

Variables d'environnement utilisees:
- `OPENAI_API_KEY` - Pour generation de plans et analyse
- `OPENAI_MODEL` - Modele GPT a utiliser (default: gpt-4-turbo-preview)

## Celery Tasks

- `generate_dream_plan` - Generation de plan IA (async)
- `generate_two_minute_start` - Generation de micro-action (async)
- `generate_vision_board` - Generation d'image DALL-E (async)
- `analyze_dream` - Analyse IA du reve (async)
- `predict_obstacles` - Prediction d'obstacles (async)
- `auto_schedule_tasks` - Planification automatique des taches
