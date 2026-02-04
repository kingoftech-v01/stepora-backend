import { create } from 'zustand';
import { Message } from '../types';

/**
 * Input type for addMessage. The id and timestamp fields are optional;
 * they will be auto-generated if not provided. This keeps backward
 * compatibility with callers that only supply { role, content }.
 */
type MessageInput = {
  id?: string;
  role: Message['role'];
  content: string;
  timestamp?: Date;
  isStreaming?: boolean;
};

interface ChatState {
  conversationId: string | null;
  messages: Message[];
  isLoading: boolean;
  isStreaming: boolean;
  error: string | null;

  setConversationId: (id: string | null) => void;
  addMessage: (message: MessageInput) => void;
  appendToMessage: (id: string, token: string) => void;
  finalizeMessage: (id: string, serverMessageId?: string) => void;
  setMessages: (messages: Message[]) => void;
  clearMessages: () => void;
  setLoading: (loading: boolean) => void;
  setStreaming: (streaming: boolean) => void;
  setError: (error: string | null) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  conversationId: null,
  messages: [],
  isLoading: false,
  isStreaming: false,
  error: null,

  setConversationId: (id) => set({ conversationId: id }),

  addMessage: (message) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: message.id ?? Date.now().toString(),
          role: message.role,
          content: message.content,
          timestamp: message.timestamp ?? new Date(),
          isStreaming: message.isStreaming,
        },
      ],
    })),

  appendToMessage: (id, token) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, content: msg.content + token } : msg
      ),
    })),

  finalizeMessage: (id, serverMessageId) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id
          ? { ...msg, id: serverMessageId || msg.id, isStreaming: false }
          : msg
      ),
    })),

  setMessages: (messages) => set({ messages }),

  clearMessages: () => set({ messages: [], conversationId: null }),

  setLoading: (loading) => set({ isLoading: loading }),

  setStreaming: (streaming) => set({ isStreaming: streaming }),

  setError: (error) => set({ error }),
}));
