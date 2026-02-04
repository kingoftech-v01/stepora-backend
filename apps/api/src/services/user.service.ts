import { prisma } from '../config/database';
import { User, Prisma } from '@prisma/client';

export interface CreateUserData {
  firebaseUid: string;
  email: string;
  displayName?: string;
  avatarUrl?: string;
  timezone?: string;
}

export interface UpdateUserData {
  displayName?: string;
  avatarUrl?: string;
  timezone?: string;
  workSchedule?: {
    workDays: number[];
    startTime: string;
    endTime: string;
  };
  notificationPrefs?: {
    reminders: boolean;
    reminderMinutesBefore: number;
    motivation: boolean;
    motivationTime: string;
    weeklyReport: boolean;
    weeklyReportDay: number;
    dndEnabled: boolean;
    dndStart: number;
    dndEnd: number;
  };
  appPrefs?: {
    theme: 'light' | 'dark' | 'system';
    language: 'fr' | 'en';
  };
}

export class UserService {
  async findById(id: string): Promise<User | null> {
    return prisma.user.findUnique({
      where: { id },
    });
  }

  async findByFirebaseUid(firebaseUid: string): Promise<User | null> {
    return prisma.user.findUnique({
      where: { firebaseUid },
    });
  }

  async findByEmail(email: string): Promise<User | null> {
    return prisma.user.findUnique({
      where: { email },
    });
  }

  async create(data: CreateUserData): Promise<User> {
    return prisma.user.create({
      data: {
        firebaseUid: data.firebaseUid,
        email: data.email,
        displayName: data.displayName,
        avatarUrl: data.avatarUrl,
        timezone: data.timezone || 'Europe/Paris',
      },
    });
  }

  async update(id: string, data: UpdateUserData): Promise<User> {
    const updateData: Prisma.UserUpdateInput = {};

    if (data.displayName !== undefined) updateData.displayName = data.displayName;
    if (data.avatarUrl !== undefined) updateData.avatarUrl = data.avatarUrl;
    if (data.timezone !== undefined) updateData.timezone = data.timezone;
    if (data.workSchedule !== undefined) updateData.workSchedule = data.workSchedule;
    if (data.notificationPrefs !== undefined) updateData.notificationPrefs = data.notificationPrefs;
    if (data.appPrefs !== undefined) updateData.appPrefs = data.appPrefs;

    return prisma.user.update({
      where: { id },
      data: updateData,
    });
  }

  async updateSubscription(
    id: string,
    subscription: 'free' | 'premium' | 'pro',
    endsAt?: Date
  ): Promise<User> {
    return prisma.user.update({
      where: { id },
      data: {
        subscription,
        subscriptionEnds: endsAt,
      },
    });
  }

  async delete(id: string): Promise<void> {
    await prisma.user.delete({
      where: { id },
    });
  }

  async registerFcmToken(
    userId: string,
    token: string,
    platform: 'ios' | 'android'
  ): Promise<void> {
    await prisma.fcmToken.upsert({
      where: { token },
      create: {
        userId,
        token,
        platform,
      },
      update: {
        userId,
        platform,
        updatedAt: new Date(),
      },
    });
  }

  async removeFcmToken(token: string): Promise<void> {
    await prisma.fcmToken.deleteMany({
      where: { token },
    });
  }

  async getUserFcmTokens(userId: string): Promise<string[]> {
    const tokens = await prisma.fcmToken.findMany({
      where: { userId },
      select: { token: true },
    });
    return tokens.map((t) => t.token);
  }

  async getStatistics(userId: string): Promise<{
    totalDreams: number;
    activeDreams: number;
    completedDreams: number;
    totalTasks: number;
    completedTasks: number;
    currentStreak: number;
    totalXp: number;
    level: number;
  }> {
    const [dreams, tasks, completedTasksByDate] = await Promise.all([
      prisma.dream.groupBy({
        by: ['status'],
        where: { userId },
        _count: true,
      }),
      prisma.task.findMany({
        where: {
          goal: {
            dream: { userId },
          },
        },
        select: {
          status: true,
          completedAt: true,
        },
      }),
      prisma.task.findMany({
        where: {
          goal: {
            dream: { userId },
          },
          status: 'completed',
          completedAt: { not: null },
        },
        select: { completedAt: true },
        orderBy: { completedAt: 'desc' },
      }),
    ]);

    const dreamsCount = dreams.reduce(
      (acc, d) => {
        acc[d.status] = d._count;
        return acc;
      },
      {} as Record<string, number>
    );

    const completedTasks = tasks.filter((t) => t.status === 'completed').length;

    // Calculate streak
    let currentStreak = 0;
    if (completedTasksByDate.length > 0) {
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      const dates = completedTasksByDate
        .map((t) => {
          const d = new Date(t.completedAt!);
          d.setHours(0, 0, 0, 0);
          return d.getTime();
        })
        .filter((v, i, a) => a.indexOf(v) === i)
        .sort((a, b) => b - a);

      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);

      if (dates[0] === today.getTime() || dates[0] === yesterday.getTime()) {
        currentStreak = 1;
        let checkDate = new Date(dates[0]);

        for (let i = 1; i < dates.length; i++) {
          checkDate.setDate(checkDate.getDate() - 1);
          if (dates[i] === checkDate.getTime()) {
            currentStreak++;
          } else {
            break;
          }
        }
      }
    }

    // Calculate XP and level (10 XP per completed task)
    const totalXp = completedTasks * 10;
    const level = Math.floor(totalXp / 100) + 1;

    return {
      totalDreams: Object.values(dreamsCount).reduce((a, b) => a + b, 0),
      activeDreams: dreamsCount['active'] || 0,
      completedDreams: dreamsCount['completed'] || 0,
      totalTasks: tasks.length,
      completedTasks,
      currentStreak,
      totalXp,
      level,
    };
  }
}

export const userService = new UserService();
