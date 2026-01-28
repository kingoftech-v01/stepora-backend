import { z } from 'zod';

export const sendMessageSchema = z.object({
  body: z.object({
    content: z.string().min(1, 'Message cannot be empty').max(5000),
  }),
  params: z.object({
    id: z.string().uuid('Invalid conversation ID'),
  }),
});

export const createConversationSchema = z.object({
  body: z.object({
    dreamId: z.string().uuid().optional(),
    type: z.enum(['dream_creation', 'general', 'goal_refinement']).default('general'),
  }),
});
