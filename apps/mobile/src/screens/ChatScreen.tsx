import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { TextInput, IconButton, ActivityIndicator } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ChatBubble } from '../components/ChatBubble';
import { SuggestionChips } from '../components/SuggestionChips';
import { useChatStore } from '../stores/chatStore';
import { useChat } from '../hooks/useChat';
import { theme } from '../theme';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export function ChatScreen() {
  const [inputText, setInputText] = useState('');
  const flatListRef = useRef<FlatList>(null);

  const { messages, isLoading, conversationId } = useChatStore();
  const { sendMessage, isStreaming } = useChat();

  const suggestions = [
    'Je veux apprendre une nouvelle langue',
    'Je veux me mettre au sport',
    'Je veux changer de carrière',
  ];

  const handleSend = async () => {
    if (!inputText.trim() || isLoading) return;

    const text = inputText.trim();
    setInputText('');

    await sendMessage(text);
  };

  const handleSuggestionPress = (suggestion: string) => {
    setInputText(suggestion);
  };

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  }, [messages]);

  const renderMessage = ({ item }: { item: Message }) => (
    <ChatBubble
      message={item.content}
      isUser={item.role === 'user'}
      timestamp={item.timestamp}
    />
  );

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <KeyboardAvoidingView
        style={styles.keyboardAvoid}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
        {/* Messages List */}
        <FlatList
          ref={flatListRef}
          data={messages}
          renderItem={renderMessage}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.messagesList}
          showsVerticalScrollIndicator={false}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <ChatBubble
                message="Bonjour ! 👋 Je suis DreamPlanner, ton assistant personnel pour transformer tes rêves en réalité.

Parle-moi de ce que tu voudrais accomplir. Quel est ton prochain grand objectif ?"
                isUser={false}
                timestamp={new Date()}
              />
            </View>
          }
          ListFooterComponent={
            isStreaming ? (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="small" color={theme.colors.primary} />
              </View>
            ) : null
          }
        />

        {/* Suggestions (shown when no messages) */}
        {messages.length === 0 && (
          <SuggestionChips
            suggestions={suggestions}
            onPress={handleSuggestionPress}
          />
        )}

        {/* Input Area */}
        <View style={styles.inputContainer}>
          <TextInput
            mode="outlined"
            placeholder="Écris ton message..."
            value={inputText}
            onChangeText={setInputText}
            style={styles.input}
            outlineStyle={styles.inputOutline}
            multiline
            maxLength={1000}
            right={
              <TextInput.Icon
                icon="send"
                onPress={handleSend}
                disabled={!inputText.trim() || isLoading}
                color={
                  inputText.trim() && !isLoading
                    ? theme.colors.primary
                    : theme.colors.disabled
                }
              />
            }
          />
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  keyboardAvoid: {
    flex: 1,
  },
  messagesList: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  emptyContainer: {
    flex: 1,
  },
  loadingContainer: {
    padding: 16,
    alignItems: 'flex-start',
  },
  inputContainer: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: theme.colors.surface,
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
  },
  input: {
    backgroundColor: theme.colors.background,
    maxHeight: 120,
  },
  inputOutline: {
    borderRadius: 24,
  },
});
