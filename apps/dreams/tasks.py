"""
Celery tasks for dreams app.
"""

import json
import logging
from datetime import datetime, time, timedelta

from celery import shared_task
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.notifications.services import NotificationService
from apps.users.models import User
from core.exceptions import OpenAIError
from integrations.openai_service import OpenAIService

from .models import (
    CalibrationResponse,
    Dream,
    DreamMilestone,
    Goal,
    Obstacle,
    PlanCheckIn,
    Task,
)

logger = logging.getLogger(__name__)


def _get_plan_redis():
    """Get Redis connection for plan generation status tracking."""
    from django.core.cache import cache

    return cache


def set_plan_status(dream_id, status, **extra):
    """Store plan generation status in Redis (expires in 1 hour)."""
    cache = _get_plan_redis()
    data = {"status": status, **extra}
    cache.set(f"plan_gen:{dream_id}", json.dumps(data), timeout=3600)


def get_plan_status(dream_id):
    """Get plan generation status from Redis."""
    cache = _get_plan_redis()
    raw = cache.get(f"plan_gen:{dream_id}")
    if raw:
        return json.loads(raw) if isinstance(raw, str) else raw
    return None


def _parse_date(date_str):
    """Parse a date string (YYYY-MM-DD) into a date object."""
    from datetime import date as date_type

    if not date_str:
        return None
    try:
        return date_type.fromisoformat(str(date_str).strip()[:10])
    except (ValueError, TypeError):
        return None


@shared_task(bind=True, max_retries=1, soft_time_limit=900, time_limit=960)
def generate_dream_plan_task(self, dream_id, user_id):
    """
    Background Celery task for AI plan generation.
    Runs outside the HTTP request so no gunicorn/nginx timeout issues.
    """
    from datetime import date as date_type

    from core.ai_usage import AIUsageTracker
    from core.ai_validators import (
        AIValidationError,
        check_plan_calibration_coherence,
        validate_calibration_summary,
        validate_plan_response,
    )

    def _parse_date(date_str):
        if not date_str:
            return None
        try:
            return date_type.fromisoformat(str(date_str).strip()[:10])
        except (ValueError, TypeError):
            return None

    try:
        set_plan_status(
            dream_id, "generating", message=_("Starting plan generation...")
        )

        dream = Dream.objects.get(id=dream_id)
        user = User.objects.get(id=user_id)
        ai_service = OpenAIService()

        # Get category from AI analysis or dream field
        category = ""
        if dream.ai_analysis and isinstance(dream.ai_analysis, dict):
            category = dream.ai_analysis.get("category", "")

        user_context = {
            "timezone": dream.user.timezone,
            "work_schedule": dream.user.work_schedule or {},
            "category": category,
            "language": dream.language or "",
            "persona": dream.user.persona or {},
        }

        # Build calibration context
        calibration_profile_dict = None
        calibration_context_dict = None
        if dream.calibration_status == "completed":
            qa_pairs = [
                {"question": r.question, "answer": r.answer}
                for r in CalibrationResponse.objects.filter(dream=dream).order_by(
                    "question_number"
                )
                if r.answer and r.answer.strip()
            ]

            if qa_pairs:
                set_plan_status(
                    dream_id,
                    "generating",
                    message=_("Analyzing your calibration answers..."),
                )
                try:
                    raw_summary = ai_service.generate_calibration_summary(
                        dream.title, dream.description, qa_pairs
                    )
                    summary = validate_calibration_summary(raw_summary)
                    calibration_profile_dict = summary.user_profile.model_dump()
                    calibration_context_dict = summary.model_dump()
                    user_context["calibration_profile"] = calibration_profile_dict
                    user_context["plan_recommendations"] = (
                        summary.plan_recommendations.model_dump()
                    )
                    if summary.enriched_description:
                        user_context["enriched_description"] = (
                            summary.enriched_description
                        )

                    # Re-detect category using enriched description + calibration context
                    from integrations.plan_processors import detect_category_from_text

                    enriched_text = summary.enriched_description or dream.description
                    qa_text = " ".join(
                        f"{q['answer']}" for q in qa_pairs if q.get("answer")
                    )
                    refined_category = detect_category_from_text(
                        dream.title, f"{enriched_text} {qa_text}"
                    )
                    if refined_category and refined_category != "other":
                        user_context["category"] = refined_category
                        logger.info(
                            f"generate_dream_plan_task: refined category to '{refined_category}'"
                        )
                except (OpenAIError, AIValidationError):
                    pass

        # Generate plan
        set_plan_status(
            dream_id,
            "generating",
            message=_("AI is building your personalized plan..."),
        )
        _target = str(dream.target_date) if dream.target_date else None
        logger.info(f"generate_dream_plan_task: dream={dream_id} target_date={_target}")

        def _progress(msg):
            set_plan_status(dream_id, "generating", message=msg)

        raw_plan = ai_service.generate_plan(
            dream.title,
            dream.description,
            user_context,
            target_date=_target,
            progress_callback=_progress,
        )
        logger.info(
            f"generate_dream_plan_task: raw milestones={len(raw_plan.get('milestones', []))}"
        )

        plan = validate_plan_response(raw_plan)
        logger.info(
            f"generate_dream_plan_task: validated milestones={len(plan.milestones)} goals={len(plan.goals)}"
        )

        set_plan_status(dream_id, "generating", message=_("Saving your plan..."))

        # Clear any existing plan data before saving (prevents duplicates on re-generation)
        Task.objects.filter(goal__dream=dream).delete()
        Goal.objects.filter(dream=dream).delete()
        Obstacle.objects.filter(dream=dream).delete()
        DreamMilestone.objects.filter(dream=dream).delete()

        # Increment AI usage
        AIUsageTracker().increment(user, "ai_plan")

        # Check coherence
        coherence_warnings = check_plan_calibration_coherence(
            plan, calibration_profile_dict
        )

        # Save AI analysis
        analysis_data = plan.model_dump()
        if calibration_context_dict:
            analysis_data["calibration_summary"] = calibration_context_dict
        if coherence_warnings:
            analysis_data["coherence_warnings"] = coherence_warnings
        dream.ai_analysis = analysis_data
        dream.save(update_fields=["ai_analysis"])

        plan_start = dream.created_at or timezone.now()

        if plan.milestones:
            milestones_to_create = [
                DreamMilestone(
                    dream=dream,
                    title=ms.title,
                    description=ms.description,
                    order=ms.order,
                    target_date=(
                        (plan_start + timedelta(days=ms.target_day))
                        if ms.target_day
                        else None
                    ),
                    expected_date=_parse_date(ms.expected_date),
                    deadline_date=_parse_date(ms.deadline_date),
                )
                for ms in plan.milestones
            ]
            db_milestones = DreamMilestone.objects.bulk_create(milestones_to_create)
            milestone_by_order = {
                ms.order: db_ms for ms, db_ms in zip(plan.milestones, db_milestones)
            }

            goals_to_create = []
            goal_data_pairs = []
            for ms_idx, ms_data in enumerate(plan.milestones):
                for goal_data in ms_data.goals:
                    goals_to_create.append(
                        Goal(
                            dream=dream,
                            milestone=db_milestones[ms_idx],
                            title=goal_data.title,
                            description=goal_data.description,
                            order=goal_data.order,
                            estimated_minutes=goal_data.estimated_minutes,
                            expected_date=_parse_date(goal_data.expected_date),
                            deadline_date=_parse_date(goal_data.deadline_date),
                        )
                    )
                    goal_data_pairs.append((goal_data, ms_idx))
            db_goals = Goal.objects.bulk_create(goals_to_create)

            goal_by_key = {}
            for i, (goal_data, ms_idx) in enumerate(goal_data_pairs):
                ms_order = plan.milestones[ms_idx].order
                goal_by_key[(ms_order, goal_data.order)] = db_goals[i]

            tasks_to_create = []
            for i, (goal_data, _ms_idx) in enumerate(goal_data_pairs):
                for task in goal_data.tasks:
                    scheduled = None
                    if hasattr(task, "day_number") and task.day_number:
                        scheduled = plan_start + timedelta(days=task.day_number - 1)
                    tasks_to_create.append(
                        Task(
                            goal=db_goals[i],
                            title=task.title,
                            description=task.description,
                            order=task.order,
                            duration_mins=task.duration_mins,
                            scheduled_date=scheduled,
                            expected_date=_parse_date(task.expected_date),
                            deadline_date=_parse_date(task.deadline_date),
                        )
                    )
            Task.objects.bulk_create(tasks_to_create)

            obstacles_to_create = []
            for ms_idx, ms_data in enumerate(plan.milestones):
                for obs in ms_data.obstacles:
                    linked_goal = None
                    if obs.goal_order is not None:
                        linked_goal = goal_by_key.get((ms_data.order, obs.goal_order))
                    obstacles_to_create.append(
                        Obstacle(
                            dream=dream,
                            milestone=db_milestones[ms_idx],
                            goal=linked_goal,
                            title=obs.title,
                            description=obs.description,
                            solution=obs.solution,
                            obstacle_type="predicted",
                        )
                    )
            for obstacle in plan.potential_obstacles:
                linked_milestone = None
                linked_goal = None
                if obstacle.milestone_order is not None:
                    linked_milestone = milestone_by_order.get(obstacle.milestone_order)
                if (
                    obstacle.milestone_order is not None
                    and obstacle.goal_order is not None
                ):
                    linked_goal = goal_by_key.get(
                        (obstacle.milestone_order, obstacle.goal_order)
                    )
                obstacles_to_create.append(
                    Obstacle(
                        dream=dream,
                        milestone=linked_milestone,
                        goal=linked_goal,
                        title=obstacle.title,
                        description=obstacle.description,
                        solution=obstacle.solution,
                        obstacle_type="predicted",
                    )
                )
            Obstacle.objects.bulk_create(obstacles_to_create)
        else:
            # Legacy: direct goals without milestones
            goals_to_create = [
                Goal(
                    dream=dream,
                    title=g.title,
                    description=g.description,
                    order=g.order,
                    estimated_minutes=g.estimated_minutes,
                )
                for g in plan.goals
            ]
            db_goals = Goal.objects.bulk_create(goals_to_create)
            tasks_to_create = []
            for i, goal_data in enumerate(plan.goals):
                for task in goal_data.tasks:
                    scheduled = None
                    if hasattr(task, "day_number") and task.day_number:
                        scheduled = plan_start + timedelta(days=task.day_number - 1)
                    tasks_to_create.append(
                        Task(
                            goal=db_goals[i],
                            title=task.title,
                            description=task.description,
                            order=task.order,
                            duration_mins=task.duration_mins,
                            scheduled_date=scheduled,
                        )
                    )
            Task.objects.bulk_create(tasks_to_create)
            obstacles_to_create = [
                Obstacle(
                    dream=dream,
                    title=o.title,
                    description=o.description,
                    solution=o.solution,
                    obstacle_type="predicted",
                )
                for o in plan.potential_obstacles
            ]
            Obstacle.objects.bulk_create(obstacles_to_create)

        milestones_count = DreamMilestone.objects.filter(dream=dream).count()
        goals_count = Goal.objects.filter(dream=dream).count()
        tasks_count = Task.objects.filter(goal__dream=dream).count()

        set_plan_status(
            dream_id,
            "completed",
            message=_("Plan generated successfully!"),
            milestones=milestones_count,
            goals=goals_count,
            tasks=tasks_count,
        )

        # Send notification to user that plan is ready
        try:
            NotificationService.create(
                user=user,
                notification_type="dream_completed",
                title=_("Your plan is ready!"),
                body=_(
                    'Your personalized plan for "%(title)s" has been generated with %(goals)s goals and %(tasks)s tasks.'
                )
                % {
                    "title": dream.title[:50],
                    "goals": goals_count,
                    "tasks": tasks_count,
                },
                scheduled_for=timezone.now(),
                data={
                    "screen": "dream",
                    "dream_id": str(dream_id),
                    "action": "plan_ready",
                },
            )
        except Exception as e:
            logger.warning(f"Failed to create plan-ready notification: {e}")

        logger.info(
            f"generate_dream_plan_task: DONE dream={dream_id} "
            f"milestones={milestones_count} goals={goals_count} tasks={tasks_count}"
        )
        return {
            "status": "completed",
            "milestones": milestones_count,
            "goals": goals_count,
            "tasks": tasks_count,
        }

    except Dream.DoesNotExist:
        set_plan_status(dream_id, "failed", error=_("Dream not found"))
        return {"status": "failed", "error": "dream_not_found"}

    except AIValidationError as e:
        set_plan_status(
            dream_id,
            "failed",
            error=_("AI produced an invalid plan: %(msg)s") % {"msg": e.message},
        )
        logger.error(
            f"generate_dream_plan_task: validation error for dream {dream_id}: {e.message}"
        )
        return {"status": "failed", "error": str(e)}

    except OpenAIError as e:
        set_plan_status(dream_id, "failed", error=str(e))
        logger.error(
            f"generate_dream_plan_task: OpenAI error for dream {dream_id}: {e}"
        )
        raise self.retry(exc=e, countdown=30)

    except Exception as e:
        set_plan_status(dream_id, "failed", error=str(e))
        logger.error(
            f"generate_dream_plan_task: unexpected error for dream {dream_id}: {e}",
            exc_info=True,
        )
        return {"status": "failed", "error": str(e)}


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
            return {"created": False, "reason": "already_exists"}

        ai_service = OpenAIService()

        # Generate micro-action with AI
        micro_action = ai_service.generate_two_minute_start(
            dream.title, dream.description
        )

        # Get or create first goal
        first_goal = dream.goals.order_by("order").first()

        if not first_goal:
            # Create initial goal if none exists
            first_goal = Goal.objects.create(
                dream=dream,
                title=_("Get started: %(title)s") % {"title": dream.title},
                description=_("First steps toward your dream"),
                order=0,
                status="pending",
            )

        # Create 2-minute start task at order 0
        Task.objects.create(
            goal=first_goal,
            title=_("Start now: %(action)s") % {"action": micro_action},
            description=_(
                "This micro-action takes only 2 minutes and will help you get started!"
            ),
            order=0,
            duration_mins=2,
            scheduled_date=timezone.now(),
            status="pending",
        )

        # Mark dream as having 2-minute start
        dream.has_two_minute_start = True
        dream.save(update_fields=["has_two_minute_start"])

        # Send notification
        NotificationService.create(
            user=dream.user,
            notification_type="task_created",
            title=_("Ready to get started in 2 minutes?"),
            body=_("We created a micro-action for your dream: %(action)s")
            % {"action": micro_action},
            scheduled_for=timezone.now(),
            data={
                "action": "open_dream",
                "screen": "DreamDetail",
                "dream_id": str(dream.id),
            },
        )

        logger.info(f"Created 2-minute start for dream {dream_id}: {micro_action}")
        return {"created": True, "action": micro_action}

    except Dream.DoesNotExist:
        logger.error(f"Dream {dream_id} not found")
        return {"created": False, "error": "dream_not_found"}

    except OpenAIError as e:
        logger.error(
            f"OpenAI error generating 2-minute start for dream {dream_id}: {str(e)}"
        )
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
        unscheduled_tasks = (
            Task.objects.filter(
                goal__dream__user=user,
                goal__dream__status="active",
                scheduled_date__isnull=True,
                status="pending",
            )
            .select_related("goal", "goal__dream")
            .order_by("goal__order", "order")
        )

        if not unscheduled_tasks.exists():
            logger.info(f"No unscheduled tasks for user {user_id}")
            return {"scheduled": 0}

        # Get user's work schedule preferences
        work_schedule = user.work_schedule or {}
        start_date = timezone.now().date()
        scheduled_count = 0

        # Default work hours if not specified
        default_start_hour = work_schedule.get("start_hour", 9)
        default_end_hour = work_schedule.get("end_hour", 17)
        working_days = work_schedule.get("working_days", [1, 2, 3, 4, 5])  # Mon-Fri

        current_date = start_date
        current_time_slot = datetime.combine(
            current_date, time(hour=default_start_hour)
        )

        for task in unscheduled_tasks:
            # Find next available time slot
            while current_date.isoweekday() not in working_days:
                current_date += timedelta(days=1)
                current_time_slot = datetime.combine(
                    current_date, time(hour=default_start_hour)
                )

            # Check if we have enough time today
            duration = task.duration_mins or 30  # Default 30 mins
            end_of_day = datetime.combine(current_date, time(hour=default_end_hour))

            if current_time_slot + timedelta(minutes=duration) > end_of_day:
                # Move to next day
                current_date += timedelta(days=1)
                while current_date.isoweekday() not in working_days:
                    current_date += timedelta(days=1)
                current_time_slot = datetime.combine(
                    current_date, time(hour=default_start_hour)
                )

            # Schedule the task
            task.scheduled_date = timezone.make_aware(current_time_slot)
            task.scheduled_time = current_time_slot.strftime("%H:%M")
            task.save(update_fields=["scheduled_date", "scheduled_time"])

            scheduled_count += 1

            # Move time slot forward
            current_time_slot += timedelta(minutes=duration + 15)  # 15 min buffer

        # Send notification
        if scheduled_count > 0:
            NotificationService.create(
                user=user,
                notification_type="tasks_scheduled",
                title=_("Tasks automatically scheduled"),
                body=_("%(count)s tasks have been added to your calendar!")
                % {"count": scheduled_count},
                scheduled_for=timezone.now(),
                data={
                    "action": "open_calendar",
                    "screen": "Calendar",
                    "scheduled_count": scheduled_count,
                },
            )

        logger.info(f"Auto-scheduled {scheduled_count} tasks for user {user_id}")
        return {"scheduled": scheduled_count}

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {"scheduled": 0, "error": "user_not_found"}

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
        dream = Dream.objects.prefetch_related("goals__tasks").get(id=dream_id)
        ai_service = OpenAIService()

        # Generate obstacle predictions with AI
        obstacles_data = ai_service.predict_obstacles_simple(
            dream.title, dream.description
        )

        created_count = 0

        for obstacle_info in obstacles_data:
            # Create or update obstacle
            obstacle, created = Obstacle.objects.get_or_create(
                dream=dream,
                title=obstacle_info["title"],
                defaults={
                    "description": obstacle_info["description"],
                    "obstacle_type": "predicted",
                    "solution": obstacle_info.get("solution", ""),
                },
            )

            if created:
                created_count += 1

        logger.info(f"Detected {created_count} obstacles for dream {dream_id}")
        return {"created": created_count, "obstacles": obstacles_data}

    except Dream.DoesNotExist:
        logger.error(f"Dream {dream_id} not found")
        return {"created": 0, "error": "dream_not_found"}

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
        active_dreams = Dream.objects.filter(status="active").prefetch_related(
            "goals__tasks"
        )

        updated_count = 0

        for dream in active_dreams:
            # Calculate total and completed tasks
            total_tasks = 0
            completed_tasks = 0

            for goal in dream.goals.all():
                tasks = goal.tasks.all()
                total_tasks += tasks.count()
                completed_tasks += tasks.filter(status="completed").count()

            # Calculate progress percentage
            if total_tasks > 0:
                progress = (completed_tasks / total_tasks) * 100
            else:
                progress = 0.0

            # Update if changed
            if dream.progress_percentage != progress:
                old_progress = dream.progress_percentage
                dream.progress_percentage = progress
                dream.save(update_fields=["progress_percentage"])
                updated_count += 1

                # Check for milestone notifications (25/50/75/100%)
                _check_milestone(dream, old_progress, progress)

                # Check if dream is complete
                if progress >= 100.0 and dream.status != "completed":
                    dream.status = "completed"
                    dream.completed_at = timezone.now()
                    dream.save(update_fields=["status", "completed_at"])

                    # Send completion notification
                    NotificationService.create(
                        user=dream.user,
                        notification_type="dream_completed",
                        title=_("Dream achieved!"),
                        body=_("Congratulations! You achieved your dream: %(title)s")
                        % {"title": dream.title},
                        scheduled_for=timezone.now(),
                        status="sent",
                        data={
                            "action": "open_dream",
                            "screen": "DreamDetail",
                            "dream_id": str(dream.id),
                        },
                    )

        logger.info(f"Updated progress for {updated_count} dreams")
        return {"updated": updated_count}

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
            status="pending",
        ).select_related("goal", "goal__dream", "goal__dream__user")

        # Group by user
        users_with_overdue = {}
        for task in overdue_tasks:
            user_id = task.goal.dream.user.id
            if user_id not in users_with_overdue:
                users_with_overdue[user_id] = {
                    "user": task.goal.dream.user,
                    "tasks": [],
                }
            users_with_overdue[user_id]["tasks"].append(task)

        created_count = 0

        for user_data in users_with_overdue.values():
            user = user_data["user"]
            overdue_count = len(user_data["tasks"])

            # Send notification
            NotificationService.create(
                user=user,
                notification_type="overdue_tasks",
                title=_("%(count)s overdue task(s)") % {"count": overdue_count},
                body=_("You have %(count)s task(s) waiting to be completed!")
                % {"count": overdue_count},
                scheduled_for=now,
                data={
                    "action": "open_calendar",
                    "screen": "Calendar",
                    "filter": "overdue",
                },
            )

            created_count += 1

        logger.info(f"Sent {created_count} overdue task notifications")
        return {"sent": created_count, "total_overdue_tasks": len(overdue_tasks)}

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
            goal__dream__user=user, created_at__gte=thirty_days_ago
        ).select_related("goal", "goal__dream")

        # Calculate completion rate
        total = tasks.count()
        completed = tasks.filter(status="completed").count()
        completion_rate = (completed / total * 100) if total > 0 else 0

        # If completion rate is low, generate suggestions
        if completion_rate < 50:
            # Build task summary for AI analysis
            task_summary = [
                {
                    "title": t.title,
                    "status": t.status,
                    "duration_mins": t.duration_mins,
                    "dream": t.goal.dream.title,
                }
                for t in tasks[:50]  # Limit to avoid token overflow
            ]
            suggestions = ai_service.generate_task_adjustments(
                user.display_name or user.email,
                task_summary,
                completion_rate,
            )

            # Send notification with suggestions
            NotificationService.create(
                user=user,
                notification_type="coaching",
                title=_("Suggestions to help you succeed"),
                body=suggestions["summary"],
                scheduled_for=timezone.now(),
                data={
                    "action": "view_suggestions",
                    "screen": "CoachingSuggestions",
                    "suggestions": suggestions["detailed"],
                    "completion_rate": completion_rate,
                },
            )

            logger.info(f"Sent task adjustment suggestions to user {user_id}")
            return {"sent": True, "completion_rate": completion_rate}

        logger.info(f"User {user_id} has good completion rate: {completion_rate}%")
        return {"sent": False, "completion_rate": completion_rate}

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {"sent": False, "error": "user_not_found"}

    except OpenAIError as e:
        logger.error(
            f"OpenAI error generating suggestions for user {user_id}: {str(e)}"
        )
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
            return {
                "created": False,
                "reason": "already_exists",
                "url": dream.vision_image_url,
            }

        ai_service = OpenAIService()

        # Generate vision board image with DALL-E
        image_url = ai_service.generate_vision_image(dream.title, dream.description)

        # Update dream with image URL
        dream.vision_image_url = image_url
        dream.save(update_fields=["vision_image_url"])

        # Send notification
        NotificationService.create(
            user=dream.user,
            notification_type="vision_ready",
            title=_("Your vision is ready!"),
            body=_("We created an inspiring image for your dream: %(title)s")
            % {"title": dream.title},
            scheduled_for=timezone.now(),
            data={
                "action": "view_vision",
                "screen": "VisionBoard",
                "dream_id": str(dream.id),
                "image_url": image_url,
            },
        )

        logger.info(f"Generated vision board for dream {dream_id}")
        return {"created": True, "url": image_url}

    except Dream.DoesNotExist:
        logger.error(f"Dream {dream_id} not found")
        return {"created": False, "error": "dream_not_found"}

    except OpenAIError as e:
        logger.error(
            f"OpenAI error generating vision board for dream {dream_id}: {str(e)}"
        )
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
            status="active", updated_at__lt=threshold
        )

        archived_count = 0

        for dream in abandoned_dreams:
            dream.status = "archived"
            dream.save(update_fields=["status"])
            archived_count += 1

            # Optionally notify user
            NotificationService.create(
                user=dream.user,
                notification_type="dream_archived",
                title=_("Dream archived"),
                body=_(
                    'Your dream "%(title)s" has been automatically archived after 90 days of inactivity.'
                )
                % {"title": dream.title},
                scheduled_for=timezone.now(),
                data={
                    "action": "view_archived",
                    "screen": "ArchivedDreams",
                    "dream_id": str(dream.id),
                },
            )

        logger.info(f"Archived {archived_count} abandoned dreams")
        return {"archived": archived_count}

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
            status="active",
            updated_at__lt=threshold,
        ).select_related("user")

        paused_count = 0
        for dream in inactive_dreams:
            # Check if the user has any recent task completions for this dream
            recent_activity = Task.objects.filter(
                goal__dream=dream,
                completed_at__gte=threshold,
            ).exists()

            if recent_activity:
                continue  # Dream has recent activity via tasks, skip

            dream.status = "paused"
            dream.save(update_fields=["status", "updated_at"])
            paused_count += 1

            NotificationService.create(
                user=dream.user,
                notification_type="dream_paused",
                title=_("Dream paused due to inactivity"),
                body=_(
                    'Your dream "%(title)s" has been paused after 30 days '
                    "of inactivity. Open the app to resume it!"
                )
                % {"title": dream.title},
                scheduled_for=timezone.now(),
                status="sent",
                data={
                    "action": "open_dream",
                    "screen": "DreamDetail",
                    "dream_id": str(dream.id),
                },
            )

        logger.info("Smart archive: paused %d inactive dreams.", paused_count)
        return {"paused": paused_count}

    except Exception as e:
        logger.error("Error in smart_archive_dreams: %s", str(e))
        raise self.retry(exc=e, countdown=300)


def _check_milestone(dream, old_progress, new_progress):
    """
    Check if a dream crossed a milestone boundary and send a notification.

    Milestones: 25%, 50%, 75% (100% is handled separately as dream completion).
    """
    milestones = [
        (25, _("Quarter of the way there!"), "progress"),
        (50, _("Halfway to your dream!"), "progress"),
        (75, _("Almost there! Just a little more!"), "progress"),
    ]

    now = timezone.now()

    for threshold, message, notif_type in milestones:
        if old_progress < threshold <= new_progress:
            NotificationService.create(
                user=dream.user,
                notification_type=notif_type,
                title=_("%(threshold)s%% - %(message)s")
                % {"threshold": threshold, "message": message},
                body=_(
                    'Your dream "%(title)s" is now %(threshold)s%% complete. %(message)s'
                )
                % {"title": dream.title, "threshold": threshold, "message": message},
                scheduled_for=now,
                status="sent",
                data={
                    "screen": "DreamDetail",
                    "dream_id": str(dream.id),
                    "milestone": threshold,
                },
            )
            logger.info(
                "Milestone notification sent: dream %s reached %d%%.",
                dream.id,
                threshold,
            )


@shared_task(bind=True, max_retries=1, soft_time_limit=300, time_limit=360)
def generate_dream_skeleton_task(self, dream_id, user_id):
    """
    Phase 1: Generate skeleton plan (milestones + goals, no tasks).
    After success, automatically chains to generate_initial_tasks_task.
    """
    from core.ai_usage import AIUsageTracker
    from core.ai_validators import AIValidationError, validate_skeleton_response

    try:
        set_plan_status(dream_id, "generating", message="Designing your roadmap...")

        dream = Dream.objects.get(id=dream_id)
        user = User.objects.get(id=user_id)
        ai_service = OpenAIService()

        category = ""
        if dream.ai_analysis and isinstance(dream.ai_analysis, dict):
            category = dream.ai_analysis.get("category", "")

        user_context = {
            "timezone": dream.user.timezone,
            "work_schedule": dream.user.work_schedule or {},
            "category": category,
            "language": dream.language or "",
            "persona": dream.user.persona or {},
        }

        # Build calibration context (same pattern as generate_dream_plan_task)
        if dream.calibration_status == "completed":
            from core.ai_validators import validate_calibration_summary

            qa_pairs = [
                {"question": r.question, "answer": r.answer}
                for r in CalibrationResponse.objects.filter(dream=dream).order_by(
                    "question_number"
                )
                if r.answer and r.answer.strip()
            ]
            if qa_pairs:
                set_plan_status(
                    dream_id,
                    "generating",
                    message="Analyzing your calibration answers...",
                )
                try:
                    raw_summary = ai_service.generate_calibration_summary(
                        dream.title, dream.description, qa_pairs
                    )
                    summary = validate_calibration_summary(raw_summary)
                    user_context["calibration_profile"] = (
                        summary.user_profile.model_dump()
                    )
                    user_context["plan_recommendations"] = (
                        summary.plan_recommendations.model_dump()
                    )
                    if summary.enriched_description:
                        user_context["enriched_description"] = (
                            summary.enriched_description
                        )
                except Exception:
                    pass

        def _progress(msg):
            set_plan_status(dream_id, "generating", message=msg)

        _target = str(dream.target_date) if dream.target_date else None
        raw_skeleton = ai_service.generate_skeleton(
            dream.title,
            dream.description,
            user_context,
            target_date=_target,
            progress_callback=_progress,
        )

        skeleton = validate_skeleton_response(raw_skeleton)
        logger.info(
            f"generate_dream_skeleton_task: validated {len(skeleton.milestones)} milestones"
        )

        set_plan_status(dream_id, "generating", message="Saving your roadmap...")

        # Clear existing plan data
        Task.objects.filter(goal__dream=dream).delete()
        Goal.objects.filter(dream=dream).delete()
        Obstacle.objects.filter(dream=dream).delete()
        DreamMilestone.objects.filter(dream=dream).delete()

        AIUsageTracker().increment(user, "ai_plan")

        # Save skeleton to dream
        skeleton_dict = skeleton.model_dump()
        dream.plan_skeleton = skeleton_dict
        dream.ai_analysis = skeleton_dict
        dream.plan_phase = "skeleton"
        dream.save(update_fields=["plan_skeleton", "ai_analysis", "plan_phase"])

        plan_start = dream.created_at or timezone.now()

        # Create milestones and goals (NO tasks)
        for ms_data in skeleton.milestones:
            db_milestone = DreamMilestone.objects.create(
                dream=dream,
                title=ms_data.title,
                description=ms_data.description,
                order=ms_data.order,
                target_date=(
                    (plan_start + timedelta(days=ms_data.target_day))
                    if ms_data.target_day
                    else None
                ),
                expected_date=_parse_date(ms_data.expected_date),
                deadline_date=_parse_date(ms_data.deadline_date),
                has_tasks=False,
            )

            for goal_data in ms_data.goals:
                Goal.objects.create(
                    dream=dream,
                    milestone=db_milestone,
                    title=goal_data.title,
                    description=goal_data.description,
                    order=goal_data.order,
                    estimated_minutes=goal_data.estimated_minutes,
                    expected_date=_parse_date(goal_data.expected_date),
                    deadline_date=_parse_date(goal_data.deadline_date),
                )

            # Create obstacles for this milestone
            for obs in ms_data.obstacles:
                Obstacle.objects.create(
                    dream=dream,
                    milestone=db_milestone,
                    title=obs.title,
                    description=obs.description,
                    solution=obs.solution,
                    obstacle_type="predicted",
                )

        # Create top-level obstacles
        for obs in skeleton.potential_obstacles:
            Obstacle.objects.create(
                dream=dream,
                title=obs.title,
                description=obs.description,
                solution=obs.solution,
                obstacle_type="predicted",
            )

        set_plan_status(
            dream_id, "generating", message="Generating your first tasks..."
        )

        # Chain to task generation (use apply_async to ensure correct queue)
        generate_initial_tasks_task.apply_async(
            args=[dream_id, user_id], queue="dreams"
        )

        logger.info(f"generate_dream_skeleton_task: DONE dream={dream_id}")
        return {"status": "skeleton_complete", "milestones": len(skeleton.milestones)}

    except Dream.DoesNotExist:
        set_plan_status(dream_id, "failed", error="Dream not found")
        return {"status": "failed", "error": "dream_not_found"}

    except AIValidationError as e:
        set_plan_status(
            dream_id, "failed", error=f"AI produced invalid skeleton: {e.message}"
        )
        logger.error(
            f"generate_dream_skeleton_task: validation error for dream {dream_id}: {e.message}"
        )
        return {"status": "failed", "error": str(e)}

    except OpenAIError as e:
        set_plan_status(dream_id, "failed", error=str(e))
        logger.error(
            f"generate_dream_skeleton_task: OpenAI error for dream {dream_id}: {e}"
        )
        raise self.retry(exc=e, countdown=30)

    except Exception as e:
        set_plan_status(dream_id, "failed", error=str(e))
        logger.error(
            f"generate_dream_skeleton_task: unexpected error for dream {dream_id}: {e}",
            exc_info=True,
        )
        return {"status": "failed", "error": str(e)}


@shared_task(bind=True, max_retries=1, soft_time_limit=600, time_limit=660)
def generate_initial_tasks_task(self, dream_id, user_id):
    """
    Phase 2: Generate detailed tasks for months 1-4 of the skeleton.
    Called automatically after skeleton generation.
    """
    from core.ai_validators import AIValidationError, validate_task_patches

    try:
        dream = Dream.objects.get(id=dream_id)
        user = User.objects.get(id=user_id)

        if not dream.plan_skeleton or dream.plan_phase not in ("skeleton", "partial"):
            logger.warning(
                f"generate_initial_tasks_task: dream {dream_id} not in skeleton phase"
            )
            return {"status": "skipped", "reason": "wrong_phase"}

        ai_service = OpenAIService()

        category = ""
        if dream.ai_analysis and isinstance(dream.ai_analysis, dict):
            category = dream.ai_analysis.get("category", "")

        user_context = {
            "timezone": dream.user.timezone,
            "work_schedule": dream.user.work_schedule or {},
            "category": category,
            "language": dream.language or "",
            "persona": dream.user.persona or {},
        }

        # Add calibration profile if available
        if dream.ai_analysis and isinstance(dream.ai_analysis, dict):
            cal_profile = dream.ai_analysis.get("calibration_summary", {}).get(
                "user_profile"
            )
            if cal_profile:
                user_context["calibration_profile"] = cal_profile

        _target = str(dream.target_date) if dream.target_date else None

        # Calculate total months
        from datetime import date as date_type

        total_months = 12
        if dream.target_date:
            today = date_type.today()
            target = (
                dream.target_date.date()
                if hasattr(dream.target_date, "date")
                else dream.target_date
            )
            total_days = max(1, (target - today).days)
            total_months = max(1, total_days // 30)

        months_to_generate = min(4, total_months)

        def _progress(msg):
            set_plan_status(dream_id, "generating", message=msg)

        set_plan_status(
            dream_id,
            "generating",
            message=f"Generating tasks for months 1-{months_to_generate}...",
        )

        raw_patches = ai_service.generate_tasks_for_months(
            dream.title,
            dream.description,
            dream.plan_skeleton,
            user_context,
            1,
            months_to_generate,
            target_date=_target,
            progress_callback=_progress,
        )

        patches = validate_task_patches(raw_patches)
        logger.info(
            f"generate_initial_tasks_task: {len(patches)} task patches validated"
        )

        plan_start = dream.created_at or timezone.now()
        tasks_created_count = 0
        milestones_with_tasks = set()

        for patch in patches:
            milestone = DreamMilestone.objects.filter(
                dream=dream, order=patch.milestone_order
            ).first()
            if not milestone:
                logger.warning(
                    f"Milestone order {patch.milestone_order} not found for dream {dream_id}"
                )
                continue

            goal = Goal.objects.filter(
                milestone=milestone, order=patch.goal_order
            ).first()
            if not goal:
                logger.warning(
                    f"Goal order {patch.goal_order} in milestone {patch.milestone_order} not found"
                )
                continue

            for task_data in patch.tasks:
                scheduled = None
                if task_data.day_number:
                    scheduled = plan_start + timedelta(days=task_data.day_number - 1)

                Task.objects.create(
                    goal=goal,
                    title=task_data.title,
                    description=task_data.description,
                    order=task_data.order,
                    duration_mins=task_data.duration_mins,
                    scheduled_date=scheduled,
                    expected_date=_parse_date(task_data.expected_date),
                    deadline_date=_parse_date(task_data.deadline_date),
                )
                tasks_created_count += 1

            milestones_with_tasks.add(milestone.id)

        # Mark milestones as having tasks
        DreamMilestone.objects.filter(id__in=milestones_with_tasks).update(
            has_tasks=True
        )

        # Update dream
        dream.tasks_generated_through_month = months_to_generate
        dream.plan_phase = "partial" if months_to_generate < total_months else "full"
        dream.next_checkin_at = timezone.now() + timedelta(days=14)
        dream.save(
            update_fields=[
                "tasks_generated_through_month",
                "plan_phase",
                "next_checkin_at",
            ]
        )

        milestones_count = DreamMilestone.objects.filter(dream=dream).count()
        goals_count = Goal.objects.filter(dream=dream).count()

        set_plan_status(
            dream_id,
            "completed",
            message="Plan generated successfully!",
            milestones=milestones_count,
            goals=goals_count,
            tasks=tasks_created_count,
        )

        # Send notification
        try:
            NotificationService.create(
                user=user,
                notification_type="dream_completed",
                title="Your plan is ready!",
                body=f'Your personalized plan for "{dream.title[:50]}" has been generated with {goals_count} goals and {tasks_created_count} tasks.',
                scheduled_for=timezone.now(),
                data={
                    "screen": "dream",
                    "dream_id": str(dream_id),
                    "action": "plan_ready",
                },
            )
        except Exception as e:
            logger.warning(f"Failed to create plan-ready notification: {e}")

        logger.info(
            f"generate_initial_tasks_task: DONE dream={dream_id} tasks={tasks_created_count}"
        )
        return {"status": "completed", "tasks": tasks_created_count}

    except Dream.DoesNotExist:
        set_plan_status(dream_id, "failed", error="Dream not found")
        return {"status": "failed", "error": "dream_not_found"}

    except AIValidationError as e:
        set_plan_status(
            dream_id, "failed", error=f"AI produced invalid tasks: {e.message}"
        )
        logger.error(
            f"generate_initial_tasks_task: validation error for dream {dream_id}: {e.message}"
        )
        return {"status": "failed", "error": str(e)}

    except OpenAIError as e:
        set_plan_status(dream_id, "failed", error=str(e))
        logger.error(
            f"generate_initial_tasks_task: OpenAI error for dream {dream_id}: {e}"
        )
        raise self.retry(exc=e, countdown=30)

    except Exception as e:
        set_plan_status(dream_id, "failed", error=str(e))
        logger.error(
            f"generate_initial_tasks_task: unexpected error for dream {dream_id}: {e}",
            exc_info=True,
        )
        return {"status": "failed", "error": str(e)}


@shared_task(bind=True, max_retries=0)
def run_biweekly_checkins(self):
    """
    Beat task: Find all dreams due for a check-in and fan out interactive questionnaires.
    Runs daily at 6 AM, processes dreams where next_checkin_at <= now.
    """
    try:
        now = timezone.now()
        due_dreams = Dream.objects.filter(
            status="active",
            plan_phase__in=["partial", "full"],
            next_checkin_at__lte=now,
        ).select_related("user")

        checkin_count = 0
        for dream in due_dreams:
            # Skip if there's already an active check-in for this dream
            active_exists = PlanCheckIn.objects.filter(
                dream=dream,
                status__in=[
                    "pending",
                    "questionnaire_generating",
                    "awaiting_user",
                    "ai_processing",
                ],
            ).exists()
            if active_exists:
                continue

            checkin = PlanCheckIn.objects.create(
                dream=dream,
                status="pending",
                scheduled_for=now,
                triggered_by="schedule",
            )
            # Dispatch interactive questionnaire generation
            generate_checkin_questionnaire_task.apply_async(
                args=[str(checkin.id)], queue="dreams"
            )
            checkin_count += 1

        logger.info(
            f"run_biweekly_checkins: dispatched {checkin_count} interactive check-ins"
        )
        return {"dispatched": checkin_count}

    except Exception as e:
        logger.error(f"run_biweekly_checkins error: {e}", exc_info=True)
        return {"dispatched": 0, "error": str(e)}


@shared_task(bind=True, max_retries=1, soft_time_limit=300, time_limit=360)
def run_single_checkin_task(self, checkin_id):
    """
    Run AI check-in for a single dream.
    The AI agent assesses progress, creates/adjusts tasks, and sends coaching.
    """
    try:
        checkin = PlanCheckIn.objects.select_related("dream", "dream__user").get(
            id=checkin_id
        )
        dream = checkin.dream
        user = dream.user

        checkin.status = "ai_processing"
        checkin.started_at = timezone.now()
        checkin.progress_at_checkin = dream.progress_percentage
        checkin.save(update_fields=["status", "started_at", "progress_at_checkin"])

        # Count tasks since last check-in
        since = dream.last_checkin_at or (timezone.now() - timedelta(days=14))
        checkin.tasks_completed_since_last = Task.objects.filter(
            goal__dream=dream, status="completed", completed_at__gte=since
        ).count()
        checkin.tasks_overdue_at_checkin = Task.objects.filter(
            goal__dream=dream, status="pending", deadline_date__lt=timezone.now().date()
        ).count()
        checkin.save(
            update_fields=["tasks_completed_since_last", "tasks_overdue_at_checkin"]
        )

        ai_service = OpenAIService()
        result = ai_service.run_checkin_agent(dream, user)

        # Update check-in record
        checkin.coaching_message = result.get("coaching_message", "")
        checkin.adjustment_summary = result.get("adjustment_summary", "")
        checkin.ai_actions = result.get("actions_taken", [])
        checkin.months_generated_through = max(
            dream.tasks_generated_through_month,
            result.get("months_generated_through", dream.tasks_generated_through_month),
        )
        checkin.pace_status = result.get("pace_status", "on_track")
        checkin.next_checkin_interval_days = result.get("next_checkin_days", 14)

        # Count specific action types
        actions = result.get("actions_taken", [])
        checkin.tasks_created = sum(
            1
            for a in actions
            if a.get("tool") in ("create_tasks", "generate_extension_tasks")
        )
        checkin.milestones_adjusted = sum(
            1
            for a in actions
            if a.get("tool")
            in (
                "update_milestone",
                "create_new_goal",
                "add_milestone",
                "remove_milestone",
                "reorder_milestone",
                "shift_milestone_dates",
            )
        )

        checkin.status = "completed"
        checkin.completed_at = timezone.now()
        checkin.save()

        # Update dream — use _update_dream_after_checkin for consistency
        _update_dream_after_checkin(dream, checkin, result)

        # Send notification with coaching message
        if result.get("coaching_message"):
            try:
                NotificationService.create(
                    user=user,
                    notification_type="check_in",
                    title="Your bi-weekly check-in is ready!",
                    body=result["coaching_message"][:500],
                    scheduled_for=timezone.now(),
                    data={
                        "screen": "dream",
                        "dream_id": str(dream.id),
                        "action": "checkin_complete",
                        "checkin_id": str(checkin.id),
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to create check-in notification: {e}")

        logger.info(
            f"run_single_checkin_task: DONE checkin={checkin_id} dream={dream.id}"
        )
        return {
            "status": "completed",
            "coaching_message": result.get("coaching_message", ""),
        }

    except PlanCheckIn.DoesNotExist:
        logger.error(f"PlanCheckIn {checkin_id} not found")
        return {"status": "failed", "error": "checkin_not_found"}

    except OpenAIError as e:
        logger.error(
            f"run_single_checkin_task: OpenAI error for checkin {checkin_id}: {e}"
        )
        try:
            checkin = PlanCheckIn.objects.get(id=checkin_id)
            checkin.status = "failed"
            checkin.error_message = str(e)
            checkin.save(update_fields=["status", "error_message"])
        except Exception:
            pass
        raise self.retry(exc=e, countdown=60)

    except Exception as e:
        logger.error(
            f"run_single_checkin_task: error for checkin {checkin_id}: {e}",
            exc_info=True,
        )
        try:
            checkin = PlanCheckIn.objects.get(id=checkin_id)
            checkin.status = "failed"
            checkin.error_message = str(e)
            checkin.save(update_fields=["status", "error_message"])
        except Exception:
            pass
        return {"status": "failed", "error": str(e)}


@shared_task(bind=True, max_retries=1, soft_time_limit=300, time_limit=360)
def generate_tasks_for_milestone_task(self, dream_id, user_id, milestone_order):
    """
    On-demand task generation for a specific milestone.
    Called when user views a future milestone and wants tasks generated.
    """
    from core.ai_validators import AIValidationError, validate_task_patches

    try:
        dream = Dream.objects.get(id=dream_id)
        User.objects.get(id=user_id)  # Validate user exists

        if not dream.plan_skeleton:
            return {"status": "failed", "error": "no_skeleton"}

        milestone = DreamMilestone.objects.filter(
            dream=dream, order=milestone_order
        ).first()
        if not milestone:
            return {"status": "failed", "error": "milestone_not_found"}

        if milestone.has_tasks:
            return {"status": "skipped", "reason": "already_has_tasks"}

        ai_service = OpenAIService()

        category = ""
        if dream.ai_analysis and isinstance(dream.ai_analysis, dict):
            category = dream.ai_analysis.get("category", "")

        user_context = {
            "timezone": dream.user.timezone,
            "work_schedule": dream.user.work_schedule or {},
            "category": category,
            "language": dream.language or "",
            "persona": dream.user.persona or {},
        }

        _target = str(dream.target_date) if dream.target_date else None

        raw_patches = ai_service.generate_tasks_for_months(
            dream.title,
            dream.description,
            dream.plan_skeleton,
            user_context,
            milestone_order,
            milestone_order,
            target_date=_target,
        )

        patches = validate_task_patches(raw_patches)

        plan_start = dream.created_at or timezone.now()
        tasks_created_count = 0

        for patch in patches:
            goal = Goal.objects.filter(
                milestone=milestone, order=patch.goal_order
            ).first()
            if not goal:
                continue

            for task_data in patch.tasks:
                scheduled = None
                if task_data.day_number:
                    scheduled = plan_start + timedelta(days=task_data.day_number - 1)

                Task.objects.create(
                    goal=goal,
                    title=task_data.title,
                    description=task_data.description,
                    order=task_data.order,
                    duration_mins=task_data.duration_mins,
                    scheduled_date=scheduled,
                    expected_date=_parse_date(task_data.expected_date),
                    deadline_date=_parse_date(task_data.deadline_date),
                )
                tasks_created_count += 1

        milestone.has_tasks = True
        milestone.save(update_fields=["has_tasks"])

        # Update tasks_generated_through_month if this is further out
        if milestone_order > dream.tasks_generated_through_month:
            dream.tasks_generated_through_month = milestone_order
            dream.save(update_fields=["tasks_generated_through_month"])

        logger.info(
            f"generate_tasks_for_milestone_task: DONE dream={dream_id} milestone={milestone_order} tasks={tasks_created_count}"
        )
        return {"status": "completed", "tasks": tasks_created_count}

    except Dream.DoesNotExist:
        return {"status": "failed", "error": "dream_not_found"}

    except AIValidationError as e:
        logger.error(
            f"generate_tasks_for_milestone_task: validation error: {e.message}"
        )
        return {"status": "failed", "error": str(e)}

    except OpenAIError as e:
        logger.error(f"generate_tasks_for_milestone_task: OpenAI error: {e}")
        raise self.retry(exc=e, countdown=30)

    except Exception as e:
        logger.error(f"generate_tasks_for_milestone_task: error: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}


# ===================================================================
# Interactive check-in system
# ===================================================================


def _calculate_pace(dream):
    """
    Calculate pace status for a dream based on expected vs actual progress.
    Returns dict with pace_status, expected_pct, actual_pct, days_behind, next_checkin_days.
    """
    from datetime import date as date_type

    if not dream.target_date:
        return {
            "pace_status": "on_track",
            "expected_pct": 0,
            "actual_pct": round(dream.progress_percentage, 1),
            "days_behind": 0,
            "next_checkin_days": 14,
        }

    today = date_type.today()
    start = dream.created_at.date() if dream.created_at else today
    target = (
        dream.target_date.date()
        if hasattr(dream.target_date, "date")
        else dream.target_date
    )

    total_days = max(1, (target - start).days)
    elapsed_days = max(0, (today - start).days)
    expected_pct = min(100, round((elapsed_days / total_days) * 100, 1))
    actual_pct = round(dream.progress_percentage, 1)

    diff = actual_pct - expected_pct

    if diff >= 15:
        pace_status = "significantly_ahead"
        next_checkin_days = 21
    elif diff >= 5:
        pace_status = "ahead"
        next_checkin_days = 21
    elif diff >= -10:
        pace_status = "on_track"
        next_checkin_days = 14
    elif diff >= -25:
        pace_status = "behind"
        next_checkin_days = 7
    else:
        pace_status = "significantly_behind"
        next_checkin_days = 7

    # Calculate days behind
    if actual_pct > 0 and expected_pct > actual_pct:
        pct_per_day = expected_pct / max(1, elapsed_days)
        days_behind = round((expected_pct - actual_pct) / max(0.01, pct_per_day))
    else:
        days_behind = 0

    return {
        "pace_status": pace_status,
        "expected_pct": expected_pct,
        "actual_pct": actual_pct,
        "days_behind": max(0, days_behind),
        "next_checkin_days": next_checkin_days,
    }


def _update_dream_after_checkin(dream, checkin, result):
    """Update dream fields after a check-in completes."""
    interval = result.get("next_checkin_days", 14)
    # Never regress months coverage — AI might return a lower value
    ai_months = result.get(
        "months_generated_through", dream.tasks_generated_through_month
    )
    dream.tasks_generated_through_month = max(
        dream.tasks_generated_through_month, ai_months
    )
    dream.last_checkin_at = timezone.now()
    dream.next_checkin_at = timezone.now() + timedelta(days=interval)
    dream.checkin_count = (dream.checkin_count or 0) + 1
    dream.checkin_interval_days = interval
    dream.save(
        update_fields=[
            "tasks_generated_through_month",
            "last_checkin_at",
            "next_checkin_at",
            "checkin_count",
            "checkin_interval_days",
        ]
    )


@shared_task(bind=True, max_retries=1, soft_time_limit=120, time_limit=150)
def generate_checkin_questionnaire_task(self, checkin_id):
    """
    Phase 1 of interactive check-in: Generate personalized questionnaire.
    On success, sends notification to user and waits for response.
    On failure, falls back to autonomous check-in.
    """
    from core.ai_validators import AIValidationError, validate_checkin_questionnaire

    try:
        checkin = PlanCheckIn.objects.select_related("dream", "dream__user").get(
            id=checkin_id
        )
        dream = checkin.dream
        user = dream.user

        checkin.status = "questionnaire_generating"
        checkin.started_at = timezone.now()
        checkin.progress_at_checkin = dream.progress_percentage
        checkin.save(update_fields=["status", "started_at", "progress_at_checkin"])

        # Snapshot progress data
        since = dream.last_checkin_at or (timezone.now() - timedelta(days=14))
        checkin.tasks_completed_since_last = Task.objects.filter(
            goal__dream=dream, status="completed", completed_at__gte=since
        ).count()
        checkin.tasks_overdue_at_checkin = Task.objects.filter(
            goal__dream=dream, status="pending", deadline_date__lt=timezone.now().date()
        ).count()
        checkin.save(
            update_fields=["tasks_completed_since_last", "tasks_overdue_at_checkin"]
        )

        # Calculate pace
        pace_analysis = _calculate_pace(dream)
        checkin.pace_status = pace_analysis["pace_status"]

        # Generate questionnaire via AI
        ai_service = OpenAIService()
        raw_result = ai_service.generate_checkin_questionnaire(
            dream, user, pace_analysis
        )

        # Validate
        validated = validate_checkin_questionnaire(raw_result)

        # Save questionnaire
        checkin.questionnaire = [q.model_dump() for q in validated.questions]
        checkin.status = "awaiting_user"
        checkin.questionnaire_expires_at = timezone.now() + timedelta(hours=48)
        checkin.save(
            update_fields=[
                "questionnaire",
                "status",
                "pace_status",
                "questionnaire_expires_at",
            ]
        )

        # Send notification
        opening = validated.opening_message or "Time for your check-in!"
        try:
            NotificationService.create(
                user=user,
                notification_type="check_in",
                title="Check-in time!",
                body=opening[:500],
                scheduled_for=timezone.now(),
                data={
                    "screen": "checkin",
                    "checkin_id": str(checkin.id),
                    "dream_id": str(dream.id),
                    "action": "checkin_questionnaire",
                },
            )
        except Exception as e:
            logger.warning(f"Failed to create check-in notification: {e}")

        logger.info(
            f"generate_checkin_questionnaire_task: DONE checkin={checkin_id} questions={len(validated.questions)}"
        )
        return {"status": "awaiting_user", "questions": len(validated.questions)}

    except PlanCheckIn.DoesNotExist:
        logger.error(f"PlanCheckIn {checkin_id} not found")
        return {"status": "failed", "error": "checkin_not_found"}

    except (AIValidationError, OpenAIError) as e:
        logger.warning(
            f"Questionnaire generation failed for checkin {checkin_id}, falling back to autonomous: {e}"
        )
        try:
            checkin = PlanCheckIn.objects.get(id=checkin_id)
            checkin.status = "ai_processing"
            checkin.save(update_fields=["status"])
            # Fall back to autonomous check-in
            run_single_checkin_task.apply_async(args=[str(checkin_id)], queue="dreams")
        except Exception:
            pass
        return {"status": "fallback_autonomous"}

    except Exception as e:
        logger.error(f"generate_checkin_questionnaire_task error: {e}", exc_info=True)
        try:
            checkin = PlanCheckIn.objects.get(id=checkin_id)
            checkin.status = "failed"
            checkin.error_message = str(e)
            checkin.save(update_fields=["status", "error_message"])
        except Exception:
            pass
        return {"status": "failed", "error": str(e)}


@shared_task(bind=True, max_retries=1, soft_time_limit=360, time_limit=420)
def process_checkin_responses_task(self, checkin_id):
    """
    Phase 2 of interactive check-in: Process user responses and adapt the plan.
    Called after user submits questionnaire answers OR after expiry (empty responses).
    """
    try:
        checkin = PlanCheckIn.objects.select_related("dream", "dream__user").get(
            id=checkin_id
        )
        dream = checkin.dream
        user = dream.user

        if checkin.status != "ai_processing":
            logger.warning(
                f"process_checkin_responses_task: checkin {checkin_id} not in ai_processing state (is {checkin.status})"
            )
            return {"status": "skipped", "reason": "wrong_state"}

        ai_service = OpenAIService()
        result = ai_service.run_interactive_checkin_agent(
            dream,
            user,
            checkin.questionnaire or [],
            checkin.user_responses or {},
        )

        # Update check-in record
        checkin.coaching_message = result.get("coaching_message", "")
        checkin.adjustment_summary = result.get("adjustment_summary", "")
        checkin.ai_actions = result.get("actions_taken", [])
        checkin.months_generated_through = max(
            dream.tasks_generated_through_month,
            result.get("months_generated_through", dream.tasks_generated_through_month),
        )
        checkin.pace_status = result.get(
            "pace_status", checkin.pace_status or "on_track"
        )
        checkin.next_checkin_interval_days = result.get("next_checkin_days", 14)

        # Count action types
        actions = result.get("actions_taken", [])
        checkin.tasks_created = sum(
            1
            for a in actions
            if a.get("tool") in ("create_tasks", "generate_extension_tasks")
        )
        checkin.milestones_adjusted = sum(
            1
            for a in actions
            if a.get("tool")
            in (
                "update_milestone",
                "create_new_goal",
                "add_milestone",
                "remove_milestone",
                "reorder_milestone",
                "shift_milestone_dates",
            )
        )

        checkin.status = "completed"
        checkin.completed_at = timezone.now()
        checkin.save()

        # Update dream
        _update_dream_after_checkin(dream, checkin, result)

        # Send coaching notification
        if result.get("coaching_message"):
            try:
                NotificationService.create(
                    user=user,
                    notification_type="check_in",
                    title="Your check-in results are ready!",
                    body=result["coaching_message"][:500],
                    scheduled_for=timezone.now(),
                    data={
                        "screen": "checkin",
                        "checkin_id": str(checkin.id),
                        "dream_id": str(dream.id),
                        "action": "checkin_complete",
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to create coaching notification: {e}")

        logger.info(
            f"process_checkin_responses_task: DONE checkin={checkin_id} dream={dream.id}"
        )
        return {"status": "completed", "pace_status": result.get("pace_status")}

    except PlanCheckIn.DoesNotExist:
        logger.error(f"PlanCheckIn {checkin_id} not found")
        return {"status": "failed", "error": "checkin_not_found"}

    except OpenAIError as e:
        logger.error(
            f"process_checkin_responses_task: OpenAI error for checkin {checkin_id}: {e}"
        )
        try:
            checkin = PlanCheckIn.objects.get(id=checkin_id)
            checkin.status = "failed"
            checkin.error_message = str(e)
            checkin.save(update_fields=["status", "error_message"])
        except Exception:
            pass
        raise self.retry(exc=e, countdown=60)

    except Exception as e:
        logger.error(
            f"process_checkin_responses_task: error for checkin {checkin_id}: {e}",
            exc_info=True,
        )
        try:
            checkin = PlanCheckIn.objects.get(id=checkin_id)
            checkin.status = "failed"
            checkin.error_message = str(e)
            checkin.save(update_fields=["status", "error_message"])
        except Exception:
            pass
        return {"status": "failed", "error": str(e)}


@shared_task(bind=True, max_retries=0)
def expire_stale_checkins(self):
    """
    Expire unanswered interactive check-ins (48h passed).
    Runs them as autonomous check-ins with empty responses.
    """
    try:
        stale = PlanCheckIn.objects.filter(
            status="awaiting_user",
            questionnaire_expires_at__lte=timezone.now(),
        )

        count = 0
        for checkin in stale:
            checkin.status = "ai_processing"
            checkin.user_responses = {}
            checkin.save(update_fields=["status", "user_responses"])
            process_checkin_responses_task.apply_async(
                args=[str(checkin.id)], queue="dreams"
            )
            count += 1

        if count:
            logger.info(f"expire_stale_checkins: expired {count} check-ins")
        return {"expired": count}

    except Exception as e:
        logger.error(f"expire_stale_checkins error: {e}", exc_info=True)
        return {"expired": 0, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════
# Recurring Task Generation
# ══════════════════════════════════════════════════════════════════════


@shared_task(bind=True, max_retries=1, soft_time_limit=300, time_limit=360)
def generate_recurring_tasks(self):
    """
    Daily job: generate upcoming recurring task instances for the next 7 days.

    For each "template" recurring task (parent_task is NULL, recurrence_type != 'none'),
    checks if instances already exist for each upcoming date, and creates them if missing.
    """
    from datetime import date as date_type

    try:
        today = timezone.now().date()
        horizon = today + timedelta(days=7)

        # Find all recurring template tasks (not children of another recurring task)
        templates = Task.objects.filter(
            recurrence_type__in=["daily", "weekly", "biweekly", "monthly", "custom"],
            parent_task__isnull=True,
        ).select_related("goal", "goal__dream")

        created_count = 0

        for template in templates:
            # Skip if the end date has passed
            if template.recurrence_end_date and template.recurrence_end_date < today:
                continue

            # Skip if the dream is not active
            if template.goal.dream.status != "active":
                continue

            # Generate dates for the next 7 days
            dates = _generate_recurrence_dates(template, today, horizon)

            for target_date in dates:
                # Skip dates beyond end date
                if template.recurrence_end_date and target_date > template.recurrence_end_date:
                    continue

                # Check if an instance already exists for this date
                existing = Task.objects.filter(
                    parent_task=template,
                    expected_date=target_date,
                ).exists()

                if not existing:
                    max_order = template.goal.tasks.count()
                    Task.objects.create(
                        goal=template.goal,
                        title=template.title,
                        description=template.description,
                        order=max_order + 1,
                        scheduled_date=timezone.make_aware(
                            timezone.datetime.combine(
                                target_date, timezone.datetime.min.time()
                            )
                        ),
                        scheduled_time=template.scheduled_time,
                        duration_mins=template.duration_mins,
                        expected_date=target_date,
                        recurrence_type=template.recurrence_type,
                        recurrence_days=template.recurrence_days,
                        recurrence_end_date=template.recurrence_end_date,
                        parent_task=template,
                    )
                    created_count += 1

        logger.info(
            "generate_recurring_tasks: created %d instances from %d templates",
            created_count,
            templates.count(),
        )
        return {"created": created_count, "templates": templates.count()}

    except Exception as e:
        logger.error("generate_recurring_tasks error: %s", e, exc_info=True)
        raise self.retry(exc=e, countdown=60)


def _generate_recurrence_dates(template, start_date, end_date):
    """Generate all recurrence dates between start_date and end_date for a template."""
    from datetime import date as date_type

    dates = []
    current = start_date

    if template.recurrence_type == "daily":
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=1)

    elif template.recurrence_type == "weekly":
        # Schedule on the same weekday as the template's expected_date or scheduled_date
        base_weekday = _get_template_weekday(template)
        while current <= end_date:
            if current.weekday() == base_weekday:
                dates.append(current)
            current += timedelta(days=1)

    elif template.recurrence_type == "biweekly":
        base_date = _get_template_base_date(template)
        base_weekday = base_date.weekday() if base_date else 0
        while current <= end_date:
            if current.weekday() == base_weekday:
                # Check it's on a biweekly cadence from the base date
                if base_date:
                    delta_days = (current - base_date).days
                    if delta_days >= 0 and delta_days % 14 == 0:
                        dates.append(current)
                else:
                    dates.append(current)
            current += timedelta(days=1)

    elif template.recurrence_type == "monthly":
        base_date = _get_template_base_date(template)
        target_day = base_date.day if base_date else 1
        target_day = min(target_day, 28)
        current_month = start_date.month
        current_year = start_date.year
        for _ in range(2):  # Check this month and next
            try:
                d = date_type(current_year, current_month, target_day)
                if start_date <= d <= end_date:
                    dates.append(d)
            except ValueError:
                pass
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1

    elif template.recurrence_type == "custom" and template.recurrence_days:
        day_map = {
            "mon": 0, "tue": 1, "wed": 2, "thu": 3,
            "fri": 4, "sat": 5, "sun": 6,
        }
        target_days = set(
            day_map[d] for d in template.recurrence_days if d in day_map
        )
        while current <= end_date:
            if current.weekday() in target_days:
                dates.append(current)
            current += timedelta(days=1)

    return dates


def _get_template_weekday(template):
    """Get the weekday for a template task."""
    if template.expected_date:
        return template.expected_date.weekday()
    if template.scheduled_date:
        return template.scheduled_date.date().weekday()
    return 0  # Monday default


def _get_template_base_date(template):
    """Get the base date for a template task."""
    from datetime import date as date_type

    if template.expected_date:
        return template.expected_date
    if template.scheduled_date:
        return template.scheduled_date.date()
    return date_type.today()


@shared_task(bind=True, max_retries=1, soft_time_limit=120, time_limit=150)
def suggest_recurrence_patterns(self, dream_id, user_id):
    """
    AI suggests recurrence patterns when a user creates a goal with a timeline.

    Returns suggested recurring tasks based on the dream's category and timeline.
    """
    try:
        dream = Dream.objects.get(id=dream_id, user_id=user_id)
        ai = OpenAIService()

        # Calculate timeline in months
        timeline_months = 6  # default
        if dream.target_date:
            delta = dream.target_date - timezone.now()
            timeline_months = max(1, delta.days // 30)

        prompt = (
            f"The user has a goal: \"{dream.title}\" in category \"{dream.category}\" "
            f"with a timeline of {timeline_months} months.\n\n"
            f"Description: {dream.description}\n\n"
            f"Suggest 3-5 recurring tasks that would help achieve this goal. "
            f"For each task, specify:\n"
            f"- title: short task name\n"
            f"- recurrence_type: one of daily, weekly, biweekly, monthly\n"
            f"- recurrence_days: (only for custom) array of day abbreviations like [\"mon\",\"wed\",\"fri\"]\n"
            f"- duration_mins: estimated minutes per session\n"
            f"- reasoning: why this recurrence helps\n\n"
            f"Return JSON array only."
        )

        response = ai.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a productivity coach. Return only valid JSON array.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=800,
            response_format={"type": "json_object"},
        )

        import json as json_mod

        raw = response.choices[0].message.content
        result = json_mod.loads(raw)
        suggestions = result.get("suggestions") or result.get("tasks") or result
        if not isinstance(suggestions, list):
            suggestions = [suggestions] if isinstance(suggestions, dict) else []

        # Store in Redis for frontend polling
        from django.core.cache import cache

        cache.set(
            f"recurrence_suggestions:{dream_id}",
            json_mod.dumps(suggestions),
            timeout=3600,
        )

        logger.info(
            "suggest_recurrence_patterns: %d suggestions for dream %s",
            len(suggestions),
            dream_id,
        )
        return {"dream_id": str(dream_id), "suggestions": suggestions}

    except Dream.DoesNotExist:
        logger.warning("suggest_recurrence_patterns: dream %s not found", dream_id)
        return {"error": "Dream not found"}
    except Exception as e:
        logger.error("suggest_recurrence_patterns error: %s", e, exc_info=True)
        raise self.retry(exc=e, countdown=30)
