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

import { ChatBubble } from '../components/ChatBubble';
import { ChatInput } from '../components/ChatInput';
import { SuggestionChips } from '../components/SuggestionChips';
import { useChatStore } from '../stores/chatStore';
import { Message } from '../types';
import { AppTheme, spacing, typography, colors } from '../theme';

// Generate unique ID
const generateId = () => Math.random().toString(36).substring(2, 9);

const WELCOME_MESSAGE: Message = {
  id: 'welcome',
  role: 'assistant',
  content: `Bonjour ! 👋 Je suis DreamPlanner, ton assistant personnel pour transformer tes rêves en réalité.

Parle-moi de ce que tu voudrais accomplir. Quel est ton prochain grand objectif ?`,
  timestamp: new Date(),
};

const SUGGESTIONS = [
  'Je veux apprendre une nouvelle langue',
  'Je veux me mettre au sport',
  'Je veux changer de carrière',
  'Je veux apprendre un instrument',
];

export const ChatScreen: React.FC = () => {
  const theme = useTheme() as AppTheme;
  const flatListRef = useRef<FlatList>(null);

  const {
    messages,
    isLoading,
    isStreaming,
    addMessage,
    setLoading,
    setStreaming,
    setError,
  } = useChatStore();

  // Initialize with welcome message if empty
  useEffect(() => {
    if (messages.length === 0) {
      addMessage(WELCOME_MESSAGE);
    }
  }, []);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  }, [messages]);

  const handleSend = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;

    // Add user message immediately
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
      // Simulate AI response for demo
      await simulateAIResponse(text);
    } catch (error) {
      setError((error as Error).message);
      addMessage({
        id: generateId(),
        role: 'assistant',
        content: "Désolé, je n'ai pas pu traiter ta demande. Réessaie dans un moment.",
        timestamp: new Date(),
      });
    } finally {
      setLoading(false);
      setStreaming(false);
    }
  }, [isLoading]);

  // Simulate AI response for demo
  const simulateAIResponse = async (userMessage: string) => {
    setStreaming(true);
    await new Promise((resolve) => setTimeout(resolve, 1200));

    let response = '';
    const lowerMessage = userMessage.toLowerCase();

    if (lowerMessage.includes('langue') || lowerMessage.includes('anglais') || lowerMessage.includes('espagnol')) {
      response = `Super choix ! Apprendre une nouvelle langue ouvre tellement de portes. 🌍

Quelques questions pour créer ton plan personnalisé :

1. Quelle langue veux-tu apprendre ?
2. Quel est ton niveau actuel (débutant, intermédiaire) ?
3. Combien de temps par jour peux-tu y consacrer ?
4. As-tu une date cible en tête ?`;
    } else if (lowerMessage.includes('sport') || lowerMessage.includes('fitness') || lowerMessage.includes('courir')) {
      response = `Excellent objectif ! Le sport est une habitude qui change la vie. 💪

Pour bien planifier, dis-moi :

1. Quel type d'activité t'attire ? (course, musculation, yoga...)
2. Quel est ton niveau actuel ?
3. Combien de fois par semaine peux-tu t'entraîner ?
4. As-tu un objectif précis ? (perdre du poids, marathon, etc.)`;
    } else if (lowerMessage.includes('carrière') || lowerMessage.includes('travail') || lowerMessage.includes('métier')) {
      response = `Un changement de carrière, c'est courageux et excitant ! 🚀

Explorons ensemble :

1. Dans quel domaine voudrais-tu te diriger ?
2. As-tu déjà des compétences dans ce domaine ?
3. Combien de temps es-tu prêt(e) à investir ?
4. Quelle est ta situation actuelle ?`;
    } else if (lowerMessage.includes('instrument') || lowerMessage.includes('guitare') || lowerMessage.includes('piano')) {
      response = `La musique, quelle belle aventure ! 🎵

Quelques questions pour bien démarrer :

1. Quel instrument veux-tu apprendre ?
2. As-tu déjà l'instrument chez toi ?
3. As-tu des bases musicales ou tu pars de zéro ?
4. Combien de temps par jour peux-tu pratiquer ?
5. Y a-t-il un morceau que tu rêves de jouer ?`;
    } else if (lowerMessage.includes('génère') || lowerMessage.includes('plan')) {
      response = `🎯 **Voici ton plan personnalisé !**

📊 **Analyse :** Objectif ambitieux mais réalisable
⏱ **Durée estimée :** 6 mois
📅 **Temps requis :** 30 min/jour

**Étape 1 (Sem. 1-2) : Les fondations**
• Préparer ton environnement
• Établir ta routine quotidienne

**Étape 2 (Sem. 3-6) : Construction**
• Progression graduelle
• Premiers résultats visibles

**Étape 3 (Sem. 7-12) : Maîtrise**
• Techniques avancées
• Consolidation

Veux-tu que j'ajoute ce plan à tes objectifs ?`;
    } else {
      response = `Je comprends ! 😊

Pour mieux t'aider à planifier cet objectif, j'aurais besoin d'en savoir plus :

• Peux-tu me décrire ton objectif en détail ?
• Quelle est ta motivation principale ?
• As-tu une date limite en tête ?
• Combien de temps peux-tu y consacrer chaque jour ?`;
    }

    addMessage({
      id: generateId(),
      role: 'assistant',
      content: response,
      timestamp: new Date(),
    });
  };

  const handleSuggestionPress = useCallback((suggestion: string) => {
    handleSend(suggestion);
  }, [handleSend]);

  const renderMessage = useCallback(({ item }: { item: Message }) => (
    <ChatBubble
      message={item.content}
      isUser={item.role === 'user'}
      timestamp={item.timestamp}
      isStreaming={item.isStreaming}
    />
  ), []);

  const keyExtractor = useCallback((item: Message) => item.id, []);
  const showSuggestions = messages.length <= 1;

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: theme.colors.background }]}
      edges={['top']}
    >
      <View style={[styles.header, { backgroundColor: theme.colors.surface }]}>
        <Text style={[styles.headerTitle, { color: theme.custom.colors.textPrimary }]}>
          DreamPlanner
        </Text>
        <Text style={[styles.headerSubtitle, { color: theme.custom.colors.textSecondary }]}>
          Ton assistant pour réaliser tes rêves
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
                <ActivityIndicator size="small" color={theme.colors.primary} />
                <Text style={[styles.loadingText, { color: theme.custom.colors.textSecondary }]}>
                  DreamPlanner réfléchit...
                </Text>
              </View>
            ) : null
          }
        />

        {showSuggestions && (
          <SuggestionChips suggestions={SUGGESTIONS} onPress={handleSuggestionPress} />
        )}

        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

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
  headerTitle: {
    ...typography.h2,
  },
  headerSubtitle: {
    ...typography.bodySmall,
    marginTop: 2,
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
