import { Router, Response, NextFunction } from 'express';
import { userService } from '../services/user.service';
import { updateUserSchema } from '../validators';
import { AuthenticatedRequest } from '../middleware/auth';
import { AppError } from '../middleware/errorHandler';

export const usersRouter = Router();

// GET /api/users/me - Get current user profile
usersRouter.get(
  '/me',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const user = await userService.findById(req.userId!);

      if (!user) {
        throw new AppError('User not found', 404);
      }

      const stats = await userService.getStatistics(user.id);

      res.json({
        success: true,
        data: {
          user: {
            id: user.id,
            email: user.email,
            displayName: user.displayName,
            avatarUrl: user.avatarUrl,
            timezone: user.timezone,
            subscription: user.subscription,
            subscriptionEnds: user.subscriptionEnds,
            workSchedule: user.workSchedule,
            notificationPrefs: user.notificationPrefs,
            appPrefs: user.appPrefs,
            createdAt: user.createdAt,
          },
          stats,
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

// PATCH /api/users/me - Update current user profile
usersRouter.patch(
  '/me',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const data = updateUserSchema.parse(req.body);

      const user = await userService.update(req.userId!, data);

      res.json({
        success: true,
        data: {
          user: {
            id: user.id,
            email: user.email,
            displayName: user.displayName,
            avatarUrl: user.avatarUrl,
            timezone: user.timezone,
            subscription: user.subscription,
            workSchedule: user.workSchedule,
            notificationPrefs: user.notificationPrefs,
            appPrefs: user.appPrefs,
          },
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

// DELETE /api/users/me - Delete current user account
usersRouter.delete(
  '/me',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      await userService.delete(req.userId!);

      res.json({
        success: true,
        message: 'Account deleted successfully',
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/users/me/stats - Get user statistics
usersRouter.get(
  '/me/stats',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const stats = await userService.getStatistics(req.userId!);

      res.json({
        success: true,
        data: stats,
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/users/me/fcm-token - Register FCM token
usersRouter.post(
  '/me/fcm-token',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const { token, platform } = req.body;

      if (!token || !platform) {
        throw new AppError('Token and platform are required', 400);
      }

      if (!['ios', 'android'].includes(platform)) {
        throw new AppError('Platform must be ios or android', 400);
      }

      await userService.registerFcmToken(req.userId!, token, platform);

      res.json({
        success: true,
        message: 'FCM token registered successfully',
      });
    } catch (error) {
      next(error);
    }
  }
);

// DELETE /api/users/me/fcm-token - Remove FCM token
usersRouter.delete(
  '/me/fcm-token',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const { token } = req.body;

      if (!token) {
        throw new AppError('Token is required', 400);
      }

      await userService.removeFcmToken(token);

      res.json({
        success: true,
        message: 'FCM token removed successfully',
      });
    } catch (error) {
      next(error);
    }
  }
);
