import { describe, it, expect, vi, beforeEach } from 'vitest';
import { conversationService } from '../../services/conversation.service';
import { prisma } from '../../config/database';
import { aiService } from '../../services/ai.service';

vi.mock('../../services/ai.service', () => ({
  aiService: {
    chat: vi.fn(),
    chatStream: vi.fn(),
  },
}));

const mockPrisma = vi.mocked(prisma);
const mockAiService = vi.mocked(aiService);

describe('ConversationService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockConversation = {
    id: 'conv-1',
    userId: 'user-1',
    dreamId: 'dream-1',
    type: 'dream_creation',
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  const mockConversationWithMessages = {
    ...mockConversation,
    messages: [
      {
        id: 'msg-1',
        conversationId: 'conv-1',
        role: 'user',
        content: 'I want to learn guitar',
        metadata: null,
        createdAt: new Date(),
      },
      {
        id: 'msg-2',
        conversationId: 'conv-1',
        role: 'assistant',
        content: 'Tell me more about your goal!',
        metadata: { tokensUsed: 100 },
        createdAt: new Date(),
      },
    ],
  };

  describe('findById', () => {
    it('should return conversation with messages', async () => {
      mockPrisma.conversation.findFirst.mockResolvedValue(
        mockConversationWithMessages as any
      );

      const result = await conversationService.findById('conv-1', 'user-1');

      expect(result).toEqual(mockConversationWithMessages);
      expect(mockPrisma.conversation.findFirst).toHaveBeenCalledWith({
        where: { id: 'conv-1', userId: 'user-1' },
        include: {
          messages: { orderBy: { createdAt: 'asc' } },
        },
      });
    });

    it('should return null when not found', async () => {
      mockPrisma.conversation.findFirst.mockResolvedValue(null);

      const result = await conversationService.findById('nonexistent', 'user-1');

      expect(result).toBeNull();
    });
  });

  describe('findAllByUser', () => {
    it('should return all conversations for user', async () => {
      mockPrisma.conversation.findMany.mockResolvedValue([
        mockConversationWithMessages,
      ] as any);
      mockPrisma.conversation.count.mockResolvedValue(1);

      const result = await conversationService.findAllByUser('user-1');

      expect(result.conversations).toHaveLength(1);
      expect(result.total).toBe(1);
    });

    it('should filter by type', async () => {
      mockPrisma.conversation.findMany.mockResolvedValue([]);
      mockPrisma.conversation.count.mockResolvedValue(0);

      await conversationService.findAllByUser('user-1', { type: 'check_in' });

      expect(mockPrisma.conversation.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: { userId: 'user-1', type: 'check_in' },
        })
      );
    });

    it('should filter by dreamId', async () => {
      mockPrisma.conversation.findMany.mockResolvedValue([]);
      mockPrisma.conversation.count.mockResolvedValue(0);

      await conversationService.findAllByUser('user-1', { dreamId: 'dream-1' });

      expect(mockPrisma.conversation.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: { userId: 'user-1', dreamId: 'dream-1' },
        })
      );
    });
  });

  describe('create', () => {
    it('should create a new conversation', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue({ id: 'dream-1', userId: 'user-1' } as any);
      mockPrisma.conversation.create.mockResolvedValue(mockConversation as any);

      const result = await conversationService.create('user-1', {
        type: 'dream_creation',
        dreamId: 'dream-1',
      });

      expect(result).toEqual(mockConversation);
    });

    it('should create conversation without dream', async () => {
      mockPrisma.conversation.create.mockResolvedValue({
        ...mockConversation,
        dreamId: null,
      } as any);

      const result = await conversationService.create('user-1', {
        type: 'general',
      });

      expect(result).toBeDefined();
    });

    it('should throw when dream does not belong to user', async () => {
      mockPrisma.dream.findFirst.mockResolvedValue(null);

      await expect(
        conversationService.create('user-1', {
          type: 'dream_creation',
          dreamId: 'nonexistent',
        })
      ).rejects.toThrow('Dream not found');
    });
  });

  describe('sendMessage', () => {
    it('should send message and get AI response', async () => {
      mockAiService.chat.mockResolvedValue({
        content: 'Hello! Tell me about your dream.',
        tokensUsed: 150,
      });

      mockPrisma.conversation.findFirst.mockResolvedValue(
        mockConversationWithMessages as any
      );
      mockPrisma.message.create
        .mockResolvedValueOnce({
          id: 'msg-3',
          conversationId: 'conv-1',
          role: 'user',
          content: 'I want to learn in 6 months',
          metadata: null,
          createdAt: new Date(),
        } as any)
        .mockResolvedValueOnce({
          id: 'msg-4',
          conversationId: 'conv-1',
          role: 'assistant',
          content: 'Hello! Tell me about your dream.',
          metadata: { tokensUsed: 150 },
          createdAt: new Date(),
        } as any);
      mockPrisma.conversation.update.mockResolvedValue(mockConversation as any);

      const result = await conversationService.sendMessage(
        'conv-1',
        'user-1',
        'I want to learn in 6 months',
        {
          userName: 'Test User',
          timezone: 'Europe/Paris',
        }
      );

      expect(result.userMessage.role).toBe('user');
      expect(result.assistantMessage.role).toBe('assistant');
      expect(mockPrisma.message.create).toHaveBeenCalledTimes(2);
    });

    it('should throw when conversation not found', async () => {
      mockPrisma.conversation.findFirst.mockResolvedValue(null);

      await expect(
        conversationService.sendMessage('nonexistent', 'user-1', 'Hello', {
          userName: 'Test',
          timezone: 'UTC',
        })
      ).rejects.toThrow('Conversation not found');
    });
  });

  describe('delete', () => {
    it('should delete conversation', async () => {
      mockPrisma.conversation.findFirst.mockResolvedValue(mockConversation as any);
      mockPrisma.conversation.delete.mockResolvedValue(mockConversation as any);

      await conversationService.delete('conv-1', 'user-1');

      expect(mockPrisma.conversation.delete).toHaveBeenCalledWith({
        where: { id: 'conv-1' },
      });
    });

    it('should throw when conversation not found', async () => {
      mockPrisma.conversation.findFirst.mockResolvedValue(null);

      await expect(
        conversationService.delete('nonexistent', 'user-1')
      ).rejects.toThrow('Conversation not found');
    });
  });

  describe('streamMessage', () => {
    it('should stream message and create assistant message', async () => {
      mockPrisma.conversation.findFirst.mockResolvedValue(
        mockConversationWithMessages as any
      );
      mockPrisma.message.create
        .mockResolvedValueOnce({
          id: 'msg-3',
          conversationId: 'conv-1',
          role: 'user',
          content: 'Tell me more',
          metadata: null,
          createdAt: new Date(),
        } as any)
        .mockResolvedValueOnce({
          id: 'msg-4',
          conversationId: 'conv-1',
          role: 'assistant',
          content: 'Here is more info',
          metadata: { model: 'gpt-4-turbo-preview' },
          createdAt: new Date(),
        } as any);
      mockPrisma.conversation.update.mockResolvedValue(mockConversation as any);

      // Mock chatStream as async generator
      async function* mockStream() {
        yield 'Here ';
        yield 'is ';
        yield 'more ';
        yield 'info';
      }
      mockAiService.chatStream.mockReturnValue(mockStream() as any);

      const chunks: any[] = [];
      for await (const chunk of conversationService.streamMessage(
        'conv-1',
        'user-1',
        'Tell me more',
        { userName: 'Test', timezone: 'UTC' }
      )) {
        chunks.push(chunk);
      }

      // First yield is the user message (done), then 4 chunks, then final done
      expect(chunks[0].type).toBe('done');
      expect(chunks[0].message.role).toBe('user');
      expect(chunks[1]).toEqual({ type: 'chunk', content: 'Here ' });
      expect(chunks[2]).toEqual({ type: 'chunk', content: 'is ' });
      expect(chunks[3]).toEqual({ type: 'chunk', content: 'more ' });
      expect(chunks[4]).toEqual({ type: 'chunk', content: 'info' });
      expect(chunks[5].type).toBe('done');
      expect(chunks[5].message.role).toBe('assistant');
    });

    it('should throw when conversation not found for streaming', async () => {
      mockPrisma.conversation.findFirst.mockResolvedValue(null);

      const generator = conversationService.streamMessage(
        'nonexistent',
        'user-1',
        'Hello',
        { userName: 'Test', timezone: 'UTC' }
      );

      await expect(generator.next()).rejects.toThrow('Conversation not found');
    });
  });

  describe('getLatestByDream', () => {
    it('should return latest conversation for a dream', async () => {
      mockPrisma.conversation.findFirst.mockResolvedValue(
        mockConversationWithMessages as any
      );

      const result = await conversationService.getLatestByDream(
        'dream-1',
        'user-1'
      );

      expect(result).toEqual(mockConversationWithMessages);
      expect(mockPrisma.conversation.findFirst).toHaveBeenCalledWith({
        where: { dreamId: 'dream-1', userId: 'user-1' },
        include: {
          messages: { orderBy: { createdAt: 'asc' } },
        },
        orderBy: { updatedAt: 'desc' },
      });
    });
  });
});
