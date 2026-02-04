// User types
export interface User {
  id: string;
  email: string;
  displayName: string | null;
  avatarUrl: string | null;
  timezone: string;
  subscription: 'free' | 'premium' | 'pro';
}

export interface WorkSchedule {
  workDays: number[]; // 0-6, 0 = Sunday
  startTime: string; // "HH:mm"
  endTime: string; // "HH:mm"
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
  language: 'fr' | 'en';
}

// Chat types
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

// Dream types
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

// API Response types
export interface ApiResponse<T> {
  data: T;
  success: boolean;
  error?: string;
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

// Navigation types
export type RootStackParamList = {
  Onboarding: undefined;
  Auth: undefined;
  Main: undefined;
};

export type MainTabParamList = {
  Chat: undefined;
  Calendar: undefined;
  Dreams: undefined;
  Profile: undefined;
};

export type AuthStackParamList = {
  Login: undefined;
  Register: undefined;
  ForgotPassword: undefined;
};
