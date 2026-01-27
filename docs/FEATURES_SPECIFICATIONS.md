# Spécifications Fonctionnelles - DreamPlanner

## 1. Onboarding & Inscription

### 1.1 Écrans d'Onboarding (3 slides)

**Slide 1 - Bienvenue**
- Titre: "Transformez vos rêves en réalité"
- Description: "DreamPlanner utilise l'IA pour créer un plan personnalisé vers vos objectifs"
- Illustration: Personne atteignant un sommet

**Slide 2 - Comment ça marche**
- Titre: "Parlez, nous planifions"
- Description: "Décrivez votre rêve, nous créons un calendrier adapté à votre vie"
- Illustration: Chat avec IA + Calendrier

**Slide 3 - Restez motivé**
- Titre: "Ne perdez jamais le cap"
- Description: "Notifications intelligentes et suivi de progression pour rester sur la bonne voie"
- Illustration: Notifications + Graphique de progression

### 1.2 Inscription

**Options d'inscription:**
- Email + Mot de passe
- Google Sign-In
- Apple Sign-In (iOS)

**Informations collectées:**
1. Nom d'affichage
2. Email
3. Fuseau horaire (détection auto)

### 1.3 Configuration Initiale

**Étape 1 - Horaires de travail**
```
"Pour mieux planifier, dis-moi quand tu travailles"

[ ] Je ne travaille pas actuellement
[x] J'ai des horaires réguliers

Jours de travail: [L] [M] [M] [J] [V] [ ] [ ]
Heure début: [09:00]
Heure fin: [18:00]
```

**Étape 2 - Préférences de notifications**
```
"Comment veux-tu que je te rappelle tes tâches?"

Rappels avant une tâche: [15 minutes ▼]

Mode "Ne pas déranger":
De [22:00] à [07:00]

Types de notifications:
[x] Rappels de tâches
[x] Messages de motivation
[x] Progression hebdomadaire
[ ] Tips et conseils
```

**Étape 3 - Premier rêve**
```
"Quel est ton premier rêve ou objectif?"

[Entrée texte libre - suggestion: "Apprendre l'espagnol en 6 mois"]

ou

[Choisir une catégorie]
- 💼 Carrière
- 🏋️ Santé & Fitness
- 📚 Apprentissage
- 💰 Finances
- ✈️ Voyage
- 🎨 Créativité
- 🧘 Bien-être
```

---

## 2. Conversation avec l'IA (Écran Principal)

### 2.1 Interface de Chat

```
┌────────────────────────────────────────┐
│ ← DreamPlanner            [+] Nouveau  │
├────────────────────────────────────────┤
│                                        │
│   🤖 Bonjour Marie ! Je suis ravi de  │
│   t'accompagner vers tes rêves.       │
│                                        │
│   Parle-moi de ce que tu voudrais     │
│   accomplir. Quel est ton prochain    │
│   grand objectif ?                     │
│                                        │
│                        ┌──────────────┐│
│                        │ Je voudrais  ││
│                        │ apprendre à  ││
│                        │ jouer de la  ││
│                        │ guitare      ││
│                        └──────────────┘│
│                                        │
│   🤖 Super choix ! La guitare est un  │
│   instrument gratifiant.              │
│                                        │
│   Quelques questions pour mieux       │
│   planifier :                         │
│                                        │
│   1. As-tu déjà une guitare ?         │
│   2. Quel style veux-tu jouer ?       │
│   3. Combien de temps par jour peux-  │
│      tu consacrer à la pratique ?     │
│   4. As-tu une date cible en tête ?   │
│                                        │
├────────────────────────────────────────┤
│ [Message...                    ] [📤] │
│                                        │
│ Suggestions rapides:                   │
│ [Oui j'ai déjà une guitare]           │
│ [Je veux jouer du rock]               │
│ [30 min par jour]                     │
└────────────────────────────────────────┘
```

### 2.2 Génération du Plan

Après la conversation, l'IA génère un plan:

```
┌────────────────────────────────────────┐
│ 🎯 Ton Plan: Apprendre la Guitare     │
├────────────────────────────────────────┤
│                                        │
│ 📊 Analyse                             │
│ ──────────────────────────────────────│
│ Faisabilité: ████████░░ 80% Élevée    │
│ Durée estimée: 6 mois                  │
│ Temps requis: 3h30/semaine            │
│                                        │
│ 🎯 Étapes du parcours                  │
│ ──────────────────────────────────────│
│                                        │
│ ○ Semaines 1-2: Les bases             │
│   • Posture et position               │
│   • Accords de base (La, Ré, Mi)      │
│   • 30 min/jour                        │
│                                        │
│ ○ Semaines 3-4: Premiers morceaux     │
│   • Enchaînement d'accords            │
│   • Premier morceau simple            │
│   • 30 min/jour                        │
│                                        │
│ ○ Semaines 5-8: Rythme & Strumming    │
│   • Patterns de strumming             │
│   • Garder le tempo                   │
│   • 30 min/jour                        │
│                                        │
│ [Voir toutes les étapes ▼]            │
│                                        │
│ 💡 Conseils                            │
│ • Échauffer ses doigts avant          │
│ • Pratiquer avec un métronome         │
│ • Filmer sa progression               │
│                                        │
│ ⚠️ Obstacles potentiels               │
│ • Douleur aux doigts (normal!)        │
│ • Plateau de progression              │
│                                        │
├────────────────────────────────────────┤
│                                        │
│ [Modifier le plan]  [✓ Adopter ce plan]│
│                                        │
└────────────────────────────────────────┘
```

---

## 3. Calendrier

### 3.1 Vue Mensuelle

```
┌────────────────────────────────────────┐
│ ←  Janvier 2026  →                     │
├────────────────────────────────────────┤
│  L    M    M    J    V    S    D      │
│                 1    2    3    4      │
│       ○         ●    ○              │
│  5    6    7    8    9   10   11     │
│  ●    ●    ●    ●    ●              │
│ 12   13   14   15   16   17   18     │
│  ●    ●    ●    ●    ●              │
│ 19   20   21   22   23   24   25     │
│  ●    ●    ●    ●    ●              │
│ 26   27   28   29   30   31          │
│  ●    ●    ●    ●    ●              │
├────────────────────────────────────────┤
│ Légende: ● Tâche prévue  ○ Complétée  │
│          🔴 En retard                  │
└────────────────────────────────────────┘
```

### 3.2 Vue Journée

```
┌────────────────────────────────────────┐
│ ← Aujourd'hui, Lundi 27 Janvier →     │
├────────────────────────────────────────┤
│                                        │
│ 06:00  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│ 07:00  ████ Réveil & routine          │
│ 08:00  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│ 09:00  ▓▓▓▓▓▓▓▓▓▓▓▓ Travail          │
│ ...                                    │
│ 12:00  ████ Pause déjeuner            │
│ 13:00  ▓▓▓▓▓▓▓▓▓▓▓▓ Travail          │
│ ...                                    │
│ 18:00  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│ 18:30  ┌──────────────────────────┐   │
│        │ 🎸 Pratique guitare      │   │
│        │    30 min                │   │
│        │    Objectif: Bases       │   │
│        │ [Commencer] [Reporter]   │   │
│        └──────────────────────────┘   │
│ 19:00  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│ 19:30  ████ Dîner                     │
│ 20:00  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│                                        │
│ Légende: ▓▓ Travail  ██ Autre  ░░ Libre│
└────────────────────────────────────────┘
```

### 3.3 Vue Semaine

```
┌────────────────────────────────────────┐
│ ← Semaine du 27 Janvier →             │
├────────────────────────────────────────┤
│      L   M   M   J   V   S   D       │
│ 7h  ░░  ░░  ░░  ░░  ░░  ░░  ░░      │
│ 8h  ░░  ░░  ░░  ░░  ░░  ░░  ░░      │
│ 9h  ▓▓  ▓▓  ▓▓  ▓▓  ▓▓  ░░  ░░      │
│ ...      ...                          │
│18h  ░░  ░░  ░░  ░░  ░░  ░░  ░░      │
│18h30 🎸  🎸  🎸  🎸  🎸  ░░  ░░      │
│19h  ░░  ░░  ░░  ░░  ░░  🎸  ░░      │
│20h  ░░  ░░  ░░  ░░  ░░  ░░  ░░      │
├────────────────────────────────────────┤
│ Cette semaine: 5 tâches • 2h30 total  │
└────────────────────────────────────────┘
```

---

## 4. Mes Rêves (Dashboard)

### 4.1 Liste des Rêves

```
┌────────────────────────────────────────┐
│ Mes Rêves                    [+ Nouveau]│
├────────────────────────────────────────┤
│                                        │
│ 🔥 En cours                            │
│ ──────────────────────────────────────│
│ ┌──────────────────────────────────┐  │
│ │ 🎸 Apprendre la guitare          │  │
│ │ ████████░░░░░░░░ 35%             │  │
│ │ 📅 Objectif: Juin 2026           │  │
│ │ ⏰ Prochaine: Aujourd'hui 18h30  │  │
│ └──────────────────────────────────┘  │
│                                        │
│ ┌──────────────────────────────────┐  │
│ │ 🏃 Courir un marathon            │  │
│ │ ██░░░░░░░░░░░░░░ 12%             │  │
│ │ 📅 Objectif: Octobre 2026        │  │
│ │ ⏰ Prochaine: Demain 6h30        │  │
│ └──────────────────────────────────┘  │
│                                        │
│ ✅ Complétés                           │
│ ──────────────────────────────────────│
│ ┌──────────────────────────────────┐  │
│ │ ✓ Lire 12 livres en 2025         │  │
│ │ Terminé le 28 Décembre 2025      │  │
│ └──────────────────────────────────┘  │
│                                        │
│ 💤 En pause                            │
│ ──────────────────────────────────────│
│ ┌──────────────────────────────────┐  │
│ │ ⏸ Apprendre le japonais          │  │
│ │ Mis en pause le 15 Janvier       │  │
│ └──────────────────────────────────┘  │
│                                        │
└────────────────────────────────────────┘
```

### 4.2 Détail d'un Rêve

```
┌────────────────────────────────────────┐
│ ← 🎸 Apprendre la guitare    [⋮ Menu] │
├────────────────────────────────────────┤
│                                        │
│ Progression                            │
│ ████████████░░░░░░░░░░░░░ 35%         │
│                                        │
│ 📅 Objectif: 15 Juin 2026              │
│ 🕐 Temps investi: 12h30                │
│ 🔥 Série actuelle: 5 jours             │
│                                        │
│ ┌──────────────────────────────────┐  │
│ │ 📊 Cette semaine                  │  │
│ │   L  M  M  J  V  S  D            │  │
│ │   ✓  ✓  ✓  ✓  ✓  ·  ·            │  │
│ │   5/5 tâches complétées          │  │
│ └──────────────────────────────────┘  │
│                                        │
│ 🎯 Étapes                              │
│ ──────────────────────────────────────│
│ ✅ Semaines 1-2: Les bases     [100%] │
│    Terminé le 10 Janvier              │
│                                        │
│ 🔄 Semaines 3-4: Premiers morceaux    │
│    ████████░░░░ 60%                   │
│    • ✓ Enchaînement La-Ré-Mi          │
│    • ✓ Premier morceau: Knockin'...   │
│    • ○ Transitions fluides            │
│    • ○ Jouer sans regarder            │
│                                        │
│ ○ Semaines 5-8: Rythme         [0%]   │
│ ○ Semaines 9-12: Barrés        [0%]   │
│ ○ Mois 4-5: Techniques         [0%]   │
│ ○ Mois 6: Perfectionnement     [0%]   │
│                                        │
├────────────────────────────────────────┤
│ [💬 Discuter] [📅 Calendrier] [✏️ Modifier]│
└────────────────────────────────────────┘
```

---

## 5. Profil & Paramètres

### 5.1 Écran Profil

```
┌────────────────────────────────────────┐
│ Mon Profil                             │
├────────────────────────────────────────┤
│                                        │
│          ┌─────┐                       │
│          │ 👤  │                       │
│          └─────┘                       │
│         Marie Dupont                   │
│      marie@email.com                   │
│                                        │
│ ┌──────────────────────────────────┐  │
│ │ 📊 Mes statistiques               │  │
│ │                                   │  │
│ │ 🎯 3 rêves en cours               │  │
│ │ ✅ 45 tâches complétées           │  │
│ │ 🔥 Meilleure série: 12 jours      │  │
│ │ ⏱ 28h de temps investi            │  │
│ └──────────────────────────────────┘  │
│                                        │
│ 🏆 Badges                              │
│ [🌱 Débutant] [🔥 5 jours] [📚 10 tâches]│
│                                        │
│ ⚙️ Paramètres                          │
│ ──────────────────────────────────────│
│ > Horaires de travail                  │
│ > Notifications                        │
│ > Apparence (Clair/Sombre)            │
│ > Langue                               │
│ > Abonnement (Free)                    │
│ > Aide & Support                       │
│ > Politique de confidentialité         │
│ > Se déconnecter                       │
│                                        │
└────────────────────────────────────────┘
```

### 5.2 Paramètres de Notifications

```
┌────────────────────────────────────────┐
│ ← Notifications                        │
├────────────────────────────────────────┤
│                                        │
│ 🔔 Général                             │
│ ──────────────────────────────────────│
│ Notifications push          [====○]   │
│                                        │
│ 📋 Types de notifications              │
│ ──────────────────────────────────────│
│ Rappels de tâches           [====○]   │
│   Avance: [15 minutes ▼]              │
│                                        │
│ Messages de motivation      [====○]   │
│   Fréquence: [Quotidien ▼]            │
│   Heure: [08:00]                       │
│                                        │
│ Rapport hebdomadaire        [====○]   │
│   Jour: [Dimanche ▼]                  │
│   Heure: [10:00]                       │
│                                        │
│ Rappels d'inactivité        [○====]   │
│   Après: [3 jours ▼]                  │
│                                        │
│ 🌙 Ne pas déranger                     │
│ ──────────────────────────────────────│
│ Activer                     [====○]   │
│ De [22:00] à [07:00]                  │
│                                        │
│ [ ] Respecter le mode silencieux      │
│     du téléphone                       │
│                                        │
└────────────────────────────────────────┘
```

---

## 6. Système de Notifications

### 6.1 Types de Notifications

**Rappel de tâche (15 min avant)**
```
┌────────────────────────────────────────┐
│ 🔔 DreamPlanner                        │
│ Dans 15 minutes: Pratique guitare      │
│ Durée: 30 min                          │
│                        [Voir] [Reporter]│
└────────────────────────────────────────┘
```

**Motivation quotidienne (matin)**
```
┌────────────────────────────────────────┐
│ 🔔 DreamPlanner                        │
│ 🔥 5 jours consécutifs ! Tu es sur la │
│ bonne voie pour maîtriser la guitare! │
│                               [Voir]   │
└────────────────────────────────────────┘
```

**Progression (milestone)**
```
┌────────────────────────────────────────┐
│ 🔔 DreamPlanner                        │
│ 🎉 Félicitations ! Tu as atteint 50%  │
│ de ton objectif "Apprendre la guitare"│
│                               [Voir]   │
└────────────────────────────────────────┘
```

**Check-in (après inactivité)**
```
┌────────────────────────────────────────┐
│ 🔔 DreamPlanner                        │
│ 👋 Ça fait 3 jours qu'on ne s'est pas │
│ vus. Comment avance ton projet ?      │
│                        [Reprendre]     │
└────────────────────────────────────────┘
```

### 6.2 Planification Intelligente

Le système de notifications prend en compte:

1. **Horaires de travail** - Pas de notifications pendant le travail
2. **Mode Ne pas déranger** - Respect des heures de repos
3. **Préférences utilisateur** - Fréquence et types personnalisés
4. **Contexte** - Messages adaptés à la progression
5. **Timezone** - Notifications à l'heure locale

---

## 7. Fonctionnalités Premium

### 7.1 Tableau Comparatif

| Fonctionnalité | Free | Premium | Pro |
|----------------|------|---------|-----|
| Rêves actifs | 3 | Illimité | Illimité |
| Historique conversations | 7 jours | Illimité | Illimité |
| Notifications basiques | ✅ | ✅ | ✅ |
| Notifications personnalisées | ❌ | ✅ | ✅ |
| Export calendrier (iCal, Google) | ❌ | ✅ | ✅ |
| Thèmes personnalisés | ❌ | ✅ | ✅ |
| Statistiques détaillées | ❌ | ❌ | ✅ |
| Coaching IA avancé | ❌ | ❌ | ✅ |
| Intégration Notion/Todoist | ❌ | ❌ | ✅ |
| Support prioritaire | ❌ | ❌ | ✅ |
| Prix | Gratuit | 9.99€/mois | 19.99€/mois |

### 7.2 Écran d'Upgrade

```
┌────────────────────────────────────────┐
│ ← Passer à Premium                     │
├────────────────────────────────────────┤
│                                        │
│      ⭐ DreamPlanner Premium ⭐        │
│                                        │
│ Débloquez tout le potentiel de vos    │
│ rêves avec Premium                     │
│                                        │
│ ✅ Rêves illimités                     │
│ ✅ Notifications personnalisées        │
│ ✅ Export vers Google Calendar         │
│ ✅ Thèmes et personnalisation         │
│ ✅ Sans publicité                      │
│                                        │
│ ┌──────────────────────────────────┐  │
│ │ Mensuel                          │  │
│ │ 9.99€/mois                       │  │
│ └──────────────────────────────────┘  │
│                                        │
│ ┌──────────────────────────────────┐  │
│ │ Annuel (Économisez 33%)   ⭐     │  │
│ │ 79.99€/an (6.66€/mois)          │  │
│ └──────────────────────────────────┘  │
│                                        │
│ 7 jours d'essai gratuit               │
│ Annulez à tout moment                  │
│                                        │
│ [Commencer l'essai gratuit]           │
│                                        │
└────────────────────────────────────────┘
```
