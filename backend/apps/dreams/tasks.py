"""
Celery tasks for dreams app.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Count, Prefetch
from datetime import timedelta, datetime, time
import logging

from .models import Dream, Goal, Task, Obstacle
from apps.users.models import User
from apps.notifications.models import Notification
from integrations.openai_service import OpenAIService
from core.exceptions import OpenAIError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_two_minute_start(dream_id):
    """
    Generate a 2-minute start micro-task for a new dream.
    Called when a dream is created or when user requests it.
    """
    try:
        dream = Dream.objects.get(id=dream_id)

        # Check if dream already has 2-minute start
        if dream.has_two_minute_start:
            logger.info(f"Dream {dream_id} already has 2-minute start")
            return {'created': False, 'reason': 'already_exists'}

        ai_service = OpenAIService()

        # Generate micro-action with AI
        micro_action = ai_service.generate_two_minute_start(dream)

        # Get or create first goal
        first_goal = dream.goals.order_by('order').first()

        if not first_goal:
            # Create initial goal if none exists
            first_goal = Goal.objects.create(
                dream=dream,
                title=f"Démarrer: {dream.title}",
                description="Premières étapes vers ton rêve",
                order=0,
                status='pending'
            )

        # Create 2-minute start task at order 0
        Task.objects.create(
            goal=first_goal,
            title=f"🚀 {micro_action}",
            description="Cette micro-action prend seulement 2 minutes et te permettra de démarrer!",
            order=0,
            duration_mins=2,
            scheduled_date=timezone.now(),
            status='pending'
        )

        # Mark dream as having 2-minute start
        dream.has_two_minute_start = True
        dream.save(update_fields=['has_two_minute_start'])

        # Send notification
        Notification.objects.create(
            user=dream.user,
            notification_type='task_created',
            title='🚀 Prêt à démarrer en 2 minutes?',
            body=f'On a créé une micro-action pour ton rêve: {micro_action}',
            scheduled_for=timezone.now(),
            data={
                'action': 'open_dream',
                'screen': 'DreamDetail',
                'dream_id': str(dream.id)
            }
        )

        logger.info(f"Created 2-minute start for dream {dream_id}: {micro_action}")
        return {'created': True, 'action': micro_action}

    except Dream.DoesNotExist:
        logger.error(f"Dream {dream_id} not found")
        return {'created': False, 'error': 'dream_not_found'}

    except OpenAIError as e:
        logger.error(f"OpenAI error generating 2-minute start for dream {dream_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60)

    except Exception as e:
        logger.error(f"Error generating 2-minute start for dream {dream_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def auto_schedule_tasks(user_id):
    """
    Automatically schedule unscheduled tasks based on user's work schedule and preferences.
    Runs daily or when user requests auto-scheduling.
    """
    try:
        user = User.objects.get(id=user_id)

        # Get unscheduled tasks for user's active dreams
        unscheduled_tasks = Task.objects.filter(
            goal__dream__user=user,
            goal__dream__status='active',
            scheduled_date__isnull=True,
            status='pending'
        ).select_related('goal', 'goal__dream').order_by('goal__order', 'order')

        if not unscheduled_tasks.exists():
            logger.info(f"No unscheduled tasks for user {user_id}")
            return {'scheduled': 0}

        # Get user's work schedule preferences
        work_schedule = user.work_schedule or {}
        start_date = timezone.now().date()
        scheduled_count = 0

        # Default work hours if not specified
        default_start_hour = work_schedule.get('start_hour', 9)
        default_end_hour = work_schedule.get('end_hour', 17)
        working_days = work_schedule.get('working_days', [1, 2, 3, 4, 5])  # Mon-Fri

        current_date = start_date
        current_time_slot = datetime.combine(current_date, time(hour=default_start_hour))

        for task in unscheduled_tasks:
            # Find next available time slot
            while current_date.isoweekday() not in working_days:
                current_date += timedelta(days=1)
                current_time_slot = datetime.combine(current_date, time(hour=default_start_hour))

            # Check if we have enough time today
            duration = task.duration_mins or 30  # Default 30 mins
            end_of_day = datetime.combine(current_date, time(hour=default_end_hour))

            if current_time_slot + timedelta(minutes=duration) > end_of_day:
                # Move to next day
                current_date += timedelta(days=1)
                while current_date.isoweekday() not in working_days:
                    current_date += timedelta(days=1)
                current_time_slot = datetime.combine(current_date, time(hour=default_start_hour))

            # Schedule the task
            task.scheduled_date = timezone.make_aware(current_time_slot)
            task.scheduled_time = current_time_slot.strftime('%H:%M')
            task.save(update_fields=['scheduled_date', 'scheduled_time'])

            scheduled_count += 1

            # Move time slot forward
            current_time_slot += timedelta(minutes=duration + 15)  # 15 min buffer

        # Send notification
        if scheduled_count > 0:
            Notification.objects.create(
                user=user,
                notification_type='tasks_scheduled',
                title='📅 Tâches planifiées automatiquement',
                body=f'{scheduled_count} tâches ont été ajoutées à ton calendrier!',
                scheduled_for=timezone.now(),
                data={
                    'action': 'open_calendar',
                    'screen': 'Calendar',
                    'scheduled_count': scheduled_count
                }
            )

        logger.info(f"Auto-scheduled {scheduled_count} tasks for user {user_id}")
        return {'scheduled': scheduled_count}

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'scheduled': 0, 'error': 'user_not_found'}

    except Exception as e:
        logger.error(f"Error auto-scheduling tasks for user {user_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def detect_obstacles(dream_id):
    """
    Use AI to detect potential obstacles for a dream and create obstacle records.
    Called when a dream is analyzed or when user requests obstacle detection.
    """
    try:
        dream = Dream.objects.prefetch_related('goals__tasks').get(id=dream_id)
        ai_service = OpenAIService()

        # Generate obstacle predictions with AI
        obstacles_data = ai_service.predict_obstacles(dream)

        created_count = 0

        for obstacle_info in obstacles_data:
            # Create or update obstacle
            obstacle, created = Obstacle.objects.get_or_create(
                dream=dream,
                title=obstacle_info['title'],
                defaults={
                    'description': obstacle_info['description'],
                    'type': 'predicted',
                    'likelihood': obstacle_info.get('likelihood', 'medium'),
                    'ai_suggested_solution': obstacle_info.get('solution', '')
                }
            )

            if created:
                created_count += 1

        logger.info(f"Detected {created_count} obstacles for dream {dream_id}")
        return {'created': created_count, 'obstacles': obstacles_data}

    except Dream.DoesNotExist:
        logger.error(f"Dream {dream_id} not found")
        return {'created': 0, 'error': 'dream_not_found'}

    except OpenAIError as e:
        logger.error(f"OpenAI error detecting obstacles for dream {dream_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60)

    except Exception as e:
        logger.error(f"Error detecting obstacles for dream {dream_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def update_dream_progress():
    """
    Update progress percentage for all active dreams.
    Runs daily to recalculate progress based on completed tasks.
    """
    try:
        active_dreams = Dream.objects.filter(status='active').prefetch_related('goals__tasks')

        updated_count = 0

        for dream in active_dreams:
            # Calculate total and completed tasks
            total_tasks = 0
            completed_tasks = 0

            for goal in dream.goals.all():
                tasks = goal.tasks.all()
                total_tasks += tasks.count()
                completed_tasks += tasks.filter(status='completed').count()

            # Calculate progress percentage
            if total_tasks > 0:
                progress = (completed_tasks / total_tasks) * 100
            else:
                progress = 0.0

            # Update if changed
            if dream.progress_percentage != progress:
                dream.progress_percentage = progress
                dream.save(update_fields=['progress_percentage'])
                updated_count += 1

                # Check if dream is complete
                if progress >= 100.0 and dream.status != 'completed':
                    dream.status = 'completed'
                    dream.completed_at = timezone.now()
                    dream.save(update_fields=['status', 'completed_at'])

                    # Send completion notification
                    Notification.objects.create(
                        user=dream.user,
                        notification_type='dream_completed',
                        title='🎉 Rêve accompli!',
                        body=f'Félicitations! Tu as réalisé ton rêve: {dream.title}',
                        scheduled_for=timezone.now(),
                        data={
                            'action': 'open_dream',
                            'screen': 'DreamDetail',
                            'dream_id': str(dream.id)
                        }
                    )

        logger.info(f"Updated progress for {updated_count} dreams")
        return {'updated': updated_count}

    except Exception as e:
        logger.error(f"Error updating dream progress: {str(e)}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def check_overdue_tasks():
    """
    Check for overdue tasks and send notifications.
    Runs daily to remind users of tasks they've missed.
    """
    try:
        now = timezone.now()
        yesterday = now - timedelta(days=1)

        # Find tasks that are overdue (scheduled for yesterday or earlier, still pending)
        overdue_tasks = Task.objects.filter(
            scheduled_date__lt=now.date(),
            scheduled_date__gte=yesterday.date(),
            status='pending'
        ).select_related('goal', 'goal__dream', 'goal__dream__user')

        # Group by user
        users_with_overdue = {}
        for task in overdue_tasks:
            user_id = task.goal.dream.user.id
            if user_id not in users_with_overdue:
                users_with_overdue[user_id] = {
                    'user': task.goal.dream.user,
                    'tasks': []
                }
            users_with_overdue[user_id]['tasks'].append(task)

        created_count = 0

        for user_data in users_with_overdue.values():
            user = user_data['user']
            overdue_count = len(user_data['tasks'])

            # Send notification
            Notification.objects.create(
                user=user,
                notification_type='overdue_tasks',
                title=f'⏰ {overdue_count} tâche{"s" if overdue_count > 1 else ""} en retard',
                body=f'Tu as {overdue_count} tâche{"s" if overdue_count > 1 else ""} qui attend{"ent" if overdue_count > 1 else ""} d\'être faite{"s" if overdue_count > 1 else ""}!',
                scheduled_for=now,
                data={
                    'action': 'open_calendar',
                    'screen': 'Calendar',
                    'filter': 'overdue'
                }
            )

            created_count += 1

        logger.info(f"Sent {created_count} overdue task notifications")
        return {'sent': created_count, 'total_overdue_tasks': len(overdue_tasks)}

    except Exception as e:
        logger.error(f"Error checking overdue tasks: {str(e)}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def suggest_task_adjustments(user_id):
    """
    Use AI to analyze user's task completion patterns and suggest adjustments.
    Part of Proactive AI Coach feature.
    """
    try:
        user = User.objects.get(id=user_id)
        ai_service = OpenAIService()

        # Get user's task history for last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)

        tasks = Task.objects.filter(
            goal__dream__user=user,
            created_at__gte=thirty_days_ago
        ).select_related('goal', 'goal__dream')

        # Calculate completion rate
        total = tasks.count()
        completed = tasks.filter(status='completed').count()
        completion_rate = (completed / total * 100) if total > 0 else 0

        # If completion rate is low, generate suggestions
        if completion_rate < 50:
            suggestions = ai_service.generate_task_adjustments(user, tasks, completion_rate)

            # Send notification with suggestions
            Notification.objects.create(
                user=user,
                notification_type='coaching',
                title='💡 Suggestions pour mieux réussir',
                body=suggestions['summary'],
                scheduled_for=timezone.now(),
                data={
                    'action': 'view_suggestions',
                    'screen': 'CoachingSuggestions',
                    'suggestions': suggestions['detailed'],
                    'completion_rate': completion_rate
                }
            )

            logger.info(f"Sent task adjustment suggestions to user {user_id}")
            return {'sent': True, 'completion_rate': completion_rate}

        logger.info(f"User {user_id} has good completion rate: {completion_rate}%")
        return {'sent': False, 'completion_rate': completion_rate}

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'sent': False, 'error': 'user_not_found'}

    except OpenAIError as e:
        logger.error(f"OpenAI error generating suggestions for user {user_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60)

    except Exception as e:
        logger.error(f"Error suggesting task adjustments for user {user_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def generate_vision_board(dream_id):
    """
    Generate vision board image using DALL-E for a dream.
    Called when user requests vision board generation.
    """
    try:
        dream = Dream.objects.get(id=dream_id)

        # Check if vision already exists
        if dream.vision_image_url:
            logger.info(f"Dream {dream_id} already has vision image")
            return {'created': False, 'reason': 'already_exists', 'url': dream.vision_image_url}

        ai_service = OpenAIService()

        # Generate vision board image with DALL-E
        image_url = ai_service.generate_vision_board_image(dream)

        # Update dream with image URL
        dream.vision_image_url = image_url
        dream.save(update_fields=['vision_image_url'])

        # Send notification
        Notification.objects.create(
            user=dream.user,
            notification_type='vision_ready',
            title='🎨 Ta vision est prête!',
            body=f'On a créé une image inspirante pour ton rêve: {dream.title}',
            scheduled_for=timezone.now(),
            data={
                'action': 'view_vision',
                'screen': 'VisionBoard',
                'dream_id': str(dream.id),
                'image_url': image_url
            }
        )

        logger.info(f"Generated vision board for dream {dream_id}")
        return {'created': True, 'url': image_url}

    except Dream.DoesNotExist:
        logger.error(f"Dream {dream_id} not found")
        return {'created': False, 'error': 'dream_not_found'}

    except OpenAIError as e:
        logger.error(f"OpenAI error generating vision board for dream {dream_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60)

    except Exception as e:
        logger.error(f"Error generating vision board for dream {dream_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def cleanup_abandoned_dreams():
    """
    Archive dreams that have been inactive for a very long time (90+ days).
    Runs weekly to keep database clean.
    """
    try:
        threshold = timezone.now() - timedelta(days=90)

        # Find dreams with no activity in 90+ days
        abandoned_dreams = Dream.objects.filter(
            status='active',
            updated_at__lt=threshold
        )

        archived_count = 0

        for dream in abandoned_dreams:
            dream.status = 'archived'
            dream.save(update_fields=['status'])
            archived_count += 1

            # Optionally notify user
            Notification.objects.create(
                user=dream.user,
                notification_type='dream_archived',
                title='📦 Rêve archivé',
                body=f'Ton rêve "{dream.title}" a été archivé automatiquement après 90 jours d\'inactivité.',
                scheduled_for=timezone.now(),
                data={
                    'action': 'view_archived',
                    'screen': 'ArchivedDreams',
                    'dream_id': str(dream.id)
                }
            )

        logger.info(f"Archived {archived_count} abandoned dreams")
        return {'archived': archived_count}

    except Exception as e:
        logger.error(f"Error cleaning up abandoned dreams: {str(e)}")
        raise self.retry(exc=e, countdown=300)
