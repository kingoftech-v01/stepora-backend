# Testing Strategy - Stepora

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    TESTING PYRAMID                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                         /\                                       │
│                        /  \      E2E Tests                      │
│                       /    \     (API end-to-end)               │
│                      /──────\    ~10% - Critical paths           │
│                     /        \                                   │
│                    /          \  Integration Tests              │
│                   /            \ (API + Database)               │
│                  /──────────────\~30% - Services & API          │
│                 /                \                               │
│                /                  \ Unit Tests                  │
│               /                    \(pytest)                    │
│              /______________________\~60% - Business logic      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Unit Tests (60%)

### 1.1 Backend (pytest + pytest-django)

**Files to test:**
```
apps/
├── dreams/
│   └── tests/
│       ├── test_models.py          ✅ High priority
│       ├── test_views.py           ✅ High priority
│       └── test_tasks.py
├── conversations/
│   └── tests/
│       ├── test_models.py
│       ├── test_views.py
│       └── test_consumers.py       ✅ High priority
├── notifications/
│   └── tests/
│       ├── test_models.py
│       ├── test_views.py
│       └── test_tasks.py
├── users/
│   └── tests/
│       ├── test_models.py
│       └── test_views.py
├── buddies/
│   └── tests/
│       ├── test_models.py
│       ├── test_views.py
│       └── test_consumers.py       ✅ High priority (BuddyChatConsumer, FCM push, block enforcement)
├── circles/
│   └── tests/
│       ├── test_models.py
│       ├── test_views.py
│       ├── test_consumers.py       ✅ High priority (CircleChatConsumer, block filtering)
│       └── test_calls.py           ✅ High priority (Agora call lifecycle, token generation)
├── social/
│   └── tests/
│       ├── test_models.py
│       ├── test_views.py
│       └── test_dream_posts.py     ✅ High priority (CRUD, feed algorithm, interactions)
└── calendar/
    └── tests/
        └── test_views.py
core/
├── test_consumers.py               ✅ High priority (RateLimitMixin, AuthenticatedConsumerMixin, BlockingMixin, ModerationMixin)
integrations/
├── test_openai_service.py          ✅ High priority
```

**Example test - AI Service:**

```python
# integrations/tests/test_openai_service.py

import pytest
from unittest.mock import patch, MagicMock
from integrations.openai_service import OpenAIService

class TestOpenAIService:
    def setup_method(self):
        self.ai_service = OpenAIService()

    @patch('integrations.openai_service.openai')
    def test_generate_plan_returns_valid_structure(self, mock_openai):
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"analysis": "...", "feasibility": "high", "goals": [{"title": "Les bases", "order": 0, "tasks": []}]}'))]
        )

        dream = MagicMock(
            title='Apprendre la guitare',
            description='Je veux jouer mes chansons préférées',
            target_date='2026-06-01',
            category='creativity',
        )
        user = MagicMock(
            work_schedule={'workDays': [1, 2, 3, 4, 5], 'startTime': '09:00', 'endTime': '18:00'},
            timezone='Europe/Paris',
        )

        plan = self.ai_service.generate_plan(dream, user)

        assert 'analysis' in plan
        assert 'feasibility' in plan
        assert 'goals' in plan
        assert len(plan['goals']) > 0
        assert plan['feasibility'] in ['high', 'medium', 'low']

    @patch('integrations.openai_service.openai')
    def test_generate_motivational_message_under_limit(self, mock_openai):
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='Continue comme ça!'))]
        )

        user = MagicMock(display_name='Marie', xp=100, level=2, streak_days=7)
        message = self.ai_service.generate_motivational_message(user)

        assert len(message) <= 150
```

**Example test - Dream Views:**

```python
# apps/dreams/tests/test_views.py

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.dreams.models import Dream

@pytest.mark.django_db
class TestDreamViewSet:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='Test123!',
            display_name='Test User',
        )
        self.client.force_authenticate(user=self.user)

    def test_create_dream(self):
        url = reverse('dream-list')
        data = {
            'title': 'Apprendre la guitare',
            'description': 'Je veux jouer mes chansons préférées',
            'category': 'creativity',
            'target_date': '2026-06-01',
        }

        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'Apprendre la guitare'
        assert response.data['status'] == 'active'

    def test_create_dream_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse('dream-list')
        data = {'title': 'Test', 'description': 'Test'}

        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_dreams_returns_only_own_dreams(self):
        Dream.objects.create(user=self.user, title='Mon rêve', description='Test')
        other_user = User.objects.create_user(email='other@test.com', password='Test123!')
        Dream.objects.create(user=other_user, title='Autre rêve', description='Test')

        url = reverse('dream-list')
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['title'] == 'Mon rêve'
```

---

## 2. Integration Tests (30%)

### 2.1 API Integration Tests

```python
# apps/dreams/tests/test_integration.py

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.dreams.models import Dream

@pytest.mark.django_db
class TestDreamsAPIIntegration:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='Test123!',
            display_name='Test User',
        )
        self.client.force_authenticate(user=self.user)

    def test_create_dream(self):
        url = reverse('dream-list')
        data = {
            'title': 'Apprendre la guitare',
            'description': 'Je veux jouer mes chansons préférées',
            'category': 'creativity',
            'target_date': '2026-06-01',
        }

        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'Apprendre la guitare'
        assert response.data['status'] == 'active'

    def test_reject_invalid_dream_data(self):
        url = reverse('dream-list')
        data = {
            'title': '',  # Invalid: empty title
            'description': 'Test',
        }

        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_require_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse('dream-list')
        data = {
            'title': 'Test Dream',
            'description': 'Test',
        }

        response = self.client.post(url, data, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.slow
    def test_generate_plan_for_dream(self):
        dream = Dream.objects.create(
            user=self.user,
            title='Courir un marathon',
            description='Mon premier marathon',
            target_date='2026-10-01',
        )

        url = reverse('dream-generate-plan', kwargs={'pk': dream.pk})
        response = self.client.post(url, {'available_hours_per_week': 5}, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'goals' in response.data
        assert len(response.data['goals']) > 0
```

### 2.2 WebSocket Integration Tests

```python
# apps/conversations/tests/test_consumers.py
# Note: Uses deprecated ws/conversations/ URL alias — new code should use ws/ai-chat/

import pytest
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from config.asgi import application
from apps.users.models import User
from apps.conversations.models import Conversation

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestAIChatConsumer:
    async def test_connect_with_valid_token(self):
        user = await database_sync_to_async(User.objects.create_user)(
            email='ws@test.com', password='Test123!'
        )
        conversation = await database_sync_to_async(Conversation.objects.create)(
            user=user, conversation_type='general'
        )

        communicator = WebsocketCommunicator(
            application,
            f'/ws/conversations/{conversation.id}/?token={user.auth_token.key}'
        )

        connected, _ = await communicator.connect()
        assert connected

        response = await communicator.receive_json_from()
        assert response['type'] == 'connection'
        assert response['status'] == 'connected'

        await communicator.disconnect()

    async def test_reject_without_authentication(self):
        communicator = WebsocketCommunicator(
            application,
            '/ws/conversations/fake-id/'
        )

        connected, code = await communicator.connect()
        assert not connected or code == 4003
```

---

## 3. E2E Tests (10%)

### 3.1 E2E API Tests (Critical Paths)

```python
# tests/e2e/test_dream_flow.py

import pytest
from rest_framework.test import APIClient
from apps.users.models import User

@pytest.mark.django_db
class TestCreateDreamFlow:
    """Test of the complete flow: registration -> dream creation -> plan generation"""

    def setup_method(self):
        self.client = APIClient()

    def test_full_dream_creation_flow(self):
        # 1. Registration
        response = self.client.post('/api/auth/registration/', {
            'email': 'e2e@test.com',
            'password1': 'TestPass123A',
            'password2': 'TestPass123A',
        })
        assert response.status_code == 201
        token = response.data['key']

        # 2. Authentication
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        # 3. Create a dream
        response = self.client.post('/api/dreams/', {
            'title': 'Apprendre la guitare',
            'description': 'Je veux jouer mes chansons préférées',
            'category': 'creativity',
            'target_date': '2026-06-01',
        }, format='json')
        assert response.status_code == 201
        dream_id = response.data['id']

        # 4. Retrieve the dream
        response = self.client.get(f'/api/dreams/{dream_id}/')
        assert response.status_code == 200
        assert response.data['title'] == 'Apprendre la guitare'

        # 5. Verify the dream in the list
        response = self.client.get('/api/dreams/')
        assert response.status_code == 200
        assert len(response.data['results']) == 1

    def test_task_completion_flow(self):
        # Setup: create user, dream, goal, task
        user = User.objects.create_user(email='task@test.com', password='TestPass123A')
        self.client.force_authenticate(user=user)

        # Create dream -> goal -> task
        dream_res = self.client.post('/api/dreams/', {
            'title': 'Test Dream', 'description': 'Test',
        }, format='json')
        dream_id = dream_res.data['id']

        goal_res = self.client.post(f'/api/dreams/{dream_id}/goals/', {
            'title': 'Goal 1', 'order': 0,
        }, format='json')
        goal_id = goal_res.data['id']

        task_res = self.client.post(f'/api/goals/{goal_id}/tasks/', {
            'title': 'Task 1', 'order': 0,
        }, format='json')
        task_id = task_res.data['id']

        # Complete the task
        response = self.client.post(f'/api/tasks/{task_id}/complete/')
        assert response.status_code == 200

        # Verify progress
        response = self.client.get(f'/api/dreams/{dream_id}/')
        assert response.data['progress_percentage'] > 0
```

---

## 4. Performance Tests

### 4.1 Backend Load Testing (k6)

```javascript
// tests/load/api-load-test.js

import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 20 },   // Ramp up
    { duration: '1m', target: 100 },   // Stay at 100 users
    { duration: '30s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% of requests < 500ms
    http_req_failed: ['rate<0.01'],    // < 1% errors
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:3000';

export default function () {
  // Login
  const loginRes = http.post(`${BASE_URL}/api/auth/login`, JSON.stringify({
    email: `loadtest${__VU}@test.com`,
    password: 'Test123!',
  }), {
    headers: { 'Content-Type': 'application/json' },
  });

  check(loginRes, {
    'login successful': (r) => r.status === 200,
  });

  const token = loginRes.json('accessToken');

  // Get dreams
  const dreamsRes = http.get(`${BASE_URL}/api/dreams`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  check(dreamsRes, {
    'dreams fetched': (r) => r.status === 200,
    'response time OK': (r) => r.timings.duration < 200,
  });

  // Get calendar
  const calendarRes = http.get(`${BASE_URL}/api/calendar?start=2026-02-01&end=2026-02-28`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  check(calendarRes, {
    'calendar fetched': (r) => r.status === 200,
  });

  sleep(1);
}
```

---

## 4.1 Test Categories for Real-Time Features

### WebSocket Consumer Tests
- Connection/disconnection lifecycle for all 4 consumers
- Post-connect token authentication flow
- Rate limiting (sliding window enforcement)
- Content moderation rejection
- Block enforcement (bidirectional) on BuddyChatConsumer and CircleChatConsumer
- Channel group messaging and broadcasting
- Heartbeat/ping lifecycle

### Call Lifecycle Tests
- Start call (CircleCall creation, Agora token generation)
- Join/leave/end call state transitions
- Participant tracking (CircleCallParticipant create/update)
- FCM push notification trigger on call start
- WebSocket `call_started` broadcast

### Feed Algorithm Tests
- Feed includes followed users' posts
- Feed includes public posts
- Feed excludes blocked users (bidirectional)
- `has_liked` and `has_encouraged` annotations
- Visibility filtering (public vs followers vs private)

### Cross-WebSocket Event Tests
- Buddy call broadcast from REST to WebSocket group
- Circle call broadcast from REST to WebSocket group
- FCM push fallback when partner not connected

---

## 5. Code Coverage

### Coverage Goals

| Module | Minimum | Target |
|--------|---------|--------|
| Services / Integrations | 95% | 99% |
| Views (DRF ViewSets) | 95% | 99% |
| Models | 95% | 99% |
| Utils / Validators | 95% | 99% |
| Celery Tasks | 90% | 99% |
| WebSocket Consumers | 90% | 99% |

### pytest Configuration

```ini
# pytest.ini

[pytest]
DJANGO_SETTINGS_MODULE = config.settings.testing
python_files = tests.py test_*.py *_tests.py
python_classes = Test*
python_functions = test_*
addopts = --cov --cov-report=html --cov-report=term-missing
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks integration tests
    e2e: marks end-to-end tests

[coverage:run]
source = apps/, integrations/, core/
omit =
    */migrations/*
    */tests/*
    */admin.py

[coverage:report]
fail_under = 80
```

---

## 6. CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml

name: Tests

on:
  push:
    branches: [main, development]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: stepora
          POSTGRES_PASSWORD: test
          POSTGRES_DB: stepora_test
        ports:
          - 5432:5432
      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - run: pip install -r requirements/testing.txt

      - name: Run migrations
        run: python manage.py migrate --settings=config.settings.testing

      - name: Run tests with coverage
        run: pytest --cov --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: stepora
          POSTGRES_PASSWORD: test
          POSTGRES_DB: stepora_test
        ports:
          - 5432:5432
      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - run: pip install -r requirements/testing.txt
      - run: python manage.py migrate --settings=config.settings.testing
      - run: pytest -m integration --settings=config.settings.testing
```

---

## 7. Pre-Release Test Checklist

### Pre-Release Checklist

- [ ] All unit tests pass (84% coverage)
- [ ] All integration tests pass
- [ ] E2E API tests pass
- [ ] Load tests pass (p95 < 500ms)
- [ ] No performance regression
- [ ] WebSocket tests work
- [ ] Security review completed
- [ ] Django migrations verified
