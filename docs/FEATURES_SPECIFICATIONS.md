# Feature Specifications - DreamPlanner

## 1. Onboarding & Registration

### 1.1 Onboarding Screens (3 slides)

**Slide 1 - Welcome**
- Title: "Transform your dreams into reality"
- Description: "DreamPlanner uses AI to create a personalized plan toward your goals"
- Illustration: Person reaching a summit

**Slide 2 - How it works**
- Title: "You talk, we plan"
- Description: "Describe your dream, we create a schedule adapted to your life"
- Illustration: AI Chat + Calendar

**Slide 3 - Stay motivated**
- Title: "Never lose track"
- Description: "Smart notifications and progress tracking to keep you on the right path"
- Illustration: Notifications + Progress chart

### 1.2 Registration

**Registration options:**
- Email + Password
- Google Sign-In
- Apple Sign-In

**Information collected:**
1. Display name
2. Email
3. Timezone (auto-detection)

### 1.3 Initial Setup

**Step 1 - Work schedule**
```
"To plan better, tell me when you work"

[ ] I am not currently working
[x] I have a regular schedule

Work days: [M] [T] [W] [T] [F] [ ] [ ]
Start time: [09:00]
End time: [18:00]
```

**Step 2 - Notification preferences**
```
"How would you like me to remind you of your tasks?"

Reminders before a task: [15 minutes ▼]

"Do Not Disturb" mode:
From [22:00] to [07:00]

Notification types:
[x] Task reminders
[x] Motivational messages
[x] Weekly progress
[ ] Tips and advice
```

**Step 3 - First dream**
```
"What is your first dream or goal?"

[Free text input - suggestion: "Learn Spanish in 6 months"]

or

[Choose a category]
- 💼 Career
- 🏋️ Health & Fitness
- 📚 Learning
- 💰 Finance
- ✈️ Travel
- 🎨 Creativity
- 🧘 Wellness
```

---

## 2. AI Conversation (Main Screen)

### 2.1 Chat Interface

```
┌────────────────────────────────────────┐
│ ← DreamPlanner            [+] New      │
├────────────────────────────────────────┤
│                                        │
│   🤖 Hello Marie! I'm delighted to    │
│   accompany you toward your dreams.    │
│                                        │
│   Tell me about what you would like    │
│   to accomplish. What is your next     │
│   big goal?                            │
│                                        │
│                        ┌──────────────┐│
│                        │ I would like ││
│                        │ to learn to  ││
│                        │ play the     ││
│                        │ guitar       ││
│                        └──────────────┘│
│                                        │
│   🤖 Great choice! The guitar is a    │
│   rewarding instrument.               │
│                                        │
│   A few questions to plan better:      │
│                                        │
│   1. Do you already have a guitar?     │
│   2. What style do you want to play?   │
│   3. How much time per day can you     │
│      dedicate to practice?             │
│   4. Do you have a target date in      │
│      mind?                             │
│                                        │
├────────────────────────────────────────┤
│ [Message...                    ] [📤] │
│                                        │
│ Quick suggestions:                     │
│ [Yes I already have a guitar]          │
│ [I want to play rock]                  │
│ [30 min per day]                       │
└────────────────────────────────────────┘
```

### 2.2 Plan Generation

After the conversation, the AI generates a plan:

```
┌────────────────────────────────────────┐
│ 🎯 Your Plan: Learn Guitar             │
├────────────────────────────────────────┤
│                                        │
│ 📊 Analysis                            │
│ ──────────────────────────────────────│
│ Feasibility: ████████░░ 80% High      │
│ Estimated duration: 6 months           │
│ Time required: 3h30/week              │
│                                        │
│ 🎯 Journey milestones                  │
│ ──────────────────────────────────────│
│                                        │
│ ○ Weeks 1-2: The basics               │
│   • Posture and positioning            │
│   • Basic chords (A, D, E)            │
│   • 30 min/day                         │
│                                        │
│ ○ Weeks 3-4: First songs              │
│   • Chord transitions                  │
│   • First simple song                  │
│   • 30 min/day                         │
│                                        │
│ ○ Weeks 5-8: Rhythm & Strumming       │
│   • Strumming patterns                 │
│   • Keeping tempo                      │
│   • 30 min/day                         │
│                                        │
│ [View all steps ▼]                     │
│                                        │
│ 💡 Tips                                │
│ • Warm up your fingers beforehand      │
│ • Practice with a metronome            │
│ • Record your progress                 │
│                                        │
│ ⚠️ Potential obstacles                 │
│ • Finger pain (normal!)               │
│ • Progress plateau                     │
│                                        │
├────────────────────────────────────────┤
│                                        │
│ [Edit plan]  [✓ Adopt this plan]       │
│                                        │
└────────────────────────────────────────┘
```

---

## 3. Calendar

### 3.1 Monthly View

```
┌────────────────────────────────────────┐
│ ←  January 2026  →                     │
├────────────────────────────────────────┤
│  M    T    W    T    F    S    S      │
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
│ Legend: ● Scheduled task  ○ Completed  │
│         🔴 Overdue                     │
└────────────────────────────────────────┘
```

### 3.2 Day View

```
┌────────────────────────────────────────┐
│ ← Today, Monday January 27 →          │
├────────────────────────────────────────┤
│                                        │
│ 06:00  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│ 07:00  ████ Wake up & routine         │
│ 08:00  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│ 09:00  ▓▓▓▓▓▓▓▓▓▓▓▓ Work             │
│ ...                                    │
│ 12:00  ████ Lunch break               │
│ 13:00  ▓▓▓▓▓▓▓▓▓▓▓▓ Work             │
│ ...                                    │
│ 18:00  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│ 18:30  ┌──────────────────────────┐   │
│        │ 🎸 Guitar practice       │   │
│        │    30 min                │   │
│        │    Goal: Basics          │   │
│        │ [Start] [Postpone]       │   │
│        └──────────────────────────┘   │
│ 19:00  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│ 19:30  ████ Dinner                    │
│ 20:00  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│                                        │
│ Legend: ▓▓ Work  ██ Other  ░░ Free     │
└────────────────────────────────────────┘
```

### 3.3 Week View

```
┌────────────────────────────────────────┐
│ ← Week of January 27 →                │
├────────────────────────────────────────┤
│      M   T   W   T   F   S   S       │
│ 7am ░░  ░░  ░░  ░░  ░░  ░░  ░░      │
│ 8am ░░  ░░  ░░  ░░  ░░  ░░  ░░      │
│ 9am ▓▓  ▓▓  ▓▓  ▓▓  ▓▓  ░░  ░░      │
│ ...      ...                          │
│6pm  ░░  ░░  ░░  ░░  ░░  ░░  ░░      │
│6:30pm 🎸  🎸  🎸  🎸  🎸  ░░  ░░      │
│7pm  ░░  ░░  ░░  ░░  ░░  🎸  ░░      │
│8pm  ░░  ░░  ░░  ░░  ░░  ░░  ░░      │
├────────────────────────────────────────┤
│ This week: 5 tasks • 2h30 total       │
└────────────────────────────────────────┘
```

---

## 4. My Dreams (Dashboard)

### 4.1 Dream List

```
┌────────────────────────────────────────┐
│ My Dreams                      [+ New] │
├────────────────────────────────────────┤
│                                        │
│ 🔥 In Progress                         │
│ ──────────────────────────────────────│
│ ┌──────────────────────────────────┐  │
│ │ 🎸 Learn guitar                  │  │
│ │ ████████░░░░░░░░ 35%             │  │
│ │ 📅 Goal: June 2026              │  │
│ │ ⏰ Next: Today 6:30 PM           │  │
│ └──────────────────────────────────┘  │
│                                        │
│ ┌──────────────────────────────────┐  │
│ │ 🏃 Run a marathon               │  │
│ │ ██░░░░░░░░░░░░░░ 12%             │  │
│ │ 📅 Goal: October 2026           │  │
│ │ ⏰ Next: Tomorrow 6:30 AM        │  │
│ └──────────────────────────────────┘  │
│                                        │
│ ✅ Completed                           │
│ ──────────────────────────────────────│
│ ┌──────────────────────────────────┐  │
│ │ ✓ Read 12 books in 2025          │  │
│ │ Completed on December 28, 2025   │  │
│ └──────────────────────────────────┘  │
│                                        │
│ 💤 Paused                              │
│ ──────────────────────────────────────│
│ ┌──────────────────────────────────┐  │
│ │ ⏸ Learn Japanese                 │  │
│ │ Paused on January 15             │  │
│ └──────────────────────────────────┘  │
│                                        │
└────────────────────────────────────────┘
```

### 4.2 Dream Detail

```
┌────────────────────────────────────────┐
│ ← 🎸 Learn guitar              [⋮ Menu] │
├────────────────────────────────────────┤
│                                        │
│ Progress                               │
│ ████████████░░░░░░░░░░░░░ 35%         │
│                                        │
│ 📅 Goal: June 15, 2026                │
│ 🕐 Time invested: 12h30               │
│ 🔥 Current streak: 5 days             │
│                                        │
│ ┌──────────────────────────────────┐  │
│ │ 📊 This week                     │  │
│ │   M  T  W  T  F  S  S            │  │
│ │   ✓  ✓  ✓  ✓  ✓  ·  ·            │  │
│ │   5/5 tasks completed            │  │
│ └──────────────────────────────────┘  │
│                                        │
│ 🎯 Steps                              │
│ ──────────────────────────────────────│
│ ✅ Weeks 1-2: The basics      [100%] │
│    Completed on January 10           │
│                                        │
│ 🔄 Weeks 3-4: First songs            │
│    ████████░░░░ 60%                   │
│    • ✓ A-D-E chord transitions       │
│    • ✓ First song: Knockin'...       │
│    • ○ Smooth transitions            │
│    • ○ Play without looking          │
│                                        │
│ ○ Weeks 5-8: Rhythm          [0%]    │
│ ○ Weeks 9-12: Barre chords   [0%]    │
│ ○ Months 4-5: Techniques     [0%]    │
│ ○ Month 6: Refinement        [0%]    │
│                                        │
├────────────────────────────────────────┤
│ [💬 Chat] [📅 Calendar] [✏️ Edit]      │
└────────────────────────────────────────┘
```

---

## 5. Profile & Settings

### 5.1 Profile Screen

```
┌────────────────────────────────────────┐
│ My Profile                             │
├────────────────────────────────────────┤
│                                        │
│          ┌─────┐                       │
│          │ 👤  │                       │
│          └─────┘                       │
│         Marie Dupont                   │
│      marie@email.com                   │
│                                        │
│ ┌──────────────────────────────────┐  │
│ │ 📊 My statistics                 │  │
│ │                                   │  │
│ │ 🎯 3 dreams in progress          │  │
│ │ ✅ 45 tasks completed            │  │
│ │ 🔥 Best streak: 12 days          │  │
│ │ ⏱ 28h of time invested          │  │
│ └──────────────────────────────────┘  │
│                                        │
│ 🏆 Badges                              │
│ [🌱 Beginner] [🔥 5 days] [📚 10 tasks]│
│                                        │
│ ⚙️ Settings                            │
│ ──────────────────────────────────────│
│ > Work schedule                        │
│ > Notifications                        │
│ > Appearance (Light/Dark)              │
│ > Language                             │
│ > Subscription (Free)                  │
│ > Help & Support                       │
│ > Privacy policy                       │
│ > Log out                              │
│                                        │
└────────────────────────────────────────┘
```

### 5.2 Notification Settings

```
┌────────────────────────────────────────┐
│ ← Notifications                        │
├────────────────────────────────────────┤
│                                        │
│ 🔔 General                             │
│ ──────────────────────────────────────│
│ Push notifications          [====○]   │
│                                        │
│ 📋 Notification types                  │
│ ──────────────────────────────────────│
│ Task reminders              [====○]   │
│   Lead time: [15 minutes ▼]           │
│                                        │
│ Motivational messages       [====○]   │
│   Frequency: [Daily ▼]               │
│   Time: [08:00]                        │
│                                        │
│ Weekly report               [====○]   │
│   Day: [Sunday ▼]                     │
│   Time: [10:00]                        │
│                                        │
│ Inactivity reminders        [○====]   │
│   After: [3 days ▼]                   │
│                                        │
│ 🌙 Do Not Disturb                      │
│ ──────────────────────────────────────│
│ Enable                      [====○]   │
│ From [22:00] to [07:00]               │
│                                        │
│ [ ] Respect user preferences           │
│                                        │
└────────────────────────────────────────┘
```

---

## 6. Notification System

### 6.1 Notification Types

**Task reminder (15 min before)**
```
┌────────────────────────────────────────┐
│ 🔔 DreamPlanner                        │
│ In 15 minutes: Guitar practice         │
│ Duration: 30 min                       │
│                      [View] [Postpone] │
└────────────────────────────────────────┘
```

**Daily motivation (morning)**
```
┌────────────────────────────────────────┐
│ 🔔 DreamPlanner                        │
│ 🔥 5 consecutive days! You are on      │
│ track to master the guitar!            │
│                               [View]   │
└────────────────────────────────────────┘
```

**Progress (milestone)**
```
┌────────────────────────────────────────┐
│ 🔔 DreamPlanner                        │
│ 🎉 Congratulations! You have reached  │
│ 50% of your goal "Learn guitar"       │
│                               [View]   │
└────────────────────────────────────────┘
```

**Check-in (after inactivity)**
```
┌────────────────────────────────────────┐
│ 🔔 DreamPlanner                        │
│ 👋 It's been 3 days since we last      │
│ connected. How is your project going?  │
│                        [Resume]        │
└────────────────────────────────────────┘
```

### 6.2 Smart Scheduling

The notification system takes into account:

1. **Work schedule** - No notifications during work
2. **Do Not Disturb mode** - Respects rest hours
3. **User preferences** - Customized frequency and types
4. **Context** - Messages adapted to progress
5. **Timezone** - Notifications at local time

---

## 7. Premium Features

### 7.1 Comparison Table

| Feature | Free | Premium | Pro |
|---------|------|---------|-----|
| Active dreams | 3 | Unlimited | Unlimited |
| Conversation history | 7 days | Unlimited | Unlimited |
| Basic notifications | ✅ | ✅ | ✅ |
| Custom notifications | ❌ | ✅ | ✅ |
| Calendar export (iCal, Google) | ❌ | ✅ | ✅ |
| Custom themes | ❌ | ✅ | ✅ |
| Detailed statistics | ❌ | ❌ | ✅ |
| Advanced AI coaching | ❌ | ❌ | ✅ |
| Notion/Todoist integration | ❌ | ❌ | ✅ |
| Priority support | ❌ | ❌ | ✅ |
| Price | Free | $14.99/month | $29.99/month |

### 7.2 Upgrade Screen

```
┌────────────────────────────────────────┐
│ ← Upgrade to Premium                   │
├────────────────────────────────────────┤
│                                        │
│      ⭐ DreamPlanner Premium ⭐        │
│                                        │
│ Unlock the full potential of your      │
│ dreams with Premium                    │
│                                        │
│ ✅ Unlimited dreams                    │
│ ✅ Custom notifications               │
│ ✅ Export to Google Calendar           │
│ ✅ Themes and customization           │
│ ✅ Ad-free                             │
│                                        │
│ ┌──────────────────────────────────┐  │
│ │ Monthly                         │  │
│ │ $14.99/month                     │  │
│ └──────────────────────────────────┘  │
│                                        │
│ ┌──────────────────────────────────┐  │
│ │ Annual (Save 33%)        ⭐     │  │
│ │ $119.99/year ($10.00/month)     │  │
│ └──────────────────────────────────┘  │
│                                        │
│ 7-day free trial                       │
│ Cancel at any time                     │
│                                        │
│ [Start free trial]                     │
│                                        │
└────────────────────────────────────────┘
```

---

## 8. Circle Group Chat

### 8.1 WebSocket Protocol

**Connection:** `ws://host/ws/circle-chat/{circle_id}/?token=<auth_token>`

**Authentication:** Post-connect token message (`{"type": "authenticate", "token": "..."}`)

**Access control:** User must be a circle member (`CircleMembership` required).

### 8.2 Message Format

| Direction | Type | Format |
|-----------|------|--------|
| Client → Server | `message` | `{"type": "message", "message": "text"}` |
| Client → Server | `typing` | `{"type": "typing", "is_typing": true}` |
| Server → Client | `message` | `{"type": "message", "message": {"id": "uuid", "content": "...", "sender_id": "uuid", "sender_name": "...", "created_at": "..."}}` |
| Server → Client | `typing_status` | `{"type": "typing_status", "user_id": "uuid", "user_name": "...", "is_typing": true}` |
| Server → Client | `call_started` | `{"type": "call_started", "call": {"id": "uuid", "initiator": "uuid", "call_type": "voice", "agora_channel": "..."}}` |

### 8.3 Block Filtering

Messages from users the recipient has blocked are silently dropped on the receiving end. Each consumer loads the user's blocked user IDs at connection time and filters incoming group broadcasts.

### 8.4 Rate Limiting

20 messages per 60-second sliding window (lower than buddy chat's 30/60s to limit group broadcast volume).

---

## 9. Circle Voice/Video Calls

### 9.1 Agora Lifecycle

```
1. Start Call (initiator)
   POST /api/circles/{id}/call/start/
   → Creates CircleCall (status: active)
   → Generates Agora RTC token
   → Broadcasts call_started to WebSocket group
   → Sends FCM push to offline members
   → Returns: { call, agora_token, agora_channel }

2. Join Call (participant)
   POST /api/circles/{id}/call/join/
   → Creates CircleCallParticipant
   → Generates Agora RTC token
   → Returns: { call, agora_token, agora_channel }

3. Leave Call (participant)
   POST /api/circles/{id}/call/leave/
   → Sets participant.left_at

4. End Call (any participant)
   POST /api/circles/{id}/call/end/
   → Sets call.status = completed
   → Calculates duration_seconds
   → Updates max_participants
```

### 9.2 Agora Token Generation

Tokens are short-lived and scoped to the specific call channel and user UID. Environment variables required:

| Variable | Description |
|----------|-------------|
| `AGORA_APP_ID` | Agora project App ID |
| `AGORA_APP_CERTIFICATE` | Agora project App Certificate |

### 9.3 Participant Tracking

The `CircleCallParticipant` model tracks when each user joins and leaves. The `CircleCall.max_participants` field records the peak participant count during the call.

---

## 10. Dream Posts (Social Platform)

### 10.1 Post Creation

Users can share dream progress publicly with:
- **Content**: Text content about their dream progress (encrypted at rest)
- **Image**: Optional image URL or uploaded image file
- **GoFundMe link**: Optional fundraising link for dream support
- **Visibility**: `public` (anyone), `followers` (followers only), `private` (only self)
- **Dream link**: Optional association with a specific dream (shows dream title)

### 10.2 Social Feed

The feed at `GET /api/social/posts/feed/` shows:
1. Posts from users the requester follows
2. Public posts from all users
3. Excludes posts from blocked users (bidirectional)
4. Annotates `has_liked` and `has_encouraged` for the requesting user
5. Ordered by newest first, paginated (20 per page)

### 10.3 Interactions

| Interaction | Endpoint | Behavior |
|-------------|----------|----------|
| **Like** | `POST /posts/{id}/like/` | Toggle on/off, updates denormalized `likes_count` |
| **Comment** | `POST /posts/{id}/comment/` | Threaded via optional `parent` field, updates `comments_count` |
| **Encourage** | `POST /posts/{id}/encourage/` | One per user, 5 types: `you_got_this`, `keep_going`, `inspired`, `proud`, `fire` |
| **Share** | `POST /posts/{id}/share/` | Increments `shares_count` |

### 10.4 Notifications

All interactions trigger notifications to the post author:
- `dream_post_like` — when someone likes their post
- `dream_post_comment` — when someone comments on their post
- `dream_post_encouragement` — when someone sends an encouragement
