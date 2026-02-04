import { describe, it, expect, beforeEach } from 'vitest';
import request from 'supertest';
import express from 'express';
import { gamificationRouter } from '../../src/routes/gamification';
import { authMiddleware } from '../../src/middleware/auth';
import { prisma } from '../../src/utils/prisma';
import admin from 'firebase-admin';

// Mock Firebase Admin
vi.mock('firebase-admin', () => ({
  default: {
    auth: () => ({
      verifyIdToken: vi.fn().mockResolvedValue({
        uid: 'test-firebase-uid',
        email: 'test@example.com',
      }),
    }),
  },
}));

describe('Gamification Routes', () => {
  let app: express.Application;
  let testUser: any;
  let authToken: string;

  beforeEach(async () => {
    // Setup Express app
    app = express();
    app.use(express.json());
    app.use('/api/gamification', authMiddleware, gamificationRouter);

    // Create test user
    testUser = await prisma.user.create({
      data: {
        firebaseUid: 'test-firebase-uid',
        email: 'test@example.com',
      },
    });

    // Create user profile
    await prisma.userProfile.create({
      data: {
        userId: testUser.id,
        totalXp: 150,
        currentLevel: 2,
        influenceScore: 200,
        currentStreak: 5,
      },
    });

    authToken = 'Bearer test-token';
  });

  describe('GET /api/gamification/profile', () => {
    it('should return user profile', async () => {
      const response = await request(app)
        .get('/api/gamification/profile')
        .set('Authorization', authToken);

      expect(response.status).toBe(200);
      expect(response.body.data.profile).toBeDefined();
      expect(response.body.data.profile.totalXp).toBe(150);
      expect(response.body.data.profile.currentLevel).toBe(2);
    });
  });

  describe('GET /api/gamification/stats', () => {
    it('should return user stats', async () => {
      const response = await request(app)
        .get('/api/gamification/stats')
        .set('Authorization', authToken);

      expect(response.status).toBe(200);
      expect(response.body.data.stats).toBeDefined();
      expect(response.body.data.stats.totalXp).toBe(150);
      expect(response.body.data.stats.influenceScore).toBe(200);
    });
  });

  describe('GET /api/gamification/xp-history', () => {
    it('should return XP transaction history', async () => {
      // Create XP transactions
      await prisma.xpTransaction.create({
        data: {
          userId: testUser.id,
          amount: 10,
          source: 'task_completed',
          description: 'Task completed',
        },
      });

      const response = await request(app)
        .get('/api/gamification/xp-history')
        .set('Authorization', authToken);

      expect(response.status).toBe(200);
      expect(response.body.data.transactions).toHaveLength(1);
      expect(response.body.data.transactions[0].amount).toBe(10);
    });
  });

  describe('GET /api/gamification/ranks', () => {
    it('should return rank tiers', async () => {
      const response = await request(app)
        .get('/api/gamification/ranks')
        .set('Authorization', authToken);

      expect(response.status).toBe(200);
      expect(response.body.data.ranks).toHaveLength(8);
    });
  });

  describe('GET /api/gamification/leaderboards/global', () => {
    it('should return global leaderboard', async () => {
      const response = await request(app)
        .get('/api/gamification/leaderboards/global')
        .set('Authorization', authToken);

      expect(response.status).toBe(200);
      expect(response.body.data.leaderboard).toBeDefined();
      expect(response.body.data.leaderboard.entries).toBeDefined();
    });
  });
});
