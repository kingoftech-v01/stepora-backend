import { z } from 'zod';

export const createDreamSchema = z.object({
  body: z.object({
    title: z.string().min(3, 'Title must be at least 3 characters').max(200),
    description: z.string().min(10, 'Description must be at least 10 characters').max(5000),
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
    targetDate: z.string().datetime().optional(),
    priority: z.number().int().min(1).max(5).default(1),
  }),
});

export const updateDreamSchema = z.object({
  body: z.object({
    title: z.string().min(3).max(200).optional(),
    description: z.string().min(10).max(5000).optional(),
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
    targetDate: z.string().datetime().optional().nullable(),
    priority: z.number().int().min(1).max(5).optional(),
    status: z.enum(['active', 'completed', 'paused', 'archived']).optional(),
  }),
});

export const generatePlanSchema = z.object({
  body: z.object({
    conversationId: z.string().uuid().optional(),
  }),
});

export const dreamIdSchema = z.object({
  params: z.object({
    id: z.string().uuid('Invalid dream ID'),
  }),
});
