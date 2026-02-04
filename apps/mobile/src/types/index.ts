/**
 * Core TypeScript type definitions for DreamPlanner mobile app.
 * Covers all domain models, API responses, and navigation types.
 */

// ============================================================
// User types
// ============================================================

export interface User {
  id: string;
  email: string;
  displayName: string | null;
  avatarUrl: string | null;
  timezone: string;
  subscription: SubscriptionTier;
  language: SupportedLanguage;
}

export type SubscriptionTier = 'free' | 'premium' | 'pro';

export type SupportedLanguage =
  | 'en' | 'fr' | 'es' | 'pt' | 'ar' | 'zh'
  | 'hi' | 'ja' | 'de' | 'ru' | 'ko' | 'it'
  | 'tr' | 'nl' | 'pl';

export interface WorkSchedule {
  workDays: number[]; // 0-6, 0 = Sunday
  startTime: string;  // "HH:mm"
  endTime: string;    // "HH:mm"
}

export interface NotificationPrefs {
  reminders: boolean;
  reminderMinutesBefore: number;
  motivation: boolean;
  dndEnabled: boolean;
  dndStart: number;
  dndEnd: number;
}

export interface AppPreferences {
  theme: 'light' | 'dark' | 'system';
  language: SupportedLanguage;
}

// ============================================================
// Chat types
// ============================================================

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

export interface Conversation {
  id: string;
  dreamId?: string;
  type: 'dream_creation' | 'planning' | 'check_in' | 'general';
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

// ============================================================
// Dream types
// ============================================================

export interface Dream {
  id: string;
  title: string;
  description: string;
  category: DreamCategory;
  targetDate?: Date;
  priority: number;
  status: DreamStatus;
  progress: number;
  createdAt: Date;
  updatedAt: Date;
  goals: Goal[];
}

export type DreamCategory =
  | 'career'
  | 'health'
  | 'education'
  | 'personal'
  | 'finance'
  | 'travel'
  | 'creativity'
  | 'wellness';

export type DreamStatus = 'active' | 'completed' | 'paused' | 'archived';

export interface Goal {
  id: string;
  dreamId: string;
  title: string;
  description?: string;
  order: number;
  status: 'pending' | 'in_progress' | 'completed' | 'skipped';
  progress: number;
  tasks: Task[];
}

export interface Task {
  id: string;
  goalId: string;
  title: string;
  description?: string;
  scheduledDate?: Date;
  scheduledTime?: string;
  durationMins?: number;
  status: 'pending' | 'completed' | 'skipped';
  completedAt?: Date;
}

// ============================================================
// Subscription types
// ============================================================

export interface SubscriptionPlan {
  id: string;
  name: string;
  tier: SubscriptionTier;
  priceMonthly: number;
  priceYearly: number;
  features: string[];
  stripePriceIdMonthly: string;
  stripePriceIdYearly: string;
}

export interface UserSubscription {
  id: string;
  tier: SubscriptionTier;
  status: 'active' | 'canceled' | 'past_due' | 'trialing';
  currentPeriodStart: string;
  currentPeriodEnd: string;
  cancelAtPeriodEnd: boolean;
  stripeSubscriptionId: string;
}

// ============================================================
// Store types
// ============================================================

export interface StoreCategory {
  id: string;
  name: string;
  slug: string;
  description: string;
  icon: string;
}

export interface StoreItem {
  id: string;
  name: string;
  description: string;
  category: StoreCategory;
  price: number;
  imageUrl: string;
  itemType: 'skin' | 'badge_frame' | 'theme' | 'avatar' | 'effect';
  previewData: Record<string, unknown>;
  isActive: boolean;
}

export interface UserInventoryItem {
  id: string;
  item: StoreItem;
  purchasedAt: string;
  isEquipped: boolean;
}

// ============================================================
// League types
// ============================================================

export type LeagueTier = 'bronze' | 'silver' | 'gold' | 'platinum' | 'diamond' | 'master' | 'legend';

export interface League {
  id: string;
  name: string;
  tier: LeagueTier;
  icon: string;
  minScore: number;
  maxScore: number;
  color: string;
}

export interface LeagueStanding {
  id: string;
  userId: string;
  username: string;
  avatarUrl: string | null;
  league: League;
  weeklyScore: number;
  rank: number;
  badges: string[];
}

export interface Season {
  id: string;
  name: string;
  startDate: string;
  endDate: string;
  isActive: boolean;
}

// ============================================================
// Social types
// ============================================================

export interface ActivityItem {
  id: string;
  type: string;
  user: {
    id: string;
    username: string;
    avatar?: string;
  };
  content: Record<string, unknown>;
  createdAt: string;
}

export interface FriendRequest {
  id: string;
  sender: {
    id: string;
    username: string;
    avatar?: string;
  };
  status: 'pending' | 'accepted' | 'rejected';
  createdAt: string;
}

// ============================================================
// Buddy types
// ============================================================

export interface DreamBuddy {
  id: string;
  partnerId: string;
  partnerName: string;
  partnerAvatar?: string;
  sharedDreamCategory: DreamCategory;
  startedAt: string;
  isActive: boolean;
}

// ============================================================
// Circle types
// ============================================================

export interface Circle {
  id: string;
  name: string;
  description: string;
  category: DreamCategory;
  memberCount: number;
  isPublic: boolean;
  createdBy: string;
}

export interface CircleMember {
  id: string;
  userId: string;
  username: string;
  avatarUrl?: string;
  role: 'owner' | 'admin' | 'member';
  joinedAt: string;
}

export interface CircleChallenge {
  id: string;
  title: string;
  description: string;
  startDate: string;
  endDate: string;
  participantCount: number;
}

// ============================================================
// Vision Board types
// ============================================================

export interface VisionBoard {
  id: string;
  dreamId: string;
  title: string;
  imageUrl: string;
  generatedPrompt: string;
  createdAt: string;
}

// ============================================================
// Gamification types
// ============================================================

export interface GamificationProfile {
  xp: number;
  level: number;
  currentStreak: number;
  longestStreak: number;
  badges: Badge[];
  title: string;
}

export interface Badge {
  id: string;
  name: string;
  description: string;
  icon: string;
  earnedAt?: string;
}

// ============================================================
// API Response types
// ============================================================

export interface ApiResponse<T> {
  data: T;
  success: boolean;
  error?: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface PlanningResult {
  analysis: string;
  feasibility: 'high' | 'medium' | 'low';
  estimatedDuration: string;
  weeklyTimeRequired: string;
  goals: GeneratedGoal[];
  tips: string[];
  potentialObstacles: string[];
}

export interface GeneratedGoal {
  title: string;
  description: string;
  durationWeeks: number;
  tasks: GeneratedTask[];
}

export interface GeneratedTask {
  title: string;
  durationMins: number;
  frequency: 'daily' | 'weekly' | 'once';
  days?: number[];
}

// ============================================================
// Navigation types
// ============================================================

export type RootStackParamList = {
  Auth: undefined;
  Main: undefined;
};

export type AuthStackParamList = {
  Login: undefined;
  Register: undefined;
  ForgotPassword: undefined;
};

export type MainTabParamList = {
  Home: undefined;
  Calendar: undefined;
  Chat: undefined;
  Social: undefined;
  Profile: undefined;
};

export type HomeStackParamList = {
  HomeScreen: undefined;
  DreamDetail: { dreamId: string };
  CreateDream: undefined;
  VisionBoard: { dreamId: string };
  MicroStart: { dreamId: string; microTask: string };
};

export type SocialStackParamList = {
  SocialScreen: undefined;
  CirclesScreen: undefined;
  CircleDetail: { circleId: string };
  DreamBuddy: undefined;
  Leaderboard: undefined;
  LeagueDetail: { leagueId: string };
};

export type ProfileStackParamList = {
  ProfileScreen: undefined;
  Subscription: undefined;
  Store: undefined;
  Settings: undefined;
};
