# TODO - Dreams App

## Completed

- [x] Models: Dream, Goal, Task, Obstacle
- [x] CRUD ViewSets for all models
- [x] OpenAI integration for analysis and generation
- [x] Plan generation with GPT-4
- [x] Vision board generation with DALL-E 3
- [x] 2-minute start system
- [x] Automatic progress calculation
- [x] Gamification integration (XP on completion)
- [x] Unit and integration tests
- [x] Serializers with validation

## Recently Completed

- [x] Add @extend_schema decorators for Swagger
- [x] XSS sanitization for text fields
- [x] **Dream sharing** - Allow sharing between users (SharedDream model + endpoints)
- [x] **Dream templates** - Pre-configured dreams by category (DreamTemplate model + viewset)
- [x] **PDF export** - Export a dream with its complete plan
- [x] **Milestone notifications** - Notifications at each important milestone
- [x] **Collaborative dreams** - Multiple users on the same dream (DreamCollaborator model)
- [x] **Custom tags** - Flexible tag system (DreamTag + M2M)
- [x] **Smart archive** - Automatic archiving of inactive dreams (Celery task)
- [x] **Dream duplication** - Copy an existing dream

## Planned - High Priority

- [ ] Add PUT /api/dreams/{id}/ usage in frontend (edit dream screen missing)
- [ ] Add manual goal creation endpoint in frontend (currently AI-only)
- [ ] Add manual task creation endpoint in frontend (currently AI-only)

## Planned - Low Priority

- [ ] **Advanced statistics** - Detailed progress charts
- [ ] **External calendar integration** - Google/Apple Calendar sync
- [ ] **Smart reminders** - AI to determine the best timing

## Known Bugs

- [ ] Progress can become out of sync if a task is deleted
- [ ] Streak may not update correctly on timezone change

## Technical Debt

- [ ] Refactor `update_progress()` into a dedicated service
- [ ] Add type hints to all methods
- [ ] Extract XP logic into a service
- [ ] Add missing docstrings
- [ ] Optimize N+1 queries in nested serializers

## Performance Optimizations

- [ ] Add Redis cache for progress statistics
- [ ] Implement pagination on tasks
- [ ] Add composite index for frequent queries
- [ ] Use select_related/prefetch_related systematically
