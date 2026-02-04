import { prisma } from '../config/database';
import { Goal, Task, Prisma } from '@prisma/client';

export interface CreateGoalData {
  title: string;
  description?: string;
  estimatedMinutes?: number;
  scheduledStart?: Date;
  scheduledEnd?: Date;
  reminderEnabled?: boolean;
  reminderTime?: Date;
}

export interface UpdateGoalData {
  title?: string;
  description?: string;
  estimatedMinutes?: number;
  scheduledStart?: Date;
  scheduledEnd?: Date;
  status?: 'pending' | 'in_progress' | 'completed' | 'skipped';
  reminderEnabled?: boolean;
  reminderTime?: Date;
}

export type GoalWithTasks = Goal & { tasks: Task[] };

export class GoalService {
  async findById(id: string, userId: string): Promise<GoalWithTasks | null> {
    return prisma.goal.findFirst({
      where: {
        id,
        dream: { userId },
      },
      include: {
        tasks: {
          orderBy: { order: 'asc' },
        },
      },
    });
  }

  async findByDream(dreamId: string, userId: string): Promise<GoalWithTasks[]> {
    return prisma.goal.findMany({
      where: {
        dreamId,
        dream: { userId },
      },
      include: {
        tasks: {
          orderBy: { order: 'asc' },
        },
      },
      orderBy: { order: 'asc' },
    });
  }

  async create(dreamId: string, userId: string, data: CreateGoalData): Promise<Goal> {
    // Verify dream belongs to user
    const dream = await prisma.dream.findFirst({
      where: { id: dreamId, userId },
    });

    if (!dream) {
      throw new Error('Dream not found');
    }

    // Get max order
    const maxOrder = await prisma.goal.aggregate({
      where: { dreamId },
      _max: { order: true },
    });

    return prisma.goal.create({
      data: {
        dreamId,
        title: data.title,
        description: data.description,
        order: (maxOrder._max.order || 0) + 1,
        estimatedMinutes: data.estimatedMinutes,
        scheduledStart: data.scheduledStart,
        scheduledEnd: data.scheduledEnd,
        reminderEnabled: data.reminderEnabled ?? true,
        reminderTime: data.reminderTime,
      },
    });
  }

  async update(id: string, userId: string, data: UpdateGoalData): Promise<Goal> {
    const goal = await prisma.goal.findFirst({
      where: {
        id,
        dream: { userId },
      },
    });

    if (!goal) {
      throw new Error('Goal not found');
    }

    const updateData: Prisma.GoalUpdateInput = {};

    if (data.title !== undefined) updateData.title = data.title;
    if (data.description !== undefined) updateData.description = data.description;
    if (data.estimatedMinutes !== undefined) updateData.estimatedMinutes = data.estimatedMinutes;
    if (data.scheduledStart !== undefined) updateData.scheduledStart = data.scheduledStart;
    if (data.scheduledEnd !== undefined) updateData.scheduledEnd = data.scheduledEnd;
    if (data.reminderEnabled !== undefined) updateData.reminderEnabled = data.reminderEnabled;
    if (data.reminderTime !== undefined) updateData.reminderTime = data.reminderTime;
    if (data.status !== undefined) {
      updateData.status = data.status;
      if (data.status === 'completed') {
        updateData.completedAt = new Date();
      }
    }

    return prisma.goal.update({
      where: { id },
      data: updateData,
    });
  }

  async delete(id: string, userId: string): Promise<void> {
    const goal = await prisma.goal.findFirst({
      where: {
        id,
        dream: { userId },
      },
    });

    if (!goal) {
      throw new Error('Goal not found');
    }

    await prisma.goal.delete({
      where: { id },
    });

    // Reorder remaining goals
    await prisma.$executeRaw`
      UPDATE goals
      SET "order" = "order" - 1
      WHERE dream_id = ${goal.dreamId} AND "order" > ${goal.order}
    `;
  }

  async reorder(dreamId: string, userId: string, goalIds: string[]): Promise<void> {
    // Verify dream belongs to user
    const dream = await prisma.dream.findFirst({
      where: { id: dreamId, userId },
    });

    if (!dream) {
      throw new Error('Dream not found');
    }

    // Update order for each goal
    await prisma.$transaction(
      goalIds.map((goalId, index) =>
        prisma.goal.update({
          where: { id: goalId },
          data: { order: index + 1 },
        })
      )
    );
  }

  async getProgress(id: string, userId: string): Promise<{
    totalTasks: number;
    completedTasks: number;
    progressPercent: number;
  }> {
    const goal = await prisma.goal.findFirst({
      where: {
        id,
        dream: { userId },
      },
      include: { tasks: true },
    });

    if (!goal) {
      throw new Error('Goal not found');
    }

    const totalTasks = goal.tasks.length;
    const completedTasks = goal.tasks.filter((t) => t.status === 'completed').length;
    const progressPercent = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

    return { totalTasks, completedTasks, progressPercent };
  }
}

export const goalService = new GoalService();
