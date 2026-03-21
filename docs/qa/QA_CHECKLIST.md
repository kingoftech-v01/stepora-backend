# Stepora QA Testing Checklist

## How to Use
- Test each item on **Mobile** (< 768px), **Tablet** (768-1024px), and **Desktop** (> 1024px)
- Mark with: **P** (pass), **F** (fail), **S** (skip), **B** (bug found)
- Add notes for any issues found in the Notes column
- Record the device/browser used for each test session

| Field | Value |
|-------|-------|
| Date | ____ |
| Tester | ____ |
| Environment | Preprod / Production |
| Build/Branch | ____ |
| Browser(s) | ____ |
| Mobile Device | ____ |
| Tablet Device | ____ |

---

## 1. Authentication

### 1.1 Registration
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 1.1.1 | Register with valid email/password | | | | |
| 1.1.2 | Register validation: empty fields show errors | | | | |
| 1.1.3 | Register validation: weak password rejected | | | | |
| 1.1.4 | Register validation: invalid email format rejected | | | | |
| 1.1.5 | Register validation: duplicate email shows error | | | | |
| 1.1.6 | Verification email sent after registration | | | | |
| 1.1.7 | Verification email link works (token in URL) | | | | |
| 1.1.8 | Resend verification email works | | | | |
| 1.1.9 | Email gate screen displays while unverified | | | | |
| 1.1.10 | Check email screen displays after registration | | | | |

### 1.2 Login
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 1.2.1 | Login with valid email/password | | | | |
| 1.2.2 | Login with wrong password shows error | | | | |
| 1.2.3 | Login with non-existent email shows error | | | | |
| 1.2.4 | Login with unverified email redirects to email gate | | | | |
| 1.2.5 | Session persistence: refresh page, still logged in | | | | |
| 1.2.6 | Token refresh: stay logged in after access token expiry (~15min) | | | | |
| 1.2.7 | httpOnly refresh cookie set correctly (web) | | | | |
| 1.2.8 | Native platform: tokens in body with `X-Client-Platform: native` | | | | |

### 1.3 Password Management
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 1.3.1 | Forgot password: send reset email | | | | |
| 1.3.2 | Reset password link works (uid~token separator) | | | | |
| 1.3.3 | Reset password: set new password successfully | | | | |
| 1.3.4 | Reset password: expired/invalid token shows error | | | | |
| 1.3.5 | Change password (from settings, requires current password) | | | | |
| 1.3.6 | Change password validation: weak new password rejected | | | | |

### 1.4 Social Login
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 1.4.1 | Google social login: initiates OAuth flow | | | | |
| 1.4.2 | Google social login: callback creates account/logs in | | | | |
| 1.4.3 | Apple social login: initiates OAuth flow | | | | |
| 1.4.4 | Apple social login: callback/redirect works | | | | |

### 1.5 Logout
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 1.5.1 | Logout clears session and redirects to login | | | | |
| 1.5.2 | After logout, protected routes redirect to login | | | | |
| 1.5.3 | After logout, refresh token is invalidated | | | | |

---

## 2. Onboarding (New User Flow)

| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 2.1 | Onboarding slides display correctly after first login | | | | |
| 2.2 | Can navigate forward through onboarding steps | | | | |
| 2.3 | Can navigate backward through onboarding steps | | | | |
| 2.4 | Step 1-4: Profile info collection works | | | | |
| 2.5 | Personality quiz loads (8 questions) | | | | |
| 2.6 | Personality quiz: can select answers for each question | | | | |
| 2.7 | Personality quiz: results display personality type | | | | |
| 2.8 | Step 5: Subscription plan selection displays plans | | | | |
| 2.9 | Free plan selection skips Stripe and goes to home | | | | |
| 2.10 | Paid plan selection redirects to Stripe checkout | | | | |
| 2.11 | Complete onboarding endpoint called at finish | | | | |
| 2.12 | Onboarding does not re-appear on subsequent logins | | | | |

---

## 3. Home Screen / Dashboard

| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 3.1 | Dashboard loads with user stats (level, XP, streak) | | | | |
| 3.2 | Greeting changes by time of day | | | | |
| 3.3 | Quick actions (create dream, etc.) work | | | | |
| 3.4 | Recent/active dreams display in cards | | | | |
| 3.5 | Streak counter visible and accurate | | | | |
| 3.6 | XP progress bar visible | | | | |
| 3.7 | Promo banner displays for free users (3-day dismiss TTL) | | | | |
| 3.8 | Promo banner dismiss persists for 3 days | | | | |
| 3.9 | Profile completeness indicator shows | | | | |
| 3.10 | Daily stats load correctly | | | | |

---

## 4. Dreams

### 4.1 Dream CRUD
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 4.1.1 | Create dream (title, description, category, timeframe) | | | | |
| 4.1.2 | Dream creation: AI auto-categorize works | | | | |
| 4.1.3 | Dream appears in list after creation | | | | |
| 4.1.4 | View dream detail page | | | | |
| 4.1.5 | Edit dream (update title, description, category, target date) | | | | |
| 4.1.6 | Delete dream with confirmation dialog | | | | |
| 4.1.7 | Duplicate dream creates a deep copy | | | | |
| 4.1.8 | Dream list: filter by status (active/completed/paused) | | | | |
| 4.1.9 | Dream list: filter by category | | | | |
| 4.1.10 | Dream list: ordering (date, priority) works | | | | |
| 4.1.11 | Dream list: search by title/description | | | | |
| 4.1.12 | Free plan dream limit enforced (CanCreateDream) | | | | |

### 4.2 AI Analysis
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 4.2.1 | Analyze dream: AI returns insights | | | | |
| 4.2.2 | Smart analysis: cross-dream pattern recognition | | | | |
| 4.2.3 | Predict obstacles: AI predicts potential obstacles | | | | |
| 4.2.4 | Conversation starters: contextual suggestions load | | | | |
| 4.2.5 | Find similar dreams: shows related public dreams/templates | | | | |
| 4.2.6 | AI rate limiting: shows appropriate message when exceeded | | | | |
| 4.2.7 | AI usage tracking: quota display is accurate | | | | |

### 4.3 Plan Generation (Progressive)
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 4.3.1 | Calibration questions load for a dream | | | | |
| 4.3.2 | Answer calibration questions (multi-step wizard) | | | | |
| 4.3.3 | Plan generates after calibration answers | | | | |
| 4.3.4 | Skeleton appears first (milestones) | | | | |
| 4.3.5 | Partial tasks appear (months 1-4) progressively | | | | |
| 4.3.6 | Milestone > Goal > Task hierarchy displays correctly | | | | |
| 4.3.7 | Generate plan button works on dream detail | | | | |
| 4.3.8 | Two-minute micro-start generation works | | | | |

### 4.4 Milestones, Goals, Tasks
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 4.4.1 | View milestones list for a dream | | | | |
| 4.4.2 | Create/edit/delete milestone | | | | |
| 4.4.3 | View goals under a milestone | | | | |
| 4.4.4 | Create/edit/delete goal | | | | |
| 4.4.5 | View tasks under a goal | | | | |
| 4.4.6 | Create/edit/delete task | | | | |
| 4.4.7 | Task checkbox toggles completion status | | | | |
| 4.4.8 | Goal/task order auto-computed correctly | | | | |
| 4.4.9 | Progress percentage updates on task completion | | | | |
| 4.4.10 | Completed goals count is accurate | | | | |
| 4.4.11 | Obstacles CRUD (create/view/edit/delete) | | | | |

### 4.5 Check-ins
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 4.5.1 | Check-in banner appears when due (7-21 day cycle) | | | | |
| 4.5.2 | Check-in wizard loads questions | | | | |
| 4.5.3 | Submit check-in answers | | | | |
| 4.5.4 | Poll check-in processing status | | | | |
| 4.5.5 | New tasks/adjustments generated after check-in | | | | |
| 4.5.6 | Manual trigger check-in works | | | | |
| 4.5.7 | Check-in list (filter by dream, status) | | | | |

### 4.6 Dream Sharing & Collaboration
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 4.6.1 | Share dream with another user | | | | |
| 4.6.2 | Shared dreams list (shared with me) | | | | |
| 4.6.3 | Add collaborator to a dream | | | | |
| 4.6.4 | View collaborators list | | | | |
| 4.6.5 | Remove collaborator | | | | |
| 4.6.6 | View public dream from another user | | | | |
| 4.6.7 | Explore public dreams screen | | | | |

### 4.7 Tags
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 4.7.1 | Add tag to a dream | | | | |
| 4.7.2 | Remove tag from a dream | | | | |
| 4.7.3 | View all tags list | | | | |

### 4.8 Templates
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 4.8.1 | Browse dream templates list | | | | |
| 4.8.2 | View template detail | | | | |
| 4.8.3 | Use template to create a new dream | | | | |
| 4.8.4 | Featured templates highlighted | | | | |

### 4.9 Vision Board
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 4.9.1 | View vision board for a dream | | | | |
| 4.9.2 | Add image to vision board (upload) | | | | |
| 4.9.3 | Generate AI vision image | | | | |
| 4.9.4 | Remove image from vision board | | | | |
| 4.9.5 | Vision board permission check (subscription gated) | | | | |

### 4.10 Dream Journal
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 4.10.1 | Create journal entry for a dream | | | | |
| 4.10.2 | View journal entries list (filter by dream) | | | | |
| 4.10.3 | Edit journal entry | | | | |
| 4.10.4 | Delete journal entry | | | | |

### 4.11 Focus Timer (Pomodoro)
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 4.11.1 | Start focus session (select dream/task) | | | | |
| 4.11.2 | Timer counts down correctly | | | | |
| 4.11.3 | Pause/resume timer | | | | |
| 4.11.4 | Complete focus session | | | | |
| 4.11.5 | Focus session recorded in history | | | | |
| 4.11.6 | Weekly focus statistics display | | | | |
| 4.11.7 | Focus timer does not crash on navigation | | | | |

### 4.12 Progress Photos
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 4.12.1 | View progress photos for a dream | | | | |
| 4.12.2 | Upload progress photo | | | | |
| 4.12.3 | Delete progress photo | | | | |

### 4.13 Progress & Export
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 4.13.1 | Progress history (snapshots over time) | | | | |
| 4.13.2 | Export dream as PDF | | | | |
| 4.13.3 | Favorite/unfavorite dream (is_favorited toggle) | | | | |

---

## 5. Social System

### 5.1 Social Feed
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 5.1.1 | Social hub loads (feed with posts) | | | | |
| 5.1.2 | Friends activity feed loads | | | | |
| 5.1.3 | Create post (text + optional image) | | | | |
| 5.1.4 | Edit own post | | | | |
| 5.1.5 | Delete own post | | | | |
| 5.1.6 | Like/unlike a post | | | | |
| 5.1.7 | Comment on a post | | | | |
| 5.1.8 | View post comments list | | | | |
| 5.1.9 | React with emoji to a post | | | | |
| 5.1.10 | Save/unsave post (bookmark) | | | | |
| 5.1.11 | View saved posts screen | | | | |
| 5.1.12 | Share/repost a post | | | | |
| 5.1.13 | Send encouragement on a post | | | | |
| 5.1.14 | Post detail screen loads with full content | | | | |
| 5.1.15 | View user's posts (by user ID) | | | | |
| 5.1.16 | Feed like (activity feed item) | | | | |
| 5.1.17 | Feed comment (activity feed item) | | | | |

### 5.2 Friends
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 5.2.1 | Search users by name/query | | | | |
| 5.2.2 | View user search results | | | | |
| 5.2.3 | Send friend request | | | | |
| 5.2.4 | Accept friend request | | | | |
| 5.2.5 | Reject friend request | | | | |
| 5.2.6 | View pending friend requests (received) | | | | |
| 5.2.7 | View sent friend requests | | | | |
| 5.2.8 | Friend requests screen (combined) | | | | |
| 5.2.9 | View friends list | | | | |
| 5.2.10 | Remove friend | | | | |
| 5.2.11 | View mutual friends with a user | | | | |
| 5.2.12 | View online friends | | | | |
| 5.2.13 | Friend suggestions load | | | | |
| 5.2.14 | Social counts (friends/followers/following for a user) | | | | |

### 5.3 Follow System
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 5.3.1 | Follow a user | | | | |
| 5.3.2 | Unfollow a user | | | | |
| 5.3.3 | Follow suggestions load | | | | |

### 5.4 Block & Report
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 5.4.1 | Block a user | | | | |
| 5.4.2 | Unblock a user | | | | |
| 5.4.3 | View blocked users list | | | | |
| 5.4.4 | Report a user (with reason) | | | | |
| 5.4.5 | Blocked user cannot send friend request | | | | |
| 5.4.6 | Blocked user cannot follow | | | | |

### 5.5 User Profiles
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 5.5.1 | View another user's public profile | | | | |
| 5.5.2 | Profile shows level, XP, streak, avatar, bio | | | | |
| 5.5.3 | Profile shows public dreams | | | | |
| 5.5.4 | Profile visibility: private profile returns 403 | | | | |
| 5.5.5 | Profile visibility: friends-only enforced | | | | |
| 5.5.6 | User profile screen loads correctly | | | | |

### 5.6 Stories
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 5.6.1 | Create story (image upload) | | | | |
| 5.6.2 | View story | | | | |
| 5.6.3 | View my stories | | | | |
| 5.6.4 | Story view count tracked | | | | |
| 5.6.5 | Story expires after 24h | | | | |

### 5.7 Social Events
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 5.7.1 | Create social event | | | | |
| 5.7.2 | View event details | | | | |
| 5.7.3 | Register for an event | | | | |
| 5.7.4 | View event list | | | | |

### 5.8 Recent Searches
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 5.8.1 | Recent searches list displays | | | | |
| 5.8.2 | Add recent search entry | | | | |
| 5.8.3 | Remove a recent search | | | | |
| 5.8.4 | Clear all recent searches | | | | |

---

## 6. Circles

### 6.1 Circle Management
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 6.1.1 | View circles list (my circles) | | | | |
| 6.1.2 | View public circles | | | | |
| 6.1.3 | View recommended circles | | | | |
| 6.1.4 | Create a new circle | | | | |
| 6.1.5 | View circle detail page | | | | |
| 6.1.6 | Edit circle (name, description, settings) | | | | |
| 6.1.7 | Delete circle (owner only) | | | | |
| 6.1.8 | Join a public circle | | | | |
| 6.1.9 | Leave a circle | | | | |
| 6.1.10 | Circle subscription gate (CanUseCircles) | | | | |

### 6.2 Circle Membership
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 6.2.1 | Invite member directly | | | | |
| 6.2.2 | Generate invite link | | | | |
| 6.2.3 | Join circle by invite code | | | | |
| 6.2.4 | View invitations list | | | | |
| 6.2.5 | Accept circle invitation | | | | |
| 6.2.6 | Decline circle invitation | | | | |
| 6.2.7 | View my invitations | | | | |
| 6.2.8 | Promote member (to moderator/admin) | | | | |
| 6.2.9 | Demote member | | | | |
| 6.2.10 | Remove member from circle | | | | |
| 6.2.11 | View members list (sheet/modal) | | | | |

### 6.3 Circle Feed
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 6.3.1 | View circle post feed | | | | |
| 6.3.2 | Create a post in circle | | | | |
| 6.3.3 | Edit own circle post | | | | |
| 6.3.4 | Delete own circle post | | | | |
| 6.3.5 | React to a circle post | | | | |
| 6.3.6 | Remove reaction from circle post | | | | |

### 6.4 Circle Challenges
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 6.4.1 | View challenges list for a circle | | | | |
| 6.4.2 | Create a challenge in a circle | | | | |
| 6.4.3 | Join a challenge | | | | |
| 6.4.4 | Submit challenge progress | | | | |
| 6.4.5 | View challenge detail (sheet) | | | | |

### 6.5 Circle Chat
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 6.5.1 | View circle chat messages | | | | |
| 6.5.2 | Send message in circle chat | | | | |
| 6.5.3 | Real-time messages via WebSocket | | | | |

### 6.6 Circle Calls
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 6.6.1 | Start a circle call | | | | |
| 6.6.2 | Join an active circle call | | | | |
| 6.6.3 | Leave a circle call | | | | |
| 6.6.4 | End a circle call (host) | | | | |
| 6.6.5 | View active call status | | | | |

### 6.7 Circle Polls
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 6.7.1 | Create a poll in circle | | | | |
| 6.7.2 | Vote on a poll | | | | |
| 6.7.3 | View poll results | | | | |

---

## 7. Chat / Messaging

### 7.1 Friend Chat
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 7.1.1 | Messages screen loads with conversation list | | | | |
| 7.1.2 | Start new conversation (search and select user) | | | | |
| 7.1.3 | Open existing conversation | | | | |
| 7.1.4 | Send text message | | | | |
| 7.1.5 | Messages appear in real-time (WebSocket) | | | | |
| 7.1.6 | Mark conversation as read | | | | |
| 7.1.7 | Read receipts display correctly | | | | |
| 7.1.8 | Pin a message | | | | |
| 7.1.9 | Like a message | | | | |
| 7.1.10 | Message list (clicking conversation navigates to chat page) | | | | |

### 7.2 Calls (Agora)
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 7.2.1 | Initiate voice call | | | | |
| 7.2.2 | Accept incoming voice call | | | | |
| 7.2.3 | Reject incoming voice call | | | | |
| 7.2.4 | End active voice call | | | | |
| 7.2.5 | Voice call screen displays correctly | | | | |
| 7.2.6 | Initiate video call | | | | |
| 7.2.7 | Accept incoming video call | | | | |
| 7.2.8 | Video call screen with local/remote video | | | | |
| 7.2.9 | Call history screen loads | | | | |
| 7.2.10 | Agora config endpoint returns valid data | | | | |
| 7.2.11 | RTC token generation works | | | | |
| 7.2.12 | RTM token generation works | | | | |

---

## 8. AI Chat / Coaching

| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 8.1 | AI chat list screen loads (conversation list) | | | | |
| 8.2 | Create new AI conversation | | | | |
| 8.3 | Send message in AI conversation | | | | |
| 8.4 | AI responds to message | | | | |
| 8.5 | Streaming response works (progressive text display) | | | | |
| 8.6 | Conversation history persists across sessions | | | | |
| 8.7 | Multiple AI conversations can coexist | | | | |
| 8.8 | Update AI conversation (rename, etc.) | | | | |
| 8.9 | Delete AI conversation | | | | |
| 8.10 | Voice message: upload audio, transcription returned | | | | |
| 8.11 | Image message: send image for analysis | | | | |
| 8.12 | Summarize conversation | | | | |
| 8.13 | Conversation branching (create branch) | | | | |
| 8.14 | View conversation branches | | | | |
| 8.15 | Conversation templates list | | | | |
| 8.16 | Start conversation from template | | | | |
| 8.17 | Chat memories: auto-extract and store | | | | |
| 8.18 | Chat memories: view memories list | | | | |
| 8.19 | Chat memories: clear memories | | | | |
| 8.20 | AI message search (across conversations) | | | | |
| 8.21 | AI subscription gate: free tier limits enforced | | | | |
| 8.22 | AI daily usage quota enforced | | | | |
| 8.23 | Content moderation: unsafe content flagged | | | | |

---

## 9. Buddies (Accountability Partners)

### 9.1 Buddy Matching
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 9.1.1 | Find buddy match (compatible partner) | | | | |
| 9.1.2 | AI buddy matching with compatibility scoring | | | | |
| 9.1.3 | View buddy suggestions on Find Buddy screen | | | | |
| 9.1.4 | Accept buddy suggestion / create pairing | | | | |
| 9.1.5 | Reject buddy suggestion | | | | |
| 9.1.6 | View buddy requests screen | | | | |

### 9.2 Buddy Pairing
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 9.2.1 | View current buddy pairing | | | | |
| 9.2.2 | View progress comparison with buddy | | | | |
| 9.2.3 | Send encouragement to buddy | | | | |
| 9.2.4 | End buddy pairing (DELETE) | | | | |
| 9.2.5 | View pairing history | | | | |

### 9.3 Buddy Chat
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 9.3.1 | Start/get buddy chat conversation | | | | |
| 9.3.2 | Send message in buddy chat | | | | |
| 9.3.3 | Real-time buddy messages (WebSocket) | | | | |

### 9.4 Accountability Contracts
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 9.4.1 | Create accountability contract | | | | |
| 9.4.2 | View contracts list | | | | |
| 9.4.3 | Accept a contract | | | | |
| 9.4.4 | Submit contract check-in | | | | |
| 9.4.5 | View contract progress | | | | |

---

## 10. Calendar

### 10.1 Calendar Core
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 10.1.1 | Calendar view loads (month view) | | | | |
| 10.1.2 | Navigate between months | | | | |
| 10.1.3 | View events on a specific day | | | | |
| 10.1.4 | Create calendar event | | | | |
| 10.1.5 | Edit calendar event | | | | |
| 10.1.6 | Delete calendar event | | | | |
| 10.1.7 | Reschedule event (drag or patch) | | | | |
| 10.1.8 | Event categories filter | | | | |
| 10.1.9 | Search events | | | | |
| 10.1.10 | Check conflicts between events | | | | |
| 10.1.11 | Daily summary loads | | | | |

### 10.2 Recurring Events
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 10.2.1 | Create recurring event (daily/weekly/monthly) | | | | |
| 10.2.2 | Recurring events expand correctly in calendar | | | | |
| 10.2.3 | Skip a single occurrence | | | | |
| 10.2.4 | Modify a single occurrence | | | | |
| 10.2.5 | View recurrence exceptions | | | | |

### 10.3 Time Blocks
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 10.3.1 | View time blocks screen | | | | |
| 10.3.2 | Create time block | | | | |
| 10.3.3 | Edit time block | | | | |
| 10.3.4 | Delete time block | | | | |
| 10.3.5 | Snooze a time block alert | | | | |
| 10.3.6 | Dismiss a time block alert | | | | |

### 10.4 Time Block Templates
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 10.4.1 | View time block templates | | | | |
| 10.4.2 | Apply a template | | | | |
| 10.4.3 | Save current schedule as template | | | | |
| 10.4.4 | View preset templates | | | | |

### 10.5 Habits
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 10.5.1 | Create habit | | | | |
| 10.5.2 | View habits list | | | | |
| 10.5.3 | Complete habit for today | | | | |
| 10.5.4 | Uncomplete habit (undo) | | | | |
| 10.5.5 | View habit statistics | | | | |
| 10.5.6 | Habit calendar data (completion heatmap) | | | | |

### 10.6 Calendar Preferences & Timezone
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 10.6.1 | View/update calendar preferences | | | | |
| 10.6.2 | View/update timezone setting | | | | |
| 10.6.3 | Upcoming alerts list | | | | |

### 10.7 Smart Scheduling
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 10.7.1 | Smart schedule: AI suggests optimal times | | | | |
| 10.7.2 | Accept smart schedule suggestion | | | | |
| 10.7.3 | Suggest time slots endpoint works | | | | |
| 10.7.4 | Batch schedule tasks | | | | |
| 10.7.5 | Schedule score display | | | | |

### 10.8 Focus Mode
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 10.8.1 | Focus mode active status check | | | | |
| 10.8.2 | Focus block events display | | | | |

### 10.9 Calendar Sharing
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 10.9.1 | Share calendar with a user | | | | |
| 10.9.2 | View shared-with-me calendars | | | | |
| 10.9.3 | View my calendar shares | | | | |
| 10.9.4 | Revoke a calendar share | | | | |
| 10.9.5 | Generate shareable calendar link | | | | |
| 10.9.6 | View shared calendar (public token) | | | | |
| 10.9.7 | Suggest event on shared calendar | | | | |

### 10.10 iCal Integration
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 10.10.1 | iCal feed URL works (external calendar apps) | | | | |
| 10.10.2 | Import iCal file | | | | |
| 10.10.3 | Export calendar data | | | | |

### 10.11 Google Calendar Integration
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 10.11.1 | Google Calendar connection status check | | | | |
| 10.11.2 | Initiate Google Calendar OAuth | | | | |
| 10.11.3 | Google Calendar OAuth callback works | | | | |
| 10.11.4 | Sync events from Google Calendar | | | | |
| 10.11.5 | Google Calendar sync settings (view/update) | | | | |
| 10.11.6 | Disconnect Google Calendar | | | | |
| 10.11.7 | Google Calendar connect screen loads | | | | |
| 10.11.8 | Google sync settings screen loads | | | | |

---

## 11. Notifications

| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 11.1 | Notifications list loads | | | | |
| 11.2 | Notifications filter by type (dreams/social/system) | | | | |
| 11.3 | Notifications filter by status (read/unread) | | | | |
| 11.4 | Mark individual notification as read | | | | |
| 11.5 | Mark all notifications as read | | | | |
| 11.6 | Delete a notification | | | | |
| 11.7 | Snooze a notification | | | | |
| 11.8 | Unread count displays correctly | | | | |
| 11.9 | Push notification (browser/service worker) received | | | | |
| 11.10 | Web push subscription registration | | | | |
| 11.11 | Device registration for push notifications | | | | |
| 11.12 | Real-time notifications via WebSocket | | | | |
| 11.13 | Free tier: only sees basic notification types | | | | |
| 11.14 | Notification preferences screen updates correctly | | | | |

---

## 12. Subscription & Payments

### 12.1 Plans
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 12.1.1 | View subscription plans list (public) | | | | |
| 12.1.2 | Current plan displayed correctly on subscription screen | | | | |
| 12.1.3 | Active promotions display per plan | | | | |

### 12.2 Checkout
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 12.2.1 | Checkout: Stripe redirect works for paid plan | | | | |
| 12.2.2 | Checkout with promotion code applied | | | | |
| 12.2.3 | Stripe checkout success returns to app | | | | |
| 12.2.4 | Stripe checkout cancel returns to app | | | | |

### 12.3 Subscription Management
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 12.3.1 | Get current subscription details | | | | |
| 12.3.2 | Cancel subscription | | | | |
| 12.3.3 | Resume canceled subscription | | | | |
| 12.3.4 | Change plan (upgrade) | | | | |
| 12.3.5 | Change plan (downgrade) | | | | |
| 12.3.6 | Cancel pending plan change | | | | |
| 12.3.7 | Downgrade toast shows correct message | | | | |
| 12.3.8 | Apply coupon to current subscription | | | | |
| 12.3.9 | View invoices list | | | | |

### 12.4 Promotions
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 12.4.1 | View active promotions | | | | |
| 12.4.2 | Promo banner on home for free users | | | | |
| 12.4.3 | Subscription upgrade modal with promo display | | | | |
| 12.4.4 | Promotion conditions enforced (email_endswith, new_users, etc.) | | | | |

### 12.5 Stripe Webhook
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 12.5.1 | Webhook processes checkout.session.completed | | | | |
| 12.5.2 | Webhook processes subscription updates | | | | |
| 12.5.3 | Webhook processes payment failures | | | | |

---

## 13. Store

### 13.1 Store Browsing
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 13.1.1 | View store categories list | | | | |
| 13.1.2 | View category detail with items | | | | |
| 13.1.3 | View store items list | | | | |
| 13.1.4 | View item detail page | | | | |
| 13.1.5 | View featured items | | | | |
| 13.1.6 | Item preview (try-on) | | | | |
| 13.1.7 | Search and filter items | | | | |

### 13.2 Purchases
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 13.2.1 | Purchase item with Stripe | | | | |
| 13.2.2 | Confirm Stripe purchase | | | | |
| 13.2.3 | Purchase item with XP | | | | |
| 13.2.4 | Already-owned item shows appropriate state | | | | |

### 13.3 Inventory
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 13.3.1 | View user inventory | | | | |
| 13.3.2 | Equip an item | | | | |
| 13.3.3 | Unequip an item | | | | |
| 13.3.4 | View purchase history | | | | |

### 13.4 Wishlist
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 13.4.1 | Add item to wishlist | | | | |
| 13.4.2 | Remove item from wishlist | | | | |
| 13.4.3 | View wishlist | | | | |

### 13.5 Gifting
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 13.5.1 | Send a gift to another user | | | | |
| 13.5.2 | Claim a received gift | | | | |
| 13.5.3 | View gifts list (sent/received) | | | | |
| 13.5.4 | Gifting screen loads | | | | |

### 13.6 Refunds
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 13.6.1 | Request a refund | | | | |
| 13.6.2 | Admin: process refund | | | | |

---

## 14. Referrals

| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 14.1 | View my referral code | | | | |
| 14.2 | Share referral code (copy/share) | | | | |
| 14.3 | Redeem a referral code | | | | |
| 14.4 | View my referrals list | | | | |
| 14.5 | View my referral rewards | | | | |
| 14.6 | Claim a referral reward | | | | |
| 14.7 | Referral screen loads correctly | | | | |

---

## 15. Leagues & Rankings

### 15.1 Leagues
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 15.1.1 | View all leagues list (Bronze through Legend) | | | | |
| 15.1.2 | View league detail (XP range, rewards) | | | | |
| 15.1.3 | League subscription gate enforced | | | | |

### 15.2 Leaderboard
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 15.2.1 | Global leaderboard loads (top 100) | | | | |
| 15.2.2 | League-specific leaderboard | | | | |
| 15.2.3 | Friends leaderboard | | | | |
| 15.2.4 | Personal standing (my rank and stats) | | | | |
| 15.2.5 | Nearby ranks (users above and below) | | | | |
| 15.2.6 | Group leaderboard | | | | |
| 15.2.7 | Leaderboard screen loads with tabs | | | | |

### 15.3 Seasons
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 15.3.1 | View current season | | | | |
| 15.3.2 | View past seasons | | | | |
| 15.3.3 | Season detail screen loads | | | | |
| 15.3.4 | View my season rewards | | | | |
| 15.3.5 | Claim season reward | | | | |

### 15.4 League Seasons
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 15.4.1 | View current league season | | | | |
| 15.4.2 | Join current league season | | | | |
| 15.4.3 | View league season leaderboard | | | | |
| 15.4.4 | Claim end-of-season rewards | | | | |

### 15.5 Groups
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 15.5.1 | View league groups | | | | |
| 15.5.2 | View my group | | | | |
| 15.5.3 | Group detail with members | | | | |
| 15.5.4 | Group leaderboard screen | | | | |

---

## 16. Gamification

| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 16.1 | Gamification profile loads (XP, level, streak) | | | | |
| 16.2 | XP progress bar displays correctly | | | | |
| 16.3 | Level-up notification/animation works | | | | |
| 16.4 | Streak counter accurate | | | | |
| 16.5 | Streak details: current streak, best streak | | | | |
| 16.6 | Streak freeze: use a freeze when streak at risk | | | | |
| 16.7 | Achievements list loads | | | | |
| 16.8 | Achievements screen: unlocked vs locked display | | | | |
| 16.9 | Achievement unlock notification | | | | |
| 16.10 | Activity heatmap displays | | | | |
| 16.11 | Daily stats load correctly | | | | |
| 16.12 | Leaderboard stats (gamification) | | | | |

---

## 17. Profile & Settings

### 17.1 Profile
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 17.1.1 | Profile page loads (bento grid layout) | | | | |
| 17.1.2 | Profile shows avatar, name, bio, level, XP, streak | | | | |
| 17.1.3 | Edit profile: update display name | | | | |
| 17.1.4 | Edit profile: update bio | | | | |
| 17.1.5 | Edit profile: update location | | | | |
| 17.1.6 | Upload avatar image (JPEG, PNG, GIF, WebP) | | | | |
| 17.1.7 | Avatar upload: file size > 5MB rejected | | | | |
| 17.1.8 | Avatar upload: invalid file type rejected | | | | |
| 17.1.9 | Avatar syncs across all views (feed, comments, etc.) | | | | |
| 17.1.10 | Profile completeness indicator | | | | |

### 17.2 Persona & Energy Profile
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 17.2.1 | View persona profile | | | | |
| 17.2.2 | Update persona profile | | | | |
| 17.2.3 | View energy profile | | | | |
| 17.2.4 | Update energy profile | | | | |
| 17.2.5 | Persona screen loads correctly | | | | |

### 17.3 Settings
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 17.3.1 | Settings screen loads with all options | | | | |
| 17.3.2 | Change password (from settings) | | | | |
| 17.3.3 | Change email (sends verification to new email) | | | | |
| 17.3.4 | Verify email change via token link | | | | |
| 17.3.5 | Update notification preferences | | | | |
| 17.3.6 | Language setting (i18n: 16 languages) | | | | |
| 17.3.7 | Timezone setting | | | | |

### 17.4 Two-Factor Authentication (2FA)
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 17.4.1 | 2FA setup: generate QR code / secret | | | | |
| 17.4.2 | 2FA verify setup: enter TOTP code to activate | | | | |
| 17.4.3 | 2FA status check | | | | |
| 17.4.4 | Login with 2FA: challenge screen appears | | | | |
| 17.4.5 | Login with 2FA: valid TOTP code grants access | | | | |
| 17.4.6 | Login with 2FA: invalid code rejected | | | | |
| 17.4.7 | Regenerate backup codes | | | | |
| 17.4.8 | Login with backup code works | | | | |
| 17.4.9 | Disable 2FA (requires password) | | | | |
| 17.4.10 | 2FA screen loads correctly | | | | |

### 17.5 Data & Privacy
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 17.5.1 | Export data as JSON | | | | |
| 17.5.2 | Export data as CSV | | | | |
| 17.5.3 | Data export screen loads | | | | |
| 17.5.4 | Delete account (soft-delete with password confirmation) | | | | |
| 17.5.5 | Delete account: data anonymized | | | | |
| 17.5.6 | Delete account: Stripe subscription canceled | | | | |
| 17.5.7 | Privacy policy page loads | | | | |
| 17.5.8 | Terms of service page loads | | | | |
| 17.5.9 | Blocked users screen loads | | | | |
| 17.5.10 | Profile visibility setting works (public/friends/private) | | | | |

### 17.6 App Info
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 17.6.1 | App version screen loads | | | | |
| 17.6.2 | OTA update check works | | | | |

---

## 18. Search

| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 18.1 | Global search endpoint returns results | | | | |
| 18.2 | Dream search returns matching dreams | | | | |
| 18.3 | User search returns matching users | | | | |
| 18.4 | Search with empty query returns appropriate response | | | | |

---

## 19. Cross-Device & Responsive Layout

### 19.1 Layout Breakpoints
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 19.1.1 | Mobile layout correct (< 768px) | | | | |
| 19.1.2 | Tablet layout correct (768-1024px) | | | | |
| 19.1.3 | Desktop layout correct (> 1024px) | | | | |
| 19.1.4 | Responsive transition between breakpoints is smooth | | | | |

### 19.2 Navigation Components
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 19.2.1 | Bottom nav visible on mobile only | | | | |
| 19.2.2 | Sidebar visible on desktop | | | | |
| 19.2.3 | Tablet navigation renders correctly | | | | |
| 19.2.4 | DesktopPageHeader renders on all desktop pages | | | | |
| 19.2.5 | TabletPageHeader renders on all tablet pages | | | | |

### 19.3 Adaptive Components
| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 19.3.1 | AdaptiveSheet: bottom sheet on mobile | | | | |
| 19.3.2 | AdaptiveSheet: centered modal on desktop/tablet | | | | |
| 19.3.3 | Touch interactions work on mobile (swipe, tap) | | | | |
| 19.3.4 | Glass morphism renders on all devices | | | | |
| 19.3.5 | Glass morphism: backdrop-filter blur works | | | | |
| 19.3.6 | CSS variables (--dp-*) applied correctly | | | | |

---

## 20. Navigation & Routing

| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 20.1 | Any page reachable in 2 clicks from home | | | | |
| 20.2 | Back button works everywhere | | | | |
| 20.3 | Deep links work (direct URL to dream detail) | | | | |
| 20.4 | Deep links work (direct URL to circle detail) | | | | |
| 20.5 | Deep links work (direct URL to user profile) | | | | |
| 20.6 | 404 page displays for invalid routes | | | | |
| 20.7 | HashRouter navigation works correctly | | | | |
| 20.8 | Page transitions smooth (no BottomNav position:fixed breaking) | | | | |
| 20.9 | Protected routes redirect to login when not authenticated | | | | |
| 20.10 | Post-login redirect returns to intended page | | | | |

---

## 21. WebSocket / Real-time Features

| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 21.1 | WebSocket connection established on login | | | | |
| 21.2 | Real-time chat messages (friend chat) | | | | |
| 21.3 | Real-time chat messages (buddy chat) | | | | |
| 21.4 | Real-time circle chat messages | | | | |
| 21.5 | Real-time AI streaming responses | | | | |
| 21.6 | Real-time notifications push | | | | |
| 21.7 | Real-time social feed updates | | | | |
| 21.8 | Real-time league leaderboard updates | | | | |
| 21.9 | WebSocket reconnection after network drop | | | | |
| 21.10 | WebSocket auth token validation | | | | |

---

## 22. Performance

| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 22.1 | Initial page load < 3 seconds | | | | |
| 22.2 | Navigation between pages < 1 second | | | | |
| 22.3 | API calls complete < 2 seconds (non-AI) | | | | |
| 22.4 | AI API calls complete < 15 seconds | | | | |
| 22.5 | No visible layout shifts (CLS) | | | | |
| 22.6 | Smooth animations at 60fps | | | | |
| 22.7 | Image lazy loading works | | | | |
| 22.8 | Pagination works on long lists (infinite scroll or pages) | | | | |
| 22.9 | No memory leaks on repeated navigation | | | | |
| 22.10 | Bundle size reasonable (< 500KB initial) | | | | |

---

## 23. Accessibility

| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 23.1 | Tab navigation works through interactive elements | | | | |
| 23.2 | Screen reader labels present (aria-label, alt text) | | | | |
| 23.3 | Color contrast ratios meet WCAG AA | | | | |
| 23.4 | Touch targets >= 44px on mobile | | | | |
| 23.5 | Focus indicators visible on keyboard navigation | | | | |
| 23.6 | Form inputs have associated labels | | | | |
| 23.7 | Error messages announced to screen readers | | | | |
| 23.8 | Skip navigation link present | | | | |
| 23.9 | Modals trap focus correctly | | | | |

---

## 24. Error Handling & Edge Cases

| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 24.1 | Offline banner when network disconnected | | | | |
| 24.2 | API errors show toast notification (not crash) | | | | |
| 24.3 | Empty states display correctly (no dreams, no friends, etc.) | | | | |
| 24.4 | Loading skeletons display during data fetch | | | | |
| 24.5 | 401 error triggers token refresh, not logout | | | | |
| 24.6 | 403 error shows subscription upgrade prompt | | | | |
| 24.7 | 429 rate limit shows "try again later" message | | | | |
| 24.8 | 500 server error shows generic error message | | | | |
| 24.9 | Form validation errors display inline | | | | |
| 24.10 | Long text content does not overflow containers | | | | |
| 24.11 | Special characters in input fields handled correctly | | | | |
| 24.12 | Concurrent actions do not cause race conditions | | | | |
| 24.13 | Browser back/forward buttons work with SPA routing | | | | |

---

## 25. Internationalization (i18n)

| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 25.1 | Default language (French) loads correctly | | | | |
| 25.2 | Switch to English: all strings translated | | | | |
| 25.3 | All 16 languages selectable | | | | |
| 25.4 | Language persists after page refresh | | | | |
| 25.5 | Date/time formats adapt to locale | | | | |
| 25.6 | RTL languages render correctly (if applicable) | | | | |
| 25.7 | No untranslated keys visible (t("key") fallback check) | | | | |
| 25.8 | API error messages respect Accept-Language header | | | | |

---

## 26. Security

| # | Test Case | Mobile | Tablet | Desktop | Notes |
|---|-----------|--------|--------|---------|-------|
| 26.1 | IDOR protection: cannot access other user's dreams | | | | |
| 26.2 | IDOR protection: cannot access other user's tasks/goals | | | | |
| 26.3 | IDOR protection: cannot modify other user's profile | | | | |
| 26.4 | Rate limiting on login endpoint | | | | |
| 26.5 | Rate limiting on registration endpoint | | | | |
| 26.6 | Rate limiting on password reset endpoint | | | | |
| 26.7 | Rate limiting on AI endpoints | | | | |
| 26.8 | Rate limiting on check-in endpoints | | | | |
| 26.9 | CORS headers correct (only allowed origins) | | | | |
| 26.10 | Content-Type validation on file uploads | | | | |
| 26.11 | Magic bytes validation on avatar uploads | | | | |
| 26.12 | Path traversal prevention on file uploads | | | | |
| 26.13 | XSS prevention: user-generated content sanitized | | | | |
| 26.14 | CSRF protection on state-changing endpoints | | | | |
| 26.15 | JWT tokens have appropriate expiry times | | | | |

---

## Bug Report Template

| # | Page | Device | Steps to Reproduce | Expected Result | Actual Result | Severity | Screenshot |
|---|------|--------|---------------------|-----------------|---------------|----------|------------|
| 1 | | | | | | P0/P1/P2/P3 | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |
| 6 | | | | | | | |
| 7 | | | | | | | |
| 8 | | | | | | | |
| 9 | | | | | | | |
| 10 | | | | | | | |

### Severity Definitions
- **P0 (Critical)**: App crash, data loss, security vulnerability, complete feature broken
- **P1 (High)**: Major feature broken, significant UX issue, blocks core workflow
- **P2 (Medium)**: Minor feature broken, cosmetic issue affecting usability
- **P3 (Low)**: Cosmetic issue, minor polish, nice-to-have improvement

---

## Test Session Summary

| Metric | Value |
|--------|-------|
| Total Test Cases | ~350 |
| Passed | ____ |
| Failed | ____ |
| Skipped | ____ |
| Bugs Found | ____ |
| P0 Bugs | ____ |
| P1 Bugs | ____ |
| P2 Bugs | ____ |
| P3 Bugs | ____ |
| Completion % | ____% |
| Test Duration | ____ hours |
| Notes | |
