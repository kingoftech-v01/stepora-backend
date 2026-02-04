import { prisma } from '../config/database';
import { Conversation, Message, Prisma } from '@prisma/client';
import { aiService } from './ai.service';

export type ConversationType = 'dream_creation' | 'planning' | 'check_in' | 'adjustment' | 'general';

export interface CreateConversationData {
  type: ConversationType;
  dreamId?: string;
}

export type ConversationWithMessages = Conversation & {
  messages: Message[];
};

export interface UserContext {
  userName: string;
  timezone: string;
  workSchedule?: {
    workDays: number[];
    startTime: string;
    endTime: string;
  };
  availableHoursPerWeek?: number;
}

export class ConversationService {
  async findById(id: string, userId: string): Promise<ConversationWithMessages | null> {
    return prisma.conversation.findFirst({
      where: { id, userId },
      include: {
        messages: {
          orderBy: { createdAt: 'asc' },
        },
      },
    });
  }

  async findAllByUser(
    userId: string,
    options?: {
      type?: ConversationType;
      dreamId?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<{ conversations: ConversationWithMessages[]; total: number }> {
    const where: Prisma.ConversationWhereInput = { userId };

    if (options?.type) where.type = options.type;
    if (options?.dreamId) where.dreamId = options.dreamId;

    const [conversations, total] = await Promise.all([
      prisma.conversation.findMany({
        where,
        include: {
          messages: {
            orderBy: { createdAt: 'asc' },
          },
        },
        orderBy: { updatedAt: 'desc' },
        take: options?.limit || 20,
        skip: options?.offset || 0,
      }),
      prisma.conversation.count({ where }),
    ]);

    return { conversations, total };
  }

  async create(userId: string, data: CreateConversationData): Promise<Conversation> {
    // Verify dream belongs to user if provided
    if (data.dreamId) {
      const dream = await prisma.dream.findFirst({
        where: { id: data.dreamId, userId },
      });

      if (!dream) {
        throw new Error('Dream not found');
      }
    }

    return prisma.conversation.create({
      data: {
        userId,
        type: data.type,
        dreamId: data.dreamId,
      },
    });
  }

  async sendMessage(
    conversationId: string,
    userId: string,
    content: string,
    userContext: UserContext
  ): Promise<{ userMessage: Message; assistantMessage: Message }> {
    const conversation = await prisma.conversation.findFirst({
      where: { id: conversationId, userId },
      include: {
        messages: {
          orderBy: { createdAt: 'asc' },
          select: { role: true, content: true },
        },
      },
    });

    if (!conversation) {
      throw new Error('Conversation not found');
    }

    // Create user message
    const userMessage = await prisma.message.create({
      data: {
        conversationId,
        role: 'user',
        content,
      },
    });

    // Get AI response
    const chatType = conversation.type === 'check_in' ? 'checkIn' : 'dreamCreation';
    const aiResponse = await aiService.chat(
      conversation.messages,
      content,
      userContext,
      chatType
    );

    // Create assistant message
    const assistantMessage = await prisma.message.create({
      data: {
        conversationId,
        role: 'assistant',
        content: aiResponse.content,
        metadata: {
          tokensUsed: aiResponse.tokensUsed,
          model: 'gpt-4-turbo-preview',
        },
      },
    });

    // Update conversation timestamp
    await prisma.conversation.update({
      where: { id: conversationId },
      data: { updatedAt: new Date() },
    });

    return { userMessage, assistantMessage };
  }

  async *streamMessage(
    conversationId: string,
    userId: string,
    content: string,
    userContext: UserContext
  ): AsyncGenerator<{ type: 'chunk' | 'done'; content?: string; message?: Message }> {
    const conversation = await prisma.conversation.findFirst({
      where: { id: conversationId, userId },
      include: {
        messages: {
          orderBy: { createdAt: 'asc' },
          select: { role: true, content: true },
        },
      },
    });

    if (!conversation) {
      throw new Error('Conversation not found');
    }

    // Create user message
    const userMessage = await prisma.message.create({
      data: {
        conversationId,
        role: 'user',
        content,
      },
    });

    yield { type: 'done', message: userMessage };

    // Stream AI response
    let fullContent = '';
    for await (const chunk of aiService.chatStream(
      conversation.messages,
      content,
      userContext
    )) {
      fullContent += chunk;
      yield { type: 'chunk', content: chunk };
    }

    // Create assistant message
    const assistantMessage = await prisma.message.create({
      data: {
        conversationId,
        role: 'assistant',
        content: fullContent,
        metadata: {
          model: 'gpt-4-turbo-preview',
        },
      },
    });

    // Update conversation timestamp
    await prisma.conversation.update({
      where: { id: conversationId },
      data: { updatedAt: new Date() },
    });

    yield { type: 'done', message: assistantMessage };
  }

  async delete(id: string, userId: string): Promise<void> {
    const conversation = await prisma.conversation.findFirst({
      where: { id, userId },
    });

    if (!conversation) {
      throw new Error('Conversation not found');
    }

    await prisma.conversation.delete({
      where: { id },
    });
  }

  async getLatestByDream(dreamId: string, userId: string): Promise<ConversationWithMessages | null> {
    return prisma.conversation.findFirst({
      where: { dreamId, userId },
      include: {
        messages: {
          orderBy: { createdAt: 'asc' },
        },
      },
      orderBy: { updatedAt: 'desc' },
    });
  }
}

export const conversationService = new ConversationService();
