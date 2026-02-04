import { describe, it, expect, vi, beforeEach } from 'vitest';
import { goalService } from '../../services/goal.service';
import { prisma } from '../../config/database';

const mockPrisma = vi.mocked(prisma);

describe('GoalService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockGoal = {
    id: 'goal-1',
    dreamId: 'dream-1',
    title: 'Learn basic chords',
    description: 'Master 5 basic chords',
    order: 1,
    estimatedMinutes: 120,
    scheduledStart: new Date('2024-01-01'),
    scheduledEnd: new Date('2024-01-14'),
    status: 'pending',
    completedAt: null,
    reminderEnabled: true,
    reminderTime: null,
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  const mockGoalWithTasks = {
    ...mockGoal,
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
  };

  describe('findById', () => {
    it('should return goal with tasks when found', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue(mockGoalWithTasks as any);

      const result = await goalService.findById('goal-1', 'user-1');

      expect(result).toEqual(mockGoalWithTasks);
      expect(mockPrisma.goal.findFirst).toHaveBeenCalledWith({
        where: {
          id: 'goal-1',
          dream: { userId: 'user-1' },
        },
        include: {
          tasks: { orderBy: { order: 'asc' } },
        },
      });
    });

    it('should return null when goal not found', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue(null);

      const result = await goalService.findById('nonexistent', 'user-1');

      expect(result).toBeNull();
    });
  });

  describe('findByDream', () => {
    it('should return goals for a dream', async () => {
      mockPrisma.goal.findMany.mockResolvedValue([mockGoalWithTasks] as any);

      const result = await goalService.findByDream('dream-1', 'user-1');

      expect(result).toHaveLength(1);
      expect(mockPrisma.goal.findMany).toHaveBeenCalledWith({
        where: {
          dreamId: 'dream-1',
          dream: { userId: 'user-1' },
        },
        include: {
          tasks: { orderBy: { order: 'asc' } },
        },
        orderBy: { order: 'asc' },
      });
    });
  });

  describe('create', () => {
    it('should create a new goal', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue({ id: 'dream-1', userId: 'user-1' } as any);
      mockPrisma.goal.aggregate.mockResolvedValue({ _max: { order: 2 } } as any);
      mockPrisma.goal.create.mockResolvedValue(mockGoal as any);

      const result = await goalService.create('dream-1', 'user-1', {
        title: 'Learn basic chords',
        description: 'Master 5 basic chords',
        estimatedMinutes: 120,
      });

      expect(result).toEqual(mockGoal);
      expect(mockPrisma.goal.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          dreamId: 'dream-1',
          title: 'Learn basic chords',
          order: 3,
        }),
      });
    });

    it('should set order to 1 when no existing goals', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue({ id: 'dream-1', userId: 'user-1' } as any);
      mockPrisma.goal.aggregate.mockResolvedValue({ _max: { order: null } } as any);
      mockPrisma.goal.create.mockResolvedValue(mockGoal as any);

      await goalService.create('dream-1', 'user-1', {
        title: 'First goal',
      });

      expect(mockPrisma.goal.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          order: 1,
        }),
      });
    });

    it('should throw when dream not found', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue(null);

      await expect(
        goalService.create('nonexistent', 'user-1', { title: 'Test' })
      ).rejects.toThrow('Dream not found');
    });
  });

  describe('update', () => {
    it('should update goal', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue(mockGoal as any);
      mockPrisma.goal.update.mockResolvedValue({
        ...mockGoal,
        title: 'Updated Goal',
      } as any);

      const result = await goalService.update('goal-1', 'user-1', {
        title: 'Updated Goal',
      });

      expect(result.title).toBe('Updated Goal');
    });

    it('should set completedAt when status is completed', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue(mockGoal as any);
      mockPrisma.goal.update.mockResolvedValue({
        ...mockGoal,
        status: 'completed',
        completedAt: new Date(),
      } as any);

      await goalService.update('goal-1', 'user-1', {
        status: 'completed',
      });

      expect(mockPrisma.goal.update).toHaveBeenCalledWith({
        where: { id: 'goal-1' },
        data: expect.objectContaining({
          status: 'completed',
          completedAt: expect.any(Date),
        }),
      });
    });

    it('should throw when goal not found', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue(null);

      await expect(
        goalService.update('nonexistent', 'user-1', { title: 'Test' })
      ).rejects.toThrow('Goal not found');
    });
  });

  describe('delete', () => {
    it('should delete goal and reorder', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue(mockGoal as any);
      mockPrisma.goal.delete.mockResolvedValue(mockGoal as any);
      mockPrisma.$executeRaw.mockResolvedValue(0);

      await goalService.delete('goal-1', 'user-1');

      expect(mockPrisma.goal.delete).toHaveBeenCalledWith({
        where: { id: 'goal-1' },
      });
      expect(mockPrisma.$executeRaw).toHaveBeenCalled();
    });

    it('should throw when goal not found', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue(null);

      await expect(
        goalService.delete('nonexistent', 'user-1')
      ).rejects.toThrow('Goal not found');
    });
  });

  describe('reorder', () => {
    it('should reorder goals', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue({ id: 'dream-1', userId: 'user-1' } as any);
      mockPrisma.$transaction.mockResolvedValue([]);

      await goalService.reorder('dream-1', 'user-1', ['goal-2', 'goal-1', 'goal-3']);

      expect(mockPrisma.$transaction).toHaveBeenCalled();
    });

    it('should throw when dream not found', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue(null);

      await expect(
        goalService.reorder('nonexistent', 'user-1', ['goal-1'])
      ).rejects.toThrow('Dream not found');
    });
  });

  describe('getProgress', () => {
    it('should calculate progress correctly', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue(mockGoalWithTasks as any);

      const progress = await goalService.getProgress('goal-1', 'user-1');

      expect(progress).toEqual({
        totalTasks: 2,
        completedTasks: 1,
        progressPercent: 50,
      });
    });

    it('should return 0% for goal with no tasks', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue({
        ...mockGoal,
        tasks: [],
      } as any);

      const progress = await goalService.getProgress('goal-1', 'user-1');

      expect(progress.progressPercent).toBe(0);
    });

    it('should throw when goal not found', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue(null);

      await expect(
        goalService.getProgress('nonexistent', 'user-1')
      ).rejects.toThrow('Goal not found');
    });
  });
});
