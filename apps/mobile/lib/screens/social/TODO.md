# Social Screens - TODO

## Current Status
- social_screen.dart: Activity feed works (read-only)
- circles_screen.dart: List works, create circle FAB functional
- circle_detail_screen.dart: Shows members, feed, and challenges tabs
- dream_buddy_screen.dart: Shows current buddy, request button functional
- leaderboard_screen.dart: Fully functional

## Placeholders to Fix

### circles_screen.dart
- [x] **FAB create circle** (onPressed empty): Show create circle bottom sheet with name, description, category dropdown, is_public toggle; call `POST /api/circles/`

### dream_buddy_screen.dart
- [x] **"Request" button** (onPressed empty): Call `POST /api/buddies/pair/` with partner_id, reload data after pairing

### circle_detail_screen.dart
- [x] Add "Leave Circle" button in AppBar actions; call `POST /api/circles/{id}/leave/`
- [x] Add TabBar: Members / Feed / Challenges
- [x] Feed tab: Load posts from `GET /api/circles/{id}/feed/`, add post creation TextField + send button
- [x] Challenges tab: Load from `GET /api/circles/{id}/challenges/`, show join button per challenge
- [x] Add "Join Circle" button for non-members viewing public circles

### social_screen.dart
- [ ] Add friend request notification badge count
- [ ] Add "Create Circle" option (same as circles_screen FAB)

## Missing Screens
- [x] Friends list screen: Show accepted friends from `GET /api/social/friends/`
- [x] User search screen: Search users via `GET /api/social/search/?q=`
- [x] Pending friend requests screen: `GET /api/social/friends/requests/pending`

## Small Improvements
- [x] Add accept/reject buttons on friend request items
- [x] Add follow/unfollow toggle on user profiles
- [x] Add buddy encouragement message input (backend: `POST /api/buddies/{id}/encourage/`)
- [x] Add circle invite button
- [ ] Show compatibility score explanation on buddy detail
