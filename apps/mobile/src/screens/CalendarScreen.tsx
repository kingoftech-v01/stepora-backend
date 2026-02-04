import React, { useState } from 'react';
import { View, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { Text, useTheme } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Calendar, LocaleConfig } from 'react-native-calendars';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

import { AppTheme, spacing, borderRadius, colors, shadows, typography } from '../theme';

// Configure French locale
LocaleConfig.locales['fr'] = {
  monthNames: [
    'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
  ],
  monthNamesShort: ['Jan.', 'Fév.', 'Mars', 'Avr.', 'Mai', 'Juin', 'Juil.', 'Août', 'Sept.', 'Oct.', 'Nov.', 'Déc.'],
  dayNames: ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'],
  dayNamesShort: ['D', 'L', 'M', 'M', 'J', 'V', 'S'],
  today: "Aujourd'hui"
};
LocaleConfig.defaultLocale = 'fr';

interface Task {
  id: string;
  title: string;
  time: string;
  duration: string;
  category: string;
  completed: boolean;
}

const MOCK_TASKS: Task[] = [
  {
    id: '1',
    title: 'Pratique guitare',
    time: '18:30 - 19:00',
    duration: '30 min',
    category: 'creativity',
    completed: false,
  },
  {
    id: '2',
    title: 'Course matinale',
    time: '7:00 - 7:30',
    duration: '30 min',
    category: 'health',
    completed: true,
  },
  {
    id: '3',
    title: 'Lecture - 20 pages',
    time: '21:00 - 21:30',
    duration: '30 min',
    category: 'education',
    completed: false,
  },
];

const getCategoryColor = (category: string): string => {
  const categoryColors: Record<string, string> = {
    health: colors.success,
    education: colors.warning,
    creativity: colors.primary[500],
  };
  return categoryColors[category] || colors.primary[500];
};

const getCategoryIcon = (category: string): string => {
  const icons: Record<string, string> = {
    health: 'run',
    education: 'book-open-variant',
    creativity: 'music',
  };
  return icons[category] || 'star';
};

interface TaskCardProps {
  task: Task;
  onComplete: () => void;
}

const TaskCard: React.FC<TaskCardProps> = ({ task, onComplete }) => {
  const theme = useTheme() as AppTheme;
  const categoryColor = getCategoryColor(task.category);

  return (
    <View
      style={[
        styles.taskCard,
        { backgroundColor: theme.colors.surface },
        shadows.sm,
        task.completed && styles.taskCardCompleted,
      ]}
    >
      <View style={[styles.taskAccent, { backgroundColor: categoryColor }]} />

      <View style={styles.taskContent}>
        <View style={styles.taskHeader}>
          <Icon
            name={getCategoryIcon(task.category)}
            size={20}
            color={task.completed ? theme.custom.colors.textMuted : categoryColor}
          />
          <Text
            style={[
              styles.taskTitle,
              { color: task.completed ? theme.custom.colors.textMuted : theme.custom.colors.textPrimary },
              task.completed && styles.taskTitleCompleted,
            ]}
          >
            {task.title}
          </Text>
        </View>

        <Text
          style={[
            styles.taskTime,
            { color: task.completed ? theme.custom.colors.textMuted : theme.custom.colors.textSecondary },
          ]}
        >
          {task.time} • {task.duration}
          {task.completed && ' • Complété'}
        </Text>
      </View>

      <TouchableOpacity
        style={[
          styles.completeButton,
          {
            backgroundColor: task.completed
              ? colors.success + '20'
              : categoryColor,
          },
        ]}
        onPress={onComplete}
        activeOpacity={0.7}
      >
        {task.completed ? (
          <Icon name="check" size={16} color={colors.success} />
        ) : (
          <Text style={styles.completeButtonText}>Go!</Text>
        )}
      </TouchableOpacity>
    </View>
  );
};

export const CalendarScreen: React.FC = () => {
  const theme = useTheme() as AppTheme;
  const today = new Date().toISOString().split('T')[0];
  const [selectedDate, setSelectedDate] = useState(today);
  const [tasks, setTasks] = useState(MOCK_TASKS);

  // Marked dates for calendar
  const markedDates = {
    [today]: {
      selected: true,
      selectedColor: colors.primary[500],
    },
    '2026-02-05': { marked: true, dotColor: colors.primary[500] },
    '2026-02-06': { marked: true, dotColor: colors.primary[500] },
    '2026-02-09': { marked: true, dotColor: colors.success },
    '2026-02-10': { marked: true, dotColor: colors.primary[500] },
    '2026-02-13': { marked: true, dotColor: colors.success },
  };

  const handleCompleteTask = (taskId: string) => {
    setTasks(tasks.map(t =>
      t.id === taskId ? { ...t, completed: !t.completed } : t
    ));
  };

  const incompleteTasks = tasks.filter(t => !t.completed);
  const completedTasks = tasks.filter(t => t.completed);

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: theme.colors.background }]}
      edges={['top']}
    >
      {/* Header */}
      <View style={[styles.header, { backgroundColor: theme.colors.surface }]}>
        <Text style={[styles.headerTitle, { color: theme.custom.colors.textPrimary }]}>
          📅 Calendrier
        </Text>
      </View>

      <ScrollView
        style={styles.scrollView}
        showsVerticalScrollIndicator={false}
      >
        {/* Calendar */}
        <Calendar
          current={today}
          markedDates={markedDates}
          onDayPress={(day) => setSelectedDate(day.dateString)}
          theme={{
            backgroundColor: theme.colors.surface,
            calendarBackground: theme.colors.surface,
            textSectionTitleColor: theme.custom.colors.textSecondary,
            selectedDayBackgroundColor: colors.primary[500],
            selectedDayTextColor: colors.white,
            todayTextColor: colors.primary[500],
            dayTextColor: theme.custom.colors.textPrimary,
            textDisabledColor: theme.custom.colors.textMuted,
            dotColor: colors.primary[500],
            arrowColor: colors.primary[500],
            monthTextColor: theme.custom.colors.textPrimary,
            textDayFontWeight: '400',
            textMonthFontWeight: '600',
            textDayHeaderFontWeight: '500',
            textDayFontSize: 14,
            textMonthFontSize: 18,
            textDayHeaderFontSize: 12,
          }}
          style={styles.calendar}
        />

        {/* Legend */}
        <View style={[styles.legend, { backgroundColor: theme.colors.surface }]}>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: colors.primary[500] }]} />
            <Text style={[styles.legendText, { color: theme.custom.colors.textSecondary }]}>
              Guitare
            </Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: colors.success }]} />
            <Text style={[styles.legendText, { color: theme.custom.colors.textSecondary }]}>
              Course
            </Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: colors.warning }]} />
            <Text style={[styles.legendText, { color: theme.custom.colors.textSecondary }]}>
              Lecture
            </Text>
          </View>
        </View>

        {/* Today's Tasks */}
        <View style={styles.tasksSection}>
          <View style={styles.tasksSectionHeader}>
            <Text style={[styles.sectionTitle, { color: theme.custom.colors.textPrimary }]}>
              Aujourd'hui
            </Text>
            <Text style={[styles.taskCount, { color: theme.custom.colors.textSecondary }]}>
              {tasks.length} tâches
            </Text>
          </View>

          {/* Incomplete tasks first */}
          {incompleteTasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onComplete={() => handleCompleteTask(task.id)}
            />
          ))}

          {/* Completed tasks */}
          {completedTasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onComplete={() => handleCompleteTask(task.id)}
            />
          ))}
        </View>
      </ScrollView>
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
  scrollView: {
    flex: 1,
  },
  calendar: {
    borderBottomWidth: 1,
    borderBottomColor: colors.gray[200],
  },
  legend: {
    flexDirection: 'row',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray[200],
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: spacing.lg,
  },
  legendDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: spacing.xs,
  },
  legendText: {
    fontSize: 12,
  },
  tasksSection: {
    padding: spacing.md,
  },
  tasksSectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  sectionTitle: {
    ...typography.h4,
  },
  taskCount: {
    fontSize: 14,
  },
  taskCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: borderRadius.lg,
    marginBottom: spacing.sm,
    overflow: 'hidden',
  },
  taskCardCompleted: {
    opacity: 0.7,
  },
  taskAccent: {
    width: 4,
    height: '100%',
  },
  taskContent: {
    flex: 1,
    padding: spacing.md,
  },
  taskHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  taskTitle: {
    ...typography.body,
    fontWeight: '500',
    marginLeft: spacing.sm,
  },
  taskTitleCompleted: {
    textDecorationLine: 'line-through',
  },
  taskTime: {
    fontSize: 12,
    marginTop: 4,
    marginLeft: 28,
  },
  completeButton: {
    width: 50,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.md,
  },
  completeButtonText: {
    color: colors.white,
    fontSize: 12,
    fontWeight: '600',
  },
});
