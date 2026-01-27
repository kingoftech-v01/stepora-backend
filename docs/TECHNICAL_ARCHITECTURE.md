# Architecture Technique - DreamPlanner

## 1. Vue d'Ensemble de l'Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTS                                   │
│  ┌──────────────┐                    ┌──────────────┐           │
│  │   iOS App    │                    │  Android App │           │
│  │ React Native │                    │ React Native │           │
│  └──────┬───────┘                    └──────┬───────┘           │
└─────────┼───────────────────────────────────┼───────────────────┘
          │                                   │
          └───────────────┬───────────────────┘
                          │ HTTPS/WSS
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API GATEWAY                                 │
│                   (AWS API Gateway)                              │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│   Auth      │   │   Core API  │   │  AI Service │
│  Service    │   │   Service   │   │   Service   │
│  (Firebase) │   │  (Node.js)  │   │  (Node.js)  │
└─────────────┘   └──────┬──────┘   └──────┬──────┘
                         │                  │
                         ▼                  ▼
               ┌─────────────────┐   ┌─────────────┐
               │   PostgreSQL    │   │  OpenAI API │
               │   + Redis       │   │   (GPT-4)   │
               └─────────────────┘   └─────────────┘
```

## 2. Stack Technique Détaillé

### 2.1 Application Mobile (Frontend)

```json
{
  "framework": "React Native 0.73+",
  "language": "TypeScript",
  "stateManagement": "Zustand",
  "navigation": "React Navigation 6",
  "ui": {
    "components": "React Native Paper / NativeBase",
    "icons": "React Native Vector Icons",
    "animations": "React Native Reanimated 3"
  },
  "networking": "Axios + React Query",
  "storage": "React Native MMKV",
  "calendar": "React Native Calendars",
  "notifications": "Notifee + Firebase"
}
```

### 2.2 Backend Services

```json
{
  "runtime": "Node.js 20 LTS",
  "framework": "Express.js / Fastify",
  "language": "TypeScript",
  "orm": "Prisma",
  "validation": "Zod",
  "authentication": "Firebase Admin SDK",
  "queue": "Bull (Redis)",
  "websocket": "Socket.io"
}
```

### 2.3 Base de Données

**PostgreSQL** - Données principales:
- Utilisateurs
- Objectifs et rêves
- Étapes et tâches
- Historique des conversations

**Redis** - Cache et temps réel:
- Sessions utilisateurs
- Cache des réponses IA
- File d'attente des notifications
- Rate limiting

### 2.4 Services Cloud

| Service | Provider | Usage |
|---------|----------|-------|
| Hosting Backend | AWS EC2 / Railway | API Server |
| Database | AWS RDS / Supabase | PostgreSQL |
| Cache | AWS ElastiCache | Redis |
| Storage | AWS S3 | Médias utilisateurs |
| CDN | CloudFront | Assets statiques |
| Push Notifications | Firebase | FCM |
| Authentication | Firebase | Auth |
| Analytics | Mixpanel | Tracking |
| Monitoring | Sentry | Error tracking |

## 3. Modèle de Données

### 3.1 Schéma Prisma

```prisma
// prisma/schema.prisma

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id              String    @id @default(uuid())
  firebaseUid     String    @unique
  email           String    @unique
  displayName     String?
  timezone        String    @default("Europe/Paris")
  workSchedule    Json?     // Horaires de travail
  preferences     Json?     // Préférences notifications
  subscription    String    @default("free") // free, premium, pro
  createdAt       DateTime  @default(now())
  updatedAt       DateTime  @updatedAt

  dreams          Dream[]
  conversations   Conversation[]
  notifications   Notification[]
}

model Dream {
  id              String    @id @default(uuid())
  userId          String
  user            User      @relation(fields: [userId], references: [id])

  title           String
  description     String    @db.Text
  targetDate      DateTime?
  priority        Int       @default(1) // 1-5
  status          String    @default("active") // active, completed, paused, archived
  category        String?   // career, health, education, personal, etc.

  aiAnalysis      Json?     // Analyse ChatGPT du rêve

  createdAt       DateTime  @default(now())
  updatedAt       DateTime  @updatedAt

  goals           Goal[]
  conversations   Conversation[]
}

model Goal {
  id              String    @id @default(uuid())
  dreamId         String
  dream           Dream     @relation(fields: [dreamId], references: [id])

  title           String
  description     String?
  order           Int       // Ordre dans la séquence

  estimatedDuration Int?    // En minutes
  scheduledStart  DateTime?
  scheduledEnd    DateTime?

  status          String    @default("pending") // pending, in_progress, completed, skipped
  completedAt     DateTime?

  reminderEnabled Boolean   @default(true)
  reminderTime    DateTime?

  createdAt       DateTime  @default(now())
  updatedAt       DateTime  @updatedAt

  tasks           Task[]
}

model Task {
  id              String    @id @default(uuid())
  goalId          String
  goal            Goal      @relation(fields: [goalId], references: [id])

  title           String
  description     String?
  order           Int

  scheduledDate   DateTime?
  scheduledTime   String?   // "HH:mm"
  duration        Int?      // Minutes

  isRecurring     Boolean   @default(false)
  recurringPattern Json?    // { type: "daily" | "weekly", days: [1,3,5] }

  status          String    @default("pending")
  completedAt     DateTime?

  createdAt       DateTime  @default(now())
  updatedAt       DateTime  @updatedAt
}

model Conversation {
  id              String    @id @default(uuid())
  userId          String
  user            User      @relation(fields: [userId], references: [id])
  dreamId         String?
  dream           Dream?    @relation(fields: [dreamId], references: [id])

  type            String    // "dream_creation", "planning", "check_in", "adjustment"

  createdAt       DateTime  @default(now())
  updatedAt       DateTime  @updatedAt

  messages        Message[]
}

model Message {
  id              String    @id @default(uuid())
  conversationId  String
  conversation    Conversation @relation(fields: [conversationId], references: [id])

  role            String    // "user" | "assistant" | "system"
  content         String    @db.Text

  metadata        Json?     // Extracted goals, dates, etc.
  tokensUsed      Int?

  createdAt       DateTime  @default(now())
}

model Notification {
  id              String    @id @default(uuid())
  userId          String
  user            User      @relation(fields: [userId], references: [id])

  type            String    // "reminder", "motivation", "progress", "achievement"
  title           String
  body            String
  data            Json?

  scheduledFor    DateTime
  sentAt          DateTime?
  readAt          DateTime?

  status          String    @default("pending") // pending, sent, failed, cancelled

  createdAt       DateTime  @default(now())
}
```

## 4. API Endpoints

### 4.1 Authentication
```
POST   /api/auth/register
POST   /api/auth/login
POST   /api/auth/refresh
DELETE /api/auth/logout
```

### 4.2 Dreams (Rêves/Objectifs)
```
GET    /api/dreams                  # Liste des rêves
POST   /api/dreams                  # Créer un rêve
GET    /api/dreams/:id              # Détail d'un rêve
PUT    /api/dreams/:id              # Modifier un rêve
DELETE /api/dreams/:id              # Supprimer un rêve
POST   /api/dreams/:id/analyze      # Analyser avec IA
POST   /api/dreams/:id/generate-plan # Générer le planning
```

### 4.3 Goals & Tasks
```
GET    /api/dreams/:dreamId/goals   # Liste des objectifs
POST   /api/dreams/:dreamId/goals   # Créer un objectif
PUT    /api/goals/:id               # Modifier un objectif
DELETE /api/goals/:id               # Supprimer un objectif
POST   /api/goals/:id/complete      # Marquer comme terminé

GET    /api/goals/:goalId/tasks     # Liste des tâches
POST   /api/goals/:goalId/tasks     # Créer une tâche
PUT    /api/tasks/:id               # Modifier une tâche
POST   /api/tasks/:id/complete      # Marquer comme terminée
```

### 4.4 Conversations (Chat IA)
```
GET    /api/conversations           # Historique
POST   /api/conversations           # Nouvelle conversation
GET    /api/conversations/:id       # Messages d'une conversation
POST   /api/conversations/:id/messages # Envoyer un message
```

### 4.5 Calendar
```
GET    /api/calendar                # Vue calendrier (query: start, end)
GET    /api/calendar/today          # Tâches du jour
PUT    /api/calendar/reschedule     # Replanifier des tâches
```

### 4.6 Notifications
```
GET    /api/notifications           # Liste des notifications
PUT    /api/notifications/:id/read  # Marquer comme lue
PUT    /api/user/notification-settings # Paramètres notifications
```

## 5. Intégration ChatGPT

### 5.1 System Prompt Principal

```typescript
const SYSTEM_PROMPT = `Tu es DreamPlanner, un assistant personnel spécialisé dans la planification d'objectifs et la réalisation de rêves.

TON RÔLE:
1. Écouter attentivement les rêves et objectifs de l'utilisateur
2. Poser des questions pertinentes pour bien comprendre
3. Décomposer les grands objectifs en étapes réalisables
4. Créer un planning réaliste tenant compte des contraintes
5. Motiver et encourager sans être condescendant

INFORMATIONS UTILISATEUR:
- Nom: {userName}
- Timezone: {timezone}
- Horaires de travail: {workSchedule}
- Préférences: {preferences}

RÈGLES:
- Toujours demander des précisions si l'objectif est vague
- Proposer des délais réalistes
- Tenir compte de l'équilibre vie pro/perso
- Inclure des pauses et temps de repos
- Être encourageant mais honnête sur la faisabilité

FORMAT DE RÉPONSE POUR LA PLANIFICATION:
Quand tu génères un plan, utilise ce format JSON:
{
  "analysis": "Analyse du rêve/objectif",
  "feasibility": "high|medium|low",
  "estimatedDuration": "X semaines/mois",
  "goals": [
    {
      "title": "Titre de l'étape",
      "description": "Description détaillée",
      "duration": "X jours/semaines",
      "tasks": [
        {
          "title": "Tâche spécifique",
          "duration": 60, // minutes
          "frequency": "daily|weekly|once"
        }
      ]
    }
  ],
  "tips": ["Conseil 1", "Conseil 2"],
  "potentialObstacles": ["Obstacle 1", "Obstacle 2"]
}`;
```

### 5.2 Service d'Intégration

```typescript
// src/services/ai.service.ts

import OpenAI from 'openai';

interface PlanningResult {
  analysis: string;
  feasibility: 'high' | 'medium' | 'low';
  estimatedDuration: string;
  goals: GeneratedGoal[];
  tips: string[];
  potentialObstacles: string[];
}

class AIService {
  private openai: OpenAI;

  constructor() {
    this.openai = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY,
    });
  }

  async chat(
    conversationHistory: Message[],
    userMessage: string,
    context: UserContext
  ): Promise<string> {
    const systemPrompt = this.buildSystemPrompt(context);

    const messages = [
      { role: 'system', content: systemPrompt },
      ...conversationHistory.map(m => ({
        role: m.role,
        content: m.content,
      })),
      { role: 'user', content: userMessage },
    ];

    const response = await this.openai.chat.completions.create({
      model: 'gpt-4-turbo-preview',
      messages,
      temperature: 0.7,
      max_tokens: 2000,
    });

    return response.choices[0].message.content;
  }

  async generatePlan(
    dream: Dream,
    userContext: UserContext
  ): Promise<PlanningResult> {
    const prompt = `
Génère un plan détaillé pour atteindre cet objectif:

RÊVE/OBJECTIF: ${dream.title}
DESCRIPTION: ${dream.description}
DATE CIBLE: ${dream.targetDate || 'Non spécifiée'}
CATÉGORIE: ${dream.category}

Contexte utilisateur:
- Horaires de travail: ${JSON.stringify(userContext.workSchedule)}
- Disponibilités: ${userContext.availableHoursPerWeek}h/semaine
- Niveau d'engagement souhaité: ${userContext.commitmentLevel}

Réponds UNIQUEMENT avec le JSON du plan, sans texte autour.
    `;

    const response = await this.openai.chat.completions.create({
      model: 'gpt-4-turbo-preview',
      messages: [
        { role: 'system', content: PLANNING_SYSTEM_PROMPT },
        { role: 'user', content: prompt },
      ],
      temperature: 0.5,
      response_format: { type: 'json_object' },
    });

    return JSON.parse(response.choices[0].message.content);
  }

  async generateMotivationalMessage(
    progress: number,
    streak: number,
    goalTitle: string
  ): Promise<string> {
    const response = await this.openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        {
          role: 'system',
          content: 'Tu génères des messages de motivation courts et personnalisés (max 100 caractères).',
        },
        {
          role: 'user',
          content: `Progression: ${progress}%, Série: ${streak} jours, Objectif: "${goalTitle}"`,
        },
      ],
      temperature: 0.8,
      max_tokens: 50,
    });

    return response.choices[0].message.content;
  }
}
```

## 6. Système de Notifications

### 6.1 Types de Notifications

| Type | Déclencheur | Exemple |
|------|-------------|---------|
| `reminder` | Tâche programmée | "C'est l'heure de pratiquer l'anglais!" |
| `motivation` | Quotidien/hebdo | "Tu as déjà accompli 3 tâches cette semaine!" |
| `progress` | Milestone atteint | "50% de ton objectif atteint!" |
| `achievement` | Badge débloqué | "Badge 'Régulier' obtenu!" |
| `check_in` | Inactivité détectée | "Comment avances-tu sur ton projet?" |

### 6.2 Service de Notifications

```typescript
// src/services/notification.service.ts

import * as admin from 'firebase-admin';
import Bull from 'bull';

class NotificationService {
  private queue: Bull.Queue;

  constructor() {
    this.queue = new Bull('notifications', {
      redis: process.env.REDIS_URL,
    });

    this.queue.process(async (job) => {
      await this.sendNotification(job.data);
    });
  }

  async scheduleTaskReminder(task: Task, userId: string) {
    const user = await prisma.user.findUnique({
      where: { id: userId },
    });

    if (!user.preferences?.notifications?.reminders) return;

    const reminderTime = new Date(task.scheduledDate);
    reminderTime.setMinutes(
      reminderTime.getMinutes() - (user.preferences.reminderMinutesBefore || 15)
    );

    await this.queue.add(
      {
        userId,
        type: 'reminder',
        title: 'Rappel',
        body: task.title,
        data: { taskId: task.id, goalId: task.goalId },
      },
      { delay: reminderTime.getTime() - Date.now() }
    );
  }

  async sendNotification(notification: NotificationPayload) {
    const user = await prisma.user.findUnique({
      where: { id: notification.userId },
    });

    // Vérifier les préférences "Ne pas déranger"
    if (this.isDoNotDisturbTime(user)) {
      // Reporter la notification
      return this.rescheduleAfterDND(notification, user);
    }

    const tokens = await this.getUserTokens(notification.userId);

    await admin.messaging().sendEachForMulticast({
      tokens,
      notification: {
        title: notification.title,
        body: notification.body,
      },
      data: notification.data,
      android: {
        priority: 'high',
        notification: {
          channelId: notification.type,
          sound: 'default',
        },
      },
      apns: {
        payload: {
          aps: {
            sound: 'default',
            badge: 1,
          },
        },
      },
    });

    await prisma.notification.update({
      where: { id: notification.id },
      data: { sentAt: new Date(), status: 'sent' },
    });
  }

  private isDoNotDisturbTime(user: User): boolean {
    const now = new Date();
    const userTime = new Date(
      now.toLocaleString('en-US', { timeZone: user.timezone })
    );
    const hour = userTime.getHours();

    const dndStart = user.preferences?.dndStart || 22;
    const dndEnd = user.preferences?.dndEnd || 7;

    return hour >= dndStart || hour < dndEnd;
  }
}
```

## 7. Structure des Dossiers

```
dreamplanner/
├── apps/
│   ├── mobile/                    # Application React Native
│   │   ├── src/
│   │   │   ├── components/        # Composants réutilisables
│   │   │   ├── screens/           # Écrans de l'app
│   │   │   ├── navigation/        # Configuration navigation
│   │   │   ├── services/          # Services API
│   │   │   ├── stores/            # État global (Zustand)
│   │   │   ├── hooks/             # Hooks personnalisés
│   │   │   ├── utils/             # Utilitaires
│   │   │   ├── types/             # Types TypeScript
│   │   │   └── theme/             # Thème et styles
│   │   ├── android/
│   │   ├── ios/
│   │   └── package.json
│   │
│   └── api/                       # Backend Node.js
│       ├── src/
│       │   ├── controllers/       # Controllers API
│       │   ├── services/          # Logique métier
│       │   ├── middleware/        # Middlewares
│       │   ├── routes/            # Routes Express
│       │   ├── validators/        # Validation Zod
│       │   └── utils/             # Utilitaires
│       ├── prisma/
│       │   └── schema.prisma
│       └── package.json
│
├── packages/
│   └── shared/                    # Code partagé
│       ├── types/                 # Types communs
│       └── constants/             # Constantes
│
├── docs/                          # Documentation
├── .github/                       # CI/CD
└── package.json                   # Monorepo config
```
