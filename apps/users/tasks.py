"""
Celery tasks for the Users app.

Handles async operations like sending email change verification emails
and account data export.
"""

import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(name="apps.users.tasks.send_email_change_verification")
def send_email_change_verification(user_id: int, new_email: str, token: str):
    """
    Send a verification email when a user requests an email change.
    """
    from core.email import send_templated_email

    from .models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("User %s not found for email change verification", user_id)
        return

    verification_url = f"{settings.FRONTEND_URL}/#/verify-email/{token}"

    send_templated_email(
        template_name="users/email_change",
        subject="Stepora — Verify your new email address",
        to=[new_email],
        context={
            "user_name": user.display_name or "there",
            "new_email": new_email,
            "verification_url": verification_url,
            "action_url": verification_url,
        },
        from_name="Stepora Account",
    )

    logger.info("Email change verification sent to %s for user %s", new_email, user_id)


@shared_task(name="apps.users.tasks.export_user_data")
def export_user_data(user_id: int):
    """
    Export all user data as JSON and email a download link.
    """
    import json

    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    from core.email import send_templated_email

    from .models import User
    from .serializers import UserSerializer

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("User %s not found for data export", user_id)
        return

    user_data = UserSerializer(user).data

    # Include related data
    export = {
        "user": user_data,
        "dreams": list(user.dreams.values()),
        "conversations": list(user.conversations.values()),
        "notifications": list(
            user.notifications.values("id", "title", "body", "created_at", "is_read")
        ),
    }

    json_content = json.dumps(export, default=str, indent=2)
    file_path = f"exports/user_{user_id}_data.json"
    default_storage.save(file_path, ContentFile(json_content.encode()))

    download_url = f"{settings.FRONTEND_URL}/api/media/{file_path}"

    send_templated_email(
        template_name="users/data_export",
        subject="Stepora — Your data export is ready",
        to=[user.email],
        context={
            "user_name": user.display_name or "there",
            "download_url": download_url,
            "action_url": download_url,
        },
        from_name="Stepora Account",
    )

    logger.info("Data export completed and emailed for user %s", user_id)


@shared_task(name="apps.users.tasks.hard_delete_expired_accounts")
def hard_delete_expired_accounts():
    """
    Hard-delete accounts that have been soft-deleted for 30+ days.

    GDPR compliance: ensures full data removal after the grace period.
    Users who soft-deleted their account have 30 days to recover it.
    After that, all data is permanently removed via CASCADE delete.
    """
    from datetime import timedelta as td

    from django.utils import timezone

    from .models import User

    cutoff = timezone.now() - td(days=30)
    expired_users = User.objects.filter(
        is_active=False,
        updated_at__lt=cutoff,
    )

    count = 0
    failed_ids = []
    for user in expired_users:
        try:
            user_id = user.id
            user.delete()  # CASCADE deletes all related data
            count += 1
            logger.info("Hard-deleted expired account %s", user_id)
        except Exception:
            logger.exception("Failed to hard-delete user %s", user.id)
            failed_ids.append(str(user.id))

    logger.info("Hard-deleted %d expired accounts", count)
    if failed_ids:
        logger.error(
            "Failed to hard-delete %d users: %s", len(failed_ids), ", ".join(failed_ids)
        )
    return {"deleted": count, "failed": failed_ids}


@shared_task(name="apps.users.tasks.generate_weekly_reports")
def generate_weekly_reports():
    """
    Generate weekly progress reports for all premium/pro users.

    Runs every Sunday evening via Celery Beat. Creates a notification
    for each user with a link to view their weekly report.
    """
    from datetime import datetime as dt
    from datetime import timedelta as td

    from django.db.models import Count, Sum
    from django.utils import timezone

    from apps.dreams.models import Dream, DreamProgressSnapshot, FocusSession, Goal
    from apps.notifications.models import Notification
    from core.ai_usage import AIUsageTracker
    from core.exceptions import OpenAIError
    from integrations.openai_service import OpenAIService

    from .models import DailyActivity, User

    now = timezone.now()
    today = now.date()
    week_start = today - td(days=7)

    # Only generate for premium/pro users who were active this week
    eligible_users = User.objects.filter(
        is_active=True,
        subscription__in=["premium", "pro"],
        last_activity__gte=now - td(days=14),
    )

    ai_service = OpenAIService()
    tracker = AIUsageTracker()
    generated = 0

    for user in eligible_users:
        try:
            # Check AI quota
            allowed, _ = tracker.check_quota(user, "ai_background")
            if not allowed:
                logger.info(
                    "Skipping weekly report for user %s (quota exceeded)", user.id
                )
                continue

            # Gather current week stats
            activities = DailyActivity.objects.filter(
                user=user,
                date__gte=week_start,
                date__lt=today,
            )
            agg = activities.aggregate(
                total_tasks=Sum("tasks_completed"),
                total_xp=Sum("xp_earned"),
                total_minutes=Sum("minutes_active"),
                active_days=Count("id"),
            )

            range_start = timezone.make_aware(
                dt.combine(week_start, dt.min.time()),
                timezone.get_current_timezone(),
            )
            range_end = timezone.make_aware(
                dt.combine(today, dt.min.time()),
                timezone.get_current_timezone(),
            )

            focus_agg = FocusSession.objects.filter(
                user=user,
                completed=True,
                started_at__gte=range_start,
                started_at__lt=range_end,
            ).aggregate(total_focus=Sum("actual_minutes"))

            dreams_progressed = (
                DreamProgressSnapshot.objects.filter(
                    dream__user=user,
                    date__gte=week_start,
                    date__lt=today,
                )
                .values("dream")
                .distinct()
                .count()
            )

            dreams_completed = Dream.objects.filter(
                user=user,
                status="completed",
                completed_at__gte=range_start,
                completed_at__lt=range_end,
            ).count()

            goals_completed = Goal.objects.filter(
                dream__user=user,
                status="completed",
                completed_at__gte=range_start,
                completed_at__lt=range_end,
            ).count()

            current_stats = {
                "tasks_completed": agg["total_tasks"] or 0,
                "focus_minutes": (focus_agg["total_focus"] or 0)
                + (agg["total_minutes"] or 0),
                "streak_days": user.streak_days or 0,
                "xp_earned": agg["total_xp"] or 0,
                "dreams_progressed": dreams_progressed,
                "dreams_completed": dreams_completed,
                "goals_completed": goals_completed,
                "active_days": agg["active_days"] or 0,
            }

            # Generate AI report
            ai_report = ai_service.generate_weekly_report(
                weekly_stats=current_stats,
            )
            tracker.increment(user, "ai_background")

            # Create notification
            score = ai_report.get("score", 0)
            summary = ai_report.get("summary", "Your weekly report is ready!")
            Notification.objects.create(
                user=user,
                notification_type="system",
                title="Your Weekly Progress Report is Ready!",
                body=f"Score: {score}/100 - {summary}",
                scheduled_for=now,
                data={
                    "screen": "weekly-report",
                    "score": score,
                },
            )

            generated += 1
            logger.info(
                "Generated weekly report for user %s (score: %d)",
                user.id,
                score,
            )

        except OpenAIError as e:
            logger.error(
                "Failed to generate weekly report for user %s: %s",
                user.id,
                str(e),
            )
        except Exception:
            logger.exception(
                "Unexpected error generating weekly report for user %s",
                user.id,
            )

    logger.info("Generated %d weekly reports", generated)
    return generated


@shared_task(name="apps.users.tasks.send_accountability_checkins")
def send_accountability_checkins():
    """
    Generate and send AI accountability check-in notifications for
    users who have not been active in 2+ days.

    Runs daily at 10 AM via Celery Beat. For each eligible user,
    generates a personalized check-in message using the AI service
    and creates a push notification.
    """
    from datetime import timedelta as td

    from django.utils import timezone

    from apps.dreams.models import Dream, Task
    from apps.notifications.models import Notification
    from core.ai_usage import AIUsageTracker
    from core.exceptions import OpenAIError
    from core.sanitizers import sanitize_text
    from integrations.openai_service import OpenAIService

    from .models import User

    now = timezone.now()
    threshold = now - td(days=2)

    # Find users who:
    # - Have active dreams
    # - Haven't been active in 2+ days
    # - Haven't received an accountability check-in in the last 24 hours
    # - Are active accounts
    eligible_users = (
        User.objects.filter(
            is_active=True,
            dreams__status="active",
            last_activity__lt=threshold,
        )
        .exclude(
            notifications__notification_type="check_in",
            notifications__created_at__gte=now - td(days=1),
        )
        .distinct()
    )

    # Respect notification preferences
    eligible_users = [
        u
        for u in eligible_users
        if (u.notification_prefs or {}).get("accountability_checkins", True)
    ]

    ai_service = OpenAIService()
    tracker = AIUsageTracker()
    created = 0

    for user in eligible_users:
        try:
            # Check AI background quota
            allowed, _ = tracker.check_quota(user, "ai_background")
            if not allowed:
                logger.info(
                    "Skipping accountability check-in for user %s (quota exceeded)",
                    user.id,
                )
                continue

            # Gather context
            days_since = (now - user.last_activity).days if user.last_activity else 0

            active_dreams = Dream.objects.filter(
                user=user,
                status="active",
            ).values("id", "title", "progress_percentage", "category")

            dream_progress = [
                {
                    "title": d["title"],
                    "progress": round(d["progress_percentage"], 1),
                    "category": d["category"] or "personal",
                }
                for d in active_dreams
            ]

            pending_tasks_qs = (
                Task.objects.filter(
                    goal__dream__user=user,
                    goal__dream__status="active",
                    status="pending",
                )
                .select_related("goal__dream")
                .order_by(
                    "scheduled_date",
                    "order",
                )[:10]
            )

            pending_tasks = [
                {
                    "title": t.title,
                    "dream_title": (
                        t.goal.dream.title if t.goal and t.goal.dream else ""
                    ),
                    "due_date": str(t.deadline_date) if t.deadline_date else "",
                }
                for t in pending_tasks_qs
            ]

            streak_data = {
                "current_streak": user.streak_days or 0,
                "best_streak": user.streak_days or 0,
            }

            display_name = user.display_name or user.email.split("@")[0]

            # Generate check-in
            checkin = ai_service.generate_checkin(
                dream_progress=dream_progress,
                days_since_activity=days_since,
                pending_tasks=pending_tasks,
                streak_data=streak_data,
                display_name=display_name,
            )

            # Track AI usage
            tracker.increment(user, "ai_background")

            # Sanitize message
            message = sanitize_text(checkin.get("message", ""))[:500]

            # Create notification
            Notification.objects.create(
                user=user,
                notification_type="check_in",
                title="Accountability Check-in",
                body=message,
                scheduled_for=now,
                data={
                    "screen": "Home",
                    "action": "show_checkin",
                    "prompt_type": checkin.get("prompt_type", "gentle_nudge"),
                    "suggested_questions": checkin.get("suggested_questions", []),
                    "quick_actions": checkin.get("quick_actions", []),
                },
            )

            created += 1
            logger.info(
                "Sent accountability check-in to user %s (type: %s, %d days inactive)",
                user.id,
                checkin.get("prompt_type"),
                days_since,
            )

        except OpenAIError as e:
            logger.error(
                "Failed to generate accountability check-in for user %s: %s",
                user.id,
                str(e),
            )
        except Exception:
            logger.exception(
                "Unexpected error generating accountability check-in for user %s",
                user.id,
            )

    logger.info("Sent %d accountability check-in notifications", created)
    return created
