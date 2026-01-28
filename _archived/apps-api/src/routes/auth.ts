import { Router } from 'express';
import { authController } from '../controllers/auth.controller';
import { authMiddleware } from '../middleware/auth';
import { validate } from '../middleware/validation';
import { registerSchema } from '../schemas/auth.schema';

const router = Router();

// Register/login with Firebase token (requires auth middleware to verify token)
router.post('/register', authMiddleware, validate(registerSchema), authController.register);

// Verify token and get user info
router.post('/verify', authMiddleware, authController.verify);

export { router as authRouter };
