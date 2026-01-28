import { prisma } from '../utils/prisma';
import { logger } from '../config/logger';

const XP_REWARDS = {
  taskCompleted: 10,
  dailyGoalMet: 25,
  dreamMilestone25: 100,
  dreamMilestone50: 200,
  dreamMilestone75: 300,
  dreamMilestone100: 500,
  streakDay: 5, // multiplied by streak length
  buddyHelp: 15,
  circleChallenge: 50,
  publicCommitmentFulfilled: 250,
  microStartCompleted: 5,
};

const MULTIPLIERS = {
  weekendWarrior: 1.5,
  earlyBird: 1.3,
  nightOwl: 1.3,
  perfectWeek: 2.0,
  comeback: 1.2,
};

const RANK_TIERS = [
  { minInfluence: 0, maxInfluence: 99, title: 'Rêveur', icon: '🌱' },
  { minInfluence: 100, maxInfluence: 499, title: 'Aspirant', icon: '🌿' },
  { minInfluence: 500, maxInfluence: 1499, title: 'Planificateur', icon: '📋' },
  { minInfluence: 1500, maxInfluence: 3499, title: 'Achiever', icon: '🎯' },
  { minInfluence: 3500, maxInfluence: 7499, title: 'Dream Warrior', icon: '⚔️' },
  { minInfluence: 7500, maxInfluence: 14999, title: 'Inspirateur', icon: '✨' },
  { minInfluence: 15000, maxInfluence: 29999, title: 'Champion', icon: '🏆' },
  { minInfluence: 30000, maxInfluence: Infinity, title: 'Légende', icon: '👑' },
];

class GamificationService {
  async awardXP(
    userId: string,
    source: string,
    amount: number,
    sourceId?: string,
    attributeImpact?: Record<string, number>
  ): Promise<number> {
    try {
      // Calculate multipliers
      let multiplier = 1.0;
      const now = new Date();
      const hour = now.getHours();
      const day = now.getDay();

      // Weekend warrior
      if (day === 0 || day === 6) {
        multiplier *= MULTIPLIERS.weekendWarrior;
      }

      // Early bird (before 8am)
      if (hour < 8) {
        multiplier *= MULTIPLIERS.earlyBird;
      }

      // Night owl (after 10pm)
      if (hour >= 22) {
        multiplier *= MULTIPLIERS.nightOwl;
      }

      const finalAmount = Math.round(amount * multiplier);

      // Record XP transaction
      await prisma.xpTransaction.create({
        data: {
          userId,
          amount: finalAmount,
          source,
          sourceId,
          multiplier,
          attributeImpact: attributeImpact || {},
          description: `Earned ${finalAmount} XP from ${source}`,
        },
      });

      // Update user profile
      await this.updateUserProfile(userId, finalAmount, attributeImpact);

      logger.info('XP awarded:', { userId, source, amount: finalAmount, multiplier });

      return finalAmount;
    } catch (error) {
      logger.error('Failed to award XP:', { error, userId, source });
      throw error;
    }
  }

  private async updateUserProfile(
    userId: string,
    xpAmount: number,
    attributeImpact?: Record<string, number>
  ): Promise<void> {
    // Get or create user profile
    let profile = await prisma.userProfile.findUnique({
      where: { userId },
    });

    if (!profile) {
      profile = await prisma.userProfile.create({
        data: { userId },
      });
    }

    const newTotalXp = profile.totalXp + xpAmount;
    const newLevel = Math.floor(newTotalXp / 100) + 1;
    const xpToNextLevel = (newLevel * 100) - newTotalXp;

    // Update attributes
    const updates: any = {
      totalXp: newTotalXp,
      currentLevel: newLevel,
      xpToNextLevel,
    };

    if (attributeImpact) {
      if (attributeImpact.discipline) {
        updates.attributeDiscipline = Math.min(100, profile.attributeDiscipline + attributeImpact.discipline);
      }
      if (attributeImpact.learning) {
        updates.attributeLearning = Math.min(100, profile.attributeLearning + attributeImpact.learning);
      }
      if (attributeImpact.wellbeing) {
        updates.attributeWellbeing = Math.min(100, profile.attributeWellbeing + attributeImpact.wellbeing);
      }
      if (attributeImpact.career) {
        updates.attributeCareer = Math.min(100, profile.attributeCareer + attributeImpact.career);
      }
      if (attributeImpact.creativity) {
        updates.attributeCreativity = Math.min(100, profile.attributeCreativity + attributeImpact.creativity);
      }
    }

    await prisma.userProfile.update({
      where: { userId },
      data: updates,
    });

    // Calculate and update influence score
    await this.updateInfluenceScore(userId);

    // Update rank title
    await this.updateRankTitle(userId);
  }

  async calculateInfluenceScore(userId: string): Promise<number> {
    const profile = await prisma.userProfile.findUnique({
      where: { userId },
    });

    if (!profile) return 0;

    // Get completed dreams count
    const completedDreams = await prisma.dream.count({
      where: { userId, status: 'completed' },
    });

    // Get buddy impact (number of buddies helped)
    const buddyImpact = await prisma.dreamBuddy.count({
      where: {
        OR: [{ user1Id: userId }, { user2Id: userId }],
        status: 'active',
      },
    });

    // Get circle contribution
    const circleContribution = await prisma.circleMember.count({
      where: { userId, leftAt: null },
    });

    // Calculate influence score
    // Influence = (Total XP × 0.6) + (Completed Dreams × 500) + (Buddy Impact × 200) + (Circle × 100) + (Streak × 10)
    const influenceScore = Math.round(
      profile.totalXp * 0.6 +
      completedDreams * 500 +
      buddyImpact * 200 +
      circleContribution * 100 +
      profile.currentStreak * 10
    );

    return influenceScore;
  }

  private async updateInfluenceScore(userId: string): Promise<void> {
    const influenceScore = await this.calculateInfluenceScore(userId);

    await prisma.userProfile.update({
      where: { userId },
      data: { influenceScore },
    });
  }

  private async updateRankTitle(userId: string): Promise<void> {
    const profile = await prisma.userProfile.findUnique({
      where: { userId },
    });

    if (!profile) return;

    const rankTier = RANK_TIERS.find(
      (tier) => profile.influenceScore >= tier.minInfluence && profile.influenceScore <= tier.maxInfluence
    );

    if (rankTier && profile.title !== rankTier.title) {
      await prisma.userProfile.update({
        where: { userId },
        data: { title: rankTier.title },
      });

      logger.info('Rank updated:', { userId, newRank: rankTier.title, influenceScore: profile.influenceScore });
    }
  }

  async handleTaskCompletion(userId: string, taskId: string, category: string): Promise<void> {
    // Base XP
    let xpAmount = XP_REWARDS.taskCompleted;

    // Attribute impact based on category
    const attributeImpact: Record<string, number> = {};
    switch (category) {
      case 'career':
        attributeImpact.career = 2;
        break;
      case 'health':
      case 'wellness':
        attributeImpact.wellbeing = 2;
        break;
      case 'education':
        attributeImpact.learning = 2;
        break;
      case 'creativity':
        attributeImpact.creativity = 2;
        break;
      default:
        attributeImpact.discipline = 2;
    }

    await this.awardXP(userId, 'task_completed', xpAmount, taskId, attributeImpact);

    // Check for streak
    await this.updateStreak(userId);
  }

  private async updateStreak(userId: string): Promise<void> {
    const profile = await prisma.userProfile.findUnique({
      where: { userId },
    });

    if (!profile) return;

    // Check if user completed tasks yesterday
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    yesterday.setHours(0, 0, 0, 0);

    const yesterdayEnd = new Date(yesterday);
    yesterdayEnd.setHours(23, 59, 59, 999);

    const yesterdayTasks = await prisma.task.count({
      where: {
        goal: { dream: { userId } },
        status: 'completed',
        completedAt: {
          gte: yesterday,
          lte: yesterdayEnd,
        },
      },
    });

    if (yesterdayTasks > 0) {
      // Continue streak
      const newStreak = profile.currentStreak + 1;
      const updates: any = {
        currentStreak: newStreak,
      };

      if (newStreak > profile.longestStreak) {
        updates.longestStreak = newStreak;
      }

      await prisma.userProfile.update({
        where: { userId },
        data: updates,
      });

      // Award streak bonus XP
      await this.awardXP(
        userId,
        'streak_day',
        XP_REWARDS.streakDay * newStreak,
        undefined,
        { discipline: 1 }
      );
    } else {
      // Check if streak insurance is available
      if (profile.streakInsuranceCount > 0) {
        // Use streak insurance
        await prisma.userProfile.update({
          where: { userId },
          data: {
            streakInsuranceCount: profile.streakInsuranceCount - 1,
          },
        });

        logger.info('Streak insurance used:', { userId });
      } else {
        // Streak broken
        await prisma.userProfile.update({
          where: { userId },
          data: { currentStreak: 0 },
        });

        logger.info('Streak broken:', { userId, previousStreak: profile.currentStreak });
      }
    }
  }

  getRankTiers() {
    return RANK_TIERS;
  }

  async getUserProfile(userId: string) {
    let profile = await prisma.userProfile.findUnique({
      where: { userId },
    });

    if (!profile) {
      // Create profile if it doesn't exist
      profile = await prisma.userProfile.create({
        data: { userId },
      });
    }

    return profile;
  }

  async getXpHistory(userId: string, limit: number = 50, offset: number = 0) {
    const transactions = await prisma.xpTransaction.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      take: limit,
      skip: offset,
    });

    return transactions;
  }

  async getUserStats(userId: string) {
    const profile = await this.getUserProfile(userId);

    // Get completed dreams
    const completedDreams = await prisma.dream.count({
      where: { userId, status: 'completed' },
    });

    // Get total tasks completed
    const completedTasks = await prisma.task.count({
      where: {
        goal: { dream: { userId } },
        status: 'completed',
      },
    });

    // Get active buddies
    const activeBuddies = await prisma.dreamBuddy.count({
      where: {
        OR: [{ user1Id: userId }, { user2Id: userId }],
        status: 'active',
      },
    });

    // Get circles
    const circles = await prisma.circleMember.count({
      where: { userId, leftAt: null },
    });

    // Get achievements count
    const achievements = await prisma.userAchievement.count({
      where: { userId },
    });

    return {
      totalXp: profile.totalXp,
      currentLevel: profile.currentLevel,
      influenceScore: profile.influenceScore,
      title: profile.title,
      currentStreak: profile.currentStreak,
      longestStreak: profile.longestStreak,
      completedDreams,
      completedTasks,
      activeBuddies,
      circles,
      achievements,
      attributes: {
        discipline: profile.attributeDiscipline,
        learning: profile.attributeLearning,
        wellbeing: profile.attributeWellbeing,
        career: profile.attributeCareer,
        creativity: profile.attributeCreativity,
      },
    };
  }
}

export const gamificationService = new GamificationService();
