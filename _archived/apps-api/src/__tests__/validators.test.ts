import { describe, it, expect } from 'vitest';
import {
  createUserSchema,
  loginSchema,
  updateUserSchema,
  createDreamSchema,
  updateDreamSchema,
  createGoalSchema,
  updateGoalSchema,
  createTaskSchema,
  updateTaskSchema,
  createConversationSchema,
  sendMessageSchema,
} from '../validators';

describe('Validators', () => {
  describe('createUserSchema', () => {
    it('should validate valid user data', () => {
      const result = createUserSchema.safeParse({
        idToken: 'firebase-token-123',
        email: 'test@example.com',
        displayName: 'Test User',
        timezone: 'Europe/Paris',
      });

      expect(result.success).toBe(true);
    });

    it('should require idToken', () => {
      const result = createUserSchema.safeParse({
        email: 'test@example.com',
      });

      expect(result.success).toBe(false);
    });

    it('should require valid email', () => {
      const result = createUserSchema.safeParse({
        idToken: 'token',
        email: 'not-an-email',
      });

      expect(result.success).toBe(false);
    });
  });

  describe('loginSchema', () => {
    it('should validate valid login data', () => {
      const result = loginSchema.safeParse({
        idToken: 'firebase-token-123',
        fcmToken: 'fcm-token',
        platform: 'android',
      });

      expect(result.success).toBe(true);
    });

    it('should require idToken', () => {
      const result = loginSchema.safeParse({});

      expect(result.success).toBe(false);
    });
  });

  describe('updateUserSchema', () => {
    it('should validate update with display name', () => {
      const result = updateUserSchema.safeParse({
        displayName: 'New Name',
      });

      expect(result.success).toBe(true);
    });

    it('should validate update with work schedule', () => {
      const result = updateUserSchema.safeParse({
        workSchedule: {
          workDays: [1, 2, 3, 4, 5],
          startTime: '09:00',
          endTime: '18:00',
        },
      });

      expect(result.success).toBe(true);
    });

    it('should validate empty update', () => {
      const result = updateUserSchema.safeParse({});

      expect(result.success).toBe(true);
    });
  });

  describe('createDreamSchema', () => {
    it('should validate valid dream data', () => {
      const result = createDreamSchema.safeParse({
        title: 'Learn Guitar',
        description: 'I want to master guitar playing',
        category: 'creativity',
        priority: 3,
      });

      expect(result.success).toBe(true);
    });

    it('should require title', () => {
      const result = createDreamSchema.safeParse({
        description: 'Some description',
      });

      expect(result.success).toBe(false);
    });

    it('should require description', () => {
      const result = createDreamSchema.safeParse({
        title: 'Test Dream',
      });

      expect(result.success).toBe(false);
    });

    it('should validate priority range', () => {
      const result = createDreamSchema.safeParse({
        title: 'Test',
        description: 'Test desc',
        priority: 6,
      });

      expect(result.success).toBe(false);
    });
  });

  describe('updateDreamSchema', () => {
    it('should validate valid update', () => {
      const result = updateDreamSchema.safeParse({
        title: 'Updated Title',
        status: 'completed',
      });

      expect(result.success).toBe(true);
    });

    it('should reject invalid status', () => {
      const result = updateDreamSchema.safeParse({
        status: 'invalid_status',
      });

      expect(result.success).toBe(false);
    });
  });

  describe('createGoalSchema', () => {
    it('should validate valid goal data', () => {
      const result = createGoalSchema.safeParse({
        dreamId: 'dream-1',
        title: 'Learn chords',
        description: 'Master basic guitar chords',
        estimatedMinutes: 120,
      });

      expect(result.success).toBe(true);
    });

    it('should require dreamId', () => {
      const result = createGoalSchema.safeParse({
        title: 'Learn chords',
      });

      expect(result.success).toBe(false);
    });

    it('should require title', () => {
      const result = createGoalSchema.safeParse({
        dreamId: 'dream-1',
      });

      expect(result.success).toBe(false);
    });
  });

  describe('updateGoalSchema', () => {
    it('should validate valid update', () => {
      const result = updateGoalSchema.safeParse({
        title: 'Updated Goal',
        status: 'completed',
      });

      expect(result.success).toBe(true);
    });

    it('should reject invalid status', () => {
      const result = updateGoalSchema.safeParse({
        status: 'not_valid',
      });

      expect(result.success).toBe(false);
    });
  });

  describe('createTaskSchema', () => {
    it('should validate valid task data', () => {
      const result = createTaskSchema.safeParse({
        goalId: 'goal-1',
        title: 'Practice C chord',
        scheduledDate: '2024-01-15',
        scheduledTime: '18:30',
        durationMins: 30,
      });

      expect(result.success).toBe(true);
    });

    it('should require goalId', () => {
      const result = createTaskSchema.safeParse({
        title: 'Practice',
      });

      expect(result.success).toBe(false);
    });

    it('should validate recurrence', () => {
      const result = createTaskSchema.safeParse({
        goalId: 'goal-1',
        title: 'Daily practice',
        recurrence: {
          type: 'daily',
          days: [1, 2, 3, 4, 5],
        },
      });

      expect(result.success).toBe(true);
    });
  });

  describe('updateTaskSchema', () => {
    it('should validate valid update', () => {
      const result = updateTaskSchema.safeParse({
        title: 'Updated Task',
        status: 'completed',
      });

      expect(result.success).toBe(true);
    });

    it('should reject invalid status', () => {
      const result = updateTaskSchema.safeParse({
        status: 'not_valid',
      });

      expect(result.success).toBe(false);
    });
  });

  describe('createConversationSchema', () => {
    it('should validate valid conversation data', () => {
      const result = createConversationSchema.safeParse({
        type: 'dream_creation',
        dreamId: 'dream-1',
      });

      expect(result.success).toBe(true);
    });

    it('should require type', () => {
      const result = createConversationSchema.safeParse({});

      expect(result.success).toBe(false);
    });

    it('should reject invalid type', () => {
      const result = createConversationSchema.safeParse({
        type: 'invalid_type',
      });

      expect(result.success).toBe(false);
    });
  });

  describe('sendMessageSchema', () => {
    it('should validate valid message', () => {
      const result = sendMessageSchema.safeParse({
        content: 'Hello, I want to learn guitar!',
      });

      expect(result.success).toBe(true);
    });

    it('should require content', () => {
      const result = sendMessageSchema.safeParse({});

      expect(result.success).toBe(false);
    });

    it('should reject empty content', () => {
      const result = sendMessageSchema.safeParse({
        content: '',
      });

      expect(result.success).toBe(false);
    });
  });
});
