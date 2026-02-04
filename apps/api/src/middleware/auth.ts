import { Request, Response, NextFunction } from 'express';
import { getAuth } from 'firebase-admin/auth';
import { prisma } from '../config/database';

export interface AuthenticatedRequest extends Request {
  userId?: string;
  user?: {
    id: string;
    firebaseUid: string;
    email: string;
  };
}

export const authMiddleware = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      res.status(401).json({
        success: false,
        error: { message: 'No authentication token provided', code: 401 },
      });
      return;
    }

    const token = authHeader.split(' ')[1];

    // For testing purposes, accept test tokens
    if (process.env.NODE_ENV === 'test' && token.startsWith('test-token-')) {
      const testUserId = token.replace('test-token-', '');

      const user = await prisma.user.findUnique({
        where: { id: testUserId },
      });

      if (!user) {
        res.status(401).json({
          success: false,
          error: { message: 'User not found', code: 401 },
        });
        return;
      }

      req.userId = user.id;
      req.user = {
        id: user.id,
        firebaseUid: user.firebaseUid,
        email: user.email,
      };
      next();
      return;
    }

    // Verify Firebase token
    const auth = getAuth();
    const decodedToken = await auth.verifyIdToken(token);

    // Find user in database
    const user = await prisma.user.findUnique({
      where: { firebaseUid: decodedToken.uid },
    });

    if (!user) {
      res.status(401).json({
        success: false,
        error: { message: 'User not found', code: 401 },
      });
      return;
    }

    req.userId = user.id;
    req.user = {
      id: user.id,
      firebaseUid: user.firebaseUid,
      email: user.email,
    };

    next();
  } catch (error) {
    console.error('Auth middleware error:', error);
    res.status(401).json({
      success: false,
      error: { message: 'Invalid or expired token', code: 401 },
    });
  }
};

export default authMiddleware;
