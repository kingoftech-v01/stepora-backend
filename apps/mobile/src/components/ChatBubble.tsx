import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from 'react-native-paper';
import { format } from 'date-fns';
import { fr } from 'date-fns/locale';
import Animated, { FadeInUp } from 'react-native-reanimated';

import { colors, spacing, borderRadius, typography } from '../theme';
import { AppTheme } from '../theme';

interface ChatBubbleProps {
  message: string;
  isUser: boolean;
  timestamp: Date;
  isStreaming?: boolean;
}

export const ChatBubble: React.FC<ChatBubbleProps> = ({
  message,
  isUser,
  timestamp,
  isStreaming = false,
}) => {
  const theme = useTheme() as AppTheme;
  const customColors = theme.custom.colors;

  const formattedTime = format(timestamp, 'HH:mm', { locale: fr });

  return (
    <Animated.View
      entering={FadeInUp.duration(300)}
      style={[
        styles.container,
        isUser ? styles.userContainer : styles.aiContainer,
      ]}
    >
      {!isUser && (
        <View style={styles.avatarContainer}>
          <View style={[styles.avatar, { backgroundColor: theme.colors.primary }]}>
            <Text style={styles.avatarText}>AI</Text>
          </View>
        </View>
      )}

      <View style={styles.bubbleWrapper}>
        {!isUser && (
          <Text style={[styles.senderName, { color: customColors.textSecondary }]}>
            DreamPlanner
          </Text>
        )}

        <View
          style={[
            styles.bubble,
            isUser
              ? [styles.userBubble, { backgroundColor: customColors.userBubble }]
              : [styles.aiBubble, { backgroundColor: customColors.aiBubble }],
          ]}
        >
          <Text
            style={[
              styles.messageText,
              { color: isUser ? colors.white : customColors.textPrimary },
            ]}
          >
            {message}
            {isStreaming && <Text style={styles.cursor}>|</Text>}
          </Text>
        </View>

        <Text
          style={[
            styles.timestamp,
            { color: customColors.textMuted },
            isUser && styles.timestampRight,
          ]}
        >
          {formattedTime}
        </Text>
      </View>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    marginBottom: spacing.md,
    paddingHorizontal: spacing.sm,
  },
  userContainer: {
    justifyContent: 'flex-end',
  },
  aiContainer: {
    justifyContent: 'flex-start',
  },
  avatarContainer: {
    marginRight: spacing.sm,
    alignSelf: 'flex-end',
  },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarText: {
    color: colors.white,
    fontSize: 12,
    fontWeight: '600',
  },
  bubbleWrapper: {
    maxWidth: '75%',
  },
  senderName: {
    fontSize: 12,
    marginBottom: 4,
    marginLeft: 4,
  },
  bubble: {
    padding: spacing.md,
    borderRadius: borderRadius.lg,
  },
  userBubble: {
    borderBottomRightRadius: borderRadius.sm,
  },
  aiBubble: {
    borderBottomLeftRadius: borderRadius.sm,
  },
  messageText: {
    ...typography.body,
  },
  cursor: {
    opacity: 0.5,
  },
  timestamp: {
    fontSize: 10,
    marginTop: 4,
    marginLeft: 4,
  },
  timestampRight: {
    textAlign: 'right',
    marginRight: 4,
  },
});
