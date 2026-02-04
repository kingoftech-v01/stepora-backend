import { prisma } from '../utils/prisma';
import { notificationService } from './notification.service';
import { logger } from '../config/logger';

interface Milestone {
  days: number;
  badge: string;
  message: string;
  xpReward: number;
}

const MILESTONES: Milestone[] = [
  { days: 1, badge: 'Premier Pas', message: 'Le plus dur est fait!', xpReward: 50 },
  { days: 3, badge: 'Momentum', message: 'Tu construis une habitude!', xpReward: 100 },
  { days: 7, badge: 'Semaine Parfaite', message: 'Une semaine complète!', xpReward: 200 },
  { days: 14, badge: 'Déterminé', message: '2 semaines, c\'est sérieux!', xpReward: 400 },
  { days: 30, badge: 'Unstoppable', message: 'Un mois! Tu es incroyable!', xpReward: 1000 },
  { days: 60, badge: 'Habitude Ancrée', message: 'C\'est devenu naturel!', xpReward: 2000 },
  { days: 100, badge: 'Centurion', message: '100 jours légendaires!', xpReward: 5000 },
  { days: 365, badge: 'Année de Rêves', message: 'Une année entière! Légende!', xpReward: 20000 },
];

class AchievementService {
  async checkForMilestones(userId: string): Promise<Milestone | null> {
    try {
      // Get user's current streak
      const user = await prisma.user.findUnique({
        where: { id: userId },
        select: { id: true },
      });

      if (!user) return null;

      // Calculate current streak based on completed tasks
      const streak = await this.calculateStreak(userId);

      // Check if streak matches any milestone
      const milestone = MILESTONES.find((m) => m.days === streak);

      if (milestone) {
        // Send celebration notification
        await notificationService.sendNotification(userId, {
          title: `🎉 ${milestone.badge}!`,
          body: milestone.message,
          type: 'achievement',
          data: {
            badge: milestone.badge,
            xpReward: milestone.xpReward.toString(),
          },
        });

        logger.info('Milestone achieved:', { userId, milestone: milestone.badge, streak });

        return milestone;
      }

      return null;
    } catch (error) {
      logger.error('Failed to check milestones:', { error, userId });
      return null;
    }
  }

  async calculateStreak(userId: string): Promise<number> {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    let currentStreak = 0;
    let checkDate = new Date(today);

    // Go backwards day by day
    for (let i = 0; i < 365; i++) {
      const dayStart = new Date(checkDate);
      const dayEnd = new Date(checkDate);
      dayEnd.setHours(23, 59, 59, 999);

      const tasksCompleted = await prisma.task.count({
        where: {
          goal: {
            dream: { userId },
          },
          status: 'completed',
          completedAt: {
            gte: dayStart,
            lte: dayEnd,
          },
        },
      });

      if (tasksCompleted > 0) {
        currentStreak++;
        checkDate.setDate(checkDate.getDate() - 1);
      } else {
        // Streak broken
        break;
      }
    }

    return currentStreak;
  }

  async generateSocialProof(userId: string): Promise<string> {
    try {
      // Get total users
      const totalUsers = await prisma.user.count();

      // Get user's total completed tasks
      const userCompletedTasks = await prisma.task.count({
        where: {
          goal: {
            dream: { userId },
          },
          status: 'completed',
        },
      });

      // Get users with fewer completed tasks
      const usersWithFewerTasks = await prisma.$queryRaw<
        Array<{ count: bigint }>
      >`
        SELECT COUNT(DISTINCT u.id) as count
        FROM "users" u
        LEFT JOIN "dreams" d ON d."user_id" = u.id
        LEFT JOIN "goals" g ON g."dream_id" = d.id
        LEFT JOIN "tasks" t ON t."goal_id" = g.id AND t.status = 'completed'
        GROUP BY u.id
        HAVING COUNT(t.id) < ${userCompletedTasks}
      `;

      const fewerCount = Number(usersWithFewerTasks[0]?.count || 0);
      const percentile = Math.round((fewerCount / totalUsers) * 100);

      if (percentile >= 80) {
        return `Tu fais mieux que ${percentile}% des utilisateurs ! 🔥`;
      } else if (percentile >= 50) {
        return `Tu es dans le top ${100 - percentile}% ! Continue ! 💪`;
      } else {
        return `Tu es en bonne voie ! Continue comme ça ! ⭐`;
      }
    } catch (error) {
      logger.error('Failed to generate social proof:', { error, userId });
      return 'Super travail ! Continue ! 🌟';
    }
  }

  async createShareTemplate(userId: string, achievement: string): Promise<string> {
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { displayName: true },
    });

    const streak = await this.calculateStreak(userId);

    return `🎉 ${achievement}!

${user?.displayName || 'Je'} suis sur une série de ${streak} jours avec DreamPlanner!

Transforme tes rêves en réalité: https://dreamplanner.app

#DreamPlanner #Goals #Motivation #Streak`;
  }
}

export const achievementService = new AchievementService();
