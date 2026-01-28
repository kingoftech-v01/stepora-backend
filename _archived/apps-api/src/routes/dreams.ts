import { Router } from 'express';
import { dreamsController } from '../controllers/dreams.controller';
import { validate } from '../middleware/validation';
import { createDreamSchema, updateDreamSchema, generatePlanSchema, dreamIdSchema } from '../schemas/dream.schema';
import { planGenerationLimiter } from '../middleware/rateLimiter';

const router = Router();

// List user's dreams
router.get('/', dreamsController.list);

// Create dream
router.post('/', validate(createDreamSchema), dreamsController.create);

// Get dream details
router.get('/:id', validate(dreamIdSchema), dreamsController.get);

// Update dream
router.patch('/:id', validate(dreamIdSchema), validate(updateDreamSchema), dreamsController.update);

// Delete dream
router.delete('/:id', validate(dreamIdSchema), dreamsController.delete);

// Generate plan with AI (rate limited)
router.post('/:id/generate-plan', validate(dreamIdSchema), validate(generatePlanSchema), planGenerationLimiter, dreamsController.generatePlan);

// Mark dream as completed
router.post('/:id/complete', validate(dreamIdSchema), dreamsController.complete);

export { router as dreamsRouter };
