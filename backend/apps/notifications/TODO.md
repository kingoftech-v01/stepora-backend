# TODO - Notifications App

## Completed

- [x] Models: Notification, NotificationTemplate, NotificationBatch
- [x] Integration Firebase Cloud Messaging
- [x] Systeme de templates avec variables
- [x] Support Do Not Disturb (DND)
- [x] Celery tasks pour envoi automatique
- [x] API REST complete
- [x] Retry logic sur echec d'envoi
- [x] Tests unitaires

## In Progress

- [ ] Ajouter decorateurs @extend_schema pour Swagger

## Planned - High Priority

- [ ] **Notification preferences granulaires** - Par type de notification
- [ ] **Rich notifications** - Images et actions dans les notifications
- [ ] **Notification channels** - Canaux Android distincts
- [ ] **Analytics** - Tracking des taux d'ouverture

## Planned - Medium Priority

- [ ] **Email fallback** - Email si push echoue
- [ ] **In-app notifications** - Centre de notifications dans l'app
- [ ] **Notification grouping** - Regrouper les notifications similaires
- [ ] **A/B testing** - Tester differents messages

## Planned - Low Priority

- [ ] **SMS notifications** - Pour les rappels critiques
- [ ] **Webhook notifications** - Pour integrations tierces
- [ ] **Notification scheduling UI** - Interface admin avancee

## Known Bugs

- [ ] Les tokens FCM expires ne sont pas nettoyes automatiquement
- [ ] Le DND peut avoir des problemes aux changements d'heure ete/hiver
- [ ] Les batch de plus de 500 ne sont pas geres

## Technical Debt

- [ ] Refactorer FCM service en classe
- [ ] Ajouter type hints
- [ ] Implementer circuit breaker pour Firebase
- [ ] Centraliser la gestion des erreurs FCM
- [ ] Ajouter metriques Prometheus

## Performance Optimizations

- [ ] Batch processing pour gros volumes
- [ ] Queue prioritaire pour notifications urgentes
- [ ] Cache des templates frequemment utilises
- [ ] Index sur scheduled_for pour les requetes
