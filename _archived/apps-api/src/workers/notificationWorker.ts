import Bull from 'bull';
import { redis } from '../config/redis';
import { prisma } from '../utils/prisma';
import { notificationService } from '../services/notification.service';
import { logger } from '../config/logger';

const notificationQueue = new Bull('notifications', {
  redis: {
    host: redis.options.host || 'localhost',
    port: redis.options.port || 6379,
  },
});

// Process notification jobs
notificationQueue.process(async (job) => {
  const { notificationId } = job.data;

  try {
    const notification = await prisma.notification.findUnique({
      where: { id: notificationId },
    });

    if (!notification) {
      logger.warn('Notification not found:', { notificationId });
      return;
    }

    if (notification.status !== 'pending') {
      logger.info('Notification already processed:', { notificationId, status: notification.status });
      return;
    }

    await notificationService.sendNotification(notification.userId, {
      title: notification.title,
      body: notification.body,
      type: notification.type,
      data: notification.data as Record<string, string>,
    });

    logger.info('Notification processed:', { notificationId });
  } catch (error) {
    logger.error('Failed to process notification:', { error, notificationId });
    throw error;
  }
});

// Schedule pending notifications (run every minute)
async function schedulePendingNotifications() {
  try {
    const now = new Date();
    const nextMinute = new Date(now.getTime() + 60000);

    const pendingNotifications = await prisma.notification.findMany({
      where: {
        status: 'pending',
        scheduledFor: {
          lte: nextMinute,
          gte: now,
        },
      },
    });

    for (const notification of pendingNotifications) {
      const delay = notification.scheduledFor.getTime() - now.getTime();

      await notificationQueue.add(
        { notificationId: notification.id },
        {
          delay: Math.max(0, delay),
          attempts: 3,
          backoff: {
            type: 'exponential',
            delay: 2000,
          },
        }
      );
    }

    if (pendingNotifications.length > 0) {
      logger.info('Scheduled pending notifications:', { count: pendingNotifications.length });
    }
  } catch (error) {
    logger.error('Failed to schedule pending notifications:', { error });
  }
}

export function initializeNotificationWorker() {
  // Schedule pending notifications every minute
  setInterval(schedulePendingNotifications, 60000);

  // Run immediately on startup
  schedulePendingNotifications();

  logger.info('✅ Notification worker initialized');
}

export { notificationQueue };
