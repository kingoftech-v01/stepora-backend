import { describe, it, expect, vi, beforeEach } from 'vitest';
import { taskService } from '../../services/task.service';
import { prisma } from '../../config/database';

const mockPrisma = vi.mocked(prisma);

describe('TaskService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockTask = {
    id: 'task-1',
    goalId: 'goal-1',
    title: 'Practice C chord',
    description: null,
    order: 1,
    scheduledDate: new Date('2024-01-15'),
    scheduledTime: '18:30',
    durationMins: 30,
    recurrence: null,
    status: 'pending',
    completedAt: null,
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  const mockTaskWithGoal = {
    ...mockTask,
    goal: {
      id: 'goal-1',
      title: 'Learn basic chords',
      dream: {
        id: 'dream-1',
        title: 'Learn Guitar',
        category: 'creativity',
      },
    },
  };

  describe('findById', () => {
    it('should return task with goal and dream', async () => {
      mockPrisma.task.findFirst.mockResolvedValue(mockTaskWithGoal as any);

      const result = await taskService.findById('task-1', 'user-1');

      expect(result).toEqual(mockTaskWithGoal);
      expect(mockPrisma.task.findFirst).toHaveBeenCalledWith(
        expect.objectContaining({
          where: {
            id: 'task-1',
            goal: { dream: { userId: 'user-1' } },
          },
        })
      );
    });

    it('should return null when not found', async () => {
      mockPrisma.task.findFirst.mockResolvedValue(null);

      const result = await taskService.findById('nonexistent', 'user-1');

      expect(result).toBeNull();
    });
  });

  describe('findByGoal', () => {
    it('should return tasks for a goal', async () => {
      mockPrisma.task.findMany.mockResolvedValue([mockTask] as any);

      const result = await taskService.findByGoal('goal-1', 'user-1');

      expect(result).toHaveLength(1);
      expect(mockPrisma.task.findMany).toHaveBeenCalledWith({
        where: {
          goalId: 'goal-1',
          goal: { dream: { userId: 'user-1' } },
        },
        orderBy: { order: 'asc' },
      });
    });
  });

  describe('findByDateRange', () => {
    it('should return tasks in date range', async () => {
      mockPrisma.task.findMany.mockResolvedValue([mockTaskWithGoal] as any);

      const start = new Date('2024-01-01');
      const end = new Date('2024-01-31');

      const result = await taskService.findByDateRange('user-1', start, end);

      expect(result).toHaveLength(1);
      expect(mockPrisma.task.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: {
            goal: { dream: { userId: 'user-1' } },
            scheduledDate: { gte: start, lte: end },
          },
        })
      );
    });
  });

  describe('findUpcoming', () => {
    it('should return upcoming tasks', async () => {
      mockPrisma.task.findMany.mockResolvedValue([mockTaskWithGoal] as any);

      const result = await taskService.findUpcoming('user-1', 5);

      expect(result).toHaveLength(1);
      expect(mockPrisma.task.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: expect.objectContaining({
            status: 'pending',
          }),
          take: 5,
        })
      );
    });

    it('should use default limit of 10', async () => {
      mockPrisma.task.findMany.mockResolvedValue([]);

      await taskService.findUpcoming('user-1');

      expect(mockPrisma.task.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          take: 10,
        })
      );
    });
  });

  describe('create', () => {
    it('should create a new task', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue({ id: 'goal-1' } as any);
      mockPrisma.task.aggregate.mockResolvedValue({ _max: { order: 3 } } as any);
      mockPrisma.task.create.mockResolvedValue(mockTask as any);

      const result = await taskService.create('goal-1', 'user-1', {
        title: 'Practice C chord',
        scheduledDate: new Date('2024-01-15'),
        scheduledTime: '18:30',
        durationMins: 30,
      });

      expect(result).toEqual(mockTask);
      expect(mockPrisma.task.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          goalId: 'goal-1',
          title: 'Practice C chord',
          order: 4,
        }),
      });
    });

    it('should set order to 1 when no existing tasks', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue({ id: 'goal-1' } as any);
      mockPrisma.task.aggregate.mockResolvedValue({ _max: { order: null } } as any);
      mockPrisma.task.create.mockResolvedValue(mockTask as any);

      await taskService.create('goal-1', 'user-1', { title: 'First task' });

      expect(mockPrisma.task.create).toHaveBeenCalledWith({
        data: expect.objectContaining({ order: 1 }),
      });
    });

    it('should throw when goal not found', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue(null);

      await expect(
        taskService.create('nonexistent', 'user-1', { title: 'Test' })
      ).rejects.toThrow('Goal not found');
    });
  });

  describe('update', () => {
    it('should update task', async () => {
      mockPrisma.task.findFirst.mockResolvedValue(mockTask as any);
      mockPrisma.task.update.mockResolvedValue({
        ...mockTask,
        title: 'Updated Task',
      } as any);

      const result = await taskService.update('task-1', 'user-1', {
        title: 'Updated Task',
      });

      expect(result.title).toBe('Updated Task');
    });

    it('should set completedAt when status is completed', async () => {
      mockPrisma.task.findFirst.mockResolvedValue(mockTask as any);
      mockPrisma.task.update.mockResolvedValue({
        ...mockTask,
        status: 'completed',
        completedAt: new Date(),
      } as any);

      await taskService.update('task-1', 'user-1', { status: 'completed' });

      expect(mockPrisma.task.update).toHaveBeenCalledWith({
        where: { id: 'task-1' },
        data: expect.objectContaining({
          status: 'completed',
          completedAt: expect.any(Date),
        }),
      });
    });

    it('should clear completedAt when status is not completed', async () => {
      mockPrisma.task.findFirst.mockResolvedValue({
        ...mockTask,
        status: 'completed',
      } as any);
      mockPrisma.task.update.mockResolvedValue(mockTask as any);

      await taskService.update('task-1', 'user-1', { status: 'pending' });

      expect(mockPrisma.task.update).toHaveBeenCalledWith({
        where: { id: 'task-1' },
        data: expect.objectContaining({
          status: 'pending',
          completedAt: null,
        }),
      });
    });

    it('should throw when task not found', async () => {
      mockPrisma.task.findFirst.mockResolvedValue(null);

      await expect(
        taskService.update('nonexistent', 'user-1', { title: 'Test' })
      ).rejects.toThrow('Task not found');
    });
  });

  describe('complete', () => {
    it('should complete a task', async () => {
      mockPrisma.task.findFirst.mockResolvedValue(mockTask as any);
      mockPrisma.task.update.mockResolvedValue({
        ...mockTask,
        status: 'completed',
        completedAt: new Date(),
      } as any);

      const result = await taskService.complete('task-1', 'user-1');

      expect(result.status).toBe('completed');
    });
  });

  describe('skip', () => {
    it('should skip a task', async () => {
      mockPrisma.task.findFirst.mockResolvedValue(mockTask as any);
      mockPrisma.task.update.mockResolvedValue({
        ...mockTask,
        status: 'skipped',
      } as any);

      const result = await taskService.skip('task-1', 'user-1');

      expect(result.status).toBe('skipped');
    });
  });

  describe('delete', () => {
    it('should delete task and reorder', async () => {
      mockPrisma.task.findFirst.mockResolvedValue(mockTask as any);
      mockPrisma.task.delete.mockResolvedValue(mockTask as any);
      mockPrisma.$executeRaw.mockResolvedValue(0);

      await taskService.delete('task-1', 'user-1');

      expect(mockPrisma.task.delete).toHaveBeenCalledWith({
        where: { id: 'task-1' },
      });
      expect(mockPrisma.$executeRaw).toHaveBeenCalled();
    });

    it('should throw when task not found', async () => {
      mockPrisma.task.findFirst.mockResolvedValue(null);

      await expect(
        taskService.delete('nonexistent', 'user-1')
      ).rejects.toThrow('Task not found');
    });
  });

  describe('reorder', () => {
    it('should reorder tasks', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue({ id: 'goal-1' } as any);
      mockPrisma.$transaction.mockResolvedValue([]);

      await taskService.reorder('goal-1', 'user-1', ['task-2', 'task-1']);

      expect(mockPrisma.$transaction).toHaveBeenCalled();
    });

    it('should throw when goal not found', async () => {
      mockPrisma.goal.findFirst.mockResolvedValue(null);

      await expect(
        taskService.reorder('nonexistent', 'user-1', ['task-1'])
      ).rejects.toThrow('Goal not found');
    });
  });

  describe('getTodayTasks', () => {
    it('should return tasks for today', async () => {
      mockPrisma.task.findMany.mockResolvedValue([mockTaskWithGoal] as any);

      const result = await taskService.getTodayTasks('user-1');

      expect(result).toHaveLength(1);
    });
  });

  describe('getOverdueTasks', () => {
    it('should return overdue tasks', async () => {
      mockPrisma.task.findMany.mockResolvedValue([mockTaskWithGoal] as any);

      const result = await taskService.getOverdueTasks('user-1');

      expect(result).toHaveLength(1);
      expect(mockPrisma.task.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: expect.objectContaining({
            status: 'pending',
          }),
        })
      );
    });
  });
});
