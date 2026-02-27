# Priority Features - DreamPlanner 2.0

## Prioritization Matrix

```
                        HIGH IMPACT
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         │  QUICK WINS      │   BIG BETS       │
         │                  │                  │
         │  • 2-Min Start   │  • Dream Buddy   │
         │  • Micro-Wins    │  • AI Coach Pro  │
         │  • Streak Ins.   │  • Dream Circles │
         │                  │  • Vision Board  │
LOW      │                  │                  │
EFFORT ──┼──────────────────┼──────────────────┼── HIGH EFFORT
         │                  │                  │
         │  FILL-INS        │   MONEY PITS     │
         │                  │                  │
         │  • Themes        │  • Voice AI      │
         │  • Avatars       │  • AR Features   │
         │                  │  • Watch App     │
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                        LOW IMPACT
```

---

## Phase 1: MVP+ (Weeks 1-4)

### P1.1 - "2-Minute Start"

**User Story**: As a user, I want to be offered a simple first action of 2 minutes so that I can start immediately without overthinking.

**Acceptance Criteria**:
- [ ] The AI automatically generates a micro starting task
- [ ] The task is displayed immediately after creating a goal
- [ ] Visual 2-minute timer
- [ ] Celebration after completion
- [ ] Transition to the next step

**Implementation**:
```typescript
// Example AI prompt to generate the 2-minute start
const MICRO_START_PROMPT = `
For this objective: {objective}

Generate ONE SINGLE action that:
1. Takes MAXIMUM 2 minutes
2. Requires no preparation
3. Can be done NOW
4. Creates an initial commitment

Format: { action: string, duration: "30s" | "1min" | "2min", why: string }
`;
```

**Effort**: 3 days
**Impact**: Very high (reduces initial dropout by 60%)

---

### P1.2 - "Rescue Mode" (Dropout Detection)

**User Story**: As a user who has stopped doing my tasks, I want to be contacted gently to understand what is blocking me and receive tailored help.

**Acceptance Criteria**:
- [ ] Detection after 3 days of inactivity
- [ ] Empathetic notification (not guilt-inducing)
- [ ] Quick questionnaire (4 options max)
- [ ] Adapted response based on the reason
- [ ] Adapted plan proposal

**Detection Logic**:
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

**Effort**: 5 days
**Impact**: Very high (recovers 40% of dropouts)

---

### P1.3 - "Micro-Wins" Celebrations

**User Story**: As a user, I want my small progress to be celebrated to stay motivated.

**Acceptance Criteria**:
- [ ] Celebration animation for each task
- [ ] Special celebration for milestones (3, 7, 14, 30 days)
- [ ] Positive comparison ("You're doing better than 80%...")
- [ ] Social sharing option
- [ ] Sound and vibration (optional)

**Milestones to celebrate**:
```typescript
const MILESTONES = [
  { days: 1, badge: "First Step", message: "The hardest part is done!" },
  { days: 3, badge: "Momentum", message: "You're building a habit!" },
  { days: 7, badge: "Perfect Week", message: "A full week completed!" },
  { days: 14, badge: "Determined", message: "2 weeks, this is serious!" },
  { days: 30, badge: "Unstoppable", message: "One month! You're amazing!" },
  { days: 60, badge: "Rooted Habit", message: "It's become second nature!" },
  { days: 100, badge: "Centurion", message: "100 legendary days!" },
];
```

**Effort**: 4 days
**Impact**: High (increases retention by 35%)

---

## Phase 2: Social (Weeks 5-8)

### P2.1 - "Dream Buddy" System

**User Story**: As a user, I want to be connected with someone who has the same goal so that we can motivate each other.

**Acceptance Criteria**:
- [ ] Matching based on: similar goal, timezone, language
- [ ] Limited profile (first name, avatar, goal, progress)
- [ ] Integrated chat
- [ ] Mutual notifications ("Your buddy completed their task!")
- [ ] Option to change buddy
- [ ] Toxic behavior reporting

**Matching Algorithm**:
```typescript
interface MatchingCriteria {
  objectiveCategory: string;      // Weight: 40%
  targetTimeframe: DateRange;     // Weight: 20%
  timezone: string;               // Weight: 15%
  language: string;               // Weight: 15%
  activityLevel: 'low' | 'medium' | 'high'; // Weight: 10%
}

function calculateMatchScore(user1: User, user2: User): number {
  // Returns a score from 0 to 100
}
```

**Effort**: 2 weeks
**Impact**: Very high (retention x2 with active buddy)

---

### P2.2 - "Public Commitment"

**User Story**: As a user, I want to be able to publicly announce my goal to create social accountability.

**Acceptance Criteria**:
- [ ] Creation of a "commitment" with deadline
- [ ] Social media sharing (design template)
- [ ] Invite "witnesses" (friends)
- [ ] Notifications to witnesses about progress
- [ ] Public celebration if successful
- [ ] Discreet handling if failed (no shaming)

**Effort**: 1 week
**Impact**: High (engagement +50%)

---

### P2.3 - Gamification "Life RPG"

**User Story**: As a user, I want my progress to feel like a game so that it's fun.

**Acceptance Criteria**:
- [ ] Customizable avatar
- [ ] XP and level system
- [ ] Attributes by life domain
- [ ] Badges and achievements
- [ ] Unlockable rewards (themes, avatars)
- [ ] Time-limited special quests

**XP System**:
```typescript
const XP_REWARDS = {
  taskCompleted: 10,
  dailyGoalMet: 25,
  streakDay: 5 * streakLength, // Progressive bonus
  milestoneReached: 100,
  buddyHelped: 15,
  challengeCompleted: 50,
};

const LEVELS = [
  { level: 1, xpRequired: 0, title: "Dreamer" },
  { level: 5, xpRequired: 500, title: "Planner" },
  { level: 10, xpRequired: 1500, title: "Achiever" },
  { level: 20, xpRequired: 5000, title: "Dream Warrior" },
  { level: 50, xpRequired: 25000, title: "Legend" },
];
```

**Effort**: 2 weeks
**Impact**: High (daily engagement +40%)

---

## Phase 3: Advanced AI (Weeks 9-12)

### P3.1 - "Proactive AI Coach"

**User Story**: As a user, I want the AI to anticipate my difficulties and suggest solutions before I give up.

**Acceptance Criteria**:
- [ ] Personal pattern analysis
- [ ] Calendar integration (Google/Apple)
- [ ] At-risk week prediction
- [ ] Proactive adaptation suggestions
- [ ] Continuous preference learning

**Data Analyzed**:
```typescript
interface UserPatterns {
  // Temporal
  bestDaysOfWeek: number[];
  bestTimeOfDay: string;
  worstDaysOfWeek: number[];

  // Behavioral
  averageSessionLength: number;
  abandonTriggers: string[];
  motivationPeaks: string[];

  // Contextual
  calendarBusyDays: Date[];
  stressIndicators: string[];
}
```

**Effort**: 3 weeks
**Impact**: Very high (reduces dropout by 50%)

---

### P3.2 - "Vision Board" with Generative AI

**User Story**: As a user, I want to visualize my accomplished goal with an AI-generated image to stay motivated.

**Acceptance Criteria**:
- [ ] Image generation based on the goal
- [ ] Personalization (your face if permitted)
- [ ] Wallpaper option
- [ ] Daily reminder with the image
- [ ] Image evolution based on progress

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

**Effort**: 2 weeks
**Impact**: Medium-High (motivation +30%)

---

## Phase 4: Virality (Weeks 13-16)

### P4.1 - "Dream Circles" (Groups)

**User Story**: As a user, I want to join a small group of people with the same goal to share our journey.

**Acceptance Criteria**:
- [ ] Groups of 5-10 people max
- [ ] Manual creation or auto matching
- [ ] Weekly group challenges
- [ ] Group activity feed
- [ ] Friendly leaderboard
- [ ] Optional video calls
- [ ] AI moderation

**Effort**: 3 weeks
**Impact**: Very high (retention x3, high virality)

---

### P4.2 - Optimized Social Sharing

**User Story**: As a user, I want to be able to share my wins on social media with an automatic professional design.

**Acceptance Criteria**:
- [ ] Instagram Story templates
- [ ] TikTok templates
- [ ] Color/style customization
- [ ] Automatic stats inclusion
- [ ] Suggested hashtags
- [ ] Deep link to the app

**Templates to create**:
- Streak milestone (7, 14, 30 days)
- Goal completed
- New challenge launched
- Badge unlocked
- Before/after comparison

**Effort**: 1 week
**Impact**: Very high (viral acquisition)

---

## Planning Summary

| Phase | Weeks | Features | Key Impact |
|-------|-------|----------|------------|
| **MVP+** | 1-4 | 2-Min Start, Rescue Mode, Micro-Wins | Reduce initial dropout |
| **Social** | 5-8 | Dream Buddy, Commitment, Gamification | Create social engagement |
| **AI+** | 9-12 | Proactive Coach, Vision Board | Prevent dropout |
| **Viral** | 13-16 | Dream Circles, Social Sharing | Organic growth |

---

## Success Metrics

### North Star Metric
**WAU (Weekly Active Users) who complete at least 1 task**

### Secondary Metrics

| Metric | MVP Target | 6-Month Target |
|--------|-----------|--------------|
| D1 Retention | 60% | 70% |
| D7 Retention | 35% | 50% |
| D30 Retention | 15% | 30% |
| Buddy Match Rate | - | 40% |
| Viral Coefficient | - | 1.2 |
| Goal Completion Rate | 10% | 25% |
| NPS | 30 | 50 |
