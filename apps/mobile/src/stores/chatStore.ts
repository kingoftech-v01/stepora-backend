import { create } from 'zustand';
import { Message, Conversation } from '../types';

interface ChatState {
  // Current conversation
  currentConversation: Conversation | null;
  messages: Message[];
  isLoading: boolean;
  isStreaming: boolean;
  error: string | null;

  // Actions
  setConversation: (conversation: Conversation | null) => void;
  addMessage: (message: Message) => void;
  updateLastMessage: (content: string) => void;
  setMessages: (messages: Message[]) => void;
  setLoading: (loading: boolean) => void;
  setStreaming: (streaming: boolean) => void;
  setError: (error: string | null) => void;
  clearChat: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  // Initial state
  currentConversation: null,
  messages: [],
  isLoading: false,
  isStreaming: false,
  error: null,

  // Actions
  setConversation: (conversation) =>
    set({
      currentConversation: conversation,
      messages: conversation?.messages || [],
    }),

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  updateLastMessage: (content) =>
    set((state) => {
      const messages = [...state.messages];
      if (messages.length > 0) {
        const lastMessage = messages[messages.length - 1];
        messages[messages.length - 1] = {
          ...lastMessage,
          content: lastMessage.content + content,
        };
      }
      return { messages };
    }),

  setMessages: (messages) => set({ messages }),

  setLoading: (loading) => set({ isLoading: loading }),

  setStreaming: (streaming) => set({ isStreaming: streaming }),

  setError: (error) => set({ error }),

  clearChat: () =>
    set({
      currentConversation: null,
      messages: [],
      isLoading: false,
      isStreaming: false,
      error: null,
    }),
}));
