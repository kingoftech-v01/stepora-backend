import { useState, useCallback } from 'react';
import { Alert } from 'react-native';
import { useChatStore } from '../stores/chatStore';
import { api, ApiError } from '../services/api';

interface UseChatReturn {
  sendMessage: (content: string) => Promise<void>;
  isStreaming: boolean;
  startNewConversation: () => Promise<void>;
  error: ApiError | null;
}

export function useChat(): UseChatReturn {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const {
    conversationId,
    setConversationId,
    addMessage,
    setLoading,
  } = useChatStore();

  const startNewConversation = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.conversations.create({
        type: 'general',
      });
      setConversationId((response as { id: string }).id);
      setError(null);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError);
      Alert.alert(
        'Erreur',
        'Impossible de démarrer une nouvelle conversation. Veuillez réessayer.'
      );
    } finally {
      setLoading(false);
    }
  }, [setConversationId, setLoading]);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim()) return;

    setError(null);

    // Add user message to store immediately
    addMessage({
      role: 'user',
      content: content.trim(),
    });

    setIsStreaming(true);
    setLoading(true);

    try {
      let currentConversationId = conversationId;

      // Create conversation if none exists
      if (!currentConversationId) {
        const createResponse = await api.conversations.create({
          type: 'general',
        });
        currentConversationId = (createResponse as { id: string }).id;
        setConversationId(currentConversationId);
      }

      // Send message to API
      const response = await api.conversations.sendMessage(
        currentConversationId,
        content.trim()
      );

      // Add assistant response to store
      const assistantMessage = response as { content: string };
      addMessage({
        role: 'assistant',
        content: assistantMessage.content,
      });

    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError);

      // Add error message to chat
      addMessage({
        role: 'assistant',
        content: "Désolé, je n'ai pas pu traiter votre message. Veuillez réessayer.",
      });

      Alert.alert(
        'Erreur',
        apiError.message || "Une erreur s'est produite lors de l'envoi du message."
      );
    } finally {
      setIsStreaming(false);
      setLoading(false);
    }
  }, [conversationId, setConversationId, addMessage, setLoading]);

  return {
    sendMessage,
    isStreaming,
    startNewConversation,
    error,
  };
}
