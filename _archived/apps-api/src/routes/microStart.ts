import { Router } from 'express';
import { Response, NextFunction } from 'express';
import { AuthRequest } from '../middleware/auth';
import { asyncHandler } from '../middleware/errorHandler';
import { microStartService } from '../services/microStart.service';
import { success } from '../utils/response';
import { z } from 'zod';
import { validate } from '../middleware/validation';
import { NotFoundError, AuthorizationError } from '../utils/errors';
import { prisma } from '../utils/prisma';

const router = Router();

const generateMicroStartSchema = z.object({
  params: z.object({
    dreamId: z.string().uuid(),
  }),
});

const completeMicroStartSchema = z.object({
  params: z.object({
    dreamId: z.string().uuid(),
  }),
});

router.post(
  '/:dreamId/generate',
  validate(generateMicroStartSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { dreamId } = req.params;

    // Check ownership
    const dream = await prisma.dream.findUnique({
      where: { id: dreamId },
      select: { userId: true, title: true, description: true },
    });

    if (!dream) {
      throw new NotFoundError('Dream not found');
    }

    if (dream.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    const microTask = await microStartService.generateMicroStart(dream.title, dream.description);

    return success(res, { microTask });
  })
);

router.post(
  '/:dreamId/complete',
  validate(completeMicroStartSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { dreamId } = req.params;

    // Check ownership
    const dream = await prisma.dream.findUnique({
      where: { id: dreamId },
      select: { userId: true },
    });

    if (!dream) {
      throw new NotFoundError('Dream not found');
    }

    if (dream.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    await microStartService.saveMicroStartCompletion(req.user!.id, dreamId);

    return success(res, null, 'Bravo! Premier pas accompli! 🎉');
  })
);

export { router as microStartRouter };
