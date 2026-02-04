import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Request, Response, NextFunction } from 'express';
import { authMiddleware, AuthenticatedRequest } from '../../middleware/auth';
import { prisma } from '../../config/database';

const mockPrisma = vi.mocked(prisma);

vi.mock('firebase-admin/auth', () => ({
  getAuth: vi.fn(() => ({
    verifyIdToken: vi.fn().mockResolvedValue({
      uid: 'firebase-uid-1',
      email: 'test@example.com',
    }),
  })),
}));

describe('Auth Middleware', () => {
  let mockReq: Partial<AuthenticatedRequest>;
  let mockRes: Partial<Response>;
  let mockNext: NextFunction;
  let jsonMock: ReturnType<typeof vi.fn>;
  let statusMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    jsonMock = vi.fn();
    statusMock = vi.fn().mockReturnValue({ json: jsonMock });
    mockReq = {
      headers: {},
    };
    mockRes = {
      status: statusMock,
      json: jsonMock,
    };
    mockNext = vi.fn();
  });

  it('should reject request without authorization header', async () => {
    mockReq.headers = {};

    await authMiddleware(
      mockReq as AuthenticatedRequest,
      mockRes as Response,
      mockNext
    );

    expect(statusMock).toHaveBeenCalledWith(401);
    expect(jsonMock).toHaveBeenCalledWith(
      expect.objectContaining({
        success: false,
        error: expect.objectContaining({
          message: expect.stringContaining('token'),
        }),
      })
    );
  });

  it('should reject request with invalid authorization format', async () => {
    mockReq.headers = {
      authorization: 'InvalidFormat',
    };

    await authMiddleware(
      mockReq as AuthenticatedRequest,
      mockRes as Response,
      mockNext
    );

    expect(statusMock).toHaveBeenCalledWith(401);
  });

  it('should authenticate with valid test token in test environment', async () => {
    process.env.NODE_ENV = 'test';
    mockReq.headers = {
      authorization: 'Bearer test-token-user-1',
    };

    mockPrisma.user.findUnique.mockResolvedValue({
      id: 'user-1',
      firebaseUid: 'test-uid',
      email: 'test@example.com',
      displayName: 'Test',
      avatarUrl: null,
      timezone: 'Europe/Paris',
      subscription: 'free',
      subscriptionEnds: null,
      workSchedule: null,
      notificationPrefs: null,
      appPrefs: null,
      createdAt: new Date(),
      updatedAt: new Date(),
    });

    await authMiddleware(
      mockReq as AuthenticatedRequest,
      mockRes as Response,
      mockNext
    );

    expect(mockNext).toHaveBeenCalled();
    expect(mockReq.userId).toBe('user-1');
  });

  it('should reject test token with nonexistent user', async () => {
    process.env.NODE_ENV = 'test';
    mockReq.headers = {
      authorization: 'Bearer test-token-nonexistent',
    };

    mockPrisma.user.findUnique.mockResolvedValue(null);

    await authMiddleware(
      mockReq as AuthenticatedRequest,
      mockRes as Response,
      mockNext
    );

    expect(statusMock).toHaveBeenCalledWith(401);
  });

  it('should authenticate with valid Firebase token', async () => {
    process.env.NODE_ENV = 'production';
    mockReq.headers = {
      authorization: 'Bearer valid-firebase-token',
    };

    const { getAuth } = await import('firebase-admin/auth');
    vi.mocked(getAuth).mockReturnValue({
      verifyIdToken: vi.fn().mockResolvedValue({
        uid: 'firebase-uid-1',
        email: 'test@example.com',
      }),
    } as any);

    mockPrisma.user.findUnique.mockResolvedValue({
      id: 'user-1',
      firebaseUid: 'firebase-uid-1',
      email: 'test@example.com',
      displayName: 'Test',
      avatarUrl: null,
      timezone: 'Europe/Paris',
      subscription: 'free',
      subscriptionEnds: null,
      workSchedule: null,
      notificationPrefs: null,
      appPrefs: null,
      createdAt: new Date(),
      updatedAt: new Date(),
    });

    await authMiddleware(
      mockReq as AuthenticatedRequest,
      mockRes as Response,
      mockNext
    );

    expect(mockNext).toHaveBeenCalled();
    expect(mockReq.userId).toBe('user-1');
    expect(mockReq.user).toEqual(
      expect.objectContaining({
        id: 'user-1',
        firebaseUid: 'firebase-uid-1',
        email: 'test@example.com',
      })
    );

    // Reset env
    process.env.NODE_ENV = 'test';
  });

  it('should reject when Firebase user not found in DB', async () => {
    process.env.NODE_ENV = 'production';
    mockReq.headers = {
      authorization: 'Bearer valid-firebase-token',
    };

    const { getAuth } = await import('firebase-admin/auth');
    vi.mocked(getAuth).mockReturnValue({
      verifyIdToken: vi.fn().mockResolvedValue({
        uid: 'unknown-uid',
        email: 'unknown@example.com',
      }),
    } as any);

    mockPrisma.user.findUnique.mockResolvedValue(null);

    await authMiddleware(
      mockReq as AuthenticatedRequest,
      mockRes as Response,
      mockNext
    );

    expect(statusMock).toHaveBeenCalledWith(401);
    expect(jsonMock).toHaveBeenCalledWith(
      expect.objectContaining({
        success: false,
        error: expect.objectContaining({
          message: 'User not found',
        }),
      })
    );

    process.env.NODE_ENV = 'test';
  });

  it('should handle Firebase token verification error', async () => {
    process.env.NODE_ENV = 'production';
    mockReq.headers = {
      authorization: 'Bearer expired-token',
    };

    const { getAuth } = await import('firebase-admin/auth');
    vi.mocked(getAuth).mockReturnValue({
      verifyIdToken: vi.fn().mockRejectedValue(new Error('Token expired')),
    } as any);

    await authMiddleware(
      mockReq as AuthenticatedRequest,
      mockRes as Response,
      mockNext
    );

    expect(statusMock).toHaveBeenCalledWith(401);
    expect(jsonMock).toHaveBeenCalledWith(
      expect.objectContaining({
        success: false,
        error: expect.objectContaining({
          message: 'Invalid or expired token',
        }),
      })
    );

    process.env.NODE_ENV = 'test';
  });
});
