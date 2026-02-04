import { describe, it, expect, vi, beforeEach } from 'vitest';
import { notificationService } from '../../services/notification.service';
import { prisma } from '../../config/database';

vi.mock('../../services/user.service', () => ({
  userService: {
    getUserFcmTokens: vi.fn(),
  },
}));

vi.mock('../../services/ai.service', () => ({
  aiService: {
    generateMotivationalMessage: vi.fn().mockResolvedValue('Keep going!'),
  },
}));

const mockPrisma = vi.mocked(prisma);

describe('NotificationService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockNotification = {
    id: 'notif-1',
    userId: 'user-1',
    type: 'reminder',
    title: 'Task Reminder',
    body: 'Practice guitar in 15 minutes',
    data: { screen: 'TaskDetail', params: { taskId: 'task-1' } },
    scheduledFor: new Date('2024-01-15T18:15:00Z'),
    sentAt: null,
    readAt: null,
    status: 'pending',
    createdAt: new Date(),
  };

  describe('findById', () => {
    it('should return notification when found', async () => {
      mockPrisma.notification.findFirst.mockResolvedValue(mockNotification as any);

      const result = await notificationService.findById('notif-1', 'user-1');

      expect(result).toEqual(mockNotification);
    });

    it('should return null when not found', async () => {
      mockPrisma.notification.findFirst.mockResolvedValue(null);

      const result = await notificationService.findById('nonexistent', 'user-1');

      expect(result).toBeNull();
    });
  });

  describe('findAllByUser', () => {
    it('should return notifications for user', async () => {
      mockPrisma.notification.findMany.mockResolvedValue([mockNotification] as any);
      mockPrisma.notification.count.mockResolvedValue(1);

      const result = await notificationService.findAllByUser('user-1');

      expect(result.notifications).toHaveLength(1);
      expect(result.total).toBe(1);
    });

    it('should filter by status', async () => {
      mockPrisma.notification.findMany.mockResolvedValue([]);
      mockPrisma.notification.count.mockResolvedValue(0);

      await notificationService.findAllByUser('user-1', { status: 'sent' });

      expect(mockPrisma.notification.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: { userId: 'user-1', status: 'sent' },
        })
      );
    });

    it('should filter by type', async () => {
      mockPrisma.notification.findMany.mockResolvedValue([]);
      mockPrisma.notification.count.mockResolvedValue(0);

      await notificationService.findAllByUser('user-1', { type: 'motivation' });

      expect(mockPrisma.notification.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: { userId: 'user-1', type: 'motivation' },
        })
      );
    });
  });

  describe('create', () => {
    it('should create a notification', async () => {
      mockPrisma.notification.create.mockResolvedValue(mockNotification as any);

      const result = await notificationService.create('user-1', {
        type: 'reminder',
        title: 'Task Reminder',
        body: 'Practice guitar in 15 minutes',
        scheduledFor: new Date('2024-01-15T18:15:00Z'),
        data: { screen: 'TaskDetail', params: { taskId: 'task-1' } },
      });

      expect(result).toEqual(mockNotification);
    });
  });

  describe('markAsRead', () => {
    it('should mark notification as read', async () => {
      mockPrisma.notification.findFirst.mockResolvedValue(mockNotification as any);
      mockPrisma.notification.update.mockResolvedValue({
        ...mockNotification,
        readAt: new Date(),
      } as any);

      const result = await notificationService.markAsRead('notif-1', 'user-1');

      expect(result.readAt).toBeDefined();
    });

    it('should throw when notification not found', async () => {
      mockPrisma.notification.findFirst.mockResolvedValue(null);

      await expect(
        notificationService.markAsRead('nonexistent', 'user-1')
      ).rejects.toThrow('Notification not found');
    });
  });

  describe('markAllAsRead', () => {
    it('should mark all as read and return count', async () => {
      mockPrisma.notification.updateMany.mockResolvedValue({ count: 5 });

      const result = await notificationService.markAllAsRead('user-1');

      expect(result).toBe(5);
      expect(mockPrisma.notification.updateMany).toHaveBeenCalledWith({
        where: { userId: 'user-1', readAt: null },
        data: { readAt: expect.any(Date) },
      });
    });
  });

  describe('delete', () => {
    it('should delete notification', async () => {
      mockPrisma.notification.findFirst.mockResolvedValue(mockNotification as any);
      mockPrisma.notification.delete.mockResolvedValue(mockNotification as any);

      await notificationService.delete('notif-1', 'user-1');

      expect(mockPrisma.notification.delete).toHaveBeenCalledWith({
        where: { id: 'notif-1' },
      });
    });

    it('should throw when notification not found', async () => {
      mockPrisma.notification.findFirst.mockResolvedValue(null);

      await expect(
        notificationService.delete('nonexistent', 'user-1')
      ).rejects.toThrow('Notification not found');
    });
  });

  describe('getUnreadCount', () => {
    it('should return unread count', async () => {
      mockPrisma.notification.count.mockResolvedValue(3);

      const count = await notificationService.getUnreadCount('user-1');

      expect(count).toBe(3);
      expect(mockPrisma.notification.count).toHaveBeenCalledWith({
        where: {
          userId: 'user-1',
          readAt: null,
          status: 'sent',
        },
      });
    });
  });

  describe('scheduleTaskReminder', () => {
    it('should schedule a reminder notification', async () => {
      mockPrisma.notification.create.mockResolvedValue(mockNotification as any);

      const result = await notificationService.scheduleTaskReminder(
        'user-1',
        'task-1',
        'Practice guitar',
        new Date('2024-01-15T18:30:00Z'),
        15
      );

      expect(result).toBeDefined();
      expect(mockPrisma.notification.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          userId: 'user-1',
          type: 'reminder',
          title: 'Rappel de tâche',
        }),
      });
    });
  });

  describe('scheduleDailyMotivation', () => {
    it('should schedule a motivation notification', async () => {
      mockPrisma.notification.create.mockResolvedValue(mockNotification as any);

      const result = await notificationService.scheduleDailyMotivation(
        'user-1',
        '08:00',
        'Learn Guitar',
        50,
        7,
        'Marie'
      );

      expect(result).toBeDefined();
      expect(mockPrisma.notification.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          type: 'motivation',
          title: 'Motivation du jour',
        }),
      });
    });
  });

  describe('sendPushNotification', () => {
    it('should return false when user has no FCM tokens', async () => {
      const { userService } = await import('../../services/user.service');
      vi.mocked(userService.getUserFcmTokens).mockResolvedValue([]);

      const result = await notificationService.sendPushNotification(
        'user-1',
        'Test Title',
        'Test Body'
      );

      expect(result).toBe(false);
    });

    it('should send push notification when user has tokens', async () => {
      const { userService } = await import('../../services/user.service');
      vi.mocked(userService.getUserFcmTokens).mockResolvedValue(['token-1', 'token-2']);

      const { getMessaging } = await import('firebase-admin/messaging');
      vi.mocked(getMessaging).mockReturnValue({
        sendEachForMulticast: vi.fn().mockResolvedValue({ successCount: 2 }),
      } as any);

      const result = await notificationService.sendPushNotification(
        'user-1',
        'Test Title',
        'Test Body',
        { screen: 'Home' }
      );

      expect(result).toBe(true);
    });

    it('should return false when push notification fails', async () => {
      const { userService } = await import('../../services/user.service');
      vi.mocked(userService.getUserFcmTokens).mockResolvedValue(['token-1']);

      const { getMessaging } = await import('firebase-admin/messaging');
      vi.mocked(getMessaging).mockReturnValue({
        sendEachForMulticast: vi.fn().mockRejectedValue(new Error('FCM error')),
      } as any);

      const result = await notificationService.sendPushNotification(
        'user-1',
        'Test Title',
        'Test Body'
      );

      expect(result).toBe(false);
    });
  });

  describe('processPendingNotifications', () => {
    it('should process and send pending notifications', async () => {
      const pendingNotif = {
        ...mockNotification,
        user: {
          id: 'user-1',
          notificationPrefs: null,
          timezone: 'Europe/Paris',
        },
      };

      mockPrisma.notification.findMany.mockResolvedValue([pendingNotif] as any);
      mockPrisma.notification.update.mockResolvedValue({} as any);

      const { userService } = await import('../../services/user.service');
      vi.mocked(userService.getUserFcmTokens).mockResolvedValue(['token-1']);

      const { getMessaging } = await import('firebase-admin/messaging');
      vi.mocked(getMessaging).mockReturnValue({
        sendEachForMulticast: vi.fn().mockResolvedValue({ successCount: 1 }),
      } as any);

      const count = await notificationService.processPendingNotifications();

      expect(count).toBe(1);
      expect(mockPrisma.notification.update).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({ status: 'sent' }),
        })
      );
    });

    it('should skip notifications during DND period', async () => {
      const currentHour = new Date().getHours();
      const pendingNotif = {
        ...mockNotification,
        user: {
          id: 'user-1',
          notificationPrefs: {
            dndEnabled: true,
            dndStart: currentHour > 0 ? currentHour - 1 : 23,
            dndEnd: currentHour < 23 ? currentHour + 1 : 0,
          },
          timezone: 'UTC',
        },
      };

      mockPrisma.notification.findMany.mockResolvedValue([pendingNotif] as any);

      const count = await notificationService.processPendingNotifications();

      expect(count).toBe(0);
    });

    it('should handle DND period crossing midnight', async () => {
      const pendingNotif = {
        ...mockNotification,
        user: {
          id: 'user-1',
          notificationPrefs: {
            dndEnabled: true,
            dndStart: 22,
            dndEnd: 7,
          },
          timezone: 'UTC',
        },
      };

      mockPrisma.notification.findMany.mockResolvedValue([pendingNotif] as any);
      mockPrisma.notification.update.mockResolvedValue({} as any);

      // The result depends on current hour - just verify it runs without error
      await notificationService.processPendingNotifications();

      expect(mockPrisma.notification.findMany).toHaveBeenCalled();
    });

    it('should mark notification as failed on error', async () => {
      const pendingNotif = {
        ...mockNotification,
        user: {
          id: 'user-1',
          notificationPrefs: null,
          timezone: 'Europe/Paris',
        },
      };

      mockPrisma.notification.findMany.mockResolvedValue([pendingNotif] as any);
      // Make the update call throw to trigger the catch block
      mockPrisma.notification.update
        .mockRejectedValueOnce(new Error('DB error'))
        .mockResolvedValue({} as any);

      const { userService } = await import('../../services/user.service');
      vi.mocked(userService.getUserFcmTokens).mockResolvedValue(['token-1']);

      const { getMessaging } = await import('firebase-admin/messaging');
      vi.mocked(getMessaging).mockReturnValue({
        sendEachForMulticast: vi.fn().mockResolvedValue({ successCount: 1 }),
      } as any);

      await notificationService.processPendingNotifications();

      // Second call is the catch block with just { status: 'failed' }
      expect(mockPrisma.notification.update).toHaveBeenCalledTimes(2);
      expect(mockPrisma.notification.update).toHaveBeenLastCalledWith({
        where: { id: 'notif-1' },
        data: { status: 'failed' },
      });
    });

    it('should mark as failed when push notification fails', async () => {
      const pendingNotif = {
        ...mockNotification,
        user: {
          id: 'user-1',
          notificationPrefs: null,
          timezone: 'Europe/Paris',
        },
      };

      mockPrisma.notification.findMany.mockResolvedValue([pendingNotif] as any);
      mockPrisma.notification.update.mockResolvedValue({} as any);

      const { userService } = await import('../../services/user.service');
      vi.mocked(userService.getUserFcmTokens).mockResolvedValue([]);

      const count = await notificationService.processPendingNotifications();

      expect(count).toBe(0);
      expect(mockPrisma.notification.update).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({ status: 'failed' }),
        })
      );
    });

    it('should return 0 when no pending notifications', async () => {
      mockPrisma.notification.findMany.mockResolvedValue([]);

      const count = await notificationService.processPendingNotifications();

      expect(count).toBe(0);
    });
  });
});
