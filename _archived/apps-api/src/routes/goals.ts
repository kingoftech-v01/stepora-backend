import { Router } from 'express';
import { goalsController } from '../controllers/goals.controller';

const router = Router();

router.get('/', goalsController.list);
router.get('/:id', goalsController.get);
router.patch('/:id', goalsController.update);
router.post('/:id/complete', goalsController.complete);

export { router as goalsRouter };
