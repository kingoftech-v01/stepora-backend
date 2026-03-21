"""
Pytest configuration and shared fixtures for all tests.
"""

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient


def pytest_configure(config):
    """Disable Elasticsearch autosync and Stripe API calls during tests."""
    import os

    # Clear Stripe API key BEFORE Django settings load dotenv,
    # to prevent real API calls from module-level stripe.api_key assignments.
    os.environ["STRIPE_SECRET_KEY"] = ""
    os.environ["STRIPE_PUBLISHABLE_KEY"] = ""

    from django.conf import settings

    settings.ELASTICSEARCH_DSL_AUTOSYNC = False
    settings.ELASTICSEARCH_DSL_SIGNAL_PROCESSOR = (
        "django_elasticsearch_dsl.signals.BaseSignalProcessor"
    )
    settings.STRIPE_SECRET_KEY = ""

    import stripe

    stripe.api_key = ""


@pytest.fixture(autouse=True)
def _clear_stripe_api_key():
    """Ensure Stripe API key is empty for every test to prevent real API calls."""
    import stripe

    original = stripe.api_key
    stripe.api_key = ""
    yield
    stripe.api_key = original

from apps.ai.models import AIConversation as Conversation, AIMessage as Message
from apps.dreams.models import Dream, Goal, Task
from apps.notifications.models import Notification, NotificationTemplate, UserDevice
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import GamificationProfile, User
from core.auth.models import EmailAddress


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Setup test database and seed subscription plans."""
    with django_db_blocker.unblock():
        SubscriptionPlan.seed_plans()


@pytest.fixture
def api_client():
    """Return API client for making test requests"""
    return APIClient()


@pytest.fixture
def user_data():
    """Return sample user data"""
    return {
        "email": "testuser@example.com",
        "display_name": "Test User",
        "timezone": "Europe/Paris",
    }


@pytest.fixture
def user(db, user_data):
    """Create and return a test user with verified email"""
    password = user_data.pop("password", "testpassword123")
    user = User.objects.create_user(**user_data, password=password)
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


@pytest.fixture
def premium_user(db):
    """Create and return a premium user with an active Premium subscription."""
    user = User.objects.create_user(
        email="premium@example.com",
        password="testpassword123",
        display_name="Premium User",
        timezone="Europe/Paris",
    )
    EmailAddress.objects.get_or_create(
        user=user, email=user.email,
        defaults={"verified": True, "primary": True},
    )
    plan = SubscriptionPlan.objects.get(slug="premium")
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return user


@pytest.fixture
def pro_user(db):
    """Create and return a pro user with an active Pro subscription."""
    user = User.objects.create_user(
        email="prouser@example.com",
        password="testpassword123",
        display_name="Pro User",
    )
    EmailAddress.objects.get_or_create(
        user=user, email=user.email,
        defaults={"verified": True, "primary": True},
    )
    plan = SubscriptionPlan.objects.get(slug="pro")
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return user


@pytest.fixture
def authenticated_client(api_client, user):
    """Return authenticated API client (free user)"""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def premium_client(premium_user):
    """Return authenticated API client for premium user"""
    client = APIClient()
    client.force_authenticate(user=premium_user)
    return client


@pytest.fixture
def pro_client(pro_user):
    """Return authenticated API client for pro user"""
    client = APIClient()
    client.force_authenticate(user=pro_user)
    return client


@pytest.fixture
def dream_data(user):
    """Return sample dream data"""
    return {
        "user": user,
        "title": "Learn Django",
        "description": "Master Django framework for web development",
        "category": "education",
        "priority": 1,
        "status": "active",
    }


@pytest.fixture
def dream(db, dream_data):
    """Create and return a test dream"""
    return Dream.objects.create(**dream_data)


@pytest.fixture
def goal_data(dream):
    """Return sample goal data"""
    return {
        "dream": dream,
        "title": "Complete Django tutorial",
        "description": "Follow official Django tutorial",
        "order": 0,
        "status": "pending",
    }


@pytest.fixture
def goal(db, goal_data):
    """Create and return a test goal"""
    return Goal.objects.create(**goal_data)


@pytest.fixture
def task_data(goal):
    """Return sample task data"""
    return {
        "goal": goal,
        "title": "Read Django documentation",
        "description": "Read the official Django docs",
        "order": 0,
        "duration_mins": 30,
        "status": "pending",
    }


@pytest.fixture
def task(db, task_data):
    """Create and return a test task"""
    return Task.objects.create(**task_data)


@pytest.fixture
def conversation_data(user):
    """Return sample conversation data"""
    return {
        "user": user,
        "conversation_type": "general",
    }


@pytest.fixture
def conversation(db, conversation_data):
    """Create and return a test conversation"""
    return Conversation.objects.create(**conversation_data)


@pytest.fixture
def message_data(conversation):
    """Return sample message data"""
    return {"conversation": conversation, "role": "user", "content": "Hello, AI!"}


@pytest.fixture
def message(db, message_data):
    """Create and return a test message"""
    return Message.objects.create(**message_data)


@pytest.fixture
def notification_data(user):
    """Return sample notification data"""
    return {
        "user": user,
        "notification_type": "reminder",
        "title": "Test Notification",
        "body": "This is a test notification",
        "scheduled_for": timezone.now(),
    }


@pytest.fixture
def notification(db, notification_data):
    """Create and return a test notification"""
    return Notification.objects.create(**notification_data)


@pytest.fixture
def gamification_profile(db, user):
    """Create and return gamification profile"""
    return GamificationProfile.objects.create(
        user=user,
        health_xp=50,
        career_xp=30,
    )


@pytest.fixture
def notification_template(db):
    """Create and return notification template"""
    return NotificationTemplate.objects.create(
        name="test_template",
        notification_type="reminder",
        title_template="Reminder: {title}",
        body_template="Don't forget to {action}",
        is_active=True,
    )


@pytest.fixture
def mock_openai():
    """Mock OpenAI API calls (v1+ SDK: client.chat.completions.create, client.images.generate)"""
    with patch("integrations.openai_service._client") as mock_client, patch(
        "integrations.openai_service._async_client"
    ) as mock_async_client:

        # Mock synchronous chat completion
        mock_chat_create = Mock()
        mock_chat_create.return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content='{"goals": [{"title": "Goal 1", "tasks": []}]}',
                        function_call=None,
                    )
                )
            ],
            usage=Mock(total_tokens=100),
            model="gpt-4",
        )
        mock_client.chat.completions.create = mock_chat_create

        # Mock image generation (DALL-E)
        mock_image_generate = Mock()
        mock_image_generate.return_value = Mock(
            data=[Mock(url="https://example.com/vision_board.png")]
        )
        mock_client.images.generate = mock_image_generate

        # Mock async chat completion
        from unittest.mock import AsyncMock

        mock_async_chat_create = AsyncMock()
        mock_async_chat_create.return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content='{"goals": [{"title": "Goal 1", "tasks": []}]}',
                        function_call=None,
                    )
                )
            ],
            usage=Mock(total_tokens=100),
            model="gpt-4",
        )
        mock_async_client.chat.completions.create = mock_async_chat_create

        yield {
            "create": mock_chat_create,
            "async_create": mock_async_chat_create,
            "image": mock_image_generate,
            "_client": mock_client,
            "_async_client": mock_async_client,
        }


@pytest.fixture
def mock_celery():
    """Mock Celery task execution"""
    with patch("celery.app.task.Task.apply_async") as mock_async, patch(
        "celery.app.task.Task.delay"
    ) as mock_delay:

        mock_async.return_value = Mock(id=f"task_{uuid.uuid4().hex}")
        mock_delay.return_value = Mock(id=f"task_{uuid.uuid4().hex}")

        yield {"apply_async": mock_async, "delay": mock_delay}


@pytest.fixture
def multiple_users(db):
    """Create multiple test users"""
    users = []
    for i in range(3):
        user = User.objects.create_user(
            email=f"user{i}@example.com",
            password="testpassword123",
            display_name=f"Test User {i}",
        )
        users.append(user)
    return users


@pytest.fixture
def multiple_dreams(db, user):
    """Create multiple test dreams"""
    dreams = []
    statuses = ["active", "completed", "paused"]
    for i, status in enumerate(statuses):
        dream = Dream.objects.create(
            user=user,
            title=f"Dream {i}",
            description=f"Description for dream {i}",
            status=status,
            priority=i + 1,
        )
        dreams.append(dream)
    return dreams


@pytest.fixture
def complete_dream_structure(db, user):
    """Create complete dream with goals and tasks"""
    dream = Dream.objects.create(
        user=user,
        title="Complete Dream",
        description="Dream with full structure",
        status="active",
    )

    goals = []
    for i in range(3):
        goal = Goal.objects.create(
            dream=dream,
            title=f"Goal {i}",
            description=f"Description for goal {i}",
            order=i,
            status="pending",
        )
        goals.append(goal)

        # Create tasks for each goal
        for j in range(3):
            Task.objects.create(
                goal=goal,
                title=f"Task {i}-{j}",
                description=f"Description for task {i}-{j}",
                order=j,
                duration_mins=30,
                status="pending",
            )

    return {
        "dream": dream,
        "goals": goals,
        "tasks": Task.objects.filter(goal__dream=dream),
    }


@pytest.fixture
def second_user(db):
    """Create a second free user for cross-user/IDOR tests"""
    return User.objects.create_user(
        email="second@example.com",
        password="testpassword123",
        display_name="Second User",
        timezone="Europe/Paris",
    )


@pytest.fixture
def second_client(second_user):
    """Authenticated client for second free user"""
    client = APIClient()
    client.force_authenticate(user=second_user)
    return client


@pytest.fixture
def second_premium_user(db):
    """Create a second premium user with an active Premium subscription."""
    user = User.objects.create_user(
        email="premium2@example.com",
        password="testpassword123",
        display_name="Premium User 2",
        timezone="Europe/Paris",
    )
    plan = SubscriptionPlan.objects.get(slug="premium")
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return user


@pytest.fixture
def second_premium_client(second_premium_user):
    """Authenticated client for second premium user"""
    client = APIClient()
    client.force_authenticate(user=second_premium_user)
    return client


@pytest.fixture
def second_pro_user(db):
    """Create a second pro user with an active Pro subscription."""
    user = User.objects.create_user(
        email="pro2@example.com",
        password="testpassword123",
        display_name="Pro User 2",
    )
    plan = SubscriptionPlan.objects.get(slug="pro")
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return user


@pytest.fixture
def second_pro_client(second_pro_user):
    """Authenticated client for second pro user"""
    client = APIClient()
    client.force_authenticate(user=second_pro_user)
    return client


@pytest.fixture
def user_device(db, user):
    """Create a test FCM device registration."""
    return UserDevice.objects.create(
        user=user,
        fcm_token="fake-fcm-token-" + uuid.uuid4().hex,
        platform="android",
        device_name="Test Device",
        app_version="1.0.0",
    )


@pytest.fixture
def mock_fcm():
    """Mock Firebase Admin SDK for FCM tests."""
    mock_messaging = Mock()
    mock_messaging.send.return_value = "projects/test/messages/fake_id"
    mock_send_response = Mock(exception=None, message_id="fake_id")
    mock_messaging.send_each_for_multicast.return_value = Mock(
        success_count=1,
        failure_count=0,
        responses=[mock_send_response],
    )
    mock_messaging.subscribe_to_topic.return_value = Mock(failure_count=0)
    mock_messaging.unsubscribe_from_topic.return_value = Mock(failure_count=0)
    mock_messaging.UnregisteredError = type("UnregisteredError", (Exception,), {})
    mock_messaging.SenderIdMismatchError = type(
        "SenderIdMismatchError", (Exception,), {}
    )
    # Mock message classes
    mock_messaging.Notification = Mock
    mock_messaging.AndroidConfig = Mock
    mock_messaging.AndroidNotification = Mock
    mock_messaging.APNSConfig = Mock
    mock_messaging.APNSPayload = Mock
    mock_messaging.Aps = Mock
    mock_messaging.ApsAlert = Mock
    mock_messaging.WebpushConfig = Mock
    mock_messaging.WebpushNotification = Mock
    mock_messaging.Message = Mock
    mock_messaging.MulticastMessage = Mock

    with patch(
        "apps.notifications.fcm_service.get_firebase_app"
    ) as mock_app, patch.dict(
        "sys.modules",
        {
            "firebase_admin.messaging": mock_messaging,
            "firebase_admin": Mock(messaging=mock_messaging),
        },
    ):
        mock_app.return_value = Mock()
        yield {
            "app": mock_app,
            "messaging": mock_messaging,
        }


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Enable database access for all tests"""
