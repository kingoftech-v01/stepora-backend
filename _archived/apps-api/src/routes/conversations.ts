import { Router, Response, NextFunction } from 'express';
import { conversationService } from '../services/conversation.service';
import { userService } from '../services/user.service';
import { createConversationSchema, sendMessageSchema } from '../validators';
import { AuthenticatedRequest } from '../middleware/auth';
import { AppError } from '../middleware/errorHandler';

export const conversationsRouter = Router();

// GET /api/conversations - Get all conversations
conversationsRouter.get(
  '/',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const { type, dreamId, limit, offset } = req.query;

      const result = await conversationService.findAllByUser(req.userId!, {
        type: type as any,
        dreamId: dreamId as string,
        limit: limit ? parseInt(limit as string, 10) : undefined,
        offset: offset ? parseInt(offset as string, 10) : undefined,
      });

      res.json({
        success: true,
        data: {
          conversations: result.conversations,
          total: result.total,
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

// GET /api/conversations/:id - Get a specific conversation
conversationsRouter.get(
  '/:id',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const conversation = await conversationService.findById(
        req.params.id,
        req.userId!
      );

      if (!conversation) {
        throw new AppError('Conversation not found', 404);
      }

      res.json({
        success: true,
        data: { conversation },
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/conversations - Create a new conversation
conversationsRouter.post(
  '/',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const data = createConversationSchema.parse(req.body);

      const conversation = await conversationService.create(req.userId!, {
        type: data.type as any,
        dreamId: data.dreamId,
      });

      res.status(201).json({
        success: true,
        data: { conversation },
      });
    } catch (error) {
      next(error);
    }
  }
);

// POST /api/conversations/:id/messages - Send a message
conversationsRouter.post(
  '/:id/messages',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      const data = sendMessageSchema.parse(req.body);

      // Get user context
      const user = await userService.findById(req.userId!);
      if (!user) {
        throw new AppError('User not found', 404);
      }

      const workSchedule = user.workSchedule as {
        workDays: number[];
        startTime: string;
        endTime: string;
      } | null;

      const { userMessage, assistantMessage } =
        await conversationService.sendMessage(
          req.params.id,
          req.userId!,
          data.content,
          {
            userName: user.displayName || 'Utilisateur',
            timezone: user.timezone,
            workSchedule: workSchedule || undefined,
          }
        );

      res.json({
        success: true,
        data: {
          userMessage,
          assistantMessage,
        },
      });
    } catch (error) {
      next(error);
    }
  }
);

// DELETE /api/conversations/:id - Delete a conversation
conversationsRouter.delete(
  '/:id',
  async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    try {
      await conversationService.delete(req.params.id, req.userId!);

      res.json({
        success: true,
        message: 'Conversation deleted successfully',
      });
    } catch (error) {
      next(error);
    }
  }
);
