"""
Celery tasks for dreams app.
"""

from celery import shared_task
from django.utils import timezone
from django.utils.translation import gettext as _
from django.db.models import Q, Count, Prefetch
from datetime import timedelta, datetime, time
import json
import logging

from .models import Dream, Goal, Task, Obstacle, DreamMilestone, CalibrationResponse
from apps.users.models import User
from apps.notifications.models import Notification
from integrations.openai_service import OpenAIService
from core.exceptions import OpenAIError

logger = logging.getLogger(__name__)


def _get_plan_redis():
    """Get Redis connection for plan generation status tracking."""
    from django.core.cache import cache
    return cache


def set_plan_status(dream_id, status, **extra):
    """Store plan generation status in Redis (expires in 1 hour)."""
    cache = _get_plan_redis()
    data = {'status': status, **extra}
    cache.set(f'plan_gen:{dream_id}', json.dumps(data), timeout=3600)


def get_plan_status(dream_id):
    """Get plan generation status from Redis."""
    cache = _get_plan_redis()
    raw = cache.get(f'plan_gen:{dream_id}')
    if raw:
        return json.loads(raw) if isinstance(raw, str) else raw
    return None


@shared_task(bind=True, max_retries=1, soft_time_limit=900, time_limit=960)
def generate_dream_plan_task(self, dream_id, user_id):
    """
    Background Celery task for AI plan generation.
    Runs outside the HTTP request so no gunicorn/nginx timeout issues.
    """
    from core.ai_validators import (
        validate_plan_response, validate_calibration_summary,
        check_plan_calibration_coherence, AIValidationError,
    )
    from core.ai_usage import AIUsageTracker
    from datetime import date as date_type

    def _parse_date(date_str):
        if not date_str:
            return None
        try:
            return date_type.fromisoformat(str(date_str).strip()[:10])
        except (ValueError, TypeError):
            return None

    try:
        set_plan_status(dream_id, 'generating', message=_('Starting plan generation...'))

        dream = Dream.objects.get(id=dream_id)
        user = User.objects.get(id=user_id)
        ai_service = OpenAIService()

        user_context = {
            'timezone': dream.user.timezone,
            'work_schedule': dream.user.work_schedule or {},
        }

        # Build calibration context
        calibration_profile_dict = None
        calibration_context_dict = None
        if dream.calibration_status == 'completed':
            qa_pairs = [
                {'question': r.question, 'answer': r.answer}
                for r in CalibrationResponse.objects.filter(dream=dream).order_by('question_number')
                if r.answer and r.answer.strip()
            ]

            if qa_pairs:
                set_plan_status(dream_id, 'generating', message=_('Analyzing your calibration answers...'))
                try:
                    raw_summary = ai_service.generate_calibration_summary(
                        dream.title, dream.description, qa_pairs
                    )
                    summary = validate_calibration_summary(raw_summary)
                    calibration_profile_dict = summary.user_profile.model_dump()
                    calibration_context_dict = summary.model_dump()
                    user_context['calibration_profile'] = calibration_profile_dict
                    user_context['plan_recommendations'] = summary.plan_recommendations.model_dump()
                    if summary.enriched_description:
                        user_context['enriched_description'] = summary.enriched_description
                except (OpenAIError, AIValidationError):
                    pass

        # Generate plan
        set_plan_status(dream_id, 'generating', message=_('AI is building your personalized plan...'))
        _target = str(dream.target_date) if dream.target_date else None
        logger.info(f"generate_dream_plan_task: dream={dream_id} target_date={_target}")

        def _progress(msg):
            set_plan_status(dream_id, 'generating', message=msg)

        raw_plan = ai_service.generate_plan(
            dream.title, dream.description, user_context, target_date=_target,
            progress_callback=_progress,
        )
        logger.info(f"generate_dream_plan_task: raw milestones={len(raw_plan.get('milestones', []))}")

        plan = validate_plan_response(raw_plan)
        logger.info(f"generate_dream_plan_task: validated milestones={len(plan.milestones)} goals={len(plan.goals)}")

        set_plan_status(dream_id, 'generating', message=_('Saving your plan...'))

        # Clear any existing plan data before saving (prevents duplicates on re-generation)
        Task.objects.filter(goal__dream=dream).delete()
        Goal.objects.filter(dream=dream).delete()
        Obstacle.objects.filter(dream=dream).delete()
        DreamMilestone.objects.filter(dream=dream).delete()

        # Increment AI usage
        AIUsageTracker().increment(user, 'ai_plan')

        # Check coherence
        coherence_warnings = check_plan_calibration_coherence(plan, calibration_profile_dict)

        # Save AI analysis
        analysis_data = plan.model_dump()
        if calibration_context_dict:
            analysis_data['calibration_summary'] = calibration_context_dict
        if coherence_warnings:
            analysis_data['coherence_warnings'] = coherence_warnings
        dream.ai_analysis = analysis_data
        dream.save(update_fields=['ai_analysis'])

        plan_start = dream.created_at or timezone.now()

        if plan.milestones:
            milestones_to_create = [
                DreamMilestone(
                    dream=dream, title=ms.title, description=ms.description,
                    order=ms.order,
                    target_date=(plan_start + timedelta(days=ms.target_day)) if ms.target_day else None,
                    expected_date=_parse_date(ms.expected_date),
                    deadline_date=_parse_date(ms.deadline_date),
                )
                for ms in plan.milestones
            ]
            db_milestones = DreamMilestone.objects.bulk_create(milestones_to_create)
            milestone_by_order = {ms.order: db_ms for ms, db_ms in zip(plan.milestones, db_milestones)}

            goals_to_create = []
            goal_data_pairs = []
            for ms_idx, ms_data in enumerate(plan.milestones):
                for goal_data in ms_data.goals:
                    goals_to_create.append(Goal(
                        dream=dream, milestone=db_milestones[ms_idx],
                        title=goal_data.title, description=goal_data.description,
                        order=goal_data.order, estimated_minutes=goal_data.estimated_minutes,
                        expected_date=_parse_date(goal_data.expected_date),
                        deadline_date=_parse_date(goal_data.deadline_date),
                    ))
                    goal_data_pairs.append((goal_data, ms_idx))
            db_goals = Goal.objects.bulk_create(goals_to_create)

            goal_by_key = {}
            for i, (goal_data, ms_idx) in enumerate(goal_data_pairs):
                ms_order = plan.milestones[ms_idx].order
                goal_by_key[(ms_order, goal_data.order)] = db_goals[i]

            tasks_to_create = []
            for i, (goal_data, _) in enumerate(goal_data_pairs):
                for task in goal_data.tasks:
                    scheduled = None
                    if hasattr(task, 'day_number') and task.day_number:
                        scheduled = plan_start + timedelta(days=task.day_number - 1)
                    tasks_to_create.append(Task(
                        goal=db_goals[i], title=task.title, description=task.description,
                        order=task.order, duration_mins=task.duration_mins,
                        scheduled_date=scheduled,
                        expected_date=_parse_date(task.expected_date),
                        deadline_date=_parse_date(task.deadline_date),
                    ))
            Task.objects.bulk_create(tasks_to_create)

            obstacles_to_create = []
            for ms_idx, ms_data in enumerate(plan.milestones):
                for obs in ms_data.obstacles:
                    linked_goal = None
                    if obs.goal_order is not None:
                        linked_goal = goal_by_key.get((ms_data.order, obs.goal_order))
                    obstacles_to_create.append(Obstacle(
                        dream=dream, milestone=db_milestones[ms_idx], goal=linked_goal,
                        title=obs.title, description=obs.description,
                        solution=obs.solution, obstacle_type='predicted',
                    ))
            for obstacle in plan.potential_obstacles:
                linked_milestone = None
                linked_goal = None
                if obstacle.milestone_order is not None:
                    linked_milestone = milestone_by_order.get(obstacle.milestone_order)
                if obstacle.milestone_order is not None and obstacle.goal_order is not None:
                    linked_goal = goal_by_key.get((obstacle.milestone_order, obstacle.goal_order))
                obstacles_to_create.append(Obstacle(
                    dream=dream, milestone=linked_milestone, goal=linked_goal,
                    title=obstacle.title, description=obstacle.description,
                    solution=obstacle.solution, obstacle_type='predicted',
                ))
            Obstacle.objects.bulk_create(obstacles_to_create)
        else:
            # Legacy: direct goals without milestones
            goals_to_create = [
                Goal(dream=dream, title=g.title, description=g.description,
                     order=g.order, estimated_minutes=g.estimated_minutes)
                for g in plan.goals
            ]
            db_goals = Goal.objects.bulk_create(goals_to_create)
            tasks_to_create = []
            for i, goal_data in enumerate(plan.goals):
                for task in goal_data.tasks:
                    scheduled = None
                    if hasattr(task, 'day_number') and task.day_number:
                        scheduled = plan_start + timedelta(days=task.day_number - 1)
                    tasks_to_create.append(Task(
                        goal=db_goals[i], title=task.title, description=task.description,
                        order=task.order, duration_mins=task.duration_mins, scheduled_date=scheduled,
                    ))
            Task.objects.bulk_create(tasks_to_create)
            obstacles_to_create = [
                Obstacle(dream=dream, title=o.title, description=o.description,
                         solution=o.solution, obstacle_type='predicted')
                for o in plan.potential_obstacles
            ]
            Obstacle.objects.bulk_create(obstacles_to_create)

        milestones_count = DreamMilestone.objects.filter(dream=dream).count()
        goals_count = Goal.objects.filter(dream=dream).count()
        tasks_count = Task.objects.filter(goal__dream=dream).count()

        set_plan_status(dream_id, 'completed',
                        message=_('Plan generated successfully!'),
                        milestones=milestones_count,
                        goals=goals_count,
                        tasks=tasks_count)

        logger.info(f"generate_dream_plan_task: DONE dream={dream_id} "
                     f"milestones={milestones_count} goals={goals_count} tasks={tasks_count}")
        return {'status': 'completed', 'milestones': milestones_count,
                'goals': goals_count, 'tasks': tasks_count}

    except Dream.DoesNotExist:
        set_plan_status(dream_id, 'failed', error=_('Dream not found'))
        return {'status': 'failed', 'error': 'dream_not_found'}

    except AIValidationError as e:
        set_plan_status(dream_id, 'failed', error=_('AI produced an invalid plan: %(msg)s') % {'msg': e.message})
        logger.error(f"generate_dream_plan_task: validation error for dream {dream_id}: {e.message}")
        return {'status': 'failed', 'error': str(e)}

    except OpenAIError as e:
        set_plan_status(dream_id, 'failed', error=str(e))
        logger.error(f"generate_dream_plan_task: OpenAI error for dream {dream_id}: {e}")
        raise self.retry(exc=e, countdown=30)

    except Exception as e:
        set_plan_status(dream_id, 'failed', error=str(e))
        logger.error(f"generate_dream_plan_task: unexpected error for dream {dream_id}: {e}", exc_info=True)
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True, max_retries=3)
def generate_two_minute_start(self, dream_id):
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
        micro_action = ai_service.generate_two_minute_start(dream.title, dream.description)

        # Get or create first goal
        first_goal = dream.goals.order_by('order').first()

        if not first_goal:
            # Create initial goal if none exists
            first_goal = Goal.objects.create(
                dream=dream,
                title=_("Get started: %(title)s") % {'title': dream.title},
                description=_("First steps toward your dream"),
                order=0,
                status='pending'
            )

        # Create 2-minute start task at order 0
        Task.objects.create(
            goal=first_goal,
            title=_("Start now: %(action)s") % {'action': micro_action},
            description=_("This micro-action takes only 2 minutes and will help you get started!"),
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
            title=_('Ready to get started in 2 minutes?'),
            body=_('We created a micro-action for your dream: %(action)s') % {'action': micro_action},
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
def auto_schedule_tasks(self, user_id):
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
                title=_('Tasks automatically scheduled'),
                body=_('%(count)s tasks have been added to your calendar!') % {'count': scheduled_count},
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
def detect_obstacles(self, dream_id):
    """
    Use AI to detect potential obstacles for a dream and create obstacle records.
    Called when a dream is analyzed or when user requests obstacle detection.
    """
    try:
        dream = Dream.objects.prefetch_related('goals__tasks').get(id=dream_id)
        ai_service = OpenAIService()

        # Generate obstacle predictions with AI
        obstacles_data = ai_service.predict_obstacles(dream.title, dream.description)

        created_count = 0

        for obstacle_info in obstacles_data:
            # Create or update obstacle
            obstacle, created = Obstacle.objects.get_or_create(
                dream=dream,
                title=obstacle_info['title'],
                defaults={
                    'description': obstacle_info['description'],
                    'obstacle_type': 'predicted',
                    'solution': obstacle_info.get('solution', '')
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
def update_dream_progress(self):
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
                old_progress = dream.progress_percentage
                dream.progress_percentage = progress
                dream.save(update_fields=['progress_percentage'])
                updated_count += 1

                # Check for milestone notifications (25/50/75/100%)
                _check_milestone(dream, old_progress, progress)

                # Check if dream is complete
                if progress >= 100.0 and dream.status != 'completed':
                    dream.status = 'completed'
                    dream.completed_at = timezone.now()
                    dream.save(update_fields=['status', 'completed_at'])

                    # Send completion notification
                    Notification.objects.create(
                        user=dream.user,
                        notification_type='dream_completed',
                        title=_('Dream achieved!'),
                        body=_('Congratulations! You achieved your dream: %(title)s') % {'title': dream.title},
                        scheduled_for=timezone.now(),
                        status='sent',
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
def check_overdue_tasks(self):
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
                title=_('%(count)s overdue task(s)') % {'count': overdue_count},
                body=_('You have %(count)s task(s) waiting to be completed!') % {'count': overdue_count},
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
def suggest_task_adjustments(self, user_id):
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
            # Build task summary for AI analysis
            task_summary = [
                {
                    'title': t.title,
                    'status': t.status,
                    'duration_mins': t.duration_mins,
                    'dream': t.goal.dream.title,
                }
                for t in tasks[:50]  # Limit to avoid token overflow
            ]
            suggestions = ai_service.generate_task_adjustments(
                user.display_name or user.email,
                task_summary,
                completion_rate,
            )

            # Send notification with suggestions
            Notification.objects.create(
                user=user,
                notification_type='coaching',
                title=_('Suggestions to help you succeed'),
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
def generate_vision_board(self, dream_id):
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
        image_url = ai_service.generate_vision_image(dream.title, dream.description)

        # Update dream with image URL
        dream.vision_image_url = image_url
        dream.save(update_fields=['vision_image_url'])

        # Send notification
        Notification.objects.create(
            user=dream.user,
            notification_type='vision_ready',
            title=_('Your vision is ready!'),
            body=_('We created an inspiring image for your dream: %(title)s') % {'title': dream.title},
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
def cleanup_abandoned_dreams(self):
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
                title=_('Dream archived'),
                body=_('Your dream "%(title)s" has been automatically archived after 90 days of inactivity.') % {'title': dream.title},
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


@shared_task(bind=True, max_retries=3)
def smart_archive_dreams(self):
    """
    Auto-pause dreams with no activity for 30+ days and notify the user.

    This is the "smart archive" feature: instead of silently archiving,
    we first pause the dream and notify the user so they can choose to
    resume or let it be archived later (at 90 days by cleanup_abandoned_dreams).
    """
    try:
        threshold = timezone.now() - timedelta(days=30)
        # Only target active dreams (not already paused/archived/completed)
        inactive_dreams = Dream.objects.filter(
            status='active',
            updated_at__lt=threshold,
        ).select_related('user')

        paused_count = 0
        for dream in inactive_dreams:
            # Check if the user has any recent task completions for this dream
            recent_activity = Task.objects.filter(
                goal__dream=dream,
                completed_at__gte=threshold,
            ).exists()

            if recent_activity:
                continue  # Dream has recent activity via tasks, skip

            dream.status = 'paused'
            dream.save(update_fields=['status', 'updated_at'])
            paused_count += 1

            Notification.objects.create(
                user=dream.user,
                notification_type='dream_paused',
                title=_('Dream paused due to inactivity'),
                body=_(
                    'Your dream "%(title)s" has been paused after 30 days '
                    'of inactivity. Open the app to resume it!'
                ) % {'title': dream.title},
                scheduled_for=timezone.now(),
                status='sent',
                data={
                    'action': 'open_dream',
                    'screen': 'DreamDetail',
                    'dream_id': str(dream.id),
                },
            )

        logger.info('Smart archive: paused %d inactive dreams.', paused_count)
        return {'paused': paused_count}

    except Exception as e:
        logger.error('Error in smart_archive_dreams: %s', str(e))
        raise self.retry(exc=e, countdown=300)


def _check_milestone(dream, old_progress, new_progress):
    """
    Check if a dream crossed a milestone boundary and send a notification.

    Milestones: 25%, 50%, 75% (100% is handled separately as dream completion).
    """
    milestones = [
        (25, _('Quarter of the way there!'), 'progress'),
        (50, _('Halfway to your dream!'), 'progress'),
        (75, _('Almost there! Just a little more!'), 'progress'),
    ]

    now = timezone.now()

    for threshold, message, notif_type in milestones:
        if old_progress < threshold <= new_progress:
            Notification.objects.create(
                user=dream.user,
                notification_type=notif_type,
                title=_('%(threshold)s%% - %(message)s') % {'threshold': threshold, 'message': message},
                body=_('Your dream "%(title)s" is now %(threshold)s%% complete. %(message)s') % {'title': dream.title, 'threshold': threshold, 'message': message},
                scheduled_for=now,
                status='sent',
                data={
                    'screen': 'DreamDetail',
                    'dreamId': str(dream.id),
                    'milestone': threshold,
                },
            )
            logger.info(
                'Milestone notification sent: dream %s reached %d%%.',
                dream.id,
                threshold,
            )
