import React, { useState, useCallback } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import {
  Text,
  TextInput,
  Button,
  Surface,
  Chip,
  IconButton,
  useTheme,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigation } from '@react-navigation/native';
import { api } from '../services/api';
import { AppTheme, spacing, borderRadius, colors, shadows, typography } from '../theme';

interface CategoryOption {
  value: string;
  label: string;
  icon: string;
  color: string;
}

const CATEGORIES: CategoryOption[] = [
  { value: 'education', label: 'Education', icon: 'school', color: colors.info },
  { value: 'career', label: 'Career', icon: 'briefcase', color: colors.primary[600] },
  { value: 'health', label: 'Health', icon: 'heart-pulse', color: colors.error },
  { value: 'finance', label: 'Finance', icon: 'currency-usd', color: colors.success },
  { value: 'personal', label: 'Personal', icon: 'account-heart', color: colors.primary[400] },
  { value: 'social', label: 'Social', icon: 'account-group', color: colors.secondary[500] },
  { value: 'creative', label: 'Creative', icon: 'palette', color: colors.warning },
  { value: 'travel', label: 'Travel', icon: 'airplane', color: colors.info },
];

const PRIORITY_OPTIONS = [
  { value: 1, label: '1', description: 'Low' },
  { value: 2, label: '2', description: 'Medium-Low' },
  { value: 3, label: '3', description: 'Medium' },
  { value: 4, label: '4', description: 'High' },
  { value: 5, label: '5', description: 'Critical' },
];

const getPriorityColor = (value: number): string => {
  switch (value) {
    case 1: return colors.gray[400];
    case 2: return colors.secondary[400];
    case 3: return colors.info;
    case 4: return colors.warning;
    case 5: return colors.error;
    default: return colors.gray[400];
  }
};

export const CreateDreamScreen: React.FC = () => {
  const theme = useTheme() as AppTheme;
  const navigation = useNavigation<any>();
  const queryClient = useQueryClient();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('');
  const [priority, setPriority] = useState(3);

  const createDreamMutation = useMutation({
    mutationFn: (data: { title: string; description: string; category: string; priority: number }) =>
      api.dreams.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dreams'] });
      Alert.alert('Dream Created', 'Your dream has been created successfully!', [
        {
          text: 'OK',
          onPress: () => navigation.goBack(),
        },
      ]);
    },
    onError: (err: any) => {
      Alert.alert(
        'Error',
        err.message || 'Failed to create dream. Please try again.'
      );
    },
  });

  const handleCreate = useCallback(() => {
    if (!title.trim()) {
      Alert.alert('Validation Error', 'Please enter a title for your dream.');
      return;
    }

    if (!category) {
      Alert.alert('Validation Error', 'Please select a category for your dream.');
      return;
    }

    createDreamMutation.mutate({
      title: title.trim(),
      description: description.trim(),
      category,
      priority,
    });
  }, [title, description, category, priority, createDreamMutation]);

  const isFormValid = title.trim().length > 0 && category.length > 0;

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]} edges={['top']}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: theme.colors.surface, borderBottomColor: theme.custom.colors.border }]}>
        <IconButton
          icon="arrow-left"
          size={24}
          onPress={() => navigation.goBack()}
          style={styles.headerBackButton}
        />
        <View style={styles.headerTitleContainer}>
          <Text style={[typography.h3, { color: theme.custom.colors.textPrimary }]}>
            Create Dream
          </Text>
        </View>
        <View style={styles.headerSpacer} />
      </View>

      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {/* Title Input */}
          <Surface style={[styles.section, shadows.sm]} elevation={1}>
            <Text style={[typography.h4, { color: theme.custom.colors.textPrimary, marginBottom: spacing.sm }]}>
              Title *
            </Text>
            <TextInput
              mode="outlined"
              placeholder="What is your dream?"
              value={title}
              onChangeText={setTitle}
              maxLength={200}
              style={styles.titleInput}
              outlineColor={theme.custom.colors.border}
              activeOutlineColor={theme.colors.primary}
              placeholderTextColor={theme.custom.colors.textMuted}
            />
            <Text style={[typography.caption, { color: theme.custom.colors.textMuted, marginTop: spacing.xs, textAlign: 'right' }]}>
              {title.length}/200
            </Text>
          </Surface>

          {/* Description Input */}
          <Surface style={[styles.section, shadows.sm]} elevation={1}>
            <Text style={[typography.h4, { color: theme.custom.colors.textPrimary, marginBottom: spacing.sm }]}>
              Description
            </Text>
            <TextInput
              mode="outlined"
              placeholder="Describe your dream in detail. What does achieving it look like?"
              value={description}
              onChangeText={setDescription}
              multiline
              numberOfLines={5}
              maxLength={2000}
              style={styles.descriptionInput}
              outlineColor={theme.custom.colors.border}
              activeOutlineColor={theme.colors.primary}
              placeholderTextColor={theme.custom.colors.textMuted}
            />
            <Text style={[typography.caption, { color: theme.custom.colors.textMuted, marginTop: spacing.xs, textAlign: 'right' }]}>
              {description.length}/2000
            </Text>
          </Surface>

          {/* Category Picker */}
          <Surface style={[styles.section, shadows.sm]} elevation={1}>
            <Text style={[typography.h4, { color: theme.custom.colors.textPrimary, marginBottom: spacing.sm }]}>
              Category *
            </Text>
            <Text style={[typography.bodySmall, { color: theme.custom.colors.textSecondary, marginBottom: spacing.md }]}>
              Choose a category that best describes your dream.
            </Text>
            <View style={styles.categoryGrid}>
              {CATEGORIES.map((cat) => {
                const isSelected = category === cat.value;
                return (
                  <Chip
                    key={cat.value}
                    icon={() => (
                      <Icon
                        name={cat.icon}
                        size={16}
                        color={isSelected ? colors.white : cat.color}
                      />
                    )}
                    selected={isSelected}
                    onPress={() => setCategory(cat.value)}
                    style={[
                      styles.categoryChip,
                      isSelected
                        ? { backgroundColor: cat.color }
                        : { backgroundColor: cat.color + '15', borderColor: cat.color + '30', borderWidth: 1 },
                    ]}
                    textStyle={{
                      color: isSelected ? colors.white : cat.color,
                      fontSize: 13,
                      fontWeight: isSelected ? '600' : '400',
                    }}
                    showSelectedOverlay={false}
                  >
                    {cat.label}
                  </Chip>
                );
              })}
            </View>
          </Surface>

          {/* Priority Slider */}
          <Surface style={[styles.section, shadows.sm]} elevation={1}>
            <Text style={[typography.h4, { color: theme.custom.colors.textPrimary, marginBottom: spacing.sm }]}>
              Priority
            </Text>
            <Text style={[typography.bodySmall, { color: theme.custom.colors.textSecondary, marginBottom: spacing.md }]}>
              How important is this dream to you?
            </Text>
            <View style={styles.priorityRow}>
              {PRIORITY_OPTIONS.map((opt) => {
                const isSelected = priority === opt.value;
                const priorityColor = getPriorityColor(opt.value);
                return (
                  <View key={opt.value} style={styles.priorityOption}>
                    <Chip
                      onPress={() => setPriority(opt.value)}
                      selected={isSelected}
                      style={[
                        styles.priorityChip,
                        isSelected
                          ? { backgroundColor: priorityColor }
                          : { backgroundColor: priorityColor + '15', borderColor: priorityColor + '30', borderWidth: 1 },
                      ]}
                      textStyle={{
                        color: isSelected ? colors.white : priorityColor,
                        fontWeight: isSelected ? '700' : '500',
                        fontSize: 15,
                      }}
                      showSelectedOverlay={false}
                    >
                      {opt.label}
                    </Chip>
                    <Text style={[typography.caption, { color: theme.custom.colors.textMuted, marginTop: spacing.xs, textAlign: 'center' }]}>
                      {opt.description}
                    </Text>
                  </View>
                );
              })}
            </View>
          </Surface>

          {/* Create Button */}
          <Button
            mode="contained"
            onPress={handleCreate}
            loading={createDreamMutation.isPending}
            disabled={!isFormValid || createDreamMutation.isPending}
            style={[styles.createButton, !isFormValid && styles.createButtonDisabled]}
            contentStyle={styles.createButtonContent}
            labelStyle={typography.h4}
            icon="plus-circle"
          >
            Create Dream
          </Button>

          {/* Bottom spacer */}
          <View style={styles.bottomSpacer} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingRight: spacing.md,
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
  },
  headerBackButton: {
    marginLeft: spacing.xs,
  },
  headerTitleContainer: {
    flex: 1,
  },
  headerSpacer: {
    width: 40,
  },
  keyboardView: {
    flex: 1,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.md,
  },
  section: {
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  titleInput: {
    backgroundColor: 'transparent',
  },
  descriptionInput: {
    backgroundColor: 'transparent',
    minHeight: 120,
  },
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  categoryChip: {
    borderRadius: borderRadius.full,
  },
  priorityRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: spacing.xs,
  },
  priorityOption: {
    flex: 1,
    alignItems: 'center',
  },
  priorityChip: {
    borderRadius: borderRadius.full,
    minWidth: 44,
  },
  createButton: {
    marginTop: spacing.md,
    borderRadius: borderRadius.md,
  },
  createButtonDisabled: {
    opacity: 0.6,
  },
  createButtonContent: {
    paddingVertical: spacing.sm,
  },
  bottomSpacer: {
    height: spacing.xxl,
  },
});
