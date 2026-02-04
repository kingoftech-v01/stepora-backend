import { Response, NextFunction } from 'express';
import { AuthRequest } from '../middleware/auth';
import { prisma } from '../utils/prisma';
import { success } from '../utils/response';
import { asyncHandler } from '../middleware/errorHandler';
import { NotFoundError, AuthorizationError } from '../utils/errors';
import { gamificationService } from '../services/gamification.service';
import { socialService } from '../services/social.service';

class TasksController {
  list = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { goalId, status, startDate, endDate } = req.query;

    const tasks = await prisma.task.findMany({
      where: {
        ...(goalId && { goalId: goalId as string }),
        ...(status && { status: status as string }),
        ...(startDate && endDate && {
          scheduledDate: {
            gte: new Date(startDate as string),
            lte: new Date(endDate as string),
          },
        }),
        goal: {
          dream: {
            userId: req.user!.id,
          },
        },
      },
      include: {
        goal: {
          select: {
            title: true,
            dream: { select: { title: true } },
          },
        },
      },
      orderBy: [{ scheduledDate: 'asc' }, { order: 'asc' }],
    });

    return success(res, { tasks });
  });

  update = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { id } = req.params;
    const updateData = req.body;

    // Check ownership
    const existing = await prisma.task.findUnique({
      where: { id },
      include: {
        goal: {
          include: { dream: { select: { userId: true } } },
        },
      },
    });

    if (!existing) {
      throw new NotFoundError('Task not found');
    }

    if (existing.goal.dream.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    const task = await prisma.task.update({
      where: { id },
      data: updateData,
    });

    return success(res, { task }, 'Task updated successfully');
  });

  complete = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { id } = req.params;

    const existing = await prisma.task.findUnique({
      where: { id },
      include: {
        goal: {
          include: {
            dream: {
              select: {
                userId: true,
                category: true,
                title: true,
              }
            }
          },
        },
      },
    });

    if (!existing) {
      throw new NotFoundError('Task not found');
    }

    if (existing.goal.dream.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    const task = await prisma.task.update({
      where: { id },
      data: {
        status: 'completed',
        completedAt: new Date(),
      },
    });

    // Award XP and update gamification stats
    try {
      const category = existing.goal.dream.category || 'general';
      await gamificationService.handleTaskCompletion(req.user!.id, id, category);

      // Create activity for social feed
      await socialService.createActivity(
        req.user!.id,
        'task_completed',
        {
          taskTitle: existing.title,
          dreamTitle: existing.goal.dream.title,
        },
        'friends'
      );
    } catch (error) {
      // Log error but don't fail the request
      console.error('Failed to update gamification:', error);
    }

    return success(res, { task }, 'Task completed! 🎉');
  });

  skip = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { id } = req.params;

    const existing = await prisma.task.findUnique({
      where: { id },
      include: {
        goal: {
          include: { dream: { select: { userId: true } } },
        },
      },
    });

    if (!existing) {
      throw new NotFoundError('Task not found');
    }

    if (existing.goal.dream.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    const task = await prisma.task.update({
      where: { id },
      data: {
        status: 'skipped',
      },
    });

    return success(res, { task }, 'Task skipped');
  });
}

export const tasksController = new TasksController();
