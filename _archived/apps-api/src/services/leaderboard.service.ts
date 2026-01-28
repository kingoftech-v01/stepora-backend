import { prisma } from '../utils/prisma';
import { redisClient } from '../config/redis';
import { logger } from '../config/logger';

interface LeaderboardEntry {
  userId: string;
  username: string;
  avatar?: string;
  influenceScore: number;
  currentLevel: number;
  title: string;
  rank: number;
}

interface LeaderboardResult {
  entries: LeaderboardEntry[];
  myRank?: number;
  total: number;
}

class LeaderboardService {
  private readonly CACHE_TTL = 300; // 5 minutes

  async getGlobalLeaderboard(
    userId: string,
    limit: number = 50,
    offset: number = 0
  ): Promise<LeaderboardResult> {
    const cacheKey = `leaderboard:global:${limit}:${offset}`;

    try {
      // Try cache first
      const cached = await redisClient.get(cacheKey);
      if (cached) {
        const result = JSON.parse(cached);
        // Still need to get user's rank
        result.myRank = await this.getUserGlobalRank(userId);
        return result;
      }

      // Fetch from database
      const profiles = await prisma.userProfile.findMany({
        where: {
          influenceScore: { gt: 0 },
        },
        select: {
          userId: true,
          influenceScore: true,
          currentLevel: true,
          title: true,
          user: {
            select: {
              username: true,
              avatar: true,
            },
          },
        },
        orderBy: {
          influenceScore: 'desc',
        },
        skip: offset,
        take: limit,
      });

      const total = await prisma.userProfile.count({
        where: {
          influenceScore: { gt: 0 },
        },
      });

      const entries: LeaderboardEntry[] = profiles.map((profile, index) => ({
        userId: profile.userId,
        username: profile.user.username || 'Anonymous',
        avatar: profile.user.avatar,
        influenceScore: profile.influenceScore,
        currentLevel: profile.currentLevel,
        title: profile.title,
        rank: offset + index + 1,
      }));

      const result = {
        entries,
        total,
      };

      // Cache for 5 minutes
      await redisClient.setEx(cacheKey, this.CACHE_TTL, JSON.stringify(result));

      // Get user's rank
      result.myRank = await this.getUserGlobalRank(userId);

      return result;
    } catch (error) {
      logger.error('Failed to get global leaderboard:', { error });
      throw error;
    }
  }

  async getFriendsLeaderboard(userId: string): Promise<LeaderboardResult> {
    const cacheKey = `leaderboard:friends:${userId}`;

    try {
      // Try cache first
      const cached = await redisClient.get(cacheKey);
      if (cached) {
        return JSON.parse(cached);
      }

      // Get user's friends
      const friendships = await prisma.friendship.findMany({
        where: {
          OR: [
            { user1Id: userId, status: 'accepted' },
            { user2Id: userId, status: 'accepted' },
          ],
        },
        select: {
          user1Id: true,
          user2Id: true,
        },
      });

      const friendIds = friendships.map((f) =>
        f.user1Id === userId ? f.user2Id : f.user1Id
      );

      // Include the user themselves
      friendIds.push(userId);

      // Fetch profiles
      const profiles = await prisma.userProfile.findMany({
        where: {
          userId: { in: friendIds },
        },
        select: {
          userId: true,
          influenceScore: true,
          currentLevel: true,
          title: true,
          user: {
            select: {
              username: true,
              avatar: true,
            },
          },
        },
        orderBy: {
          influenceScore: 'desc',
        },
      });

      const entries: LeaderboardEntry[] = profiles.map((profile, index) => ({
        userId: profile.userId,
        username: profile.user.username || 'Anonymous',
        avatar: profile.user.avatar,
        influenceScore: profile.influenceScore,
        currentLevel: profile.currentLevel,
        title: profile.title,
        rank: index + 1,
      }));

      const myRank = entries.findIndex((e) => e.userId === userId) + 1;

      const result = {
        entries,
        myRank: myRank > 0 ? myRank : undefined,
        total: entries.length,
      };

      // Cache for 5 minutes
      await redisClient.setEx(cacheKey, this.CACHE_TTL, JSON.stringify(result));

      return result;
    } catch (error) {
      logger.error('Failed to get friends leaderboard:', { error, userId });
      throw error;
    }
  }

  async getLocalLeaderboard(
    userId: string,
    country?: string,
    city?: string,
    limit: number = 50
  ): Promise<LeaderboardResult> {
    try {
      // Get user's location if not provided
      if (!country) {
        const user = await prisma.user.findUnique({
          where: { id: userId },
          select: { country: true, city: true },
        });
        country = user?.country;
        city = user?.city;
      }

      if (!country) {
        // Return empty if no location
        return { entries: [], total: 0 };
      }

      const cacheKey = `leaderboard:local:${country}:${city || 'all'}:${limit}`;

      // Try cache first
      const cached = await redisClient.get(cacheKey);
      if (cached) {
        const result = JSON.parse(cached);
        result.myRank = await this.getUserLocalRank(userId, country, city);
        return result;
      }

      // Build where clause
      const where: any = {
        user: {
          country,
        },
      };

      if (city) {
        where.user.city = city;
      }

      // Fetch profiles
      const profiles = await prisma.userProfile.findMany({
        where,
        select: {
          userId: true,
          influenceScore: true,
          currentLevel: true,
          title: true,
          user: {
            select: {
              username: true,
              avatar: true,
              country: true,
              city: true,
            },
          },
        },
        orderBy: {
          influenceScore: 'desc',
        },
        take: limit,
      });

      const total = await prisma.userProfile.count({ where });

      const entries: LeaderboardEntry[] = profiles.map((profile, index) => ({
        userId: profile.userId,
        username: profile.user.username || 'Anonymous',
        avatar: profile.user.avatar,
        influenceScore: profile.influenceScore,
        currentLevel: profile.currentLevel,
        title: profile.title,
        rank: index + 1,
      }));

      const result = {
        entries,
        total,
      };

      // Cache for 5 minutes
      await redisClient.setEx(cacheKey, this.CACHE_TTL, JSON.stringify(result));

      // Get user's rank
      result.myRank = await this.getUserLocalRank(userId, country, city);

      return result;
    } catch (error) {
      logger.error('Failed to get local leaderboard:', { error, userId });
      throw error;
    }
  }

  async getCategoryLeaderboard(
    userId: string,
    category: string,
    limit: number = 50
  ): Promise<LeaderboardResult> {
    const cacheKey = `leaderboard:category:${category}:${limit}`;

    try {
      // Try cache first
      const cached = await redisClient.get(cacheKey);
      if (cached) {
        const result = JSON.parse(cached);
        result.myRank = await this.getUserCategoryRank(userId, category);
        return result;
      }

      // Get users with completed dreams in this category
      const usersWithCategory = await prisma.dream.findMany({
        where: {
          category,
          status: 'completed',
        },
        select: {
          userId: true,
        },
        distinct: ['userId'],
      });

      const userIds = usersWithCategory.map((d) => d.userId);

      if (userIds.length === 0) {
        return { entries: [], total: 0 };
      }

      // Get profiles for these users
      const profiles = await prisma.userProfile.findMany({
        where: {
          userId: { in: userIds },
        },
        select: {
          userId: true,
          influenceScore: true,
          currentLevel: true,
          title: true,
          user: {
            select: {
              username: true,
              avatar: true,
            },
          },
        },
        orderBy: {
          influenceScore: 'desc',
        },
        take: limit,
      });

      const entries: LeaderboardEntry[] = profiles.map((profile, index) => ({
        userId: profile.userId,
        username: profile.user.username || 'Anonymous',
        avatar: profile.user.avatar,
        influenceScore: profile.influenceScore,
        currentLevel: profile.currentLevel,
        title: profile.title,
        rank: index + 1,
      }));

      const result = {
        entries,
        total: profiles.length,
      };

      // Cache for 5 minutes
      await redisClient.setEx(cacheKey, this.CACHE_TTL, JSON.stringify(result));

      // Get user's rank
      result.myRank = await this.getUserCategoryRank(userId, category);

      return result;
    } catch (error) {
      logger.error('Failed to get category leaderboard:', { error, category });
      throw error;
    }
  }

  async getCircleLeaderboard(
    userId: string,
    circleId: string
  ): Promise<LeaderboardResult> {
    const cacheKey = `leaderboard:circle:${circleId}`;

    try {
      // Check if user is member
      const membership = await prisma.circleMember.findUnique({
        where: {
          circleId_userId: {
            circleId,
            userId,
          },
          leftAt: null,
        },
      });

      if (!membership) {
        throw new Error('Not a member of this circle');
      }

      // Try cache first
      const cached = await redisClient.get(cacheKey);
      if (cached) {
        return JSON.parse(cached);
      }

      // Get all circle members
      const members = await prisma.circleMember.findMany({
        where: {
          circleId,
          leftAt: null,
        },
        select: {
          userId: true,
        },
      });

      const memberIds = members.map((m) => m.userId);

      // Get profiles
      const profiles = await prisma.userProfile.findMany({
        where: {
          userId: { in: memberIds },
        },
        select: {
          userId: true,
          influenceScore: true,
          currentLevel: true,
          title: true,
          user: {
            select: {
              username: true,
              avatar: true,
            },
          },
        },
        orderBy: {
          influenceScore: 'desc',
        },
      });

      const entries: LeaderboardEntry[] = profiles.map((profile, index) => ({
        userId: profile.userId,
        username: profile.user.username || 'Anonymous',
        avatar: profile.user.avatar,
        influenceScore: profile.influenceScore,
        currentLevel: profile.currentLevel,
        title: profile.title,
        rank: index + 1,
      }));

      const myRank = entries.findIndex((e) => e.userId === userId) + 1;

      const result = {
        entries,
        myRank: myRank > 0 ? myRank : undefined,
        total: entries.length,
      };

      // Cache for 5 minutes
      await redisClient.setEx(cacheKey, this.CACHE_TTL, JSON.stringify(result));

      return result;
    } catch (error) {
      logger.error('Failed to get circle leaderboard:', { error, circleId });
      throw error;
    }
  }

  private async getUserGlobalRank(userId: string): Promise<number | undefined> {
    try {
      const profile = await prisma.userProfile.findUnique({
        where: { userId },
        select: { influenceScore: true },
      });

      if (!profile) return undefined;

      const rank = await prisma.userProfile.count({
        where: {
          influenceScore: { gt: profile.influenceScore },
        },
      });

      return rank + 1;
    } catch (error) {
      logger.error('Failed to get user global rank:', { error, userId });
      return undefined;
    }
  }

  private async getUserLocalRank(
    userId: string,
    country?: string,
    city?: string
  ): Promise<number | undefined> {
    try {
      const profile = await prisma.userProfile.findUnique({
        where: { userId },
        select: { influenceScore: true },
      });

      if (!profile || !country) return undefined;

      const where: any = {
        influenceScore: { gt: profile.influenceScore },
        user: {
          country,
        },
      };

      if (city) {
        where.user.city = city;
      }

      const rank = await prisma.userProfile.count({ where });

      return rank + 1;
    } catch (error) {
      logger.error('Failed to get user local rank:', { error, userId });
      return undefined;
    }
  }

  private async getUserCategoryRank(
    userId: string,
    category: string
  ): Promise<number | undefined> {
    try {
      const profile = await prisma.userProfile.findUnique({
        where: { userId },
        select: { influenceScore: true },
      });

      if (!profile) return undefined;

      // Get users with completed dreams in this category
      const usersWithCategory = await prisma.dream.findMany({
        where: {
          category,
          status: 'completed',
        },
        select: {
          userId: true,
        },
        distinct: ['userId'],
      });

      const userIds = usersWithCategory.map((d) => d.userId);

      const rank = await prisma.userProfile.count({
        where: {
          userId: { in: userIds },
          influenceScore: { gt: profile.influenceScore },
        },
      });

      return rank + 1;
    } catch (error) {
      logger.error('Failed to get user category rank:', { error, userId });
      return undefined;
    }
  }

  async invalidateLeaderboardCache(type: string, identifier?: string): Promise<void> {
    try {
      const pattern = identifier
        ? `leaderboard:${type}:${identifier}*`
        : `leaderboard:${type}*`;

      // In a real implementation, you'd use SCAN to find and delete matching keys
      // For now, just log
      logger.info('Invalidating leaderboard cache:', { pattern });
    } catch (error) {
      logger.error('Failed to invalidate cache:', { error, type });
    }
  }
}

export const leaderboardService = new LeaderboardService();
