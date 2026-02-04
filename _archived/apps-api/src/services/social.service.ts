import { prisma } from '../utils/prisma';
import { notificationService } from './notification.service';
import { logger } from '../config/logger';

interface UserSearchResult {
  id: string;
  username: string;
  avatar?: string;
  influenceScore: number;
  title: string;
  isFriend: boolean;
  isFollowing: boolean;
}

interface FriendRequest {
  id: string;
  sender: {
    id: string;
    username: string;
    avatar?: string;
  };
  createdAt: Date;
}

interface ActivityFeedItem {
  id: string;
  type: string;
  user: {
    id: string;
    username: string;
    avatar?: string;
  };
  content: any;
  createdAt: Date;
}

class SocialService {
  // ===== FRIENDSHIPS =====

  async sendFriendRequest(userId: string, targetUserId: string): Promise<void> {
    try {
      // Check if already friends or request exists
      const existing = await prisma.friendship.findFirst({
        where: {
          OR: [
            { user1Id: userId, user2Id: targetUserId },
            { user1Id: targetUserId, user2Id: userId },
          ],
        },
      });

      if (existing) {
        if (existing.status === 'accepted') {
          throw new Error('Already friends');
        } else if (existing.status === 'pending') {
          throw new Error('Friend request already sent');
        }
      }

      // Create friend request
      const friendship = await prisma.friendship.create({
        data: {
          user1Id: userId,
          user2Id: targetUserId,
          status: 'pending',
        },
      });

      // Send notification
      await notificationService.sendNotification(targetUserId, {
        title: 'Nouvelle demande d\'ami',
        body: 'Quelqu\'un veut être ton ami !',
        type: 'friend_request',
        data: {
          friendshipId: friendship.id,
          userId,
        },
      });

      logger.info('Friend request sent:', { userId, targetUserId });
    } catch (error) {
      logger.error('Failed to send friend request:', { error, userId, targetUserId });
      throw error;
    }
  }

  async acceptFriendRequest(userId: string, friendshipId: string): Promise<void> {
    try {
      const friendship = await prisma.friendship.findUnique({
        where: { id: friendshipId },
      });

      if (!friendship) {
        throw new Error('Friend request not found');
      }

      if (friendship.user2Id !== userId) {
        throw new Error('Not authorized');
      }

      if (friendship.status !== 'pending') {
        throw new Error('Friend request is not pending');
      }

      // Accept request
      await prisma.friendship.update({
        where: { id: friendshipId },
        data: { status: 'accepted' },
      });

      // Send notification
      await notificationService.sendNotification(friendship.user1Id, {
        title: 'Demande d\'ami acceptée',
        body: 'Votre demande d\'ami a été acceptée !',
        type: 'friend_accepted',
        data: {
          userId,
        },
      });

      logger.info('Friend request accepted:', { friendshipId, userId });
    } catch (error) {
      logger.error('Failed to accept friend request:', { error, friendshipId, userId });
      throw error;
    }
  }

  async rejectFriendRequest(userId: string, friendshipId: string): Promise<void> {
    try {
      const friendship = await prisma.friendship.findUnique({
        where: { id: friendshipId },
      });

      if (!friendship) {
        throw new Error('Friend request not found');
      }

      if (friendship.user2Id !== userId) {
        throw new Error('Not authorized');
      }

      await prisma.friendship.delete({
        where: { id: friendshipId },
      });

      logger.info('Friend request rejected:', { friendshipId, userId });
    } catch (error) {
      logger.error('Failed to reject friend request:', { error, friendshipId, userId });
      throw error;
    }
  }

  async removeFriend(userId: string, friendId: string): Promise<void> {
    try {
      const friendship = await prisma.friendship.findFirst({
        where: {
          OR: [
            { user1Id: userId, user2Id: friendId },
            { user1Id: friendId, user2Id: userId },
          ],
          status: 'accepted',
        },
      });

      if (!friendship) {
        throw new Error('Friendship not found');
      }

      await prisma.friendship.delete({
        where: { id: friendship.id },
      });

      logger.info('Friend removed:', { userId, friendId });
    } catch (error) {
      logger.error('Failed to remove friend:', { error, userId, friendId });
      throw error;
    }
  }

  async getFriends(userId: string) {
    const friendships = await prisma.friendship.findMany({
      where: {
        OR: [
          { user1Id: userId, status: 'accepted' },
          { user2Id: userId, status: 'accepted' },
        ],
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
                title: true,
                currentLevel: true,
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
                title: true,
                currentLevel: true,
              },
            },
          },
        },
      },
    });

    return friendships.map((f) => {
      const friend = f.user1Id === userId ? f.user2 : f.user1;
      return {
        id: friend.id,
        username: friend.username,
        avatar: friend.avatar,
        influenceScore: friend.profile?.influenceScore || 0,
        title: friend.profile?.title || 'Rêveur',
        currentLevel: friend.profile?.currentLevel || 1,
      };
    });
  }

  async getPendingRequests(userId: string): Promise<FriendRequest[]> {
    const requests = await prisma.friendship.findMany({
      where: {
        user2Id: userId,
        status: 'pending',
      },
      include: {
        user1: {
          select: {
            id: true,
            username: true,
            avatar: true,
          },
        },
      },
      orderBy: {
        createdAt: 'desc',
      },
    });

    return requests.map((r) => ({
      id: r.id,
      sender: {
        id: r.user1.id,
        username: r.user1.username || 'Anonymous',
        avatar: r.user1.avatar,
      },
      createdAt: r.createdAt,
    }));
  }

  // ===== FOLLOWS =====

  async followUser(userId: string, targetUserId: string): Promise<void> {
    try {
      // Check if already following
      const existing = await prisma.follow.findUnique({
        where: {
          followerId_followingId: {
            followerId: userId,
            followingId: targetUserId,
          },
        },
      });

      if (existing) {
        throw new Error('Already following');
      }

      await prisma.follow.create({
        data: {
          followerId: userId,
          followingId: targetUserId,
        },
      });

      // Send notification
      await notificationService.sendNotification(targetUserId, {
        title: 'Nouveau follower',
        body: 'Quelqu\'un vous suit maintenant !',
        type: 'new_follower',
        data: {
          userId,
        },
      });

      logger.info('User followed:', { userId, targetUserId });
    } catch (error) {
      logger.error('Failed to follow user:', { error, userId, targetUserId });
      throw error;
    }
  }

  async unfollowUser(userId: string, targetUserId: string): Promise<void> {
    try {
      await prisma.follow.delete({
        where: {
          followerId_followingId: {
            followerId: userId,
            followingId: targetUserId,
          },
        },
      });

      logger.info('User unfollowed:', { userId, targetUserId });
    } catch (error) {
      logger.error('Failed to unfollow user:', { error, userId, targetUserId });
      throw error;
    }
  }

  async getFollowers(userId: string) {
    const follows = await prisma.follow.findMany({
      where: { followingId: userId },
      include: {
        follower: {
          select: {
            id: true,
            username: true,
            avatar: true,
            profile: {
              select: {
                influenceScore: true,
                title: true,
              },
            },
          },
        },
      },
    });

    return follows.map((f) => ({
      id: f.follower.id,
      username: f.follower.username,
      avatar: f.follower.avatar,
      influenceScore: f.follower.profile?.influenceScore || 0,
      title: f.follower.profile?.title || 'Rêveur',
    }));
  }

  async getFollowing(userId: string) {
    const follows = await prisma.follow.findMany({
      where: { followerId: userId },
      include: {
        following: {
          select: {
            id: true,
            username: true,
            avatar: true,
            profile: {
              select: {
                influenceScore: true,
                title: true,
              },
            },
          },
        },
      },
    });

    return follows.map((f) => ({
      id: f.following.id,
      username: f.following.username,
      avatar: f.following.avatar,
      influenceScore: f.following.profile?.influenceScore || 0,
      title: f.following.profile?.title || 'Rêveur',
    }));
  }

  // ===== SEARCH =====

  async searchUsers(
    searchQuery: string,
    currentUserId: string,
    limit: number = 20
  ): Promise<UserSearchResult[]> {
    const users = await prisma.user.findMany({
      where: {
        OR: [
          { username: { contains: searchQuery, mode: 'insensitive' } },
          { email: { contains: searchQuery, mode: 'insensitive' } },
        ],
        id: { not: currentUserId },
      },
      select: {
        id: true,
        username: true,
        avatar: true,
        profile: {
          select: {
            influenceScore: true,
            title: true,
          },
        },
      },
      take: limit,
    });

    // Check friendship and follow status
    const results = await Promise.all(
      users.map(async (user) => {
        const friendship = await prisma.friendship.findFirst({
          where: {
            OR: [
              { user1Id: currentUserId, user2Id: user.id },
              { user1Id: user.id, user2Id: currentUserId },
            ],
            status: 'accepted',
          },
        });

        const following = await prisma.follow.findUnique({
          where: {
            followerId_followingId: {
              followerId: currentUserId,
              followingId: user.id,
            },
          },
        });

        return {
          id: user.id,
          username: user.username || 'Anonymous',
          avatar: user.avatar,
          influenceScore: user.profile?.influenceScore || 0,
          title: user.profile?.title || 'Rêveur',
          isFriend: !!friendship,
          isFollowing: !!following,
        };
      })
    );

    return results;
  }

  // ===== ACTIVITY FEED =====

  async getFriendsFeed(userId: string, limit: number = 50): Promise<ActivityFeedItem[]> {
    try {
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

      // Include user's own activities
      friendIds.push(userId);

      // Get activity feed
      const activities = await prisma.activityFeed.findMany({
        where: {
          userId: { in: friendIds },
          visibility: { in: ['public', 'friends'] },
        },
        include: {
          user: {
            select: {
              id: true,
              username: true,
              avatar: true,
            },
          },
        },
        orderBy: {
          createdAt: 'desc',
        },
        take: limit,
      });

      return activities.map((activity) => ({
        id: activity.id,
        type: activity.activityType,
        user: {
          id: activity.user.id,
          username: activity.user.username || 'Anonymous',
          avatar: activity.user.avatar,
        },
        content: activity.content,
        createdAt: activity.createdAt,
      }));
    } catch (error) {
      logger.error('Failed to get friends feed:', { error, userId });
      throw error;
    }
  }

  async createActivity(
    userId: string,
    activityType: string,
    content: any,
    visibility: 'public' | 'friends' | 'private' = 'friends'
  ): Promise<void> {
    try {
      await prisma.activityFeed.create({
        data: {
          userId,
          activityType,
          content,
          visibility,
        },
      });

      logger.info('Activity created:', { userId, activityType });
    } catch (error) {
      logger.error('Failed to create activity:', { error, userId, activityType });
      throw error;
    }
  }
}

export const socialService = new SocialService();
