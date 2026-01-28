import { Router } from 'express';
import { conversationsController } from '../controllers/conversations.controller';
import { validate } from '../middleware/validation';
import { sendMessageSchema, createConversationSchema } from '../schemas/conversation.schema';
import { aiChatLimiter } from '../middleware/rateLimiter';

const router = Router();

router.get('/', conversationsController.list);
router.post('/', validate(createConversationSchema), conversationsController.create);
router.get('/:id', conversationsController.get);
router.post('/:id/messages', validate(sendMessageSchema), aiChatLimiter, conversationsController.sendMessage);

export { router as conversationsRouter };
