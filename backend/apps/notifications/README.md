# Notifications App

Application Django pour les notifications push et rappels.

## Overview

L'app Notifications gere toutes les communications push:
- **Notification** - Notification individuelle
- **NotificationTemplate** - Templates reutilisables
- **NotificationBatch** - Envois groupes

## Models

### Notification

| Champ | Type | Description |
|-------|------|-------------|
| id | UUID | Identifiant unique |
| user | FK(User) | Destinataire |
| notification_type | CharField | Type de notification |
| title | CharField(255) | Titre |
| body | TextField | Corps du message |
| data | JSONField | Donnees deep linking |
| scheduled_for | DateTime | Date d'envoi prevue |
| sent_at | DateTime | Date d'envoi reel |
| read_at | DateTime | Date de lecture |
| status | CharField | pending, sent, failed, cancelled |
| retry_count | Integer | Nombre de tentatives |

**Types de notification:**
- `reminder` - Rappel de tache
- `motivation` - Message motivationnel
- `progress` - Mise a jour de progression
- `achievement` - Badge/achievement debloque
- `check_in` - Point de suivi
- `rescue` - Mode sauvetage
- `buddy` - Message de buddy
- `system` - Notification systeme

### NotificationTemplate

| Champ | Type | Description |
|-------|------|-------------|
| id | UUID | Identifiant unique |
| name | CharField(100) | Nom unique |
| notification_type | CharField | Type |
| title_template | CharField(255) | Template titre |
| body_template | TextField | Template corps |
| available_variables | JSONField | Variables disponibles |
| is_active | Boolean | Template actif |

### NotificationBatch

| Champ | Type | Description |
|-------|------|-------------|
| id | UUID | Identifiant unique |
| name | CharField(255) | Nom du batch |
| total_scheduled | Integer | Notifications planifiees |
| total_sent | Integer | Notifications envoyees |
| total_failed | Integer | Notifications echouees |
| status | CharField | scheduled, processing, completed, failed |

## API Endpoints

- `GET /api/notifications/` - Liste des notifications
- `GET /api/notifications/{id}/` - Detail
- `POST /api/notifications/{id}/read/` - Marquer comme lu
- `POST /api/notifications/read-all/` - Tout marquer comme lu
- `GET /api/notifications/unread-count/` - Nombre de non-lus
- `DELETE /api/notifications/{id}/` - Supprimer

### Templates (Admin)
- `GET /api/notification-templates/` - Liste des templates
- `POST /api/notification-templates/` - Creer un template

## Serializers

- `NotificationSerializer` - Notification complete
- `NotificationListSerializer` - Version liste
- `NotificationTemplateSerializer` - Template complet

## Firebase Cloud Messaging

L'integration FCM gere:
1. Envoi de notifications individuelles
2. Envoi en batch (jusqu'a 500)
3. Gestion des tokens expires
4. Retry automatique sur echec

## Do Not Disturb (DND)

Les notifications respectent les preferences DND:
- `dndEnabled` - DND active
- `dndStart` - Heure de debut (0-23)
- `dndEnd` - Heure de fin (0-23)

Les notifications sont reportees si envoyees pendant DND.

## Celery Tasks

| Task | Frequence | Description |
|------|-----------|-------------|
| `process_pending_notifications` | 1 min | Envoie les notifications en attente |
| `send_reminder_notifications` | 15 min | Rappels de taches |
| `generate_daily_motivation` | 8h00 | Messages motivationnels |
| `send_weekly_report` | Dim 10h | Rapport hebdomadaire |
| `check_overdue_tasks` | 10h00 | Detection taches en retard |
| `cleanup_old_notifications` | Lun 2h | Nettoyage anciennes notifications |

## Template Variables

Variables disponibles dans les templates:
- `{user_name}` - Nom de l'utilisateur
- `{dream_title}` - Titre du reve
- `{goal_title}` - Titre de l'objectif
- `{task_title}` - Titre de la tache
- `{progress}` - Pourcentage de progression
- `{streak_days}` - Jours de streak
- `{xp_gained}` - XP gagne

## Testing

```bash
# Tests unitaires
python manage.py test apps.notifications

# Avec coverage
pytest apps/notifications/tests.py -v --cov=apps.notifications
```

## Configuration

Variables d'environnement:
- `FIREBASE_PROJECT_ID` - ID projet Firebase
- `FIREBASE_PRIVATE_KEY` - Cle privee
- `FIREBASE_CLIENT_EMAIL` - Email client
