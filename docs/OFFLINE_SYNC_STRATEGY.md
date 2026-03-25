# Offline-First Sync Strategy

> Implementation-ready design for web (`stepora-frontend`) and mobile (`stepora-mobile`).
> Covers queue architecture, security rules, conflict resolution, UI, and anti-abuse.

---

## Table of Contents

1. [Current State & Gap Analysis](#1-current-state--gap-analysis)
2. [Sync Queue Architecture](#2-sync-queue-architecture)
3. [Security Rules — Block List](#3-security-rules--block-list)
4. [Allow List — Safe to Queue](#4-allow-list--safe-to-queue)
5. [Queue Storage Layer](#5-queue-storage-layer)
6. [Flush & Retry Logic](#6-flush--retry-logic)
7. [Conflict Resolution](#7-conflict-resolution)
8. [Backend Changes](#8-backend-changes)
9. [UI Requirements](#9-ui-requirements)
10. [Anti-Abuse Protections](#10-anti-abuse-protections)
11. [Platform-Specific Notes](#11-platform-specific-notes)
12. [Migration Path](#12-migration-path)
13. [Testing Checklist](#13-testing-checklist)

---

## 1. Current State & Gap Analysis

### What exists today

Both web and mobile already have a basic offline queue:

| Feature | Web (`stepora-frontend`) | Mobile (`stepora-mobile`) |
|---|---|---|
| Storage | `localStorage` (`dp-offline-queue`) | `AsyncStorage` (`dp-offline-queue`) |
| Enqueue trigger | `catch` in `request()` on network error | Same |
| Block list | Substring match: `/auth/`, `/2fa/`, `/password/`, `/delete-account`, `/conversations/`, `/users/`, `/social/report`, `/export`, `/checkout`, `/subscription/` | Same |
| Max age | 24 hours | 24 hours |
| Deduplication | None | None |
| Priority | None (FIFO) | None (FIFO) |
| Queue cap | Unlimited | Unlimited |
| Conflict resolution | None (server response discarded) | None |
| Retry logic | One pass; if still offline, keeps remaining | Same |
| Flush trigger | `NetworkProvider` calls `flushOfflineQueue()` on reconnect | Same (in `NetworkContext`) |
| Queue change event | `dp-offline-queue-change` CustomEvent | Not emitted (AsyncStorage is fire-and-forget) |
| Anti-abuse | None | None |

### Key gaps to address

1. **No priority system** — task completions (XP-granting) treated same as read receipts.
2. **No deduplication** — editing a profile 3 times offline creates 3 queue items.
3. **No queue cap** — malicious or buggy client can fill storage.
4. **Block list too coarse** — `/users/` blocks `PATCH /api/users/update_profile/` which should be allowed.
5. **No conflict resolution** — server-side XP/streak can diverge.
6. **No anti-abuse** — unlimited offline task completions enable XP farming.
7. **Max age too short** — 24h is tight for weekend offline use; spec requires 7 days.
8. **No user feedback** — no banner, no sync count, no conflict review.
9. **Mobile missing queue change events** — `NetworkProvider` cannot show badge count.

---

## 2. Sync Queue Architecture

### Queue item schema

```typescript
interface SyncQueueItem {
  id: string;            // UUID v4 — generated client-side
  url: string;           // API endpoint path (e.g., "/api/dreams/tasks/abc123/")
  method: string;        // HTTP method: "POST" | "PATCH" | "PUT" | "DELETE"
  body: string | null;   // JSON-stringified request body (already snake_case)
  timestamp: number;     // Date.now() at enqueue time
  retryCount: number;    // Starts at 0, incremented on each failed flush attempt
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  entityKey: string;     // Dedup key: `${method}:${url}` (keeps latest per key)
}
```

### Priority levels

| Priority | Endpoints | Rationale |
|---|---|---|
| **HIGH** | Task complete/uncomplete, goal complete, milestone complete, journal entry, focus session complete | These grant XP and affect streaks — must sync ASAP |
| **MEDIUM** | Dream edit, profile edit, calendar event create/edit, settings changes | User data edits — important but not gamification-critical |
| **LOW** | Notification mark-read, mark-all-read, social post like, comment, story view | Side-effects only; can be delayed or lost |

### Constants

```javascript
var SYNC_QUEUE_MAX_ITEMS     = 100;
var SYNC_QUEUE_MAX_AGE_MS    = 7 * 24 * 60 * 60 * 1000;  // 7 days
var SYNC_QUEUE_MAX_RETRIES   = 5;
var SYNC_QUEUE_RETRY_BACKOFF = [1000, 5000, 15000, 60000, 300000]; // ms
```

### Flush order

Items are flushed in this order:
1. **Priority** — HIGH before MEDIUM before LOW
2. **Timestamp** — oldest first within same priority (FIFO per tier)

---

## 3. Security Rules — Block List

These endpoints **must NEVER be queued**. When the user attempts one of these offline, show:
**"This action requires an internet connection."**

```javascript
/**
 * Endpoints that MUST NOT be queued offline.
 * Matched by prefix — if the URL starts with any of these, reject it.
 */
var OFFLINE_BLOCK_PREFIXES = [
  // Auth — session integrity, password, 2FA
  '/api/auth/',

  // Subscriptions — all payment operations
  '/api/subscriptions/',

  // Store purchases — real-money and XP purchases
  '/api/store/purchase',

  // Account deletion — irreversible
  '/api/users/delete-account/',

  // AI endpoints — require server-side OpenAI calls
  '/api/ai/',

  // Referral redemption — server validation required
  '/api/referrals/redeem/',

  // Streak freeze — server must validate cooldown + eligibility
  '/api/gamification/streak-freeze/',

  // Data export — generates server-side files
  '/api/users/export-data/',
];

/**
 * Endpoints matched by regex — for parameterized AI-dependent routes.
 */
var OFFLINE_BLOCK_PATTERNS = [
  // Plan generation (needs AI)
  /\/api\/dreams\/dreams\/[^/]+\/generate_plan\//,
  /\/api\/dreams\/dreams\/[^/]+\/generate_two_minute_start\//,
  /\/api\/dreams\/dreams\/[^/]+\/generate_vision\//,

  // Calibration (needs AI)
  /\/api\/dreams\/dreams\/[^/]+\/start_calibration\//,
  /\/api\/dreams\/dreams\/[^/]+\/answer_calibration\//,

  // Smart analysis / auto-categorize (needs AI)
  /\/api\/dreams\/dreams\/smart-analysis\//,
  /\/api\/dreams\/dreams\/auto-categorize\//,
  /\/api\/dreams\/dreams\/refine\//,

  // Predict obstacles (needs AI)
  /\/api\/dreams\/dreams\/[^/]+\/predict-obstacles\//,

  // Smart scheduling (needs AI)
  /\/api\/calendar\/smart-schedule\//,
  /\/api\/calendar\/suggest-time-slots\//,

  // AI coaching messages
  /\/api\/ai\/conversations\/[^/]+\/send_message\//,
  /\/api\/ai\/conversations\/[^/]+\/send-voice\//,
  /\/api\/ai\/conversations\/[^/]+\/send-image\//,

  // User AI features
  /\/api\/users\/morning-briefing\//,
  /\/api\/users\/motivation\//,
  /\/api\/users\/notification-timing\//,
  /\/api\/users\/check-in\//,

  // 2FA management
  /\/api\/users\/2fa\//,

  // Email change (requires server verification)
  /\/api\/users\/change-email\//,
];
```

### Implementation — `isBlockedOffline(url)`

```javascript
function isBlockedOffline(url) {
  // Check prefix matches
  for (var i = 0; i < OFFLINE_BLOCK_PREFIXES.length; i++) {
    if (url.indexOf(OFFLINE_BLOCK_PREFIXES[i]) === 0) return true;
  }
  // Check regex matches
  for (var j = 0; j < OFFLINE_BLOCK_PATTERNS.length; j++) {
    if (OFFLINE_BLOCK_PATTERNS[j].test(url)) return true;
  }
  return false;
}
```

---

## 4. Allow List — Safe to Queue

These endpoints are **explicitly safe** for offline queuing. Every endpoint not on this list AND not on the block list is treated as **implicitly blocked** (fail-safe default: reject unknown endpoints).

```javascript
/**
 * Allowlist: endpoints safe to queue offline.
 * Each entry defines the URL pattern, allowed methods, and priority.
 */
var OFFLINE_ALLOW_LIST = [
  // ─── HIGH priority (XP / gamification impact) ────────────────
  {
    pattern: /^\/api\/dreams\/tasks\/[^/]+\/complete\/$/,
    methods: ['POST'],
    priority: 'HIGH',
  },
  {
    pattern: /^\/api\/dreams\/tasks\/[^/]+\/$/,
    methods: ['PATCH'],   // toggle is_completed, edit task title/notes
    priority: 'HIGH',
  },
  {
    pattern: /^\/api\/dreams\/goals\/[^/]+\/complete\/$/,
    methods: ['POST'],
    priority: 'HIGH',
  },
  {
    pattern: /^\/api\/dreams\/milestones\/[^/]+\/complete\/$/,
    methods: ['POST'],
    priority: 'HIGH',
  },
  {
    pattern: /^\/api\/dreams\/journal\/$/,
    methods: ['POST'],
    priority: 'HIGH',
  },
  {
    pattern: /^\/api\/dreams\/journal\/[^/]+\/$/,
    methods: ['PATCH', 'PUT'],
    priority: 'HIGH',
  },
  {
    pattern: /^\/api\/dreams\/focus\/complete\/$/,
    methods: ['POST'],
    priority: 'HIGH',
  },
  {
    pattern: /^\/api\/calendar\/habits\/[^/]+\/complete\/$/,
    methods: ['POST'],
    priority: 'HIGH',
  },
  {
    pattern: /^\/api\/calendar\/habits\/[^/]+\/uncomplete\/$/,
    methods: ['POST'],
    priority: 'HIGH',
  },

  // ─── MEDIUM priority (user data) ────────────────────────────
  {
    pattern: /^\/api\/dreams\/dreams\/[^/]+\/$/,
    methods: ['PATCH', 'PUT'],  // dream edit
    priority: 'MEDIUM',
  },
  {
    pattern: /^\/api\/users\/update_profile\/$/,
    methods: ['PATCH', 'PUT'],
    priority: 'MEDIUM',
  },
  {
    pattern: /^\/api\/users\/upload_avatar\/$/,
    methods: ['POST'],
    priority: 'MEDIUM',
  },
  {
    pattern: /^\/api\/calendar\/events\/$/,
    methods: ['POST'],    // create event
    priority: 'MEDIUM',
  },
  {
    pattern: /^\/api\/calendar\/events\/[^/]+\/$/,
    methods: ['PATCH', 'PUT', 'DELETE'],  // edit/delete event
    priority: 'MEDIUM',
  },
  {
    pattern: /^\/api\/calendar\/timeblocks\/$/,
    methods: ['POST'],
    priority: 'MEDIUM',
  },
  {
    pattern: /^\/api\/calendar\/timeblocks\/[^/]+\/$/,
    methods: ['PATCH', 'PUT', 'DELETE'],
    priority: 'MEDIUM',
  },
  {
    pattern: /^\/api\/users\/notification-preferences\/$/,
    methods: ['PATCH', 'PUT'],
    priority: 'MEDIUM',
  },
  {
    pattern: /^\/api\/calendar\/preferences\/$/,
    methods: ['PATCH', 'PUT'],
    priority: 'MEDIUM',
  },
  {
    pattern: /^\/api\/dreams\/obstacles\/[^/]+\/$/,
    methods: ['PATCH'],
    priority: 'MEDIUM',
  },
  {
    pattern: /^\/api\/dreams\/obstacles\/[^/]+\/resolve\/$/,
    methods: ['POST'],
    priority: 'MEDIUM',
  },
  {
    pattern: /^\/api\/dreams\/dreams\/[^/]+\/tags\/$/,
    methods: ['POST'],
    priority: 'MEDIUM',
  },

  // ─── LOW priority (side-effects) ────────────────────────────
  {
    pattern: /^\/api\/notifications\/[^/]+\/mark_read\/$/,
    methods: ['POST'],
    priority: 'LOW',
  },
  {
    pattern: /^\/api\/notifications\/mark_all_read\/$/,
    methods: ['POST'],
    priority: 'LOW',
  },
  {
    pattern: /^\/api\/social\/posts\/[^/]+\/like\/$/,
    methods: ['POST'],
    priority: 'LOW',
  },
  {
    pattern: /^\/api\/social\/posts\/[^/]+\/comment\/$/,
    methods: ['POST'],
    priority: 'LOW',
  },
  {
    pattern: /^\/api\/social\/feed\/[^/]+\/like\/$/,
    methods: ['POST'],
    priority: 'LOW',
  },
  {
    pattern: /^\/api\/social\/feed\/[^/]+\/comment\/$/,
    methods: ['POST'],
    priority: 'LOW',
  },
  {
    pattern: /^\/api\/social\/stories\/[^/]+\/view\/$/,
    methods: ['POST'],
    priority: 'LOW',
  },
  {
    pattern: /^\/api\/dreams\/dreams\/[^/]+\/like\/$/,
    methods: ['POST'],
    priority: 'LOW',
  },
  {
    pattern: /^\/api\/notifications\/[^/]+\/opened\/$/,
    methods: ['POST'],
    priority: 'LOW',
  },
];
```

### Implementation — `getAllowedEntry(url, method)`

```javascript
/**
 * Returns the allow-list entry if URL+method is safe to queue, null otherwise.
 */
function getAllowedEntry(url, method) {
  for (var i = 0; i < OFFLINE_ALLOW_LIST.length; i++) {
    var entry = OFFLINE_ALLOW_LIST[i];
    if (entry.pattern.test(url) && entry.methods.indexOf(method) !== -1) {
      return entry;
    }
  }
  return null;
}
```

---

## 5. Queue Storage Layer

### Shared module: `src/services/syncQueue.js`

This module is platform-agnostic. Storage adapters differ per platform.

```javascript
// ── syncQueue.js ──────────────────────────────────────────────────
// Unified offline sync queue for web and mobile.

var QUEUE_KEY = 'dp-offline-queue';
var MAX_ITEMS = 100;
var MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;
var MAX_RETRIES = 5;

// ── Storage adapter (set at init) ──────────────────────────────
var _storage = null;

/**
 * Initialize with platform storage adapter.
 * Web:    { get(key), set(key, val) } using localStorage (sync)
 * Mobile: { get(key), set(key, val) } using AsyncStorage (async)
 *
 * Both get/set MUST return Promises (web adapter wraps sync calls).
 */
function initSyncQueue(storageAdapter) {
  _storage = storageAdapter;
}

// ── Internal helpers ───────────────────────────────────────────

function _generateId() {
  // Compact unique ID: timestamp + random suffix
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

async function _loadQueue() {
  var raw = await _storage.get(QUEUE_KEY);
  if (!raw) return [];
  try {
    return JSON.parse(raw);
  } catch (e) {
    return [];
  }
}

async function _saveQueue(queue) {
  await _storage.set(QUEUE_KEY, JSON.stringify(queue));
  _emitChange(queue.length);
}

function _emitChange(count) {
  // Web: CustomEvent. Mobile: EventEmitter (see platform notes).
  if (typeof window !== 'undefined' && window.dispatchEvent) {
    window.dispatchEvent(
      new CustomEvent('dp-offline-queue-change', { detail: { count: count } })
    );
  }
}

// ── Public API ─────────────────────────────────────────────────

/**
 * Enqueue a mutation for offline sync.
 * Returns true if enqueued, false if rejected (blocked, full, or duplicate).
 */
async function enqueue(url, method, body, priority) {
  // 1. Block-list check
  if (isBlockedOffline(url)) return false;

  // 2. Allow-list check
  var entry = getAllowedEntry(url, method);
  if (!entry) return false;

  var resolvedPriority = priority || entry.priority;

  // 3. Anti-abuse checks (see section 10)
  var abuseResult = checkAbuseLimit(url, method);
  if (!abuseResult.allowed) return false;

  // 4. Load queue
  var queue = await _loadQueue();

  // 5. Evict expired items (>7 days old)
  var now = Date.now();
  queue = queue.filter(function (item) {
    return now - item.timestamp < MAX_AGE_MS;
  });

  // 6. Evict items that exceeded max retries
  queue = queue.filter(function (item) {
    return item.retryCount < MAX_RETRIES;
  });

  // 7. Deduplication: same URL + method → keep latest (replace)
  var entityKey = method + ':' + url;
  queue = queue.filter(function (item) {
    return item.entityKey !== entityKey;
  });

  // 8. Enforce queue cap — if at limit, drop lowest-priority oldest item
  if (queue.length >= MAX_ITEMS) {
    var dropped = _dropLowestPriority(queue);
    if (!dropped) return false; // All HIGH and still full — reject
  }

  // 9. Push new item
  queue.push({
    id: _generateId(),
    url: url,
    method: method,
    body: body || null,
    timestamp: now,
    retryCount: 0,
    priority: resolvedPriority,
    entityKey: entityKey,
  });

  await _saveQueue(queue);
  return true;
}

/**
 * Drop the lowest-priority, oldest item from the queue.
 * Returns true if an item was dropped, false if the queue is all HIGH.
 */
function _dropLowestPriority(queue) {
  var priorityOrder = { LOW: 0, MEDIUM: 1, HIGH: 2 };
  var minIdx = -1;
  var minScore = Infinity;

  for (var i = 0; i < queue.length; i++) {
    var score = priorityOrder[queue[i].priority] * 1e15 + queue[i].timestamp;
    if (score < minScore) {
      minScore = score;
      minIdx = i;
    }
  }

  if (minIdx >= 0 && queue[minIdx].priority !== 'HIGH') {
    queue.splice(minIdx, 1);
    return true;
  }
  return false;
}

/**
 * Get pending queue count (for badge display).
 */
async function getQueueCount() {
  var queue = await _loadQueue();
  return queue.length;
}

/**
 * Get all pending items (for debug/review UI).
 */
async function getQueueItems() {
  return _loadQueue();
}

/**
 * Remove a specific item by ID (e.g., user dismisses a conflict).
 */
async function removeItem(itemId) {
  var queue = await _loadQueue();
  queue = queue.filter(function (item) {
    return item.id !== itemId;
  });
  await _saveQueue(queue);
}

/**
 * Clear entire queue (logout, account switch).
 */
async function clearQueue() {
  await _saveQueue([]);
}
```

### Web storage adapter

```javascript
// web: src/services/syncStorageWeb.js
var webStorageAdapter = {
  get: function (key) {
    return Promise.resolve(localStorage.getItem(key));
  },
  set: function (key, value) {
    localStorage.setItem(key, value);
    return Promise.resolve();
  },
};
```

### Mobile storage adapter

```javascript
// mobile: src/services/syncStorageMobile.js
import AsyncStorage from '@react-native-async-storage/async-storage';

var mobileStorageAdapter = {
  get: function (key) {
    return AsyncStorage.getItem(key);
  },
  set: function (key, value) {
    return AsyncStorage.setItem(key, value);
  },
};
```

---

## 6. Flush & Retry Logic

### `flushQueue(requestFn)`

Called when network status transitions to online. Accepts `request()` as a dependency injection so the queue module stays testable.

```javascript
/**
 * Flush the offline queue, processing items in priority order.
 *
 * @param {Function} requestFn - The api.js `request()` function.
 * @returns {Object} { synced: number, failed: number, conflicts: SyncQueueItem[] }
 */
async function flushQueue(requestFn) {
  var queue = await _loadQueue();
  if (queue.length === 0) return { synced: 0, failed: 0, conflicts: [] };

  // Sort: HIGH first, then MEDIUM, then LOW; within same priority, oldest first
  var priorityOrder = { HIGH: 0, MEDIUM: 1, LOW: 2 };
  queue.sort(function (a, b) {
    var pDiff = priorityOrder[a.priority] - priorityOrder[b.priority];
    if (pDiff !== 0) return pDiff;
    return a.timestamp - b.timestamp;
  });

  var synced = 0;
  var failed = [];
  var conflicts = [];

  for (var i = 0; i < queue.length; i++) {
    var item = queue[i];

    // Skip items older than MAX_AGE
    if (Date.now() - item.timestamp > MAX_AGE_MS) {
      continue; // Silently discard
    }

    // Skip items that exceeded retry limit
    if (item.retryCount >= MAX_RETRIES) {
      conflicts.push(item);
      continue;
    }

    try {
      var parsedBody = item.body ? JSON.parse(item.body) : undefined;
      var response = await requestFn(item.url, {
        method: item.method,
        body: parsedBody,
        _fromSyncQueue: true,  // Flag so request() skips re-enqueuing on failure
      });

      // Check for conflict indicators in response
      if (response && response._syncConflict) {
        conflicts.push(Object.assign({}, item, { serverData: response }));
      } else {
        synced++;
      }
    } catch (e) {
      if (e && e.offline) {
        // Network still down — keep this item and all remaining
        item.retryCount++;
        failed.push(item);
        failed = failed.concat(queue.slice(i + 1));
        break;
      }

      if (e && e.status === 400) {
        // 400 = validation error (e.g., "Task already completed")
        // This is expected for idempotent endpoints — discard silently
        synced++;
      } else if (e && e.status === 404) {
        // Resource deleted while offline — discard
        synced++;
      } else if (e && e.status === 409) {
        // Conflict — save for user review
        conflicts.push(Object.assign({}, item, { serverError: e.body }));
      } else if (e && (e.status >= 500 || e.status === 429)) {
        // Server error or rate-limited — retry later
        item.retryCount++;
        failed.push(item);
      } else {
        // Other client error (403, etc.) — discard
        synced++;
      }
    }
  }

  await _saveQueue(failed);
  return { synced: synced, failed: failed.length, conflicts: conflicts };
}
```

### Retry backoff

When `flushQueue` is called and some items fail, the `NetworkProvider` schedules a retry:

```javascript
// In NetworkProvider / NetworkContext
var RETRY_DELAYS = [1000, 5000, 15000, 60000, 300000]; // 1s, 5s, 15s, 1m, 5m

function handleReconnect() {
  var attempt = 0;

  function tryFlush() {
    flushQueue(request).then(function (result) {
      // Show toast: "Synced N changes"
      if (result.synced > 0) {
        showSyncToast(result.synced);
      }
      // Show conflict review if needed
      if (result.conflicts.length > 0) {
        showConflictToast(result.conflicts);
      }
      // Retry if some items failed
      if (result.failed > 0 && attempt < RETRY_DELAYS.length) {
        setTimeout(tryFlush, RETRY_DELAYS[attempt]);
        attempt++;
      }
    });
  }

  tryFlush();
}
```

---

## 7. Conflict Resolution

### Resolution strategy by data domain

| Domain | Strategy | Rationale |
|---|---|---|
| **XP, level, streak** | Server wins | Server is source of truth for gamification. `add_xp()` uses atomic `F()` expressions. Streak is updated via `record_activity()` which is idempotent per day. |
| **Task completion time** | Client wins | The user completed the task at a specific time offline. Send `completedAt` in the body; backend should accept if not already completed. |
| **Journal text** | Client wins | User's written content — what they typed offline is their intent. |
| **Profile fields** | Client wins (last-write-wins) | Simple text/preference fields. User's last edit is their intent. |
| **Dream title/description** | Client wins (last-write-wins) | User content. |
| **Notification read status** | Merge (union) | If either client or server marks as read, it stays read. |
| **Social likes** | Idempotent (toggle) | Server handles `get_or_create` — safe to replay. |
| **Calendar events** | Client wins for owned events | User is editing their own calendar. |

### How conflicts are detected

The backend already returns `400` for double-completion ("Task is already completed."). This is not a conflict — it is an expected idempotent guard. The queue flush treats `400` as success (discard the item).

True conflicts are rare in Stepora because:
1. Single-user data (dreams, tasks, profile) has one writer.
2. Gamification fields (XP, streak) are server-computed — the client never writes them directly.
3. Social actions (likes) are idempotent by design (`get_or_create`).

### Backend: Accept offline timestamps

For task completion, the client should send the offline timestamp so the server records when the user actually completed the task:

```python
# In TaskViewSet.complete() — accept optional client_completed_at
@action(detail=True, methods=["post"])
def complete(self, request, pk=None):
    task = self.get_object()
    if task.status == "completed":
        return Response(
            {"error": _("Task is already completed.")},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Accept offline completion timestamp
    client_completed_at = request.data.get("completed_at")
    if client_completed_at:
        from django.utils.dateparse import parse_datetime
        parsed = parse_datetime(client_completed_at)
        if parsed and (timezone.now() - parsed).total_seconds() <= 86400:
            # Within 24h — accept client timestamp
            task.complete(completed_at=parsed)
        else:
            # Older than 24h or invalid — flag for review, use server time
            task.complete()
            logger.warning(
                "Stale offline completion for task %s (ts=%s)",
                task.id, client_completed_at,
            )
    else:
        task.complete()

    return Response(TaskSerializer(task).data)
```

### Client-side: Attach timestamps to queued items

When enqueuing a task completion, inject the offline timestamp into the body:

```javascript
// In the task completion mutation (React Query or direct call)
function completeTaskOffline(taskId) {
  return apiPost(DREAMS.TASKS.COMPLETE(taskId), {
    completedAt: new Date().toISOString(),
  });
}
```

The `request()` function in `api.js` already converts `completedAt` to `completed_at` via `camelToSnake()`.

---

## 8. Backend Changes

### 8.1 Accept `completed_at` on completion endpoints

Affected endpoints (all in `apps/dreams/views.py`):
- `TaskViewSet.complete()` — line 3521
- `GoalViewSet.complete()` — (similar pattern)
- `DreamMilestoneViewSet.complete()` — line 3151

Each should accept an optional `completed_at` field and validate it is within 24 hours.

### 8.2 Sync metadata endpoint (optional, future enhancement)

A dedicated endpoint to return server-side truth for conflict resolution:

```
GET /api/v1/sync/status/
```

Response:
```json
{
  "xp": 1250,
  "level": 13,
  "streakDays": 7,
  "streakUpdatedAt": "2026-03-25",
  "longestStreak": 14,
  "lastSyncAt": "2026-03-25T10:30:00Z"
}
```

The client can call this after flushing to reconcile gamification state. This is a **phase 2** enhancement — not needed for initial implementation.

### 8.3 Idempotency keys (future enhancement)

For POST endpoints (journal creation, event creation), the client can send an `X-Idempotency-Key` header containing the queue item's `id`. The backend stores processed keys in Redis (TTL: 24h) and returns the cached response for duplicates. This prevents double-journal-entries if the queue flushes but the client doesn't receive the response.

```python
# Middleware sketch (phase 2)
class IdempotencyMiddleware:
    def __call__(self, request):
        key = request.headers.get("X-Idempotency-Key")
        if key and request.method == "POST":
            cached = cache.get(f"idempotency:{key}")
            if cached:
                return JsonResponse(cached["body"], status=cached["status"])
        response = self.get_response(request)
        if key and request.method == "POST" and response.status_code < 400:
            cache.set(f"idempotency:{key}", {
                "body": response.content,
                "status": response.status_code,
            }, timeout=86400)
        return response
```

---

## 9. UI Requirements

### 9.1 Offline banner

Shown at the top of the screen when `isOnline === false`.

```
┌─────────────────────────────────────────────────┐
│  ⚡ You're offline. Changes will sync when      │
│     connected.                                   │
└─────────────────────────────────────────────────┘
```

- **Style**: `var(--dp-warning-bg)`, full-width, fixed position below the header
- **Dismiss**: Not dismissable — auto-hides when online
- **Accessibility**: `role="status"`, `aria-live="polite"`

### 9.2 Sync pending badge

When `queueCount > 0` and `isOnline === true` (items waiting to flush):

- Small badge on the sync icon in the bottom nav or header
- Shows count: e.g., `3` pending
- Pulsing animation while actively flushing

### 9.3 Sync success toast

After `flushQueue` completes with `synced > 0`:

```
"Synced 5 changes"    ← brief toast, auto-dismiss after 3s
```

### 9.4 Conflict toast

After `flushQueue` completes with `conflicts.length > 0`:

```
"Some changes couldn't sync — tap to review"
```

Tapping opens a bottom sheet (mobile) or modal (desktop) listing the conflicting items with options:
- **Retry** — re-enqueue the item
- **Discard** — remove from queue
- **View details** — show what was sent vs. server state

### 9.5 Blocked action feedback

When user tries a blocked endpoint while offline:

```
"This action requires an internet connection."
```

- **Style**: Error toast, auto-dismiss after 4s
- **i18n key**: `offline.actionBlocked`

### 9.6 Component: `OfflineBanner`

```jsx
// src/components/OfflineBanner.jsx (shared between web and mobile)
function OfflineBanner() {
  var { isOnline, queueCount } = useNetwork();

  if (isOnline && queueCount === 0) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        background: isOnline ? 'var(--dp-info-bg)' : 'var(--dp-warning-bg)',
        color: isOnline ? 'var(--dp-info-text)' : 'var(--dp-warning-text)',
        padding: '8px 16px',
        textAlign: 'center',
        fontSize: '14px',
        fontWeight: 500,
      }}
    >
      {!isOnline
        ? t('offline.banner')
        : t('offline.syncing', { count: queueCount })}
    </div>
  );
}
```

### 9.7 i18n keys

Add to all 16 language JSON files in `src/i18n/`:

```json
{
  "offline.banner": "You're offline. Changes will sync when connected.",
  "offline.syncing": "Syncing {{count}} pending changes...",
  "offline.syncComplete": "Synced {{count}} changes",
  "offline.syncConflict": "Some changes couldn't sync — tap to review",
  "offline.actionBlocked": "This action requires an internet connection.",
  "offline.queueFull": "Too many offline changes. Please connect to sync.",
  "offline.abuseLimit": "Offline limit reached for this action."
}
```

---

## 10. Anti-Abuse Protections

### Session-scoped counters

These counters reset when the app goes online (queue is flushed) or the app restarts.

```javascript
var _offlineSessionCounters = {
  taskCompletions: 0,       // max 20 per offline session
  journalEntries: 0,        // max 10 per offline session
  completedTaskIds: {},      // Set<taskId> — no duplicate completions
};

var OFFLINE_LIMITS = {
  TASK_COMPLETIONS: 20,
  JOURNAL_ENTRIES: 10,
};

/**
 * Reset counters when going online (called by NetworkProvider on reconnect).
 */
function resetOfflineCounters() {
  _offlineSessionCounters.taskCompletions = 0;
  _offlineSessionCounters.journalEntries = 0;
  _offlineSessionCounters.completedTaskIds = {};
}

/**
 * Check if a queued action is within abuse limits.
 * Returns { allowed: boolean, reason?: string }
 */
function checkAbuseLimit(url, method) {
  // Task completion check
  if (/\/api\/dreams\/tasks\/[^/]+\/complete\/$/.test(url)) {
    // Extract task ID from URL
    var taskIdMatch = url.match(/\/tasks\/([^/]+)\/complete\/$/);
    var taskId = taskIdMatch ? taskIdMatch[1] : null;

    // No duplicate task completions
    if (taskId && _offlineSessionCounters.completedTaskIds[taskId]) {
      return { allowed: false, reason: 'duplicate_task' };
    }

    // Max 20 task completions per offline session
    if (_offlineSessionCounters.taskCompletions >= OFFLINE_LIMITS.TASK_COMPLETIONS) {
      return { allowed: false, reason: 'task_limit' };
    }

    // Track
    _offlineSessionCounters.taskCompletions++;
    if (taskId) _offlineSessionCounters.completedTaskIds[taskId] = true;
    return { allowed: true };
  }

  // Habit completion check (same limit as tasks — they grant XP)
  if (/\/api\/calendar\/habits\/[^/]+\/complete\/$/.test(url)) {
    if (_offlineSessionCounters.taskCompletions >= OFFLINE_LIMITS.TASK_COMPLETIONS) {
      return { allowed: false, reason: 'task_limit' };
    }
    _offlineSessionCounters.taskCompletions++;
    return { allowed: true };
  }

  // Journal entry check
  if (/\/api\/dreams\/journal\/$/.test(url) && method === 'POST') {
    if (_offlineSessionCounters.journalEntries >= OFFLINE_LIMITS.JOURNAL_ENTRIES) {
      return { allowed: false, reason: 'journal_limit' };
    }
    _offlineSessionCounters.journalEntries++;
    return { allowed: true };
  }

  // All other allowed endpoints — no abuse limit
  return { allowed: true };
}
```

### Server-side timestamp validation

When flushing queued task completions, the client sends `completedAt`. The backend validates:

```python
# In task.complete() or the view
from django.utils import timezone
from datetime import timedelta

def validate_offline_completion(completed_at):
    """
    If completion timestamp is >24h old, flag for review.
    Returns (accepted: bool, flagged: bool)
    """
    if not completed_at:
        return True, False

    age = timezone.now() - completed_at
    if age > timedelta(hours=24):
        # Log for admin review — don't block, but flag
        logger.warning(
            "Offline task completion is %s old — flagging for review",
            age,
        )
        return True, True  # Accept but flag

    if age < timedelta(seconds=-60):
        # Future timestamp (clock skew >1 min) — reject
        return False, False

    return True, False
```

### Rate limiting on flush

The existing backend throttles (e.g., `AICalibrationRateThrottle`) do not apply to offline-safe endpoints. But to prevent a malicious client from flushing 100 task completions at once:

- The flush loop adds a **50ms delay** between requests during flush.
- If the server returns `429`, the flush pauses for the `Retry-After` header value.

```javascript
// In flushQueue, between iterations:
async function flushQueue(requestFn) {
  // ... (sorting, loop setup)

  for (var i = 0; i < queue.length; i++) {
    // ... (process item)

    // Throttle: 50ms between flush requests
    if (i < queue.length - 1) {
      await new Promise(function (resolve) { setTimeout(resolve, 50); });
    }
  }

  // ...
}
```

---

## 11. Platform-Specific Notes

### Web (`stepora-frontend`)

- **Storage**: `localStorage` via `syncStorageWeb.js` adapter
- **Network detection**: `NetworkContext.jsx` already uses `getNetworkStatus()` and `addNetworkListener()` from `src/services/native.js` (Capacitor `Network` plugin or browser `navigator.onLine`)
- **Queue events**: `CustomEvent('dp-offline-queue-change')` — already wired to `NetworkProvider`
- **Service Worker**: Not currently in use. Future enhancement: SW can intercept requests and enqueue when offline, enabling true offline-first for the PWA.
- **Tab sync**: If the user has multiple tabs open, `localStorage` events (`storage` event) can be used to sync queue state across tabs. For now, flush only happens in the tab that detects reconnect.

### Mobile — React Native (`stepora-mobile`)

- **Storage**: `AsyncStorage` via `syncStorageMobile.js` adapter
- **Network detection**: Mobile does not yet have a `NetworkContext`. Create one using `@react-native-community/netinfo`:

```javascript
// mobile: src/context/NetworkContext.jsx
import { createContext, useContext, useState, useEffect } from 'react';
import NetInfo from '@react-native-community/netinfo';
import { flushQueue, getQueueCount, resetOfflineCounters } from '../services/syncQueue';
import { request } from '../services/api';

var NetworkContext = createContext({ isOnline: true, queueCount: 0 });

export function useNetwork() {
  return useContext(NetworkContext);
}

export function NetworkProvider({ children }) {
  var [isOnline, setIsOnline] = useState(true);
  var [queueCount, setQueueCount] = useState(0);

  useEffect(function () {
    // Initial state
    NetInfo.fetch().then(function (state) {
      setIsOnline(state.isConnected && state.isInternetReachable !== false);
    });

    // Listen for changes
    var unsubscribe = NetInfo.addEventListener(function (state) {
      var online = state.isConnected && state.isInternetReachable !== false;
      setIsOnline(online);
      if (online) {
        resetOfflineCounters();
        flushQueue(request).then(function (result) {
          getQueueCount().then(setQueueCount);
        });
      }
    });

    // Refresh queue count periodically
    getQueueCount().then(setQueueCount);

    return function () {
      unsubscribe();
    };
  }, []);

  return (
    <NetworkContext.Provider value={{ isOnline: isOnline, queueCount: queueCount }}>
      {children}
    </NetworkContext.Provider>
  );
}
```

- **Queue change events**: On mobile, since there is no `window.dispatchEvent`, the `_emitChange` function should call a registered callback instead:

```javascript
// Mobile override for _emitChange
var _queueChangeListeners = [];

function addQueueChangeListener(fn) {
  _queueChangeListeners.push(fn);
  return function () {
    _queueChangeListeners = _queueChangeListeners.filter(function (l) {
      return l !== fn;
    });
  };
}

function _emitChange(count) {
  for (var i = 0; i < _queueChangeListeners.length; i++) {
    _queueChangeListeners[i](count);
  }
}
```

- **App background/foreground**: When the app comes back to foreground, check network and flush:

```javascript
import { AppState } from 'react-native';

AppState.addEventListener('change', function (nextState) {
  if (nextState === 'active') {
    NetInfo.fetch().then(function (state) {
      if (state.isConnected) {
        flushQueue(request);
      }
    });
  }
});
```

---

## 12. Migration Path

### Phase 1: Replace existing queue (Week 1)

1. Create `src/services/syncQueue.js` with the full queue logic from section 5.
2. Create platform-specific storage adapters.
3. Update `enqueueOfflineMutation()` in both `api.js` files to delegate to `syncQueue.enqueue()`.
4. Update `flushOfflineQueue()` to delegate to `syncQueue.flushQueue()`.
5. Update `clearAuth()` to call `syncQueue.clearQueue()`.
6. Migrate existing `dp-offline-queue` data on first load (parse old format, re-enqueue with new fields).

```javascript
// Migration: old format → new format
async function migrateOldQueue() {
  var queue = await _loadQueue();
  if (queue.length > 0 && !queue[0].id) {
    // Old format: { url, method, body, timestamp }
    var migrated = queue.map(function (item) {
      var entry = getAllowedEntry(item.url, item.method);
      return {
        id: _generateId(),
        url: item.url,
        method: item.method,
        body: item.body,
        timestamp: item.timestamp,
        retryCount: 0,
        priority: entry ? entry.priority : 'MEDIUM',
        entityKey: item.method + ':' + item.url,
      };
    });
    await _saveQueue(migrated);
  }
}
```

### Phase 2: UI components (Week 2)

1. Create `OfflineBanner` component.
2. Add sync badge to bottom nav / header.
3. Add toast notifications for sync results.
4. Add i18n keys to all 16 language files.

### Phase 3: Backend hardening (Week 3)

1. Accept `completed_at` on task/goal/milestone completion endpoints.
2. Add timestamp validation and logging.
3. (Optional) Add `X-Idempotency-Key` middleware.

### Phase 4: Anti-abuse + conflict review (Week 4)

1. Wire up session-scoped counters.
2. Add conflict review bottom sheet / modal.
3. Add server-side flagging for stale completions.
4. Add flush throttling (50ms delay).

---

## 13. Testing Checklist

### Unit tests

- [ ] `enqueue()` rejects blocked endpoints
- [ ] `enqueue()` accepts allowed endpoints with correct priority
- [ ] `enqueue()` deduplicates by `entityKey` (keeps latest)
- [ ] `enqueue()` enforces 100-item cap (drops LOW before MEDIUM)
- [ ] `enqueue()` evicts items older than 7 days
- [ ] `enqueue()` evicts items with `retryCount >= 5`
- [ ] `enqueue()` rejects duplicate task completions (same task ID)
- [ ] `enqueue()` rejects when task completion limit (20) reached
- [ ] `enqueue()` rejects when journal entry limit (10) reached
- [ ] `flushQueue()` processes items in priority order (HIGH first)
- [ ] `flushQueue()` treats 400 as success (idempotent guard)
- [ ] `flushQueue()` treats 404 as success (resource deleted)
- [ ] `flushQueue()` retries on 500 (increments retryCount)
- [ ] `flushQueue()` stops on offline error (keeps remaining items)
- [ ] `flushQueue()` respects 429 (keeps item, increments retryCount)
- [ ] `isBlockedOffline()` blocks all auth endpoints
- [ ] `isBlockedOffline()` blocks all subscription endpoints
- [ ] `isBlockedOffline()` blocks AI/generate endpoints
- [ ] `getAllowedEntry()` returns correct priority for each endpoint
- [ ] `resetOfflineCounters()` clears all session counters
- [ ] Migration from old queue format preserves items

### Integration tests

- [ ] Offline task completion queues and syncs on reconnect
- [ ] Offline journal entry queues and syncs on reconnect
- [ ] Offline profile edit queues and syncs on reconnect
- [ ] Double task completion offline sends only one request
- [ ] Blocked endpoint (subscription) shows error toast
- [ ] Queue survives app restart (storage persistence)
- [ ] Queue is cleared on logout
- [ ] Offline banner appears/disappears with network changes
- [ ] Sync toast shows correct count after flush
- [ ] Conflict toast appears when server returns 409
- [ ] Queue count badge updates in real-time

### E2E tests

- [ ] Complete 5 tasks offline, go online, verify XP is correct
- [ ] Write journal entry offline, go online, verify it appears in dream detail
- [ ] Edit profile offline, go online, verify changes persisted
- [ ] Try to purchase subscription offline, verify error message
- [ ] Try to use AI coach offline, verify error message
- [ ] Complete 21st task offline (exceeds limit), verify rejection
- [ ] Stay offline for 8 days, verify stale items are discarded on reconnect

---

## Appendix A: Integration with `api.js`

### Modified `request()` function (key changes only)

```javascript
// In the catch block for network errors (both web and mobile api.js):

} catch (fetchError) {
  if (fetchError && fetchError.name === 'AbortError') {
    throw fetchError;
  }

  var networkMsg = 'Network error: ' + (fetchError?.message || String(fetchError));

  if (method !== 'GET' && method !== 'HEAD') {
    // Skip re-enqueue if this request came FROM the sync queue
    if (options._fromSyncQueue) {
      var syncErr = new Error(networkMsg);
      syncErr.status = 0;
      syncErr.offline = true;
      throw syncErr;
    }

    // Check if this endpoint is blocked offline
    if (isBlockedOffline(url)) {
      var blockedErr = new Error(t('offline.actionBlocked'));
      blockedErr.status = 0;
      blockedErr.offline = true;
      blockedErr.blocked = true;
      throw blockedErr;
    }

    // Try to enqueue
    var enqueued = await enqueue(url, method, options.body || null);
    var offlineError = new Error(
      enqueued ? networkMsg : t('offline.actionBlocked')
    );
    offlineError.status = 0;
    offlineError.offline = true;
    offlineError.queued = enqueued;
    throw offlineError;
  }

  var getError = new Error(networkMsg);
  getError.status = 0;
  getError.offline = true;
  throw getError;
}
```

### Handling in UI (React Query example)

```javascript
// In a useMutation onError handler:
onError: function (error) {
  if (error.offline && error.blocked) {
    // Show "requires internet" toast
    showToast(t('offline.actionBlocked'), 'error');
  } else if (error.offline && error.queued) {
    // Show "will sync when connected" toast
    showToast(t('offline.banner'), 'info');
  } else if (error.offline) {
    // Queuing failed (limit reached, queue full)
    showToast(t('offline.queueFull'), 'warning');
  } else {
    // Normal online error
    showToast(error.userMessage || error.message, 'error');
  }
}
```

---

## Appendix B: Full block/allow summary table

| Endpoint Pattern | Method | Offline | Priority | Rationale |
|---|---|---|---|---|
| `/api/auth/*` | ALL | BLOCKED | - | Auth requires server |
| `/api/subscriptions/*` | ALL | BLOCKED | - | Payment operations |
| `/api/store/purchase*` | ALL | BLOCKED | - | Real-money/XP purchases |
| `/api/ai/*` | ALL | BLOCKED | - | Requires OpenAI |
| `/api/users/delete-account/` | POST | BLOCKED | - | Irreversible |
| `/api/users/export-data/` | GET | BLOCKED | - | Server-generated file |
| `/api/users/2fa/*` | ALL | BLOCKED | - | Security-critical |
| `/api/users/change-email/` | POST | BLOCKED | - | Requires verification |
| `/api/referrals/redeem/` | POST | BLOCKED | - | Server validation |
| `/api/gamification/streak-freeze/` | POST | BLOCKED | - | Cooldown validation |
| `/api/dreams/*/generate_plan/` | POST | BLOCKED | - | Needs AI |
| `/api/dreams/*/start_calibration/` | POST | BLOCKED | - | Needs AI |
| `/api/dreams/*/answer_calibration/` | POST | BLOCKED | - | Needs AI |
| `/api/dreams/tasks/*/complete/` | POST | ALLOWED | HIGH | XP grant |
| `/api/dreams/tasks/*/` | PATCH | ALLOWED | HIGH | Task edit |
| `/api/dreams/goals/*/complete/` | POST | ALLOWED | HIGH | XP grant |
| `/api/dreams/milestones/*/complete/` | POST | ALLOWED | HIGH | XP grant |
| `/api/dreams/journal/` | POST | ALLOWED | HIGH | User content |
| `/api/dreams/journal/*/` | PATCH/PUT | ALLOWED | HIGH | User content |
| `/api/dreams/focus/complete/` | POST | ALLOWED | HIGH | XP grant |
| `/api/calendar/habits/*/complete/` | POST | ALLOWED | HIGH | Streak impact |
| `/api/dreams/dreams/*/` | PATCH/PUT | ALLOWED | MEDIUM | Dream edit |
| `/api/users/update_profile/` | PATCH/PUT | ALLOWED | MEDIUM | Profile edit |
| `/api/calendar/events/` | POST | ALLOWED | MEDIUM | Event creation |
| `/api/calendar/events/*/` | PATCH/PUT/DEL | ALLOWED | MEDIUM | Event edit |
| `/api/notifications/*/mark_read/` | POST | ALLOWED | LOW | Read receipt |
| `/api/notifications/mark_all_read/` | POST | ALLOWED | LOW | Bulk read |
| `/api/social/posts/*/like/` | POST | ALLOWED | LOW | Social action |
| `/api/social/posts/*/comment/` | POST | ALLOWED | LOW | Social action |
| `/api/social/stories/*/view/` | POST | ALLOWED | LOW | View tracking |
| `/api/dreams/dreams/*/like/` | POST | ALLOWED | LOW | Favorite toggle |
| Any other mutation endpoint | ALL | BLOCKED | - | Fail-safe default |
