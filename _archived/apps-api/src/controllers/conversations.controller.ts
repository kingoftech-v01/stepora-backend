import { Response, NextFunction } from 'express';
import { AuthRequest } from '../middleware/auth';
import { prisma } from '../utils/prisma';
import { success } from '../utils/response';
import { asyncHandler } from '../middleware/errorHandler';
import { NotFoundError, AuthorizationError } from '../utils/errors';
import { aiService } from '../services/ai.service';
import { io } from '../index';

class ConversationsController {
  list = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const conversations = await prisma.conversation.findMany({
      where: { userId: req.user!.id },
      include: {
        dream: { select: { title: true } },
        messages: {
          orderBy: { createdAt: 'desc' },
          take: 1,
        },
      },
      orderBy: { updatedAt: 'desc' },
    });

    return success(res, { conversations });
  });

  create = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { dreamId, type } = req.body;

    const conversation = await prisma.conversation.create({
      data: {
        userId: req.user!.id,
        dreamId,
        type: type || 'general',
      },
    });

    return success(res, { conversation }, 'Conversation created', 201);
  });

  get = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { id } = req.params;

    const conversation = await prisma.conversation.findUnique({
      where: { id },
      include: {
        messages: {
          orderBy: { createdAt: 'asc' },
        },
        dream: { select: { title: true, description: true } },
      },
    });

    if (!conversation) {
      throw new NotFoundError('Conversation not found');
    }

    if (conversation.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    return success(res, { conversation });
  });

  sendMessage = asyncHandler(async (req: AuthRequest, res: Response, next: NextFunction) => {
    const { id } = req.params;
    const { content } = req.body;

    // Check ownership
    const conversation = await prisma.conversation.findUnique({
      where: { id },
      include: {
        messages: {
          orderBy: { createdAt: 'asc' },
          take: 10,
        },
      },
    });

    if (!conversation) {
      throw new NotFoundError('Conversation not found');
    }

    if (conversation.userId !== req.user!.id) {
      throw new AuthorizationError('Access denied');
    }

    // Save user message
    const userMessage = await prisma.message.create({
      data: {
        conversationId: id,
        role: 'user',
        content,
      },
    });

    // Get AI response
    const history = conversation.messages.map((msg) => ({
      role: msg.role as 'user' | 'assistant' | 'system',
      content: msg.content,
    }));

    const aiResponse = await aiService.chat(
      [...history, { role: 'user', content }],
      conversation.type === 'dream_creation' ? 'dreamCreation' : 'general'
    );

    // Save AI message
    const assistantMessage = await prisma.message.create({
      data: {
        conversationId: id,
        role: 'assistant',
        content: aiResponse.response,
        metadata: {
          tokensUsed: aiResponse.tokensUsed,
        },
      },
    });

    // Update conversation timestamp
    await prisma.conversation.update({
      where: { id },
      data: { updatedAt: new Date() },
    });

    return success(res, {
      userMessage,
      assistantMessage,
    });
  });
}

export const conversationsController = new ConversationsController();
