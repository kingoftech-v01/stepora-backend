import { prisma } from '../config/database';
import { Notification, Prisma } from '@prisma/client';
import { getMessaging } from 'firebase-admin/messaging';
import { userService } from './user.service';
import { aiService } from './ai.service';

export type NotificationType = 'reminder' | 'motivation' | 'progress' | 'achievement' | 'check_in';

export interface CreateNotificationData {
  type: NotificationType;
  title: string;
  body: string;
  scheduledFor: Date;
  data?: {
    screen?: string;
    params?: Record<string, string>;
  };
}

export interface NotificationPrefs {
  reminders: boolean;
  reminderMinutesBefore: number;
  motivation: boolean;
  motivationTime: string;
  weeklyReport: boolean;
  weeklyReportDay: number;
  dndEnabled: boolean;
  dndStart: number;
  dndEnd: number;
}

export class NotificationService {
  async findById(id: string, userId: string): Promise<Notification | null> {
    return prisma.notification.findFirst({
      where: { id, userId },
    });
  }

  async findAllByUser(
    userId: string,
    options?: {
      status?: string;
      type?: NotificationType;
      limit?: number;
      offset?: number;
    }
  ): Promise<{ notifications: Notification[]; total: number }> {
    const where: Prisma.NotificationWhereInput = { userId };

    if (options?.status) where.status = options.status;
    if (options?.type) where.type = options.type;

    const [notifications, total] = await Promise.all([
      prisma.notification.findMany({
        where,
        orderBy: { scheduledFor: 'desc' },
        take: options?.limit || 50,
        skip: options?.offset || 0,
      }),
      prisma.notification.count({ where }),
    ]);

    return { notifications, total };
  }

  async create(userId: string, data: CreateNotificationData): Promise<Notification> {
    return prisma.notification.create({
      data: {
        userId,
        type: data.type,
        title: data.title,
        body: data.body,
        scheduledFor: data.scheduledFor,
        data: data.data as Prisma.InputJsonValue,
      },
    });
  }

  async markAsRead(id: string, userId: string): Promise<Notification> {
    const notification = await prisma.notification.findFirst({
      where: { id, userId },
    });

    if (!notification) {
      throw new Error('Notification not found');
    }

    return prisma.notification.update({
      where: { id },
      data: { readAt: new Date() },
    });
  }

  async markAllAsRead(userId: string): Promise<number> {
    const result = await prisma.notification.updateMany({
      where: {
        userId,
        readAt: null,
      },
      data: { readAt: new Date() },
    });

    return result.count;
  }

  async delete(id: string, userId: string): Promise<void> {
    const notification = await prisma.notification.findFirst({
      where: { id, userId },
    });

    if (!notification) {
      throw new Error('Notification not found');
    }

    await prisma.notification.delete({
      where: { id },
    });
  }

  async getUnreadCount(userId: string): Promise<number> {
    return prisma.notification.count({
      where: {
        userId,
        readAt: null,
        status: 'sent',
      },
    });
  }

  async sendPushNotification(
    userId: string,
    title: string,
    body: string,
    data?: Record<string, string>
  ): Promise<boolean> {
    try {
      const tokens = await userService.getUserFcmTokens(userId);

      if (tokens.length === 0) {
        return false;
      }

      const messaging = getMessaging();

      await messaging.sendEachForMulticast({
        tokens,
        notification: {
          title,
          body,
        },
        data,
        android: {
          priority: 'high',
          notification: {
            channelId: 'dreamplanner_default',
            priority: 'high',
          },
        },
        apns: {
          payload: {
            aps: {
              alert: {
                title,
                body,
              },
              sound: 'default',
              badge: 1,
            },
          },
        },
      });

      return true;
    } catch (error) {
      console.error('Error sending push notification:', error);
      return false;
    }
  }

  async processPendingNotifications(): Promise<number> {
    const now = new Date();

    const pendingNotifications = await prisma.notification.findMany({
      where: {
        status: 'pending',
        scheduledFor: { lte: now },
      },
      include: {
        user: {
          select: {
            id: true,
            notificationPrefs: true,
            timezone: true,
          },
        },
      },
    });

    let sentCount = 0;

    for (const notification of pendingNotifications) {
      try {
        // Check DND
        const prefs = notification.user.notificationPrefs as NotificationPrefs | null;
        if (prefs?.dndEnabled) {
          const userHour = this.getUserLocalHour(notification.user.timezone);
          if (this.isInDndPeriod(userHour, prefs.dndStart, prefs.dndEnd)) {
            continue;
          }
        }

        // Send push notification
        const sent = await this.sendPushNotification(
          notification.userId,
          notification.title,
          notification.body,
          notification.data as Record<string, string> | undefined
        );

        await prisma.notification.update({
          where: { id: notification.id },
          data: {
            status: sent ? 'sent' : 'failed',
            sentAt: sent ? now : null,
          },
        });

        if (sent) sentCount++;
      } catch (error) {
        console.error(`Error processing notification ${notification.id}:`, error);

        await prisma.notification.update({
          where: { id: notification.id },
          data: { status: 'failed' },
        });
      }
    }

    return sentCount;
  }

  async scheduleTaskReminder(
    userId: string,
    taskId: string,
    taskTitle: string,
    scheduledDate: Date,
    minutesBefore: number = 15
  ): Promise<Notification> {
    const reminderTime = new Date(scheduledDate);
    reminderTime.setMinutes(reminderTime.getMinutes() - minutesBefore);

    return this.create(userId, {
      type: 'reminder',
      title: 'Rappel de tâche',
      body: `"${taskTitle}" dans ${minutesBefore} minutes`,
      scheduledFor: reminderTime,
      data: {
        screen: 'TaskDetail',
        params: { taskId },
      },
    });
  }

  async scheduleDailyMotivation(
    userId: string,
    time: string,
    goalTitle: string,
    progress: number,
    streak: number,
    userName: string
  ): Promise<Notification> {
    // Parse time (HH:mm)
    const [hours, minutes] = time.split(':').map(Number);
    const scheduledFor = new Date();
    scheduledFor.setHours(hours, minutes, 0, 0);

    // If time has passed today, schedule for tomorrow
    if (scheduledFor <= new Date()) {
      scheduledFor.setDate(scheduledFor.getDate() + 1);
    }

    // Generate motivational message
    const message = await aiService.generateMotivationalMessage(
      progress,
      streak,
      goalTitle,
      userName
    );

    return this.create(userId, {
      type: 'motivation',
      title: 'Motivation du jour',
      body: message,
      scheduledFor,
    });
  }

  private getUserLocalHour(timezone: string): number {
    try {
      const now = new Date();
      const userTime = new Intl.DateTimeFormat('en-US', {
        timeZone: timezone,
        hour: 'numeric',
        hour12: false,
      }).format(now);
      return parseInt(userTime, 10);
    } catch {
      return new Date().getHours();
    }
  }

  private isInDndPeriod(currentHour: number, dndStart: number, dndEnd: number): boolean {
    if (dndStart < dndEnd) {
      return currentHour >= dndStart && currentHour < dndEnd;
    } else {
      // DND crosses midnight (e.g., 22:00 - 07:00)
      return currentHour >= dndStart || currentHour < dndEnd;
    }
  }
}

export const notificationService = new NotificationService();
