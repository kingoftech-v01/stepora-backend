import React, { useState } from 'react';
import { View, ScrollView, StyleSheet, TouchableOpacity, RefreshControl } from 'react-native';
import { Text, Card, Avatar, Surface, useTheme, Chip } from 'react-native-paper';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { useAuthStore } from '../../stores/authStore';

type LeaderboardType = 'global' | 'friends' | 'local' | 'category';

interface LeaderboardEntry {
  userId: string;
  username: string;
  avatar?: string;
  influenceScore: number;
  currentLevel: number;
  title: string;
  rank: number;
}

export const LeaderboardScreen = () => {
  const theme = useTheme();
  const user = useAuthStore((state) => state.user);
  const [selectedType, setSelectedType] = useState<LeaderboardType>('global');

  const { data: leaderboard, isLoading, refetch } = useQuery({
    queryKey: ['leaderboard', selectedType],
    queryFn: async () => {
      const endpoint =
        selectedType === 'global'
          ? '/gamification/leaderboards/global'
          : selectedType === 'friends'
          ? '/gamification/leaderboards/friends'
          : selectedType === 'local'
          ? '/gamification/leaderboards/local'
          : '/gamification/leaderboards/category/career';

      const response = await api.get(endpoint);
      return response.data.leaderboard;
    },
  });

  const renderPodium = () => {
    if (!leaderboard?.entries || leaderboard.entries.length < 3) return null;

    const top3 = leaderboard.entries.slice(0, 3);
    const [gold, silver, bronze] = [top3[0], top3[1], top3[2]];

    return (
      <View style={styles.podiumContainer}>
        {/* Silver - 2nd place */}
        {silver && (
          <View style={[styles.podiumItem, styles.silverPodium]}>
            <View style={styles.rankBadge}>
              <Text style={styles.rankText}>2</Text>
            </View>
            <Avatar.Image size={50} source={{ uri: silver.avatar }} />
            <Text style={styles.podiumName} numberOfLines={1}>
              {silver.username}
            </Text>
            <Text style={styles.podiumScore}>{silver.influenceScore}</Text>
            <Text style={styles.podiumTitle}>{silver.title}</Text>
          </View>
        )}

        {/* Gold - 1st place */}
        {gold && (
          <View style={[styles.podiumItem, styles.goldPodium]}>
            <View style={[styles.rankBadge, styles.goldBadge]}>
              <Text style={styles.rankText}>👑</Text>
            </View>
            <Avatar.Image size={70} source={{ uri: gold.avatar }} />
            <Text style={[styles.podiumName, styles.goldName]} numberOfLines={1}>
              {gold.username}
            </Text>
            <Text style={[styles.podiumScore, styles.goldScore]}>{gold.influenceScore}</Text>
            <Text style={styles.podiumTitle}>{gold.title}</Text>
          </View>
        )}

        {/* Bronze - 3rd place */}
        {bronze && (
          <View style={[styles.podiumItem, styles.bronzePodium]}>
            <View style={styles.rankBadge}>
              <Text style={styles.rankText}>3</Text>
            </View>
            <Avatar.Image size={50} source={{ uri: bronze.avatar }} />
            <Text style={styles.podiumName} numberOfLines={1}>
              {bronze.username}
            </Text>
            <Text style={styles.podiumScore}>{bronze.influenceScore}</Text>
            <Text style={styles.podiumTitle}>{bronze.title}</Text>
          </View>
        )}
      </View>
    );
  };

  const renderEntry = (entry: LeaderboardEntry, index: number) => {
    const isCurrentUser = entry.userId === user?.id;

    return (
      <Surface
        key={entry.userId}
        style={[styles.entryCard, isCurrentUser && styles.currentUserCard]}
        elevation={isCurrentUser ? 2 : 0}
      >
        <View style={styles.rankCircle}>
          <Text style={styles.rankNumber}>{entry.rank}</Text>
        </View>

        <Avatar.Image size={40} source={{ uri: entry.avatar }} />

        <View style={styles.entryInfo}>
          <Text style={[styles.entryName, isCurrentUser && styles.currentUserName]}>
            {entry.username} {isCurrentUser && '(You)'}
          </Text>
          <Text style={styles.entryTitle}>{entry.title}</Text>
        </View>

        <View style={styles.entryStats}>
          <Text style={styles.entryScore}>{entry.influenceScore}</Text>
          <Text style={styles.entryLabel}>Influence</Text>
        </View>

        <View style={styles.entryStats}>
          <Text style={styles.entryLevel}>Lv {entry.currentLevel}</Text>
        </View>
      </Surface>
    );
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text variant="headlineMedium" style={styles.title}>
          Classement
        </Text>

        {leaderboard?.myRank && (
          <Chip icon="trophy" style={styles.myRankChip}>
            Ton rang: #{leaderboard.myRank}
          </Chip>
        )}
      </View>

      {/* Filter Tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterContainer}>
        <Chip
          selected={selectedType === 'global'}
          onPress={() => setSelectedType('global')}
          style={styles.filterChip}
        >
          Global
        </Chip>
        <Chip
          selected={selectedType === 'friends'}
          onPress={() => setSelectedType('friends')}
          style={styles.filterChip}
        >
          Amis
        </Chip>
        <Chip
          selected={selectedType === 'local'}
          onPress={() => setSelectedType('local')}
          style={styles.filterChip}
        >
          Local
        </Chip>
        <Chip
          selected={selectedType === 'category'}
          onPress={() => setSelectedType('category')}
          style={styles.filterChip}
        >
          Catégorie
        </Chip>
      </ScrollView>

      {/* Leaderboard Content */}
      <ScrollView
        style={styles.content}
        refreshControl={<RefreshControl refreshing={isLoading} onRefresh={refetch} />}
      >
        {/* Podium for top 3 */}
        {selectedType === 'global' && renderPodium()}

        {/* Rest of the list */}
        <View style={styles.listContainer}>
          {leaderboard?.entries
            ?.slice(selectedType === 'global' ? 3 : 0)
            .map((entry: LeaderboardEntry, index: number) =>
              renderEntry(entry, selectedType === 'global' ? index + 3 : index)
            )}
        </View>

        {!isLoading && (!leaderboard?.entries || leaderboard.entries.length === 0) && (
          <View style={styles.emptyState}>
            <Text variant="bodyLarge" style={styles.emptyText}>
              Aucun résultat pour ce classement
            </Text>
          </View>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    padding: 20,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  title: {
    fontWeight: 'bold',
    marginBottom: 10,
  },
  myRankChip: {
    alignSelf: 'flex-start',
  },
  filterContainer: {
    padding: 15,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  filterChip: {
    marginRight: 10,
  },
  content: {
    flex: 1,
  },
  podiumContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'flex-end',
    padding: 20,
    backgroundColor: '#fff',
    marginBottom: 10,
  },
  podiumItem: {
    alignItems: 'center',
    marginHorizontal: 10,
    padding: 15,
    borderRadius: 12,
    width: 100,
  },
  goldPodium: {
    backgroundColor: '#FFD700',
    height: 180,
    justifyContent: 'center',
  },
  silverPodium: {
    backgroundColor: '#C0C0C0',
    height: 150,
    justifyContent: 'flex-end',
  },
  bronzePodium: {
    backgroundColor: '#CD7F32',
    height: 130,
    justifyContent: 'flex-end',
  },
  rankBadge: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#fff',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 10,
  },
  goldBadge: {
    backgroundColor: '#FFF8DC',
  },
  rankText: {
    fontWeight: 'bold',
    fontSize: 16,
  },
  podiumName: {
    marginTop: 8,
    fontWeight: '600',
    fontSize: 14,
    textAlign: 'center',
  },
  goldName: {
    fontSize: 16,
  },
  podiumScore: {
    fontSize: 16,
    fontWeight: 'bold',
    marginTop: 4,
  },
  goldScore: {
    fontSize: 18,
  },
  podiumTitle: {
    fontSize: 11,
    color: '#666',
    marginTop: 2,
  },
  listContainer: {
    padding: 15,
  },
  entryCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    marginBottom: 10,
    borderRadius: 12,
    backgroundColor: '#fff',
  },
  currentUserCard: {
    borderWidth: 2,
    borderColor: '#6200ee',
  },
  rankCircle: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#f0f0f0',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  rankNumber: {
    fontWeight: 'bold',
    color: '#666',
  },
  entryInfo: {
    flex: 1,
    marginLeft: 12,
  },
  entryName: {
    fontSize: 16,
    fontWeight: '600',
  },
  currentUserName: {
    color: '#6200ee',
  },
  entryTitle: {
    fontSize: 13,
    color: '#666',
    marginTop: 2,
  },
  entryStats: {
    alignItems: 'center',
    marginLeft: 12,
  },
  entryScore: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  entryLabel: {
    fontSize: 11,
    color: '#666',
  },
  entryLevel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6200ee',
  },
  emptyState: {
    padding: 40,
    alignItems: 'center',
  },
  emptyText: {
    color: '#999',
    textAlign: 'center',
  },
});
