import { Router } from 'express';
import { notificationsController } from '../controllers/notifications.controller';

const router = Router();

router.get('/', notificationsController.list);
router.patch('/:id/read', notificationsController.markRead);
router.patch('/read-all', notificationsController.markAllRead);

export { router as notificationsRouter };
