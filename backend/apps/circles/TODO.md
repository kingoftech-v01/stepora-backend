# Circles App - TODO

## Planned Features

- [ ] **Circle edit and delete** - Add PUT/PATCH and DELETE endpoints for circles. Only admins should be able to edit circle details (name, description, category, visibility) or delete the entire circle. Deleting a circle should cascade-delete memberships, posts, and challenges.

- [ ] **Invitation system** - Implement an invite mechanism for private circles. Allow admins/moderators to generate invite links or send direct invitations to users. Track pending invitations with accept/reject flow.

- [ ] **Moderator management** - Add endpoints to promote members to moderator, demote moderators to member, and transfer admin ownership. Moderators should be able to delete posts and remove members.

- [ ] **Post editing and deletion** - Allow post authors to edit or delete their own posts. Allow moderators and admins to delete any post. Add `edited_at` timestamp for transparency.

- [ ] **Post reactions** - Add a reaction system for circle posts (e.g., thumbs up, fire, clap, heart). Track reactions per post per user to prevent duplicates. Return reaction counts in the post serializer.

- [ ] **Challenge progress tracking** - Track individual participant progress within challenges. Add a progress update endpoint where participants can log their daily/weekly progress. Display progress leaderboards within challenges.

## Improvements

- [ ] **Circle search** - Add a search endpoint for discovering circles by name or description text, with category and membership size filters.

- [ ] **Circle activity stats** - Track and expose circle activity metrics: posts per day, active members, challenge participation rate. Use these for the "recommended" filter algorithm.

- [ ] **Pin posts** - Allow admins/moderators to pin important posts to the top of the feed.

- [ ] **Challenge creation endpoint** - Add a POST endpoint for admins/moderators to create challenges via the API rather than only through the admin panel.

- [ ] **Member activity indicators** - Show when members were last active in the circle (last post date, last visit) to help identify inactive members.
