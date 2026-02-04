import React from 'react';
import { View, FlatList, StyleSheet, RefreshControl } from 'react-native';
import { Text, FAB, Card, Chip, ActivityIndicator } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useDreams } from '../../hooks/useDreams';
import { useTodayTasks } from '../../hooks/useCalendar';
import { theme } from '../../theme';

export function HomeScreen({ navigation }: any) {
  const { data: dreamsData, isLoading: dreamsLoading, refetch: refetchDreams } = useDreams({ status: 'active' });
  const { data: todayData, isLoading: tasksLoading } = useTodayTasks();

  const dreams = dreamsData?.data?.dreams || [];
  const todayTasks = todayData?.data?.tasks || [];

  const handleRefresh = () => {
    refetchDreams();
  };

  if (dreamsLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={theme.colors.primary} />
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text variant="headlineMedium" style={styles.headerTitle}>
          My Dreams
        </Text>
        <Text variant="bodyMedium" style={styles.headerSubtitle}>
          {todayTasks.length} task{todayTasks.length !== 1 ? 's' : ''} today
        </Text>
      </View>

      <FlatList
        data={dreams}
        renderItem={({ item }) => (
          <Card style={styles.card} onPress={() => console.log('Dream tapped:', item.id)}>
            <Card.Content>
              <View style={styles.cardHeader}>
                <Text variant="titleLarge">{item.title}</Text>
                {item.category && (
                  <Chip mode="outlined" compact>
                    {item.category}
                  </Chip>
                )}
              </View>
              <Text variant="bodyMedium" numberOfLines={2} style={styles.description}>
                {item.description}
              </Text>
              <View style={styles.progress}>
                <Text variant="bodySmall">
                  Progress: {item.completionPercentage || 0}%
                </Text>
                <Text variant="bodySmall">
                  Priority: {item.priority}/5
                </Text>
              </View>
            </Card.Content>
          </Card>
        )}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={dreamsLoading} onRefresh={handleRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text variant="titleLarge" style={styles.emptyTitle}>
              No dreams yet
            </Text>
            <Text variant="bodyMedium" style={styles.emptySubtext}>
              Start by creating your first dream
            </Text>
          </View>
        }
      />

      <FAB
        icon="plus"
        style={styles.fab}
        onPress={() => console.log('Create dream')}
        label="New Dream"
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    padding: 20,
    backgroundColor: '#ffffff',
  },
  headerTitle: {
    fontWeight: 'bold',
    color: theme.colors.primary,
  },
  headerSubtitle: {
    marginTop: 4,
    color: '#666',
  },
  listContent: {
    padding: 16,
  },
  card: {
    marginBottom: 16,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  description: {
    color: '#666',
    marginBottom: 12,
  },
  progress: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  empty: {
    padding: 48,
    alignItems: 'center',
  },
  emptyTitle: {
    color: '#666',
  },
  emptySubtext: {
    marginTop: 8,
    color: '#999',
  },
  fab: {
    position: 'absolute',
    right: 16,
    bottom: 16,
    backgroundColor: theme.colors.primary,
  },
});
