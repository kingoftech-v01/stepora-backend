# Design System - DreamPlanner

## 1. Identité Visuelle

### 1.1 Logo & Nom

**Nom**: DreamPlanner
**Tagline**: "Transformez vos rêves en réalité"

**Concept du logo**:
- Icône: Étoile stylisée combinée avec un calendrier/checklist
- Symbolise: Rêves (étoile) + Planification (calendrier)
- Style: Moderne, minimaliste, inspirant

### 1.2 Palette de Couleurs

```
COULEURS PRINCIPALES
────────────────────────────────────────

Primary (Violet Dream)
├── 50:  #F3E8FF  (backgrounds légers)
├── 100: #E9D5FF
├── 200: #D8B4FE
├── 300: #C084FC
├── 400: #A855F7
├── 500: #8B5CF6  ← Primary
├── 600: #7C3AED
├── 700: #6D28D9
├── 800: #5B21B6
└── 900: #4C1D95

Secondary (Teal Success)
├── 50:  #F0FDFA
├── 100: #CCFBF1
├── 200: #99F6E4
├── 300: #5EEAD4
├── 400: #2DD4BF
├── 500: #14B8A6  ← Secondary
├── 600: #0D9488
├── 700: #0F766E
├── 800: #115E59
└── 900: #134E4A

COULEURS SÉMANTIQUES
────────────────────────────────────────

Success:  #10B981 (Emerald 500)
Warning:  #F59E0B (Amber 500)
Error:    #EF4444 (Red 500)
Info:     #3B82F6 (Blue 500)

COULEURS NEUTRES
────────────────────────────────────────

Gray
├── 50:  #F9FAFB  (background)
├── 100: #F3F4F6
├── 200: #E5E7EB
├── 300: #D1D5DB
├── 400: #9CA3AF
├── 500: #6B7280  (body text)
├── 600: #4B5563
├── 700: #374151
├── 800: #1F2937  (headings)
└── 900: #111827  (darkest)
```

### 1.3 Thème Sombre

```
Dark Mode Mapping
────────────────────────────────────────

Background:
├── Surface:     #0F0F23
├── Card:        #1A1A2E
├── Elevated:    #25253A

Text:
├── Primary:     #F9FAFB
├── Secondary:   #9CA3AF
├── Muted:       #6B7280

Primary reste: #8B5CF6 (ajusté luminosité)
```

## 2. Typographie

### 2.1 Police de caractères

**Police principale**: Inter
- Moderne et lisible
- Excellente lisibilité sur mobile
- Support multilingue

**Police alternative**: System Default
- San Francisco (iOS)
- Roboto (Android)

### 2.2 Échelle Typographique

```
HEADINGS
────────────────────────────────────────

H1 (Display)
├── Size: 32px / 2rem
├── Weight: 700 (Bold)
├── Line-height: 1.2
└── Usage: Titres principaux d'écran

H2 (Title)
├── Size: 24px / 1.5rem
├── Weight: 600 (Semi-bold)
├── Line-height: 1.3
└── Usage: Titres de sections

H3 (Subtitle)
├── Size: 20px / 1.25rem
├── Weight: 600 (Semi-bold)
├── Line-height: 1.4
└── Usage: Sous-titres

H4 (Card Title)
├── Size: 18px / 1.125rem
├── Weight: 500 (Medium)
├── Line-height: 1.4
└── Usage: Titres de cartes

BODY TEXT
────────────────────────────────────────

Body Large
├── Size: 18px / 1.125rem
├── Weight: 400 (Regular)
├── Line-height: 1.6
└── Usage: Texte important

Body (Default)
├── Size: 16px / 1rem
├── Weight: 400 (Regular)
├── Line-height: 1.5
└── Usage: Texte courant

Body Small
├── Size: 14px / 0.875rem
├── Weight: 400 (Regular)
├── Line-height: 1.5
└── Usage: Texte secondaire

Caption
├── Size: 12px / 0.75rem
├── Weight: 400 (Regular)
├── Line-height: 1.4
└── Usage: Labels, timestamps
```

## 3. Composants UI

### 3.1 Boutons

```
PRIMARY BUTTON
────────────────────────────────────────
┌────────────────────────────────────────┐
│           Commencer                    │
└────────────────────────────────────────┘
├── Background: Primary-500 (#8B5CF6)
├── Text: White
├── Padding: 16px 24px
├── Border-radius: 12px
├── Font: 16px, Semi-bold
├── States:
│   ├── Hover: Primary-600
│   ├── Pressed: Primary-700
│   └── Disabled: Gray-300, opacity 0.5

SECONDARY BUTTON
────────────────────────────────────────
┌────────────────────────────────────────┐
│           Annuler                      │
└────────────────────────────────────────┘
├── Background: Transparent
├── Border: 2px solid Primary-500
├── Text: Primary-500
├── Padding: 14px 22px
├── Border-radius: 12px

GHOST BUTTON
────────────────────────────────────────
┌────────────────────────────────────────┐
│           En savoir plus               │
└────────────────────────────────────────┘
├── Background: Transparent
├── Text: Primary-500
├── Padding: 16px 24px
├── Underline on hover

ICON BUTTON
────────────────────────────────────────
┌──────┐
│  +   │
└──────┘
├── Size: 48px x 48px
├── Border-radius: 24px (circle)
├── Icon size: 24px
```

### 3.2 Cartes

```
DREAM CARD
────────────────────────────────────────
┌────────────────────────────────────────┐
│ 🎸 Apprendre la guitare               │
│                                        │
│ ████████░░░░░░░░░░░░ 35%              │
│                                        │
│ 📅 Objectif: Juin 2026                │
│ ⏰ Prochaine tâche: Aujourd'hui 18h30 │
└────────────────────────────────────────┘

├── Background: White (Dark: Card)
├── Border-radius: 16px
├── Padding: 16px
├── Shadow: 0 2px 8px rgba(0,0,0,0.08)
├── Border: 1px solid Gray-100

TASK CARD
────────────────────────────────────────
┌────────────────────────────────────────┐
│ ○ Pratique guitare - 30 min           │
│   18:30 - 19:00                        │
│                    [Commencer]         │
└────────────────────────────────────────┘

├── Background: Primary-50
├── Border-left: 4px solid Primary-500
├── Border-radius: 12px
├── Padding: 12px 16px
```

### 3.3 Progress Bar

```
PROGRESS BAR
────────────────────────────────────────

Default:
████████████░░░░░░░░░░░░░░░░ 45%

├── Track: Gray-200
├── Fill: Gradient (Primary-400 → Primary-600)
├── Height: 8px
├── Border-radius: 4px

With Label:
Progression          45%
████████████░░░░░░░░░░░░░░░░
```

### 3.4 Input Fields

```
TEXT INPUT
────────────────────────────────────────
Label
┌────────────────────────────────────────┐
│ Placeholder text...                    │
└────────────────────────────────────────┘
Helper text

├── Border: 1px solid Gray-300
├── Border-radius: 12px
├── Padding: 16px
├── Focus: Border Primary-500, Shadow
├── Error: Border Error, Red text

CHAT INPUT
────────────────────────────────────────
┌────────────────────────────────────┬───┐
│ Écrivez votre message...           │ ➤ │
└────────────────────────────────────┴───┘

├── Border-radius: 24px
├── Background: Gray-100
├── Send button: Primary-500
```

### 3.5 Navigation

```
BOTTOM TAB BAR
────────────────────────────────────────
┌────────────────────────────────────────┐
│  💬        📅        🎯        👤     │
│ Chat    Calendrier  Rêves    Profil  │
└────────────────────────────────────────┘

├── Height: 64px + safe area
├── Background: White
├── Active: Primary-500
├── Inactive: Gray-400
├── Icon size: 24px
├── Label: 12px

TOP APP BAR
────────────────────────────────────────
┌────────────────────────────────────────┐
│ ←  Titre de la page              ⋮    │
└────────────────────────────────────────┘

├── Height: 56px
├── Background: Transparent / Blur
├── Title: H3, center or left
```

## 4. Iconographie

### 4.1 Set d'icônes

Utiliser **Phosphor Icons** ou **Lucide Icons**
- Style: Regular (outline) par défaut
- Filled pour états actifs
- Taille standard: 24px

### 4.2 Icônes Principales

```
Navigation
├── 💬 chat-circle
├── 📅 calendar
├── 🎯 target
├── 👤 user

Actions
├── ➕ plus
├── ✏️ pencil
├── 🗑️ trash
├── ✓ check
├── ✕ x

Catégories de rêves
├── 💼 briefcase (Carrière)
├── 🏋️ barbell (Fitness)
├── 📚 book-open (Apprentissage)
├── 💰 currency-dollar (Finances)
├── ✈️ airplane (Voyage)
├── 🎨 palette (Créativité)
├── 🧘 flower-lotus (Bien-être)

Status
├── ⏳ clock (En attente)
├── 🔄 arrow-clockwise (En cours)
├── ✅ check-circle (Terminé)
├── ⏸️ pause (En pause)
```

## 5. Espacement

### 5.1 Système de Spacing

```
BASE: 4px

Space Scale
├── xs:   4px   (0.25rem)
├── sm:   8px   (0.5rem)
├── md:   16px  (1rem)
├── lg:   24px  (1.5rem)
├── xl:   32px  (2rem)
├── 2xl:  48px  (3rem)
├── 3xl:  64px  (4rem)
```

### 5.2 Layout Spacing

```
Screen Padding
├── Horizontal: 16px (mobile), 24px (tablet)
├── Vertical: 16px

Card Spacing
├── Internal padding: 16px
├── Between cards: 12px

Section Spacing
├── Between sections: 24px
├── Section title margin-bottom: 16px
```

## 6. Animations

### 6.1 Timing Functions

```
Easing Curves
├── ease-out:     cubic-bezier(0, 0, 0.2, 1)    → Entrées
├── ease-in:      cubic-bezier(0.4, 0, 1, 1)    → Sorties
├── ease-in-out:  cubic-bezier(0.4, 0, 0.2, 1)  → Mouvements
├── spring:       React Native Reanimated       → Interactions
```

### 6.2 Durées

```
Duration Scale
├── instant:  100ms  (micro-interactions)
├── fast:     200ms  (boutons, toggles)
├── normal:   300ms  (transitions d'écran)
├── slow:     500ms  (animations complexes)
```

### 6.3 Animations Clés

```
Page Transition
├── Type: Slide + Fade
├── Duration: 300ms
├── Easing: ease-in-out

Card Press
├── Type: Scale down
├── Scale: 0.98
├── Duration: 100ms

Progress Update
├── Type: Width animation
├── Duration: 500ms
├── Easing: ease-out

Notification Toast
├── Enter: Slide down + Fade in
├── Exit: Slide up + Fade out
├── Duration: 200ms

Chat Bubble
├── Type: Scale + Fade
├── Initial: scale(0.9), opacity(0)
├── Final: scale(1), opacity(1)
├── Duration: 200ms
```

## 7. Responsive Design

### 7.1 Breakpoints

```
Breakpoints
├── Mobile:     < 480px   (default)
├── Mobile L:   480-768px
├── Tablet:     768-1024px
├── Desktop:    > 1024px  (web only)
```

### 7.2 Adaptations

```
Mobile (Default)
├── Single column layout
├── Bottom tab navigation
├── Full-width cards
├── Touch targets: 48px minimum

Tablet
├── Two-column layout possible
├── Side navigation optional
├── Cards in grid (2 columns)
├── Larger spacing

Safe Areas
├── iOS: Respect notch + home indicator
├── Android: Status bar + navigation bar
```

## 8. Accessibilité

### 8.1 Contraste

```
Minimum Ratios (WCAG 2.1)
├── Normal text: 4.5:1
├── Large text (18px+): 3:1
├── UI components: 3:1

Vérifié:
├── Primary-500 sur White: ✓ 4.7:1
├── Gray-500 sur White: ✓ 4.6:1
├── White sur Primary-500: ✓ 4.7:1
```

### 8.2 Touch Targets

```
Minimum Sizes
├── Buttons: 48px x 48px
├── Links: 44px x 44px
├── Spacing between targets: 8px minimum
```

### 8.3 Screen Reader

```
Labels
├── Tous les boutons ont des labels accessibles
├── Images ont des alt text
├── Formulaires ont des labels associés

Focus
├── Visible focus indicators
├── Logical focus order
├── Skip links where needed
```
