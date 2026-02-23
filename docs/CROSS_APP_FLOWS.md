# DreamPlanner — Cross-App Flow Documentation

> **Purpose**: Traces the exact code path for operations that span multiple apps. Each flow documents the methods called, parameters passed, and side effects triggered — so you never have to trace through the code yourself.

---

## Table of Contents

1. [Task Completion Chain](#flow-1-task-completion-chain)
2. [Goal & Dream Completion](#flow-2-goal--dream-completion)
3. [Dream Creation with AI](#flow-3-dream-creation-with-ai)
4. [User Registration](#flow-4-user-registration)
5. [Notification Delivery Pipeline](#flow-5-notification-delivery-pipeline)
6. [Subscription Change](#flow-6-subscription-change)

---

## Flow 1: Task Completion Chain

**Entry**: `POST /api/dreams/tasks/{id}/complete/`
**Apps touched**: dreams, users, leagues (signal), notifications (achievement)

### Step-by-step

```
TaskViewSet.complete(request, pk)                    apps/dreams/views.py
  │
  └─> Task.complete()                                apps/dreams/models.py
      │
      ├─ 1. Task.status = 'completed'
      │     Task.completed_at = now()
      │     Task.save()
      │
      ├─ 2. Goal.update_progress()                   apps/dreams/models.py
      │     │  Calculates: completed_tasks / total_tasks * 100
      │     │  Saves: goal.progress_percentage
      │     │
      │     └─> Dream.update_progress()
      │           Calculates: completed_goals / total_goals * 100
      │           Saves: dream.progress_percentage
      │           └─> DreamProgressSnapshot.record_snapshot(dream)
      │
      ├─ 3. User.add_xp(xp_amount)                  apps/users/models.py
      │     │  xp_amount = max(10, (task.duration_mins or 30) // 3)
      │     │  user.xp += amount
      │     │  user.level = (user.xp // 100) + 1
      │     │  user.save(update_fields=['xp', 'level'])
      │     │
      │     └─> TRIGGERS Django signals:
      │         ├─ pre_save: track_xp_change()       apps/leagues/signals.py
      │         │    Stores instance._previous_xp
      │         │
      │         └─ post_save: update_league_standing_on_xp_change()
      │              If XP changed: LeagueService.update_standing(user)
      │                             apps/leagues/services.py
      │
      ├─ 4. User.update_activity()                   apps/users/models.py
      │     user.last_activity = now()
      │     user.save(update_fields=['last_activity'])
      │
      ├─ 5. Task._update_streak()                    apps/dreams/models.py
      │     If last_activity == yesterday:  streak_days += 1
      │     If last_activity < yesterday:   streak_days = 1
      │     user.save(update_fields=['streak_days'])
      │
      ├─ 6. DailyActivity.record_task_completion()   apps/users/models.py
      │     get_or_create DailyActivity for today
      │     activity.tasks_completed += 1
      │     activity.xp_earned += xp_amount
      │     activity.minutes_active += task.duration_mins
      │
      └─ 7. AchievementService.check_achievements()  apps/users/services.py
            Queries all active Achievement definitions
            Pre-computes user stats:
              - streak_days, level, xp, dreams created/completed
              - tasks completed, friends count, buddy status, circles
            For each unearned achievement where condition is met:
              → UserAchievement.objects.create(user, achievement)
              → user.add_xp(achievement.xp_reward)  ← RECURSIVE (back to step 3)
```

### XP Amounts

| Action | XP Formula |
| --- | --- |
| Task completion | `max(10, duration_mins // 3)` — minimum 10 XP |
| Goal completion | 100 XP (fixed) |
| Dream completion | 500 XP (fixed) |
| Achievement unlock | Varies per achievement definition (xp_reward field) |

---

## Flow 2: Goal & Dream Completion

### Goal Completion

**Entry**: `POST /api/dreams/goals/{id}/complete/`

```
GoalViewSet.complete(request, pk)                    apps/dreams/views.py
  └─> Goal.complete()                                apps/dreams/models.py
      ├─ goal.status = 'completed'
      ├─ goal.completed_at = now()
      ├─ goal.progress_percentage = 100.0
      ├─ goal.save()
      ├─ Dream.update_progress()     (recalculates dream %)
      └─ User.add_xp(100)           (triggers league signal)
```

### Dream Completion

**Entry**: `POST /api/dreams/dreams/{id}/complete/`

```
DreamViewSet.complete(request, pk)                   apps/dreams/views.py
  └─> Dream.complete()                               apps/dreams/models.py
      ├─ dream.status = 'completed'
      ├─ dream.completed_at = now()
      ├─ dream.progress_percentage = 100.0
      ├─ dream.save()
      ├─ User.add_xp(500)           (triggers league signal)
      └─ AchievementService.check_achievements(user)
```

---

## Flow 3: Dream Creation with AI

**Entry**: `POST /api/dreams/dreams/` → calibration → plan generation
**Apps touched**: dreams, integrations (OpenAI), core (moderation, AI validation, quotas), users, notifications

### Phase 1: Dream Creation

```
POST /api/dreams/dreams/
  │  body: { title, description, category, target_date }
  ▼
DreamViewSet.create()                                apps/dreams/views.py
  ├─ Permission: CanCreateDream
  │    Checks user.can_create_dream() → dream count < plan.dream_limit
  ├─ Serializer validates + sanitizes input
  └─ Dream.objects.create(user=request.user, ...)
```

### Phase 2: Calibration (7-15 questions)

```
POST /api/dreams/dreams/{id}/start_calibration/
  ▼
DreamViewSet.start_calibration()                     apps/dreams/views.py
  ├─ Permission: CanUseAI
  ├─ Quota Check: AIUsageTracker.check_quota(user, 'ai_plan')
  ├─ OpenAIService.generate_calibration_questions()  integrations/openai_service.py
  │    → GPT-4 generates 7 personalized questions
  │    → Validated with CalibrationQuestionsResponseSchema
  └─ Returns questions to client

POST /api/dreams/dreams/{id}/answer_calibration/     (repeat for each answer)
  ▼
DreamViewSet.answer_calibration()                    apps/dreams/views.py
  ├─ Saves CalibrationResponse(dream, question, answer, order)
  ├─ If < 5 answers: generate follow-up questions
  └─ If sufficient: returns { ready_for_plan: true }
```

### Phase 3: AI Plan Generation

```
POST /api/dreams/dreams/{id}/generate_plan/
  ▼
DreamViewSet.generate_plan()                         apps/dreams/views.py
  ├─ Permission: CanUseAI
  ├─ Quota Check: AIUsageTracker.check_quota(user, 'ai_plan')
  │
  ├─ Content Moderation (input)                      core/moderation.py
  │    Tier 1: Jailbreak pattern regex
  │    Tier 2: Roleplay pattern regex
  │    Tier 3: Harmful content regex
  │    Tier 4: OpenAI Moderation API
  │
  ├─ OpenAIService.generate_plan()                   integrations/openai_service.py
  │    Sends: dream details + calibration Q&A + ethical preamble
  │    Returns: structured plan (goals, tasks, tips, obstacles)
  │
  ├─ Output Validation                               core/ai_validators.py
  │    validate_plan_response() — Pydantic PlanResponseSchema
  │    validate_ai_output_safety() — harmful content check
  │    check_ai_character_integrity() — jailbreak detection
  │    check_plan_calibration_coherence() — plan matches user data
  │
  ├─ Create Goals + Tasks from AI plan
  │    For each goal in plan:
  │      Goal.objects.create(dream, title, description, order)
  │      For each task in goal:
  │        Task.objects.create(goal, title, description, order, duration_mins)
  │
  ├─ AIUsageTracker.increment(user, 'ai_plan')      core/ai_usage.py
  │
  └─ DreamProgressSnapshot.record_snapshot(dream)
```

### Phase 3 (Alternative): Skip Calibration

```
POST /api/dreams/dreams/{id}/skip_calibration/
  ▼
DreamViewSet.skip_calibration()                      apps/dreams/views.py
  └─ Sets dream.calibration_skipped = True
     Plan generation proceeds without calibration data
```

---

## Flow 4: User Registration

**Entry**: `POST /api/auth/registration/`
**Apps touched**: users, subscriptions (signal), leagues (signal)

```
POST /api/auth/registration/
  │  body: { email, password1, password2 }
  ▼
dj-rest-auth RegisterView
  ├─ RegisterSerializer (core/serializers.py)
  │    Email-only auth (no username field)
  │    Validates email + password
  ▼
UserManager.create_user(email, password)             apps/users/models.py
  ├─ Normalizes email
  ├─ Creates User with defaults:
  │    subscription='free', xp=0, level=1, streak_days=0
  │    profile_visibility='public', timezone='Europe/Paris'
  ├─ user.save()
  │
  └─ TRIGGERS post_save signals:
     │
     ├─ Signal 1: create_stripe_customer_on_user_creation
     │    File: apps/subscriptions/signals.py
     │    Action: StripeService.create_customer(user)
     │    Creates: StripeCustomer record (user → stripe_customer_id)
     │    Non-blocking: logs error but doesn't prevent registration
     │
     └─ Signal 2: update_league_standing_on_xp_change
          File: apps/leagues/signals.py
          Action: Skipped (XP is 0 for new user, condition not met)
```

### Lazy-Created Models (on first access, not at registration)

| Model | When Created | How |
| --- | --- | --- |
| `GamificationProfile` | First GET `/api/users/gamification/` | `get_or_create()` in view |
| `DailyActivity` | First task completion | `get_or_create()` in `record_task_completion()` |
| `UserSettings` | First preference update | Created in preference update view |

---

## Flow 5: Notification Delivery Pipeline

**Entry**: Any app calls `NotificationDeliveryService.deliver(notification)`
**Apps touched**: notifications, core (channel layer → Redis)

### Creation

```
# Example: Celery task creates notification
Notification.objects.create(
    user=user,
    notification_type='task_reminder',    # one of 12+ types
    title='Time to work on your dream!',
    body='Your task "Research competitors" is due today.',
    data={'dream_id': '...', 'task_id': '...'},
    scheduled_for=now(),
    status='pending',
)
```

### Delivery (3 channels)

```
NotificationDeliveryService.deliver(notification)    apps/notifications/services.py
  │
  ├─ Read: user.notification_prefs (JSONField)
  │    { websocket_enabled: true, email_enabled: false, push_enabled: true, ... }
  │
  ├─ Channel 1: WebSocket (default: ON)
  │    if prefs.websocket_enabled:
  │      group_name = f'notifications_{user.id}'
  │      channel_layer.group_send(group_name, {
  │        'type': 'send_notification',
  │        'notification': { id, type, title, body, data, image_url, action_url }
  │      })
  │      → NotificationConsumer receives and pushes to client
  │
  ├─ Channel 2: Email (default: OFF — opt-in)
  │    if prefs.email_enabled:
  │      Renders: notifications/email/notification.{txt,html}
  │      Sends: EmailMultiAlternatives via Django mail backend
  │
  └─ Channel 3: Web Push / VAPID (default: ON)
       if prefs.push_enabled:
         Queries: WebPushSubscription.objects.filter(user=user, is_active=True)
         For each subscription:
           pywebpush.webpush(subscription_info, payload, vapid_key)
           On 404/410: deactivate subscription (expired)
```

### Periodic Processing

The `process_pending_notifications` Celery task (every 60 seconds) picks up notifications with `status='pending'` and `scheduled_for <= now()`, then calls `deliver()` on each.

### Do Not Disturb (DND)

```
If user.notification_prefs.dndEnabled == True:
  If current_hour is between dndStart and dndEnd:
    Notification is held (stays pending) until DND window ends
    Supports midnight-crossing windows (e.g., 22:00 → 07:00)
```

---

## Flow 6: Subscription Change

**Entry**: `POST /api/subscriptions/subscription/checkout/`
**Apps touched**: subscriptions, users (denormalized fields), core (permissions affected)

### Checkout Flow

```
POST /api/subscriptions/subscription/checkout/
  │  body: { plan_slug: 'premium', success_url: '...', cancel_url: '...' }
  ▼
SubscriptionViewSet.checkout()                       apps/subscriptions/views.py
  ├─ Validates plan exists, is active, not free tier
  ├─ StripeService.create_checkout_session(user, plan, urls)
  │    apps/subscriptions/services.py
  │    1. Gets/creates StripeCustomer for user
  │    2. Creates Stripe Checkout Session with plan's stripe_price_id
  │    3. Returns: { checkout_url, session_id }
  └─ Returns checkout_url → Client redirects to Stripe
```

### Webhook Flow (after payment)

```
POST /api/subscriptions/webhook/stripe/
  │  Stripe sends: checkout.session.completed event
  ▼
StripeWebhookView.post()                            apps/subscriptions/views.py
  ├─ StripeService.handle_webhook_event(payload, sig_header)
  │    1. Verifies Stripe signature (STRIPE_WEBHOOK_SECRET)
  │    2. Dispatches by event type
  ▼
_handle_checkout_completed(session)                  apps/subscriptions/services.py
  ├─ Finds user via StripeCustomer.stripe_customer_id
  ├─ Finds plan via stripe_price_id lookup
  ├─ Subscription.objects.update_or_create(
  │    user=user,
  │    defaults={
  │      plan=plan,
  │      stripe_subscription_id=session.subscription,
  │      status='active',
  │      current_period_start=...,
  │      current_period_end=...,
  │    }
  │  )
  └─ _sync_user_subscription(user, plan, period_end)
       user.subscription = plan.slug       ('premium' or 'pro')
       user.subscription_ends = period_end
       user.save(update_fields=['subscription', 'subscription_ends'])
```

### What Changes After Upgrade

Once `user.subscription` is updated, all permission checks immediately reflect the new tier:

| Permission Class | What It Checks | Effect |
| --- | --- | --- |
| `CanCreateDream` | `user.can_create_dream()` → plan.dream_limit | Can create more dreams |
| `CanUseAI` | `user.subscription in ('premium', 'pro')` | AI chat/plan unlocked |
| `CanUseBuddy` | `user.subscription in ('premium', 'pro')` | Buddy matching unlocked |
| `CanUseCircles` | `user.subscription == 'pro'` (create) | Circle creation unlocked |
| `CanUseVisionBoard` | `user.subscription == 'pro'` | Vision board unlocked |
| `CanUseLeague` | `user.subscription in ('premium', 'pro')` | Leagues unlocked |
| `CanUseStore` | `user.subscription in ('premium', 'pro')` | Store purchasing unlocked |
| `CanUseSocialFeed` | `user.subscription in ('premium', 'pro')` | Full social feed unlocked |

AI daily quotas also change — `AIUsageTracker.get_limits()` reads limits from the user's subscription plan.

### Other Webhook Events

| Event | Handler | Action |
| --- | --- | --- |
| `invoice.paid` | `_handle_invoice_paid` | Updates billing period dates |
| `invoice.payment_failed` | `_handle_invoice_payment_failed` | Sets subscription status to `past_due` |
| `customer.subscription.updated` | `_handle_subscription_updated` | Mirrors status/plan changes from Stripe |
| `customer.subscription.deleted` | `_handle_subscription_deleted` | Sets status to `canceled`, reverts user to `free` tier |

### Cancellation Flow

```
POST /api/subscriptions/subscription/cancel/
  └─> StripeService.cancel_subscription(user)
      Sets cancel_at_period_end = True on Stripe
      User keeps access until current_period_end
      At period end: Stripe fires customer.subscription.deleted webhook
        → user.subscription reverted to 'free'
        → All premium/pro features gated again

POST /api/subscriptions/subscription/reactivate/
  └─> StripeService.reactivate_subscription(user)
      Removes cancel_at_period_end on Stripe
      User continues on current plan
```
