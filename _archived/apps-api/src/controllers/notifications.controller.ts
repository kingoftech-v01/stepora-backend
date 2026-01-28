import { Response, NextFunction } from 'express';
import { AuthRequest } from '../middleware/auth';
import { prisma } from '../utils/prisma';
import { success } from '../utils/response';
import { asyncHandler } from '../middleware/errorHandler';

class NotificationsController {
  list = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const notifications = await prisma.notification.findMany({
      where: { userId: req.user!.id },
      orderBy: { scheduledFor: 'desc' },
      take: 50,
    });

    return success(res, { notifications });
  });

  markRead = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { id } = req.params;

    const notification = await prisma.notification.updateMany({
      where: {
        id,
        userId: req.user!.id,
      },
      data: {
        readAt: new Date(),
      },
    });

    return success(res, null, 'Notification marked as read');
  });

  markAllRead = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    await prisma.notification.updateMany({
      where: {
        userId: req.user!.id,
        readAt: null,
      },
      data: {
        readAt: new Date(),
      },
    });

    return success(res, null, 'All notifications marked as read');
  });
}

export const notificationsController = new NotificationsController();
