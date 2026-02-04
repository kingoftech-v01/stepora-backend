import { act } from 'react-test-renderer';
import { useChatStore } from '../../stores/chatStore';

beforeEach(() => {
  act(() => {
    useChatStore.getState().clearChat();
  });
});

describe('ChatStore', () => {
  describe('Initial state', () => {
    it('should have correct initial state', () => {
      const state = useChatStore.getState();

      expect(state.currentConversation).toBeNull();
      expect(state.messages).toEqual([]);
      expect(state.isLoading).toBe(false);
      expect(state.isStreaming).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('setConversation', () => {
    it('should set conversation and its messages', () => {
      const conversation = {
        id: 'conv-1',
        type: 'dream_creation' as const,
        messages: [
          { id: 'msg-1', role: 'user' as const, content: 'Hello', timestamp: new Date() },
        ],
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      act(() => {
        useChatStore.getState().setConversation(conversation);
      });

      const state = useChatStore.getState();
      expect(state.currentConversation).toEqual(conversation);
      expect(state.messages).toHaveLength(1);
    });

    it('should handle null conversation', () => {
      act(() => {
        useChatStore.getState().setConversation(null);
      });

      const state = useChatStore.getState();
      expect(state.currentConversation).toBeNull();
      expect(state.messages).toEqual([]);
    });
  });

  describe('addMessage', () => {
    it('should add a message to the list', () => {
      const message = {
        id: 'msg-1',
        role: 'user' as const,
        content: 'I want to learn guitar',
        timestamp: new Date(),
      };

      act(() => {
        useChatStore.getState().addMessage(message);
      });

      expect(useChatStore.getState().messages).toHaveLength(1);
      expect(useChatStore.getState().messages[0].content).toBe('I want to learn guitar');
    });

    it('should append to existing messages', () => {
      act(() => {
        useChatStore.getState().addMessage({
          id: 'msg-1',
          role: 'user',
          content: 'First',
          timestamp: new Date(),
        });
        useChatStore.getState().addMessage({
          id: 'msg-2',
          role: 'assistant',
          content: 'Second',
          timestamp: new Date(),
        });
      });

      expect(useChatStore.getState().messages).toHaveLength(2);
    });
  });

  describe('updateLastMessage', () => {
    it('should append content to the last message', () => {
      act(() => {
        useChatStore.getState().addMessage({
          id: 'msg-1',
          role: 'assistant',
          content: 'Hello',
          timestamp: new Date(),
        });
      });

      act(() => {
        useChatStore.getState().updateLastMessage(' World');
      });

      expect(useChatStore.getState().messages[0].content).toBe('Hello World');
    });

    it('should do nothing when no messages exist', () => {
      act(() => {
        useChatStore.getState().updateLastMessage('test');
      });

      expect(useChatStore.getState().messages).toHaveLength(0);
    });
  });

  describe('setMessages', () => {
    it('should replace all messages', () => {
      act(() => {
        useChatStore.getState().addMessage({
          id: 'msg-1',
          role: 'user',
          content: 'Old',
          timestamp: new Date(),
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
  });

  describe('setStreaming', () => {
    it('should set streaming state', () => {
      act(() => {
        useChatStore.getState().setStreaming(true);
      });

      expect(useChatStore.getState().isStreaming).toBe(true);
    });
  });

  describe('setError', () => {
    it('should set error', () => {
      act(() => {
        useChatStore.getState().setError('Something went wrong');
      });

      expect(useChatStore.getState().error).toBe('Something went wrong');
    });

    it('should clear error', () => {
      act(() => {
        useChatStore.getState().setError('Error');
        useChatStore.getState().setError(null);
      });

      expect(useChatStore.getState().error).toBeNull();
    });
  });

  describe('clearChat', () => {
    it('should reset all chat state', () => {
      // Set some state
      act(() => {
        useChatStore.getState().addMessage({
          id: 'msg-1',
          role: 'user',
          content: 'Hello',
          timestamp: new Date(),
        });
        useChatStore.getState().setLoading(true);
        useChatStore.getState().setStreaming(true);
        useChatStore.getState().setError('error');
      });

      // Clear
      act(() => {
        useChatStore.getState().clearChat();
      });

      const state = useChatStore.getState();
      expect(state.currentConversation).toBeNull();
      expect(state.messages).toEqual([]);
      expect(state.isLoading).toBe(false);
      expect(state.isStreaming).toBe(false);
      expect(state.error).toBeNull();
    });
  });
});
