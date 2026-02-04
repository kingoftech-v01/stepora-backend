# DreamPlanner

**Transformez vos rêves en réalité**

Application mobile cross-platform (iOS & Android) qui utilise l'intelligence artificielle de ChatGPT pour aider les utilisateurs à planifier et atteindre leurs objectifs.

---

## Screenshots

<p align="center">
  <img src="./assets/screenshots/01-chat-screen.svg" width="200" alt="Chat Screen" />
  <img src="./assets/screenshots/02-dreams-dashboard.svg" width="200" alt="Dreams Dashboard" />
  <img src="./assets/screenshots/03-calendar-screen.svg" width="200" alt="Calendar Screen" />
  <img src="./assets/screenshots/04-profile-screen.svg" width="200" alt="Profile Screen" />
</p>

<p align="center">
  <em>Chat IA &nbsp;•&nbsp; Dashboard &nbsp;•&nbsp; Calendrier &nbsp;•&nbsp; Profil</em>
</p>

---

## Fonctionnalités

| Feature | Description |
|---------|-------------|
| **Conversation IA** | Discutez naturellement de vos rêves et objectifs |
| **Planification intelligente** | Génération automatique d'un calendrier personnalisé |
| **Gestion du temps** | Respect de vos horaires de travail et temps de repos |
| **Notifications** | Rappels au bon moment pour rester sur la bonne voie |
| **Suivi de progression** | Visualisez votre avancement et célébrez vos victoires |
| **Dream Buddy** | Système de partenariat pour se motiver mutuellement |
| **Gamification** | XP, niveaux, badges pour rendre l'expérience ludique |
| **Rescue Mode** | Détection d'abandon et intervention proactive de l'IA |

## Le Problème Résolu

```
    ENTHOUSIASME  →  CONFUSION  →  DÉCOURAGEMENT  →  ABANDON
         ↑                                              |
         └──────────── DreamPlanner intervient ←────────┘
```

**73% des personnes** abandonnent leurs objectifs. DreamPlanner utilise l'IA pour:
- Clarifier et décomposer les objectifs vagues
- Créer un plan réaliste adapté à votre vie
- Vous accompagner avec des rappels intelligents
- Détecter les signes d'abandon et intervenir

---

## Structure du Projet

```
dreamplanner/
├── apps/
│   ├── mobile/          # Application React Native (iOS/Android)
│   └── api/             # Backend Node.js/Express
├── packages/
│   └── shared/          # Code partagé (types, constantes)
├── assets/
│   └── screenshots/     # Mockups de l'application
└── docs/                # Documentation du projet
```

## Documentation

| Document | Description |
|----------|-------------|
| [PROJECT_OVERVIEW.md](./docs/PROJECT_OVERVIEW.md) | Vision, fonctionnalités et modèle économique |
| [TECHNICAL_ARCHITECTURE.md](./docs/TECHNICAL_ARCHITECTURE.md) | Architecture système et base de données |
| [FEATURES_SPECIFICATIONS.md](./docs/FEATURES_SPECIFICATIONS.md) | Wireframes et spécifications UI/UX |
| [UI_DESIGN_SYSTEM.md](./docs/UI_DESIGN_SYSTEM.md) | Couleurs, typographie et composants |
| [DEVELOPMENT_ROADMAP.md](./docs/DEVELOPMENT_ROADMAP.md) | Plan de développement sur 18 semaines |
| [IMPROVEMENTS_STRATEGY.md](./docs/IMPROVEMENTS_STRATEGY.md) | Stratégie d'amélioration et différenciation |
| [PRIORITY_FEATURES.md](./docs/PRIORITY_FEATURES.md) | Fonctionnalités prioritaires et user stories |
| [TESTING_STRATEGY.md](./docs/TESTING_STRATEGY.md) | Stratégie de tests complète |

---

## Stack Technique

### Mobile
| Technology | Usage |
|------------|-------|
| React Native 0.73+ | Framework cross-platform |
| TypeScript | Typage statique |
| Zustand | State management |
| React Navigation | Navigation |
| React Native Paper | UI Components |
| React Query | Data fetching |

### Backend
| Technology | Usage |
|------------|-------|
| Node.js 20 LTS | Runtime |
| Express.js | Web framework |
| TypeScript | Typage statique |
| Prisma | ORM |
| PostgreSQL | Base de données |
| Redis | Cache & queues |

### Services
| Service | Usage |
|---------|-------|
| OpenAI GPT-4 | Intelligence artificielle |
| Firebase | Auth & Push Notifications |
| AWS | Hosting & Infrastructure |

---

## Tests

### Pyramide de Tests

```
              /\
             /  \        E2E (Detox) - 10%
            /────\       Parcours critiques
           /      \
          /        \     Integration - 30%
         /──────────\    API + Components
        /            \
       /              \  Unit Tests - 60%
      /________________\ Jest/Vitest
```

### Exécuter les Tests

```bash
# Tests unitaires
yarn test

# Tests avec couverture
yarn test --coverage

# Tests E2E iOS
yarn mobile e2e:ios

# Tests E2E Android
yarn mobile e2e:android

# Tests de charge
yarn api test:load
```

### Couverture Cible

| Module | Minimum | Idéal |
|--------|---------|-------|
| Services Backend | 80% | 90% |
| Stores Mobile | 85% | 95% |
| Utils | 90% | 95% |
| Components | 60% | 75% |

---

## Démarrage Rapide

### Prérequis

- Node.js 20+
- Yarn 1.22+
- PostgreSQL 15+
- Redis 7+
- Xcode (pour iOS)
- Android Studio (pour Android)

### Installation

```bash
# Cloner le repository
git clone https://github.com/your-org/dreamplanner.git
cd dreamplanner

# Installer les dépendances
yarn install

# Configurer les variables d'environnement
cp apps/api/.env.example apps/api/.env
# Éditer .env avec vos valeurs

# Initialiser la base de données
yarn api db:push

# Lancer le backend
yarn dev:api

# Lancer l'app mobile (dans un autre terminal)
yarn dev:mobile
```

### Variables d'Environnement

```env
# Database
DATABASE_URL="postgresql://user:password@localhost:5432/dreamplanner"

# Redis
REDIS_URL="redis://localhost:6379"

# OpenAI
OPENAI_API_KEY="sk-..."

# Firebase
FIREBASE_PROJECT_ID="..."
FIREBASE_PRIVATE_KEY="..."
FIREBASE_CLIENT_EMAIL="..."

# App
NODE_ENV="development"
PORT=3000
CORS_ORIGIN="*"
```

---

## Scripts Disponibles

```bash
# Développement
yarn dev:api          # Lance le backend en mode dev
yarn dev:mobile       # Lance Metro bundler

# Build
yarn build:api            # Build le backend
yarn build:mobile:ios     # Build iOS
yarn build:mobile:android # Build Android

# Tests
yarn test             # Lance tous les tests
yarn test --coverage  # Tests avec couverture
yarn lint             # Lint le code
yarn typecheck        # Vérifie les types TypeScript

# Base de données
yarn api db:generate  # Génère le client Prisma
yarn api db:push      # Push le schema vers la DB
yarn api db:migrate   # Crée une migration
yarn api db:studio    # Ouvre Prisma Studio
```

---

## Roadmap

### Phase 1: MVP (Semaines 1-8)
- [x] Documentation et planification
- [ ] Setup infrastructure
- [ ] Chat IA basique
- [ ] Calendrier et tâches

### Phase 2: Notifications (Semaines 9-12)
- [ ] Push notifications
- [ ] Rappels intelligents
- [ ] Mode "Ne pas déranger"

### Phase 3: Social (Semaines 13-16)
- [ ] Dream Buddy system
- [ ] Gamification (XP, badges)
- [ ] Partage social

### Phase 4: Launch (Semaines 17-18)
- [ ] Beta testing
- [ ] App Store / Play Store
- [ ] Marketing

---

## Contribution

1. Fork le projet
2. Créer une branche (`git checkout -b feature/amazing-feature`)
3. Commit les changements (`git commit -m 'Add amazing feature'`)
4. Push la branche (`git push origin feature/amazing-feature`)
5. Ouvrir une Pull Request

### Guidelines

- Suivre le [Design System](./docs/UI_DESIGN_SYSTEM.md)
- Écrire des tests pour les nouvelles fonctionnalités
- Respecter la couverture de code minimale
- Documenter les changements significatifs

---

## Licence

Propriétaire - Tous droits réservés

---

<p align="center">
  <strong>DreamPlanner</strong> - Tes rêves méritent un plan
</p>
