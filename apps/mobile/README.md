# DreamPlanner Mobile App

React Native mobile application for DreamPlanner - an AI-powered goal achievement platform.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | React Native 0.73.2 |
| Language | TypeScript 5.3 |
| Navigation | React Navigation 6 (bottom tabs + native stacks) |
| State Management | Zustand 4.5 |
| API Client | Axios + TanStack React Query 5 |
| UI Components | React Native Paper 5.12 |
| Icons | react-native-vector-icons (MaterialCommunityIcons) |
| Auth | Firebase Auth (via @react-native-firebase) |
| Push Notifications | Notifee + Firebase Cloud Messaging |
| Storage | React Native MMKV |
| i18n | Custom framework (15 languages) |

## Project Structure

```
src/
├── screens/                  # 16 screens
│   ├── auth/                 # Authentication flow
│   │   ├── LoginScreen.tsx
│   │   └── RegisterScreen.tsx
│   ├── main/                 # Bottom tab screens
│   │   ├── HomeScreen.tsx        # Dream list + notifications badge
│   │   ├── CalendarScreen.tsx    # Calendar views
│   │   ├── LeaderboardScreen.tsx # Rankings
│   │   └── ProfileScreen.tsx     # Profile + settings
│   ├── ChatScreen.tsx        # AI chat (WebSocket streaming)
│   ├── DreamDetailScreen.tsx # Dream goals/tasks with progress
│   ├── CreateDreamScreen.tsx # Dream creation form
│   ├── VisionBoardScreen.tsx # DALL-E vision boards
│   ├── MicroStartScreen.tsx  # 2-minute micro-tasks
│   ├── SocialScreen.tsx      # Activity feed
│   ├── CirclesScreen.tsx     # Dream circles
│   ├── CircleDetailScreen.tsx# Circle posts & challenges
│   ├── DreamBuddyScreen.tsx  # Buddy matching
│   ├── LeagueScreen.tsx      # League standings
│   ├── SubscriptionScreen.tsx# Stripe plans
│   ├── StoreScreen.tsx       # Cosmetic items
│   └── NotificationsScreen.tsx # Notification center
│
├── navigation/               # React Navigation config
│   ├── RootNavigator.tsx     # Auth vs Main conditional
│   ├── AuthNavigator.tsx     # Login/Register stack
│   ├── MainNavigator.tsx     # 5-tab navigator + nested stacks
│   └── types.ts              # Type-safe navigation params
│
├── services/                 # Backend communication
│   └── api.ts                # Axios client with Firebase token injection
│
├── stores/                   # Zustand state management
│   └── authStore.ts          # Auth state, language preference
│
├── hooks/                    # Custom React hooks
│   ├── useDreams.ts          # Dream CRUD + AI features
│   ├── useTasks.ts           # Task management
│   └── useChat.ts            # WebSocket chat
│
├── i18n/                     # Internationalization
│   ├── index.ts              # t() function, language switching
│   └── locales/              # 15 language files
│       ├── en.ts  ├── fr.ts  ├── es.ts  ├── pt.ts
│       ├── ar.ts  ├── zh.ts  ├── hi.ts  ├── ja.ts
│       ├── de.ts  ├── ru.ts  ├── ko.ts  ├── it.ts
│       ├── tr.ts  ├── nl.ts  └── pl.ts
│
├── theme/                    # Theming system
│   └── index.ts              # Colors, spacing, typography, light/dark
│
├── components/               # Reusable UI components
└── config/                   # App configuration
    └── env.ts                # Environment variables
```

## Navigation Architecture

```
RootNavigator
├── AuthNavigator (when not logged in)
│   ├── Login
│   └── Register
│
└── MainNavigator (when logged in)
    ├── HomeTab (stack)
    │   ├── HomeScreen (dream list)
    │   ├── DreamDetail
    │   ├── CreateDream
    │   ├── VisionBoard
    │   ├── MicroStart
    │   └── Notifications
    │
    ├── CalendarTab
    │   └── CalendarScreen
    │
    ├── ChatTab
    │   └── ChatScreen (WebSocket AI chat)
    │
    ├── SocialTab (stack)
    │   ├── SocialScreen (feed)
    │   ├── Circles
    │   ├── CircleDetail
    │   ├── DreamBuddy
    │   ├── Leaderboard
    │   └── League
    │
    └── ProfileTab (stack)
        ├── ProfileScreen
        ├── Subscription
        └── Store
```

## API Integration

All screens use real API calls via the centralized `ApiService` class. The service:

- Injects Firebase auth tokens automatically on every request
- Retries on 401 with token refresh
- Supports paginated responses (DRF format)
- Covers all backend endpoints:
  - **Dreams**: CRUD, AI analysis, plan generation, vision boards
  - **Tasks**: Create, complete, schedule
  - **Conversations**: WebSocket streaming chat with GPT-4
  - **Calendar**: Day/week/month views, auto-scheduling
  - **Notifications**: List, mark read, mark all read
  - **Subscriptions**: Plans, checkout, cancel, reactivate, portal
  - **Store**: Categories, items, purchase, equip/unequip, inventory
  - **Leagues**: Leagues, seasons, leaderboards, rewards
  - **Circles**: CRUD, join/leave, posts, challenges
  - **Social**: Friends, follows, activity feed, search
  - **Buddies**: Current, find match, pair, encourage

## Getting Started

```bash
# Install dependencies
npm install

# iOS (requires Xcode)
cd ios && pod install && cd ..
npm run ios

# Android (requires Android Studio)
npm run android

# Run tests
npm test

# Type checking
npm run typecheck

# Linting
npm run lint
```

## Environment Setup

Create `src/config/env.ts`:

```typescript
export const ENV = {
  API_URL: 'http://localhost:8000',
  WS_URL: 'ws://localhost:9000',
};
```

For production, point to your deployed backend URLs.

## Internationalization

The app supports 15 languages with a custom i18n framework:

```typescript
import { t, setLanguage } from '../i18n';

// Use translations
<Text>{t('home.title')}</Text>

// Switch language
setLanguage('fr');
```

Supported: English, French, Spanish, Portuguese, Arabic, Chinese, Hindi, Japanese, German, Russian, Korean, Italian, Turkish, Dutch, Polish.

## Testing

```bash
# Run all tests
npm test

# With coverage
npm test -- --coverage

# Run specific test
npm test -- --testPathPattern="i18n"
```

Test files are in `src/__tests__/` covering:
- i18n framework (language switching, translations, fallback)
- API service (endpoint wiring, error handling)
- Screen components (rendering, interactions)
