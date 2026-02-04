import { Router, Request, Response, NextFunction } from 'express';
import { getAuth } from 'firebase-admin/auth';
import { userService } from '../services/user.service';
import { createUserSchema, loginSchema } from '../validators';
import { AppError } from '../middleware/errorHandler';

export const authRouter = Router();

// POST /api/auth/register - Register new user
authRouter.post(
  '/register',
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const data = createUserSchema.parse(req.body);

      // Verify Firebase token
      const auth = getAuth();
      let decodedToken;

      try {
        decodedToken = await auth.verifyIdToken(data.idToken);
      } catch (error) {
        throw new AppError('Invalid or expired token', 401);
      }

      // Check if user already exists
      const existingUser = await userService.findByFirebaseUid(decodedToken.uid);
      if (existingUser) {
        throw new AppError('User already exists', 409);
      }

      // Create user in database
      const user = await userService.create({
        firebaseUid: decodedToken.uid,
        email: decodedToken.email || data.email,
        displayName: data.displayName || decodedToken.name,
        avatarUrl: decodedToken.picture,
        timezone: data.timezone,
      });

      // Register FCM token if provided
      if (data.fcmToken && data.platform) {
        await userService.registerFcmToken(user.id, data.fcmToken, data.platform);
      }

      res.status(201).json({
        success: true,
        data: {
          user: {
            id: user.id,
            email: user.email,
            displayName: user.displayName,
            avatarUrl: user.avatarUrl,
            timezone: user.timezone,
            subscription: user.subscription,
          },
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/auth/login - Login existing user
authRouter.post(
  '/login',
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const data = loginSchema.parse(req.body);

      // Verify Firebase token
      const auth = getAuth();
      let decodedToken;

      try {
        decodedToken = await auth.verifyIdToken(data.idToken);
      } catch (error) {
        throw new AppError('Invalid or expired token', 401);
      }

      // Find user
      let user = await userService.findByFirebaseUid(decodedToken.uid);

      // Auto-create user if doesn't exist (for social logins)
      if (!user) {
        user = await userService.create({
          firebaseUid: decodedToken.uid,
          email: decodedToken.email!,
          displayName: decodedToken.name,
          avatarUrl: decodedToken.picture,
        });
      }

      // Register/update FCM token if provided
      if (data.fcmToken && data.platform) {
        await userService.registerFcmToken(user.id, data.fcmToken, data.platform);
      }

      // Get user statistics
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
            workSchedule: user.workSchedule,
            notificationPrefs: user.notificationPrefs,
            appPrefs: user.appPrefs,
          },
          stats,
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/auth/logout - Logout (remove FCM token)
authRouter.post(
  '/logout',
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { fcmToken } = req.body;

      if (fcmToken) {
        await userService.removeFcmToken(fcmToken);
      }

      res.json({
        success: true,
        message: 'Logged out successfully',
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/auth/refresh-token - Refresh user session
authRouter.post(
  '/refresh-token',
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { idToken } = req.body;

      if (!idToken) {
        throw new AppError('Token is required', 400);
      }

      // Verify Firebase token
      const auth = getAuth();
      let decodedToken;

      try {
        decodedToken = await auth.verifyIdToken(idToken);
      } catch (error) {
        throw new AppError('Invalid or expired token', 401);
      }

      // Find user
      const user = await userService.findByFirebaseUid(decodedToken.uid);

      if (!user) {
        throw new AppError('User not found', 404);
      }

      res.json({
        success: true,
        data: {
          valid: true,
          expiresAt: new Date(decodedToken.exp * 1000).toISOString(),
        },
      });
    } catch (error) {
      next(error);
    }
  }
);
