import { z } from 'zod';

// Auth validators
export const createUserSchema = z.object({
  idToken: z.string().min(1),
  email: z.string().email(),
  displayName: z.string().min(1).max(100).optional(),
  timezone: z.string().default('Europe/Paris'),
  fcmToken: z.string().optional(),
  platform: z.enum(['ios', 'android']).optional(),
});

export const loginSchema = z.object({
  idToken: z.string().min(1),
  fcmToken: z.string().optional(),
  platform: z.enum(['ios', 'android']).optional(),
});

// User validators
export const updateUserSchema = z.object({
  displayName: z.string().min(1).max(100).optional(),
  avatarUrl: z.string().url().optional().nullable(),
  timezone: z.string().optional(),
  workSchedule: z
    .object({
      workDays: z.array(z.number().min(0).max(6)),
      startTime: z.string().regex(/^\d{2}:\d{2}$/),
      endTime: z.string().regex(/^\d{2}:\d{2}$/),
    })
    .optional(),
  notificationPrefs: z
    .object({
      reminders: z.boolean(),
      reminderMinutesBefore: z.number().min(0).max(60),
      motivation: z.boolean(),
      motivationTime: z.string().optional(),
      weeklyReport: z.boolean().optional(),
      weeklyReportDay: z.number().min(0).max(6).optional(),
      dndEnabled: z.boolean(),
      dndStart: z.number().min(0).max(23),
      dndEnd: z.number().min(0).max(23),
    })
    .optional(),
  appPrefs: z
    .object({
      theme: z.enum(['light', 'dark', 'system']),
      language: z.enum(['fr', 'en']),
    })
    .optional(),
});

// Dream validators
export const createDreamSchema = z.object({
  title: z.string().min(1).max(200),
  description: z.string().min(1).max(5000),
  category: z.enum([
    'career',
    'health',
    'education',
    'personal',
    'finance',
    'travel',
    'creativity',
    'wellness',
  ]).optional(),
  targetDate: z.string().optional(),
  priority: z.number().min(1).max(5).default(1),
});

export const updateDreamSchema = z.object({
  title: z.string().min(1).max(200).optional(),
  description: z.string().min(1).max(5000).optional(),
  category: z.enum([
    'career',
    'health',
    'education',
    'personal',
    'finance',
    'travel',
    'creativity',
    'wellness',
  ]).optional(),
  targetDate: z.string().optional().nullable(),
  priority: z.number().min(1).max(5).optional(),
  status: z.enum(['active', 'completed', 'paused', 'archived']).optional(),
});

// Goal validators
export const createGoalSchema = z.object({
  dreamId: z.string().min(1),
  title: z.string().min(1).max(200),
  description: z.string().max(2000).optional(),
  estimatedMinutes: z.number().min(0).optional(),
  scheduledStart: z.string().optional(),
  scheduledEnd: z.string().optional(),
  reminderEnabled: z.boolean().optional(),
  reminderTime: z.string().optional(),
});

export const updateGoalSchema = z.object({
  title: z.string().min(1).max(200).optional(),
  description: z.string().max(2000).optional(),
  status: z.enum(['pending', 'in_progress', 'completed', 'skipped']).optional(),
  estimatedMinutes: z.number().min(0).optional(),
  scheduledStart: z.string().optional().nullable(),
  scheduledEnd: z.string().optional().nullable(),
  reminderEnabled: z.boolean().optional(),
  reminderTime: z.string().optional().nullable(),
});

// Task validators
export const createTaskSchema = z.object({
  goalId: z.string().min(1),
  title: z.string().min(1).max(200),
  description: z.string().max(1000).optional(),
  scheduledDate: z.string().optional(),
  scheduledTime: z.string().regex(/^\d{2}:\d{2}$/).optional(),
  durationMins: z.number().min(1).max(480).optional(),
  recurrence: z
    .object({
      type: z.enum(['daily', 'weekly']),
      days: z.array(z.number().min(0).max(6)).optional(),
      until: z.string().optional(),
    })
    .optional(),
});

export const updateTaskSchema = z.object({
  title: z.string().min(1).max(200).optional(),
  description: z.string().max(1000).optional(),
  scheduledDate: z.string().optional().nullable(),
  scheduledTime: z.string().regex(/^\d{2}:\d{2}$/).optional().nullable(),
  durationMins: z.number().min(1).max(480).optional(),
  status: z.enum(['pending', 'completed', 'skipped']).optional(),
  recurrence: z
    .object({
      type: z.enum(['daily', 'weekly']),
      days: z.array(z.number().min(0).max(6)).optional(),
      until: z.string().optional(),
    })
    .optional()
    .nullable(),
});

// Conversation validators
export const createConversationSchema = z.object({
  type: z.enum(['dream_creation', 'planning', 'check_in', 'adjustment', 'general']),
  dreamId: z.string().optional(),
});

export const sendMessageSchema = z.object({
  content: z.string().min(1).max(10000),
});

// Calendar validators
export const getCalendarSchema = z.object({
  start: z.string(),
  end: z.string(),
});

// Types
export type CreateUserInput = z.infer<typeof createUserSchema>;
export type LoginInput = z.infer<typeof loginSchema>;
export type UpdateUserInput = z.infer<typeof updateUserSchema>;
export type CreateDreamInput = z.infer<typeof createDreamSchema>;
export type UpdateDreamInput = z.infer<typeof updateDreamSchema>;
export type CreateGoalInput = z.infer<typeof createGoalSchema>;
export type UpdateGoalInput = z.infer<typeof updateGoalSchema>;
export type CreateTaskInput = z.infer<typeof createTaskSchema>;
export type UpdateTaskInput = z.infer<typeof updateTaskSchema>;
export type CreateConversationInput = z.infer<typeof createConversationSchema>;
export type SendMessageInput = z.infer<typeof sendMessageSchema>;
