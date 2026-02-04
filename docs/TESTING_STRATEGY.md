# Stratégie de Tests - DreamPlanner

## Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────────┐
│                    PYRAMIDE DE TESTS                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                         /\                                       │
│                        /  \      E2E Tests                      │
│                       /    \     (Detox/Maestro)                │
│                      /──────\    ~10% - Parcours critiques      │
│                     /        \                                   │
│                    /          \  Integration Tests              │
│                   /            \ (API + Components)             │
│                  /──────────────\~30% - Services & API          │
│                 /                \                               │
│                /                  \ Unit Tests                  │
│               /                    \(Jest/Vitest)               │
│              /______________________\~60% - Logique métier      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Tests Unitaires (60%)

### 1.1 Backend (Vitest)

**Fichiers à tester:**
```
apps/api/src/
├── services/
│   ├── ai.service.test.ts         ✅ Priorité haute
│   ├── notification.service.test.ts
│   ├── calendar.service.test.ts
│   └── planning.service.test.ts   ✅ Priorité haute
├── utils/
│   ├── dateUtils.test.ts
│   ├── validation.test.ts
│   └── scheduling.test.ts
└── controllers/
    └── *.controller.test.ts
```

**Exemple de test - AI Service:**

```typescript
// apps/api/src/services/__tests__/ai.service.test.ts

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AIService } from '../ai.service';

describe('AIService', () => {
  let aiService: AIService;

  beforeEach(() => {
    aiService = new AIService();
  });

  describe('generatePlan', () => {
    it('should generate a valid plan structure', async () => {
      const dream = {
        title: 'Apprendre la guitare',
        description: 'Je veux jouer mes chansons préférées',
        targetDate: new Date('2026-06-01'),
        category: 'creativity',
      };

      const context = {
        userName: 'Marie',
        timezone: 'Europe/Paris',
        workSchedule: {
          workDays: [1, 2, 3, 4, 5],
          startTime: '09:00',
          endTime: '18:00',
        },
      };

      const plan = await aiService.generatePlan(dream, context);

      expect(plan).toHaveProperty('analysis');
      expect(plan).toHaveProperty('feasibility');
      expect(plan).toHaveProperty('goals');
      expect(plan.goals.length).toBeGreaterThan(0);
      expect(['high', 'medium', 'low']).toContain(plan.feasibility);
    });

    it('should respect work schedule when generating tasks', async () => {
      // Test que les tâches ne sont pas planifiées pendant les heures de travail
    });

    it('should handle missing target date gracefully', async () => {
      // Test avec date non spécifiée
    });
  });

  describe('generateMotivationalMessage', () => {
    it('should generate message under 100 characters', async () => {
      const message = await aiService.generateMotivationalMessage(
        50, // progress
        7,  // streak
        'Apprendre la guitare',
        'Marie'
      );

      expect(message.length).toBeLessThanOrEqual(100);
    });

    it('should adapt message to streak length', async () => {
      const message1 = await aiService.generateMotivationalMessage(50, 1, 'Test', 'User');
      const message7 = await aiService.generateMotivationalMessage(50, 7, 'Test', 'User');
      const message30 = await aiService.generateMotivationalMessage(50, 30, 'Test', 'User');

      // Les messages devraient être différents selon la série
      expect(message1).not.toBe(message30);
    });
  });
});
```

**Exemple de test - Scheduling Utils:**

```typescript
// apps/api/src/utils/__tests__/scheduling.test.ts

import { describe, it, expect } from 'vitest';
import {
  isWorkingHours,
  findAvailableSlots,
  calculateNextTaskDate,
  isDoNotDisturbTime,
} from '../scheduling';

describe('Scheduling Utils', () => {
  describe('isWorkingHours', () => {
    const workSchedule = {
      workDays: [1, 2, 3, 4, 5], // Lun-Ven
      startTime: '09:00',
      endTime: '18:00',
    };

    it('should return true during work hours on workday', () => {
      const monday10am = new Date('2026-02-02T10:00:00'); // Lundi
      expect(isWorkingHours(monday10am, workSchedule)).toBe(true);
    });

    it('should return false on weekend', () => {
      const saturday10am = new Date('2026-02-07T10:00:00'); // Samedi
      expect(isWorkingHours(saturday10am, workSchedule)).toBe(false);
    });

    it('should return false before work starts', () => {
      const monday7am = new Date('2026-02-02T07:00:00');
      expect(isWorkingHours(monday7am, workSchedule)).toBe(false);
    });

    it('should return false after work ends', () => {
      const monday7pm = new Date('2026-02-02T19:00:00');
      expect(isWorkingHours(monday7pm, workSchedule)).toBe(false);
    });
  });

  describe('findAvailableSlots', () => {
    it('should find slots outside work hours', () => {
      const slots = findAvailableSlots(
        new Date('2026-02-02'), // Lundi
        30, // durée en minutes
        { workDays: [1, 2, 3, 4, 5], startTime: '09:00', endTime: '18:00' }
      );

      expect(slots.length).toBeGreaterThan(0);
      slots.forEach(slot => {
        const hour = slot.getHours();
        expect(hour < 9 || hour >= 18).toBe(true);
      });
    });

    it('should respect minimum gap between tasks', () => {
      // Test que les créneaux ont au moins 15min d'écart
    });
  });

  describe('isDoNotDisturbTime', () => {
    it('should return true during DND hours', () => {
      const prefs = { dndStart: 22, dndEnd: 7 };

      expect(isDoNotDisturbTime(new Date('2026-02-02T23:00:00'), prefs)).toBe(true);
      expect(isDoNotDisturbTime(new Date('2026-02-02T06:00:00'), prefs)).toBe(true);
    });

    it('should return false outside DND hours', () => {
      const prefs = { dndStart: 22, dndEnd: 7 };

      expect(isDoNotDisturbTime(new Date('2026-02-02T10:00:00'), prefs)).toBe(false);
      expect(isDoNotDisturbTime(new Date('2026-02-02T20:00:00'), prefs)).toBe(false);
    });
  });
});
```

### 1.2 Mobile (Jest + React Native Testing Library)

**Fichiers à tester:**
```
apps/mobile/src/
├── stores/
│   ├── authStore.test.ts
│   ├── chatStore.test.ts
│   └── dreamsStore.test.ts
├── hooks/
│   ├── useChat.test.ts
│   └── useNotifications.test.ts
├── utils/
│   ├── formatters.test.ts
│   └── validators.test.ts
└── components/
    └── *.test.tsx
```

**Exemple de test - Auth Store:**

```typescript
// apps/mobile/src/stores/__tests__/authStore.test.ts

import { renderHook, act } from '@testing-library/react-hooks';
import { useAuthStore } from '../authStore';

describe('AuthStore', () => {
  beforeEach(() => {
    // Reset store between tests
    useAuthStore.getState().logout();
  });

  describe('setUser', () => {
    it('should set user and mark as authenticated', () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.setUser({
          id: '123',
          email: 'test@example.com',
          displayName: 'Test User',
          avatarUrl: null,
          timezone: 'Europe/Paris',
          subscription: 'free',
        });
      });

      expect(result.current.user?.email).toBe('test@example.com');
      expect(result.current.isAuthenticated).toBe(true);
    });
  });

  describe('logout', () => {
    it('should clear all user data', () => {
      const { result } = renderHook(() => useAuthStore());

      // First set a user
      act(() => {
        result.current.setUser({
          id: '123',
          email: 'test@example.com',
          displayName: 'Test',
          avatarUrl: null,
          timezone: 'Europe/Paris',
          subscription: 'premium',
        });
      });

      // Then logout
      act(() => {
        result.current.logout();
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.accessToken).toBeNull();
    });
  });

  describe('setWorkSchedule', () => {
    it('should update work schedule', () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.setWorkSchedule({
          workDays: [1, 2, 3, 4, 5],
          startTime: '09:00',
          endTime: '18:00',
        });
      });

      expect(result.current.workSchedule?.workDays).toEqual([1, 2, 3, 4, 5]);
    });
  });
});
```

**Exemple de test - Composant ChatBubble:**

```tsx
// apps/mobile/src/components/__tests__/ChatBubble.test.tsx

import React from 'react';
import { render, screen } from '@testing-library/react-native';
import { ChatBubble } from '../ChatBubble';

describe('ChatBubble', () => {
  it('renders user message correctly', () => {
    render(
      <ChatBubble
        message="Hello World"
        isUser={true}
        timestamp={new Date('2026-02-04T10:00:00')}
      />
    );

    expect(screen.getByText('Hello World')).toBeTruthy();
  });

  it('renders AI message with different style', () => {
    const { getByTestId } = render(
      <ChatBubble
        message="AI Response"
        isUser={false}
        timestamp={new Date('2026-02-04T10:00:00')}
      />
    );

    const bubble = getByTestId('chat-bubble');
    // Vérifier que le style est différent pour l'IA
    expect(bubble.props.style).toMatchObject(
      expect.objectContaining({ alignSelf: 'flex-start' })
    );
  });

  it('formats timestamp correctly', () => {
    render(
      <ChatBubble
        message="Test"
        isUser={true}
        timestamp={new Date('2026-02-04T10:30:00')}
      />
    );

    expect(screen.getByText('10:30')).toBeTruthy();
  });
});
```

---

## 2. Tests d'Intégration (30%)

### 2.1 API Integration Tests

```typescript
// apps/api/src/__tests__/integration/dreams.integration.test.ts

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import request from 'supertest';
import { app } from '../../index';
import { prisma } from '../../config/database';

describe('Dreams API Integration', () => {
  let authToken: string;
  let userId: string;

  beforeAll(async () => {
    // Setup: Create test user and get auth token
    const res = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'test@example.com',
        password: 'Test123!',
        displayName: 'Test User',
      });

    authToken = res.body.accessToken;
    userId = res.body.user.id;
  });

  afterAll(async () => {
    // Cleanup
    await prisma.user.delete({ where: { id: userId } });
    await prisma.$disconnect();
  });

  describe('POST /api/dreams', () => {
    it('should create a new dream', async () => {
      const response = await request(app)
        .post('/api/dreams')
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          title: 'Apprendre la guitare',
          description: 'Je veux jouer mes chansons préférées',
          category: 'creativity',
          targetDate: '2026-06-01',
        });

      expect(response.status).toBe(201);
      expect(response.body).toHaveProperty('id');
      expect(response.body.title).toBe('Apprendre la guitare');
      expect(response.body.status).toBe('active');
    });

    it('should reject invalid dream data', async () => {
      const response = await request(app)
        .post('/api/dreams')
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          title: '', // Invalid: empty title
          description: 'Test',
        });

      expect(response.status).toBe(400);
      expect(response.body).toHaveProperty('errors');
    });

    it('should require authentication', async () => {
      const response = await request(app)
        .post('/api/dreams')
        .send({
          title: 'Test Dream',
          description: 'Test',
        });

      expect(response.status).toBe(401);
    });
  });

  describe('POST /api/dreams/:id/generate-plan', () => {
    it('should generate a plan for a dream', async () => {
      // First create a dream
      const createRes = await request(app)
        .post('/api/dreams')
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          title: 'Courir un marathon',
          description: 'Mon premier marathon',
          targetDate: '2026-10-01',
        });

      const dreamId = createRes.body.id;

      // Then generate plan
      const response = await request(app)
        .post(`/api/dreams/${dreamId}/generate-plan`)
        .set('Authorization', `Bearer ${authToken}`)
        .send({
          availableHoursPerWeek: 5,
        });

      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('goals');
      expect(response.body.goals.length).toBeGreaterThan(0);
    }, 30000); // Timeout plus long pour l'appel IA
  });
});
```

### 2.2 Component Integration Tests

```tsx
// apps/mobile/src/screens/__tests__/ChatScreen.integration.test.tsx

import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChatScreen } from '../ChatScreen';
import { mockApiService } from '../../__mocks__/apiService';

jest.mock('../../services/api', () => mockApiService);

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

const wrapper = ({ children }) => (
  <QueryClientProvider client={queryClient}>
    {children}
  </QueryClientProvider>
);

describe('ChatScreen Integration', () => {
  beforeEach(() => {
    queryClient.clear();
    jest.clearAllMocks();
  });

  it('should send message and receive AI response', async () => {
    mockApiService.sendMessage.mockResolvedValueOnce({
      id: '1',
      role: 'assistant',
      content: 'Bonjour ! Comment puis-je t\'aider ?',
    });

    const { getByPlaceholderText, getByTestId, findByText } = render(
      <ChatScreen />,
      { wrapper }
    );

    // Type message
    const input = getByPlaceholderText('Écris ton message...');
    fireEvent.changeText(input, 'Bonjour');

    // Send message
    const sendButton = getByTestId('send-button');
    fireEvent.press(sendButton);

    // Wait for AI response
    await waitFor(() => {
      expect(findByText('Comment puis-je t\'aider ?')).toBeTruthy();
    });
  });

  it('should display quick suggestions when conversation is empty', () => {
    const { getByText } = render(<ChatScreen />, { wrapper });

    expect(getByText('Je veux apprendre une nouvelle langue')).toBeTruthy();
    expect(getByText('Je veux me mettre au sport')).toBeTruthy();
  });

  it('should handle suggestion tap', async () => {
    const { getByText, getByPlaceholderText } = render(
      <ChatScreen />,
      { wrapper }
    );

    const suggestion = getByText('Je veux apprendre une nouvelle langue');
    fireEvent.press(suggestion);

    const input = getByPlaceholderText('Écris ton message...');
    expect(input.props.value).toBe('Je veux apprendre une nouvelle langue');
  });
});
```

---

## 3. Tests E2E (10%)

### 3.1 Configuration Detox (React Native)

```javascript
// .detoxrc.js

module.exports = {
  testRunner: {
    args: {
      $0: 'jest',
      config: 'e2e/jest.config.js',
    },
    jest: {
      setupTimeout: 120000,
    },
  },
  apps: {
    'ios.debug': {
      type: 'ios.app',
      binaryPath: 'ios/build/Build/Products/Debug-iphonesimulator/DreamPlanner.app',
      build: 'xcodebuild -workspace ios/DreamPlanner.xcworkspace -scheme DreamPlanner -configuration Debug -sdk iphonesimulator -derivedDataPath ios/build',
    },
    'android.debug': {
      type: 'android.apk',
      binaryPath: 'android/app/build/outputs/apk/debug/app-debug.apk',
      build: 'cd android && ./gradlew assembleDebug assembleAndroidTest -DtestBuildType=debug',
    },
  },
  devices: {
    simulator: {
      type: 'ios.simulator',
      device: { type: 'iPhone 15' },
    },
    emulator: {
      type: 'android.emulator',
      device: { avdName: 'Pixel_5_API_33' },
    },
  },
  configurations: {
    'ios.sim.debug': {
      device: 'simulator',
      app: 'ios.debug',
    },
    'android.emu.debug': {
      device: 'emulator',
      app: 'android.debug',
    },
  },
};
```

### 3.2 Tests E2E Critiques

```typescript
// e2e/flows/onboarding.e2e.ts

import { device, element, by, expect } from 'detox';

describe('Onboarding Flow', () => {
  beforeAll(async () => {
    await device.launchApp({ newInstance: true });
  });

  it('should complete full onboarding flow', async () => {
    // Slide 1
    await expect(element(by.text('Transformez vos rêves en réalité'))).toBeVisible();
    await element(by.id('next-button')).tap();

    // Slide 2
    await expect(element(by.text('Parlez, nous planifions'))).toBeVisible();
    await element(by.id('next-button')).tap();

    // Slide 3
    await expect(element(by.text('Ne perdez jamais le cap'))).toBeVisible();
    await element(by.id('get-started-button')).tap();

    // Login/Register screen
    await expect(element(by.id('email-input'))).toBeVisible();
  });
});
```

```typescript
// e2e/flows/createDream.e2e.ts

import { device, element, by, expect, waitFor } from 'detox';

describe('Create Dream Flow', () => {
  beforeAll(async () => {
    await device.launchApp({ newInstance: true });
    // Login avec utilisateur de test
    await loginTestUser();
  });

  it('should create a dream through chat', async () => {
    // Naviguer vers Chat
    await element(by.id('tab-chat')).tap();

    // Attendre le message de bienvenue
    await waitFor(element(by.text(/Bonjour/)))
      .toBeVisible()
      .withTimeout(5000);

    // Envoyer un message
    await element(by.id('chat-input')).typeText('Je veux apprendre la guitare');
    await element(by.id('send-button')).tap();

    // Attendre la réponse de l'IA
    await waitFor(element(by.text(/guitare/)))
      .toBeVisible()
      .withTimeout(10000);

    // Répondre aux questions
    await element(by.id('chat-input')).typeText('Oui j\'ai déjà une guitare');
    await element(by.id('send-button')).tap();

    // Continuer la conversation...
    await element(by.id('chat-input')).typeText('30 minutes par jour');
    await element(by.id('send-button')).tap();

    await element(by.id('chat-input')).typeText('Dans 6 mois');
    await element(by.id('send-button')).tap();

    // Attendre la génération du plan
    await waitFor(element(by.text('Ton Plan')))
      .toBeVisible()
      .withTimeout(30000);

    // Accepter le plan
    await element(by.text('Adopter ce plan')).tap();

    // Vérifier que le rêve apparaît dans le dashboard
    await element(by.id('tab-dreams')).tap();
    await expect(element(by.text('Apprendre la guitare'))).toBeVisible();
  });

  it('should complete a task from calendar', async () => {
    await element(by.id('tab-calendar')).tap();

    // Trouver une tâche
    await waitFor(element(by.id('task-card')))
      .toBeVisible()
      .withTimeout(5000);

    // Compléter la tâche
    await element(by.id('complete-task-button')).tap();

    // Vérifier la célébration
    await waitFor(element(by.text(/Bravo/)))
      .toBeVisible()
      .withTimeout(3000);
  });
});
```

```typescript
// e2e/flows/notifications.e2e.ts

import { device, element, by, expect } from 'detox';

describe('Notifications Flow', () => {
  beforeAll(async () => {
    await device.launchApp({
      newInstance: true,
      permissions: { notifications: 'YES' },
    });
    await loginTestUser();
  });

  it('should receive and handle task reminder notification', async () => {
    // Simuler une notification
    await device.sendUserNotification({
      trigger: { type: 'push' },
      title: 'Rappel',
      body: 'Pratique guitare dans 15 min',
      payload: { taskId: 'test-task-id' },
    });

    // Tap sur la notification
    await element(by.text('Pratique guitare dans 15 min')).tap();

    // Devrait ouvrir le calendrier avec la tâche
    await expect(element(by.id('task-detail-modal'))).toBeVisible();
  });
});
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

### 4.2 Mobile Performance Tests

```typescript
// apps/mobile/src/__tests__/performance/rendering.perf.test.tsx

import { measureRenders } from 'reassure';
import { ChatScreen } from '../../screens/ChatScreen';

describe('Performance Tests', () => {
  it('ChatScreen renders within threshold', async () => {
    await measureRenders(<ChatScreen />, {
      runs: 10,
      scenario: async (screen) => {
        // Simuler interaction
        const input = screen.getByPlaceholderText('Écris ton message...');
        fireEvent.changeText(input, 'Test message');
      },
    });
  });

  it('DreamsList renders 50 items efficiently', async () => {
    const dreams = generateMockDreams(50);

    await measureRenders(<DreamsList dreams={dreams} />, {
      runs: 10,
    });
  });
});
```

---

## 5. Couverture de Code

### Objectifs de Couverture

| Module | Minimum | Idéal |
|--------|---------|-------|
| Services (Backend) | 80% | 90% |
| Controllers (Backend) | 70% | 85% |
| Utils | 90% | 95% |
| Stores (Mobile) | 85% | 95% |
| Components (Mobile) | 60% | 75% |
| Hooks (Mobile) | 80% | 90% |

### Configuration Jest

```javascript
// apps/mobile/jest.config.js

module.exports = {
  preset: 'react-native',
  setupFilesAfterEnv: ['@testing-library/jest-native/extend-expect'],
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/__tests__/**',
    '!src/**/__mocks__/**',
  ],
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 75,
      lines: 80,
      statements: 80,
    },
  },
};
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
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'yarn'

      - run: yarn install --frozen-lockfile

      - name: Run API tests
        run: yarn api test --coverage

      - name: Run Mobile tests
        run: yarn mobile test --coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'yarn'

      - run: yarn install --frozen-lockfile
      - run: yarn api db:push
      - run: yarn api test:integration

  e2e-ios:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - run: yarn install --frozen-lockfile
      - run: yarn mobile ios:build
      - run: yarn mobile e2e:ios
```

---

## 7. Checklist de Test Avant Release

### Pre-Release Checklist

- [ ] Tous les tests unitaires passent (>80% coverage)
- [ ] Tous les tests d'intégration passent
- [ ] Tests E2E sur iOS et Android passent
- [ ] Tests de charge passent (p95 < 500ms)
- [ ] Pas de régression de performance
- [ ] Tests d'accessibilité passent
- [ ] Tests sur différentes tailles d'écran
- [ ] Tests offline fonctionnent
- [ ] Tests de notifications fonctionnent
- [ ] Revue de sécurité effectuée
