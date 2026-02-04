import React, { useState } from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { Text, Card, Chip, ActivityIndicator } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Calendar } from 'react-native-calendars';
import { format } from 'date-fns';
import { useCalendar } from '../../hooks/useCalendar';
import { theme } from '../../theme';

export function CalendarScreen() {
  const [selectedDate, setSelectedDate] = useState(format(new Date(), 'yyyy-MM-dd'));

  const startOfMonth = format(new Date(), 'yyyy-MM-01');
  const endOfMonth = format(new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0), 'yyyy-MM-dd');

  const { data: calendarData, isLoading } = useCalendar(startOfMonth, endOfMonth);

  const tasks = calendarData?.data?.tasks || {};
  const selectedTasks = tasks[selectedDate] || [];

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text variant="headlineMedium" style={styles.headerTitle}>
          Calendar
        </Text>
      </View>

      <Calendar
        current={selectedDate}
        onDayPress={(day) => setSelectedDate(day.dateString)}
        markedDates={{
          [selectedDate]: { selected: true, selectedColor: theme.colors.primary },
          ...Object.keys(tasks).reduce((acc, date) => {
            if (date !== selectedDate && tasks[date].length > 0) {
              acc[date] = { marked: true, dotColor: theme.colors.primary };
            }
            return acc;
          }, {} as any),
        }}
        theme={{
          selectedDayBackgroundColor: theme.colors.primary,
          todayTextColor: theme.colors.primary,
          arrowColor: theme.colors.primary,
        }}
      />

      <ScrollView style={styles.tasksList}>
        <Text variant="titleMedium" style={styles.sectionTitle}>
          Tasks for {format(new Date(selectedDate), 'MMM dd, yyyy')}
        </Text>

        {isLoading ? (
          <ActivityIndicator style={styles.loader} />
        ) : selectedTasks.length > 0 ? (
          selectedTasks.map((task: any) => (
            <Card key={task.id} style={styles.taskCard}>
              <Card.Content>
                <View style={styles.taskHeader}>
                  <Text variant="titleMedium">{task.title}</Text>
                  <Chip compact>{task.status}</Chip>
                </View>
                {task.scheduledTime && (
                  <Text variant="bodySmall" style={styles.taskTime}>
                    ⏰ {task.scheduledTime}
                  </Text>
                )}
                <Text variant="bodySmall" style={styles.taskGoal}>
                  {task.goal?.dream?.title}
                </Text>
              </Card.Content>
            </Card>
          ))
        ) : (
          <View style={styles.emptyState}>
            <Text variant="bodyMedium" style={styles.emptyText}>
              No tasks for this day
            </Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    padding: 20,
    backgroundColor: '#ffffff',
  },
  headerTitle: {
    fontWeight: 'bold',
    color: theme.colors.primary,
  },
  tasksList: {
    flex: 1,
    padding: 16,
  },
  sectionTitle: {
    marginBottom: 16,
    color: '#333',
  },
  taskCard: {
    marginBottom: 12,
    elevation: 2,
  },
  taskHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  taskTime: {
    color: '#666',
    marginBottom: 4,
  },
  taskGoal: {
    color: '#999',
  },
  loader: {
    marginTop: 32,
  },
  emptyState: {
    padding: 32,
    alignItems: 'center',
  },
  emptyText: {
    color: '#999',
  },
});
