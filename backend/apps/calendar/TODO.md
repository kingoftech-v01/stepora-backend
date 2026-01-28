# TODO - Calendar App

## Completed

- [x] Models: CalendarEvent, TimeBlock
- [x] API REST complete
- [x] Filtrage par date et plage
- [x] Vues today/week/overdue
- [x] Auto-scheduling basic
- [x] Integration avec Tasks
- [x] Tests unitaires

## Recently Completed

- [x] Ajouter decorateurs @extend_schema pour Swagger
- [x] Sanitization XSS des champs texte

## Planned - High Priority

- [ ] **Drag & drop reschedule** - Support API pour reorganisation
- [ ] **Conflits detection** - Detecter les chevauchements
- [ ] **Recurring events** - Evenements recurrents natifs
- [ ] **Smart suggestions** - Suggestions de creneaux optimaux

## Planned - Medium Priority

- [ ] **Google Calendar sync** - Synchronisation bidirectionnelle
- [ ] **Apple Calendar sync** - Integration iCal
- [ ] **Time zone handling** - Meilleure gestion des fuseaux
- [ ] **Buffer time** - Temps de transition entre taches

## Planned - Low Priority

- [ ] **Calendar sharing** - Partager son calendrier
- [ ] **Team calendars** - Calendriers d'equipe
- [ ] **Availability API** - API pour trouver des creneaux libres
- [ ] **Calendar export** - Export iCal/ICS

## Known Bugs

- [ ] L'auto-schedule peut creer des chevauchements dans certains cas
- [ ] Les evenements a cheval sur minuit ne sont pas bien geres
- [ ] Le reschedule ne met pas a jour la tache associee

## Technical Debt

- [ ] Refactorer l'algorithme de scheduling
- [ ] Ajouter type hints
- [ ] Extraire la logique de planning dans un service
- [ ] Ajouter validation des plages horaires
- [ ] Gerer les edge cases de timezone

## Performance Optimizations

- [ ] Index composite sur (user, start_time)
- [ ] Cache des TimeBlocks (rarement modifies)
- [ ] Pagination pour les vues longues periodes
- [ ] Optimiser les requetes de disponibilite
