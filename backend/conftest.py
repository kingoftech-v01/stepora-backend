"""
Pytest configuration and shared fixtures for all tests.
"""

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient
from unittest.mock import Mock, patch
from datetime import timedelta
import uuid

from apps.users.models import User, FcmToken, GamificationProfile, DreamBuddy
from apps.dreams.models import Dream, Goal, Task, Obstacle
from apps.conversations.models import Conversation, Message
from apps.notifications.models import Notification, NotificationTemplate


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """Setup test database"""
    pass


@pytest.fixture
def api_client():
    """Return API client for making test requests"""
    return APIClient()


@pytest.fixture
def user_data():
    """Return sample user data"""
    return {
        'email': 'testuser@example.com',
        'display_name': 'Test User',
        'timezone': 'Europe/Paris',
    }


@pytest.fixture
def user(db, user_data):
    """Create and return a test user"""
    password = user_data.pop('password', 'testpassword123')
    user = User.objects.create_user(**user_data, password=password)
    return user


@pytest.fixture
def premium_user(db):
    """Create and return a premium user"""
    user = User.objects.create_user(
        email='premium@example.com',
        password='testpassword123',
        display_name='Premium User',
        timezone='Europe/Paris',
        subscription='premium',
        subscription_ends=timezone.now() + timedelta(days=30),
    )
    return user


@pytest.fixture
def pro_user(db):
    """Create and return a pro user"""
    user = User.objects.create_user(
        email='prouser@example.com',
        password='testpassword123',
        display_name='Pro User',
        subscription='pro',
        subscription_ends=timezone.now() + timedelta(days=30),
    )
    return user


@pytest.fixture
def authenticated_client(api_client, user):
    """Return authenticated API client"""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def dream_data(user):
    """Return sample dream data"""
    return {
        'user': user,
        'title': 'Learn Django',
        'description': 'Master Django framework for web development',
        'category': 'education',
        'priority': 1,
        'status': 'active'
    }


@pytest.fixture
def dream(db, dream_data):
    """Create and return a test dream"""
    return Dream.objects.create(**dream_data)


@pytest.fixture
def goal_data(dream):
    """Return sample goal data"""
    return {
        'dream': dream,
        'title': 'Complete Django tutorial',
        'description': 'Follow official Django tutorial',
        'order': 0,
        'status': 'pending'
    }


@pytest.fixture
def goal(db, goal_data):
    """Create and return a test goal"""
    return Goal.objects.create(**goal_data)


@pytest.fixture
def task_data(goal):
    """Return sample task data"""
    return {
        'goal': goal,
        'title': 'Read Django documentation',
        'description': 'Read the official Django docs',
        'order': 0,
        'duration_mins': 30,
        'status': 'pending'
    }


@pytest.fixture
def task(db, task_data):
    """Create and return a test task"""
    return Task.objects.create(**task_data)


@pytest.fixture
def conversation_data(user):
    """Return sample conversation data"""
    return {
        'user': user,
        'conversation_type': 'general',
        'title': 'Test Conversation',
        'context': {'topic': 'testing'}
    }


@pytest.fixture
def conversation(db, conversation_data):
    """Create and return a test conversation"""
    return Conversation.objects.create(**conversation_data)


@pytest.fixture
def message_data(conversation):
    """Return sample message data"""
    return {
        'conversation': conversation,
        'role': 'user',
        'content': 'Hello, AI!'
    }


@pytest.fixture
def message(db, message_data):
    """Create and return a test message"""
    return Message.objects.create(**message_data)


@pytest.fixture
def notification_data(user):
    """Return sample notification data"""
    return {
        'user': user,
        'notification_type': 'reminder',
        'title': 'Test Notification',
        'body': 'This is a test notification',
        'scheduled_for': timezone.now()
    }


@pytest.fixture
def notification(db, notification_data):
    """Create and return a test notification"""
    return Notification.objects.create(**notification_data)


@pytest.fixture
def fcm_token(db, user):
    """Create and return FCM token for user"""
    return FcmToken.objects.create(
        user=user,
        token=f'fcm_token_{uuid.uuid4().hex}',
        device_type='ios'
    )


@pytest.fixture
def gamification_profile(db, user):
    """Create and return gamification profile"""
    return GamificationProfile.objects.create(
        user=user,
        xp=100,
        level=2,
        attributes={'health': 50, 'career': 30}
    )


@pytest.fixture
def notification_template(db):
    """Create and return notification template"""
    return NotificationTemplate.objects.create(
        name='test_template',
        notification_type='reminder',
        title_template='Reminder: {title}',
        body_template='Don\'t forget to {action}',
        is_active=True
    )


@pytest.fixture
def mock_openai():
    """Mock OpenAI API calls"""
    with patch('openai.ChatCompletion.create') as mock_create, \
         patch('openai.ChatCompletion.acreate') as mock_acreate, \
         patch('openai.Image.create') as mock_image:

        # Mock synchronous chat completion
        mock_create.return_value = Mock(
            choices=[
                Mock(message=Mock(content='{"goals": [{"title": "Goal 1", "tasks": []}]}'))
            ]
        )

        # Mock asynchronous chat completion with streaming
        async def mock_stream():
            chunks = ['This ', 'is ', 'a ', 'test ', 'response.']
            for chunk in chunks:
                yield Mock(choices=[Mock(delta=Mock(content=chunk))])

        mock_acreate.return_value = mock_stream()

        # Mock image generation
        mock_image.return_value = Mock(
            data=[Mock(url='https://example.com/vision_board.png')]
        )

        yield {
            'create': mock_create,
            'acreate': mock_acreate,
            'image': mock_image
        }


@pytest.fixture
def mock_fcm():
    """Mock FCM (Firebase Cloud Messaging) calls"""
    with patch('firebase_admin.messaging.send') as mock_send, \
         patch('firebase_admin.messaging.send_multicast') as mock_multicast:

        mock_send.return_value = f'message_id_{uuid.uuid4().hex}'
        mock_multicast.return_value = Mock(
            success_count=1,
            failure_count=0,
            responses=[]
        )

        yield {
            'send': mock_send,
            'multicast': mock_multicast
        }


@pytest.fixture
def mock_celery():
    """Mock Celery task execution"""
    with patch('celery.app.task.Task.apply_async') as mock_async, \
         patch('celery.app.task.Task.delay') as mock_delay:

        mock_async.return_value = Mock(id=f'task_{uuid.uuid4().hex}')
        mock_delay.return_value = Mock(id=f'task_{uuid.uuid4().hex}')

        yield {
            'apply_async': mock_async,
            'delay': mock_delay
        }


@pytest.fixture
def multiple_users(db):
    """Create multiple test users"""
    users = []
    for i in range(3):
        user = User.objects.create_user(
            email=f'user{i}@example.com',
            password='testpassword123',
            display_name=f'Test User {i}'
        )
        users.append(user)
    return users


@pytest.fixture
def multiple_dreams(db, user):
    """Create multiple test dreams"""
    dreams = []
    statuses = ['active', 'completed', 'paused']
    for i, status in enumerate(statuses):
        dream = Dream.objects.create(
            user=user,
            title=f'Dream {i}',
            description=f'Description for dream {i}',
            status=status,
            priority=i + 1
        )
        dreams.append(dream)
    return dreams


@pytest.fixture
def complete_dream_structure(db, user):
    """Create complete dream with goals and tasks"""
    dream = Dream.objects.create(
        user=user,
        title='Complete Dream',
        description='Dream with full structure',
        status='active'
    )

    goals = []
    for i in range(3):
        goal = Goal.objects.create(
            dream=dream,
            title=f'Goal {i}',
            description=f'Description for goal {i}',
            order=i,
            status='pending'
        )
        goals.append(goal)

        # Create tasks for each goal
        for j in range(3):
            Task.objects.create(
                goal=goal,
                title=f'Task {i}-{j}',
                description=f'Description for task {i}-{j}',
                order=j,
                duration_mins=30,
                status='pending'
            )

    return {
        'dream': dream,
        'goals': goals,
        'tasks': Task.objects.filter(goal__dream=dream)
    }


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Enable database access for all tests"""
    pass
