import { prisma } from '../utils/prisma';
import { notificationService } from './notification.service';
import { socialService } from './social.service';
import { logger } from '../config/logger';

interface CreateCircleData {
  name: string;
  description: string;
  category?: string;
  isPublic: boolean;
  maxMembers?: number;
}

interface CreateChallengeData {
  title: string;
  description: string;
  startDate: Date;
  endDate: Date;
  targetType: string;
  targetValue: number;
}

class CircleService {
  async createCircle(userId: string, data: CreateCircleData) {
    try {
      const { name, description, category, isPublic, maxMembers } = data;

      const circle = await prisma.dreamCircle.create({
        data: {
          name,
          description,
          category,
          isPublic,
          maxMembers: maxMembers || 10,
          createdBy: userId,
        },
      });

      // Add creator as admin member
      await prisma.circleMember.create({
        data: {
          circleId: circle.id,
          userId,
          role: 'admin',
          joinedAt: new Date(),
        },
      });

      // Create activity
      await socialService.createActivity(userId, 'circle_created', {
        circleId: circle.id,
        circleName: name,
      }, 'public');

      logger.info('Circle created:', { circleId: circle.id, userId });

      return circle;
    } catch (error) {
      logger.error('Failed to create circle:', { error, userId });
      throw error;
    }
  }

  async getCircles(
    userId: string,
    filter?: 'my' | 'public' | 'recommended',
    category?: string,
    limit: number = 20
  ) {
    try {
      let where: any = {};

      if (filter === 'my') {
        // Get circles user is a member of
        const memberCircles = await prisma.circleMember.findMany({
          where: { userId, leftAt: null },
          select: { circleId: true },
        });

        where.id = { in: memberCircles.map((m) => m.circleId) };
      } else if (filter === 'public') {
        where.isPublic = true;
      } else if (filter === 'recommended') {
        // Recommend circles based on user's dream categories
        const userDreams = await prisma.dream.findMany({
          where: { userId, status: 'active' },
          select: { category: true },
        });

        const userCategories = [...new Set(userDreams.map((d) => d.category))];
        where.isPublic = true;
        if (userCategories.length > 0) {
          where.category = { in: userCategories };
        }
      }

      if (category) {
        where.category = category;
      }

      const circles = await prisma.dreamCircle.findMany({
        where,
        include: {
          _count: {
            select: {
              members: {
                where: { leftAt: null },
              },
            },
          },
          members: {
            where: { leftAt: null },
            take: 3,
            select: {
              user: {
                select: {
                  avatar: true,
                },
              },
            },
          },
        },
        take: limit,
        orderBy: {
          createdAt: 'desc',
        },
      });

      return circles.map((circle) => ({
        id: circle.id,
        name: circle.name,
        description: circle.description,
        category: circle.category,
        isPublic: circle.isPublic,
        maxMembers: circle.maxMembers,
        memberCount: circle._count.members,
        memberAvatars: circle.members.map((m) => m.user.avatar).filter(Boolean),
      }));
    } catch (error) {
      logger.error('Failed to get circles:', { error, userId });
      throw error;
    }
  }

  async getCircle(userId: string, circleId: string) {
    try {
      const circle = await prisma.dreamCircle.findUnique({
        where: { id: circleId },
        include: {
          members: {
            where: { leftAt: null },
            include: {
              user: {
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
          },
          challenges: {
            where: {
              endDate: { gte: new Date() },
            },
            orderBy: {
              startDate: 'asc',
            },
            take: 5,
          },
        },
      });

      if (!circle) {
        throw new Error('Circle not found');
      }

      // Check if user is a member
      const membership = circle.members.find((m) => m.userId === userId);

      return {
        id: circle.id,
        name: circle.name,
        description: circle.description,
        category: circle.category,
        isPublic: circle.isPublic,
        maxMembers: circle.maxMembers,
        createdBy: circle.createdBy,
        members: circle.members.map((m) => ({
          id: m.user.id,
          username: m.user.username || 'Anonymous',
          avatar: m.user.avatar,
          influenceScore: m.user.profile?.influenceScore || 0,
          title: m.user.profile?.title || 'Rêveur',
          role: m.role,
          joinedAt: m.joinedAt,
        })),
        challenges: circle.challenges,
        isMember: !!membership,
        myRole: membership?.role,
      };
    } catch (error) {
      logger.error('Failed to get circle:', { error, circleId });
      throw error;
    }
  }

  async joinCircle(userId: string, circleId: string) {
    try {
      const circle = await prisma.dreamCircle.findUnique({
        where: { id: circleId },
        include: {
          _count: {
            select: {
              members: {
                where: { leftAt: null },
              },
            },
          },
        },
      });

      if (!circle) {
        throw new Error('Circle not found');
      }

      if (!circle.isPublic) {
        throw new Error('Circle is private');
      }

      if (circle._count.members >= circle.maxMembers) {
        throw new Error('Circle is full');
      }

      // Check if already a member
      const existing = await prisma.circleMember.findUnique({
        where: {
          circleId_userId: {
            circleId,
            userId,
          },
        },
      });

      if (existing && !existing.leftAt) {
        throw new Error('Already a member');
      }

      // Join circle
      if (existing) {
        // Rejoin
        await prisma.circleMember.update({
          where: {
            circleId_userId: {
              circleId,
              userId,
            },
          },
          data: {
            leftAt: null,
            joinedAt: new Date(),
          },
        });
      } else {
        // New join
        await prisma.circleMember.create({
          data: {
            circleId,
            userId,
            role: 'member',
            joinedAt: new Date(),
          },
        });
      }

      // Notify circle members
      const members = await prisma.circleMember.findMany({
        where: { circleId, leftAt: null, userId: { not: userId } },
        select: { userId: true },
      });

      for (const member of members) {
        await notificationService.sendNotification(member.userId, {
          title: 'Nouveau membre',
          body: 'Quelqu\'un a rejoint ton cercle !',
          type: 'circle_member_joined',
          data: {
            circleId,
            userId,
          },
        });
      }

      // Create activity
      await socialService.createActivity(userId, 'circle_joined', {
        circleId,
        circleName: circle.name,
      });

      logger.info('User joined circle:', { userId, circleId });
    } catch (error) {
      logger.error('Failed to join circle:', { error, userId, circleId });
      throw error;
    }
  }

  async leaveCircle(userId: string, circleId: string) {
    try {
      const membership = await prisma.circleMember.findUnique({
        where: {
          circleId_userId: {
            circleId,
            userId,
          },
        },
      });

      if (!membership || membership.leftAt) {
        throw new Error('Not a member of this circle');
      }

      // Check if user is the creator
      const circle = await prisma.dreamCircle.findUnique({
        where: { id: circleId },
      });

      if (circle?.createdBy === userId) {
        // Transfer ownership or delete circle
        const otherAdmins = await prisma.circleMember.findFirst({
          where: {
            circleId,
            userId: { not: userId },
            role: 'admin',
            leftAt: null,
          },
        });

        if (otherAdmins) {
          // Transfer to another admin
          await prisma.dreamCircle.update({
            where: { id: circleId },
            data: { createdBy: otherAdmins.userId },
          });
        } else {
          // Make oldest member admin
          const oldestMember = await prisma.circleMember.findFirst({
            where: {
              circleId,
              userId: { not: userId },
              leftAt: null,
            },
            orderBy: {
              joinedAt: 'asc',
            },
          });

          if (oldestMember) {
            await prisma.circleMember.update({
              where: {
                circleId_userId: {
                  circleId,
                  userId: oldestMember.userId,
                },
              },
              data: { role: 'admin' },
            });

            await prisma.dreamCircle.update({
              where: { id: circleId },
              data: { createdBy: oldestMember.userId },
            });
          }
        }
      }

      // Leave circle
      await prisma.circleMember.update({
        where: {
          circleId_userId: {
            circleId,
            userId,
          },
        },
        data: {
          leftAt: new Date(),
        },
      });

      logger.info('User left circle:', { userId, circleId });
    } catch (error) {
      logger.error('Failed to leave circle:', { error, userId, circleId });
      throw error;
    }
  }

  async createChallenge(userId: string, circleId: string, data: CreateChallengeData) {
    try {
      // Check if user is admin
      const membership = await prisma.circleMember.findUnique({
        where: {
          circleId_userId: {
            circleId,
            userId,
          },
        },
      });

      if (!membership || membership.leftAt || membership.role !== 'admin') {
        throw new Error('Not authorized');
      }

      const challenge = await prisma.circleChallenge.create({
        data: {
          circleId,
          createdBy: userId,
          ...data,
        },
      });

      // Notify circle members
      const members = await prisma.circleMember.findMany({
        where: { circleId, leftAt: null, userId: { not: userId } },
        select: { userId: true },
      });

      for (const member of members) {
        await notificationService.sendNotification(member.userId, {
          title: 'Nouveau challenge',
          body: `Nouveau challenge dans ton cercle: ${data.title}`,
          type: 'circle_challenge',
          data: {
            circleId,
            challengeId: challenge.id,
          },
        });
      }

      logger.info('Challenge created:', { challengeId: challenge.id, circleId, userId });

      return challenge;
    } catch (error) {
      logger.error('Failed to create challenge:', { error, circleId, userId });
      throw error;
    }
  }

  async joinChallenge(userId: string, challengeId: string) {
    try {
      const challenge = await prisma.circleChallenge.findUnique({
        where: { id: challengeId },
      });

      if (!challenge) {
        throw new Error('Challenge not found');
      }

      // Check if user is a circle member
      const membership = await prisma.circleMember.findUnique({
        where: {
          circleId_userId: {
            circleId: challenge.circleId,
            userId,
          },
        },
      });

      if (!membership || membership.leftAt) {
        throw new Error('Not a member of this circle');
      }

      // Check if already participating
      const existing = await prisma.challengeParticipant.findUnique({
        where: {
          challengeId_userId: {
            challengeId,
            userId,
          },
        },
      });

      if (existing) {
        throw new Error('Already participating');
      }

      await prisma.challengeParticipant.create({
        data: {
          challengeId,
          userId,
          progress: 0,
        },
      });

      logger.info('User joined challenge:', { userId, challengeId });
    } catch (error) {
      logger.error('Failed to join challenge:', { error, userId, challengeId });
      throw error;
    }
  }

  async getCircleFeed(userId: string, circleId: string, limit: number = 20) {
    try {
      // Check if user is a member
      const membership = await prisma.circleMember.findUnique({
        where: {
          circleId_userId: {
            circleId,
            userId,
          },
        },
      });

      if (!membership || membership.leftAt) {
        throw new Error('Not a member of this circle');
      }

      const posts = await prisma.circlePost.findMany({
        where: { circleId },
        include: {
          user: {
            select: {
              id: true,
              username: true,
              avatar: true,
            },
          },
          reactions: {
            select: {
              type: true,
              userId: true,
            },
          },
        },
        orderBy: {
          createdAt: 'desc',
        },
        take: limit,
      });

      return posts.map((post) => ({
        id: post.id,
        content: post.content,
        user: {
          id: post.user.id,
          username: post.user.username || 'Anonymous',
          avatar: post.user.avatar,
        },
        reactions: post.reactions,
        createdAt: post.createdAt,
      }));
    } catch (error) {
      logger.error('Failed to get circle feed:', { error, circleId });
      throw error;
    }
  }

  async createPost(userId: string, circleId: string, content: string) {
    try {
      // Check if user is a member
      const membership = await prisma.circleMember.findUnique({
        where: {
          circleId_userId: {
            circleId,
            userId,
          },
        },
      });

      if (!membership || membership.leftAt) {
        throw new Error('Not a member of this circle');
      }

      const post = await prisma.circlePost.create({
        data: {
          circleId,
          userId,
          content,
        },
      });

      logger.info('Circle post created:', { postId: post.id, circleId, userId });

      return post;
    } catch (error) {
      logger.error('Failed to create post:', { error, circleId, userId });
      throw error;
    }
  }
}

export const circleService = new CircleService();
