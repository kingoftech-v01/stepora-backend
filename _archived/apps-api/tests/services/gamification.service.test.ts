import { describe, it, expect, beforeEach } from 'vitest';
import { gamificationService } from '../../src/services/gamification.service';
import { prisma } from '../../src/utils/prisma';

describe('GamificationService', () => {
  let testUserId: string;

  beforeEach(async () => {
    // Create test user
    const user = await prisma.user.create({
      data: {
        firebaseUid: 'test-uid-' + Date.now(),
        email: 'test@example.com',
      },
    });
    testUserId = user.id;
  });

  describe('awardXP', () => {
    it('should award XP to user', async () => {
      const xp = await gamificationService.awardXP(
        testUserId,
        'task_completed',
        10,
        'test-task-id'
      );

      expect(xp).toBeGreaterThanOrEqual(10);

      // Check XP transaction was created
      const transaction = await prisma.xpTransaction.findFirst({
        where: { userId: testUserId },
      });

      expect(transaction).toBeDefined();
      expect(transaction?.source).toBe('task_completed');
      expect(transaction?.amount).toBe(xp);
    });

    it('should apply weekend multiplier', async () => {
      // Mock date to be a weekend
      const originalDate = Date;
      const mockDate = new Date('2024-01-06'); // Saturday
      global.Date = class extends Date {
        constructor() {
          super();
          return mockDate;
        }
        static now() {
          return mockDate.getTime();
        }
      } as any;

      const xp = await gamificationService.awardXP(
        testUserId,
        'task_completed',
        10
      );

      // Weekend multiplier is 1.5x, so 10 * 1.5 = 15
      expect(xp).toBe(15);

      // Restore original Date
      global.Date = originalDate;
    });

    it('should update user profile level', async () => {
      // Award enough XP to level up (100 XP = level 2)
      await gamificationService.awardXP(testUserId, 'test', 100);

      const profile = await prisma.userProfile.findUnique({
        where: { userId: testUserId },
      });

      expect(profile).toBeDefined();
      expect(profile?.currentLevel).toBe(2);
      expect(profile?.totalXp).toBeGreaterThanOrEqual(100);
    });

    it('should increase attributes based on category', async () => {
      await gamificationService.awardXP(
        testUserId,
        'task_completed',
        10,
        'test-task',
        { discipline: 2, career: 3 }
      );

      const profile = await prisma.userProfile.findUnique({
        where: { userId: testUserId },
      });

      expect(profile?.attributeDiscipline).toBe(2);
      expect(profile?.attributeCareer).toBe(3);
    });
  });

  describe('calculateInfluenceScore', () => {
    it('should calculate influence score correctly', async () => {
      // Award XP
      await gamificationService.awardXP(testUserId, 'test', 100);

      // Create completed dream
      await prisma.dream.create({
        data: {
          userId: testUserId,
          title: 'Test Dream',
          description: 'Test',
          status: 'completed',
        },
      });

      const influenceScore = await gamificationService.calculateInfluenceScore(testUserId);

      // Influence = (100 * 0.6) + (1 * 500) = 60 + 500 = 560
      expect(influenceScore).toBeGreaterThanOrEqual(560);
    });
  });

  describe('handleTaskCompletion', () => {
    it('should award XP and update streak', async () => {
      await gamificationService.handleTaskCompletion(
        testUserId,
        'test-task-id',
        'career'
      );

      const profile = await prisma.userProfile.findUnique({
        where: { userId: testUserId },
      });

      expect(profile?.totalXp).toBeGreaterThan(0);
      expect(profile?.attributeCareer).toBeGreaterThan(0);
    });
  });

  describe('getRankTiers', () => {
    it('should return all rank tiers', () => {
      const tiers = gamificationService.getRankTiers();

      expect(tiers).toHaveLength(8);
      expect(tiers[0].title).toBe('Rêveur');
      expect(tiers[7].title).toBe('Légende');
    });
  });
});
