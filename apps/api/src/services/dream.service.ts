import { prisma } from '../config/database';
import { Dream, Goal, Task, Prisma } from '@prisma/client';
import { aiService } from './ai.service';

export interface CreateDreamData {
  title: string;
  description: string;
  category?: string;
  targetDate?: Date;
  priority?: number;
}

export interface UpdateDreamData {
  title?: string;
  description?: string;
  category?: string;
  targetDate?: Date;
  priority?: number;
  status?: 'active' | 'completed' | 'paused' | 'archived';
}

export type DreamWithGoals = Dream & {
  goals: (Goal & { tasks: Task[] })[];
};

export class DreamService {
  async findById(id: string, userId: string): Promise<DreamWithGoals | null> {
    return prisma.dream.findFirst({
      where: { id, userId },
      include: {
        goals: {
          include: { tasks: true },
          orderBy: { order: 'asc' },
        },
      },
    });
  }

  async findAllByUser(
    userId: string,
    options?: {
      status?: string;
      category?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<{ dreams: DreamWithGoals[]; total: number }> {
    const where: Prisma.DreamWhereInput = { userId };

    if (options?.status) where.status = options.status;
    if (options?.category) where.category = options.category;

    const [dreams, total] = await Promise.all([
      prisma.dream.findMany({
        where,
        include: {
          goals: {
            include: { tasks: true },
            orderBy: { order: 'asc' },
          },
        },
        orderBy: [{ priority: 'desc' }, { createdAt: 'desc' }],
        take: options?.limit || 50,
        skip: options?.offset || 0,
      }),
      prisma.dream.count({ where }),
    ]);

    return { dreams, total };
  }

  async create(userId: string, data: CreateDreamData): Promise<Dream> {
    return prisma.dream.create({
      data: {
        userId,
        title: data.title,
        description: data.description,
        category: data.category,
        targetDate: data.targetDate,
        priority: data.priority || 1,
      },
    });
  }

  async update(id: string, userId: string, data: UpdateDreamData): Promise<Dream> {
    const dream = await prisma.dream.findFirst({
      where: { id, userId },
    });

    if (!dream) {
      throw new Error('Dream not found');
    }

    const updateData: Prisma.DreamUpdateInput = {};

    if (data.title !== undefined) updateData.title = data.title;
    if (data.description !== undefined) updateData.description = data.description;
    if (data.category !== undefined) updateData.category = data.category;
    if (data.targetDate !== undefined) updateData.targetDate = data.targetDate;
    if (data.priority !== undefined) updateData.priority = data.priority;
    if (data.status !== undefined) {
      updateData.status = data.status;
      if (data.status === 'completed') {
        updateData.completedAt = new Date();
      }
    }

    return prisma.dream.update({
      where: { id },
      data: updateData,
    });
  }

  async delete(id: string, userId: string): Promise<void> {
    const dream = await prisma.dream.findFirst({
      where: { id, userId },
    });

    if (!dream) {
      throw new Error('Dream not found');
    }

    await prisma.dream.delete({
      where: { id },
    });
  }

  async generatePlan(
    dreamId: string,
    userId: string,
    userContext: {
      userName: string;
      timezone: string;
      workSchedule?: {
        workDays: number[];
        startTime: string;
        endTime: string;
      };
      availableHoursPerWeek?: number;
    }
  ): Promise<DreamWithGoals> {
    const dream = await prisma.dream.findFirst({
      where: { id: dreamId, userId },
    });

    if (!dream) {
      throw new Error('Dream not found');
    }

    // Generate plan using AI
    const plan = await aiService.generatePlan(
      {
        title: dream.title,
        description: dream.description,
        targetDate: dream.targetDate,
        category: dream.category,
      },
      userContext
    );

    // Update dream with AI analysis
    await prisma.dream.update({
      where: { id: dreamId },
      data: {
        aiAnalysis: {
          feasibility: plan.feasibility,
          estimatedDuration: plan.estimatedDuration,
          weeklyTimeRequired: plan.weeklyTimeRequired,
          tips: plan.tips,
          potentialObstacles: plan.potentialObstacles,
        },
      },
    });

    // Create goals and tasks
    const startDate = new Date();
    let currentDate = new Date(startDate);

    for (let i = 0; i < plan.goals.length; i++) {
      const goalData = plan.goals[i];
      const goalEndDate = new Date(currentDate);
      goalEndDate.setDate(goalEndDate.getDate() + goalData.durationWeeks * 7);

      const goal = await prisma.goal.create({
        data: {
          dreamId,
          title: goalData.title,
          description: goalData.description,
          order: i + 1,
          scheduledStart: currentDate,
          scheduledEnd: goalEndDate,
          estimatedMinutes: goalData.tasks.reduce((sum, t) => sum + t.durationMins, 0),
        },
      });

      // Create tasks for this goal
      let taskOrder = 1;
      for (const taskData of goalData.tasks) {
        if (taskData.frequency === 'daily' || taskData.frequency === 'weekly') {
          // Create recurring tasks
          const endDate = new Date(goalEndDate);
          let taskDate = new Date(currentDate);

          while (taskDate <= endDate) {
            const dayOfWeek = taskDate.getDay();
            const shouldCreate =
              taskData.frequency === 'daily'
                ? (taskData.days?.includes(dayOfWeek) ?? true)
                : taskData.days?.includes(dayOfWeek) ?? false;

            if (shouldCreate) {
              await prisma.task.create({
                data: {
                  goalId: goal.id,
                  title: taskData.title,
                  order: taskOrder++,
                  scheduledDate: new Date(taskDate),
                  durationMins: taskData.durationMins,
                  recurrence: {
                    type: taskData.frequency,
                    days: taskData.days,
                  },
                },
              });
            }

            taskDate.setDate(taskDate.getDate() + 1);
          }
        } else {
          // Single task
          await prisma.task.create({
            data: {
              goalId: goal.id,
              title: taskData.title,
              order: taskOrder++,
              scheduledDate: currentDate,
              durationMins: taskData.durationMins,
            },
          });
        }
      }

      currentDate = new Date(goalEndDate);
    }

    // Return updated dream with goals
    return this.findById(dreamId, userId) as Promise<DreamWithGoals>;
  }

  async getProgress(dreamId: string, userId: string): Promise<{
    totalGoals: number;
    completedGoals: number;
    totalTasks: number;
    completedTasks: number;
    progressPercent: number;
  }> {
    const dream = await prisma.dream.findFirst({
      where: { id: dreamId, userId },
      include: {
        goals: {
          include: { tasks: true },
        },
      },
    });

    if (!dream) {
      throw new Error('Dream not found');
    }

    const totalGoals = dream.goals.length;
    const completedGoals = dream.goals.filter((g) => g.status === 'completed').length;
    const totalTasks = dream.goals.reduce((sum, g) => sum + g.tasks.length, 0);
    const completedTasks = dream.goals.reduce(
      (sum, g) => sum + g.tasks.filter((t) => t.status === 'completed').length,
      0
    );

    const progressPercent = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

    return {
      totalGoals,
      completedGoals,
      totalTasks,
      completedTasks,
      progressPercent,
    };
  }
}

export const dreamService = new DreamService();
