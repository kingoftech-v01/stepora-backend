import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import { useTheme } from 'react-native-paper';
import Animated, { FadeInUp } from 'react-native-reanimated';

import { colors, spacing, borderRadius } from '../theme';
import { AppTheme } from '../theme';

interface SuggestionChipsProps {
  suggestions: string[];
  onPress: (suggestion: string) => void;
}

export const SuggestionChips: React.FC<SuggestionChipsProps> = ({
  suggestions,
  onPress,
}) => {
  const theme = useTheme() as AppTheme;

  return (
    <Animated.View entering={FadeInUp.delay(300).duration(400)} style={styles.container}>
      <Text style={[styles.title, { color: theme.custom.colors.textSecondary }]}>
        Suggestions
      </Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {suggestions.map((suggestion, index) => (
          <TouchableOpacity
            key={index}
            style={[
              styles.chip,
              { backgroundColor: theme.colors.primaryContainer },
            ]}
            onPress={() => onPress(suggestion)}
            activeOpacity={0.7}
          >
            <Text style={[styles.chipText, { color: theme.colors.primary }]}>
              {suggestion}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    paddingVertical: spacing.sm,
  },
  title: {
    fontSize: 12,
    fontWeight: '500',
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  scrollContent: {
    paddingHorizontal: spacing.md,
    gap: spacing.sm,
  },
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.xl,
    marginRight: spacing.sm,
  },
  chipText: {
    fontSize: 14,
    fontWeight: '500',
  },
});
