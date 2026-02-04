import { z } from 'zod';

export const registerSchema = z.object({
  body: z.object({
    displayName: z.string().min(2).max(50).optional(),
    timezone: z.string().optional(),
  }),
});

export const updateProfileSchema = z.object({
  body: z.object({
    displayName: z.string().min(2).max(50).optional(),
    timezone: z.string().optional(),
    workSchedule: z.object({
      workDays: z.array(z.number().min(0).max(6)),
      startTime: z.string().regex(/^\d{2}:\d{2}$/),
      endTime: z.string().regex(/^\d{2}:\d{2}$/),
    }).optional(),
    appPreferences: z.object({
      theme: z.enum(['light', 'dark', 'system']).optional(),
      language: z.enum(['en', 'fr']).optional(),
    }).optional(),
    notificationPrefs: z.object({
      reminders: z.boolean().optional(),
      motivation: z.boolean().optional(),
      progress: z.boolean().optional(),
      achievements: z.boolean().optional(),
      dndMode: z.object({
        enabled: z.boolean(),
        startTime: z.string().regex(/^\d{2}:\d{2}$/),
        endTime: z.string().regex(/^\d{2}:\d{2}$/),
      }).optional(),
    }).optional(),
  }),
});
