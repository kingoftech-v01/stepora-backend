import { Router } from 'express';
import { Response, NextFunction } from 'express';
import { AuthRequest } from '../middleware/auth';
import { asyncHandler } from '../middleware/errorHandler';
import { rescueModeService } from '../services/rescueMode.service';
import { success } from '../utils/response';
import { z } from 'zod';
import { validate } from '../middleware/validation';

const router = Router();

const rescueResponseSchema = z.object({
  body: z.object({
    response: z.enum(['too_busy', 'lost_motivation', 'unclear_steps', 'other']),
    otherReason: z.string().optional(),
  }),
});

router.post(
  '/response',
  validate(rescueResponseSchema),
  asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { response, otherReason } = req.body;

    const message = await rescueModeService.handleRescueResponse(
      req.user!.id,
      response,
      otherReason
    );

    return success(res, { message });
  })
);

export { router as rescueModeRouter };
