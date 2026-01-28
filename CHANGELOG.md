# Changelog

Toutes les modifications notables de ce projet seront documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Versionnement Sémantique](https://semver.org/lang/fr/).

## [1.0.0] - 2025-01-28

### Ajouté

#### Backend Django
- **Authentification Firebase** - Intégration complète avec Firebase Admin SDK
- **App Users** - Gestion des profils, préférences, tokens FCM
- **App Dreams** - CRUD complet pour rêves, objectifs, tâches, obstacles
- **App Conversations** - Chat en temps réel avec WebSocket et GPT-4
- **App Notifications** - Push notifications avec FCM et templates
- **App Calendar** - Vues calendrier et planification intelligente
- **Gamification** - Système XP, niveaux, badges, streaks
- **Dream Buddy** - Système de partenariat d'accountability

#### Intégrations
- OpenAI GPT-4 pour génération de plans et coaching
- DALL-E 3 pour génération de vision boards
- Firebase Cloud Messaging pour notifications push
- Redis pour cache et Celery broker
- PostgreSQL comme base de données principale

#### Documentation
- README complet avec instructions de setup
- Documentation technique d'architecture
- Spécifications des fonctionnalités
- Guide de contribution
- Guide de déploiement

#### Sécurité
- Authentification JWT via Firebase
- Rate limiting multi-tier
- Validation des entrées avec Zod/Django validators
- Protection CORS
- Headers de sécurité avec Helmet

#### Tests
- Tests unitaires pour tous les modèles
- Tests d'intégration pour les API endpoints
- Tests WebSocket pour le chat en temps réel
- Configuration pytest avec fixtures réutilisables
- Couverture de code > 80%

### Infrastructure
- Docker et Docker Compose pour développement local
- Configuration production pour Railway/AWS
- CI/CD avec GitHub Actions
- Monitoring avec Sentry

## [0.1.0] - 2024-12-01

### Ajouté
- Structure initiale du projet
- Configuration monorepo avec apps/api et apps/mobile
- Schéma de base de données initial
- Prototypes d'écrans mobile

---

## Types de Changements

- `Ajouté` pour les nouvelles fonctionnalités
- `Modifié` pour les changements dans les fonctionnalités existantes
- `Déprécié` pour les fonctionnalités qui seront supprimées prochainement
- `Supprimé` pour les fonctionnalités supprimées
- `Corrigé` pour les corrections de bugs
- `Sécurité` pour les vulnérabilités corrigées
