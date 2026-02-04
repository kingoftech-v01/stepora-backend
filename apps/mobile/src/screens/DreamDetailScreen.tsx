import React, { useState, useCallback } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  RefreshControl,
} from 'react-native';
import {
  Text,
  Button,
  Surface,
  Chip,
  FAB,
  Portal,
  ProgressBar,
  Checkbox,
  IconButton,
  useTheme,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import { api } from '../services/api';
import { AppTheme, spacing, borderRadius, colors, shadows, typography } from '../theme';
import { Dream, Goal, Task, HomeStackParamList } from '../types';

type DreamDetailRouteProp = RouteProp<HomeStackParamList, 'DreamDetail'>;

const CATEGORY_CONFIG: Record<string, { icon: string; color: string }> = {
  education: { icon: 'school', color: colors.info },
  career: { icon: 'briefcase', color: colors.primary[600] },
  health: { icon: 'heart-pulse', color: colors.error },
  finance: { icon: 'currency-usd', color: colors.success },
  personal: { icon: 'account-heart', color: colors.primary[400] },
  social: { icon: 'account-group', color: colors.secondary[500] },
  creative: { icon: 'palette', color: colors.warning },
  creativity: { icon: 'palette', color: colors.warning },
  travel: { icon: 'airplane', color: colors.info },
  wellness: { icon: 'spa', color: colors.secondary[400] },
};

const STATUS_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  active: { label: 'Active', icon: 'play-circle', color: colors.success },
  completed: { label: 'Completed', icon: 'check-circle', color: colors.primary[500] },
  paused: { label: 'Paused', icon: 'pause-circle', color: colors.warning },
  archived: { label: 'Archived', icon: 'archive', color: colors.gray[400] },
};

const PRIORITY_LABELS: Record<number, { label: string; color: string }> = {
  1: { label: 'Low', color: colors.gray[400] },
  2: { label: 'Medium-Low', color: colors.secondary[400] },
  3: { label: 'Medium', color: colors.info },
  4: { label: 'High', color: colors.warning },
  5: { label: 'Critical', color: colors.error },
};

export const DreamDetailScreen: React.FC = () => {
  const theme = useTheme() as AppTheme;
  const route = useRoute<DreamDetailRouteProp>();
  const navigation = useNavigation<any>();
  const { dreamId } = route.params;
  const queryClient = useQueryClient();

  const [expandedGoals, setExpandedGoals] = useState<Record<string, boolean>>({});
  const [fabOpen, setFabOpen] = useState(false);

  const {
    data: dream,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useQuery<Dream>({
    queryKey: ['dream', dreamId],
    queryFn: () => api.dreams.get(dreamId) as Promise<Dream>,
  });

  const completeTaskMutation = useMutation({
    mutationFn: (taskId: string) => api.tasks.complete(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dream', dreamId] });
      queryClient.invalidateQueries({ queryKey: ['dreams'] });
    },
    onError: (err: any) => {
      Alert.alert('Error', err.message || 'Failed to complete task. Please try again.');
    },
  });

  const generatePlanMutation = useMutation({
    mutationFn: () => api.dreams.generatePlan(dreamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dream', dreamId] });
      Alert.alert('Plan Generated', 'Your AI-powered plan has been created successfully!');
    },
    onError: (err: any) => {
      Alert.alert('Error', err.message || 'Failed to generate plan. Please try again.');
    },
  });

  const toggleGoalExpanded = useCallback((goalId: string) => {
    setExpandedGoals((prev) => ({
      ...prev,
      [goalId]: !prev[goalId],
    }));
  }, []);

  const handleCompleteTask = useCallback(
    (task: Task) => {
      if (task.status === 'completed') return;
      Alert.alert('Complete Task', `Mark "${task.title}" as completed?`, [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Complete',
          onPress: () => completeTaskMutation.mutate(task.id),
        },
      ]);
    },
    [completeTaskMutation]
  );

  const handleGenerateAIPlan = useCallback(() => {
    setFabOpen(false);
    Alert.alert(
      'Generate AI Plan',
      'This will create an AI-powered plan with goals and tasks for your dream. Continue?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Generate',
          onPress: () => generatePlanMutation.mutate(),
        },
      ]
    );
  }, [generatePlanMutation]);

  const handleVisionBoard = useCallback(() => {
    setFabOpen(false);
    navigation.navigate('VisionBoard', { dreamId });
  }, [navigation, dreamId]);

  const handleMicroStart = useCallback(() => {
    setFabOpen(false);
    navigation.navigate('MicroStart', {
      dreamId,
      microTask: {
        action: 'Start working on your dream',
        duration: '2min',
        why: 'Small steps lead to big achievements',
      },
    });
  }, [navigation, dreamId]);

  const formatDuration = (mins?: number): string => {
    if (!mins) return '';
    if (mins < 60) return `${mins}min`;
    const hours = Math.floor(mins / 60);
    const remaining = mins % 60;
    return remaining > 0 ? `${hours}h ${remaining}min` : `${hours}h`;
  };

  const getTaskStatusIcon = (status: string): { icon: string; color: string } => {
    switch (status) {
      case 'completed':
        return { icon: 'checkbox-marked-circle', color: colors.success };
      case 'skipped':
        return { icon: 'skip-next-circle', color: colors.gray[400] };
      default:
        return { icon: 'checkbox-blank-circle-outline', color: colors.gray[300] };
    }
  };

  const getGoalStatusColor = (status: string): string => {
    switch (status) {
      case 'completed':
        return colors.success;
      case 'in_progress':
        return colors.info;
      case 'skipped':
        return colors.gray[400];
      default:
        return colors.gray[300];
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <Text style={[styles.loadingText, { color: theme.custom.colors.textSecondary }]}>
            Loading dream details...
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  // Error state
  if (isError || !dream) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.colors.background }]} edges={['top']}>
        <View style={styles.errorContainer}>
          <Icon name="cloud-alert" size={64} color={colors.error} />
          <Text style={[styles.errorTitle, { color: theme.custom.colors.textPrimary }]}>
            Failed to Load
          </Text>
          <Text style={[styles.errorText, { color: theme.custom.colors.textSecondary }]}>
            {(error as any)?.message || 'Could not load dream details. Please check your connection and try again.'}
          </Text>
          <Button mode="contained" onPress={() => refetch()} style={styles.retryButton}>
            Retry
          </Button>
          <Button mode="text" onPress={() => navigation.goBack()} style={styles.backButton}>
            Go Back
          </Button>
        </View>
      </SafeAreaView>
    );
  }

  const categoryConfig = CATEGORY_CONFIG[dream.category] || { icon: 'star', color: colors.primary[500] };
  const statusConfig = STATUS_CONFIG[dream.status] || STATUS_CONFIG.active;
  const priorityConfig = PRIORITY_LABELS[dream.priority] || PRIORITY_LABELS[3];
  const completionPercentage = dream.progress ?? 0;

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
          <Text style={[typography.h3, { color: theme.custom.colors.textPrimary }]} numberOfLines={1}>
            {dream.title}
          </Text>
        </View>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={() => refetch()} />
        }
      >
        {/* Dream Info Card */}
        <Surface style={[styles.infoCard, shadows.md]} elevation={2}>
          {/* Category and Status Row */}
          <View style={styles.chipRow}>
            <Chip
              icon={() => <Icon name={categoryConfig.icon} size={16} color={categoryConfig.color} />}
              style={[styles.categoryChip, { backgroundColor: categoryConfig.color + '15' }]}
              textStyle={{ color: categoryConfig.color, fontSize: 13 }}
            >
              {dream.category.charAt(0).toUpperCase() + dream.category.slice(1)}
            </Chip>
            <Chip
              icon={() => <Icon name={statusConfig.icon} size={16} color={statusConfig.color} />}
              style={[styles.statusChip, { backgroundColor: statusConfig.color + '15' }]}
              textStyle={{ color: statusConfig.color, fontSize: 13 }}
            >
              {statusConfig.label}
            </Chip>
            <Chip
              icon={() => <Icon name="flag" size={14} color={priorityConfig.color} />}
              style={[styles.priorityChip, { backgroundColor: priorityConfig.color + '15' }]}
              textStyle={{ color: priorityConfig.color, fontSize: 12 }}
              compact
            >
              {priorityConfig.label}
            </Chip>
          </View>

          {/* Description */}
          {dream.description ? (
            <Text style={[typography.body, { color: theme.custom.colors.textSecondary, marginTop: spacing.md }]}>
              {dream.description}
            </Text>
          ) : null}

          {/* Progress Bar */}
          <View style={styles.progressSection}>
            <View style={styles.progressHeader}>
              <Text style={[typography.bodySmall, { color: theme.custom.colors.textSecondary }]}>
                Progress
              </Text>
              <Text style={[typography.bodySmall, { color: theme.custom.colors.textPrimary, fontWeight: '600' }]}>
                {Math.round(completionPercentage)}%
              </Text>
            </View>
            <ProgressBar
              progress={completionPercentage / 100}
              color={completionPercentage >= 100 ? colors.success : theme.colors.primary}
              style={styles.progressBar}
            />
          </View>
        </Surface>

        {/* Goals Section */}
        <View style={styles.sectionHeader}>
          <Icon name="flag-checkered" size={20} color={theme.custom.colors.textPrimary} />
          <Text style={[typography.h3, { color: theme.custom.colors.textPrimary, marginLeft: spacing.sm }]}>
            Goals
          </Text>
          <Text style={[typography.bodySmall, { color: theme.custom.colors.textMuted, marginLeft: spacing.sm }]}>
            ({dream.goals?.length || 0})
          </Text>
        </View>

        {(!dream.goals || dream.goals.length === 0) ? (
          <Surface style={[styles.emptyGoalsCard, shadows.sm]} elevation={1}>
            <Icon name="target" size={48} color={theme.custom.colors.textMuted} />
            <Text style={[typography.body, { color: theme.custom.colors.textSecondary, marginTop: spacing.sm, textAlign: 'center' }]}>
              No goals yet. Use "Generate AI Plan" to create goals and tasks automatically.
            </Text>
          </Surface>
        ) : (
          dream.goals.map((goal: Goal, goalIndex: number) => {
            const isExpanded = expandedGoals[goal.id] ?? true;
            const goalStatusColor = getGoalStatusColor(goal.status);
            const completedTasks = goal.tasks?.filter((t) => t.status === 'completed').length || 0;
            const totalTasks = goal.tasks?.length || 0;

            return (
              <Surface key={goal.id} style={[styles.goalCard, shadows.sm]} elevation={1}>
                {/* Goal Header */}
                <TouchableOpacity
                  style={styles.goalHeader}
                  onPress={() => toggleGoalExpanded(goal.id)}
                  activeOpacity={0.7}
                >
                  <View style={[styles.goalIndicator, { backgroundColor: goalStatusColor }]} />
                  <View style={styles.goalHeaderContent}>
                    <Text style={[typography.h4, { color: theme.custom.colors.textPrimary }]} numberOfLines={2}>
                      {goal.title}
                    </Text>
                    <View style={styles.goalMeta}>
                      <Text style={[typography.caption, { color: theme.custom.colors.textMuted }]}>
                        {completedTasks}/{totalTasks} tasks
                      </Text>
                      {goal.progress > 0 && (
                        <Text style={[typography.caption, { color: goalStatusColor, marginLeft: spacing.sm }]}>
                          {Math.round(goal.progress)}%
                        </Text>
                      )}
                    </View>
                  </View>
                  <Icon
                    name={isExpanded ? 'chevron-up' : 'chevron-down'}
                    size={24}
                    color={theme.custom.colors.textMuted}
                  />
                </TouchableOpacity>

                {/* Goal Progress Bar */}
                <ProgressBar
                  progress={(goal.progress || 0) / 100}
                  color={goalStatusColor}
                  style={styles.goalProgressBar}
                />

                {/* Tasks List (collapsible) */}
                {isExpanded && goal.tasks && goal.tasks.length > 0 && (
                  <View style={styles.tasksList}>
                    {goal.tasks.map((task: Task, taskIndex: number) => {
                      const taskStatus = getTaskStatusIcon(task.status);
                      const isCompleted = task.status === 'completed';
                      const isCompletingThis = completeTaskMutation.isPending &&
                        completeTaskMutation.variables === task.id;

                      return (
                        <TouchableOpacity
                          key={task.id}
                          style={[
                            styles.taskItem,
                            taskIndex < goal.tasks.length - 1 && styles.taskItemBorder,
                            isCompleted && styles.taskItemCompleted,
                          ]}
                          onPress={() => handleCompleteTask(task)}
                          activeOpacity={isCompleted ? 1 : 0.6}
                          disabled={isCompleted || completeTaskMutation.isPending}
                        >
                          {isCompletingThis ? (
                            <ActivityIndicator size={22} color={theme.colors.primary} style={styles.taskCheckbox} />
                          ) : (
                            <Icon
                              name={taskStatus.icon}
                              size={22}
                              color={taskStatus.color}
                              style={styles.taskCheckbox}
                            />
                          )}
                          <View style={styles.taskContent}>
                            <Text
                              style={[
                                typography.body,
                                {
                                  color: isCompleted
                                    ? theme.custom.colors.textMuted
                                    : theme.custom.colors.textPrimary,
                                },
                                isCompleted && styles.taskTitleCompleted,
                              ]}
                              numberOfLines={2}
                            >
                              {task.title}
                            </Text>
                            <View style={styles.taskMeta}>
                              {task.durationMins ? (
                                <View style={styles.taskMetaItem}>
                                  <Icon name="clock-outline" size={13} color={theme.custom.colors.textMuted} />
                                  <Text style={[typography.caption, { color: theme.custom.colors.textMuted, marginLeft: 3 }]}>
                                    {formatDuration(task.durationMins)}
                                  </Text>
                                </View>
                              ) : null}
                              <View style={styles.taskMetaItem}>
                                <Icon
                                  name={taskStatus.icon}
                                  size={13}
                                  color={taskStatus.color}
                                />
                                <Text style={[typography.caption, { color: taskStatus.color, marginLeft: 3 }]}>
                                  {task.status.charAt(0).toUpperCase() + task.status.slice(1)}
                                </Text>
                              </View>
                            </View>
                          </View>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                )}

                {isExpanded && (!goal.tasks || goal.tasks.length === 0) && (
                  <View style={styles.noTasksContainer}>
                    <Text style={[typography.bodySmall, { color: theme.custom.colors.textMuted, textAlign: 'center' }]}>
                      No tasks for this goal yet.
                    </Text>
                  </View>
                )}
              </Surface>
            );
          })
        )}

        {/* Generating Plan Indicator */}
        {generatePlanMutation.isPending && (
          <Surface style={[styles.generatingCard, shadows.sm]} elevation={1}>
            <ActivityIndicator size="small" color={colors.primary[500]} />
            <Text style={[typography.bodySmall, { color: theme.custom.colors.textPrimary, flex: 1 }]}>
              Generating your AI plan... This may take a moment.
            </Text>
          </Surface>
        )}

        {/* Bottom spacer for FAB */}
        <View style={styles.bottomSpacer} />
      </ScrollView>

      {/* FAB Group */}
      <Portal>
        <FAB.Group
          open={fabOpen}
          visible
          icon={fabOpen ? 'close' : 'plus'}
          fabStyle={[styles.fab, { backgroundColor: theme.colors.primary }]}
          color={colors.white}
          actions={[
            {
              icon: 'robot',
              label: 'Generate AI Plan',
              onPress: handleGenerateAIPlan,
              color: theme.colors.primary,
              style: { backgroundColor: colors.white },
              labelStyle: { color: theme.custom.colors.textPrimary },
            },
            {
              icon: 'image-filter-hdr',
              label: 'Vision Board',
              onPress: handleVisionBoard,
              color: colors.info,
              style: { backgroundColor: colors.white },
              labelStyle: { color: theme.custom.colors.textPrimary },
            },
            {
              icon: 'rocket-launch',
              label: 'MicroStart',
              onPress: handleMicroStart,
              color: colors.success,
              style: { backgroundColor: colors.white },
              labelStyle: { color: theme.custom.colors.textPrimary },
            },
          ]}
          onStateChange={({ open }) => setFabOpen(open)}
        />
      </Portal>
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
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.md,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    ...typography.body,
    marginTop: spacing.md,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  errorTitle: {
    ...typography.h3,
    marginTop: spacing.md,
    textAlign: 'center',
  },
  errorText: {
    ...typography.body,
    marginTop: spacing.sm,
    textAlign: 'center',
  },
  retryButton: {
    marginTop: spacing.lg,
  },
  backButton: {
    marginTop: spacing.sm,
  },
  infoCard: {
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  categoryChip: {
    borderRadius: borderRadius.full,
  },
  statusChip: {
    borderRadius: borderRadius.full,
  },
  priorityChip: {
    borderRadius: borderRadius.full,
  },
  progressSection: {
    marginTop: spacing.lg,
  },
  progressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  progressBar: {
    height: 8,
    borderRadius: 4,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.md,
    marginBottom: spacing.md,
  },
  emptyGoalsCard: {
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    alignItems: 'center',
  },
  goalCard: {
    borderRadius: borderRadius.lg,
    marginBottom: spacing.md,
    overflow: 'hidden',
  },
  goalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
  },
  goalIndicator: {
    width: 4,
    height: 40,
    borderRadius: 2,
    marginRight: spacing.sm,
  },
  goalHeaderContent: {
    flex: 1,
    marginRight: spacing.sm,
  },
  goalMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.xs,
  },
  goalProgressBar: {
    height: 3,
    marginHorizontal: spacing.md,
  },
  tasksList: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.sm,
  },
  taskItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: spacing.sm,
  },
  taskItemBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.gray[200],
  },
  taskItemCompleted: {
    opacity: 0.7,
  },
  taskCheckbox: {
    marginRight: spacing.sm,
    marginTop: 2,
  },
  taskContent: {
    flex: 1,
  },
  taskTitleCompleted: {
    textDecorationLine: 'line-through',
  },
  taskMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.xs,
    gap: spacing.md,
  },
  taskMetaItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  noTasksContainer: {
    padding: spacing.md,
    paddingTop: 0,
  },
  generatingCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    borderRadius: borderRadius.md,
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  bottomSpacer: {
    height: 100,
  },
  fab: {
    borderRadius: borderRadius.full,
  },
});
