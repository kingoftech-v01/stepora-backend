"""
Celery tasks for notifications app.
"""

from django.utils.translation import gettext as _
from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Count, Prefetch
from datetime import timedelta
import logging

from .models import Notification, NotificationTemplate
from apps.users.models import User
from apps.dreams.models import Dream, Task
from integrations.openai_service import OpenAIService
from core.exceptions import OpenAIError
from core.sanitizers import sanitize_text
from core.ai_usage import AIUsageTracker

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_pending_notifications(self):
    """
    Process and send pending notifications.
    Runs every minute to check for notifications that need to be sent.
    """
    try:
        now = timezone.now()

        # Get all pending notifications that should be sent now
        pending = Notification.objects.filter(
            status='pending',
            scheduled_for__lte=now
        ).select_related('user')

        from .services import NotificationDeliveryService
        service = NotificationDeliveryService()

        sent_count = 0
        failed_count = 0

        for notification in pending:
            try:
                if not notification.should_send():
                    # Reschedule for later (DND)
                    notification.scheduled_for = now + timedelta(hours=1)
                    notification.save(update_fields=['scheduled_for'])
                    continue

                success = service.deliver(notification)
                if success:
                    notification.mark_sent()
                    sent_count += 1
                else:
                    notification.mark_failed("All delivery channels failed")
                    failed_count += 1

            except Exception as e:
                logger.error(f"Error processing notification {notification.id}: {str(e)}")
                notification.mark_failed(str(e))
                failed_count += 1

        logger.info(f"Processed notifications: {sent_count} sent, {failed_count} failed")
        return {'sent': sent_count, 'failed': failed_count}

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
        users = User.objects.filter(
            dreams__status='active',
            notification_prefs__motivation=True,
            is_active=True
        ).distinct().prefetch_related(
            Prefetch('dreams', queryset=Dream.objects.filter(status='active'))
        )

        created_count = 0

        tracker = AIUsageTracker()

        for user in users:
            try:
                # Check AI background quota
                allowed, _ = tracker.check_quota(user, 'ai_background')
                if not allowed:
                    logger.info(f"Skipping motivation for user {user.id}: background quota reached")
                    continue

                # Generate personalized motivation message and sanitize
                raw_message = ai_service.generate_motivational_message(user)
                message = sanitize_text(raw_message)[:500]

                # Increment usage counter
                tracker.increment(user, 'ai_background')

                # Create notification
                Notification.objects.create(
                    user=user,
                    notification_type='motivation',
                    title=_('Daily motivation'),
                    body=message,
                    scheduled_for=timezone.now(),
                    data={
                        'action': 'open_dreams',
                        'screen': 'DreamsDashboard'
                    }
                )

                created_count += 1

                # Update user's last_activity
                user.last_activity = timezone.now()
                user.save(update_fields=['last_activity'])

            except OpenAIError as e:
                logger.error(f"OpenAI error generating motivation for user {user.id}: {str(e)}")
                continue

            except Exception as e:
                logger.error(f"Error generating motivation for user {user.id}: {str(e)}")
                continue

        logger.info(f"Generated {created_count} daily motivation messages")
        return {'created': created_count}

    except Exception as e:
        logger.error(f"Error in generate_daily_motivation: {str(e)}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def send_weekly_report(self):
    """
    Generate and send weekly progress reports to users.
    Runs every Sunday at 10:00 AM (configured in Celery beat schedule).
    """
    try:
        ai_service = OpenAIService()
        week_ago = timezone.now() - timedelta(days=7)

        # Get users with active dreams
        users = User.objects.filter(
            dreams__status='active',
            notification_prefs__weekly_report=True,
            is_active=True
        ).distinct()

        created_count = 0

        tracker = AIUsageTracker()

        for user in users:
            try:
                # Check AI background quota
                allowed, _ = tracker.check_quota(user, 'ai_background')
                if not allowed:
                    logger.info(f"Skipping weekly report for user {user.id}: background quota reached")
                    continue

                # Calculate weekly stats
                completed_tasks = Task.objects.filter(
                    goal__dream__user=user,
                    status='completed',
                    completed_at__gte=week_ago
                ).count()

                total_tasks = Task.objects.filter(
                    goal__dream__user=user,
                    status__in=['pending', 'in_progress', 'completed']
                ).count()

                # Calculate XP gained this week
                xp_gained = user.xp  # In production, you'd track weekly XP

                # Generate personalized report with AI and sanitize
                raw_report = ai_service.generate_weekly_report(
                    user=user,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                    xp_gained=xp_gained
                )
                report = sanitize_text(raw_report)[:2000]

                # Increment usage counter
                tracker.increment(user, 'ai_background')

                # Create notification
                Notification.objects.create(
                    user=user,
                    notification_type='weekly_report',
                    title=_('Your weekly report'),
                    body=report,
                    scheduled_for=timezone.now(),
                    data={
                        'action': 'open_stats',
                        'screen': 'WeeklyReport',
                        'stats': {
                            'completed_tasks': completed_tasks,
                            'total_tasks': total_tasks,
                            'xp_gained': xp_gained
                        }
                    }
                )

                created_count += 1

            except OpenAIError as e:
                logger.error(f"OpenAI error generating report for user {user.id}: {str(e)}")
                continue

            except Exception as e:
                logger.error(f"Error generating report for user {user.id}: {str(e)}")
                continue

        logger.info(f"Generated {created_count} weekly reports")
        return {'created': created_count}

    except Exception as e:
        logger.error(f"Error in send_weekly_report: {str(e)}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
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
        inactive_users = User.objects.filter(
            dreams__status='active',
            last_activity__lt=threshold,
            is_active=True
        ).exclude(
            notifications__notification_type='rescue',
            notifications__created_at__gte=timezone.now() - timedelta(days=7)
        ).distinct().prefetch_related(
            Prefetch('dreams', queryset=Dream.objects.filter(status='active'))
        )

        created_count = 0

        tracker = AIUsageTracker()

        for user in inactive_users:
            try:
                # Check AI background quota
                allowed, _ = tracker.check_quota(user, 'ai_background')
                if not allowed:
                    logger.info(f"Skipping rescue for user {user.id}: background quota reached")
                    continue

                # Generate personalized rescue message with AI and sanitize
                raw_rescue = ai_service.generate_rescue_message(user)
                rescue_message = sanitize_text(raw_rescue)[:500]

                # Increment usage counter
                tracker.increment(user, 'ai_background')

                # Get user's most recent dream for context
                recent_dream = user.dreams.filter(status='active').order_by('-updated_at').first()

                # Create rescue notification
                Notification.objects.create(
                    user=user,
                    notification_type='rescue',
                    title=_('We are still here for you'),
                    body=rescue_message,
                    scheduled_for=timezone.now(),
                    data={
                        'action': 'open_dream',
                        'screen': 'DreamDetail',
                        'dream_id': str(recent_dream.id) if recent_dream else None
                    }
                )

                created_count += 1

            except OpenAIError as e:
                logger.error(f"OpenAI error generating rescue message for user {user.id}: {str(e)}")
                continue

            except Exception as e:
                logger.error(f"Error generating rescue message for user {user.id}: {str(e)}")
                continue

        logger.info(f"Created {created_count} rescue mode notifications")
        return {'created': created_count}

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
            status='pending'
        ).select_related('dream', 'dream__user')

        created_count = 0

        for goal in goals_with_reminders:
            try:
                # Check if reminder already sent
                existing_notification = Notification.objects.filter(
                    user=goal.dream.user,
                    notification_type='reminder',
                    data__goal_id=str(goal.id),
                    created_at__gte=now - timedelta(hours=1)
                ).exists()

                if existing_notification:
                    continue

                # Create reminder notification
                Notification.objects.create(
                    user=goal.dream.user,
                    notification_type='reminder',
                    title=_('Reminder: %(title)s') % {'title': goal.title},
                    body=_("It's time to work on your goal!"),
                    scheduled_for=goal.reminder_time,
                    data={
                        'action': 'open_goal',
                        'screen': 'GoalDetail',
                        'goal_id': str(goal.id),
                        'dream_id': str(goal.dream.id)
                    }
                )

                created_count += 1

            except Exception as e:
                logger.error(f"Error creating reminder for goal {goal.id}: {str(e)}")
                continue

        logger.info(f"Created {created_count} reminder notifications")
        return {'created': created_count}

    except Exception as e:
        logger.error(f"Error in send_reminder_notifications: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def cleanup_old_notifications(self):
    """
    Clean up old read notifications to keep database lean.
    Runs weekly to delete notifications older than 30 days.
    """
    try:
        threshold = timezone.now() - timedelta(days=30)

        # Delete old read notifications
        deleted_count, _ = Notification.objects.filter(
            read_at__lt=threshold,
            status='sent'
        ).delete()

        logger.info(f"Deleted {deleted_count} old notifications")
        return {'deleted': deleted_count}

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
            Notification.objects.create(
                user=user,
                notification_type='achievement',
                title=_('%(days)s-day streak!') % {'days': streak_days},
                body=_('Incredible! You maintained your streak for %(days)s consecutive days. Keep it up!') % {'days': streak_days},
                scheduled_for=timezone.now(),
                data={
                    'action': 'open_profile',
                    'screen': 'Profile',
                    'achievement': 'streak',
                    'days': streak_days
                }
            )

            logger.info(f"Sent streak milestone notification to user {user_id}: {streak_days} days")
            return {'sent': True, 'days': streak_days}

        return {'sent': False, 'days': streak_days}

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for streak notification")
        return {'sent': False, 'error': 'user_not_found'}

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

        Notification.objects.create(
            user=user,
            notification_type='achievement',
            title=_('Level %(level)s reached!') % {'level': new_level},
            body=_('Congratulations! You reached level %(level)s. Keep achieving your dreams!') % {'level': new_level},
            scheduled_for=timezone.now(),
            data={
                'action': 'open_profile',
                'screen': 'Profile',
                'achievement': 'level_up',
                'level': new_level
            }
        )

        logger.info(f"Sent level up notification to user {user_id}: level {new_level}")
        return {'sent': True, 'level': new_level}

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for level up notification")
        return {'sent': False, 'error': 'user_not_found'}

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
        from apps.conversations.models import Call
        threshold = timezone.now() - timedelta(seconds=30)

        stale_calls = Call.objects.filter(
            status='ringing',
            created_at__lt=threshold,
        ).select_related('caller', 'callee')

        expired_count = 0

        for call in stale_calls:
            # Atomic update: only transition if still ringing (prevents race with accept/reject)
            updated = Call.objects.filter(id=call.id, status='ringing').update(
                status='missed', updated_at=timezone.now()
            )
            if not updated:
                continue  # Already accepted/rejected/cancelled by another process

            # Notify the callee about the missed call
            caller_name = call.caller.display_name or _('Someone')
            Notification.objects.create(
                user=call.callee,
                notification_type='missed_call',
                title=_('Missed %(call_type)s call') % {'call_type': call.call_type},
                body=_('%(name)s tried to call you') % {'name': caller_name},
                scheduled_for=timezone.now(),
                data={
                    'call_id': str(call.id),
                    'caller_id': str(call.caller.id),
                    'type': 'missed_call',
                    'screen': 'CallHistory',
                },
            )

            # Notify the caller that callee didn't answer
            callee_name = call.callee.display_name or _('Your buddy')
            Notification.objects.create(
                user=call.caller,
                notification_type='missed_call',
                title=_("%(name)s didn't answer") % {'name': callee_name},
                body=_('Your %(call_type)s call was not answered') % {'call_type': call.call_type},
                scheduled_for=timezone.now(),
                data={
                    'call_id': str(call.id),
                    'callee_id': str(call.callee.id),
                    'type': 'missed_call',
                    'screen': 'CallHistory',
                },
            )

            # Send real-time WebSocket events so caller/callee UIs update immediately
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync

                channel_layer = get_channel_layer()
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        f"notifications_{call.caller.id}",
                        {
                            'type': 'send_notification',
                            'data': {
                                'type': 'missed_call',
                                'call_id': str(call.id),
                                'message': _("%(name)s didn't answer") % {'name': callee_name},
                            },
                        },
                    )
                    async_to_sync(channel_layer.group_send)(
                        f"notifications_{call.callee.id}",
                        {
                            'type': 'send_notification',
                            'data': {
                                'type': 'missed_call',
                                'call_id': str(call.id),
                                'message': _('Missed %(call_type)s call from %(name)s') % {'call_type': call.call_type, 'name': caller_name},
                            },
                        },
                    )
            except Exception as ws_err:
                logger.warning(f"Failed to send WebSocket missed-call event: {ws_err}")

            expired_count += 1

        if expired_count:
            logger.info(f"Expired {expired_count} ringing calls to missed")
        return {'expired': expired_count}

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
            status='pending',
            scheduled_date__date=today,
            scheduled_date__gte=now,
            scheduled_date__lte=window_end,
        ).select_related('goal__dream', 'goal__dream__user')

        fcm = FCMService()
        sent_count = 0

        for task in tasks:
            user = task.goal.dream.user
            if not user.is_active:
                continue

            # Skip if we already sent a task_due notification for this task recently
            already_sent = Notification.objects.filter(
                user=user,
                notification_type='task_due',
                data__task_id=str(task.id),
                created_at__gte=now - timedelta(minutes=10),
            ).exists()
            if already_sent:
                continue

            dream_title = ''
            try:
                dream_title = task.goal.dream.title or ''
            except Exception as e:
                logger.warning('Could not fetch dream title for task %s: %s', task.id, e)

            data = {
                'type': 'task_due',
                'notification_type': 'task_due',
                'task_id': str(task.id),
                'title': task.title or _('Task Due'),
                'dream': dream_title,
                'dream_title': dream_title,
                'priority': str(task.goal.dream.priority) if task.goal.dream.priority else 'medium',
                'category': task.goal.dream.category or 'personal',
            }

            # Create notification record
            Notification.objects.create(
                user=user,
                notification_type='task_due',
                title=_('%(title)s') % {'title': task.title},
                body=_('Time to work on your task!'),
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
                        title=_('%(title)s') % {'title': task.title},
                        body=_('Time to work on your task!'),
                        data=data,
                    )
                    sent_count += 1
                except Exception as e:
                    logger.warning(f"FCM send failed for task {task.id}: {e}")

        if sent_count:
            logger.info(f"Sent {sent_count} task-due FCM notifications")
        return {'sent': sent_count}

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
        return {'deactivated': deactivated}
    except Exception as e:
        logger.error(f"Error in cleanup_stale_fcm_tokens: {e}")
        raise self.retry(exc=e, countdown=300)
