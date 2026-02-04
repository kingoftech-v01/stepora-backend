-- Performance Indexes Migration
-- Add indexes for frequently queried columns to improve performance

-- User indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid);

-- Dream indexes (already have userId and status composite index)
CREATE INDEX IF NOT EXISTS idx_dreams_category ON dreams(category);
CREATE INDEX IF NOT EXISTS idx_dreams_target_date ON dreams(target_date);

-- Task indexes (already have goalId and scheduledDate composite index)
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_completed_at ON tasks(completed_at);

-- UserProfile indexes for leaderboards
CREATE INDEX IF NOT EXISTS idx_user_profiles_influence_score ON user_profiles(influence_score DESC);
CREATE INDEX IF NOT EXISTS idx_user_profiles_total_xp ON user_profiles(total_xp DESC);
CREATE INDEX IF NOT EXISTS idx_user_profiles_current_level ON user_profiles(current_level DESC);

-- XP Transaction indexes
CREATE INDEX IF NOT EXISTS idx_xp_transactions_source ON xp_transactions(source);

-- Friendship indexes
CREATE INDEX IF NOT EXISTS idx_friendships_status ON friendships(status);

-- DreamBuddy indexes
CREATE INDEX IF NOT EXISTS idx_dream_buddies_status ON dream_buddies(status);

-- CircleMember indexes
CREATE INDEX IF NOT EXISTS idx_circle_members_left_at ON circle_members(left_at);

-- CirclePost indexes for feeds
CREATE INDEX IF NOT EXISTS idx_circle_posts_created_at ON circle_posts(created_at DESC);

-- ActivityFeed indexes
CREATE INDEX IF NOT EXISTS idx_activity_feeds_visibility ON activity_feeds(visibility);

-- Notification indexes
CREATE INDEX IF NOT EXISTS idx_notifications_scheduled_for ON notifications(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_notifications_sent_at ON notifications(sent_at);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_tasks_goal_status ON tasks(goal_id, status);
CREATE INDEX IF NOT EXISTS idx_dreams_user_category ON dreams(user_id, category, status);
CREATE INDEX IF NOT EXISTS idx_notifications_user_status ON notifications(user_id, status, scheduled_for);

-- Add partial indexes for active records only (more efficient)
CREATE INDEX IF NOT EXISTS idx_active_dreams ON dreams(user_id, status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_pending_tasks ON tasks(goal_id) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_active_circle_members ON circle_members(circle_id) WHERE left_at IS NULL;

-- Full-text search indexes (if using PostgreSQL)
CREATE INDEX IF NOT EXISTS idx_dreams_title_search ON dreams USING gin(to_tsvector('english', title));
CREATE INDEX IF NOT EXISTS idx_dreams_description_search ON dreams USING gin(to_tsvector('english', description));
