import { Router } from 'express';
import { Response, NextFunction } from 'express';
import { AuthRequest } from '../middleware/auth';
import { asyncHandler } from '../middleware/errorHandler';
import { circleService } from '../services/circle.service';
import { success } from '../utils/response';
import { z } from 'zod';
import { validate } from '../middleware/validation';

const router = Router();

const createCircleSchema = z.object({
  body: z.object({
    name: z.string().min(1).max(100),
    description: z.string().min(1).max(500),
    category: z.string().optional(),
    isPublic: z.boolean(),
    maxMembers: z.number().min(2).max(50).optional(),
  }),
});

const getCirclesSchema = z.object({
  query: z.object({
    filter: z.enum(['my', 'public', 'recommended']).optional(),
    category: z.string().optional(),
    limit: z.string().optional().transform((val) => (val ? parseInt(val, 10) : 20)),
  }),
});

const circleIdSchema = z.object({
  params: z.object({
    circleId: z.string().uuid(),
  }),
});

const createChallengeSchema = z.object({
  params: z.object({
    circleId: z.string().uuid(),
  }),
  body: z.object({
    title: z.string().min(1).max(100),
    description: z.string().min(1).max(500),
    startDate: z.string().transform((val) => new Date(val)),
    endDate: z.string().transform((val) => new Date(val)),
    targetType: z.string(),
    targetValue: z.number(),
  }),
});

const joinChallengeSchema = z.object({
  params: z.object({
    challengeId: z.string().uuid(),
  }),
});

const circleFeedSchema = z.object({
  params: z.object({
    circleId: z.string().uuid(),
  }),
  query: z.object({
    limit: z.string().optional().transform((val) => (val ? parseInt(val, 10) : 20)),
  }),
});

const createPostSchema = z.object({
  params: z.object({
    circleId: z.string().uuid(),
  }),
  body: z.object({
    content: z.string().min(1).max(1000),
  }),
});

// ===== CIRCLES =====

// Create circle
router.post(
  '/',
  validate(createCircleSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const circleData = req.body;

    const circle = await circleService.createCircle(userId, circleData);

    return success(res, { circle }, 'Cercle créé avec succès');
  })
);

// Get circles (with filters)
router.get(
  '/',
  validate(getCirclesSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { filter, category, limit } = req.query as {
      filter?: 'my' | 'public' | 'recommended';
      category?: string;
      limit: number;
    };

    const circles = await circleService.getCircles(userId, filter, category, limit);

    return success(res, { circles });
  })
);

// Get circle details
router.get(
  '/:circleId',
  validate(circleIdSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { circleId } = req.params;

    const circle = await circleService.getCircle(userId, circleId);

    return success(res, { circle });
  })
);

// Join circle
router.post(
  '/:circleId/join',
  validate(circleIdSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { circleId } = req.params;

    await circleService.joinCircle(userId, circleId);

    return success(res, null, 'Tu as rejoint le cercle');
  })
);

// Leave circle
router.post(
  '/:circleId/leave',
  validate(circleIdSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { circleId } = req.params;

    await circleService.leaveCircle(userId, circleId);

    return success(res, null, 'Tu as quitté le cercle');
  })
);

// ===== CHALLENGES =====

// Create challenge in circle
router.post(
  '/:circleId/challenges',
  validate(createChallengeSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { circleId } = req.params;
    const challengeData = req.body;

    const challenge = await circleService.createChallenge(userId, circleId, challengeData);

    return success(res, { challenge }, 'Challenge créé avec succès');
  })
);

// Join challenge
router.post(
  '/challenges/:challengeId/join',
  validate(joinChallengeSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { challengeId } = req.params;

    await circleService.joinChallenge(userId, challengeId);

    return success(res, null, 'Tu participes au challenge');
  })
);

// ===== CIRCLE FEED =====

// Get circle feed
router.get(
  '/:circleId/feed',
  validate(circleFeedSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { circleId } = req.params;
    const limit = parseInt(req.query.limit as string) || 20;

    const feed = await circleService.getCircleFeed(userId, circleId, limit);

    return success(res, { feed });
  })
);

// Create post in circle
router.post(
  '/:circleId/posts',
  validate(createPostSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { circleId } = req.params;
    const { content } = req.body;

    const post = await circleService.createPost(userId, circleId, content);

    return success(res, { post }, 'Post créé avec succès');
  })
);

export { router as circleRouter };
