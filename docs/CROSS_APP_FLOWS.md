# Stepora — Cross-App Flow Documentation

> **Purpose**: Traces the exact code path for operations that span multiple apps. Each flow documents the methods called, parameters passed, and side effects triggered — so you never have to trace through the code yourself.

---

## Table of Contents

1. [Task Completion Chain](#flow-1-task-completion-chain)
2. [Goal & Dream Completion](#flow-2-goal--dream-completion)
3. [Dream Creation with AI](#flow-3-dream-creation-with-ai)
4. [User Registration](#flow-4-user-registration)
5. [Notification Delivery Pipeline](#flow-5-notification-delivery-pipeline)
6. [Subscription Change](#flow-6-subscription-change)
7. [Buddy Pairing](#flow-7-buddy-pairing)
8. [Circle Lifecycle](#flow-8-circle-lifecycle)
9. [Store Purchase](#flow-9-store-purchase)
10. [League & Season](#flow-10-league--season)
11. [Social Interaction](#flow-11-social-interaction)
12. [Account Deletion (GDPR)](#flow-12-account-deletion-gdpr)
13. [Calendar & Scheduling](#flow-13-calendar--scheduling)
14. [Two-Factor Authentication](#flow-14-two-factor-authentication)
15. [Password Reset & Email Change](#flow-15-password-reset--email-change)
16. [Real-Time Messaging Pipeline](#flow-16-real-time-messaging-pipeline)
17. [Circle Voice/Video Call](#flow-17-circle-voicevideo-call)
18. [Dream Post Social Interaction](#flow-18-dream-post-social-interaction)

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
core.auth RegisterView                                core/auth/views.py
  ├─ RegisterSerializer (core/auth/serializers.py)
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

Once the `Subscription` record is updated, all permission checks immediately reflect the new tier via `user.get_active_plan()`:

| Permission Class | What It Checks (via `SubscriptionPlan` fields) | Effect |
| --- | --- | --- |
| `CanCreateDream` | `user.can_create_dream()` → `plan.dream_limit` | Can create more dreams |
| `CanUseAI` | `plan.has_ai` | AI chat/plan unlocked |
| `CanUseBuddy` | `plan.has_buddy` | Buddy matching unlocked |
| `CanUseCircles` | `plan.has_circles` (join), `plan.has_circle_create` (create) | Circle access unlocked |
| `CanUseVisionBoard` | `plan.has_vision_board` | Vision board unlocked |
| `CanUseLeague` | `plan.has_league` | Leagues unlocked |
| `CanUseStore` | `plan.has_store` | Store purchasing unlocked |
| `CanUseSocialFeed` | `plan.has_social_feed` | Full social feed unlocked |

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

---

## Flow 7: Buddy Pairing

**Entry**: `POST /api/buddies/find-match/` or `POST /api/buddies/pair/`
**Apps touched**: buddies, notifications, users

### Step-by-step

```
POST /api/buddies/find-match/
  ▼
BuddyViewSet.find_match(request)                    apps/buddies/views.py
  ├─ Permission: IsAuthenticated, CanUseBuddy
  ├─ Check: no existing active pairing for user
  ├─ Query candidates:
  │    Users without active pairings, active, ordered by last_activity
  │    Limit: top 50 candidates
  ├─ Scoring algorithm (per candidate):
  │    level_score = max(0, 1.0 - (level_diff / 50))  × 0.3
  │    xp_score    = max(0, 1.0 - (xp_diff / 10000))  × 0.3
  │    activity_score = max(0, 1.0 - (days_inactive / 30)) × 0.4
  ├─ Compute shared interests via GamificationProfile categories
  └─ Returns: { match: { userId, username, avatar, compatibilityScore, sharedInterests } }

POST /api/buddies/pair/
  ▼
BuddyViewSet.pair(request)                          apps/buddies/views.py
  ├─ Permission: IsAuthenticated, CanUseBuddy
  ├─ Validates: partner_id != self, no existing active pairing for either user
  ├─ Computes compatibility_score (level + XP similarity)
  └─ BuddyPairing.objects.create(
       user1=request.user, user2=partner,
       status='pending',
       compatibility_score=compatibility,
       expires_at=now() + 7 days,
     )
```

### Accept / Reject

```
POST /api/buddies/{id}/accept/
  ▼
BuddyViewSet.accept(request, pk)                    apps/buddies/views.py
  ├─ Lookup: BuddyPairing(id=pk, user2=request.user, status='pending')
  └─ pairing.status = 'active'
     pairing.save(update_fields=['status', 'updated_at'])

POST /api/buddies/{id}/reject/
  ▼
BuddyViewSet.reject(request, pk)                    apps/buddies/views.py
  ├─ Lookup: BuddyPairing(id=pk, user2=request.user, status='pending')
  └─ pairing.status = 'cancelled', pairing.ended_at = now()
```

### Encouragement & Streak

```
POST /api/buddies/{id}/encourage/
  ▼
BuddyViewSet.encourage(request, pk)                 apps/buddies/views.py
  ├─ Lookup: BuddyPairing(id=pk, status='active')
  ├─ Verify: request.user is user1 or user2
  ├─ BuddyEncouragement.objects.create(              apps/buddies/models.py
  │    pairing=pairing, sender=request.user, message=...
  │  )
  ├─ Streak logic:
  │    If last_encouragement was yesterday: streak += 1
  │    If last_encouragement was today:     no change
  │    If older:                            streak = 1
  │    Update best_encouragement_streak if new high
  └─ Notification.objects.create(                    apps/notifications/models.py
       user=partner, type='buddy',
       title='Buddy Encouragement', body=message
     )
```

### End Pairing

```
DELETE /api/buddies/{id}/
  ▼
BuddyViewSet.destroy(request, pk)                   apps/buddies/views.py
  ├─ Lookup: BuddyPairing(id=pk, status='active')
  ├─ Verify: request.user is user1 or user2
  └─ pairing.status = 'cancelled', pairing.ended_at = now()
```

### Auto-Expiry (Celery)

```
expire_pending_buddy_requests()                      apps/buddies/tasks.py
  │  Runs daily via Celery beat
  └─ BuddyPairing.objects.filter(
       status='pending', expires_at__lt=now()
     ).update(status='cancelled', ended_at=now())

send_buddy_checkin_reminders()                       apps/buddies/tasks.py
  │  Runs daily via Celery beat
  └─ For active pairings with no encouragement in 3+ days:
     Sends 'buddy' notification to both users
     (skips if reminder already sent in last 24h)
```

### Key Detail

Pending buddy requests **auto-expire after 7 days** via the `expire_pending_buddy_requests` Celery task. Active pairings with no encouragement in 3+ days trigger check-in reminder notifications.

---

## Flow 8: Circle Lifecycle

**Entry**: `POST /api/circles/`
**Apps touched**: circles, notifications

### Step-by-step

```
POST /api/circles/
  │  body: { name, description, category, is_public, max_members }
  ▼
CircleViewSet.create()                               apps/circles/views.py
  ├─ Permission: IsAuthenticated, CanUseCircles (pro required to create)
  ├─ CircleCreateSerializer validates input
  ├─ Circle.objects.create(creator=request.user, ...)  apps/circles/models.py
  └─ CircleMembership.objects.create(
       circle=circle, user=request.user, role='admin'
     )
```

### Invite Members

```
# Direct invite (admin/moderator only)
POST /api/circles/{id}/invite/
  ▼
CircleViewSet.invite(request, pk)                    apps/circles/views.py
  ├─ Verify: caller is admin or moderator
  ├─ Check: target user not already a member, no pending invite
  └─ CircleInvitation.objects.create(                apps/circles/models.py
       circle, inviter, invitee=target_user,
       invite_code=secrets.token_urlsafe(12),
       expires_at=now() + 7 days,
     )

# Link invite (shareable code, no specific invitee)
POST /api/circles/{id}/invite-link/
  └─ Same as above, invitee=None, expires_at=now() + 14 days

# Join via invite code
POST /api/circles/join/{invite_code}/
  ▼
JoinByInviteCodeView.post(request, invite_code)      apps/circles/views.py
  ├─ Lookup: CircleInvitation(invite_code, status='pending')
  ├─ Validate: not expired, correct invitee (if direct), circle not full
  ├─ CircleMembership.objects.create(role='member')
  └─ Mark invitation as 'accepted' (for direct invites)

# Join public circle directly
POST /api/circles/{id}/join/
  └─ Checks: is_public=True, not already member, not full
     Creates CircleMembership(role='member')
```

### Post Content & React

```
POST /api/circles/{id}/posts/
  ▼
CircleViewSet.posts(request, pk)                     apps/circles/views.py
  ├─ Verify: user is a circle member
  └─ CirclePost.objects.create(                      apps/circles/models.py
       circle, author=request.user, content=...
     )

POST /api/circles/{id}/posts/{post_id}/react/
  ▼
CircleViewSet.react_to_post(request, pk, post_id)    apps/circles/views.py
  ├─ Verify: user is a circle member
  └─ PostReaction.objects.update_or_create(           apps/circles/models.py
       post, user, defaults={reaction_type: 'thumbs_up'|'fire'|'clap'|'heart'}
     )
```

### Challenges

```
# Create challenge (admin/moderator creates via admin or separate endpoint)
CircleChallenge.objects.create(                      apps/circles/models.py
  circle, title, description, start_date, end_date, status='upcoming'
)

# Join challenge
POST /api/challenges/{id}/join/
  ▼
ChallengeViewSet.join(request, pk)                   apps/circles/views.py
  ├─ Verify: user is member of the challenge's circle
  └─ challenge.participants.add(request.user)

# Submit progress
POST /api/circles/{id}/challenges/{challenge_id}/progress/
  ▼
CircleViewSet.submit_progress(request, pk, challenge_id)
  └─ ChallengeProgress.objects.create(               apps/circles/models.py
       challenge, user, progress_value, notes
     )
```

### Moderation (Admin Only)

```
POST /api/circles/{id}/members/{member_id}/promote/
  └─ target_membership.role = 'moderator'            (admin only)

POST /api/circles/{id}/members/{member_id}/demote/
  └─ target_membership.role = 'member'               (admin only, moderators only)

DELETE /api/circles/{id}/members/{member_id}/remove/
  └─ target_membership.delete()                      (admin/moderator, cannot remove admin)
```

### Leave / Delete

```
POST /api/circles/{id}/leave/
  ▼
CircleViewSet.leave(request, pk)                     apps/circles/views.py
  ├─ If user is admin and no other admins exist:
  │    Auto-transfer ownership to oldest moderator
  │    If no moderators: transfer to oldest member
  │    new_admin.role = 'admin'
  │    circle.creator = new_admin.user
  └─ membership.delete()

DELETE /api/circles/{id}/
  └─ Admin only. circle.delete() — CASCADE removes all memberships, posts, challenges
```

### Key Detail

When the **creator leaves**, ownership is automatically transferred to the oldest moderator. If no moderators exist, it transfers to the oldest regular member. This ensures circles are never left without an admin.

---

## Flow 9: Store Purchase

**Entry**: `GET /api/store/items/`
**Apps touched**: store, subscriptions, notifications

### Browse & Wishlist

```
GET /api/store/items/                                apps/store/views.py
  ▼
StoreItemViewSet.list()
  ├─ Permission: AllowAny (public browsing)
  ├─ Filters: category__slug, item_type, rarity
  ├─ Search: name, description
  ├─ Active items within availability window only
  └─ Cached for 5 minutes (cache_page)

GET /api/store/items/featured/
  └─ Returns epic + legendary rarity items (max 10)

POST /api/store/wishlist/
  └─ Wishlist.objects.create(user, item)             apps/store/models.py
```

### Purchase via Stripe

```
POST /api/store/purchase/
  │  body: { item_id }
  ▼
PurchaseView.post(request)                           apps/store/views.py
  ├─ Permission: IsAuthenticated, CanUseStore (premium+ required)
  └─ StoreService.create_payment_intent(user, item)  apps/store/services.py
       ├─ Validates: item.is_active, user doesn't already own item
       ├─ amount_cents = int(item.price * 100)
       ├─ stripe.PaymentIntent.create(
       │    amount, currency='usd',
       │    metadata={user_id, item_id, item_name, item_type},
       │    receipt_email=user.email
       │  )
       └─ Returns: { client_secret, payment_intent_id, amount }

POST /api/store/purchase/confirm/
  │  body: { item_id, payment_intent_id }
  ▼
PurchaseConfirmView.post(request)                    apps/store/views.py
  └─ StoreService.confirm_purchase(user, item, pi_id) apps/store/services.py
       ├─ stripe.PaymentIntent.retrieve(pi_id)
       ├─ Verify: status == 'succeeded'
       ├─ Verify: amount matches item.price * 100
       ├─ Verify: metadata.user_id matches request.user
       └─ UserInventory.objects.create(              apps/store/models.py
            user, item, stripe_payment_intent_id,
            is_equipped=False
          )
```

### Purchase via XP

```
POST /api/store/purchase/xp/
  │  body: { item_id }
  ▼
XPPurchaseView.post(request)                         apps/store/views.py
  └─ StoreService.purchase_with_xp(user, item)       apps/store/services.py
       ├─ Validates: item.is_active, item.xp_price > 0
       ├─ Check: user.xp >= item.xp_price
       ├─ user.xp -= item.xp_price
       │  user.save(update_fields=['xp'])
       └─ UserInventory.objects.create(user, item)
```

### Equip / Unequip

```
POST /api/store/inventory/{id}/equip/
  │  body: { equip: true|false }
  ▼
UserInventoryViewSet.equip(request, pk)              apps/store/views.py
  └─ StoreService.equip_item(user, inventory_id)     apps/store/services.py
       ├─ Unequip all other items of the same item_type
       │  (only one badge_frame, theme_skin, etc. at a time)
       └─ inventory_entry.is_equipped = True
```

### Gift to Another User

```
POST /api/store/gift/
  │  body: { item_id, recipient_id, message }
  ▼
GiftSendView.post(request)                           apps/store/views.py
  └─ StoreService.send_gift(sender, recipient, item, message)
       apps/store/services.py
       ├─ Validates: item active, sender != recipient, recipient doesn't own item
       ├─ stripe.PaymentIntent.create(metadata={type: 'gift'})
       └─ Gift.objects.create(                       apps/store/models.py
            sender, recipient, item, message,
            stripe_payment_intent_id, is_claimed=False
          )

POST /api/store/gift/{gift_id}/claim/
  └─ StoreService.claim_gift(user, gift_id)
       ├─ gift.is_claimed = True, gift.claimed_at = now()
       └─ UserInventory.objects.create(user, gift.item)
```

### Request Refund

```
POST /api/store/refund/
  │  body: { inventory_id, reason }
  ▼
RefundRequestView.post(request)                      apps/store/views.py
  └─ StoreService.request_refund(user, inventory_id, reason)
       apps/store/services.py
       ├─ Validates: item was purchased with money (has stripe_payment_intent_id)
       ├─ Check: no existing pending refund for this item
       └─ RefundRequest.objects.create(status='pending')

# Admin processes refund:
StoreService.process_refund(refund_request_id, approve=True)
  ├─ stripe.Refund.create(payment_intent=...)
  ├─ inventory_entry.delete()  (remove from user's inventory)
  └─ refund_request.status = 'refunded'
```

### Key Detail

Supports both **Stripe payments** and **XP-based purchasing**. Items with `xp_price > 0` can be bought with XP, deducting from the user's XP balance. Only one item of each `item_type` (badge_frame, theme_skin, etc.) can be equipped at a time.

---

## Flow 10: League & Season

**Entry**: Automatic via Celery tasks
**Apps touched**: leagues, users, dreams, notifications

### Season Lifecycle

```
Season Model                                         apps/leagues/models.py
  ├─ Season duration: 90 days
  ├─ Only one active season at a time
  ├─ get_active_season() → cached for 1 hour
  └─ has_ended property: now() > end_date

check_season_end()                                   apps/leagues/tasks.py
  │  Runs daily via Celery beat
  ▼
  ├─ If season.has_ended:
  │    1. LeagueService.calculate_season_rewards(season)
  │       For each standing: SeasonReward.objects.get_or_create(
  │         season, user, league_achieved=standing.league
  │       )
  │       season.is_active = False
  │    2. send_league_change_notifications.delay(season_id)
  │    3. _create_next_season(ended_season)
  │       Season.objects.create(
  │         name='Season N+1', start_date=now(),
  │         end_date=now() + 90 days, is_active=True
  │       )
  └─ Else: log days remaining
```

### XP → League Standing (Signal-Driven)

```
User.add_xp(amount)  or  user.xp += amount; user.save()
  ▼
TRIGGERS Django signals:                             apps/leagues/signals.py

  pre_save: track_xp_change(sender, instance)
    └─ instance._previous_xp = User.objects.get(pk).xp

  post_save: update_league_standing_on_xp_change(sender, instance, created)
    └─ If XP changed (previous_xp != instance.xp):
       LeagueService.update_standing(instance)       apps/leagues/services.py
         ├─ season = Season.get_active_season()
         ├─ league = LeagueService.get_user_league(user)
         │    Checks XP against league min_xp/max_xp ranges
         ├─ LeagueStanding.objects.get_or_create(user, season)
         │    Updates: league, xp_earned_this_season, streak_best
         └─ _recalculate_ranks(season)
              Dense ranking: Window(DenseRank(), order_by=-xp)
              Users with same XP get the same rank
```

### League Tiers

| Tier | XP Range | Tier Order |
| --- | --- | --- |
| Bronze | 0 - 499 | 0 |
| Silver | 500 - 1,499 | 1 |
| Gold | 1,500 - 3,499 | 2 |
| Platinum | 3,500 - 6,999 | 3 |
| Diamond | 7,000 - 11,999 | 4 |
| Master | 12,000 - 19,999 | 5 |
| Legend | 20,000+ | 6 |

### Daily Rank Snapshots

```
create_daily_rank_snapshots()                        apps/leagues/tasks.py
  │  Runs daily via Celery beat
  └─ For each standing in active season:
     RankSnapshot.objects.update_or_create(           apps/leagues/models.py
       user, season, snapshot_date=today,
       defaults={league, rank, xp}
     )
```

### Weekly Promotion / Demotion

```
send_league_change_notifications()                   apps/leagues/tasks.py
  ├─ Records old leagues for all standings
  ├─ LeagueService.promote_demote_users()            apps/leagues/services.py
  │    For each standing: recalculates league from current XP
  │    If league changed: log promotion or demotion
  │    _recalculate_ranks(season)
  └─ For each user whose league changed:
     Notification.objects.create(
       type='achievement' (promoted) or 'system' (demoted),
       title='Promoted to {league}!' or 'League changed to {league}',
       data={screen: 'leaderboard', league_tier: ...}
     )
```

### Key Detail

Uses **dense ranking** (users with the same XP receive the same rank). 7 tiers from Bronze to Legend. Season transitions are fully automatic — when a season ends, rewards are calculated, a new 90-day season is created, and promotion/demotion notifications are sent.

---

## Flow 11: Social Interaction

**Entry**: `POST /api/social/friendships/`
**Apps touched**: social, users, notifications

### Step-by-step

```
# Search for users
GET /api/social/search/?q=username
  ▼
UserSearchView.get(request)                          apps/social/views.py
  ├─ Searches: display_name, email (icontains)
  ├─ Excludes: blocked users (bidirectional)
  └─ Returns: public profile data (id, display_name, avatar, level, xp, streak)
```

### Friend Request Lifecycle

```
POST /api/social/friendships/friends/request/
  │  body: { target_user_id }
  ▼
FriendshipViewSet.send_request(request)              apps/social/views.py
  ├─ Validates: not self, target exists
  ├─ Check: BlockedUser.objects.filter() — bidirectional block check
  ├─ Check: no existing friendship (accepted or pending)
  │    If rejected: re-sets to 'pending' (allows retry)
  └─ Friendship.objects.create(                      apps/social/models.py
       user1=request.user, user2=target_user,
       status='pending'
     )

POST /api/social/friendships/friends/{id}/accept/
  ▼
FriendshipViewSet.accept_request(request, pk)        apps/social/views.py
  ├─ Lookup: Friendship(id=pk, user2=request.user, status='pending')
  └─ friendship.status = 'accepted'

POST /api/social/friendships/friends/{id}/reject/
  ▼
FriendshipViewSet.reject_request(request, pk)        apps/social/views.py
  └─ friendship.status = 'rejected'

DELETE /api/social/friendships/friends/{id}/remove/
  ▼
FriendshipViewSet.remove_friend(request, pk)         apps/social/views.py
  └─ friendship.delete()
```

### Mutual Friends

```
Calculated in UserViewSet.retrieve()                 apps/users/views.py
  ├─ Queries accepted friendships for both users
  ├─ Builds set of friend IDs for each
  └─ mutual = len(my_friends & their_friends)
```

### Follow / Unfollow

```
POST /api/social/friendships/follow/
  │  body: { target_user_id }
  ▼
FriendshipViewSet.follow(request)                    apps/social/views.py
  ├─ Check: BlockedUser.is_blocked()
  └─ UserFollow.objects.get_or_create(               apps/social/models.py
       follower=request.user, following=target_user
     )

POST /api/social/friendships/unfollow/
  └─ UserFollow.objects.filter(
       follower=request.user, following=target_user
     ).delete()
```

### Block / Unblock

```
POST /api/social/block/
  │  body: { user_id, reason }
  ▼
BlockUserView.post(request)                          apps/social/views.py
  ├─ BlockedUser.objects.create(                     apps/social/models.py
  │    blocker=request.user, blocked=target_user, reason=...
  │  )
  ├─ Remove existing friendship (both directions)
  └─ Remove follow relationships (both directions)

POST /api/social/unblock/
  └─ BlockedUser.objects.filter(
       blocker=request.user, blocked=target_user
     ).delete()
```

### Report User

```
POST /api/social/report/
  │  body: { user_id, reason, category }
  ▼
ReportUserView.post(request)                         apps/social/views.py
  └─ ReportedUser.objects.create(                    apps/social/models.py
       reporter=request.user, reported=target_user,
       reason, category, status='pending'
     )
```

---

## Flow 12: Account Deletion (GDPR)

**Entry**: `DELETE /api/users/delete-account/`
**Apps touched**: users, subscriptions, buddies, circles

### Step-by-step

```
DELETE /api/users/delete-account/
  │  body: { password }
  ▼
UserViewSet.delete_account(request)                  apps/users/views.py
  │
  ├─ 1. Verify password
  │     user.check_password(password)
  │     If invalid: 400 "Invalid password"
  │
  ├─ 2. Audit log
  │     log_account_change(user, 'account_deletion')  core/audit.py
  │
  ├─ 3. Cancel Stripe subscription
  │     StripeService.cancel_subscription(user)       apps/subscriptions/services.py
  │     (best-effort: logs error but continues)
  │
  ├─ 4. End active buddy pairings
  │     BuddyPairing.objects.filter(                  apps/buddies/models.py
  │       Q(user1=user) | Q(user2=user),
  │       status__in=['pending', 'active']
  │     ).update(status='cancelled', ended_at=now())
  │
  ├─ 5. Remove circle memberships
  │     CircleMembership.objects.filter(user=user).delete()
  │                                                   apps/circles/models.py
  │
  ├─ 6. Anonymize PII
  │     user.display_name  = 'Deleted User'
  │     user.email         = 'deleted_{user.id}@deleted.stepora.app'
  │     user.avatar_url    = ''
  │     user.avatar_image  → delete file
  │     user.bio           = ''
  │     user.location      = ''
  │     user.social_links  = None
  │     user.notification_prefs = None
  │     user.app_prefs     = None
  │     user.work_schedule = None
  │
  ├─ 7. Deactivate account
  │     user.is_active = False
  │     user.save()
  │
  └─ 8. Delete auth tokens
       Token.objects.filter(user=user).delete()
```

### Hard Delete (30-Day Grace Period)

```
hard_delete_expired_accounts()                       apps/users/tasks.py
  │  Runs daily via Celery beat
  ▼
  ├─ cutoff = now() - 30 days
  ├─ User.objects.filter(
  │    is_active=False, updated_at__lt=cutoff
  │  )
  └─ For each expired user:
     user.delete()  → CASCADE deletes ALL related data:
       Dreams, Goals, Tasks, Conversations, Messages,
       Notifications, BuddyPairings, CirclePosts,
       Inventory, Friendships, Follows, etc.
```

### Key Detail

Account deletion uses a **30-day grace period**. During soft-delete, PII is anonymized (display_name becomes "Deleted User", email becomes `deleted_{uuid}@deleted.stepora.app`). After 30 days, the `hard_delete_expired_accounts` Celery task permanently removes the user and all related data via CASCADE deletion.

---

## Flow 13: Calendar & Scheduling

**Entry**: `POST /api/calendar/events/`
**Apps touched**: calendar, dreams, notifications

### Create Event with Conflict Detection

```
POST /api/calendar/events/
  │  body: { title, description, start_time, end_time, task, location,
  │          reminder_minutes_before, is_recurring, recurrence_rule, force }
  ▼
CalendarEventViewSet.create(request)                 apps/calendar/views.py
  ├─ Permission: IsAuthenticated
  ├─ Conflict check:                                 apps/calendar/views.py
  │    _check_conflicts(user, start_time, end_time)
  │    Queries: CalendarEvent.objects.filter(
  │      user, status='scheduled',
  │      start_time__lt=end_time, end_time__gt=start_time
  │    )
  │    If conflicts exist and force=False:
  │      Return 409 with conflicting events + hint to set force=true
  └─ CalendarEvent.objects.create(                   apps/calendar/models.py
       user, task, title, description, start_time, end_time,
       location, reminder_minutes_before, status='scheduled',
       is_recurring, recurrence_rule
     )
```

### Recurring Events

```
generate_recurring_events()                          apps/calendar/tasks.py
  │  Runs nightly via Celery beat
  ▼
  ├─ Horizon: now() + 14 days
  ├─ For each parent event (is_recurring=True, parent_event=None):
  │    Parse recurrence_rule: { frequency, interval, end_date }
  │    frequency: 'daily' | 'weekly' | 'monthly'
  │    Find latest existing instance start_time
  │    Generate instances up to horizon:
  │      CalendarEvent.objects.create(
  │        parent_event=parent, is_recurring=False,
  │        title, description, duration same as parent,
  │        start_time=next occurrence, status='scheduled'
  │      )
  └─ Returns: count of instances created
```

### Reschedule Event

```
PATCH /api/calendar/events/{id}/reschedule/
  │  body: { start_time, end_time, force }
  ▼
CalendarEventViewSet.reschedule(request, pk)         apps/calendar/views.py
  ├─ Conflict check (same as create)
  ├─ event.start_time = new_start
  │  event.end_time = new_end
  │  event.status = 'scheduled'
  │  event.save()
  └─ If event.task exists:
     event.task.scheduled_date = new_start
     event.task.save(update_fields=['scheduled_date'])
```

### Google Calendar Sync (Bidirectional)

```
POST /api/calendar/google/sync/
  ▼
GoogleCalendarSyncView.post(request)                 apps/calendar/views.py
  └─ sync_google_calendar.delay(integration_id)      apps/calendar/tasks.py
       ├─ Push: Stepora events → Google Calendar
       │    For events modified since last_sync_at:
       │      service.push_event(event)
       └─ Pull: Google Calendar → Stepora
            service.pull_events()
            For each Google event not already in DB:
              CalendarEvent.objects.create(...)

# OAuth flow:
GET  /api/calendar/google/auth/     → returns auth_url for OAuth2
POST /api/calendar/google/callback/ → exchanges code for tokens
     GoogleCalendarIntegration.objects.update_or_create(
       user, access_token, refresh_token, token_expiry, sync_enabled=True
     )
```

### Smart Time Slot Suggestions

```
GET /api/calendar/suggest-time-slots/?date=YYYY-MM-DD&duration_mins=60
  ▼
CalendarViewSet.suggest_time_slots(request)          apps/calendar/views.py
  ├─ Collects busy intervals:
  │    CalendarEvent.objects.filter(user, date, status='scheduled')
  │    TimeBlock.objects.filter(user, day_of_week, block_type='blocked')
  ├─ Scans 8:00 AM to 10:00 PM window
  ├─ Adds buffer (default 15 minutes) between events
  └─ Returns up to 10 open slots: [{ start, end }, ...]
```

### iCal Export

```
GET /api/calendar/ical/{feed_token}/
  ▼
ICalFeedView.get(request, feed_token)                apps/calendar/views.py
  ├─ Auth: via secret feed_token (not user session)
  ├─ Generates VCALENDAR format (past 30 days to next 90 days)
  └─ Returns: text/calendar response
```

### Key Detail

**Conflict detection** is built into event creation and rescheduling — conflicting events are returned as a 409 response with a `force=true` override option. Smart time slot suggestions account for existing events, blocked time blocks, and configurable buffer time.

---

## Flow 14: Two-Factor Authentication

**Entry**: `POST /api/users/2fa/setup/`
**Apps touched**: users

### Step-by-step

```
POST /api/users/2fa/setup/
  ▼
UserViewSet.setup_2fa(request)                       apps/users/views.py
  ├─ Check: user.totp_enabled must be False
  ├─ secret = pyotp.random_base32()
  ├─ user.totp_secret = secret                       apps/users/models.py
  │  user.save(update_fields=['totp_secret'])
  ├─ totp = pyotp.TOTP(secret)
  ├─ uri = totp.provisioning_uri(
  │    name=user.email, issuer_name='Stepora'
  │  )
  └─ Returns: { secret, otpauth_url }
     (Client displays QR code from otpauth_url)
```

### Verify Setup

```
POST /api/users/2fa/verify-setup/
  │  body: { code }
  ▼
UserViewSet.verify_2fa_setup(request)                apps/users/views.py
  ├─ Check: user.totp_secret must exist
  ├─ totp = pyotp.TOTP(user.totp_secret)
  ├─ totp.verify(code)
  │    If valid:
  │      user.totp_enabled = True
  │      user.save(update_fields=['totp_enabled'])
  │      Returns: { message: '2FA enabled successfully.' }
  └─  If invalid: 400 "Invalid code."
```

### Generate Backup Codes

```
POST /api/users/2fa/backup-codes/
  ▼
UserViewSet.generate_backup_codes(request)           apps/users/views.py
  ├─ Check: user.totp_enabled must be True
  ├─ codes = [secrets.token_hex(4) for _ in range(10)]
  ├─ hashed = [sha256(code) for code in codes]
  ├─ user.backup_codes = hashed                      apps/users/models.py
  │  user.save(update_fields=['backup_codes'])
  └─ Returns: { backup_codes: [plaintext codes] }
     (Shown once — cannot be retrieved again)
```

### Login with 2FA

```
POST /api/auth/login/
  │  body: { email, password }
  ▼
core.auth LoginView                                    core/auth/views.py
  ├─ If user.totp_enabled:
  │    Returns challenge token (signed, 5min TTL)
  │    Client must call POST /api/auth/2fa-challenge/ with OTP
  │    pyotp.TOTP(user.totp_secret).verify(code)
  │    Or: check code against backup_codes (PBKDF2 hash match)
  └─ Returns JWT tokens (access + refresh) on success
```

### Disable 2FA

```
POST /api/users/2fa/disable/
  │  body: { password, code }
  ▼
UserViewSet.disable_2fa(request)                     apps/users/views.py
  ├─ Verify: user.check_password(password)
  ├─ Verify: user.totp_enabled == True
  ├─ totp = pyotp.TOTP(user.totp_secret)
  │  totp.verify(code)
  └─ user.totp_enabled = False
     user.totp_secret = ''
     user.backup_codes = None
     user.save(update_fields=['totp_enabled', 'totp_secret', 'backup_codes'])
```

### Key Fields (User Model)

| Field | Type | Description |
| --- | --- | --- |
| `totp_enabled` | BooleanField | Whether 2FA is active |
| `totp_secret` | CharField | TOTP shared secret (base32) |
| `backup_codes` | JSONField | List of sha256-hashed one-time recovery codes |

---

## Flow 15: Password Reset & Email Change

**Entry**: `POST /api/auth/password/reset/` (core.auth) or `POST /api/users/change-email/`
**Apps touched**: users

### Password Reset

```
POST /api/auth/password/reset/
  │  body: { email }
  ▼
core.auth PasswordResetView                            core/auth/views.py
  ├─ Generates HMAC password reset token (core/auth/tokens.py)
  ├─ Sends email asynchronously via Celery task (core/auth/tasks.py)
  └─ Email contains reset link with uid + token

POST /api/auth/password/reset/confirm/
  │  body: { uid, token, new_password1, new_password2 }
  ▼
core.auth PasswordResetConfirmView                     core/auth/views.py
  ├─ Validates: HMAC token is valid and not expired
  ├─ Validates: new password meets strength requirements
  └─ user.set_password(new_password)
     user.save()
```

### Email Change

```
POST /api/users/change-email/
  │  body: { new_email, password }
  ▼
UserViewSet.change_email(request)                    apps/users/views.py
  ├─ Validates: new_email not empty
  ├─ Verify: user.check_password(password)
  ├─ Check: new_email not already taken by another user
  ├─ Invalidate previous pending requests:
  │    EmailChangeRequest.objects.filter(
  │      user=request.user, is_verified=False
  │    ).delete()
  ├─ Create new request:
  │    token = secrets.token_urlsafe(64)
  │    EmailChangeRequest.objects.create(             apps/users/models.py
  │      user, new_email, token,
  │      expires_at=now() + 24 hours
  │    )
  └─ send_email_change_verification.delay(           apps/users/tasks.py
       user_id, new_email, token
     )
     Sends email with verification link:
       {FRONTEND_URL}/verify-email/{token}
       Expires in 24 hours
```

### Email Verification (Completing the Change)

```
# When user clicks the verification link:
GET /verify-email/{token}
  ▼
  ├─ Lookup: EmailChangeRequest(token=token, is_verified=False)
  ├─ Check: not expired (expires_at > now())
  ├─ user.email = request.new_email
  │  user.save(update_fields=['email'])
  ├─ request.is_verified = True
  │  request.save()
  └─ (Optional) Notification sent to old email address
```

### Key Model: EmailChangeRequest

| Field | Type | Description |
| --- | --- | --- |
| `user` | ForeignKey(User) | The user requesting the change |
| `new_email` | EmailField | The new email address to verify |
| `token` | CharField(unique) | 64-byte URL-safe verification token |
| `is_verified` | BooleanField | Whether the change has been confirmed |
| `expires_at` | DateTimeField | Token expiry (24 hours from creation) |

---

## Flow 16: Real-Time Messaging Pipeline

**Entry**: WebSocket connection to `ws/ai-chat/`, `ws/buddy-chat/`, or `ws/circle-chat/`
**Apps touched**: conversations, buddies, circles, core, notifications

### Step-by-step (all 3 consumers)

```
Client connects to ws/{consumer-path}/{id}/?token=<auth_token>
  │
  ▼
1. Connection accepted (WebSocket handshake)              apps/{app}/consumers.py
  │  Consumer.__init__() → _init_rate_limit() → _init_auth()
  │                                                       core/consumers.py
  ▼
2. Client sends authenticate message                      core/consumers.py
  │  {"type": "authenticate", "token": "<auth_token>"}
  │  → _handle_authenticate_message()
  │  → get_user_from_token()                              core/websocket_auth.py
  │  → _setup_authenticated() → _setup_authenticated_inner()
  ▼
3. Consumer-specific setup:                               apps/{app}/consumers.py
  │
  │  AIChatConsumer:
  │    → _load_and_verify_conversation() — verify ownership
  │    → reject buddy_chat type (close code 4004)
  │    → join group: ai_chat_{conversation_id}
  │
  │  BuddyChatConsumer:
  │    → _load_and_verify_pairing() — verify active BuddyPairing
  │    → _is_blocked() — bidirectional block check          core/consumers.py
  │    → _get_or_create_conversation() — find/create buddy_chat Conversation
  │    → join group: buddy_chat_{pairing_id}
  │
  │  CircleChatConsumer:
  │    → _verify_membership() — check CircleMembership exists
  │    → _get_blocked_user_ids() — load blocked IDs for filtering
  │    → join group: circle_chat_{circle_id}
  ▼
4. Client sends message                                   apps/{app}/consumers.py
  │  {"type": "message", "message": "Hello!"}
  │  → receive() → type routing
  ▼
5. Rate limit check                                       core/consumers.py
  │  _is_rate_limited() — sliding window (30/60s buddy, 20/60s circle)
  │  If limited: send error, return
  ▼
6. Content moderation                                     core/consumers.py
  │  _moderate_content(content) → ContentModerationService  core/moderation.py
  │  If flagged: send moderation rejection, return
  ▼
7. Save message                                           apps/{app}/consumers.py
  │  AIChatConsumer: Conversation.add_message() → AI response stream
  │  BuddyChatConsumer: _save_message() → Conversation/Message
  │  CircleChatConsumer: _save_message() → CircleMessage
  ▼
8. Broadcast to group                                     apps/{app}/consumers.py
  │  channel_layer.group_send(group_name, {type, message, sender_id, ...})
  │  → All connected consumers in group receive via handler
  │  CircleChatConsumer: filters messages from blocked senders
  ▼
9. FCM push (BuddyChatConsumer only)                      apps/buddies/consumers.py
  │  _send_push_notification() — if partner not connected,
  │  send Firebase Cloud Messaging push notification
```

### Key Detail

All 3 chat consumers share the same mixin-based architecture from `core/consumers.py`. The pipeline is: connect → authenticate → setup → receive → rate limit → moderate → save → broadcast → (optional) push. Block enforcement differs: buddy chat re-checks blocks on every message; circle chat filters on receive.

---

## Flow 17: Circle Voice/Video Call

**Entry**: `POST /api/circles/{id}/call/start/`
**Apps touched**: circles, core, notifications

### Step-by-step

```
POST /api/circles/{id}/call/start/
  │  body: { call_type: "voice"|"video" }
  ▼
CircleViewSet.start_call(request, pk)                    apps/circles/views.py
  ├─ Permission: IsAuthenticated, member of circle
  ├─ Check: no active call already exists for this circle
  ├─ CircleCall.objects.create(                           apps/circles/models.py
  │    circle, initiator=request.user, call_type,
  │    status='active', agora_channel='circle_{uuid}',
  │    started_at=now()
  │  )
  ├─ CircleCallParticipant.objects.create(
  │    call, user=request.user, joined_at=now()
  │  )
  ├─ Generate Agora RTC token:
  │    token = generate_rtc_token(
  │      app_id=AGORA_APP_ID,
  │      app_certificate=AGORA_APP_CERTIFICATE,
  │      channel=call.agora_channel,
  │      uid=user.id
  │    )
  ├─ Broadcast to WebSocket group:
  │    channel_layer.group_send(
  │      'circle_chat_{circle_id}',
  │      {type: 'call_started', call: serialized_call}
  │    )
  ├─ FCM push to circle members:
  │    Send push notification to all members not connected
  └─ Returns: { call, agora_token, agora_channel }

POST /api/circles/{id}/call/join/
  ▼
CircleViewSet.join_call(request, pk)                     apps/circles/views.py
  ├─ Find active CircleCall for circle
  ├─ CircleCallParticipant.objects.create(
  │    call, user=request.user, joined_at=now()
  │  )
  ├─ Update call.max_participants if new peak
  ├─ Generate Agora RTC token for joiner
  └─ Returns: { call, agora_token, agora_channel }

POST /api/circles/{id}/call/leave/
  ▼
CircleViewSet.leave_call(request, pk)                    apps/circles/views.py
  ├─ Find participant record
  └─ participant.left_at = now()

POST /api/circles/{id}/call/end/
  ▼
CircleViewSet.end_call(request, pk)                      apps/circles/views.py
  ├─ call.status = 'completed'
  ├─ call.ended_at = now()
  ├─ call.duration_seconds = (ended_at - started_at).seconds
  └─ Update max_participants from count of participants
```

### Key Detail

Circle calls use **Agora.io** for real-time communication. The server generates short-lived RTC tokens scoped to the call's channel name and user UID. Call state is tracked server-side via `CircleCall` and `CircleCallParticipant` models. When a call starts, both WebSocket broadcast and FCM push ensure all circle members are notified.

> **Setup requirement:** The Agora **Signaling** service must be enabled in the [Agora Console](https://console.agora.io) (select a data center + subscribe to a plan). If not enabled, RTM login fails with error `2010026`. See `DEPLOYMENT.md` for steps.

---

## Flow 18: Dream Post Social Interaction

**Entry**: `POST /api/social/posts/`
**Apps touched**: social, users, notifications

### Step-by-step

```
POST /api/social/posts/
  │  body: { content, dream_id?, gofundme_url?, visibility?, image_url? }
  ▼
DreamPostViewSet.create(request)                         apps/social/views.py
  ├─ Permission: IsAuthenticated
  ├─ Validate via DreamPostCreateSerializer               apps/social/serializers.py
  └─ DreamPost.objects.create(                            apps/social/models.py
       user=request.user, content, dream, gofundme_url,
       visibility='public', likes_count=0, comments_count=0
     )

GET /api/social/posts/feed/
  ▼
DreamPostViewSet.feed(request)                           apps/social/views.py
  ├─ Query: posts from followed users + public posts
  ├─ Exclude: blocked users (bidirectional check)
  ├─ Annotate: has_liked, has_encouraged for request.user
  ├─ Order: -created_at
  └─ Paginate: StandardResultsSetPagination (20/page)

POST /api/social/posts/{id}/like/
  ▼
DreamPostViewSet.like(request, pk)                       apps/social/views.py
  ├─ Toggle: DreamPostLike.objects.get_or_create / delete
  ├─ Update: post.likes_count (increment or decrement)
  └─ Create Notification (type: 'dream_post_like')       apps/notifications/

POST /api/social/posts/{id}/comment/
  │  body: { content, parent? }
  ▼
DreamPostViewSet.comment(request, pk)                    apps/social/views.py
  ├─ DreamPostComment.objects.create(                     apps/social/models.py
  │    post, user=request.user, content, parent (for threading)
  │  )
  ├─ post.comments_count += 1
  └─ Create Notification (type: 'dream_post_comment')    apps/notifications/

POST /api/social/posts/{id}/encourage/
  │  body: { encouragement_type, message? }
  ▼
DreamPostViewSet.encourage(request, pk)                  apps/social/views.py
  ├─ DreamEncouragement.objects.create(                   apps/social/models.py
  │    post, user=request.user, encouragement_type, message
  │  )
  │  Types: you_got_this, keep_going, inspired, proud, fire
  └─ Create Notification (type: 'dream_post_encouragement')

POST /api/social/posts/{id}/share/
  ▼
DreamPostViewSet.share(request, pk)                      apps/social/views.py
  └─ post.shares_count += 1
```

### Key Detail

Dream posts support three distinct interaction types: **likes** (simple toggle), **comments** (threaded via parent FK), and **encouragements** (5 typed reactions distinct from likes). All interactions trigger notifications. The feed algorithm shows posts from followed users plus public posts, excluding blocked users, with `has_liked`/`has_encouraged` annotations for the requesting user.
