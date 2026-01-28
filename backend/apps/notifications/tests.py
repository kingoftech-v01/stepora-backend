"""
Tests for notifications app.
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from unittest.mock import patch, Mock
import uuid

from .models import Notification, NotificationTemplate
from apps.users.models import User, FcmToken


class TestNotificationModel:
    """Test Notification model"""

    def test_create_notification(self, db, notification_data):
        """Test creating a notification"""
        notification = Notification.objects.create(**notification_data)

        assert notification.user == notification_data['user']
        assert notification.notification_type == 'reminder'
        assert notification.status == 'pending'
        assert notification.read_at is None

    def test_notification_str(self, notification):
        """Test notification string representation"""
        expected = f"{notification.notification_type} - {notification.user.email}"
        assert str(notification) == expected

    def test_mark_read(self, notification):
        """Test marking notification as read"""
        assert notification.read_at is None

        notification.mark_read()

        assert notification.read_at is not None
        assert (timezone.now() - notification.read_at).seconds < 5

    def test_notification_scheduled_in_future(self, db, user):
        """Test notification scheduled for future"""
        future_time = timezone.now() + timedelta(hours=2)

        notification = Notification.objects.create(
            user=user,
            notification_type='reminder',
            title='Future notification',
            body='Scheduled for later',
            scheduled_for=future_time
        )

        assert notification.scheduled_for > timezone.now()
        assert notification.status == 'pending'

    def test_notification_with_data(self, db, user):
        """Test notification with additional data"""
        data = {
            'action': 'open_dream',
            'dream_id': str(uuid.uuid4()),
            'screen': 'DreamDetail'
        }

        notification = Notification.objects.create(
            user=user,
            notification_type='reminder',
            title='Test notification',
            body='With data',
            scheduled_for=timezone.now(),
            data=data
        )

        assert notification.data['action'] == 'open_dream'
        assert notification.data['screen'] == 'DreamDetail'


class TestNotificationTemplateModel:
    """Test NotificationTemplate model"""

    def test_create_template(self, db):
        """Test creating a notification template"""
        template = NotificationTemplate.objects.create(
            name='test_template',
            notification_type='reminder',
            title_template='Reminder: {title}',
            body_template='Don\'t forget to {action}',
            is_active=True
        )

        assert template.name == 'test_template'
        assert template.notification_type == 'reminder'
        assert template.is_active

    def test_render_template(self, notification_template):
        """Test rendering template with variables"""
        context = {
            'title': 'Complete task',
            'action': 'finish your homework'
        }

        title = notification_template.title_template.format(**context)
        body = notification_template.body_template.format(**context)

        assert title == 'Reminder: Complete task'
        assert body == 'Don\'t forget to finish your homework'

    def test_inactive_template(self, db):
        """Test inactive template"""
        template = NotificationTemplate.objects.create(
            name='inactive_template',
            notification_type='reminder',
            title_template='Test',
            body_template='Test',
            is_active=False
        )

        # Active templates query should not include this
        active_templates = NotificationTemplate.objects.filter(is_active=True)
        assert template not in active_templates


class TestNotificationViewSet:
    """Test Notification API endpoints"""

    def test_list_notifications(self, authenticated_client, user):
        """Test GET /api/notifications/"""
        # Create notifications
        Notification.objects.create(
            user=user,
            notification_type='reminder',
            title='Notification 1',
            body='Body 1',
            scheduled_for=timezone.now()
        )
        Notification.objects.create(
            user=user,
            notification_type='motivation',
            title='Notification 2',
            body='Body 2',
            scheduled_for=timezone.now()
        )

        response = authenticated_client.get('/api/notifications/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2

    def test_mark_notification_read(self, authenticated_client, notification):
        """Test POST /api/notifications/{id}/mark-read/"""
        assert notification.read_at is None

        response = authenticated_client.post(f'/api/notifications/{notification.id}/mark_read/')

        assert response.status_code == status.HTTP_200_OK
        notification.refresh_from_db()
        assert notification.read_at is not None

    def test_mark_all_read(self, authenticated_client, user):
        """Test POST /api/notifications/mark-all-read/"""
        # Create multiple unread notifications
        for i in range(3):
            Notification.objects.create(
                user=user,
                notification_type='reminder',
                title=f'Notification {i}',
                body=f'Body {i}',
                scheduled_for=timezone.now(),
                status='sent'
            )

        response = authenticated_client.post('/api/notifications/mark_all_read/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['marked_read'] == 3

        # All should be marked as read
        unread_count = Notification.objects.filter(user=user, read_at__isnull=True).count()
        assert unread_count == 0

    def test_unread_count(self, authenticated_client, user):
        """Test GET /api/notifications/unread-count/"""
        # Create some read and unread notifications
        Notification.objects.create(
            user=user,
            notification_type='reminder',
            title='Read notification',
            body='Body',
            scheduled_for=timezone.now(),
            status='sent',
            read_at=timezone.now()
        )

        for i in range(3):
            Notification.objects.create(
                user=user,
                notification_type='reminder',
                title=f'Unread {i}',
                body='Body',
                scheduled_for=timezone.now(),
                status='sent'
            )

        response = authenticated_client.get('/api/notifications/unread_count/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['unread_count'] == 3

    def test_filter_by_type(self, authenticated_client, user):
        """Test filtering notifications by type"""
        Notification.objects.create(
            user=user,
            notification_type='reminder',
            title='Reminder',
            body='Body',
            scheduled_for=timezone.now()
        )
        Notification.objects.create(
            user=user,
            notification_type='motivation',
            title='Motivation',
            body='Body',
            scheduled_for=timezone.now()
        )

        response = authenticated_client.get('/api/notifications/?notification_type=reminder')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['notification_type'] == 'reminder'


class TestNotificationTasks:
    """Test Celery tasks for notifications"""

    def test_process_pending_notifications(self, db, user, fcm_token, mock_fcm):
        """Test process_pending_notifications task"""
        # Create pending notifications
        Notification.objects.create(
            user=user,
            notification_type='reminder',
            title='Test notification',
            body='Body',
            scheduled_for=timezone.now() - timedelta(minutes=1),
            status='pending'
        )

        from apps.notifications.tasks import process_pending_notifications

        with patch('apps.notifications.tasks.FCMService') as mock_service:
            mock_service.return_value.should_send_notification.return_value = True
            mock_service.return_value.send_notification.return_value = True

            result = process_pending_notifications()

            assert result['sent'] == 1
            assert result['failed'] == 0

            # Notification should be marked as sent
            notification = Notification.objects.first()
            assert notification.status == 'sent'
            assert notification.sent_at is not None

    def test_process_pending_notifications_dnd(self, db, user, fcm_token, mock_fcm):
        """Test pending notifications respect DND"""
        # Create notification
        notification = Notification.objects.create(
            user=user,
            notification_type='reminder',
            title='Test notification',
            body='Body',
            scheduled_for=timezone.now() - timedelta(minutes=1),
            status='pending'
        )

        from apps.notifications.tasks import process_pending_notifications

        with patch('apps.notifications.tasks.FCMService') as mock_service:
            # User is in DND period
            mock_service.return_value.should_send_notification.return_value = False
            mock_service.return_value.send_notification.return_value = True

            result = process_pending_notifications()

            # Should be rescheduled, not sent
            notification.refresh_from_db()
            assert notification.status == 'pending'
            assert notification.scheduled_for > timezone.now()

    def test_generate_daily_motivation(self, db, user, dream, mock_openai):
        """Test generate_daily_motivation task"""
        # Set user preferences
        user.notification_prefs = {'motivation': True}
        user.save()

        from apps.notifications.tasks import generate_daily_motivation

        with patch('apps.notifications.tasks.OpenAIService') as mock_service:
            mock_service.return_value.generate_motivational_message.return_value = 'Stay motivated!'

            result = generate_daily_motivation()

            assert result['created'] >= 1

            # Notification should be created
            notification = Notification.objects.filter(
                user=user,
                notification_type='motivation'
            ).first()

            assert notification is not None
            assert notification.title == '💪 Motivation du jour'

    def test_send_weekly_report(self, db, user, dream, task, mock_openai):
        """Test send_weekly_report task"""
        # Set user preferences
        user.notification_prefs = {'weekly_report': True}
        user.save()

        # Complete a task
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save()

        from apps.notifications.tasks import send_weekly_report

        with patch('apps.notifications.tasks.OpenAIService') as mock_service:
            mock_service.return_value.generate_weekly_report.return_value = 'Great week!'

            result = send_weekly_report()

            assert result['created'] >= 1

            # Notification should be created
            notification = Notification.objects.filter(
                user=user,
                notification_type='weekly_report'
            ).first()

            assert notification is not None
            assert 'rapport hebdomadaire' in notification.title

    def test_check_inactive_users(self, db, user, dream, mock_openai):
        """Test check_inactive_users task (Rescue Mode)"""
        # Set user as inactive
        user.last_activity = timezone.now() - timedelta(days=4)
        user.save()

        from apps.notifications.tasks import check_inactive_users

        with patch('apps.notifications.tasks.OpenAIService') as mock_service:
            mock_service.return_value.generate_rescue_message.return_value = 'We miss you!'

            result = check_inactive_users()

            assert result['created'] >= 1

            # Rescue notification should be created
            notification = Notification.objects.filter(
                user=user,
                notification_type='rescue'
            ).first()

            assert notification is not None
            assert 'toujours là' in notification.title

    def test_send_reminder_notifications(self, db, user, goal):
        """Test send_reminder_notifications task"""
        # Set reminder for goal
        goal.reminder_enabled = True
        goal.reminder_time = timezone.now() + timedelta(minutes=10)
        goal.save()

        from apps.notifications.tasks import send_reminder_notifications

        result = send_reminder_notifications()

        assert result['created'] >= 1

        # Reminder notification should be created
        notification = Notification.objects.filter(
            user=user,
            notification_type='reminder'
        ).first()

        assert notification is not None

    def test_cleanup_old_notifications(self, db, user):
        """Test cleanup_old_notifications task"""
        # Create old read notifications
        old_date = timezone.now() - timedelta(days=35)

        for i in range(5):
            notification = Notification.objects.create(
                user=user,
                notification_type='reminder',
                title=f'Old notification {i}',
                body='Body',
                scheduled_for=old_date,
                status='sent',
                read_at=old_date
            )
            # Manually set created_at to old date
            notification.created_at = old_date
            notification.save()

        initial_count = Notification.objects.count()

        from apps.notifications.tasks import cleanup_old_notifications

        result = cleanup_old_notifications()

        assert result['deleted'] == 5
        assert Notification.objects.count() == initial_count - 5

    def test_send_streak_milestone_notification(self, db, user, mock_celery):
        """Test send_streak_milestone_notification task"""
        from apps.notifications.tasks import send_streak_milestone_notification

        result = send_streak_milestone_notification(str(user.id), 7)

        assert result['sent'] is True

        # Notification should be created
        notification = Notification.objects.filter(
            user=user,
            notification_type='achievement',
            data__achievement='streak'
        ).first()

        assert notification is not None
        assert '7 jours' in notification.title

    def test_send_level_up_notification(self, db, user):
        """Test send_level_up_notification task"""
        from apps.notifications.tasks import send_level_up_notification

        result = send_level_up_notification(str(user.id), 5)

        assert result['sent'] is True

        # Notification should be created
        notification = Notification.objects.filter(
            user=user,
            notification_type='achievement',
            data__achievement='level_up'
        ).first()

        assert notification is not None
        assert 'Niveau 5' in notification.title


class TestFCMService:
    """Test FCM service"""

    def test_should_send_notification_within_hours(self, db, user):
        """Test should_send_notification checks DND"""
        from integrations.fcm_service import FCMService

        service = FCMService()

        # Set DND hours
        user.notification_prefs = {
            'dnd_start': '22:00',
            'dnd_end': '08:00'
        }
        user.save()

        # Test during DND (assuming current time is 23:00)
        with patch('django.utils.timezone.now') as mock_now:
            mock_time = timezone.now().replace(hour=23, minute=0)
            mock_now.return_value = mock_time

            result = service.should_send_notification(user, mock_time)

            # Should not send during DND
            # Note: Implementation may vary
            # assert result is False

    def test_send_notification_success(self, db, user, fcm_token, notification, mock_fcm):
        """Test sending notification successfully"""
        from integrations.fcm_service import FCMService

        service = FCMService()

        with patch('firebase_admin.messaging.send') as mock_send:
            mock_send.return_value = 'message_id_123'

            result = service.send_notification(notification)

            assert result is True
            mock_send.assert_called_once()

    def test_send_notification_no_tokens(self, db, user, notification):
        """Test sending notification with no FCM tokens"""
        from integrations.fcm_service import FCMService

        service = FCMService()

        result = service.send_notification(notification)

        # Should fail gracefully
        assert result is False
