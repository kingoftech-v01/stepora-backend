import React, { useState } from 'react';
import { View, FlatList, StyleSheet } from 'react-native';
import { Text, Card, Avatar, Button, Chip, FAB, Portal, Dialog, TextInput } from 'react-native-paper';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { useNavigation } from '@react-navigation/native';

type FilterType = 'my' | 'public' | 'recommended';

export const CirclesScreen = () => {
  const navigation = useNavigation();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<FilterType>('recommended');
  const [createDialogVisible, setCreateDialogVisible] = useState(false);
  const [newCircle, setNewCircle] = useState({
    name: '',
    description: '',
    category: 'career',
    isPublic: true,
  });

  const { data: circles, isLoading } = useQuery({
    queryKey: ['circles', filter],
    queryFn: async () => {
      const response = await api.get(`/circles?filter=${filter}`);
      return response.data.circles;
    },
  });

  const createCircleMutation = useMutation({
    mutationFn: async () => {
      await api.post('/circles', newCircle);
    },
    onSuccess: () => {
      setCreateDialogVisible(false);
      setNewCircle({ name: '', description: '', category: 'career', isPublic: true });
      queryClient.invalidateQueries({ queryKey: ['circles'] });
    },
  });

  const joinCircleMutation = useMutation({
    mutationFn: async (circleId: string) => {
      await api.post(`/circles/${circleId}/join`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['circles'] });
    },
  });

  const renderCircle = ({ item }: any) => (
    <Card
      style={styles.circleCard}
      onPress={() => navigation.navigate('CircleDetail' as never, { circleId: item.id } as never)}
    >
      <Card.Content>
        <View style={styles.circleHeader}>
          <Text variant="titleLarge" style={styles.circleName}>
            {item.name}
          </Text>
          {item.category && (
            <Chip icon="tag" compact>
              {item.category}
            </Chip>
          )}
        </View>

        <Text variant="bodyMedium" style={styles.circleDescription} numberOfLines={2}>
          {item.description}
        </Text>

        <View style={styles.circleFooter}>
          <View style={styles.memberAvatars}>
            {item.memberAvatars?.slice(0, 3).map((avatar: string, index: number) => (
              <Avatar.Image
                key={index}
                size={30}
                source={{ uri: avatar }}
                style={[styles.memberAvatar, { marginLeft: index > 0 ? -10 : 0 }]}
              />
            ))}
            <Text variant="bodySmall" style={styles.memberCount}>
              {item.memberCount} / {item.maxMembers} members
            </Text>
          </View>

          <Button
            mode="contained"
            compact
            onPress={() => joinCircleMutation.mutate(item.id)}
            loading={joinCircleMutation.isPending}
          >
            Join
          </Button>
        </View>
      </Card.Content>
    </Card>
  );

  return (
    <View style={styles.container}>
      {/* Filters */}
      <View style={styles.filters}>
        <Chip selected={filter === 'my'} onPress={() => setFilter('my')} style={styles.filterChip}>
          My Circles
        </Chip>
        <Chip
          selected={filter === 'recommended'}
          onPress={() => setFilter('recommended')}
          style={styles.filterChip}
        >
          Recommended
        </Chip>
        <Chip
          selected={filter === 'public'}
          onPress={() => setFilter('public')}
          style={styles.filterChip}
        >
          Public
        </Chip>
      </View>

      {/* Circles List */}
      <FlatList
        data={circles}
        renderItem={renderCircle}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Text variant="headlineSmall" style={styles.emptyTitle}>
              No circles found
            </Text>
            <Text variant="bodyMedium" style={styles.emptyText}>
              Create your own circle to get started!
            </Text>
          </View>
        }
      />

      {/* Create FAB */}
      <FAB
        icon="plus"
        style={styles.fab}
        onPress={() => setCreateDialogVisible(true)}
        label="Create Circle"
      />

      {/* Create Dialog */}
      <Portal>
        <Dialog visible={createDialogVisible} onDismiss={() => setCreateDialogVisible(false)}>
          <Dialog.Title>Create a Dream Circle</Dialog.Title>
          <Dialog.Content>
            <TextInput
              label="Circle Name"
              value={newCircle.name}
              onChangeText={(text) => setNewCircle({ ...newCircle, name: text })}
              style={styles.input}
            />
            <TextInput
              label="Description"
              value={newCircle.description}
              onChangeText={(text) => setNewCircle({ ...newCircle, description: text })}
              multiline
              numberOfLines={3}
              style={styles.input}
            />
            <View style={styles.switchRow}>
              <Text>Public Circle</Text>
              <Chip
                selected={newCircle.isPublic}
                onPress={() => setNewCircle({ ...newCircle, isPublic: !newCircle.isPublic })}
              >
                {newCircle.isPublic ? 'Yes' : 'No'}
              </Chip>
            </View>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setCreateDialogVisible(false)}>Cancel</Button>
            <Button
              onPress={() => createCircleMutation.mutate()}
              loading={createCircleMutation.isPending}
            >
              Create
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  filters: {
    flexDirection: 'row',
    padding: 15,
    gap: 10,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  filterChip: {
    flex: 1,
  },
  list: {
    padding: 15,
  },
  circleCard: {
    marginBottom: 15,
  },
  circleHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  circleName: {
    fontWeight: 'bold',
    flex: 1,
  },
  circleDescription: {
    color: '#666',
    marginBottom: 12,
  },
  circleFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  memberAvatars: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  memberAvatar: {
    borderWidth: 2,
    borderColor: '#fff',
  },
  memberCount: {
    marginLeft: 12,
    color: '#666',
  },
  fab: {
    position: 'absolute',
    right: 16,
    bottom: 16,
  },
  emptyState: {
    padding: 40,
    alignItems: 'center',
  },
  emptyTitle: {
    marginBottom: 8,
    textAlign: 'center',
  },
  emptyText: {
    color: '#999',
    textAlign: 'center',
  },
  input: {
    marginBottom: 12,
  },
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
  },
});
