# TODO - Dreams App

## Completed

- [x] Models: Dream, Goal, Task, Obstacle
- [x] CRUD ViewSets pour tous les models
- [x] Integration OpenAI pour analyse et generation
- [x] Generation de plans avec GPT-4
- [x] Generation de vision boards avec DALL-E 3
- [x] Systeme 2-minute start
- [x] Calcul automatique de progression
- [x] Integration gamification (XP sur completion)
- [x] Tests unitaires et d'integration
- [x] Serializers avec validation

## Recently Completed

- [x] Ajouter decorateurs @extend_schema pour Swagger
- [x] Sanitization XSS des champs texte

## Planned - High Priority

- [ ] **Partage de reves** - Permettre le partage entre utilisateurs
- [ ] **Templates de reves** - Reves pre-configures par categorie
- [ ] **Export PDF** - Exporter un reve avec son plan complet
- [ ] **Milestone notifications** - Notifications a chaque etape importante

## Planned - Medium Priority

- [ ] **Reves collaboratifs** - Plusieurs utilisateurs sur un meme reve
- [ ] **Tags personnalises** - Systeme de tags flexibles
- [ ] **Archive intelligente** - Archivage automatique des reves inactifs
- [ ] **Duplication de reves** - Copier un reve existant

## Planned - Low Priority

- [ ] **Statistiques avancees** - Graphiques de progression detailles
- [ ] **Integration calendrier externe** - Sync Google/Apple Calendar
- [ ] **Rappels intelligents** - IA pour determiner le meilleur moment

## Known Bugs

- [ ] La progression peut etre desynchronisee si une tache est supprimee
- [ ] Le streak peut ne pas se mettre a jour correctement au changement de timezone

## Technical Debt

- [ ] Refactorer `update_progress()` en service dedie
- [ ] Ajouter type hints a toutes les methodes
- [ ] Extraire la logique XP dans un service
- [ ] Ajouter docstrings manquants
- [ ] Optimiser les requetes N+1 dans les serializers imbriques

## Performance Optimizations

- [ ] Ajouter cache Redis pour les statistiques de progression
- [ ] Implementer pagination sur les taches
- [ ] Ajouter index composite pour les requetes frequentes
- [ ] Utiliser select_related/prefetch_related systematiquement
