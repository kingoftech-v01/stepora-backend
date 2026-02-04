import { describe, it, expect, vi, beforeEach } from 'vitest';
import { userService } from '../../services/user.service';
import { prisma } from '../../config/database';

const mockPrisma = vi.mocked(prisma);

describe('UserService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockUser = {
    id: 'user-1',
    firebaseUid: 'firebase-uid-1',
    email: 'test@example.com',
    displayName: 'Test User',
    avatarUrl: null,
    timezone: 'Europe/Paris',
    subscription: 'free',
    subscriptionEnds: null,
    workSchedule: null,
    notificationPrefs: null,
    appPrefs: null,
    createdAt: new Date('2024-01-01'),
    updatedAt: new Date('2024-01-01'),
  };

  describe('findById', () => {
    it('should return user when found', async () => {
      mockPrisma.user.findUnique.mockResolvedValue(mockUser);

      const result = await userService.findById('user-1');

      expect(result).toEqual(mockUser);
      expect(mockPrisma.user.findUnique).toHaveBeenCalledWith({
        where: { id: 'user-1' },
      });
    });

    it('should return null when user not found', async () => {
      mockPrisma.user.findUnique.mockResolvedValue(null);

      const result = await userService.findById('nonexistent');

      expect(result).toBeNull();
    });
  });

  describe('findByFirebaseUid', () => {
    it('should return user by firebase UID', async () => {
      mockPrisma.user.findUnique.mockResolvedValue(mockUser);

      const result = await userService.findByFirebaseUid('firebase-uid-1');

      expect(result).toEqual(mockUser);
      expect(mockPrisma.user.findUnique).toHaveBeenCalledWith({
        where: { firebaseUid: 'firebase-uid-1' },
      });
    });
  });

  describe('findByEmail', () => {
    it('should return user by email', async () => {
      mockPrisma.user.findUnique.mockResolvedValue(mockUser);

      const result = await userService.findByEmail('test@example.com');

      expect(result).toEqual(mockUser);
      expect(mockPrisma.user.findUnique).toHaveBeenCalledWith({
        where: { email: 'test@example.com' },
      });
    });
  });

  describe('create', () => {
    it('should create a new user', async () => {
      mockPrisma.user.create.mockResolvedValue(mockUser);

      const result = await userService.create({
        firebaseUid: 'firebase-uid-1',
        email: 'test@example.com',
        displayName: 'Test User',
        timezone: 'Europe/Paris',
      });

      expect(result).toEqual(mockUser);
      expect(mockPrisma.user.create).toHaveBeenCalledWith({
        data: {
          firebaseUid: 'firebase-uid-1',
          email: 'test@example.com',
          displayName: 'Test User',
          avatarUrl: undefined,
          timezone: 'Europe/Paris',
        },
      });
    });

    it('should use default timezone when not provided', async () => {
      mockPrisma.user.create.mockResolvedValue(mockUser);

      await userService.create({
        firebaseUid: 'firebase-uid-1',
        email: 'test@example.com',
      });

      expect(mockPrisma.user.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          timezone: 'Europe/Paris',
        }),
      });
    });
  });

  describe('update', () => {
    it('should update user profile', async () => {
      const updatedUser = { ...mockUser, displayName: 'Updated Name' };
      mockPrisma.user.update.mockResolvedValue(updatedUser);

      const result = await userService.update('user-1', {
        displayName: 'Updated Name',
      });

      expect(result.displayName).toBe('Updated Name');
      expect(mockPrisma.user.update).toHaveBeenCalledWith({
        where: { id: 'user-1' },
        data: { displayName: 'Updated Name' },
      });
    });

    it('should update work schedule', async () => {
      const workSchedule = {
        workDays: [1, 2, 3, 4, 5],
        startTime: '09:00',
        endTime: '18:00',
      };

      mockPrisma.user.update.mockResolvedValue({
        ...mockUser,
        workSchedule,
      });

      const result = await userService.update('user-1', { workSchedule });

      expect(result.workSchedule).toEqual(workSchedule);
    });

    it('should update notification preferences', async () => {
      const notificationPrefs = {
        reminders: true,
        reminderMinutesBefore: 15,
        motivation: true,
        motivationTime: '08:00',
        weeklyReport: true,
        weeklyReportDay: 0,
        dndEnabled: true,
        dndStart: 22,
        dndEnd: 7,
      };

      mockPrisma.user.update.mockResolvedValue({
        ...mockUser,
        notificationPrefs,
      });

      const result = await userService.update('user-1', { notificationPrefs });

      expect(result.notificationPrefs).toEqual(notificationPrefs);
    });

    it('should update app preferences', async () => {
      const appPrefs = { theme: 'dark' as const, language: 'en' as const };

      mockPrisma.user.update.mockResolvedValue({
        ...mockUser,
        appPrefs,
      });

      const result = await userService.update('user-1', { appPrefs });

      expect(result.appPrefs).toEqual(appPrefs);
    });
  });

  describe('updateSubscription', () => {
    it('should update subscription', async () => {
      const endsAt = new Date('2025-01-01');
      mockPrisma.user.update.mockResolvedValue({
        ...mockUser,
        subscription: 'premium',
        subscriptionEnds: endsAt,
      });

      const result = await userService.updateSubscription('user-1', 'premium', endsAt);

      expect(result.subscription).toBe('premium');
      expect(mockPrisma.user.update).toHaveBeenCalledWith({
        where: { id: 'user-1' },
        data: { subscription: 'premium', subscriptionEnds: endsAt },
      });
    });
  });

  describe('delete', () => {
    it('should delete user', async () => {
      mockPrisma.user.delete.mockResolvedValue(mockUser);

      await userService.delete('user-1');

      expect(mockPrisma.user.delete).toHaveBeenCalledWith({
        where: { id: 'user-1' },
      });
    });
  });

  describe('registerFcmToken', () => {
    it('should register a new FCM token', async () => {
      mockPrisma.fcmToken.upsert.mockResolvedValue({
        id: 'token-1',
        userId: 'user-1',
        token: 'fcm-token-123',
        platform: 'android',
        createdAt: new Date(),
        updatedAt: new Date(),
      });

      await userService.registerFcmToken('user-1', 'fcm-token-123', 'android');

      expect(mockPrisma.fcmToken.upsert).toHaveBeenCalledWith({
        where: { token: 'fcm-token-123' },
        create: {
          userId: 'user-1',
          token: 'fcm-token-123',
          platform: 'android',
        },
        update: expect.objectContaining({
          userId: 'user-1',
          platform: 'android',
        }),
      });
    });
  });

  describe('removeFcmToken', () => {
    it('should remove FCM token', async () => {
      mockPrisma.fcmToken.deleteMany.mockResolvedValue({ count: 1 });

      await userService.removeFcmToken('fcm-token-123');

      expect(mockPrisma.fcmToken.deleteMany).toHaveBeenCalledWith({
        where: { token: 'fcm-token-123' },
      });
    });
  });

  describe('getUserFcmTokens', () => {
    it('should return user FCM tokens', async () => {
      mockPrisma.fcmToken.findMany.mockResolvedValue([
        { token: 'token-1' } as any,
        { token: 'token-2' } as any,
      ]);

      const tokens = await userService.getUserFcmTokens('user-1');

      expect(tokens).toEqual(['token-1', 'token-2']);
    });

    it('should return empty array when no tokens', async () => {
      mockPrisma.fcmToken.findMany.mockResolvedValue([]);

      const tokens = await userService.getUserFcmTokens('user-1');

      expect(tokens).toEqual([]);
    });
  });

  describe('getStatistics', () => {
    it('should return user statistics', async () => {
      mockPrisma.dream.groupBy.mockResolvedValue([
        { status: 'active', _count: 3 },
        { status: 'completed', _count: 2 },
      ] as any);

      mockPrisma.task.findMany
        .mockResolvedValueOnce([
          { status: 'completed', completedAt: new Date() },
          { status: 'completed', completedAt: new Date() },
          { status: 'pending', completedAt: null },
        ] as any)
        .mockResolvedValueOnce([
          { completedAt: new Date() },
          { completedAt: new Date(Date.now() - 86400000) },
        ] as any);

      const stats = await userService.getStatistics('user-1');

      expect(stats).toEqual(expect.objectContaining({
        totalDreams: 5,
        activeDreams: 3,
        completedDreams: 2,
        totalTasks: 3,
        completedTasks: 2,
        totalXp: 20,
      }));
    });

    it('should handle user with no data', async () => {
      mockPrisma.dream.groupBy.mockResolvedValue([] as any);
      mockPrisma.task.findMany
        .mockResolvedValueOnce([])
        .mockResolvedValueOnce([]);

      const stats = await userService.getStatistics('user-1');

      expect(stats.totalDreams).toBe(0);
      expect(stats.completedTasks).toBe(0);
      expect(stats.currentStreak).toBe(0);
      expect(stats.level).toBe(1);
    });
  });
});
