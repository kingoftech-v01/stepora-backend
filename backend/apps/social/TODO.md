# Social App - TODO

## Planned Features

- [ ] **Unfollow endpoint** - Add a POST or DELETE endpoint to unfollow a user. Currently there is no way to remove a follow relationship via the API.

- [ ] **Unfriend endpoint** - Add a POST or DELETE endpoint to remove an accepted friendship. Should delete the Friendship record or set it to a removed state so users can re-send requests later.

- [ ] **Block user** - Implement a user blocking system. Blocked users should not be able to send friend requests, follow, or appear in search results. Add a BlockedUser model and corresponding API endpoints.

- [ ] **Followers/following counts** - Add API endpoints or fields to retrieve a user's follower count and following count. Include these in the user profile and search result serializers.

- [ ] **Feed filtering** - Add query parameters to the activity feed endpoint for filtering by activity type (e.g., only show `dream_completed` or `badge_earned` items). Support date range filtering as well.

- [ ] **Sent friend requests endpoint** - Add a GET endpoint to list friend requests sent by the current user that are still pending, so users can track their outgoing requests.

## Improvements

- [ ] **Mutual friends** - Add an endpoint or field showing mutual friends between the current user and another user, useful for social discovery.

- [ ] **Friend request notifications** - Trigger push notifications when a user receives a friend request or when their request is accepted.

- [ ] **Follow suggestions** - Implement an algorithm to suggest users to follow based on shared circles, mutual friends, similar goals, or activity levels.

- [ ] **Activity feed optimization** - Cache the friend/follow ID sets to avoid recomputing them on every feed request. Consider using Redis sorted sets for efficient feed assembly.

- [ ] **Batch follow/friend operations** - Support following or sending friend requests to multiple users in a single API call for onboarding flows.
