import { Response, NextFunction } from 'express';
import { AuthRequest } from '../middleware/auth';
import { prisma } from '../utils/prisma';
import { success } from '../utils/response';
import { asyncHandler } from '../middleware/errorHandler';
import { NotFoundError } from '../utils/errors';

class UsersController {
  getMe = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const user = await prisma.user.findUnique({
      where: { id: req.user!.id },
      include: {
        dreams: {
          where: { status: 'active' },
          select: { id: true, title: true, priority: true },
          take: 5,
        },
      },
    });

    if (!user) {
      throw new NotFoundError('User not found');
    }

    return success(res, { user });
  });

  updateMe = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { displayName, timezone, workSchedule, appPreferences, notificationPrefs } = req.body;

    const user = await prisma.user.update({
      where: { id: req.user!.id },
      data: {
        ...(displayName && { displayName }),
        ...(timezone && { timezone }),
        ...(workSchedule && { workSchedule }),
        ...(appPreferences && { appPreferences }),
        ...(notificationPrefs && { notificationPrefs }),
      },
    });

    return success(res, { user }, 'Profile updated successfully');
  });

  registerFcmToken = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { token, platform } = req.body;

    // Remove old tokens for this device
    await prisma.fcmToken.deleteMany({
      where: {
        userId: req.user!.id,
        token,
      },
    });

    // Create new token
    const fcmToken = await prisma.fcmToken.create({
      data: {
        userId: req.user!.id,
        token,
        platform,
      },
    });

    return success(res, { fcmToken }, 'FCM token registered successfully');
  });
}

export const usersController = new UsersController();
