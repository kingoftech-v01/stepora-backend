import { Request, Response, NextFunction } from 'express';
import { admin } from '../config/firebase';
import { prisma } from '../utils/prisma';
import { AuthenticationError } from '../utils/errors';
import { logger } from '../config/logger';

export interface AuthRequest extends Request {
  user?: {
    id: string;
    firebaseUid: string;
    email: string;
    displayName?: string;
    subscription: string;
  };
}

export const authMiddleware = async (
  req: AuthRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    // Get token from Authorization header
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      throw new AuthenticationError('No token provided');
    }

    const token = authHeader.substring(7);

    // Verify Firebase token
    let decodedToken;
    try {
      decodedToken = await admin.auth().verifyIdToken(token);
    } catch (error: any) {
      logger.warn('Token verification failed:', { error: error.message });
      throw new AuthenticationError('Invalid or expired token');
    }

    // Get or create user in database
    let user = await prisma.user.findUnique({
      where: { firebaseUid: decodedToken.uid },
      select: {
        id: true,
        firebaseUid: true,
        email: true,
        displayName: true,
        subscription: true,
      },
    });

    // Create user if doesn't exist (first login)
    if (!user) {
      user = await prisma.user.create({
        data: {
          firebaseUid: decodedToken.uid,
          email: decodedToken.email!,
          displayName: decodedToken.name,
        },
        select: {
          id: true,
          firebaseUid: true,
          email: true,
          displayName: true,
          subscription: true,
        },
      });

      logger.info('New user created:', { userId: user.id, email: user.email });
    }

    // Attach user to request
    req.user = user;
    next();
  } catch (error) {
    next(error);
  }
};
