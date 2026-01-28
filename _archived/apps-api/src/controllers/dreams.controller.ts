import { Response, NextFunction } from 'express';
import { AuthRequest } from '../middleware/auth';
import { prisma } from '../utils/prisma';
import { success } from '../utils/response';
import { asyncHandler } from '../middleware/errorHandler';
import { NotFoundError, AuthorizationError } from '../utils/errors';
import { aiService } from '../services/ai.service';
import { logger } from '../config/logger';

class DreamsController {
  list = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { status, category } = req.query;

    const dreams = await prisma.dream.findMany({
      where: {
        userId: req.user!.id,
        ...(status && { status: status as string }),
        ...(category && { category: category as string }),
      },
      include: {
        _count: {
          select: { goals: true },
        },
      },
      orderBy: [{ priority: 'desc' }, { createdAt: 'desc' }],
    });

    // Calculate completion percentage for each dream
    const dreamsWithProgress = await Promise.all(
      dreams.map(async (dream) => {
        const goalsCount = await prisma.goal.count({
          where: { dreamId: dream.id },
        });
        const completedGoals = await prisma.goal.count({
          where: { dreamId: dream.id, status: 'completed' },
        });

        return {
          ...dream,
          completionPercentage: goalsCount > 0 ? Math.round((completedGoals / goalsCount) * 100) : 0,
        };
      })
    );

    return success(res, { dreams: dreamsWithProgress });
  });

  create = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { title, description, category, targetDate, priority } = req.body;

    const dream = await prisma.dream.create({
      data: {
        userId: req.user!.id,
        title,
        description,
        category,
        targetDate: targetDate ? new Date(targetDate) : null,
        priority: priority || 1,
      },
    });

    logger.info('Dream created:', { userId: req.user!.id, dreamId: dream.id });

    return success(res, { dream }, 'Dream created successfully', 201);
  });

  get = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { id } = req.params;

    const dream = await prisma.dream.findUnique({
      where: { id },
      include: {
        goals: {
          include: {
            tasks: {
              where: {
                status: { in: ['pending', 'in_progress'] },
              },
              orderBy: { order: 'asc' },
            },
          },
          orderBy: { order: 'asc' },
        },
        conversations: {
          orderBy: { createdAt: 'desc' },
          take: 1,
        },
      },
    });

    if (!dream) {
      throw new NotFoundError('Dream not found');
    }

    if (dream.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    return success(res, { dream });
  });

  update = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { id } = req.params;
    const { title, description, category, targetDate, priority, status } = req.body;

    // Check ownership
    const existing = await prisma.dream.findUnique({
      where: { id },
      select: { userId: true },
    });

    if (!existing) {
      throw new NotFoundError('Dream not found');
    }

    if (existing.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    const dream = await prisma.dream.update({
      where: { id },
      data: {
        ...(title && { title }),
        ...(description && { description }),
        ...(category && { category }),
        ...(targetDate !== undefined && { targetDate: targetDate ? new Date(targetDate) : null }),
        ...(priority && { priority }),
        ...(status && { status }),
      },
    });

    return success(res, { dream }, 'Dream updated successfully');
  });

  delete = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { id } = req.params;

    // Check ownership
    const existing = await prisma.dream.findUnique({
      where: { id },
      select: { userId: true },
    });

    if (!existing) {
      throw new NotFoundError('Dream not found');
    }

    if (existing.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    await prisma.dream.delete({ where: { id } });

    return success(res, null, 'Dream deleted successfully');
  });

  generatePlan = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { id } = req.params;
    const { conversationId } = req.body;

    // Check ownership
    const dream = await prisma.dream.findUnique({
      where: { id },
      select: {
        userId: true,
        title: true,
        description: true,
        targetDate: true,
      },
    });

    if (!dream) {
      throw new NotFoundError('Dream not found');
    }

    if (dream.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    // Get user context
    const user = await prisma.user.findUnique({
      where: { id: req.user!.id },
      select: {
        timezone: true,
        workSchedule: true,
      },
    });

    // Generate plan using AI
    logger.info('Generating plan:', { userId: req.user!.id, dreamId: id });
    const plan = await aiService.generatePlan({
      objective: dream.title,
      description: dream.description,
      targetDate: dream.targetDate ? dream.targetDate.toISOString() : undefined,
      userContext: {
        timezone: user?.timezone,
        workSchedule: user?.workSchedule as any,
      },
    });

    // Create goals and tasks in database
    const goalsData = await Promise.all(
      plan.goals.map(async (goal, goalIndex) => {
        const createdGoal = await prisma.goal.create({
          data: {
            dreamId: id,
            title: goal.title,
            description: goal.description,
            order: goalIndex,
            estimatedMinutes: goal.estimatedMinutes,
          },
        });

        // Create tasks for this goal
        await prisma.task.createMany({
          data: goal.tasks.map((task, taskIndex) => ({
            goalId: createdGoal.id,
            title: task.title,
            description: task.description,
            order: taskIndex,
            estimatedMinutes: task.estimatedMinutes,
          })),
        });

        return createdGoal;
      })
    );

    // Update dream with AI analysis
    await prisma.dream.update({
      where: { id },
      data: {
        aiAnalysis: {
          ...plan,
          generatedAt: new Date().toISOString(),
        },
      },
    });

    logger.info('Plan generated successfully:', {
      userId: req.user!.id,
      dreamId: id,
      goalsCount: goalsData.length,
    });

    return success(res, {
      plan,
      goals: goalsData,
    }, 'Plan generated successfully');
  });

  complete = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { id } = req.params;

    // Check ownership
    const existing = await prisma.dream.findUnique({
      where: { id },
      select: { userId: true },
    });

    if (!existing) {
      throw new NotFoundError('Dream not found');
    }

    if (existing.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    const dream = await prisma.dream.update({
      where: { id },
      data: {
        status: 'completed',
        completedAt: new Date(),
      },
    });

    logger.info('Dream completed:', { userId: req.user!.id, dreamId: id });

    return success(res, { dream }, 'Dream completed! Congratulations!');
  });
}

export const dreamsController = new DreamsController();
