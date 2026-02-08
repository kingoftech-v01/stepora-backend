# Buddies App - TODO

## Planned Features

- [ ] **Buddy request acceptance flow** - Change the pairing creation to a two-step process: the initiator sends a buddy request (status: `pending`), and the partner must accept before the pairing becomes `active`. Add accept/reject endpoints similar to the friendship system.

- [ ] **Buddy chat** - Add a real-time messaging channel between paired buddies. Integrate with the existing conversations/WebSocket infrastructure or create a dedicated buddy chat model for lightweight messaging.

- [ ] **Pairing history** - Add an endpoint to retrieve a user's past buddy pairings (completed and cancelled), including partner info, duration, compatibility score, and encouragement count. Useful for tracking accountability history.

- [ ] **Check-in reminders** - Implement automated reminder notifications to encourage buddies to check in with each other. Use Celery beat to schedule periodic reminders (e.g., every 3 days if no encouragement has been sent).

- [ ] **Encouragement streak tracking** - Track consecutive days where at least one encouragement was exchanged between buddies. Display the current and best encouragement streak in the pairing detail response.

## Improvements

- [ ] **Improved matching algorithm** - Enhance compatibility scoring with additional signals: shared dream categories, similar goal timelines, timezone compatibility, and preferred check-in frequency.

- [ ] **Buddy suggestions list** - Instead of returning a single best match, return a ranked list of top 3-5 matches so users can choose their preferred buddy partner.

- [ ] **Mutual pairing completion** - Add a `completed` status transition that requires both users to agree the pairing was successful, rather than only allowing `cancelled` as the end state.

- [ ] **Buddy activity feed** - Create a dedicated feed showing only the paired buddy's recent activity (tasks completed, dreams progressed, milestones reached) for easy at-a-glance accountability.

- [ ] **Rate limiting on encouragements** - Add a cooldown period between encouragement messages to prevent spam (e.g., max 5 encouragements per day per pairing).
