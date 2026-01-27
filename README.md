# DreamPlanner

**Transformez vos rêves en réalité**

Application mobile cross-platform (iOS & Android) qui utilise l'intelligence artificielle de ChatGPT pour aider les utilisateurs à planifier et atteindre leurs objectifs.

## Fonctionnalités

- **Conversation IA** - Discutez naturellement de vos rêves et objectifs
- **Planification intelligente** - Génération automatique d'un calendrier personnalisé
- **Gestion du temps** - Respect de vos horaires de travail et temps de repos
- **Notifications** - Rappels au bon moment pour rester sur la bonne voie
- **Suivi de progression** - Visualisez votre avancement et célébrez vos victoires

## Structure du Projet

```
dreamplanner/
├── apps/
│   ├── mobile/          # Application React Native (iOS/Android)
│   └── api/             # Backend Node.js/Express
├── packages/
│   └── shared/          # Code partagé (types, constantes)
└── docs/                # Documentation du projet
```

## Documentation

- [Vue d'ensemble du projet](./docs/PROJECT_OVERVIEW.md)
- [Architecture technique](./docs/TECHNICAL_ARCHITECTURE.md)
- [Spécifications fonctionnelles](./docs/FEATURES_SPECIFICATIONS.md)
- [Design System UI/UX](./docs/UI_DESIGN_SYSTEM.md)
- [Roadmap de développement](./docs/DEVELOPMENT_ROADMAP.md)

## Stack Technique

### Mobile
- React Native 0.73+
- TypeScript
- Zustand (State management)
- React Navigation
- React Native Paper (UI)
- React Query

### Backend
- Node.js 20 LTS
- Express.js
- TypeScript
- Prisma (ORM)
- PostgreSQL
- Redis

### Services
- OpenAI GPT-4 (IA)
- Firebase (Auth, Push Notifications)
- AWS (Hosting)

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

## Scripts Disponibles

```bash
# Développement
yarn dev:api          # Lance le backend en mode dev
yarn dev:mobile       # Lance Metro bundler

# Build
yarn build:api        # Build le backend
yarn build:mobile:ios     # Build iOS
yarn build:mobile:android # Build Android

# Tests
yarn test             # Lance tous les tests
yarn lint             # Lint le code
yarn typecheck        # Vérifie les types TypeScript

# Base de données
yarn api db:generate  # Génère le client Prisma
yarn api db:push      # Push le schema vers la DB
yarn api db:migrate   # Crée une migration
yarn api db:studio    # Ouvre Prisma Studio
```

## Contribution

1. Fork le projet
2. Créer une branche (`git checkout -b feature/amazing-feature`)
3. Commit les changements (`git commit -m 'Add amazing feature'`)
4. Push la branche (`git push origin feature/amazing-feature`)
5. Ouvrir une Pull Request

## Licence

Propriétaire - Tous droits réservés
