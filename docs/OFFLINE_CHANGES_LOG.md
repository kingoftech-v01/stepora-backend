# Offline-First Changes Log

> Comprehensive record of all offline-first changes implemented on 2026-03-25.
> Covers web frontend, mobile app, and backend strategy documentation.

---

## 1. Executive Summary

### Before (audit scores)

| Platform | Score | Key Deficiencies |
|---|---|---|
| **Mobile** (`stepora-mobile`) | **2/10** | Queue existed but `flushOfflineQueue()` was never called anywhere. No network detection library. No `NetworkContext`. No `OfflineBanner` component. No React Query persister. `gcTime` defaulted to 5 minutes. No anti-abuse limits. No payment guards. `/store/` purchases could be queued offline. |
| **Web** (`stepora-frontend`) | **4/10** | Queue existed and flushed on reconnect, but `gcTime` was 5 minutes (cache evicted quickly). No flush on page reload. No optimistic UI. Silent data loss on 4xx/5xx during flush. No SW caching for API responses. No payment guards on UI buttons. OfflineBanner showed only offline state (no syncing/synced). `/users/` block was too broad (blocked profile updates). |

### After (implemented changes)

| Platform | Estimated Score | Key Improvements |
|---|---|---|
| **Mobile** | **6/10** | Flush trigger wired (AppState `active` + NetworkContext reconnect). `gcTime` 24h. New `NetworkContext` with periodic connectivity checks. New `OfflineBanner`. Anti-abuse counters (20 tasks, 10 journals). Deduplication. Payment guards on Store/Subscription/Gifting. Optimistic UI for tasks, notifications, social likes, friend requests. Cached user in AsyncStorage. Idempotency keys sent on flush. |
| **Web** | **7/10** | `gcTime` 24h. `networkMode: 'offlineFirst'`. Flush on page load + reconnect. Cache invalidation after flush. 3-state OfflineBanner (offline/syncing/synced). Workbox SW caching for all API GET responses (24h, StaleWhileRevalidate). Refined sensitive patterns. 4xx discard with `dp-sync-error` event. 5xx re-queue with retry count (max 5). Optimistic UI for tasks, calendar events, dream creation, notifications, social likes/comments, friend requests. Payment guards on Subscription/Store/Gifting. New i18n keys (en + fr). |

### What is still NOT implemented

- React Query persistent storage (IndexedDB/AsyncStorage persister) -- cache is still in-memory only
- Full allow-list / block-list system from the strategy doc (implementation uses simplified sensitive patterns)
- Priority-based queue ordering (HIGH/MEDIUM/LOW)
- Conflict resolution UI (bottom sheet / modal for reviewing conflicts)
- Server-side `completed_at` acceptance on task/goal/milestone endpoints
- Idempotency middleware on backend
- Sync metadata endpoint (`GET /api/v1/sync/status/`)
- Background sync (Headless JS / WorkManager / BGTaskScheduler)
- FormData offline support (file uploads)
- 7-day queue TTL (still 24h)
- 100-item queue cap

---

## 2. Web Frontend Changes

**Repo**: `stepora-frontend`
**Commit**: `e0f6176` -- "Offline-first: core infrastructure + payment guards + optimistic UI + SW caching"
**Total**: 19 files changed, +645 / -85 lines

### Infrastructure

| File | Change |
|---|---|
| `src/main.jsx` | `gcTime` changed from `5 min` to `24 hours`. Added `networkMode: 'offlineFirst'` to default query options. |
| `src/context/NetworkContext.jsx` | Added `flushAndInvalidate()` helper that flushes queue then invalidates `['dreams']`, `['dashboard']`, `['notifications']` caches. Added flush on mount when `navigator.onLine && queueCount > 0` (handles page reload with pending items). Changed reconnect handler from bare `flushOfflineQueue()` to `flushAndInvalidate(queryClient)`. Imported `useQueryClient`. |
| `src/services/api.js` | **Sensitive patterns**: Split `/users/` into specific sub-paths (`/users/delete-account`, `/users/change-email`, `/users/2fa/`, `/users/export`). Added `/store/purchase`, `/store/equip`, `/gamification/streak-freeze`, `/referrals/redeem`, `/leagues/claim`. **Queue item**: Added `id` field (base36 timestamp + random suffix) and `retryCount` field. **Flush logic**: Replaced silent discard with 3-way error handling: 4xx discards item + dispatches `dp-sync-error` CustomEvent; 5xx re-queues with incremented `retryCount` (max 5); unknown errors re-queue as-is. **Idempotency**: Sends `X-Idempotency-Key: item.id` header on flush requests. |
| `vite.config.js` | Added two Workbox `runtimeCaching` rules: `StaleWhileRevalidate` for `api.stepora.app/api/v1/*` and `dpapi.jhpetitfrere.com/api/*` with `api-cache` bucket (200 max entries, 24h TTL, cacheable statuses 0 and 200). |

### UI Components

| File | Change |
|---|---|
| `src/components/shared/OfflineBanner.jsx` | Complete rewrite. 3 states: **offline** (amber WifiOff icon), **syncing** (blue spinning RefreshCw icon + queue count), **synced** (green Check icon, auto-hides after 2.5s). Tracks `queueCount` transitions to detect flush completion. Added CSS `@keyframes dp-spin` for spinner. |
| `src/components/shared/SubscriptionUpgradeModal.jsx` | Imports `useNetwork` and `useToast`. Blocks `handleUpgrade` when offline with error toast: `t('offline.actionRequiresInternet')`. |

### Optimistic UI Mutations

| File | Mutation | Optimistic Behavior |
|---|---|---|
| `src/pages/dreams/DreamDetail/useDreamDetailScreen.js` | `taskCompleteMut` | Toggles task `status` between `completed`/`pending` in `['dream', id]` cache. Rolls back on error. |
| `src/pages/dreams/DreamCreateScreen/useDreamCreateScreen.js` | Dream creation (post-success) | Inserts newly created dream at top of `['dreams']` cache so it appears immediately on list navigation. |
| `src/pages/calendar/CalendarScreen/useCalendarScreen.js` | `deleteEventMut` | Optimistically removes event from `['calendar-events']` cache. Rolls back on error. |
| `src/pages/calendar/CalendarScreen/useCalendarScreen.js` | `createEventMut` | Inserts optimistic event with temp ID into `['calendar-events']` cache. Rolls back on error. |
| `src/pages/notifications/NotificationsScreen/useNotificationsScreen.js` | `markAllReadMut` | Sets all notifications `isRead: true` in paginated cache. Sets `['unread']` count to 0. Rolls back on error. |
| `src/pages/notifications/NotificationsScreen/useNotificationsScreen.js` | `markReadMut` | Sets single notification `isRead: true`. Decrements `['unread']` count. Rolls back on error. |
| `src/pages/social/PostDetailScreen/usePostDetailScreen.js` | `likeMut` | Toggles `hasLiked`/`isLiked` and increments/decrements `likesCount` in `['post-detail', id]` cache. |
| `src/pages/social/PostDetailScreen/usePostDetailScreen.js` | `commentMut` | Appends optimistic comment to `['post-comments', id]`. Increments `commentsCount` on post detail. Clears input. |
| `src/pages/social/SocialHub/useSocialHubScreen.js` | `likePostMut` | Toggles like on posts in `['social-posts-feed']` cache. |
| `src/pages/social/SocialHub/useSocialHubScreen.js` | `likeEventMut` | Toggles like on feed events in `['feed']` cache. |
| `src/pages/social/FriendRequestsScreen/useFriendRequestsScreen.js` | `handleAccept` | Removes accepted request from `['friend-requests-received']` cache. Rolls back on error. |
| `src/pages/social/FriendRequestsScreen/useFriendRequestsScreen.js` | `handleDecline` | Removes declined request from `['friend-requests-received']` cache. Rolls back on error. |
| `src/pages/social/FriendRequestsScreen/useFriendRequestsScreen.js` | `handleCancelSent` | Removes cancelled request from `['friend-requests-sent']` cache. Rolls back on error. |
| `src/pages/social/UserProfileScreen/useUserProfileScreen.js` | Various social mutations | Optimistic follow/unfollow/friend request with cache updates. |

### Payment Guards (Offline Block)

| File | Guarded Action |
|---|---|
| `src/pages/store/SubscriptionScreen/useSubscriptionScreen.js` | Checkout, cancel, reactivate, change plan -- blocked when offline. |
| `src/pages/store/StoreScreen/useStoreScreen.js` | XP purchase, equip item -- blocked when offline. |
| `src/pages/store/GiftingScreen/useGiftingScreen.js` | Send gift, claim gift -- blocked when offline. |
| `src/components/shared/SubscriptionUpgradeModal.jsx` | Upgrade navigation -- blocked when offline. |

### i18n

| File | Keys Added |
|---|---|
| `src/i18n/en.json` | `offline.actionRequiresInternet`, `offline.syncComplete`, `offline.syncFailed`, `offline.syncing` |
| `src/i18n/fr.json` | Same 4 keys in French |

---

## 3. Mobile Changes

**Repo**: `stepora-mobile`
**Commit**: `21ce8410` -- "Offline-first: flush trigger, NetworkContext, OfflineBanner, payment guards, anti-abuse"
**Total**: 12 files changed, +565 / -77 lines

### Infrastructure

| File | Change |
|---|---|
| `src/App.jsx` | Added `AppState` listener: calls `flushOfflineQueue()` when app state becomes `'active'`. Added `gcTime: 1000 * 60 * 60 * 24` (24 hours) to QueryClient config. Wrapped app in `<NetworkProvider>`. Added `<OfflineBanner />` above `<RootNavigator>`. Imported `AppState`, `flushOfflineQueue`, `NetworkProvider`, `OfflineBanner`. |
| `src/context/NetworkContext.jsx` | **NEW FILE** (99 lines). Uses periodic fetch-based connectivity checks (`HEAD /api/health/` every 15 seconds) since `@react-native-community/netinfo` is not installed. Provides `isOnline` and `queueCount` via React Context. Auto-flushes queue on reconnect (when `wasOffline` transitions to online). Checks connectivity on `AppState` foreground. |
| `src/context/AuthContext.jsx` | Caches critical user fields (`id`, `displayName`, `avatarUrl`, `onboardingCompleted`, `subscription`) to `AsyncStorage` under `dp-cached-user` on every successful `USERS.ME` fetch. Loads cached user as initial state before network fetch (prevents blank profile on cold start offline). Clears cached user on logout. Calls `flushOfflineQueue()` after successful `fetchUser`. |
| `src/services/api.js` | **Sensitive patterns**: Same refinement as web -- split `/users/` into specific sub-paths, added `/store/purchase`, `/store/equip`, `/gamification/streak-freeze`, `/referrals/redeem`, `/leagues/claim`. **Anti-abuse counters**: Session-scoped `_offlineTaskCount` (max 20) and `_offlineJournalCount` (max 10), reset on successful flush. **Deduplication**: If queue already has item with same URL + method, replaces it instead of appending. **Queue item**: Added `id` field and `retryCount` field. **Flush logic**: 5xx errors re-queue with incremented `retryCount` (max 5); 4xx and max-retry items discarded. Counters reset after flush. **Idempotency**: Sends `X-Idempotency-Key: item.id` header. |

### New Components

| File | Description |
|---|---|
| `src/components/shared/OfflineBanner.js` | **NEW FILE** (94 lines). Two components: `OfflineBanner` (default export) -- red banner when offline (with pending count), orange when syncing; `OfflineDataBanner` (named export) -- dismissible banner for screens showing cached/stale data. Uses React Native `View`, `Text`, `TouchableOpacity`, `StyleSheet`. |

### Optimistic UI Mutations

| File | Mutation | Optimistic Behavior |
|---|---|---|
| `src/screens/dreams/useDreamDetailScreen.js` | `taskCompleteMut` | Toggles task `completed`/`status` across the milestone > goal > task hierarchy in `['dream', id]` cache. Rolls back on error via `onMutate` context. |
| `src/screens/notifications/NotificationsScreen.js` | `markAllReadMut` | Sets all notifications `isRead: true` in paginated `['notifications']` cache. Rolls back on error. |
| `src/screens/notifications/NotificationsScreen.js` | `markReadMut` | Sets single notification `isRead: true` in paginated cache. Rolls back on error. |
| `src/screens/social/CommunityScreen.js` | `likeMut` | Toggles `isLiked`/`is_liked` and adjusts `likesCount`/`likes_count` in `['social-posts-feed']` paginated cache. |
| `src/screens/social/FriendRequestsScreen.js` | `acceptMut` | Marks request as accepted in local state + optimistic cache removal. Full `onMutate`/`onError`/`onSettled` pattern. |
| `src/screens/social/FriendRequestsScreen.js` | `declineMut` | Marks request as declined + optimistic cache removal. Full pattern with rollback. |
| `src/screens/social/FriendRequestsScreen.js` | `cancelSentMut` | Marks sent request as cancelled + optimistic cache removal. Full pattern with rollback. |

### Payment Guards (Offline Block)

| File | Guarded Actions |
|---|---|
| `src/screens/store/StoreScreen.js` | `handleBuy`, `handleEquip`, `toggleWishlist`, refund confirmation -- all blocked with `Alert.alert('Offline', ...)` when `!isOnline`. |
| `src/screens/subscription/SubscriptionScreen.js` | Cancel pending change, reactivate subscription -- blocked with `Alert.alert` when offline. |
| `src/screens/store/GiftingScreen.js` | `handleSendGift`, `handleClaimGift` -- blocked with `Alert.alert` when offline. |

---

## 4. Backend Changes

**Repo**: `stepora`
**Commit**: `0351636` -- "Add offline-first sync strategy document"
**Total**: 1 file changed, +1427 lines (documentation only)

| File | Description |
|---|---|
| `docs/OFFLINE_SYNC_STRATEGY.md` | Complete implementation-ready strategy document (1427 lines). Covers: queue architecture with priority/dedup/cap, block list (auth, payments, AI, account deletion, streak freeze), allow list (25+ endpoints with priority), conflict resolution strategy, anti-abuse counters, UI requirements, platform-specific notes, 4-week migration path, testing checklist. |

**No backend code changes were made in this round.** The strategy document specifies future backend changes:

- Accept `completed_at` on task/goal/milestone completion endpoints (for offline timestamp)
- `X-Idempotency-Key` middleware (store processed keys in Redis, 24h TTL)
- `GET /api/v1/sync/status/` endpoint for gamification state reconciliation

---

## 5. Security: Block List

The following actions require an internet connection and are blocked from the offline queue. When attempted offline, the user sees an error message.

### Blocked by Sensitive Patterns (both web and mobile)

| Pattern | Reason |
|---|---|
| `/auth/` | Authentication requires server session validation |
| `/2fa/` | Two-factor auth requires server-side TOTP verification |
| `/password/` | Password changes require current password verification |
| `/users/delete-account` | Irreversible account deletion |
| `/users/change-email` | Requires server-side email verification flow |
| `/users/2fa/` | 2FA setup/disable is security-critical |
| `/users/export` | Data export generates server-side files |
| `/conversations/` | AI and friend chat require server-side processing |
| `/social/report` | Abuse reports require immediate server processing |
| `/export` | Data export endpoints |
| `/checkout` | Stripe checkout requires live payment processing |
| `/subscription/` | All subscription changes require Stripe API |
| `/store/purchase` | XP/item purchases require server-side balance validation |
| `/store/equip` | Item equipping requires server-side inventory validation |
| `/gamification/streak-freeze` | Streak freeze requires server-side cooldown + eligibility check |
| `/referrals/redeem` | Referral redemption requires server validation |
| `/leagues/claim` | League reward claiming requires server validation |

### Blocked by UI Guards (buttons disabled or show error)

| Screen | Actions Blocked |
|---|---|
| SubscriptionScreen | Checkout, cancel, reactivate, change plan |
| StoreScreen | Buy, equip, wishlist toggle, refund request |
| GiftingScreen | Send gift, claim gift |
| SubscriptionUpgradeModal | Upgrade navigation |

### Strategy Doc: Additional Blocks (not yet implemented)

The strategy document specifies a more comprehensive block list including:
- All AI endpoints (`/api/ai/`)
- Plan generation (`generate_plan`, `generate_two_minute_start`, `generate_vision`)
- Calibration endpoints (`start_calibration`, `answer_calibration`)
- Smart analysis (`smart-analysis`, `auto-categorize`, `refine`)
- Smart scheduling (`smart-schedule`, `suggest-time-slots`)
- Morning briefing, motivation, notification timing, check-in
- These are currently not explicitly blocked but would fail naturally (server returns error)

---

## 6. Security: Anti-Abuse

### Mobile: Session-Scoped Counters

Implemented in `src/services/api.js`:

| Counter | Limit | Scope | Reset |
|---|---|---|---|
| `_offlineTaskCount` | 20 per session | Tracks task PATCH/PUT mutations containing `/tasks/` in URL | Reset to 0 after `flushOfflineQueue()` completes |
| `_offlineJournalCount` | 10 per session | Tracks journal POST mutations containing `/journal/` in URL | Reset to 0 after `flushOfflineQueue()` completes |

When a limit is reached, the mutation is silently dropped with a console warning. The queue item is not created.

### Both Platforms: Deduplication

- **Mobile**: If a queue item with the same `url + method` already exists, it is replaced (not appended). This prevents duplicate task completions and redundant edits.
- **Web**: Queue items now have an `id` field used as `X-Idempotency-Key` header during flush, allowing the server to detect and reject duplicate POST requests.

### Both Platforms: Retry Cap

- Queue items have a `retryCount` field starting at 0.
- On 5xx server errors during flush, `retryCount` is incremented and the item is re-queued.
- After 5 failed retries, the item is permanently discarded.
- On 4xx client errors, the item is immediately discarded (it will never succeed).

### Web: Error Events

- When a 4xx item is discarded during flush, a `dp-sync-error` CustomEvent is dispatched with `{ url, status, message }`.
- When max retries are reached, same event is dispatched with message `'Max retries exceeded'`.
- These events can be consumed by any UI component for user notification.

### Strategy Doc: Additional Anti-Abuse (not yet implemented)

The strategy document specifies:
- Per-task-ID deduplication (same task cannot be completed twice offline)
- Habit completion shares the 20-task limit
- `checkAbuseLimit()` function returning `{ allowed, reason }` per endpoint
- Server-side timestamp validation (reject completions >24h old or with future timestamps)
- 50ms delay between flush requests to prevent burst
- 100-item queue cap with lowest-priority eviction

---

## 7. Before vs After Table

| Feature | Before (Web) | After (Web) | Before (Mobile) | After (Mobile) |
|---|---|---|---|---|
| **Offline queue** | Exists, flushes on reconnect | Flushes on reconnect + page load; retry logic for 5xx; 4xx discard with event | Exists, **never flushed** | Flushes on AppState active + NetworkContext reconnect |
| **gcTime** | 5 minutes | 24 hours | 5 min (default) | 24 hours |
| **networkMode** | Default (pauses queries offline) | `offlineFirst` (serves cache offline) | Default | Default (unchanged) |
| **Offline banner** | Shows only "offline" state | 3 states: offline / syncing N / all synced | None (only i18n keys existed) | New component: offline + pending count / syncing |
| **Queue count display** | Computed but never shown | Shown in OfflineBanner during sync | Not computed | Shown in OfflineBanner |
| **Task completion** | Wait for server response | Optimistic toggle with rollback | Wait for server response | Optimistic toggle with rollback |
| **Social likes** | Wait for server response | Optimistic toggle on posts + feed | Wait for server response | Optimistic toggle on feed posts |
| **Comments** | Wait for server response | Optimistic append with user info | No change | No change |
| **Notifications mark-read** | Wait for server response | Optimistic mark + unread count decrement | Wait for server response | Optimistic mark in paginated cache |
| **Friend requests** | Immediate state update, no cache rollback | Optimistic cache removal + full rollback on error | Immediate state update, no cache rollback | Full useMutation with onMutate/onError/onSettled |
| **Calendar events** | No optimistic UI | Optimistic create (temp ID) + delete (remove from cache) | No change | No change |
| **Dream creation** | No cache update on success | Inserts new dream at top of list cache post-success | No change | No change |
| **SW API caching** | None -- all GET requests go to network | StaleWhileRevalidate for all `/api/v1/*` and `/api/*` GET responses (24h, 200 entries) | N/A | N/A |
| **Store purchases offline** | Silently queued (vulnerability) | Blocked -- button shows error toast | Silently queued (vulnerability) | Blocked -- Alert.alert shown |
| **Subscription offline** | No UI guard (queue exclusion only) | Button disabled + error toast | No UI guard | Alert.alert shown |
| **Gifting offline** | No UI guard | Blocked with error toast | No UI guard | Alert.alert shown |
| **Sensitive pattern: /users/** | Blocked ALL /users/ (too broad) | Split: specific sub-paths blocked, profile update allowed | Same | Same refinement |
| **Flush error handling** | Silent discard (data loss) | 4xx: discard + emit event; 5xx: re-queue with retry count | Silent discard | 5xx: re-queue (max 5 retries); 4xx: discard |
| **Anti-abuse** | None | None (planned) | None | 20 tasks / 10 journals per session + deduplication |
| **Idempotency key** | Not sent | Sent as `X-Idempotency-Key` header | Not sent | Sent as `X-Idempotency-Key` header |
| **Cached user (cold start)** | No -- blank profile offline | No change (still no persister) | No -- blank profile | User cached in AsyncStorage, loaded as initial state |
| **Network detection** | Browser `navigator.onLine` events | Same (via Capacitor/browser) | None -- only on fetch failure | Periodic HEAD request every 15s + AppState check |
| **Post-flush cache invalidation** | None -- stale data shown | Invalidates dreams, dashboard, notifications caches | None | No explicit invalidation (relies on refetch) |

---

## 8. Known Remaining Gaps

### Critical (high impact)

1. **No React Query persister** -- Cache is still entirely in-memory on both web and mobile. A hard reload (web) or app restart (mobile) while offline produces empty screens. The `gcTime: 24h` helps within a session but does not survive restarts. The strategy doc identifies this as the highest-impact missing piece.

2. **24h queue TTL is too short** -- The strategy doc specifies 7 days for weekend offline scenarios. Current implementation still uses 24h on both platforms.

3. **No queue cap** -- A malicious or buggy client can fill storage with unlimited queue items. Strategy doc specifies 100-item cap with lowest-priority eviction.

4. **No priority-based flush ordering** -- Queue items are flushed FIFO. The strategy doc specifies HIGH > MEDIUM > LOW priority ordering. Task completions (XP-granting) should flush before notification mark-reads.

### Important (medium impact)

5. **No conflict resolution UI** -- Strategy doc specifies conflict review bottom sheet / modal. Currently, 409 Conflict responses are treated as generic errors.

6. **Backend does not accept `completed_at`** -- Offline task completions are sent without timestamps. The server records server-time, not the actual offline completion time.

7. **No idempotency middleware on backend** -- The client sends `X-Idempotency-Key` headers, but the backend does not check them. Duplicate POST requests (journal creation, event creation) can still create duplicate records.

8. **Web: No anti-abuse counters** -- Only mobile has the 20-task / 10-journal session limits. Web has none.

9. **Mobile: `networkMode` not set to `offlineFirst`** -- Web sets this, mobile does not. Mobile React Query will pause queries when it detects offline (via the `onLine` API), potentially showing loading spinners instead of cached data.

10. **Mobile: No `@react-native-community/netinfo`** -- The `NetworkContext` uses periodic `HEAD /api/health/` requests (every 15s) instead of native OS network events. This is less reliable and adds unnecessary network traffic.

### Minor (low impact)

11. **i18n keys only added for en/fr** -- The strategy doc specifies keys for all 16 languages. Other languages will fall back to the key name.

12. **No `OfflineDataBanner` usage** -- The mobile `OfflineBanner.js` exports an `OfflineDataBanner` component for showing "cached data" indicator, but no screen renders it.

13. **No FormData offline support** -- File uploads (avatar, vision board images) fail silently offline because `enqueueOfflineMutation` cannot serialize FormData.

14. **No tab sync on web** -- If multiple tabs are open, only the tab that detects reconnect will flush. Other tabs don't know the queue state changed.

15. **No 50ms throttle between flush requests** -- Strategy doc specifies a delay to prevent burst; not implemented.

16. **Mobile: Gifting/Store/Subscription offline guard uses `try/catch require()`** -- The pattern `try { var net = require(...); } catch(e) {}` is fragile and may tree-shake incorrectly in production builds.

---

## 9. Testing Recommendations

### Manual Testing: Offline Queue

1. **Web -- Queue and flush cycle**:
   - Enable airplane mode (or throttle network to "Offline" in DevTools).
   - Complete 3 tasks, mark 2 notifications as read, like a social post.
   - Verify OfflineBanner shows amber "You're offline" state.
   - Re-enable network.
   - Verify OfflineBanner transitions to blue "Syncing 6 changes..." then green "All synced!".
   - Verify all mutations persisted on server (reload page and check).

2. **Web -- Page reload with pending items**:
   - Go offline, complete 2 tasks.
   - Hard reload the page while still offline.
   - Go online.
   - Verify the `NetworkContext` detects `navigator.onLine && queueCount > 0` and auto-flushes.

3. **Mobile -- AppState flush**:
   - Go offline, complete tasks.
   - Background the app.
   - Re-enable network while app is backgrounded.
   - Foreground the app.
   - Verify `AppState 'active'` triggers `flushOfflineQueue()`.

4. **Mobile -- NetworkContext periodic check**:
   - Go offline. Verify banner appears within 15 seconds.
   - Go online. Verify banner disappears and queue flushes.

### Manual Testing: Payment Guards

5. **Blocked actions offline**:
   - Go offline.
   - Try to: purchase an item in Store, start a subscription checkout, send a gift, upgrade via SubscriptionUpgradeModal.
   - Verify each shows an error message (toast on web, Alert on mobile).
   - Verify NO queue items are created for these actions.

### Manual Testing: Optimistic UI

6. **Task completion toggle**:
   - Go offline.
   - Toggle a task complete/incomplete on DreamDetail screen.
   - Verify the UI updates immediately (checkbox toggles, status changes).
   - Go online.
   - Verify server state matches (reload and check).

7. **Social like toggle**:
   - Go offline.
   - Like a post on SocialHub.
   - Verify like count increments and heart fills immediately.
   - Go online. Verify server state persists.

8. **Notification mark-read**:
   - Go offline.
   - Mark a notification as read.
   - Verify it visually updates immediately.
   - Mark all as read.
   - Verify all notifications show as read.
   - Go online. Verify persisted.

9. **Optimistic rollback**:
   - Mock a server error (e.g., return 403 for task complete).
   - Complete a task.
   - Verify UI updates optimistically, then rolls back when error is received.

### Manual Testing: Anti-Abuse (Mobile Only)

10. **Task limit**:
    - Go offline.
    - Complete 21 tasks (different tasks).
    - Verify the 21st completion is silently dropped (console warning).
    - Go online. Verify only 20 completions sync.

11. **Journal limit**:
    - Go offline.
    - Create 11 journal entries.
    - Verify the 11th is dropped.

12. **Deduplication (Mobile)**:
    - Go offline.
    - Edit the same dream title 3 times.
    - Check AsyncStorage `dp-offline-queue`: should contain only 1 entry for that URL.

### Manual Testing: Service Worker (Web Only)

13. **SW API cache**:
    - Load the dreams list page (triggers GET to `/api/v1/dreams/`).
    - Open DevTools > Application > Cache Storage > `api-cache`.
    - Verify the API response is cached.
    - Go offline.
    - Navigate away and back to dreams list.
    - Verify data appears from SW cache (not blank screen).

14. **SW cache expiry**:
    - Verify `api-cache` entries expire after 24 hours.
    - Verify max 200 entries (older entries evicted).

### Manual Testing: Error Handling

15. **4xx flush discard (Web)**:
    - Queue a mutation that will return 400 (e.g., complete an already-completed task).
    - Go online.
    - Verify the item is discarded (not re-queued).
    - Verify `dp-sync-error` event is dispatched (check in DevTools console).

16. **5xx flush retry**:
    - Queue a mutation that will return 500.
    - Go online.
    - Verify the item is re-queued with `retryCount: 1`.
    - After 5 retries, verify the item is permanently discarded.

### Automated Test Recommendations

17. **Unit tests for `api.js`**:
    - `enqueueOfflineMutation` rejects all sensitive patterns
    - `enqueueOfflineMutation` accepts allowed mutations
    - Deduplication replaces existing items (mobile)
    - Anti-abuse counters enforce limits (mobile)
    - `flushOfflineQueue` handles 4xx/5xx correctly
    - Retry count is respected (max 5)
    - Counter reset after flush (mobile)

18. **Component tests**:
    - `OfflineBanner` renders correct state for offline/syncing/synced
    - Payment guard components disable buttons when `isOnline: false`
    - Optimistic mutations update cache immediately and rollback on error

19. **Integration tests**:
    - Full offline > queue > reconnect > flush > verify cycle
    - Multiple mutations queued and flushed in order
    - Cache invalidation fires after flush (web)

---

## Appendix: File Inventory

### Web Frontend (`stepora-frontend`) -- 19 files

```
src/main.jsx
src/context/NetworkContext.jsx
src/services/api.js
src/components/shared/OfflineBanner.jsx
src/components/shared/SubscriptionUpgradeModal.jsx
src/pages/calendar/CalendarScreen/useCalendarScreen.js
src/pages/dreams/DreamCreateScreen/useDreamCreateScreen.js
src/pages/dreams/DreamDetail/useDreamDetailScreen.js
src/pages/notifications/NotificationsScreen/useNotificationsScreen.js
src/pages/social/FriendRequestsScreen/useFriendRequestsScreen.js
src/pages/social/PostDetailScreen/usePostDetailScreen.js
src/pages/social/SocialHub/useSocialHubScreen.js
src/pages/social/UserProfileScreen/useUserProfileScreen.js
src/pages/store/GiftingScreen/useGiftingScreen.js
src/pages/store/StoreScreen/useStoreScreen.js
src/pages/store/SubscriptionScreen/useSubscriptionScreen.js
src/i18n/en.json
src/i18n/fr.json
vite.config.js
```

### Mobile (`stepora-mobile`) -- 12 files

```
src/App.jsx
src/context/AuthContext.jsx
src/context/NetworkContext.jsx           (NEW)
src/components/shared/OfflineBanner.js   (NEW)
src/services/api.js
src/screens/dreams/useDreamDetailScreen.js
src/screens/notifications/NotificationsScreen.js
src/screens/social/CommunityScreen.js
src/screens/social/FriendRequestsScreen.js
src/screens/store/GiftingScreen.js
src/screens/store/StoreScreen.js
src/screens/subscription/SubscriptionScreen.js
```

### Backend (`stepora`) -- 1 file

```
docs/OFFLINE_SYNC_STRATEGY.md           (NEW)
```
