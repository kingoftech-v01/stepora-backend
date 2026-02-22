# Stratégie de Tests - DreamPlanner

## Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────────┐
│                    PYRAMIDE DE TESTS                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                         /\                                       │
│                        /  \      E2E Tests                      │
│                       /    \     (API end-to-end)               │
│                      /──────\    ~10% - Parcours critiques      │
│                     /        \                                   │
│                    /          \  Integration Tests              │
│                   /            \ (API + Database)               │
│                  /──────────────\~30% - Services & API          │
│                 /                \                               │
│                /                  \ Unit Tests                  │
│               /                    \(pytest)                    │
│              /______________________\~60% - Logique métier      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Tests Unitaires (60%)

### 1.1 Backend (pytest + pytest-django)

**Fichiers à tester:**
```
apps/
├── dreams/
│   └── tests/
│       ├── test_models.py          ✅ Priorité haute
│       ├── test_views.py           ✅ Priorité haute
│       └── test_tasks.py
├── conversations/
│   └── tests/
│       ├── test_models.py
│       ├── test_views.py
│       └── test_consumers.py       ✅ Priorité haute
├── notifications/
│   └── tests/
│       ├── test_models.py
│       ├── test_views.py
│       └── test_tasks.py
├── users/
│   └── tests/
│       ├── test_models.py
│       └── test_views.py
└── calendar/
    └── tests/
        └── test_views.py
integrations/
├── test_openai_service.py          ✅ Priorité haute
```

**Exemple de test - AI Service:**

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
        mock_openai.ChatCompletion.create.return_value = MagicMock(
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
        mock_openai.ChatCompletion.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='Continue comme ça!'))]
        )

        user = MagicMock(display_name='Marie', xp=100, level=2, streak_days=7)
        message = self.ai_service.generate_motivational_message(user)

        assert len(message) <= 150
```

**Exemple de test - Dream Views:**

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

## 2. Tests d'Intégration (30%)

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

import pytest
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from config.asgi import application
from apps.users.models import User
from apps.conversations.models import Conversation

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestChatConsumer:
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

## 3. Tests E2E (10%)

### 3.1 Tests E2E API (Parcours Critiques)

```python
# tests/e2e/test_dream_flow.py

import pytest
from rest_framework.test import APIClient
from apps.users.models import User

@pytest.mark.django_db
class TestCreateDreamFlow:
    """Test du parcours complet: inscription -> création rêve -> génération plan"""

    def setup_method(self):
        self.client = APIClient()

    def test_full_dream_creation_flow(self):
        # 1. Inscription
        response = self.client.post('/api/auth/registration/', {
            'email': 'e2e@test.com',
            'password1': 'TestPass123A',
            'password2': 'TestPass123A',
        })
        assert response.status_code == 201
        token = response.data['key']

        # 2. Authentification
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        # 3. Créer un rêve
        response = self.client.post('/api/dreams/', {
            'title': 'Apprendre la guitare',
            'description': 'Je veux jouer mes chansons préférées',
            'category': 'creativity',
            'target_date': '2026-06-01',
        }, format='json')
        assert response.status_code == 201
        dream_id = response.data['id']

        # 4. Récupérer le rêve
        response = self.client.get(f'/api/dreams/{dream_id}/')
        assert response.status_code == 200
        assert response.data['title'] == 'Apprendre la guitare'

        # 5. Vérifier le rêve dans la liste
        response = self.client.get('/api/dreams/')
        assert response.status_code == 200
        assert len(response.data['results']) == 1

    def test_task_completion_flow(self):
        # Setup: créer utilisateur, rêve, goal, task
        user = User.objects.create_user(email='task@test.com', password='TestPass123A')
        self.client.force_authenticate(user=user)

        # Créer rêve -> goal -> task
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

        # Compléter la tâche
        response = self.client.post(f'/api/tasks/{task_id}/complete/')
        assert response.status_code == 200

        # Vérifier la progression
        response = self.client.get(f'/api/dreams/{dream_id}/')
        assert response.data['progress_percentage'] > 0
```

---

## 4. Tests de Performance

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
    http_req_duration: ['p(95)<500'],  // 95% des requêtes < 500ms
    http_req_failed: ['rate<0.01'],    // < 1% d'erreurs
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

## 5. Couverture de Code

### Objectifs de Couverture

| Module | Minimum | Target |
|--------|---------|--------|
| Services / Integrations | 95% | 99% |
| Views (DRF ViewSets) | 95% | 99% |
| Models | 95% | 99% |
| Utils / Validators | 95% | 99% |
| Celery Tasks | 90% | 99% |
| WebSocket Consumers | 90% | 99% |

### Configuration pytest

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
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: dreamplanner
          POSTGRES_PASSWORD: test
          POSTGRES_DB: dreamplanner_test
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
          POSTGRES_USER: dreamplanner
          POSTGRES_PASSWORD: test
          POSTGRES_DB: dreamplanner_test
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

## 7. Checklist de Test Avant Release

### Pre-Release Checklist

- [ ] Tous les tests unitaires passent (>80% coverage)
- [ ] Tous les tests d'intégration passent
- [ ] Tests E2E API passent
- [ ] Tests de charge passent (p95 < 500ms)
- [ ] Pas de régression de performance
- [ ] Tests WebSocket fonctionnent
- [ ] Revue de sécurité effectuée
- [ ] Migrations Django vérifiées
