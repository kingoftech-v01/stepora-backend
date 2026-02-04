import React, { useState } from 'react';
import { View, ScrollView, StyleSheet, FlatList } from 'react-native';
import {
  Text,
  Card,
  Avatar,
  Button,
  Searchbar,
  Chip,
  Surface,
  IconButton,
} from 'react-native-paper';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';

type TabType = 'feed' | 'friends' | 'search';

interface ActivityItem {
  id: string;
  type: string;
  user: {
    id: string;
    username: string;
    avatar?: string;
  };
  content: any;
  createdAt: string;
}

export const SocialScreen = () => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabType>('feed');
  const [searchQuery, setSearchQuery] = useState('');

  const { data: feed } = useQuery({
    queryKey: ['friendsFeed'],
    queryFn: async () => {
      const response = await api.get('/social/feed/friends');
      return response.data.activities;
    },
    enabled: activeTab === 'feed',
  });

  const { data: friends } = useQuery({
    queryKey: ['friends'],
    queryFn: async () => {
      const response = await api.get('/social/friends');
      return response.data.friends;
    },
    enabled: activeTab === 'friends',
  });

  const { data: requests } = useQuery({
    queryKey: ['friendRequests'],
    queryFn: async () => {
      const response = await api.get('/social/friends/requests/pending');
      return response.data.requests;
    },
    enabled: activeTab === 'friends',
  });

  const { data: searchResults, refetch: searchUsers } = useQuery({
    queryKey: ['userSearch', searchQuery],
    queryFn: async () => {
      if (!searchQuery || searchQuery.length < 2) return [];
      const response = await api.get(`/social/users/search?q=${searchQuery}`);
      return response.data.users;
    },
    enabled: activeTab === 'search' && searchQuery.length >= 2,
  });

  const sendRequestMutation = useMutation({
    mutationFn: async (targetUserId: string) => {
      await api.post('/social/friends/request', { targetUserId });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['userSearch'] });
      queryClient.invalidateQueries({ queryKey: ['friends'] });
    },
  });

  const acceptRequestMutation = useMutation({
    mutationFn: async (requestId: string) => {
      await api.post(`/social/friends/accept/${requestId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['friendRequests'] });
      queryClient.invalidateQueries({ queryKey: ['friends'] });
    },
  });

  const rejectRequestMutation = useMutation({
    mutationFn: async (requestId: string) => {
      await api.post(`/social/friends/reject/${requestId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['friendRequests'] });
    },
  });

  const followMutation = useMutation({
    mutationFn: async (targetUserId: string) => {
      await api.post('/social/follow', { targetUserId });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['userSearch'] });
    },
  });

  const getActivityMessage = (activity: ActivityItem) => {
    switch (activity.type) {
      case 'task_completed':
        return `a complété une tâche: "${activity.content.taskTitle}"`;
      case 'dream_completed':
        return `a réalisé un rêve: "${activity.content.dreamTitle}" 🎉`;
      case 'milestone_reached':
        return `a atteint un jalon: ${activity.content.milestone}`;
      case 'buddy_matched':
        return `a trouvé un Dream Buddy!`;
      case 'circle_joined':
        return `a rejoint le cercle "${activity.content.circleName}"`;
      default:
        return 'a une nouvelle activité';
    }
  };

  const renderFeed = () => (
    <FlatList
      data={feed}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => (
        <Card style={styles.activityCard}>
          <Card.Content>
            <View style={styles.activityHeader}>
              <Avatar.Image size={40} source={{ uri: item.user.avatar }} />
              <View style={styles.activityInfo}>
                <Text variant="bodyMedium" style={styles.activityUser}>
                  {item.user.username}
                </Text>
                <Text variant="bodySmall" style={styles.activityText}>
                  {getActivityMessage(item)}
                </Text>
                <Text variant="bodySmall" style={styles.activityTime}>
                  {new Date(item.createdAt).toLocaleDateString('fr-FR')}
                </Text>
              </View>
            </View>
          </Card.Content>
        </Card>
      )}
      ListEmptyComponent={
        <View style={styles.emptyState}>
          <Text variant="bodyLarge" style={styles.emptyText}>
            Aucune activité récente
          </Text>
          <Text variant="bodySmall" style={styles.emptySubtext}>
            Ajoute des amis pour voir leurs progrès !
          </Text>
        </View>
      }
    />
  );

  const renderFriends = () => (
    <ScrollView>
      {/* Pending Requests */}
      {requests && requests.length > 0 && (
        <View style={styles.section}>
          <Text variant="titleMedium" style={styles.sectionTitle}>
            Demandes en attente ({requests.length})
          </Text>
          {requests.map((request: any) => (
            <Card key={request.id} style={styles.friendCard}>
              <Card.Content>
                <View style={styles.friendRow}>
                  <Avatar.Image size={50} source={{ uri: request.sender.avatar }} />
                  <View style={styles.friendInfo}>
                    <Text variant="bodyLarge">{request.sender.username}</Text>
                  </View>
                  <View style={styles.friendActions}>
                    <IconButton
                      icon="check"
                      mode="contained"
                      size={20}
                      onPress={() => acceptRequestMutation.mutate(request.id)}
                    />
                    <IconButton
                      icon="close"
                      size={20}
                      onPress={() => rejectRequestMutation.mutate(request.id)}
                    />
                  </View>
                </View>
              </Card.Content>
            </Card>
          ))}
        </View>
      )}

      {/* Friends List */}
      <View style={styles.section}>
        <Text variant="titleMedium" style={styles.sectionTitle}>
          Mes amis ({friends?.length || 0})
        </Text>
        {friends?.map((friend: any) => (
          <Card key={friend.id} style={styles.friendCard}>
            <Card.Content>
              <View style={styles.friendRow}>
                <Avatar.Image size={50} source={{ uri: friend.avatar }} />
                <View style={styles.friendInfo}>
                  <Text variant="bodyLarge">{friend.username}</Text>
                  <Text variant="bodySmall" style={styles.friendTitle}>
                    {friend.title} • Niveau {friend.currentLevel}
                  </Text>
                  <Text variant="bodySmall" style={styles.friendInfluence}>
                    {friend.influenceScore} influence
                  </Text>
                </View>
              </View>
            </Card.Content>
          </Card>
        ))}
        {(!friends || friends.length === 0) && (
          <View style={styles.emptyState}>
            <Text variant="bodyMedium" style={styles.emptyText}>
              Pas encore d'amis
            </Text>
          </View>
        )}
      </View>
    </ScrollView>
  );

  const renderSearch = () => (
    <View style={styles.searchContainer}>
      <Searchbar
        placeholder="Rechercher des utilisateurs..."
        onChangeText={setSearchQuery}
        value={searchQuery}
        style={styles.searchBar}
      />

      {searchResults && searchResults.length > 0 && (
        <FlatList
          data={searchResults}
          keyExtractor={(item: any) => item.id}
          renderItem={({ item }) => (
            <Card style={styles.userCard}>
              <Card.Content>
                <View style={styles.userRow}>
                  <Avatar.Image size={50} source={{ uri: item.avatar }} />
                  <View style={styles.userInfo}>
                    <Text variant="bodyLarge">{item.username}</Text>
                    <Text variant="bodySmall" style={styles.userTitle}>
                      {item.title}
                    </Text>
                    <Text variant="bodySmall" style={styles.userInfluence}>
                      {item.influenceScore} influence
                    </Text>
                  </View>
                  <View style={styles.userActions}>
                    {item.isFriend ? (
                      <Chip icon="check">Ami</Chip>
                    ) : (
                      <Button
                        mode="contained"
                        compact
                        onPress={() => sendRequestMutation.mutate(item.id)}
                      >
                        Ajouter
                      </Button>
                    )}
                    {!item.isFollowing && (
                      <Button
                        mode="outlined"
                        compact
                        onPress={() => followMutation.mutate(item.id)}
                        style={styles.followButton}
                      >
                        Suivre
                      </Button>
                    )}
                  </View>
                </View>
              </Card.Content>
            </Card>
          )}
        />
      )}

      {searchQuery.length >= 2 && (!searchResults || searchResults.length === 0) && (
        <View style={styles.emptyState}>
          <Text variant="bodyMedium" style={styles.emptyText}>
            Aucun résultat
          </Text>
        </View>
      )}
    </View>
  );

  return (
    <View style={styles.container}>
      {/* Tabs */}
      <View style={styles.tabs}>
        <Chip
          selected={activeTab === 'feed'}
          onPress={() => setActiveTab('feed')}
          style={styles.tab}
        >
          Activités
        </Chip>
        <Chip
          selected={activeTab === 'friends'}
          onPress={() => setActiveTab('friends')}
          style={styles.tab}
        >
          Amis
        </Chip>
        <Chip
          selected={activeTab === 'search'}
          onPress={() => setActiveTab('search')}
          style={styles.tab}
        >
          Rechercher
        </Chip>
      </View>

      {/* Content */}
      <View style={styles.content}>
        {activeTab === 'feed' && renderFeed()}
        {activeTab === 'friends' && renderFriends()}
        {activeTab === 'search' && renderSearch()}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  tabs: {
    flexDirection: 'row',
    padding: 15,
    gap: 10,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  tab: {
    flex: 1,
  },
  content: {
    flex: 1,
  },
  activityCard: {
    margin: 10,
    marginBottom: 0,
  },
  activityHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  activityInfo: {
    marginLeft: 12,
    flex: 1,
  },
  activityUser: {
    fontWeight: '600',
  },
  activityText: {
    marginTop: 4,
    color: '#666',
  },
  activityTime: {
    marginTop: 4,
    color: '#999',
  },
  section: {
    padding: 15,
  },
  sectionTitle: {
    fontWeight: 'bold',
    marginBottom: 12,
  },
  friendCard: {
    marginBottom: 10,
  },
  friendRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  friendInfo: {
    marginLeft: 12,
    flex: 1,
  },
  friendTitle: {
    color: '#666',
    marginTop: 2,
  },
  friendInfluence: {
    color: '#999',
    marginTop: 2,
  },
  friendActions: {
    flexDirection: 'row',
  },
  searchContainer: {
    flex: 1,
  },
  searchBar: {
    margin: 15,
  },
  userCard: {
    marginHorizontal: 15,
    marginBottom: 10,
  },
  userRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  userInfo: {
    marginLeft: 12,
    flex: 1,
  },
  userTitle: {
    color: '#666',
    marginTop: 2,
  },
  userInfluence: {
    color: '#999',
    marginTop: 2,
  },
  userActions: {
    gap: 8,
  },
  followButton: {
    marginTop: 4,
  },
  emptyState: {
    padding: 40,
    alignItems: 'center',
  },
  emptyText: {
    color: '#999',
    textAlign: 'center',
  },
  emptySubtext: {
    color: '#bbb',
    marginTop: 8,
    textAlign: 'center',
  },
});
