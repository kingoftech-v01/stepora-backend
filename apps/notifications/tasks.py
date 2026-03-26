"""
Celery tasks for notifications app.

Includes:
- Processing pending notifications via FCM
- Sending reminder notifications
- Daily motivational notifications
- Weekly progress digest (email + push)
- Inactive user rescue notifications
- Cleanup of old notifications
- Call expiry and due-task checks
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db.models import Prefetch, Sum
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.dreams.models import Dream, Task
from apps.users.models import User
from core.ai_usage import AIUsageTracker
from core.decorators import celery_distributed_lock
from core.exceptions import OpenAIError
from core.sanitizers import sanitize_text
from integrations.openai_service import OpenAIService

from .models import Notification
from .services import NotificationService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Weekly digest helpers
# ---------------------------------------------------------------------------

MOTIVATIONAL_MESSAGES = [
    "Every step counts. You're building something amazing!",
    "Progress, not perfection. Keep going!",
    "Small daily improvements lead to stunning results.",
    "You're closer to your dreams than you think!",
    "Consistency is the key to unlocking your potential.",
    "Believe in yourself -- you've already come this far!",
    "Dream big, act small, start now.",
    "Your future self will thank you for today's effort.",
]


def _pick_motivational_message(tasks_completed, streak_days):
    """Pick a motivational message based on weekly performance."""
    if tasks_completed == 0 and streak_days == 0:
        return "A new week is a fresh start. Set one small goal today!"
    if tasks_completed >= 20:
        return "Incredible week! You're on fire -- keep that momentum going!"
    if streak_days >= 7:
        return f"Amazing {streak_days}-day streak! Consistency is your superpower."
    # Deterministic but varied selection
    idx = (tasks_completed + streak_days) % len(MOTIVATIONAL_MESSAGES)
    return MOTIVATIONAL_MESSAGES[idx]


def _send_digest_push(user, title, body, data):
    """Send a push notification to all of the user's active FCM devices."""
    from .fcm_service import FCMService
    from .models import UserDevice

    tokens = list(
        UserDevice.objects.filter(user=user, is_active=True).values_list(
            "fcm_token", flat=True
        )
    )
    if not tokens:
        return

    try:
        fcm = FCMService()
        result = fcm.send_multicast(tokens, title, body, data=data)

        # Deactivate invalid tokens
        if result.invalid_tokens:
            UserDevice.objects.filter(
                fcm_token__in=result.invalid_tokens,
            ).update(is_active=False)
            logger.info(
                "Deactivated %d invalid FCM tokens for user %s.",
                len(result.invalid_tokens),
                user.id,
            )
    except Exception as exc:
        logger.error(
            "FCM push failed for weekly digest (user %s): %s",
            user.id,
            exc,
            exc_info=True,
        )


def _send_digest_email(user, subject, context):
    """Render the weekly digest HTML email and dispatch via the core email task."""
    from core.tasks import send_rendered_email

    try:
        html_body = render_to_string("emails/weekly_digest.html", context)
    except Exception as exc:
        logger.error(
            "Failed to render weekly digest email template: %s", exc, exc_info=True
        )
        raise

    # Plain-text fallback
    plain = (
        f"Hi {context['display_name']},\n\n"
        f"Here's your weekly progress report "
        f"({context['week_start']} - {context['week_end']}):\n\n"
        f"- Tasks completed: {context['tasks_completed']}\n"
        f"- XP earned: {context['xp_earned']}\n"
        f"- Streak: {context['streak_days']} days\n"
        f"- Active dreams: {context['dreams_count']}\n\n"
        f"{context['motivational_msg']}\n\n"
        f"Keep going!\nThe Stepora Team"
    )

    base_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@stepora.net")
    from_email = f"Stepora Notifications <{base_email}>"

    send_rendered_email.delay(
        subject=subject,
        body=plain,
        from_email=from_email,
        to=[user.email],
        alternatives=[(html_body, "text/html")],
    )


@shared_task(bind=True, max_retries=3)
@celery_distributed_lock(timeout=120)
def process_pending_notifications(self):
    """
    Process and send pending notifications.
    Runs every minute to check for notifications that need to be sent.
    """
    try:
        now = timezone.now()

        # Get all pending notifications that should be sent now
        pending = Notification.objects.filter(
            status="pending", scheduled_for__lte=now
        ).select_related("user")

        from .services import NotificationDeliveryService

        service = NotificationDeliveryService()

        sent_count = 0
        failed_count = 0

        for notification in pending:
            try:
                if not notification.should_send():
                    # Reschedule for later (DND)
                    notification.scheduled_for = now + timedelta(hours=1)
                    notification.save(update_fields=["scheduled_for"])
                    continue

                success = service.deliver(notification)
                if success:
                    notification.mark_sent()
                    sent_count += 1
                else:
                    notification.mark_failed("All delivery channels failed")
                    failed_count += 1

            except Exception as e:
                logger.error(
                    f"Error processing notification {notification.id}: {str(e)}"
                )
                notification.mark_failed(str(e))
                failed_count += 1

        logger.info(
            f"Processed notifications: {sent_count} sent, {failed_count} failed"
        )
        return {"sent": sent_count, "failed": failed_count}

    except Exception as e:
        logger.error(f"Error in process_pending_notifications: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def generate_daily_motivation(self):
    """
    Generate and send daily motivational messages to active users.
    Runs every day at 8:00 AM (configured in Celery beat schedule).
    """
    try:
        ai_service = OpenAIService()

        # Get users who:
        # - Have active dreams
        # - Want motivation notifications
        # - Are not in DND period
        users = (
            User.objects.filter(
                dreams__status="active",
                notification_prefs__motivation=True,
                is_active=True,
            )
            .distinct()
            .prefetch_related(
                Prefetch("dreams", queryset=Dream.objects.filter(status="active"))
            )
        )

        created_count = 0

        tracker = AIUsageTracker()

        for user in users:
            try:
                # Check AI background quota
                allowed, _quota_info = tracker.check_quota(user, "ai_background")
                if not allowed:
                    logger.info(
                        f"Skipping motivation for user {user.id}: background quota reached"
                    )
                    continue

                # Pick the most relevant active dream for motivation context
                active_dream = (
                    user.dreams.filter(status="active")
                    .order_by("-updated_at")
                    .first()
                )
                dream_title = active_dream.title if active_dream else "your dream"
                dream_category = (
                    getattr(active_dream, "category", None) if active_dream else None
                )
                progress = (
                    active_dream.progress_percentage if active_dream else 0
                )

                # Generate personalized motivation message and sanitize
                raw_message = ai_service.generate_motivational_message(
                    user_name=user.display_name or user.email.split("@")[0],
                    goal_title=dream_title,
                    progress_percentage=round(progress, 1),
                    streak_days=getattr(user, "streak_days", 0),
                    category=dream_category,
                )
                message = sanitize_text(raw_message)[:500]

                # Increment usage counter
                tracker.increment(user, "ai_background")

                # Create notification
                NotificationService.create(
                    user=user,
                    notification_type="motivation",
                    title=_("Daily motivation"),
                    body=message,
                    scheduled_for=timezone.now(),
                    data={
                        "action": "open_dreams",
                        "screen": "DreamsDashboard",
                        "dream_id": str(active_dream.id) if active_dream else None,
                        "category": dream_category,
                    },
                )

                created_count += 1

                # Update user's last_activity
                user.last_activity = timezone.now()
                user.save(update_fields=["last_activity"])

            except OpenAIError as e:
                logger.error(
                    f"OpenAI error generating motivation for user {user.id}: {str(e)}"
                )
                continue

            except Exception as e:
                logger.error(
                    f"Error generating motivation for user {user.id}: {str(e)}"
                )
                continue

        logger.info(f"Generated {created_count} daily motivation messages")
        return {"created": created_count}

    except Exception as e:
        logger.error(f"Error in generate_daily_motivation: {str(e)}")
        raise self.retry(exc=e, countdown=300)


@shared_task(name="notifications.send_weekly_digests")
@celery_distributed_lock(timeout=1800)
def send_weekly_digests():
    """
    Dispatch per-user weekly digest tasks for all active users.

    Can be called directly or via the ``send_weekly_report`` alias that
    the existing Celery Beat schedule references.
    """
    users = User.objects.filter(is_active=True)
    dispatched = 0

    for user in users.iterator():
        # Respect notification preferences -- skip if weekly_report disabled
        prefs = user.notification_prefs or {}
        if not prefs.get("weekly_report", True):
            continue

        send_user_digest.delay(str(user.id))
        dispatched += 1

    logger.info("Weekly digest: dispatched %d user tasks.", dispatched)
    return {"dispatched": dispatched}


@shared_task(
    name="notifications.send_user_digest",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_user_digest(self, user_id):
    """
    Generate and send the weekly progress digest for a single user.

    Steps:
    1. Gather stats for the past 7 days.
    2. Create a Notification record (type='weekly_report').
    3. Send a push notification via FCM.
    4. Send an HTML email via the core email task.
    """
    from apps.users.models import DailyActivity

    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        logger.warning("send_user_digest: user %s not found or inactive.", user_id)
        return {"sent": False, "reason": "user_not_found"}

    now = timezone.now()
    week_ago = now - timedelta(days=7)

    # ---- Gather weekly stats ------------------------------------------------

    # Tasks completed this week
    tasks_completed_qs = Task.objects.filter(
        goal__dream__user=user,
        status="completed",
        completed_at__gte=week_ago,
        completed_at__lte=now,
    )
    tasks_completed = tasks_completed_qs.count()

    # Total XP earned this week
    weekly_activities = DailyActivity.objects.filter(
        user=user,
        date__gte=week_ago.date(),
        date__lte=now.date(),
    )
    xp_earned = (
        weekly_activities.aggregate(
            total_xp=Sum("xp_earned"),
        )["total_xp"]
        or 0
    )
    total_minutes = (
        weekly_activities.aggregate(
            total_mins=Sum("minutes_active"),
        )["total_mins"]
        or 0
    )

    # Active dreams and their progress
    active_dreams = Dream.objects.filter(user=user, status="active")
    dreams_count = active_dreams.count()

    # Top 3 dreams by progress
    top_dreams = []
    for dream in active_dreams.order_by("-progress_percentage")[:3]:
        top_dreams.append(
            {
                "title": dream.title,
                "progress": round(dream.progress_percentage, 1),
                "id": str(dream.id),
            }
        )

    # Dreams completed this week
    dreams_completed = Dream.objects.filter(
        user=user,
        status="completed",
        completed_at__gte=week_ago,
        completed_at__lte=now,
    ).count()

    # Upcoming tasks for next week
    next_week = now + timedelta(days=7)
    upcoming_tasks_qs = (
        Task.objects.filter(
            goal__dream__user=user,
            goal__dream__status="active",
            status="pending",
            scheduled_date__gte=now,
            scheduled_date__lte=next_week,
        )
        .select_related("goal", "goal__dream")
        .order_by("scheduled_date")
    )
    upcoming_tasks = [
        {
            "title": t.title,
            "dream": t.goal.dream.title,
            "date": t.scheduled_date.strftime("%a %b %d") if t.scheduled_date else "",
        }
        for t in upcoming_tasks_qs[:5]
    ]
    upcoming_count = upcoming_tasks_qs.count()

    # Streak
    streak_days = user.streak_days

    # Motivational message
    motivational_msg = _pick_motivational_message(tasks_completed, streak_days)

    # ---- Build notification content -----------------------------------------

    display_name = user.display_name or user.email.split("@")[0]

    title = f"Your Week in Review, {display_name}"

    # Build a concise text body (used for push + Notification.body)
    body_parts = []
    if tasks_completed > 0:
        body_parts.append(
            f"{tasks_completed} task{'s' if tasks_completed != 1 else ''} completed"
        )
    if dreams_completed > 0:
        body_parts.append(
            f"{dreams_completed} dream{'s' if dreams_completed != 1 else ''} achieved!"
        )
    if xp_earned > 0:
        body_parts.append(f"{xp_earned} XP earned")
    if streak_days > 0:
        body_parts.append(f"{streak_days}-day streak")
    if not body_parts:
        body_parts.append("Check in to keep your momentum going")

    body = " | ".join(body_parts) + f". {motivational_msg}"

    # Data payload for deep-linking
    data = {
        "screen": "WeeklyDigest",
        "action": "view_digest",
        "tasks_completed": str(tasks_completed),
        "xp_earned": str(xp_earned),
        "streak_days": str(streak_days),
        "dreams_count": str(dreams_count),
    }

    # ---- Create Notification record -----------------------------------------

    notification = NotificationService.create(
        user=user,
        notification_type="weekly_report",
        title=title,
        body=body,
        scheduled_for=now,
        status="sent",
        sent_at=now,
        data=data,
    )

    # ---- Send push notification via FCM -------------------------------------

    _send_digest_push(user, title, body, data)

    # ---- Send email ---------------------------------------------------------

    email_context = {
        "display_name": display_name,
        "tasks_completed": tasks_completed,
        "dreams_completed": dreams_completed,
        "xp_earned": xp_earned,
        "total_minutes": total_minutes,
        "streak_days": streak_days,
        "dreams_count": dreams_count,
        "top_dreams": top_dreams,
        "upcoming_tasks": upcoming_tasks,
        "upcoming_count": upcoming_count,
        "motivational_msg": motivational_msg,
        "week_start": week_ago.strftime("%b %d"),
        "week_end": now.strftime("%b %d, %Y"),
        "app_url": getattr(settings, "FRONTEND_URL", "https://app.stepora.app"),
    }

    _send_digest_email(user, title, email_context)

    logger.info(
        "Weekly digest sent to %s: tasks=%d xp=%d streak=%d.",
        user.email,
        tasks_completed,
        xp_earned,
        streak_days,
    )
    return {
        "sent": True,
        "notification_id": str(notification.id),
        "tasks_completed": tasks_completed,
        "xp_earned": xp_earned,
    }


@shared_task(bind=True, max_retries=3)
def send_weekly_report(self):
    """
    Legacy entry point kept for the existing Celery Beat schedule.

    Delegates to the new ``send_weekly_digests`` dispatcher which fans out
    per-user digest tasks for better scalability and error isolation.
    """
    return send_weekly_digests()


@shared_task(bind=True, max_retries=3)
@celery_distributed_lock(timeout=600)
def check_inactive_users(self):
    """
    Check for inactive users and send rescue mode notifications.
    Runs daily to detect users who haven't been active for 3+ days.
    """
    try:
        ai_service = OpenAIService()
        threshold = timezone.now() - timedelta(days=3)

        # Find users who:
        # - Have active dreams
        # - Haven't been active in 3+ days
        # - Haven't received a rescue notification recently
        inactive_users = (
            User.objects.filter(
                dreams__status="active", last_activity__lt=threshold, is_active=True
            )
            .exclude(
                notifications__notification_type="rescue",
                notifications__created_at__gte=timezone.now() - timedelta(days=7),
            )
            .distinct()
            .prefetch_related(
                Prefetch("dreams", queryset=Dream.objects.filter(status="active"))
            )
        )

        created_count = 0

        tracker = AIUsageTracker()

        for user in inactive_users:
            try:
                # Check AI background quota
                allowed, _quota_info = tracker.check_quota(user, "ai_background")
                if not allowed:
                    logger.info(
                        f"Skipping rescue for user {user.id}: background quota reached"
                    )
                    continue

                # Generate personalized rescue message with AI and sanitize
                raw_rescue = ai_service.generate_rescue_message(user)
                rescue_message = sanitize_text(raw_rescue)[:500]

                # Increment usage counter
                tracker.increment(user, "ai_background")

                # Get user's most recent dream for context
                recent_dream = (
                    user.dreams.filter(status="active").order_by("-updated_at").first()
                )

                # Create rescue notification
                NotificationService.create(
                    user=user,
                    notification_type="rescue",
                    title=_("We are still here for you"),
                    body=rescue_message,
                    scheduled_for=timezone.now(),
                    data={
                        "action": "open_dream",
                        "screen": "DreamDetail",
                        "dream_id": str(recent_dream.id) if recent_dream else None,
                    },
                )

                created_count += 1

            except OpenAIError as e:
                logger.error(
                    f"OpenAI error generating rescue message for user {user.id}: {str(e)}"
                )
                continue

            except Exception as e:
                logger.error(
                    f"Error generating rescue message for user {user.id}: {str(e)}"
                )
                continue

        logger.info(f"Created {created_count} rescue mode notifications")
        return {"created": created_count}

    except Exception as e:
        logger.error(f"Error in check_inactive_users: {str(e)}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def send_reminder_notifications(self):
    """
    Send reminder notifications for goals with reminder_enabled.
    Runs every 15 minutes to check for upcoming goals.
    """
    try:
        from apps.dreams.models import Goal

        now = timezone.now()
        reminder_window_start = now
        reminder_window_end = now + timedelta(minutes=15)

        # Get goals with reminders in the next 15 minutes
        goals_with_reminders = Goal.objects.filter(
            reminder_enabled=True,
            reminder_time__gte=reminder_window_start,
            reminder_time__lt=reminder_window_end,
            status="pending",
        ).select_related("dream", "dream__user")

        created_count = 0

        for goal in goals_with_reminders:
            try:
                # Check if reminder already sent
                existing_notification = Notification.objects.filter(
                    user=goal.dream.user,
                    notification_type="reminder",
                    data__goal_id=str(goal.id),
                    created_at__gte=now - timedelta(hours=1),
                ).exists()

                if existing_notification:
                    continue

                # Create reminder notification
                NotificationService.create(
                    user=goal.dream.user,
                    notification_type="reminder",
                    title=_("Reminder: %(title)s") % {"title": goal.title},
                    body=_("It's time to work on your goal!"),
                    scheduled_for=goal.reminder_time,
                    data={
                        "action": "open_goal",
                        "screen": "GoalDetail",
                        "goal_id": str(goal.id),
                        "dream_id": str(goal.dream.id),
                    },
                )

                created_count += 1

            except Exception as e:
                logger.error(f"Error creating reminder for goal {goal.id}: {str(e)}")
                continue

        logger.info(f"Created {created_count} reminder notifications")
        return {"created": created_count}

    except Exception as e:
        logger.error(f"Error in send_reminder_notifications: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
@celery_distributed_lock(timeout=300)
def cleanup_old_notifications(self):
    """
    Clean up old read notifications to keep database lean.
    Runs weekly to delete notifications older than 30 days.
    """
    try:
        threshold = timezone.now() - timedelta(days=30)

        # Delete old read notifications
        deleted_count, _detail = Notification.objects.filter(
            read_at__lt=threshold, status="sent"
        ).delete()

        logger.info(f"Deleted {deleted_count} old notifications")
        return {"deleted": deleted_count}

    except Exception as e:
        logger.error(f"Error in cleanup_old_notifications: {str(e)}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def send_streak_milestone_notification(self, user_id, streak_days):
    """
    Send notification when user reaches streak milestone.
    Called from views when streak is updated.
    """
    try:
        user = User.objects.get(id=user_id)

        # Send milestone notification for specific milestones
        milestones = [7, 14, 30, 60, 100, 365]

        if streak_days in milestones:
            NotificationService.create(
                user=user,
                notification_type="achievement",
                title=_("%(days)s-day streak!") % {"days": streak_days},
                body=_(
                    "Incredible! You maintained your streak for %(days)s consecutive days. Keep it up!"
                )
                % {"days": streak_days},
                scheduled_for=timezone.now(),
                data={
                    "action": "open_profile",
                    "screen": "Profile",
                    "achievement": "streak",
                    "days": streak_days,
                },
            )

            logger.info(
                f"Sent streak milestone notification to user {user_id}: {streak_days} days"
            )
            return {"sent": True, "days": streak_days}

        return {"sent": False, "days": streak_days}

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for streak notification")
        return {"sent": False, "error": "user_not_found"}

    except Exception as e:
        logger.error(f"Error sending streak notification: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_level_up_notification(self, user_id, new_level):
    """
    Send notification when user levels up.
    Called from gamification logic when level increases.
    """
    try:
        user = User.objects.get(id=user_id)

        NotificationService.create(
            user=user,
            notification_type="achievement",
            title=_("Level %(level)s reached!") % {"level": new_level},
            body=_(
                "Congratulations! You reached level %(level)s. Keep achieving your dreams!"
            )
            % {"level": new_level},
            scheduled_for=timezone.now(),
            data={
                "action": "open_profile",
                "screen": "Profile",
                "achievement": "level_up",
                "level": new_level,
            },
        )

        logger.info(f"Sent level up notification to user {user_id}: level {new_level}")
        return {"sent": True, "level": new_level}

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for level up notification")
        return {"sent": False, "error": "user_not_found"}

    except Exception as e:
        logger.error(f"Error sending level up notification: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def expire_ringing_calls(self):
    """
    Expire calls stuck in 'ringing' for more than 30 seconds.
    Sets them to 'missed' and notifies both caller and callee.
    Runs every 15 seconds via Celery beat.
    """
    try:
        from apps.chat.models import Call

        threshold = timezone.now() - timedelta(seconds=30)

        stale_calls = Call.objects.filter(
            status="ringing",
            created_at__lt=threshold,
        ).select_related("caller", "callee")

        expired_count = 0

        for call in stale_calls:
            # Atomic update: only transition if still ringing (prevents race with accept/reject)
            updated = Call.objects.filter(id=call.id, status="ringing").update(
                status="missed", updated_at=timezone.now()
            )
            if not updated:
                continue  # Already accepted/rejected/cancelled by another process

            # Notify the callee about the missed call
            caller_name = call.caller.display_name or _("Someone")
            NotificationService.create(
                user=call.callee,
                notification_type="missed_call",
                title=_("Missed %(call_type)s call") % {"call_type": call.call_type},
                body=_("%(name)s tried to call you") % {"name": caller_name},
                scheduled_for=timezone.now(),
                data={
                    "call_id": str(call.id),
                    "caller_id": str(call.caller.id),
                    "type": "missed_call",
                    "screen": "CallHistory",
                },
            )

            # Notify the caller that callee didn't answer
            callee_name = call.callee.display_name or _("Your buddy")
            NotificationService.create(
                user=call.caller,
                notification_type="missed_call",
                title=_("%(name)s didn't answer") % {"name": callee_name},
                body=_("Your %(call_type)s call was not answered")
                % {"call_type": call.call_type},
                scheduled_for=timezone.now(),
                data={
                    "call_id": str(call.id),
                    "callee_id": str(call.callee.id),
                    "type": "missed_call",
                    "screen": "CallHistory",
                },
            )

            # Send real-time WebSocket events so caller/callee UIs update immediately
            try:
                from asgiref.sync import async_to_sync
                from channels.layers import get_channel_layer

                channel_layer = get_channel_layer()
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        f"notifications_{call.caller.id}",
                        {
                            "type": "send_notification",
                            "data": {
                                "type": "missed_call",
                                "call_id": str(call.id),
                                "message": _("%(name)s didn't answer")
                                % {"name": callee_name},
                            },
                        },
                    )
                    async_to_sync(channel_layer.group_send)(
                        f"notifications_{call.callee.id}",
                        {
                            "type": "send_notification",
                            "data": {
                                "type": "missed_call",
                                "call_id": str(call.id),
                                "message": _("Missed %(call_type)s call from %(name)s")
                                % {"call_type": call.call_type, "name": caller_name},
                            },
                        },
                    )
            except Exception as ws_err:
                logger.warning(f"Failed to send WebSocket missed-call event: {ws_err}")

            expired_count += 1

        if expired_count:
            logger.info(f"Expired {expired_count} ringing calls to missed")
        return {"expired": expired_count}

    except Exception as e:
        logger.error(f"Error in expire_ringing_calls: {str(e)}")
        raise self.retry(exc=e, countdown=15)


@shared_task(bind=True, max_retries=3)
def check_due_tasks(self):
    """
    Find tasks due in the next 3 minutes and send FCM push notifications
    with task_due data so the frontend triggers the task call overlay.
    Runs every 3 minutes via Celery beat.
    """
    try:
        from apps.notifications.fcm_service import FCMService
        from apps.notifications.models import UserDevice

        now = timezone.now()
        window_end = now + timedelta(minutes=3)
        today = now.date()

        # Find pending tasks scheduled for today with a time in the next 3 minutes
        tasks = Task.objects.filter(
            status="pending",
            scheduled_date__date=today,
            scheduled_date__gte=now,
            scheduled_date__lte=window_end,
        ).select_related("goal__dream", "goal__dream__user")

        fcm = FCMService()
        sent_count = 0

        for task in tasks:
            user = task.goal.dream.user
            if not user.is_active:
                continue

            # Skip if we already sent a task_due notification for this task recently
            already_sent = Notification.objects.filter(
                user=user,
                notification_type="task_due",
                data__task_id=str(task.id),
                created_at__gte=now - timedelta(minutes=10),
            ).exists()
            if already_sent:
                continue

            dream_title = ""
            try:
                dream_title = task.goal.dream.title or ""
            except Exception as e:
                logger.warning(
                    "Could not fetch dream title for task %s: %s", task.id, e
                )

            data = {
                "type": "task_due",
                "notification_type": "task_due",
                "task_id": str(task.id),
                "title": task.title or _("Task Due"),
                "dream": dream_title,
                "dream_title": dream_title,
                "priority": (
                    str(task.goal.dream.priority)
                    if task.goal.dream.priority
                    else "medium"
                ),
                "category": task.goal.dream.category or "personal",
            }

            # Create notification record
            NotificationService.create(
                user=user,
                notification_type="task_due",
                title=_("%(title)s") % {"title": task.title},
                body=_("Time to work on your task!"),
                scheduled_for=now,
                data=data,
            )

            # Send FCM push to all user devices
            devices = UserDevice.objects.filter(user=user, is_active=True)
            tokens = [d.fcm_token for d in devices if d.fcm_token]

            for token in tokens:
                try:
                    fcm.send_to_token(
                        token=token,
                        title=_("%(title)s") % {"title": task.title},
                        body=_("Time to work on your task!"),
                        data=data,
                    )
                    sent_count += 1
                except Exception as e:
                    logger.warning(f"FCM send failed for task {task.id}: {e}")

        if sent_count:
            logger.info(f"Sent {sent_count} task-due FCM notifications")
        return {"sent": sent_count}

    except Exception as e:
        logger.error(f"Error in check_due_tasks: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def cleanup_stale_fcm_tokens(self):
    """
    Deactivate FCM device registrations not updated in 60+ days.
    Stale tokens waste API calls and increase latency.
    Runs weekly alongside cleanup_old_notifications.
    """
    try:
        from .models import UserDevice

        threshold = timezone.now() - timedelta(days=60)
        deactivated = UserDevice.objects.filter(
            is_active=True,
            updated_at__lt=threshold,
        ).update(is_active=False)
        logger.info(f"Deactivated {deactivated} stale FCM device registrations")
        return {"deactivated": deactivated}
    except Exception as e:
        logger.error(f"Error in cleanup_stale_fcm_tokens: {e}")
        raise self.retry(exc=e, countdown=300)
