import { Router } from 'express';
import { Response, NextFunction } from 'express';
import { AuthRequest } from '../middleware/auth';
import { asyncHandler } from '../middleware/errorHandler';
import { buddyService } from '../services/buddy.service';
import { success } from '../utils/response';
import { z } from 'zod';
import { validate } from '../middleware/validation';

const router = Router();

const findMatchSchema = z.object({
  body: z.object({
    dreamCategory: z.string().optional(),
    timeframe: z.number().optional(),
    timezone: z.string().optional(),
    language: z.string().optional(),
  }),
});

const createPairingSchema = z.object({
  body: z.object({
    partnerId: z.string().uuid(),
  }),
});

const endPairingSchema = z.object({
  params: z.object({
    buddyId: z.string().uuid(),
  }),
});

const encourageBuddySchema = z.object({
  params: z.object({
    buddyId: z.string().uuid(),
  }),
  body: z.object({
    message: z.string().optional(),
  }),
});

const buddyProgressSchema = z.object({
  params: z.object({
    buddyId: z.string().uuid(),
  }),
});

// Find buddy match
router.post(
  '/find-match',
  validate(findMatchSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { dreamCategory, timeframe, timezone, language } = req.body;

    const match = await buddyService.findBuddyMatch({
      userId,
      dreamCategory,
      timeframe,
      timezone,
      language,
    });

    if (!match) {
      return success(res, { match: null }, 'Aucun buddy trouvé pour le moment');
    }

    return success(res, { match });
  })
);

// Create buddy pairing
router.post(
  '/pair',
  validate(createPairingSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { partnerId } = req.body;

    await buddyService.createBuddyPairing(userId, partnerId);

    return success(res, null, 'Buddy pairing créé avec succès');
  })
);

// Get current buddy
router.get(
  '/current',
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;

    const buddy = await buddyService.getCurrentBuddy(userId);

    return success(res, { buddy });
  })
);

// End buddy pairing
router.delete(
  '/:buddyId',
  validate(endPairingSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { buddyId } = req.params;

    await buddyService.endBuddyPairing(userId, buddyId);

    return success(res, null, 'Buddy pairing terminé');
  })
);

// Encourage buddy
router.post(
  '/:buddyId/encourage',
  validate(encourageBuddySchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { buddyId } = req.params;
    const { message } = req.body;

    await buddyService.encourageBuddy(userId, buddyId, message);

    return success(res, null, 'Encouragement envoyé');
  })
);

// Get buddy progress comparison
router.get(
  '/:buddyId/progress',
  validate(buddyProgressSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const { buddyId } = req.params;

    const progress = await buddyService.getBuddyProgress(userId, buddyId);

    return success(res, { progress });
  })
);

export { router as buddyRouter };
