# Changelog

Toutes les modifications notables de ce projet seront documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Versionnement Sémantique](https://semver.org/lang/fr/).

## [1.1.0] - 2026-02-22

### Added
- **3-Channel Notification Delivery**: WebSocket (real-time), Email, and Web Push (VAPID) notification channels with per-user preference toggles
- **NotificationConsumer**: WebSocket consumer for real-time notification delivery, mark-read, and unread count updates
- **NotificationDeliveryService**: Unified service dispatching notifications across all 3 channels with DND support
- **WebPushSubscription model**: Browser push subscription management with VAPID key support
- **NotificationBatch model**: Batch notification tracking with success rate analytics
- **Notification engagement tracking**: `opened_at` field and `/opened/` action for delivery analytics
- **Notification grouping**: `/grouped/` endpoint to view notifications by type
- **AI Validators**: Pydantic validation schemas for all AI-generated responses (`core/ai_validators.py`)
- **XSS Sanitization**: `core/sanitizers.py` with bleach-based HTML sanitization for all user-facing content

### Tests
- **Circles test suite**: 165 tests covering models, views, serializers, admin, invitation flows, challenge actions
- **Social test suite**: 159 tests covering friendship lifecycle, follows, blocking, reporting, activity feed, user search, follow suggestions
- **Buddies test suite**: 72 tests covering pairing, encouragement, streaks, progress comparison, history
- **Notification test suite expanded**: 45+ new tests for WebSocket consumer, delivery service, Web Push, batch serializer
- **AI validators test suite**: 80+ tests covering all Pydantic schemas, validation functions, coherence checker
- **Coverage target raised**: 80% → 99%

### Fixed
- Fixed broken `conftest.py` imports (`DreamBuddy` model removed, replaced with `BuddyPairing`)
- Fixed `core/tests.py` import names (`liveness` → `liveness_check`, `readiness` → `readiness_check`)
- Fixed notification test assertions using French strings instead of English
- Removed root `__init__.py` that caused Django app discovery errors

---

## [1.0.0] - 2025-01-28

### Ajouté

#### Backend Django
- **App Users** - Gestion des profils, préférences
- **App Dreams** - CRUD complet pour rêves, objectifs, tâches, obstacles
- **App Conversations** - Chat en temps réel avec WebSocket et GPT-4
- **App Notifications** - Push notifications et templates
- **App Calendar** - Vues calendrier et planification intelligente
- **Gamification** - Système XP, niveaux, badges, streaks
- **Dream Buddy** - Système de partenariat d'accountability

#### Intégrations
- OpenAI GPT-4 pour génération de plans et coaching
- DALL-E 3 pour génération de vision boards
- Redis pour cache et Celery broker
- PostgreSQL comme base de données principale

#### Documentation
- README complet avec instructions de setup
- Documentation technique d'architecture
- Spécifications des fonctionnalités
- Guide de contribution
- Guide de déploiement

#### Sécurité
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
- Structure initiale du projet Django
- Schéma de base de données initial

---

## Types de Changements

- `Ajouté` pour les nouvelles fonctionnalités
- `Modifié` pour les changements dans les fonctionnalités existantes
- `Déprécié` pour les fonctionnalités qui seront supprimées prochainement
- `Supprimé` pour les fonctionnalités supprimées
- `Corrigé` pour les corrections de bugs
- `Sécurité` pour les vulnérabilités corrigées
