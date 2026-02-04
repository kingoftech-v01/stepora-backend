import { act } from 'react-test-renderer';
import { useChatStore } from '../../stores/chatStore';

beforeEach(() => {
  act(() => {
    useChatStore.getState().clearMessages();
  });
});

describe('ChatStore', () => {
  describe('Initial state', () => {
    it('should have correct initial state', () => {
      const state = useChatStore.getState();

      expect(state.conversationId).toBeNull();
      expect(state.messages).toEqual([]);
      expect(state.isLoading).toBe(false);
    });
  });

  describe('setConversationId', () => {
    it('should set conversation id', () => {
      act(() => {
        useChatStore.getState().setConversationId('conv-1');
      });

      expect(useChatStore.getState().conversationId).toBe('conv-1');
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
