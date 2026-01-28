# TODO - Conversations App

## Completed

- [x] Models: Conversation, Message, ConversationSummary
- [x] REST API endpoints
- [x] WebSocket consumer avec streaming
- [x] Integration GPT-4
- [x] System prompts dynamiques par type
- [x] Rate limiting par tier
- [x] Tests unitaires et WebSocket
- [x] Gestion du contexte conversation

## In Progress

- [ ] Ajouter decorateurs @extend_schema pour Swagger
- [ ] Implementer authentification WebSocket Firebase
- [ ] Sanitization XSS du contenu des messages

## Planned - High Priority

- [ ] **Fonction calling** - Permettre a l'IA de creer des taches directement
- [ ] **Summarization automatique** - Resume des conversations longues
- [ ] **Context window management** - Gestion intelligente du contexte
- [ ] **Retry logic** - Gestion des erreurs OpenAI avec retry

## Planned - Medium Priority

- [ ] **Voice messages** - Support audio avec Whisper
- [ ] **Image analysis** - Analyser des images avec GPT-4V
- [ ] **Export conversations** - Exporter en PDF/JSON
- [ ] **Conversation templates** - Templates de coaching pre-definis

## Planned - Low Priority

- [ ] **Multi-language** - Support multilingue dynamique
- [ ] **Sentiment analysis** - Detecter l'humeur de l'utilisateur
- [ ] **Proactive messaging** - L'IA initie des conversations

## Known Bugs

- [ ] WebSocket peut perdre la connexion sans reconnexion automatique
- [ ] Le streaming peut se bloquer sur des reponses tres longues
- [ ] Les tokens ne sont pas comptes precisement pour le rate limiting

## Technical Debt

- [ ] Refactorer le consumer en classes plus petites
- [ ] Ajouter type hints
- [ ] Implementer circuit breaker pour OpenAI
- [ ] Centraliser la gestion des prompts
- [ ] Ajouter tests de charge pour WebSocket

## Performance Optimizations

- [ ] Cache Redis pour les prompts systeme
- [ ] Pagination des messages (actuellement limite a 20)
- [ ] Compression des messages archives
- [ ] Connection pooling pour WebSocket
