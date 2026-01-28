import { Response, NextFunction } from 'express';
import { AuthRequest } from '../middleware/auth';
import { prisma } from '../utils/prisma';
import { success } from '../utils/response';
import { asyncHandler } from '../middleware/errorHandler';
import { admin } from '../config/firebase';
import { logger } from '../config/logger';

class AuthController {
  register = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { displayName, timezone } = req.body;

    // User is already authenticated via authMiddleware
    // Update additional info if provided
    if (displayName || timezone) {
      const user = await prisma.user.update({
        where: { id: req.user!.id },
        data: {
          ...(displayName && { displayName }),
          ...(timezone && { timezone }),
        },
      });

      logger.info('User registered with additional info:', { userId: user.id });
      return success(res, { user }, 'Registration successful', 201);
    }

    return success(res, { user: req.user }, 'Registration successful', 201);
  });

  verify = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    // User is already verified via authMiddleware
    return success(res, { user: req.user });
  });
}

export const authController = new AuthController();
