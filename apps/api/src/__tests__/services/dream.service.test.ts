import { describe, it, expect, vi, beforeEach } from 'vitest';
import { dreamService } from '../../services/dream.service';
import { prisma } from '../../config/database';
import { aiService } from '../../services/ai.service';

vi.mock('../../services/ai.service', () => ({
  aiService: {
    generatePlan: vi.fn(),
    chat: vi.fn(),
    chatStream: vi.fn(),
    analyzeDream: vi.fn(),
    generateMotivationalMessage: vi.fn(),
  },
}));

const mockPrisma = vi.mocked(prisma);
const mockAiService = vi.mocked(aiService);

describe('DreamService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockDream = {
    id: 'dream-1',
    userId: 'user-1',
    title: 'Learn Guitar',
    description: 'I want to learn to play guitar well',
    category: 'creativity',
    targetDate: new Date('2025-06-01'),
    priority: 3,
    status: 'active',
    completedAt: null,
    aiAnalysis: null,
    createdAt: new Date('2024-01-01'),
    updatedAt: new Date('2024-01-01'),
  };

  const mockDreamWithGoals = {
    ...mockDream,
    goals: [
      {
        id: 'goal-1',
        dreamId: 'dream-1',
        title: 'Learn basic chords',
        description: 'Master 5 basic chords',
        order: 1,
        estimatedMinutes: 120,
        scheduledStart: new Date('2024-01-01'),
        scheduledEnd: new Date('2024-01-14'),
        status: 'in_progress',
        completedAt: null,
        reminderEnabled: true,
        reminderTime: null,
        createdAt: new Date(),
        updatedAt: new Date(),
        tasks: [
          {
            id: 'task-1',
            goalId: 'goal-1',
            title: 'Practice C chord',
            description: null,
            order: 1,
            scheduledDate: new Date('2024-01-01'),
            scheduledTime: '18:30',
            durationMins: 30,
            recurrence: null,
            status: 'completed',
            completedAt: new Date(),
            createdAt: new Date(),
            updatedAt: new Date(),
          },
          {
            id: 'task-2',
            goalId: 'goal-1',
            title: 'Practice G chord',
            description: null,
            order: 2,
            scheduledDate: new Date('2024-01-02'),
            scheduledTime: '18:30',
            durationMins: 30,
            recurrence: null,
            status: 'pending',
            completedAt: null,
            createdAt: new Date(),
            updatedAt: new Date(),
          },
        ],
      },
    ],
  };

  describe('findById', () => {
    it('should return dream with goals when found', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue(mockDreamWithGoals as any);

      const result = await dreamService.findById('dream-1', 'user-1');

      expect(result).toEqual(mockDreamWithGoals);
      expect(mockPrisma.dream.findFirst).toHaveBeenCalledWith({
        where: { id: 'dream-1', userId: 'user-1' },
        include: {
          goals: {
            include: { tasks: true },
            orderBy: { order: 'asc' },
          },
        },
      });
    });

    it('should return null when dream not found', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue(null);

      const result = await dreamService.findById('nonexistent', 'user-1');

      expect(result).toBeNull();
    });
  });

  describe('findAllByUser', () => {
    it('should return all dreams for user', async () => {
      mockPrisma.dream.findMany.mockResolvedValue([mockDreamWithGoals] as any);
      mockPrisma.dream.count.mockResolvedValue(1);

      const result = await dreamService.findAllByUser('user-1');

      expect(result.dreams).toHaveLength(1);
      expect(result.total).toBe(1);
    });

    it('should filter by status', async () => {
      mockPrisma.dream.findMany.mockResolvedValue([]);
      mockPrisma.dream.count.mockResolvedValue(0);

      await dreamService.findAllByUser('user-1', { status: 'completed' });

      expect(mockPrisma.dream.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: { userId: 'user-1', status: 'completed' },
        })
      );
    });

    it('should filter by category', async () => {
      mockPrisma.dream.findMany.mockResolvedValue([]);
      mockPrisma.dream.count.mockResolvedValue(0);

      await dreamService.findAllByUser('user-1', { category: 'health' });

      expect(mockPrisma.dream.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: { userId: 'user-1', category: 'health' },
        })
      );
    });

    it('should apply pagination', async () => {
      mockPrisma.dream.findMany.mockResolvedValue([]);
      mockPrisma.dream.count.mockResolvedValue(0);

      await dreamService.findAllByUser('user-1', { limit: 10, offset: 5 });

      expect(mockPrisma.dream.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          take: 10,
          skip: 5,
        })
      );
    });
  });

  describe('create', () => {
    it('should create a new dream', async () => {
      mockPrisma.dream.create.mockResolvedValue(mockDream as any);

      const result = await dreamService.create('user-1', {
        title: 'Learn Guitar',
        description: 'I want to learn to play guitar well',
        category: 'creativity',
        targetDate: new Date('2025-06-01'),
        priority: 3,
      });

      expect(result).toEqual(mockDream);
      expect(mockPrisma.dream.create).toHaveBeenCalledWith({
        data: {
          userId: 'user-1',
          title: 'Learn Guitar',
          description: 'I want to learn to play guitar well',
          category: 'creativity',
          targetDate: new Date('2025-06-01'),
          priority: 3,
        },
      });
    });

    it('should use default priority when not provided', async () => {
      mockPrisma.dream.create.mockResolvedValue(mockDream as any);

      await dreamService.create('user-1', {
        title: 'Test',
        description: 'Test desc',
      });

      expect(mockPrisma.dream.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          priority: 1,
        }),
      });
    });
  });

  describe('update', () => {
    it('should update dream', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue(mockDream as any);
      mockPrisma.dream.update.mockResolvedValue({
        ...mockDream,
        title: 'Updated Title',
      } as any);

      const result = await dreamService.update('dream-1', 'user-1', {
        title: 'Updated Title',
      });

      expect(result.title).toBe('Updated Title');
    });

    it('should set completedAt when status is completed', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue(mockDream as any);
      mockPrisma.dream.update.mockResolvedValue({
        ...mockDream,
        status: 'completed',
        completedAt: new Date(),
      } as any);

      await dreamService.update('dream-1', 'user-1', {
        status: 'completed',
      });

      expect(mockPrisma.dream.update).toHaveBeenCalledWith({
        where: { id: 'dream-1' },
        data: expect.objectContaining({
          status: 'completed',
          completedAt: expect.any(Date),
        }),
      });
    });

    it('should throw when dream not found', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue(null);

      await expect(
        dreamService.update('nonexistent', 'user-1', { title: 'Test' })
      ).rejects.toThrow('Dream not found');
    });
  });

  describe('delete', () => {
    it('should delete dream', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue(mockDream as any);
      mockPrisma.dream.delete.mockResolvedValue(mockDream as any);

      await dreamService.delete('dream-1', 'user-1');

      expect(mockPrisma.dream.delete).toHaveBeenCalledWith({
        where: { id: 'dream-1' },
      });
    });

    it('should throw when dream not found', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue(null);

      await expect(
        dreamService.delete('nonexistent', 'user-1')
      ).rejects.toThrow('Dream not found');
    });
  });

  describe('getProgress', () => {
    it('should calculate progress correctly', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue(mockDreamWithGoals as any);

      const progress = await dreamService.getProgress('dream-1', 'user-1');

      expect(progress).toEqual({
        totalGoals: 1,
        completedGoals: 0,
        totalTasks: 2,
        completedTasks: 1,
        progressPercent: 50,
      });
    });

    it('should return 0% for dream with no tasks', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue({
        ...mockDream,
        goals: [],
      } as any);

      const progress = await dreamService.getProgress('dream-1', 'user-1');

      expect(progress.progressPercent).toBe(0);
    });

    it('should throw when dream not found', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue(null);

      await expect(
        dreamService.getProgress('nonexistent', 'user-1')
      ).rejects.toThrow('Dream not found');
    });
  });

  describe('generatePlan', () => {
    it('should generate plan using AI and create goals/tasks', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue(mockDream as any);
      mockPrisma.dream.update.mockResolvedValue(mockDream as any);

      mockAiService.generatePlan.mockResolvedValue({
        analysis: 'Great objective',
        feasibility: 'high',
        estimatedDuration: '6 months',
        weeklyTimeRequired: '3h',
        goals: [
          {
            title: 'Learn basics',
            description: 'Learn basic chords',
            durationWeeks: 2,
            tasks: [
              {
                title: 'Practice C chord',
                durationMins: 30,
                frequency: 'once',
              },
            ],
          },
        ],
        tips: ['Start slow'],
        potentialObstacles: ['Finger pain'],
      });

      mockPrisma.goal.create.mockResolvedValue({
        id: 'goal-new',
        dreamId: 'dream-1',
        title: 'Learn basics',
        description: 'Learn basic chords',
        order: 1,
        estimatedMinutes: 30,
        scheduledStart: new Date(),
        scheduledEnd: new Date(),
        status: 'pending',
        completedAt: null,
        reminderEnabled: true,
        reminderTime: null,
        createdAt: new Date(),
        updatedAt: new Date(),
      } as any);

      mockPrisma.task.create.mockResolvedValue({
        id: 'task-new',
        goalId: 'goal-new',
        title: 'Practice C chord',
        order: 1,
        durationMins: 30,
      } as any);

      // Mock the final findById call
      mockPrisma.dream.findFirst.mockResolvedValue(mockDreamWithGoals as any);

      const result = await dreamService.generatePlan('dream-1', 'user-1', {
        userName: 'Test',
        timezone: 'Europe/Paris',
      });

      expect(mockAiService.generatePlan).toHaveBeenCalled();
      expect(mockPrisma.goal.create).toHaveBeenCalled();
      expect(mockPrisma.task.create).toHaveBeenCalled();
      expect(result).toBeDefined();
    });

    it('should throw when dream not found', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue(null);

      await expect(
        dreamService.generatePlan('nonexistent', 'user-1', {
          userName: 'Test',
          timezone: 'Europe/Paris',
        })
      ).rejects.toThrow('Dream not found');
    });
  });
});
