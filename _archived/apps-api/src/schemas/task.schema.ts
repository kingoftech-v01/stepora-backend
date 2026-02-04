import { z } from 'zod';

export const updateTaskSchema = z.object({
  body: z.object({
    title: z.string().min(1).max(200).optional(),
    description: z.string().max(2000).optional(),
    scheduledDate: z.string().date().optional().nullable(),
    scheduledTime: z.string().regex(/^\d{2}:\d{2}$/).optional().nullable(),
    estimatedMinutes: z.number().int().min(1).max(1440).optional(),
    status: z.enum(['pending', 'in_progress', 'completed', 'skipped', 'cancelled']).optional(),
  }),
  params: z.object({
    id: z.string().uuid(),
  }),
});

export const taskIdSchema = z.object({
  params: z.object({
    id: z.string().uuid('Invalid task ID'),
  }),
});

export const listTasksSchema = z.object({
  query: z.object({
    goalId: z.string().uuid().optional(),
    status: z.enum(['pending', 'in_progress', 'completed', 'skipped', 'cancelled']).optional(),
    startDate: z.string().date().optional(),
    endDate: z.string().date().optional(),
    page: z.string().regex(/^\d+$/).transform(Number).default('1'),
    limit: z.string().regex(/^\d+$/).transform(Number).default('20'),
  }),
});
