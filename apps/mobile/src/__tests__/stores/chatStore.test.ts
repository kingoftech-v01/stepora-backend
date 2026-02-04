import { act } from 'react-test-renderer';
import { useChatStore } from '../../stores/chatStore';

beforeEach(() => {
  act(() => {
    useChatStore.getState().clearMessages();
    useChatStore.getState().setStreaming(false);
    useChatStore.getState().setError(null);
    useChatStore.getState().setLoading(false);
  });
});

describe('ChatStore', () => {
  describe('Initial state', () => {
    it('should have correct initial state', () => {
      const state = useChatStore.getState();

      expect(state.conversationId).toBeNull();
      expect(state.messages).toEqual([]);
      expect(state.isLoading).toBe(false);
      expect(state.isStreaming).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('setConversationId', () => {
    it('should set conversation id', () => {
      act(() => {
        useChatStore.getState().setConversationId('conv-1');
      });

      expect(useChatStore.getState().conversationId).toBe('conv-1');
    });

    it('should accept null to clear the conversation id', () => {
      act(() => {
        useChatStore.getState().setConversationId('conv-1');
        useChatStore.getState().setConversationId(null);
      });

      expect(useChatStore.getState().conversationId).toBeNull();
    });
  });

  describe('addMessage', () => {
    it('should add a message with auto-generated id and timestamp', () => {
      act(() => {
        useChatStore.getState().addMessage({
          role: 'user',
          content: 'I want to learn guitar',
        });
      });

      const messages = useChatStore.getState().messages;
      expect(messages).toHaveLength(1);
      expect(messages[0].content).toBe('I want to learn guitar');
      expect(messages[0].role).toBe('user');
      expect(messages[0].id).toBeDefined();
      expect(messages[0].timestamp).toBeDefined();
    });

    it('should use the provided id and timestamp when given', () => {
      const ts = new Date('2025-01-01T00:00:00Z');

      act(() => {
        useChatStore.getState().addMessage({
          id: 'custom-id',
          role: 'assistant',
          content: 'Hello!',
          timestamp: ts,
        });
      });

      const messages = useChatStore.getState().messages;
      expect(messages).toHaveLength(1);
      expect(messages[0].id).toBe('custom-id');
      expect(messages[0].timestamp).toEqual(ts);
    });

    it('should preserve the isStreaming flag', () => {
      act(() => {
        useChatStore.getState().addMessage({
          id: 'streaming-msg',
          role: 'assistant',
          content: '',
          isStreaming: true,
        });
      });

      const messages = useChatStore.getState().messages;
      expect(messages[0].isStreaming).toBe(true);
    });

    it('should append to existing messages', () => {
      act(() => {
        useChatStore.getState().addMessage({
          role: 'user',
          content: 'First',
        });
        useChatStore.getState().addMessage({
          role: 'assistant',
          content: 'Second',
        });
      });

      expect(useChatStore.getState().messages).toHaveLength(2);
      expect(useChatStore.getState().messages[0].content).toBe('First');
      expect(useChatStore.getState().messages[1].content).toBe('Second');
    });
  });

  describe('appendToMessage', () => {
    it('should append a token to the matching message', () => {
      act(() => {
        useChatStore.getState().addMessage({
          id: 'msg-1',
          role: 'assistant',
          content: 'Hello',
        });
        useChatStore.getState().appendToMessage('msg-1', ' world');
      });

      expect(useChatStore.getState().messages[0].content).toBe('Hello world');
    });

    it('should not modify other messages', () => {
      act(() => {
        useChatStore.getState().addMessage({
          id: 'msg-1',
          role: 'user',
          content: 'User message',
        });
        useChatStore.getState().addMessage({
          id: 'msg-2',
          role: 'assistant',
          content: 'AI ',
        });
        useChatStore.getState().appendToMessage('msg-2', 'response');
      });

      const messages = useChatStore.getState().messages;
      expect(messages[0].content).toBe('User message');
      expect(messages[1].content).toBe('AI response');
    });
  });

  describe('finalizeMessage', () => {
    it('should set isStreaming to false on the matching message', () => {
      act(() => {
        useChatStore.getState().addMessage({
          id: 'msg-1',
          role: 'assistant',
          content: 'Streamed content',
          isStreaming: true,
        });
        useChatStore.getState().finalizeMessage('msg-1');
      });

      expect(useChatStore.getState().messages[0].isStreaming).toBe(false);
    });

    it('should replace the local id with the server message id', () => {
      act(() => {
        useChatStore.getState().addMessage({
          id: 'local-temp',
          role: 'assistant',
          content: 'Done',
          isStreaming: true,
        });
        useChatStore.getState().finalizeMessage('local-temp', 'server-uuid-123');
      });

      expect(useChatStore.getState().messages[0].id).toBe('server-uuid-123');
      expect(useChatStore.getState().messages[0].isStreaming).toBe(false);
    });
  });

  describe('setMessages', () => {
    it('should replace all messages', () => {
      act(() => {
        useChatStore.getState().addMessage({
          role: 'user',
          content: 'Old',
        });
      });

      const newMessages = [
        { id: 'msg-new', role: 'user' as const, content: 'New', timestamp: new Date() },
      ];

      act(() => {
        useChatStore.getState().setMessages(newMessages);
      });

      expect(useChatStore.getState().messages).toHaveLength(1);
      expect(useChatStore.getState().messages[0].content).toBe('New');
    });
  });

  describe('setLoading', () => {
    it('should set loading state', () => {
      act(() => {
        useChatStore.getState().setLoading(true);
      });

      expect(useChatStore.getState().isLoading).toBe(true);
    });

    it('should unset loading state', () => {
      act(() => {
        useChatStore.getState().setLoading(true);
        useChatStore.getState().setLoading(false);
      });

      expect(useChatStore.getState().isLoading).toBe(false);
    });
  });

  describe('setStreaming', () => {
    it('should set streaming state', () => {
      act(() => {
        useChatStore.getState().setStreaming(true);
      });

      expect(useChatStore.getState().isStreaming).toBe(true);
    });

    it('should unset streaming state', () => {
      act(() => {
        useChatStore.getState().setStreaming(true);
        useChatStore.getState().setStreaming(false);
      });

      expect(useChatStore.getState().isStreaming).toBe(false);
    });
  });

  describe('setError', () => {
    it('should set an error message', () => {
      act(() => {
        useChatStore.getState().setError('Connection lost');
      });

      expect(useChatStore.getState().error).toBe('Connection lost');
    });

    it('should clear the error when set to null', () => {
      act(() => {
        useChatStore.getState().setError('Some error');
        useChatStore.getState().setError(null);
      });

      expect(useChatStore.getState().error).toBeNull();
    });
  });

  describe('clearMessages', () => {
    it('should reset messages and conversationId', () => {
      act(() => {
        useChatStore.getState().setConversationId('conv-1');
        useChatStore.getState().addMessage({
          role: 'user',
          content: 'Hello',
        });
        useChatStore.getState().setLoading(true);
      });

      act(() => {
        useChatStore.getState().clearMessages();
      });

      const state = useChatStore.getState();
      expect(state.conversationId).toBeNull();
      expect(state.messages).toEqual([]);
    });
  });
});
