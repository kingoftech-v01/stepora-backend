# Calendar App

Application Django pour la gestion du calendrier et la planification.

## Overview

L'app Calendar gere la planification des taches:
- **CalendarEvent** - Evenement dans le calendrier
- **TimeBlock** - Blocs de temps recurents (preferences)

## Models

### CalendarEvent

| Champ | Type | Description |
|-------|------|-------------|
| id | UUID | Identifiant unique |
| user | FK(User) | Proprietaire |
| task | FK(Task) | Tache associee (optionnel) |
| title | CharField(255) | Titre de l'evenement |
| description | TextField | Description |
| start_time | DateTime | Debut |
| end_time | DateTime | Fin |
| location | CharField(255) | Lieu/contexte |
| reminder_minutes_before | Integer | Rappel avant (minutes) |
| status | CharField | scheduled, completed, cancelled, rescheduled |

### TimeBlock

| Champ | Type | Description |
|-------|------|-------------|
| id | UUID | Identifiant unique |
| user | FK(User) | Proprietaire |
| block_type | CharField | Type de bloc |
| day_of_week | Integer | 0=Lundi, 6=Dimanche |
| start_time | TimeField | Heure de debut |
| end_time | TimeField | Heure de fin |
| is_active | Boolean | Bloc actif |

**Types de blocs:**
- `work` - Travail
- `personal` - Personnel
- `family` - Famille
- `exercise` - Exercice
- `blocked` - Bloque (indisponible)

## API Endpoints

### Events
- `GET /api/calendar/` - Liste des evenements
- `GET /api/calendar/?date=2024-01-15` - Evenements d'un jour
- `GET /api/calendar/?start=2024-01-01&end=2024-01-31` - Plage de dates
- `POST /api/calendar/` - Creer un evenement
- `GET /api/calendar/{id}/` - Detail
- `PUT /api/calendar/{id}/` - Modifier
- `DELETE /api/calendar/{id}/` - Supprimer
- `POST /api/calendar/{id}/reschedule/` - Replanifier

### Vues speciales
- `GET /api/calendar/today/` - Evenements d'aujourd'hui
- `GET /api/calendar/week/` - Evenements de la semaine
- `GET /api/calendar/overdue/` - Taches en retard
- `POST /api/calendar/auto-schedule/` - Planification automatique

### Time Blocks
- `GET /api/time-blocks/` - Liste des blocs
- `POST /api/time-blocks/` - Creer un bloc
- `PUT /api/time-blocks/{id}/` - Modifier
- `DELETE /api/time-blocks/{id}/` - Supprimer

## Serializers

- `CalendarEventSerializer` - Evenement complet avec tache
- `CalendarEventListSerializer` - Version liste
- `TimeBlockSerializer` - Bloc de temps

## Planification Intelligente

L'auto-scheduling prend en compte:
1. **TimeBlocks** - Respecte les blocs de disponibilite
2. **Preferences utilisateur** - Horaires de travail dans le profil
3. **Duree des taches** - Ne depasse pas les blocs disponibles
4. **Priorite** - Planifie d'abord les taches prioritaires
5. **Deadlines** - Respecte les dates limites des reves

## Algorithme de Planification

```python
def auto_schedule_tasks(user, tasks):
    1. Recuperer les TimeBlocks actifs
    2. Pour chaque jour dans la plage:
       - Identifier les creneaux disponibles
       - Filtrer les taches non planifiees
       - Attribuer les taches aux creneaux
    3. Creer les CalendarEvents correspondants
```

## Testing

```bash
# Tests unitaires
python manage.py test apps.calendar

# Avec coverage
pytest apps/calendar/tests.py -v --cov=apps.calendar
```

## Configuration

La planification utilise les preferences utilisateur:
- `work_schedule` - Horaires de travail (JSON)
- `timezone` - Fuseau horaire pour les calculs

## Integration avec Dreams

Quand une tache est completee:
1. Le CalendarEvent passe en status `completed`
2. La Task sous-jacente est marquee complete
3. L'XP est attribue a l'utilisateur
4. Le streak est mis a jour
