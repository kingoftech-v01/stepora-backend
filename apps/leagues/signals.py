"""
Signals for the Leagues & Ranking system.

League standings are updated via Celery Beat schedule (4x/day)
instead of real-time on every XP change. This reduces DB load
and avoids performance issues from cascading updates.

The pre_save/post_save hooks that previously updated standings
on every User.save() have been removed.
"""
