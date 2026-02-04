import { prisma } from '../config/database';
import { Task, Prisma } from '@prisma/client';

export interface CreateTaskData {
  title: string;
  description?: string;
  scheduledDate?: Date;
  scheduledTime?: string;
  durationMins?: number;
  recurrence?: {
    type: 'daily' | 'weekly';
    days?: number[];
    until?: string;
  };
}

export interface UpdateTaskData {
  title?: string;
  description?: string;
  scheduledDate?: Date;
  scheduledTime?: string;
  durationMins?: number;
  status?: 'pending' | 'completed' | 'skipped';
  recurrence?: {
    type: 'daily' | 'weekly';
    days?: number[];
    until?: string;
  } | null;
}

export interface TaskWithGoalAndDream extends Task {
  goal: {
    id: string;
    title: string;
    dream: {
      id: string;
      title: string;
      category: string | null;
    };
  };
}

export class TaskService {
  async findById(id: string, userId: string): Promise<TaskWithGoalAndDream | null> {
    return prisma.task.findFirst({
      where: {
        id,
        goal: {
          dream: { userId },
        },
      },
      include: {
        goal: {
          select: {
            id: true,
            title: true,
            dream: {
              select: {
                id: true,
                title: true,
                category: true,
              },
            },
          },
        },
      },
    });
  }

  async findByGoal(goalId: string, userId: string): Promise<Task[]> {
    return prisma.task.findMany({
      where: {
        goalId,
        goal: {
          dream: { userId },
        },
      },
      orderBy: { order: 'asc' },
    });
  }

  async findByDateRange(
    userId: string,
    startDate: Date,
    endDate: Date
  ): Promise<TaskWithGoalAndDream[]> {
    return prisma.task.findMany({
      where: {
        goal: {
          dream: { userId },
        },
        scheduledDate: {
          gte: startDate,
          lte: endDate,
        },
      },
      include: {
        goal: {
          select: {
            id: true,
            title: true,
            dream: {
              select: {
                id: true,
                title: true,
                category: true,
              },
            },
          },
        },
      },
      orderBy: [{ scheduledDate: 'asc' }, { scheduledTime: 'asc' }],
    });
  }

  async findUpcoming(userId: string, limit: number = 10): Promise<TaskWithGoalAndDream[]> {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    return prisma.task.findMany({
      where: {
        goal: {
          dream: { userId },
        },
        scheduledDate: { gte: today },
        status: 'pending',
      },
      include: {
        goal: {
          select: {
            id: true,
            title: true,
            dream: {
              select: {
                id: true,
                title: true,
                category: true,
              },
            },
          },
        },
      },
      orderBy: [{ scheduledDate: 'asc' }, { scheduledTime: 'asc' }],
      take: limit,
    });
  }

  async create(goalId: string, userId: string, data: CreateTaskData): Promise<Task> {
    // Verify goal belongs to user
    const goal = await prisma.goal.findFirst({
      where: {
        id: goalId,
        dream: { userId },
      },
    });

    if (!goal) {
      throw new Error('Goal not found');
    }

    // Get max order
    const maxOrder = await prisma.task.aggregate({
      where: { goalId },
      _max: { order: true },
    });

    return prisma.task.create({
      data: {
        goalId,
        title: data.title,
        description: data.description,
        order: (maxOrder._max.order || 0) + 1,
        scheduledDate: data.scheduledDate,
        scheduledTime: data.scheduledTime,
        durationMins: data.durationMins,
        recurrence: data.recurrence as Prisma.InputJsonValue,
      },
    });
  }

  async update(id: string, userId: string, data: UpdateTaskData): Promise<Task> {
    const task = await prisma.task.findFirst({
      where: {
        id,
        goal: {
          dream: { userId },
        },
      },
    });

    if (!task) {
      throw new Error('Task not found');
    }

    const updateData: Prisma.TaskUpdateInput = {};

    if (data.title !== undefined) updateData.title = data.title;
    if (data.description !== undefined) updateData.description = data.description;
    if (data.scheduledDate !== undefined) updateData.scheduledDate = data.scheduledDate;
    if (data.scheduledTime !== undefined) updateData.scheduledTime = data.scheduledTime;
    if (data.durationMins !== undefined) updateData.durationMins = data.durationMins;
    if (data.recurrence !== undefined) updateData.recurrence = data.recurrence as Prisma.InputJsonValue;
    if (data.status !== undefined) {
      updateData.status = data.status;
      if (data.status === 'completed') {
        updateData.completedAt = new Date();
      } else {
        updateData.completedAt = null;
      }
    }

    return prisma.task.update({
      where: { id },
      data: updateData,
    });
  }

  async complete(id: string, userId: string): Promise<Task> {
    return this.update(id, userId, { status: 'completed' });
  }

  async skip(id: string, userId: string): Promise<Task> {
    return this.update(id, userId, { status: 'skipped' });
  }

  async delete(id: string, userId: string): Promise<void> {
    const task = await prisma.task.findFirst({
      where: {
        id,
        goal: {
          dream: { userId },
        },
      },
    });

    if (!task) {
      throw new Error('Task not found');
    }

    await prisma.task.delete({
      where: { id },
    });

    // Reorder remaining tasks
    await prisma.$executeRaw`
      UPDATE tasks
      SET "order" = "order" - 1
      WHERE goal_id = ${task.goalId} AND "order" > ${task.order}
    `;
  }

  async reorder(goalId: string, userId: string, taskIds: string[]): Promise<void> {
    // Verify goal belongs to user
    const goal = await prisma.goal.findFirst({
      where: {
        id: goalId,
        dream: { userId },
      },
    });

    if (!goal) {
      throw new Error('Goal not found');
    }

    // Update order for each task
    await prisma.$transaction(
      taskIds.map((taskId, index) =>
        prisma.task.update({
          where: { id: taskId },
          data: { order: index + 1 },
        })
      )
    );
  }

  async getTodayTasks(userId: string): Promise<TaskWithGoalAndDream[]> {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    return this.findByDateRange(userId, today, tomorrow);
  }

  async getOverdueTasks(userId: string): Promise<TaskWithGoalAndDream[]> {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    return prisma.task.findMany({
      where: {
        goal: {
          dream: { userId },
        },
        scheduledDate: { lt: today },
        status: 'pending',
      },
      include: {
        goal: {
          select: {
            id: true,
            title: true,
            dream: {
              select: {
                id: true,
                title: true,
                category: true,
              },
            },
          },
        },
      },
      orderBy: { scheduledDate: 'asc' },
    });
  }
}

export const taskService = new TaskService();
