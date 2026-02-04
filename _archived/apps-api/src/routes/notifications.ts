import { Router, Response, NextFunction } from 'express';
import { notificationService } from '../services/notification.service';
import { AuthenticatedRequest } from '../middleware/auth';
import { AppError } from '../middleware/errorHandler';

export const notificationsRouter = Router();

// GET /api/notifications - Get all notifications
notificationsRouter.get(
  '/',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const { status, type, limit, offset } = req.query;

      const result = await notificationService.findAllByUser(req.userId!, {
        status: status as string,
        type: type as any,
        limit: limit ? parseInt(limit as string, 10) : undefined,
        offset: offset ? parseInt(offset as string, 10) : undefined,
      });

      res.json({
        success: true,
        data: {
          notifications: result.notifications,
          total: result.total,
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/notifications/unread-count - Get unread notification count
notificationsRouter.get(
  '/unread-count',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const count = await notificationService.getUnreadCount(req.userId!);

      res.json({
        success: true,
        data: { count },
      });
    } catch (error) {
      next(error);
    }
  }
);

// PATCH /api/notifications/:id/read - Mark notification as read
notificationsRouter.patch(
  '/:id/read',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const notification = await notificationService.markAsRead(
        req.params.id,
        req.userId!
      );

      res.json({
        success: true,
        data: { notification },
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/notifications/read-all - Mark all notifications as read
notificationsRouter.post(
  '/read-all',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const count = await notificationService.markAllAsRead(req.userId!);

      res.json({
        success: true,
        data: { markedCount: count },
      });
    } catch (error) {
      next(error);
    }
  }
);

// DELETE /api/notifications/:id - Delete a notification
notificationsRouter.delete(
  '/:id',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      await notificationService.delete(req.params.id, req.userId!);

      res.json({
        success: true,
        message: 'Notification deleted successfully',
      });
    } catch (error) {
      next(error);
    }
  }
);
