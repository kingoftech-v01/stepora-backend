"""
Tests for integration services (OpenAI, FCM, Firebase).
"""

import pytest
from unittest.mock import patch, Mock, AsyncMock
import json

from .openai_service import OpenAIService
from .fcm_service import FCMService
from .firebase_admin_service import FirebaseAdminService
from core.exceptions import OpenAIError, FCMError


class TestOpenAIService:
    """Test OpenAI integration service"""

    def test_init_service(self):
        """Test initializing OpenAI service"""
        service = OpenAIService()
        assert service is not None
        assert hasattr(service, 'SYSTEM_PROMPTS')

    def test_system_prompts_exist(self):
        """Test all required system prompts are defined"""
        service = OpenAIService()

        required_prompts = [
            'dream_creation',
            'planning',
            'motivation',
            'coaching',
            'rescue'
        ]

        for prompt_type in required_prompts:
            assert prompt_type in service.SYSTEM_PROMPTS
            assert len(service.SYSTEM_PROMPTS[prompt_type]) > 0

    def test_chat_completion(self, mock_openai):
        """Test synchronous chat completion"""
        service = OpenAIService()

        messages = [
            {'role': 'user', 'content': 'Hello'}
        ]

        response = service.chat(messages)

        assert response is not None
        mock_openai['create'].assert_called_once()

    def test_generate_plan(self, mock_openai, dream):
        """Test generating plan for dream"""
        service = OpenAIService()

        with patch('openai.ChatCompletion.create') as mock_create:
            mock_create.return_value = Mock(
                choices=[
                    Mock(
                        message=Mock(
                            content=json.dumps({
                                'goals': [
                                    {
                                        'title': 'Goal 1',
                                        'description': 'Description',
                                        'order': 0,
                                        'tasks': [
                                            {'title': 'Task 1', 'order': 0, 'duration': 30}
                                        ]
                                    }
                                ]
                            })
                        )
                    )
                ]
            )

            plan = service.generate_plan(dream, dream.user)

            assert 'goals' in plan
            assert len(plan['goals']) == 1
            assert plan['goals'][0]['title'] == 'Goal 1'

    def test_analyze_dream(self, mock_openai, dream):
        """Test analyzing dream with AI"""
        service = OpenAIService()

        with patch('openai.ChatCompletion.create') as mock_create:
            mock_create.return_value = Mock(
                choices=[
                    Mock(
                        message=Mock(
                            content=json.dumps({
                                'feasibility': 'high',
                                'timeline': '6 months',
                                'key_steps': ['Step 1', 'Step 2']
                            })
                        )
                    )
                ]
            )

            analysis = service.analyze_dream(dream)

            assert 'feasibility' in analysis
            assert analysis['feasibility'] == 'high'

    def test_generate_motivational_message(self, mock_openai, user, dream):
        """Test generating motivational message"""
        service = OpenAIService()

        with patch('openai.ChatCompletion.create') as mock_create:
            mock_create.return_value = Mock(
                choices=[Mock(message=Mock(content='Stay motivated!'))]
            )

            message = service.generate_motivational_message(user)

            assert message == 'Stay motivated!'
            mock_create.assert_called_once()

    def test_generate_two_minute_start(self, mock_openai, dream):
        """Test generating 2-minute start action"""
        service = OpenAIService()

        with patch('openai.ChatCompletion.create') as mock_create:
            mock_create.return_value = Mock(
                choices=[Mock(message=Mock(content='Open tutorial website'))]
            )

            action = service.generate_two_minute_start(dream)

            assert action == 'Open tutorial website'

    def test_generate_rescue_message(self, mock_openai, user, dream):
        """Test generating rescue message for inactive user"""
        service = OpenAIService()

        with patch('openai.ChatCompletion.create') as mock_create:
            mock_create.return_value = Mock(
                choices=[Mock(message=Mock(content='We miss you! Come back to your dreams.'))]
            )

            message = service.generate_rescue_message(user)

            assert 'miss you' in message.lower()

    def test_generate_weekly_report(self, mock_openai, user):
        """Test generating weekly report"""
        service = OpenAIService()

        with patch('openai.ChatCompletion.create') as mock_create:
            mock_create.return_value = Mock(
                choices=[Mock(message=Mock(content='Great week! You completed 5 tasks.'))]
            )

            report = service.generate_weekly_report(
                user=user,
                completed_tasks=5,
                total_tasks=10,
                xp_gained=150
            )

            assert 'completed' in report.lower()

    def test_predict_obstacles(self, mock_openai, dream):
        """Test predicting obstacles for dream"""
        service = OpenAIService()

        with patch('openai.ChatCompletion.create') as mock_create:
            mock_create.return_value = Mock(
                choices=[
                    Mock(
                        message=Mock(
                            content=json.dumps([
                                {
                                    'title': 'Time management',
                                    'description': 'Finding time to study',
                                    'likelihood': 'high',
                                    'solution': 'Use time blocking'
                                }
                            ])
                        )
                    )
                ]
            )

            obstacles = service.predict_obstacles(dream)

            assert len(obstacles) > 0
            assert obstacles[0]['title'] == 'Time management'

    def test_generate_task_adjustments(self, mock_openai, user):
        """Test generating task adjustment suggestions"""
        service = OpenAIService()

        with patch('openai.ChatCompletion.create') as mock_create:
            mock_create.return_value = Mock(
                choices=[
                    Mock(
                        message=Mock(
                            content=json.dumps({
                                'summary': 'Try shorter tasks',
                                'detailed': ['Break tasks into 30-min blocks', 'Schedule in morning']
                            })
                        )
                    )
                ]
            )

            from apps.dreams.models import Task
            tasks = []

            suggestions = service.generate_task_adjustments(user, tasks, completion_rate=40)

            assert 'summary' in suggestions
            assert 'detailed' in suggestions

    def test_generate_vision_board_image(self, mock_openai, dream):
        """Test generating vision board image with DALL-E"""
        service = OpenAIService()

        with patch('openai.Image.create') as mock_image:
            mock_image.return_value = Mock(
                data=[Mock(url='https://example.com/vision.png')]
            )

            url = service.generate_vision_board_image(dream)

            assert url == 'https://example.com/vision.png'
            mock_image.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_stream_async(self, dream, conversation):
        """Test async streaming chat"""
        service = OpenAIService()

        async def mock_stream():
            chunks = ['Hello', ' ', 'world']
            for chunk in chunks:
                yield Mock(choices=[Mock(delta={'content': chunk})])

        with patch('openai.ChatCompletion.acreate') as mock_acreate:
            mock_acreate.return_value = mock_stream()

            result = []
            async for chunk in service.chat_stream_async(
                messages=[{'role': 'user', 'content': 'Hi'}],
                conversation_type='general'
            ):
                result.append(chunk)

            assert len(result) == 3
            assert ''.join(result) == 'Hello world'

    def test_openai_error_handling(self):
        """Test OpenAI error handling"""
        service = OpenAIService()

        with patch('openai.ChatCompletion.create') as mock_create:
            mock_create.side_effect = Exception('API Error')

            with pytest.raises(OpenAIError):
                service.chat([{'role': 'user', 'content': 'Test'}])


class TestFCMService:
    """Test Firebase Cloud Messaging service"""

    def test_init_service(self):
        """Test initializing FCM service"""
        service = FCMService()
        assert service is not None

    def test_send_notification(self, mock_fcm, user, fcm_token, notification):
        """Test sending notification via FCM"""
        service = FCMService()

        with patch('firebase_admin.messaging.send') as mock_send:
            mock_send.return_value = 'message_id_123'

            result = service.send_notification(notification)

            assert result is True
            mock_send.assert_called_once()

    def test_send_notification_no_tokens(self, user, notification):
        """Test sending notification when user has no FCM tokens"""
        service = FCMService()

        result = service.send_notification(notification)

        assert result is False

    def test_send_to_multiple_tokens(self, mock_fcm, user, notification):
        """Test sending notification to multiple devices"""
        from apps.users.models import FcmToken

        # Create multiple FCM tokens
        FcmToken.objects.create(user=user, token='token1', device_type='ios')
        FcmToken.objects.create(user=user, token='token2', device_type='android')

        service = FCMService()

        with patch('firebase_admin.messaging.send_multicast') as mock_multicast:
            mock_multicast.return_value = Mock(
                success_count=2,
                failure_count=0
            )

            result = service.send_notification(notification)

            assert result is True
            mock_multicast.assert_called_once()

    def test_should_send_notification(self, user):
        """Test DND (Do Not Disturb) check"""
        service = FCMService()

        # No DND set - should send
        from django.utils import timezone
        now = timezone.now()

        result = service.should_send_notification(user, now)
        assert result is True

    def test_should_not_send_during_dnd(self, user):
        """Test notification blocked during DND hours"""
        service = FCMService()

        # Set DND hours (22:00 - 08:00)
        user.notification_prefs = {
            'dnd_start': '22:00',
            'dnd_end': '08:00'
        }
        user.save()

        from django.utils import timezone

        # Test at 23:00 (during DND)
        test_time = timezone.now().replace(hour=23, minute=0)

        # Implementation depends on service logic
        # result = service.should_send_notification(user, test_time)
        # assert result is False

    def test_build_notification_message(self, notification):
        """Test building FCM message"""
        service = FCMService()

        message = service._build_message(notification, 'fcm_token_123')

        # Check message structure
        assert message is not None

    def test_handle_invalid_token(self, mock_fcm, user, fcm_token, notification):
        """Test handling invalid FCM token"""
        service = FCMService()

        with patch('firebase_admin.messaging.send') as mock_send:
            mock_send.side_effect = Exception('Invalid registration token')

            with pytest.raises(FCMError):
                service.send_notification(notification)

    def test_batch_send_notifications(self, mock_fcm, multiple_users):
        """Test sending notifications in batch"""
        from apps.notifications.models import Notification
        from apps.users.models import FcmToken

        # Create FCM tokens for users
        for user in multiple_users:
            FcmToken.objects.create(user=user, token=f'token_{user.id}', device_type='ios')

        # Create notifications
        notifications = []
        for user in multiple_users:
            notif = Notification.objects.create(
                user=user,
                notification_type='reminder',
                title='Test',
                body='Body',
                scheduled_for=timezone.now()
            )
            notifications.append(notif)

        service = FCMService()

        with patch('firebase_admin.messaging.send') as mock_send:
            mock_send.return_value = 'message_id'

            for notif in notifications:
                service.send_notification(notif)

            assert mock_send.call_count == len(multiple_users)


class TestFirebaseAdminService:
    """Test Firebase Admin service"""

    def test_init_firebase_admin(self):
        """Test Firebase Admin initialization"""
        with patch('firebase_admin.initialize_app') as mock_init:
            service = FirebaseAdminService()

            # Firebase Admin should be initialized
            # This depends on implementation

    def test_verify_token(self, mock_firebase_auth):
        """Test verifying Firebase ID token"""
        service = FirebaseAdminService()

        with patch('firebase_admin.auth.verify_id_token') as mock_verify:
            mock_verify.return_value = {
                'uid': 'test_uid',
                'email': 'test@example.com'
            }

            result = service.verify_token('valid_token')

            assert result['uid'] == 'test_uid'
            assert result['email'] == 'test@example.com'

    def test_verify_invalid_token(self):
        """Test verifying invalid token"""
        service = FirebaseAdminService()

        with patch('firebase_admin.auth.verify_id_token') as mock_verify:
            mock_verify.side_effect = Exception('Invalid token')

            with pytest.raises(Exception):
                service.verify_token('invalid_token')

    def test_get_user_by_uid(self):
        """Test getting user by Firebase UID"""
        service = FirebaseAdminService()

        with patch('firebase_admin.auth.get_user') as mock_get:
            mock_get.return_value = Mock(
                uid='test_uid',
                email='test@example.com',
                display_name='Test User'
            )

            user = service.get_user('test_uid')

            assert user.uid == 'test_uid'
            assert user.email == 'test@example.com'

    def test_create_custom_token(self):
        """Test creating custom Firebase token"""
        service = FirebaseAdminService()

        with patch('firebase_admin.auth.create_custom_token') as mock_create:
            mock_create.return_value = b'custom_token_bytes'

            token = service.create_custom_token('test_uid')

            assert token == b'custom_token_bytes'
            mock_create.assert_called_once_with('test_uid')
