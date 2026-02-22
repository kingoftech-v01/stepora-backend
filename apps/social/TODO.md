# Social App - TODO

## Completed

- [x] **Unfollow endpoint** - POST/DELETE endpoint to unfollow a user.

- [x] **Unfriend endpoint** - POST/DELETE endpoint to remove an accepted friendship.

- [x] **Block user** - User blocking system with BlockedUser model and corresponding API endpoints. Blocked users cannot send friend requests, follow, or appear in search results.

- [x] **Followers/following counts** - API fields to retrieve a user's follower count and following count. Included in user profile and search result serializers.

- [x] **Feed filtering** - Query parameters on the activity feed endpoint for filtering by activity type and date range.

- [x] **Sent friend requests endpoint** - GET endpoint to list friend requests sent by the current user that are still pending.

- [x] **Mutual friends** - Endpoint showing mutual friends between the current user and another user.

- [x] **Follow suggestions** - Algorithm to suggest users to follow based on shared circles, mutual friends, similar goals, or activity levels.

- [x] **User reporting** - ReportedUser model with reporting endpoints.

## Planned Improvements

- [ ] **Friend request notifications** - Trigger push notifications when a user receives a friend request or when their request is accepted.

- [ ] **Activity feed optimization** - Cache the friend/follow ID sets to avoid recomputing them on every feed request. Consider using Redis sorted sets for efficient feed assembly.

- [ ] **Batch follow/friend operations** - Support following or sending friend requests to multiple users in a single API call for onboarding flows.
