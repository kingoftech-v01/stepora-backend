# Fonctionnalités Prioritaires - DreamPlanner 2.0

## Matrice de Priorisation

```
                        IMPACT ÉLEVÉ
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         │  QUICK WINS      │   BIG BETS       │
         │                  │                  │
         │  • 2-Min Start   │  • Dream Buddy   │
         │  • Micro-Wins    │  • AI Coach Pro  │
         │  • Streak Ins.   │  • Dream Circles │
         │                  │  • Vision Board  │
EFFORT   │                  │                  │
FAIBLE ──┼──────────────────┼──────────────────┼── EFFORT ÉLEVÉ
         │                  │                  │
         │  FILL-INS        │   MONEY PITS     │
         │                  │                  │
         │  • Themes        │  • Voice AI      │
         │  • Avatars       │  • AR Features   │
         │                  │  • Watch App     │
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                        IMPACT FAIBLE
```

---

## Phase 1: MVP+ (Semaines 1-4)

### P1.1 - "2-Minute Start"

**User Story**: En tant qu'utilisateur, je veux qu'on me propose une première action simple de 2 minutes pour que je puisse commencer immédiatement sans réfléchir.

**Acceptance Criteria**:
- [ ] L'IA génère automatiquement une micro-tâche de démarrage
- [ ] La tâche est affichée immédiatement après la création d'un objectif
- [ ] Timer visuel de 2 minutes
- [ ] Célébration après complétion
- [ ] Transition vers la prochaine étape

**Implémentation**:
```typescript
// Exemple de prompt IA pour générer le 2-minute start
const MICRO_START_PROMPT = `
Pour cet objectif: {objective}

Génère UNE SEULE action qui:
1. Prend MAXIMUM 2 minutes
2. Ne nécessite aucune préparation
3. Peut être faite MAINTENANT
4. Crée un premier engagement

Format: { action: string, duration: "30s" | "1min" | "2min", why: string }
`;
```

**Effort**: 3 jours
**Impact**: Très élevé (réduit l'abandon initial de 60%)

---

### P1.2 - "Rescue Mode" (Détection d'abandon)

**User Story**: En tant qu'utilisateur qui a arrêté de faire mes tâches, je veux être contacté gentiment pour comprendre ce qui bloque et recevoir de l'aide adaptée.

**Acceptance Criteria**:
- [ ] Détection après 3 jours d'inactivité
- [ ] Notification empathique (pas culpabilisante)
- [ ] Questionnaire rapide (4 options max)
- [ ] Réponse adaptée selon la raison
- [ ] Proposition de plan adapté

**Logique de détection**:
```typescript
interface AbandonSignals {
  daysSinceLastActivity: number;
  missedTasksStreak: number;
  appOpenWithoutAction: number;
  previousAbandonPatterns: boolean;
}

function shouldTriggerRescue(signals: AbandonSignals): boolean {
  return (
    signals.daysSinceLastActivity >= 3 ||
    signals.missedTasksStreak >= 5 ||
    (signals.appOpenWithoutAction >= 3 && signals.previousAbandonPatterns)
  );
}
```

**Effort**: 5 jours
**Impact**: Très élevé (récupère 40% des abandons)

---

### P1.3 - "Micro-Wins" Celebrations

**User Story**: En tant qu'utilisateur, je veux que mes petits progrès soient célébrés pour rester motivé.

**Acceptance Criteria**:
- [ ] Animation de célébration pour chaque tâche
- [ ] Célébration spéciale pour les milestones (3, 7, 14, 30 jours)
- [ ] Comparaison positive ("Tu fais mieux que 80%...")
- [ ] Option de partage social
- [ ] Son et vibration (optionnels)

**Milestones à célébrer**:
```typescript
const MILESTONES = [
  { days: 1, badge: "Premier Pas", message: "Le plus dur est fait!" },
  { days: 3, badge: "Momentum", message: "Tu construis une habitude!" },
  { days: 7, badge: "Semaine Parfaite", message: "Une semaine complète!" },
  { days: 14, badge: "Déterminé", message: "2 semaines, c'est sérieux!" },
  { days: 30, badge: "Unstoppable", message: "Un mois! Tu es incroyable!" },
  { days: 60, badge: "Habitude Ancrée", message: "C'est devenu naturel!" },
  { days: 100, badge: "Centurion", message: "100 jours légendaires!" },
];
```

**Effort**: 4 jours
**Impact**: Élevé (augmente rétention de 35%)

---

## Phase 2: Social (Semaines 5-8)

### P2.1 - "Dream Buddy" System

**User Story**: En tant qu'utilisateur, je veux être connecté avec quelqu'un qui a le même objectif pour qu'on se motive mutuellement.

**Acceptance Criteria**:
- [ ] Matching basé sur: objectif similaire, timezone, langue
- [ ] Profil limité (prénom, avatar, objectif, progression)
- [ ] Chat intégré
- [ ] Notifications mutuelles ("Ton buddy a complété sa tâche!")
- [ ] Option de changer de buddy
- [ ] Rapport de comportement toxique

**Algorithme de matching**:
```typescript
interface MatchingCriteria {
  objectiveCategory: string;      // Poids: 40%
  targetTimeframe: DateRange;     // Poids: 20%
  timezone: string;               // Poids: 15%
  language: string;               // Poids: 15%
  activityLevel: 'low' | 'medium' | 'high'; // Poids: 10%
}

function calculateMatchScore(user1: User, user2: User): number {
  // Retourne un score de 0 à 100
}
```

**Effort**: 2 semaines
**Impact**: Très élevé (rétention x2 avec buddy actif)

---

### P2.2 - "Public Commitment"

**User Story**: En tant qu'utilisateur, je veux pouvoir annoncer publiquement mon objectif pour créer de la responsabilité sociale.

**Acceptance Criteria**:
- [ ] Création d'un "engagement" avec date limite
- [ ] Partage sur réseaux sociaux (template design)
- [ ] Inviter des "témoins" (amis)
- [ ] Notifications aux témoins sur la progression
- [ ] Célébration publique si réussi
- [ ] Gestion discrète si échoué (pas de shame)

**Effort**: 1 semaine
**Impact**: Élevé (engagement +50%)

---

### P2.3 - Gamification "Life RPG"

**User Story**: En tant qu'utilisateur, je veux que ma progression ressemble à un jeu pour que ce soit fun.

**Acceptance Criteria**:
- [ ] Avatar personnalisable
- [ ] Système de XP et niveaux
- [ ] Attributs par domaine de vie
- [ ] Badges et achievements
- [ ] Récompenses débloquables (thèmes, avatars)
- [ ] Quêtes spéciales limitées dans le temps

**Système d'XP**:
```typescript
const XP_REWARDS = {
  taskCompleted: 10,
  dailyGoalMet: 25,
  streakDay: 5 * streakLength, // Bonus progressif
  milestoneReached: 100,
  buddyHelped: 15,
  challengeCompleted: 50,
};

const LEVELS = [
  { level: 1, xpRequired: 0, title: "Rêveur" },
  { level: 5, xpRequired: 500, title: "Planificateur" },
  { level: 10, xpRequired: 1500, title: "Achiever" },
  { level: 20, xpRequired: 5000, title: "Dream Warrior" },
  { level: 50, xpRequired: 25000, title: "Légende" },
];
```

**Effort**: 2 semaines
**Impact**: Élevé (engagement quotidien +40%)

---

## Phase 3: AI Avancée (Semaines 9-12)

### P3.1 - "Proactive AI Coach"

**User Story**: En tant qu'utilisateur, je veux que l'IA anticipe mes difficultés et me propose des solutions avant que j'abandonne.

**Acceptance Criteria**:
- [ ] Analyse des patterns personnels
- [ ] Intégration calendrier (Google/Apple)
- [ ] Prédiction des semaines à risque
- [ ] Suggestions proactives d'adaptation
- [ ] Apprentissage continu des préférences

**Données analysées**:
```typescript
interface UserPatterns {
  // Temporel
  bestDaysOfWeek: number[];
  bestTimeOfDay: string;
  worstDaysOfWeek: number[];

  // Comportemental
  averageSessionLength: number;
  abandonTriggers: string[];
  motivationPeaks: string[];

  // Contextuel
  calendarBusyDays: Date[];
  stressIndicators: string[];
}
```

**Effort**: 3 semaines
**Impact**: Très élevé (réduit abandon de 50%)

---

### P3.2 - "Vision Board" avec IA Générative

**User Story**: En tant qu'utilisateur, je veux visualiser mon objectif accompli avec une image générée par IA pour rester motivé.

**Acceptance Criteria**:
- [ ] Génération d'image basée sur l'objectif
- [ ] Personnalisation (ton visage si permis)
- [ ] Option fond d'écran
- [ ] Rappel quotidien avec l'image
- [ ] Évolution de l'image selon progression

**Prompt engineering**:
```typescript
const VISION_PROMPT = `
Create an inspiring, realistic image of:
{user_description} achieving their goal of {objective}

Style: Warm, aspirational, photorealistic
Mood: Triumphant, happy, accomplished
Setting: {relevant_context}

Important: Make it feel achievable, not fantasy
`;
```

**Effort**: 2 semaines
**Impact**: Moyen-Élevé (motivation +30%)

---

## Phase 4: Viralité (Semaines 13-16)

### P4.1 - "Dream Circles" (Groupes)

**User Story**: En tant qu'utilisateur, je veux rejoindre un petit groupe de personnes avec le même objectif pour partager notre parcours.

**Acceptance Criteria**:
- [ ] Groupes de 5-10 personnes max
- [ ] Création manuelle ou matching auto
- [ ] Défis de groupe hebdomadaires
- [ ] Feed d'activité du groupe
- [ ] Classement amical
- [ ] Appels vidéo optionnels
- [ ] Modération IA

**Effort**: 3 semaines
**Impact**: Très élevé (rétention x3, viralité élevée)

---

### P4.2 - Partage Social Optimisé

**User Story**: En tant qu'utilisateur, je veux pouvoir partager mes victoires sur les réseaux avec un design professionnel automatique.

**Acceptance Criteria**:
- [ ] Templates Instagram Story
- [ ] Templates TikTok
- [ ] Personnalisation couleurs/style
- [ ] Inclusion automatique des stats
- [ ] Hashtags suggérés
- [ ] Deep link vers l'app

**Templates à créer**:
- Streak milestone (7, 14, 30 jours)
- Objectif complété
- Nouveau défi lancé
- Badge débloqué
- Comparaison avant/après

**Effort**: 1 semaine
**Impact**: Très élevé (acquisition virale)

---

## Récapitulatif du Planning

| Phase | Semaines | Fonctionnalités | Impact Clé |
|-------|----------|-----------------|------------|
| **MVP+** | 1-4 | 2-Min Start, Rescue Mode, Micro-Wins | Réduire abandon initial |
| **Social** | 5-8 | Dream Buddy, Commitment, Gamification | Créer engagement social |
| **AI+** | 9-12 | Proactive Coach, Vision Board | Prévenir abandon |
| **Viral** | 13-16 | Dream Circles, Social Sharing | Croissance organique |

---

## Métriques de Succès

### North Star Metric
**WAU (Weekly Active Users) qui complètent au moins 1 tâche**

### Métriques Secondaires

| Métrique | Cible MVP | Cible 6 mois |
|----------|-----------|--------------|
| D1 Retention | 60% | 70% |
| D7 Retention | 35% | 50% |
| D30 Retention | 15% | 30% |
| Buddy Match Rate | - | 40% |
| Viral Coefficient | - | 1.2 |
| Goal Completion Rate | 10% | 25% |
| NPS | 30 | 50 |
