import { prisma } from '../utils/prisma';
import { notificationService } from './notification.service';
import { socialService } from './social.service';
import { logger } from '../config/logger';

interface BuddyMatchCriteria {
  userId: string;
  dreamCategory?: string;
  timeframe?: number;
  timezone?: string;
  language?: string;
}

interface BuddyMatch {
  userId: string;
  username: string;
  avatar?: string;
  matchScore: number;
  sharedCategory?: string;
  influenceScore: number;
}

class BuddyService {
  async findBuddyMatch(criteria: BuddyMatchCriteria): Promise<BuddyMatch | null> {
    try {
      const { userId, dreamCategory, timeframe, timezone, language } = criteria;

      // Get user's current buddy (if any)
      const existingBuddy = await prisma.dreamBuddy.findFirst({
        where: {
          OR: [{ user1Id: userId }, { user2Id: userId }],
          status: 'active',
        },
      });

      if (existingBuddy) {
        throw new Error('User already has an active buddy');
      }

      // Get user's active dreams for matching
      const userDreams = await prisma.dream.findMany({
        where: { userId, status: 'active' },
        select: { category: true, targetDate: true },
      });

      if (userDreams.length === 0) {
        return null; // Can't match without dreams
      }

      const userCategories = [...new Set(userDreams.map((d) => d.category))];

      // Find potential matches
      const potentialMatches = await prisma.user.findMany({
        where: {
          id: { not: userId },
          dreams: {
            some: {
              status: 'active',
              category: dreamCategory ? dreamCategory : { in: userCategories },
            },
          },
        },
        select: {
          id: true,
          username: true,
          avatar: true,
          timezone: true,
          preferredLanguage: true,
          profile: {
            select: {
              influenceScore: true,
            },
          },
          dreams: {
            where: { status: 'active' },
            select: {
              category: true,
              targetDate: true,
              goals: {
                select: {
                  tasks: {
                    where: { status: 'completed' },
                    select: { id: true },
                  },
                },
              },
            },
          },
        },
        take: 50,
      });

      // Filter out users who already have a buddy
      const matchesWithoutBuddy = await Promise.all(
        potentialMatches.map(async (match) => {
          const hasBuddy = await prisma.dreamBuddy.findFirst({
            where: {
              OR: [{ user1Id: match.id }, { user2Id: match.id }],
              status: 'active',
            },
          });
          return hasBuddy ? null : match;
        })
      );

      const filteredMatches = matchesWithoutBuddy.filter((m) => m !== null);

      if (filteredMatches.length === 0) {
        return null;
      }

      // Calculate match scores
      const scoredMatches = filteredMatches.map((match: any) => {
        let score = 0;

        // Category match (40%)
        const matchCategories = [...new Set(match.dreams.map((d: any) => d.category))];
        const categoryOverlap = userCategories.filter((c) => matchCategories.includes(c));
        score += (categoryOverlap.length / userCategories.length) * 40;

        // Timeframe similarity (20%)
        if (timeframe && match.dreams.length > 0) {
          const matchTimeframes = match.dreams
            .filter((d: any) => d.targetDate)
            .map((d: any) => {
              const days = Math.ceil(
                (new Date(d.targetDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
              );
              return days;
            });

          if (matchTimeframes.length > 0) {
            const avgMatchTimeframe =
              matchTimeframes.reduce((a: number, b: number) => a + b, 0) / matchTimeframes.length;
            const timeframeDiff = Math.abs(timeframe - avgMatchTimeframe);
            const timeframeSimilarity = Math.max(0, 1 - timeframeDiff / 365);
            score += timeframeSimilarity * 20;
          }
        }

        // Timezone match (15%)
        if (timezone && match.timezone === timezone) {
          score += 15;
        }

        // Language match (15%)
        if (language && match.preferredLanguage === language) {
          score += 15;
        }

        // Activity level match (10%) - similar completion rate
        const userCompletedTasks = userDreams.reduce(
          (sum, d: any) =>
            sum +
            d.goals.reduce(
              (gSum: number, g: any) => gSum + g.tasks.filter((t: any) => t.status === 'completed').length,
              0
            ),
          0
        );

        const matchCompletedTasks = match.dreams.reduce(
          (sum: number, d: any) =>
            sum +
            d.goals.reduce((gSum: number, g: any) => gSum + g.tasks.length, 0),
          0
        );

        const activityDiff = Math.abs(userCompletedTasks - matchCompletedTasks);
        const activitySimilarity = Math.max(0, 1 - activityDiff / 100);
        score += activitySimilarity * 10;

        return {
          userId: match.id,
          username: match.username || 'Anonymous',
          avatar: match.avatar,
          matchScore: Math.round(score),
          sharedCategory: categoryOverlap[0],
          influenceScore: match.profile?.influenceScore || 0,
        };
      });

      // Sort by match score
      scoredMatches.sort((a, b) => b.matchScore - a.matchScore);

      return scoredMatches[0] || null;
    } catch (error) {
      logger.error('Failed to find buddy match:', { error, userId: criteria.userId });
      throw error;
    }
  }

  async createBuddyPairing(user1Id: string, user2Id: string): Promise<void> {
    try {
      // Create buddy relationship
      const buddy = await prisma.dreamBuddy.create({
        data: {
          user1Id,
          user2Id,
          status: 'active',
          matchedAt: new Date(),
        },
      });

      // Send notifications to both users
      await notificationService.sendNotification(user1Id, {
        title: 'Nouveau Dream Buddy!',
        body: 'Tu as été jumelé avec un partenaire de rêve !',
        type: 'buddy_matched',
        data: {
          buddyId: buddy.id,
          partnerId: user2Id,
        },
      });

      await notificationService.sendNotification(user2Id, {
        title: 'Nouveau Dream Buddy!',
        body: 'Tu as été jumelé avec un partenaire de rêve !',
        type: 'buddy_matched',
        data: {
          buddyId: buddy.id,
          partnerId: user1Id,
        },
      });

      // Create activity
      await socialService.createActivity(user1Id, 'buddy_matched', {
        partnerId: user2Id,
      });

      logger.info('Buddy pairing created:', { user1Id, user2Id });
    } catch (error) {
      logger.error('Failed to create buddy pairing:', { error, user1Id, user2Id });
      throw error;
    }
  }

  async getCurrentBuddy(userId: string) {
    const buddy = await prisma.dreamBuddy.findFirst({
      where: {
        OR: [{ user1Id: userId }, { user2Id: userId }],
        status: 'active',
      },
      include: {
        user1: {
          select: {
            id: true,
            username: true,
            avatar: true,
            profile: {
              select: {
                influenceScore: true,
                currentLevel: true,
                currentStreak: true,
                title: true,
              },
            },
          },
        },
        user2: {
          select: {
            id: true,
            username: true,
            avatar: true,
            profile: {
              select: {
                influenceScore: true,
                currentLevel: true,
                currentStreak: true,
                title: true,
              },
            },
          },
        },
      },
    });

    if (!buddy) return null;

    const partner = buddy.user1Id === userId ? buddy.user2 : buddy.user1;

    // Get partner's recent activity
    const recentTasks = await prisma.task.count({
      where: {
        goal: { dream: { userId: partner.id } },
        status: 'completed',
        completedAt: {
          gte: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000), // Last 7 days
        },
      },
    });

    return {
      id: buddy.id,
      partner: {
        id: partner.id,
        username: partner.username || 'Anonymous',
        avatar: partner.avatar,
        influenceScore: partner.profile?.influenceScore || 0,
        currentLevel: partner.profile?.currentLevel || 1,
        currentStreak: partner.profile?.currentStreak || 0,
        title: partner.profile?.title || 'Rêveur',
      },
      matchedAt: buddy.matchedAt,
      recentActivity: recentTasks,
    };
  }

  async endBuddyPairing(userId: string, buddyId: string): Promise<void> {
    try {
      const buddy = await prisma.dreamBuddy.findUnique({
        where: { id: buddyId },
      });

      if (!buddy) {
        throw new Error('Buddy pairing not found');
      }

      if (buddy.user1Id !== userId && buddy.user2Id !== userId) {
        throw new Error('Not authorized');
      }

      await prisma.dreamBuddy.update({
        where: { id: buddyId },
        data: {
          status: 'ended',
          endedAt: new Date(),
        },
      });

      logger.info('Buddy pairing ended:', { userId, buddyId });
    } catch (error) {
      logger.error('Failed to end buddy pairing:', { error, userId, buddyId });
      throw error;
    }
  }

  async encourageBuddy(userId: string, buddyId: string, message?: string): Promise<void> {
    try {
      const buddy = await prisma.dreamBuddy.findUnique({
        where: { id: buddyId },
      });

      if (!buddy) {
        throw new Error('Buddy pairing not found');
      }

      if (buddy.user1Id !== userId && buddy.user2Id !== userId) {
        throw new Error('Not authorized');
      }

      const partnerId = buddy.user1Id === userId ? buddy.user2Id : buddy.user1Id;

      // Send encouragement notification
      await notificationService.sendNotification(partnerId, {
        title: 'Encouragement de ton Buddy!',
        body: message || 'Ton buddy t\'encourage ! Continue comme ça ! 💪',
        type: 'buddy_encouragement',
        data: {
          buddyId,
          fromUserId: userId,
        },
      });

      // Award XP to the encourager
      // This would be called from the gamification service
      // await gamificationService.awardXP(userId, 'buddy_help', 15);

      logger.info('Buddy encouraged:', { userId, partnerId });
    } catch (error) {
      logger.error('Failed to encourage buddy:', { error, userId, buddyId });
      throw error;
    }
  }

  async getBuddyProgress(userId: string, buddyId: string) {
    try {
      const buddy = await prisma.dreamBuddy.findUnique({
        where: { id: buddyId },
      });

      if (!buddy) {
        throw new Error('Buddy pairing not found');
      }

      if (buddy.user1Id !== userId && buddy.user2Id !== userId) {
        throw new Error('Not authorized');
      }

      const partnerId = buddy.user1Id === userId ? buddy.user2Id : buddy.user1Id;

      // Get both users' stats
      const [userStats, partnerStats] = await Promise.all([
        this.getUserBuddyStats(userId),
        this.getUserBuddyStats(partnerId),
      ]);

      return {
        user: userStats,
        partner: partnerStats,
      };
    } catch (error) {
      logger.error('Failed to get buddy progress:', { error, userId, buddyId });
      throw error;
    }
  }

  private async getUserBuddyStats(userId: string) {
    const profile = await prisma.userProfile.findUnique({
      where: { userId },
    });

    const tasksThisWeek = await prisma.task.count({
      where: {
        goal: { dream: { userId } },
        status: 'completed',
        completedAt: {
          gte: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
        },
      },
    });

    const activeDreams = await prisma.dream.count({
      where: { userId, status: 'active' },
    });

    return {
      currentStreak: profile?.currentStreak || 0,
      tasksThisWeek,
      activeDreams,
      influenceScore: profile?.influenceScore || 0,
    };
  }
}

export const buddyService = new BuddyService();
