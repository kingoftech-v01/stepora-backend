import admin from 'firebase-admin';
import { prisma } from '../utils/prisma';
import { logger } from '../config/logger';

class NotificationService {
  async sendNotification(
    userId: string,
    notification: {
      title: string;
      body: string;
      data?: Record<string, string>;
      type: string;
    }
  ) {
    try {
      // Get user's FCM tokens
      const fcmTokens = await prisma.fcmToken.findMany({
        where: { userId },
        select: { token: true },
      });

      if (fcmTokens.length === 0) {
        logger.warn('No FCM tokens found for user:', { userId });
        return;
      }

      // Create notification record
      const notificationRecord = await prisma.notification.create({
        data: {
          userId,
          type: notification.type,
          title: notification.title,
          body: notification.body,
          data: notification.data || {},
          scheduledFor: new Date(),
        },
      });

      // Send to all tokens
      const tokens = fcmTokens.map((t) => t.token);
      const message = {
        notification: {
          title: notification.title,
          body: notification.body,
        },
        data: {
          ...(notification.data || {}),
          notificationId: notificationRecord.id,
        },
        tokens,
      };

      const response = await admin.messaging().sendEachForMulticast(message);

      // Update notification status
      await prisma.notification.update({
        where: { id: notificationRecord.id },
        data: {
          status: response.successCount > 0 ? 'sent' : 'failed',
          sentAt: response.successCount > 0 ? new Date() : null,
        },
      });

      logger.info('Notification sent:', {
        userId,
        successCount: response.successCount,
        failureCount: response.failureCount,
      });

      // Clean up invalid tokens
      if (response.responses) {
        const failedTokens: string[] = [];
        response.responses.forEach((resp, idx) => {
          if (!resp.success && resp.error) {
            if (
              resp.error.code === 'messaging/invalid-registration-token' ||
              resp.error.code === 'messaging/registration-token-not-registered'
            ) {
              failedTokens.push(tokens[idx]);
            }
          }
        });

        if (failedTokens.length > 0) {
          await prisma.fcmToken.deleteMany({
            where: {
              token: { in: failedTokens },
            },
          });
          logger.info('Removed invalid FCM tokens:', { count: failedTokens.length });
        }
      }

      return response;
    } catch (error) {
      logger.error('Failed to send notification:', { error, userId });
      throw error;
    }
  }

  async scheduleNotification(
    userId: string,
    scheduledFor: Date,
    notification: {
      title: string;
      body: string;
      type: string;
      data?: Record<string, string>;
    }
  ) {
    const notificationRecord = await prisma.notification.create({
      data: {
        userId,
        type: notification.type,
        title: notification.title,
        body: notification.body,
        data: notification.data || {},
        scheduledFor,
        status: 'pending',
      },
    });

    logger.info('Notification scheduled:', {
      userId,
      notificationId: notificationRecord.id,
      scheduledFor,
    });

    return notificationRecord;
  }

  async scheduleReminders(userId: string) {
    // Get upcoming tasks for the next 7 days
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(0, 0, 0, 0);

    const weekEnd = new Date(tomorrow);
    weekEnd.setDate(weekEnd.getDate() + 7);

    const tasks = await prisma.task.findMany({
      where: {
        scheduledDate: {
          gte: tomorrow,
          lte: weekEnd,
        },
        status: 'pending',
        goal: {
          dream: {
            userId,
            status: 'active',
          },
        },
      },
      include: {
        goal: {
          select: {
            title: true,
            dream: { select: { title: true } },
          },
        },
      },
    });

    // Get user's notification preferences
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { notificationPrefs: true },
    });

    const prefs = user?.notificationPrefs as any;
    if (!prefs?.reminders) {
      return; // Reminders disabled
    }

    // Schedule reminders for each task (1 hour before scheduled time)
    for (const task of tasks) {
      if (!task.scheduledDate || !task.scheduledTime) continue;

      const [hours, minutes] = task.scheduledTime.split(':').map(Number);
      const reminderTime = new Date(task.scheduledDate);
      reminderTime.setHours(hours - 1, minutes, 0, 0);

      // Don't schedule if in the past
      if (reminderTime < new Date()) continue;

      await this.scheduleNotification(userId, reminderTime, {
        title: `Upcoming: ${task.title}`,
        body: `Your task "${task.title}" starts in 1 hour`,
        type: 'reminder',
        data: {
          taskId: task.id,
          goalId: task.goalId,
        },
      });
    }

    logger.info('Reminders scheduled:', { userId, count: tasks.length });
  }
}

export const notificationService = new NotificationService();
