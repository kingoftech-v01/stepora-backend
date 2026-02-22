# Politique de Sécurité

## Versions Supportées

| Version | Supportée          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Signaler une Vulnérabilité

Nous prenons la sécurité de DreamPlanner très au sérieux. Si vous découvrez une vulnérabilité de sécurité, merci de nous la signaler de manière responsable.

### Comment Signaler

1. **Ne pas** créer d'issue publique sur GitHub
2. Envoyez un email à **security@dreamplanner.example.com** avec :
   - Description détaillée de la vulnérabilité
   - Étapes pour reproduire le problème
   - Impact potentiel
   - Suggestions de correction (si possible)

### Ce à quoi s'attendre

- **Accusé de réception** : Dans les 48 heures
- **Évaluation initiale** : Dans les 7 jours
- **Résolution** : Selon la sévérité (critique: 7 jours, haute: 14 jours, moyenne: 30 jours)

### Portée

Les vulnérabilités suivantes sont dans notre portée :

- Injection SQL
- Cross-Site Scripting (XSS)
- Cross-Site Request Forgery (CSRF)
- Authentification/Autorisation cassée
- Exposition de données sensibles
- Mauvaise configuration de sécurité
- Composants avec vulnérabilités connues

### Hors Portée

- Attaques par déni de service (DoS)
- Spam ou ingénierie sociale
- Problèmes sur des systèmes que nous ne contrôlons pas

## Mesures de Sécurité Implémentées

### Authentification
- Tokens avec expiration courte
- Refresh tokens sécurisés

### Autorisation
- Vérification de propriété sur toutes les ressources
- Permissions basées sur les rôles
- Rate limiting par utilisateur et IP

### Protection des Données
- Chiffrement en transit (HTTPS/TLS)
- Sanitization des entrées utilisateur
- Validation avec Zod schemas
- Protection CORS configurée

### Infrastructure
- Headers de sécurité (Helmet.js)
- Protection CSRF
- Logging et monitoring avec Sentry

## Bonnes Pratiques pour les Contributeurs

1. Ne jamais commiter de secrets ou credentials
2. Utiliser des variables d'environnement
3. Valider toutes les entrées utilisateur
4. Utiliser des requêtes paramétrées (Prisma/Django ORM)
5. Suivre le principe du moindre privilège

## Reconnaissance

Nous remercions tous les chercheurs en sécurité qui nous aident à améliorer DreamPlanner.
