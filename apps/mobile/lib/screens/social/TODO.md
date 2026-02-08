# Social Screens - TODO

## Current Status
- social_screen.dart: Activity feed works (read-only)
- circles_screen.dart: List works, create circle FAB is empty
- circle_detail_screen.dart: Shows members only, no feed/challenges tabs
- dream_buddy_screen.dart: Shows current buddy, "Request" button is empty
- leaderboard_screen.dart: Fully functional

## Placeholders to Fix

### circles_screen.dart
- [ ] **FAB create circle** (onPressed empty): Show create circle bottom sheet with name, description, category dropdown, is_public toggle; call `POST /api/circles/`

### dream_buddy_screen.dart
- [ ] **"Request" button** (onPressed empty): Call `POST /api/buddies/pair/` with partner_id, reload data after pairing

### circle_detail_screen.dart
- [ ] Add "Leave Circle" button in AppBar actions; call `POST /api/circles/{id}/leave/`
- [ ] Add TabBar: Members / Feed / Challenges
- [ ] Feed tab: Load posts from `GET /api/circles/{id}/feed/`, add post creation TextField + send button
- [ ] Challenges tab: Load from `GET /api/circles/{id}/challenges/`, show join button per challenge
- [ ] Add "Join Circle" button for non-members viewing public circles

### social_screen.dart
- [ ] Add friend request notification badge count
- [ ] Add "Create Circle" option (same as circles_screen FAB)

## Missing Screens
- [ ] Friends list screen: Show accepted friends from `GET /api/social/friends/`
- [ ] User search screen: Search users via `GET /api/social/search/?q=`
- [ ] Pending friend requests screen: `GET /api/social/friends/requests/pending`

## Small Improvements
- [ ] Add accept/reject buttons on friend request items
- [ ] Add follow/unfollow toggle on user profiles
- [ ] Add buddy encouragement message input (backend: `POST /api/buddies/{id}/encourage/`)
- [ ] Show compatibility score explanation on buddy detail
