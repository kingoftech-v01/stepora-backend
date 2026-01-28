import { Router } from 'express';
import { Response, NextFunction } from 'express';
import { AuthRequest } from '../middleware/auth';
import { asyncHandler } from '../middleware/errorHandler';
import { gamificationService } from '../services/gamification.service';
import { leaderboardService } from '../services/leaderboard.service';
import { success } from '../utils/response';
import { z } from 'zod';
import { validate } from '../middleware/validation';

const router = Router();

const leaderboardQuerySchema = z.object({
  query: z.object({
    limit: z.string().optional().transform((val) => (val ? parseInt(val, 10) : 50)),
    offset: z.string().optional().transform((val) => (val ? parseInt(val, 10) : 0)),
  }),
});

const categoryLeaderboardSchema = z.object({
  params: z.object({
    category: z.string(),
  }),
  query: z.object({
    limit: z.string().optional().transform((val) => (val ? parseInt(val, 10) : 50)),
  }),
});

const circleLeaderboardSchema = z.object({
  params: z.object({
    circleId: z.string().uuid(),
  }),
});

// Get user profile (XP, level, attributes, streak, etc.)
router.get(
  '/profile',
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;

    const profile = await gamificationService.getUserProfile(userId);

    return success(res, { profile });
  })
);

// Get user's XP history
router.get(
  '/xp-history',
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const limit = parseInt(req.query.limit as string) || 50;
    const offset = parseInt(req.query.offset as string) || 0;

    const transactions = await gamificationService.getXpHistory(userId, limit, offset);

    return success(res, { transactions });
  })
);

// Get user stats summary
router.get(
  '/stats',
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;

    const stats = await gamificationService.getUserStats(userId);

    return success(res, { stats });
  })
);

// Get rank tiers
router.get(
  '/ranks',
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const ranks = gamificationService.getRankTiers();

    return success(res, { ranks });
  })
);

// === LEADERBOARDS ===

// Get global leaderboard
router.get(
  '/leaderboards/global',
  validate(leaderboardQuerySchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { limit, offset } = req.query as { limit: number; offset: number };

    const leaderboard = await leaderboardService.getGlobalLeaderboard(userId, limit, offset);

    return success(res, { leaderboard });
  })
);

// Get friends leaderboard
router.get(
  '/leaderboards/friends',
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;

    const leaderboard = await leaderboardService.getFriendsLeaderboard(userId);

    return success(res, { leaderboard });
  })
);

// Get local leaderboard
router.get(
  '/leaderboards/local',
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const country = req.query.country as string | undefined;
    const city = req.query.city as string | undefined;
    const limit = parseInt(req.query.limit as string) || 50;

    const leaderboard = await leaderboardService.getLocalLeaderboard(userId, country, city, limit);

    return success(res, { leaderboard });
  })
);

// Get category leaderboard
router.get(
  '/leaderboards/category/:category',
  validate(categoryLeaderboardSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { category } = req.params;
    const limit = parseInt(req.query.limit as string) || 50;

    const leaderboard = await leaderboardService.getCategoryLeaderboard(userId, category, limit);

    return success(res, { leaderboard });
  })
);

// Get circle leaderboard
router.get(
  '/leaderboards/circle/:circleId',
  validate(circleLeaderboardSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { circleId } = req.params;

    const leaderboard = await leaderboardService.getCircleLeaderboard(userId, circleId);

    return success(res, { leaderboard });
  })
);

export { router as gamificationRouter };
