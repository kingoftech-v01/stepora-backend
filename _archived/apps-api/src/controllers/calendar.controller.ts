import { Response, NextFunction } from 'express';
import { AuthRequest } from '../middleware/auth';
import { prisma } from '../utils/prisma';
import { success } from '../utils/response';
import { asyncHandler } from '../middleware/errorHandler';

class CalendarController {
  getCalendar = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { startDate, endDate } = req.query;

    const tasks = await prisma.task.findMany({
      where: {
        scheduledDate: {
          gte: new Date(startDate as string),
          lte: new Date(endDate as string),
        },
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
            dream: { select: { title: true, category: true } },
          },
        },
      },
      orderBy: [{ scheduledDate: 'asc' }, { scheduledTime: 'asc' }],
    });

    // Group by date
    const tasksByDate = tasks.reduce((acc, task) => {
      if (!task.scheduledDate) return acc;

      const dateKey = task.scheduledDate.toISOString().split('T')[0];
      if (!acc[dateKey]) {
        acc[dateKey] = [];
      }
      acc[dateKey].push(task);
      return acc;
    }, {} as Record<string, typeof tasks>);

    return success(res, { tasks: tasksByDate });
  });

  getToday = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    const tasks = await prisma.task.findMany({
      where: {
        scheduledDate: {
          gte: today,
          lt: tomorrow,
        },
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
            dream: { select: { title: true, category: true } },
          },
        },
      },
      orderBy: [{ scheduledTime: 'asc' }, { order: 'asc' }],
    });

    return success(res, { tasks });
  });

  getWeek = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const weekEnd = new Date(today);
    weekEnd.setDate(weekEnd.getDate() + 7);

    const tasks = await prisma.task.findMany({
      where: {
        scheduledDate: {
          gte: today,
          lt: weekEnd,
        },
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
            dream: { select: { title: true, category: true } },
          },
        },
      },
      orderBy: [{ scheduledDate: 'asc' }, { scheduledTime: 'asc' }],
    });

    return success(res, { tasks });
  });
}

export const calendarController = new CalendarController();
