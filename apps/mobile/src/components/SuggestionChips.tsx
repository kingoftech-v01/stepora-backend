import React from 'react';
import { ScrollView, StyleSheet } from 'react-native';
import { Chip } from 'react-native-paper';

interface SuggestionChipsProps {
  suggestions: string[];
  onPress: (suggestion: string) => void;
}

export function SuggestionChips({ suggestions, onPress }: SuggestionChipsProps) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.container}
    >
      {suggestions.map((suggestion, index) => (
        <Chip
          key={index}
          onPress={() => onPress(suggestion)}
          style={styles.chip}
          mode="outlined"
        >
          {suggestion}
        </Chip>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  chip: {
    marginRight: 8,
  },
});
