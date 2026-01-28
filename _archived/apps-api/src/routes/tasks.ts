import { Router } from 'express';
import { tasksController } from '../controllers/tasks.controller';
import { validate } from '../middleware/validation';
import { updateTaskSchema, taskIdSchema, listTasksSchema } from '../schemas/task.schema';

const router = Router();

router.get('/', validate(listTasksSchema), tasksController.list);
router.patch('/:id', validate(taskIdSchema), validate(updateTaskSchema), tasksController.update);
router.post('/:id/complete', validate(taskIdSchema), tasksController.complete);
router.post('/:id/skip', validate(taskIdSchema), tasksController.skip);

export { router as tasksRouter };
