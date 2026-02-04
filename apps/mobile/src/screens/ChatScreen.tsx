import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { Text, useTheme, ActivityIndicator } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import auth from '@react-native-firebase/auth';

import { ChatBubble } from '../components/ChatBubble';
import { ChatInput } from '../components/ChatInput';
import { SuggestionChips } from '../components/SuggestionChips';
import { useChatStore } from '../stores/chatStore';
import { Message } from '../types';
import { AppTheme, spacing, typography, colors } from '../theme';
import { api } from '../services/api';
import { ENV } from '../config/env';

// ---------------------------------------------------------------------------
// Helpers & constants
// ---------------------------------------------------------------------------

const generateId = () => Math.random().toString(36).substring(2, 9);

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 5;

const WELCOME_MESSAGE: Message = {
  id: 'welcome',
  role: 'assistant',
  content: `Hello! I'm DreamPlanner, your personal assistant for turning your dreams into reality.\n\nTell me about what you'd like to accomplish. What's your next big goal?`,
  timestamp: new Date(),
};

const SUGGESTIONS = [
  'I want to learn a new language',
  'I want to start working out',
  'I want to change careers',
  'I want to learn an instrument',
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const ChatScreen: React.FC = () => {
  const theme = useTheme() as AppTheme;
  const flatListRef = useRef<FlatList>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const streamingMessageIdRef = useRef<string | null>(null);

  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>('disconnected');

  const {
    conversationId,
    messages,
    isLoading,
    isStreaming,
    addMessage,
    appendToMessage,
    finalizeMessage,
    setConversationId,
    setLoading,
    setStreaming,
    setError,
  } = useChatStore();

  // -----------------------------------------------------------------------
  // Lifecycle
  // -----------------------------------------------------------------------

  // Seed the chat with a welcome message when the screen first renders.
  useEffect(() => {
    if (messages.length === 0) {
      addMessage(WELCOME_MESSAGE);
    }
  }, []);

  // Auto-scroll to the bottom whenever the message list changes.
  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  }, [messages]);

  // Bootstrap: load or create a conversation, then open the WebSocket.
  useEffect(() => {
    initializeConversation();
    return () => {
      cleanupWebSocket();
    };
  }, []);

  // -----------------------------------------------------------------------
  // WebSocket management
  // -----------------------------------------------------------------------

  const cleanupWebSocket = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      // Prevent the onclose handler from triggering reconnection.
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const initializeConversation = async () => {
    try {
      // Attempt to load existing conversations from the backend.
      const response: any = await api.conversations.list();
      const conversations = response.results || response;

      let activeConversationId: string;

      if (conversations && conversations.length > 0) {
        // Resume the most recent conversation.
        activeConversationId = conversations[0].id;
      } else {
        // No prior conversations -- create a new one.
        const newConversation: any = await api.conversations.create({
          type: 'general',
        });
        activeConversationId = newConversation.id;
      }

      setConversationId(activeConversationId);
      connectWebSocket(activeConversationId);
    } catch (error) {
      // If the API is unreachable, generate a local ID so the user can still
      // type messages (they will be sent via REST once connectivity returns).
      console.warn(
        'Failed to initialize conversation; will use REST fallback:',
        error,
      );
      const fallbackId = generateId();
      setConversationId(fallbackId);
      setConnectionStatus('error');
    }
  };

  const connectWebSocket = async (convId: string) => {
    cleanupWebSocket();
    setConnectionStatus('connecting');

    try {
      const user = auth().currentUser;
      if (!user) {
        setConnectionStatus('error');
        return;
      }

      const token = await user.getIdToken();
      const wsUrl = `${ENV.WS_URL}/chat/${convId}/?token=${token}`;
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = (event: WebSocketMessageEvent) => {
        handleWebSocketMessage(event);
      };

      ws.onerror = () => {
        setConnectionStatus('error');
      };

      ws.onclose = () => {
        setConnectionStatus('disconnected');
        attemptReconnect(convId);
      };

      wsRef.current = ws;
    } catch (error) {
      console.warn('Failed to connect WebSocket:', error);
      setConnectionStatus('error');
    }
  };

  const attemptReconnect = (convId: string) => {
    if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
      setConnectionStatus('error');
      return;
    }

    reconnectAttemptsRef.current += 1;
    const delay = RECONNECT_DELAY_MS * reconnectAttemptsRef.current;

    reconnectTimerRef.current = setTimeout(() => {
      connectWebSocket(convId);
    }, delay);
  };

  // -----------------------------------------------------------------------
  // Incoming WebSocket messages
  // -----------------------------------------------------------------------

  const handleWebSocketMessage = (event: WebSocketMessageEvent) => {
    try {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'chat.token': {
          if (!streamingMessageIdRef.current) {
            // First token -- create a new placeholder assistant message.
            const msgId = generateId();
            streamingMessageIdRef.current = msgId;
            setStreaming(true);
            addMessage({
              id: msgId,
              role: 'assistant',
              content: data.token,
              timestamp: new Date(),
              isStreaming: true,
            });
          } else {
            // Subsequent tokens -- append to the existing message.
            appendToMessage(streamingMessageIdRef.current, data.token);
          }
          break;
        }

        case 'chat.complete': {
          if (streamingMessageIdRef.current) {
            finalizeMessage(
              streamingMessageIdRef.current,
              data.message_id,
            );
            streamingMessageIdRef.current = null;
          }
          setStreaming(false);
          setLoading(false);
          break;
        }

        case 'chat.error': {
          setError(data.message || 'An error occurred');
          setStreaming(false);
          setLoading(false);
          streamingMessageIdRef.current = null;
          addMessage({
            id: generateId(),
            role: 'assistant',
            content:
              'Sorry, I could not process your request. Please try again in a moment.',
            timestamp: new Date(),
          });
          break;
        }

        default:
          break;
      }
    } catch (error) {
      console.warn('Failed to parse WebSocket message:', error);
    }
  };

  // -----------------------------------------------------------------------
  // Sending messages
  // -----------------------------------------------------------------------

  /** Attempt to send via the open WebSocket. Returns true on success. */
  const sendViaWebSocket = (text: string): boolean => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: 'chat.message',
          content: text,
        }),
      );
      return true;
    }
    return false;
  };

  /** Fallback: send via the REST API and add the response to the store. */
  const sendViaRest = async (text: string) => {
    const convId = useChatStore.getState().conversationId;
    if (!convId) {
      throw new Error('No active conversation');
    }

    const response: any = await api.conversations.sendMessage(convId, text);
    const assistantContent =
      response.content || response.message || response.reply || '';

    addMessage({
      id: response.id || generateId(),
      role: 'assistant',
      content: assistantContent,
      timestamp: new Date(),
    });
  };

  const handleSend = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return;

      // Immediately show the user's message in the list.
      const userMessage: Message = {
        id: generateId(),
        role: 'user',
        content: text,
        timestamp: new Date(),
      };
      addMessage(userMessage);
      setLoading(true);
      setError(null);

      try {
        // Prefer the WebSocket path for streaming responses.
        const sentViaWs = sendViaWebSocket(text);

        if (!sentViaWs) {
          // WebSocket unavailable -- fall back to REST.
          await sendViaRest(text);
          setLoading(false);
        }
        // When sent via WS, loading is cleared by the chat.complete handler.
      } catch (error) {
        setError((error as Error).message || 'Failed to send message');
        addMessage({
          id: generateId(),
          role: 'assistant',
          content:
            'Sorry, I could not process your request. Please try again in a moment.',
          timestamp: new Date(),
        });
        setLoading(false);
        setStreaming(false);
      }
    },
    [isLoading],
  );

  const handleSuggestionPress = useCallback(
    (suggestion: string) => {
      handleSend(suggestion);
    },
    [handleSend],
  );

  // -----------------------------------------------------------------------
  // Render helpers
  // -----------------------------------------------------------------------

  const renderMessage = useCallback(
    ({ item }: { item: Message }) => (
      <ChatBubble
        message={item.content}
        isUser={item.role === 'user'}
        timestamp={item.timestamp}
        isStreaming={item.isStreaming}
      />
    ),
    [],
  );

  const keyExtractor = useCallback((item: Message) => item.id, []);

  const showSuggestions = messages.length <= 1;

  // Connection status visual helpers
  const getStatusColor = (): string => {
    switch (connectionStatus) {
      case 'connected':
        return colors.success;
      case 'connecting':
        return colors.warning;
      case 'disconnected':
        return colors.gray[400];
      case 'error':
        return colors.error;
    }
  };

  const getStatusLabel = (): string => {
    switch (connectionStatus) {
      case 'connected':
        return 'Connected';
      case 'connecting':
        return 'Connecting...';
      case 'disconnected':
        return 'Disconnected';
      case 'error':
        return 'Connection error';
    }
  };

  // -----------------------------------------------------------------------
  // JSX
  // -----------------------------------------------------------------------

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: theme.colors.background }]}
      edges={['top']}
    >
      {/* Header */}
      <View style={[styles.header, { backgroundColor: theme.colors.surface }]}>
        <View style={styles.headerRow}>
          <Text
            style={[
              styles.headerTitle,
              { color: theme.custom.colors.textPrimary },
            ]}
          >
            DreamPlanner
          </Text>

          {/* Connection status indicator */}
          <View style={styles.statusContainer}>
            <View
              style={[
                styles.statusDot,
                { backgroundColor: getStatusColor() },
              ]}
            />
            <Text
              style={[
                styles.statusText,
                { color: theme.custom.colors.textSecondary },
              ]}
            >
              {getStatusLabel()}
            </Text>
          </View>
        </View>

        <Text
          style={[
            styles.headerSubtitle,
            { color: theme.custom.colors.textSecondary },
          ]}
        >
          Your assistant for making dreams come true
        </Text>
      </View>

      <KeyboardAvoidingView
        style={styles.keyboardAvoid}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <FlatList
          ref={flatListRef}
          data={messages}
          renderItem={renderMessage}
          keyExtractor={keyExtractor}
          contentContainerStyle={styles.messagesList}
          showsVerticalScrollIndicator={false}
          ListFooterComponent={
            isLoading && !isStreaming ? (
              <View style={styles.loadingContainer}>
                <ActivityIndicator
                  size="small"
                  color={theme.colors.primary}
                />
                <Text
                  style={[
                    styles.loadingText,
                    { color: theme.custom.colors.textSecondary },
                  ]}
                >
                  DreamPlanner is thinking...
                </Text>
              </View>
            ) : null
          }
        />

        {showSuggestions && (
          <SuggestionChips
            suggestions={SUGGESTIONS}
            onPress={handleSuggestionPress}
          />
        )}

        <ChatInput
          onSend={handleSend}
          isLoading={isLoading}
          placeholder="Type your message..."
        />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray[200],
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  headerTitle: {
    ...typography.h2,
  },
  headerSubtitle: {
    ...typography.bodySmall,
    marginTop: 2,
  },
  statusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  statusText: {
    fontSize: 12,
  },
  keyboardAvoid: {
    flex: 1,
  },
  messagesList: {
    paddingVertical: spacing.md,
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  loadingText: {
    marginLeft: spacing.sm,
    fontSize: 14,
  },
});
