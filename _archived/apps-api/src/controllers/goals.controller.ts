import { Response, NextFunction } from 'express';
import { AuthRequest } from '../middleware/auth';
import { prisma } from '../utils/prisma';
import { success } from '../utils/response';
import { asyncHandler } from '../middleware/errorHandler';
import { NotFoundError, AuthorizationError } from '../utils/errors';

class GoalsController {
  list = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { dreamId } = req.query;

    const goals = await prisma.goal.findMany({
      where: {
        ...(dreamId && { dreamId: dreamId as string }),
        dream: {
          userId: req.user!.id,
        },
      },
      include: {
        tasks: {
          where: { status: { in: ['pending', 'in_progress'] } },
        },
        _count: {
          select: { tasks: true },
        },
      },
      orderBy: { order: 'asc' },
    });

    return success(res, { goals });
  });

  get = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { id } = req.params;

    const goal = await prisma.goal.findUnique({
      where: { id },
      include: {
        tasks: {
          orderBy: { order: 'asc' },
        },
        dream: {
          select: { userId: true },
        },
      },
    });

    if (!goal) {
      throw new NotFoundError('Goal not found');
    }

    if (goal.dream.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    return success(res, { goal });
  });

  update = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { id } = req.params;
    const updateData = req.body;

    // Check ownership via dream
    const existing = await prisma.goal.findUnique({
      where: { id },
      include: { dream: { select: { userId: true } } },
    });

    if (!existing) {
      throw new NotFoundError('Goal not found');
    }

    if (existing.dream.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    const goal = await prisma.goal.update({
      where: { id },
      data: updateData,
    });

    return success(res, { goal }, 'Goal updated successfully');
  });

  complete = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { id } = req.params;

    const existing = await prisma.goal.findUnique({
      where: { id },
      include: { dream: { select: { userId: true } } },
    });

    if (!existing) {
      throw new NotFoundError('Goal not found');
    }

    if (existing.dream.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    const goal = await prisma.goal.update({
      where: { id },
      data: {
        status: 'completed',
        completedAt: new Date(),
      },
    });

    return success(res, { goal }, 'Goal completed!');
  });
}

export const goalsController = new GoalsController();
