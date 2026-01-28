import { Router } from 'express';
import { usersController } from '../controllers/users.controller';
import { validate } from '../middleware/validation';
import { updateProfileSchema } from '../schemas/auth.schema';
import { z } from 'zod';

const router = Router();

// Get current user profile
router.get('/me', usersController.getMe);

// Update current user profile
router.patch('/me', validate(updateProfileSchema), usersController.updateMe);

// Register FCM token for push notifications
const fcmTokenSchema = z.object({
  body: z.object({
    token: z.string(),
    platform: z.enum(['ios', 'android']),
  }),
});

router.post('/fcm-token', validate(fcmTokenSchema), usersController.registerFcmToken);

export { router as usersRouter };
